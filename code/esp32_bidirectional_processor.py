#!/usr/bin/env python3
"""
ESP32 Bidirectional Communication via REST API - Sensor Data + Prediction Results
Menerima data sensor dari ESP32 via HTTP POST, jalankan inference, kirim hasil prediksi kembali via JSON response
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import numpy as np
import time
import sys
from datetime import datetime
import csv
import json
import socket
import os
from collections import deque

# TensorFlow Lite import
try:
    import tensorflow as tf
    TFLITE_AVAILABLE = True
except ImportError:
    print("⚠️ TensorFlow not available. Install with: pip install tensorflow")
    TFLITE_AVAILABLE = False

class ESP32BidirectionalProcessor:
    def __init__(self, host='0.0.0.0', port=5000, model_path='food_model_250.tflite', save_to_file=True, max_history=100):
        """
        Inisialisasi processor untuk komunikasi dua arah dengan ESP32 via REST API
        
        Args:
            host: Host untuk Flask server (0.0.0.0 untuk listen semua interface)
            port: Port untuk Flask server (default: 5000)
            model_path: Path ke file model TensorFlow Lite
            save_to_file: Apakah data disimpan ke file
            max_history: Jumlah maksimal data yang disimpan dalam memory
        """
        self.host = host
        self.port = port
        self.model_path = model_path
        self.save_to_file = save_to_file
        self.max_history = max_history
        
        # Flask app setup
        self.app = Flask(__name__)
        CORS(self.app)  # Enable CORS untuk cross-origin requests
        
        # Data storage
        self.sensor_data_log = []
        self.prediction_history = deque(maxlen=max_history)  # Store last predictions
        self.csv_filename = f"sensor_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self.predictions_csv_filename = f"predictions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        # Sensor names untuk display (sesuai dengan ESP32 yang hanya punya 2 sensor)
        self.sensor_names = ["MQ2", "MQ3"]
        
        # TensorFlow Lite setup
        self.interpreter = None
        self.input_details = None
        self.output_details = None
        
        # Setup model jika tersedia
        if TFLITE_AVAILABLE:
            self.setup_model()
        else:
            print("⚠️ Running without TensorFlow Lite inference")
        
        # Setup CSV file jika diperlukan
        if self.save_to_file:
            self.setup_csv_file()
            self.setup_predictions_csv_file()
        
        # Setup Flask routes
        self.setup_routes()
        
        # Request counter
        self.request_count = 0
        
        # Last prediction data
        self.last_prediction = None
        self.last_sensor_data = None
        self.last_timestamp = None
    
    def setup_model(self):
        """Setup TensorFlow Lite model"""
        try:
            self.interpreter = tf.lite.Interpreter(model_path=self.model_path)
            self.interpreter.allocate_tensors()
            
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()
            
            print(f"✅ Model loaded: {self.model_path}")
            print(f"Input shape: {self.input_details[0]['shape']}")
            print(f"Output shape: {self.output_details[0]['shape']}")
            
        except Exception as e:
            print(f"❌ Error loading model: {e}")
            print("⚠️ Continuing without model inference")
            self.interpreter = None
    
    def setup_csv_file(self):
        """Setup CSV file untuk menyimpan data sensor"""
        try:
            with open(self.csv_filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                # Write header
                header = ['timestamp', 'datetime', 'sensor_mq2', 'sensor_mq3']
                writer.writerow(header)
            print(f"✅ CSV file created: {self.csv_filename}")
        except Exception as e:
            print(f"❌ Error creating CSV file: {e}")
    
    def setup_predictions_csv_file(self):
        """Setup CSV file khusus untuk menyimpan hasil prediksi"""
        try:
            with open(self.predictions_csv_filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                # Write header
                header = ['timestamp', 'datetime', 'sensor_mq2', 'sensor_mq3', 
                         'prediction', 'prediction_label', 'confidence', 'probabilities']
                writer.writerow(header)
            print(f"✅ Predictions CSV file created: {self.predictions_csv_filename}")
        except Exception as e:
            print(f"❌ Error creating predictions CSV file: {e}")
    
    def save_prediction_to_csv(self, sensor_data, prediction, confidence, probabilities):
        """Simpan hasil prediksi ke CSV khusus predictions"""
        try:
            timestamp = time.time()
            datetime_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            with open(self.predictions_csv_filename, 'a', newline='') as csvfile:
                writer = csv.writer(csvfile)
                # Convert probabilities array to string
                prob_str = ','.join([f"{p:.6f}" for p in probabilities])
                row = [
                    timestamp,
                    datetime_str,
                    float(sensor_data[0]),
                    float(sensor_data[1]),
                    int(prediction),
                    self.interpret_prediction(prediction),
                    float(confidence),
                    prob_str
                ]
                writer.writerow(row)
                
            print(f"💾 Prediction saved to: {self.predictions_csv_filename}")
                
        except Exception as e:
            print(f"❌ Error saving prediction to CSV: {e}")
    
    def get_local_ip(self):
        """Get local IP address untuk ditampilkan ke user"""
        try:
            # Connect to external server untuk mendapatkan local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
    
    def setup_routes(self):
        """Setup Flask routes untuk REST API"""
        
        @self.app.route('/api/sensor-data', methods=['POST'])
        def receive_sensor_data():
            """Endpoint untuk menerima data sensor dari ESP32"""
            try:
                # Parse JSON request
                data = request.get_json()
                
                if not data or 'sensors' not in data:
                    return jsonify({
                        'error': 'Invalid request format. Expected: {"sensors": [val1, val2]}'
                    }), 400
                
                sensor_values = data['sensors']
                
                # Validate sensor data
                if not isinstance(sensor_values, list):
                    return jsonify({'error': 'sensors must be an array'}), 400
                
                if len(sensor_values) != 2:
                    return jsonify({
                        'error': f'Expected 2 sensor values, got {len(sensor_values)}'
                    }), 400
                
                # Convert to numpy array
                try:
                    sensor_data = np.array(sensor_values, dtype=np.float32)
                except (ValueError, TypeError) as e:
                    return jsonify({'error': f'Invalid sensor values: {str(e)}'}), 400
                
                # Run inference
                prediction, confidence, probabilities = self.run_inference(sensor_data)
                
                if prediction is None:
                    return jsonify({'error': 'Inference failed'}), 500
                
                # Increment request counter
                self.request_count += 1
                
                # Store data
                self.sensor_data_log.append(sensor_data.copy())
                
                # Store prediction in history
                prediction_data = {
                    'timestamp': time.time(),
                    'datetime': datetime.now().isoformat(),
                    'sensor_data': sensor_data.tolist(),
                    'prediction': int(prediction),
                    'prediction_label': self.interpret_prediction(prediction),
                    'confidence': float(confidence),
                    'probabilities': probabilities.tolist() if probabilities is not None else []
                }
                self.prediction_history.append(prediction_data)
                
                # Update last prediction
                self.last_prediction = prediction_data
                self.last_sensor_data = sensor_data
                self.last_timestamp = datetime.now()
                
                # Display results
                self.display_sensor_data(sensor_data, prediction, confidence)
                
                # Save to CSV jika enabled
                if self.save_to_file:
                    self.save_data_to_csv(sensor_data)
                    self.save_prediction_to_csv(sensor_data, prediction, confidence, probabilities)
                
                # Return JSON response
                response = {
                    'success': True,
                    'prediction': int(prediction),
                    'confidence': float(confidence),
                    'interpretation': self.interpret_prediction(prediction),
                    'request_id': self.request_count,
                    'timestamp': datetime.now().isoformat()
                }
                
                print(f"📤 Sending response: {response}")
                print("=" * 80)
                
                return jsonify(response), 200
                
            except Exception as e:
                print(f"❌ Error processing request: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/last-prediction', methods=['GET'])
        def get_last_prediction():
            """Endpoint untuk mengambil data hasil prediksi terakhir"""
            try:
                if self.last_prediction is None:
                    return jsonify({
                        'success': False,
                        'message': 'No prediction data available yet',
                        'timestamp': datetime.now().isoformat()
                    }), 404
                
                # Return last prediction data
                return jsonify({
                    'success': True,
                    'data': self.last_prediction,
                    'message': 'Last prediction retrieved successfully',
                    'total_predictions': len(self.prediction_history),
                    'timestamp': datetime.now().isoformat()
                }), 200
                
            except Exception as e:
                print(f"❌ Error getting last prediction: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/prediction-history', methods=['GET'])
        def get_prediction_history():
            """Endpoint untuk mengambil semua data prediksi yang tersimpan di memory"""
            try:
                limit = request.args.get('limit', default=50, type=int)
                if limit > self.max_history:
                    limit = self.max_history
                
                history_list = list(self.prediction_history)[-limit:]
                
                return jsonify({
                    'success': True,
                    'data': history_list,
                    'count': len(history_list),
                    'total_available': len(self.prediction_history),
                    'limit_applied': limit,
                    'timestamp': datetime.now().isoformat()
                }), 200
                
            except Exception as e:
                print(f"❌ Error getting prediction history: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/download-predictions-csv', methods=['GET'])
        def download_predictions_csv():
            """Endpoint untuk mendownload file CSV hasil prediksi"""
            try:
                if not os.path.exists(self.predictions_csv_filename):
                    return jsonify({
                        'success': False,
                        'message': 'Predictions CSV file not found'
                    }), 404
                
                return send_file(
                    self.predictions_csv_filename,
                    as_attachment=True,
                    download_name=f'predictions_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
                    mimetype='text/csv'
                )
                
            except Exception as e:
                print(f"❌ Error downloading predictions CSV: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/health', methods=['GET'])
        def health_check():
            """Health check endpoint"""
            return jsonify({
                'status': 'healthy',
                'model_loaded': self.interpreter is not None,
                'total_requests': self.request_count,
                'total_predictions': len(self.prediction_history),
                'last_prediction_time': self.last_timestamp.isoformat() if self.last_timestamp else None,
                'predictions_csv_file': self.predictions_csv_filename,
                'server_time': datetime.now().isoformat()
            }), 200
        
        @self.app.route('/', methods=['GET'])
        def index():
            """Root endpoint dengan informasi server"""
            local_ip = self.get_local_ip()
            return jsonify({
                'message': 'ESP32 Bidirectional AI Processor API',
                'endpoints': {
                    'POST /api/sensor-data': 'Send sensor data and get prediction',
                    'GET /api/last-prediction': 'Get last prediction data',
                    'GET /api/prediction-history': 'Get prediction history (with ?limit=N)',
                    'GET /api/download-predictions-csv': 'Download predictions CSV file',
                    'GET /api/health': 'Health check'
                },
                'server_ip': local_ip,
                'server_port': self.port,
                'model_loaded': self.interpreter is not None,
                'total_predictions': len(self.prediction_history),
                'last_prediction_available': self.last_prediction is not None,
                'csv_files': {
                    'sensor_data': self.csv_filename,
                    'predictions': self.predictions_csv_filename
                }
            }), 200
    
    def run_inference(self, sensor_data):
        """
        Jalankan inference dengan TensorFlow Lite
        
        Args:
            sensor_data: Array numpy dengan 2 nilai sensor (MQ2, MQ3)
            
        Returns:
            prediction: Prediksi kelas (0=fresh, 1=degraded, 2=error)
            confidence: Confidence score
            probabilities: Array dengan semua probabilitas kelas
        """
        if self.interpreter is None:
            # Simulate prediction jika model tidak tersedia
            probabilities = np.array([0.85, 0.10, 0.05])
            return 0, 0.85, probabilities
        
        try:
            # Reshape data untuk model (batch_size=1, features=2)
            # Note: Model mungkin masih expect 8 features, perlu padding atau adjustment
            # Untuk sekarang, kita asumsikan model bisa handle 2 features
            input_data = np.expand_dims(sensor_data, axis=0)
            
            # Jika model expect 8 features, pad dengan zeros
            expected_features = self.input_details[0]['shape'][1]
            if expected_features == 8 and len(sensor_data) == 2:
                # Pad dengan zeros untuk 6 sensor lainnya
                padded_data = np.zeros((1, 8), dtype=np.float32)
                padded_data[0, 0] = sensor_data[0]  # MQ2
                padded_data[0, 1] = sensor_data[1]  # MQ3
                input_data = padded_data
                print("⚠️ Model expects 8 features, padding with zeros for sensors 3-8")
            
            # Set input tensor
            self.interpreter.set_tensor(self.input_details[0]['index'], input_data)
            
            # Run inference
            self.interpreter.invoke()
            
            # Get output
            output_data = self.interpreter.get_tensor(self.output_details[0]['index'])
            
            # Get prediction
            prediction = np.argmax(output_data[0])
            confidence = np.max(output_data[0])
            
            return prediction, confidence, output_data[0]
            
        except Exception as e:
            print(f"❌ Error during inference: {e}")
            import traceback
            traceback.print_exc()
            return None, None, None
    
    def interpret_prediction(self, prediction):
        """Interpretasi hasil prediksi"""
        interpretations = {
            0: "FRESH",
            1: "DEGRADED", 
            2: "ERROR"
        }
        return interpretations.get(prediction, "UNKNOWN")
    
    
    def save_data_to_csv(self, sensor_data):
        """Simpan data sensor ke CSV file (tanpa prediksi)"""
        try:
            timestamp = time.time()
            datetime_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            with open(self.csv_filename, 'a', newline='') as csvfile:
                writer = csv.writer(csvfile)
                row = [timestamp, datetime_str] + sensor_data.tolist()
                writer.writerow(row)
                
        except Exception as e:
            print(f"❌ Error saving to CSV: {e}")
    
    def display_sensor_data(self, sensor_data, prediction, confidence):
        """Display data sensor dengan format yang rapi"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        print(f"\n[{timestamp}] 📊 Sensor Data + Prediction (Request #{self.request_count}):")
        print("-" * 60)
        
        for i, (name, value) in enumerate(zip(self.sensor_names, sensor_data)):
            print(f"{name:>6}: {value:>8.6f}")
        
        print("-" * 60)
        
        # Display prediction
        interpretation = self.interpret_prediction(prediction)
        print(f"🤖 AI Prediction: {interpretation}")
        print(f"📊 Confidence: {confidence:.3f}")
        
        # Visual indicator
        if prediction == 0:
            print("🟢 Status: FRESH - Makanan masih segar")
        elif prediction == 1:
            print("🟡 Status: DEGRADED - Makanan mulai rusak")
        else:
            print("🔴 Status: ERROR - Tidak dapat ditentukan")
        
        print(f"💾 Prediction saved to: {self.predictions_csv_filename}")
        print("-" * 60)
    
    def start_server(self):
        """Start Flask REST API server"""
        local_ip = self.get_local_ip()
        
        print("\n" + "=" * 80)
        print("🤖 ESP32 Bidirectional AI Processor - REST API Server")
        print("=" * 80)
        print(f"📡 Server starting on: http://{self.host}:{self.port}")
        print(f"🌐 Local IP Address: {local_ip}")
        print(f"📋 ESP32 should connect to: http://{local_ip}:{self.port}/api/sensor-data")
        print(f"💾 CSV file (sensor data): {self.csv_filename}")
        print(f"💾 CSV file (predictions): {self.predictions_csv_filename}")
        print(f"🤖 Model: {self.model_path} ({'✅ Loaded' if self.interpreter else '❌ Not loaded'})")
        print("=" * 80)
        print("\n🔄 Server is running...")
        print("📝 Waiting for sensor data from ESP32...")
        print("🤖 Running AI inference on each request...")
        print("📤 Sending predictions back via JSON response...")
        print("📊 New endpoints available:")
        print("   - GET /api/last-prediction (get last prediction data)")
        print("   - GET /api/prediction-history (get prediction history)")
        print("   - GET /api/download-predictions-csv (download predictions CSV)")
        print("Press Ctrl+C to stop\n")
        
        try:
            # Run Flask server
            self.app.run(host=self.host, port=self.port, debug=False, threaded=True)
        except KeyboardInterrupt:
            print("\n🛑 Stopping server...")
            print(f"📊 Total requests processed: {self.request_count}")
            print(f"📊 Total predictions saved: {len(self.prediction_history)}")
            print(f"💾 Predictions saved to: {self.predictions_csv_filename}")
        except Exception as e:
            print(f"❌ Error running server: {e}")
            import traceback
            traceback.print_exc()
    
    def export_to_json(self, filename=None):
        """Export data ke JSON format"""
        if not self.sensor_data_log:
            print("❌ No data to export")
            return
        
        if filename is None:
            filename = f"sensor_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            data_dict = {
                'metadata': {
                    'timestamp': datetime.now().isoformat(),
                    'total_samples': len(self.sensor_data_log),
                    'sensor_names': self.sensor_names,
                    'host': self.host,
                    'port': self.port,
                    'model_path': self.model_path,
                    'prediction_history_count': len(self.prediction_history)
                },
                'sensor_data': [sensor_data.tolist() for sensor_data in self.sensor_data_log],
                'prediction_history': list(self.prediction_history)
            }
            
            with open(filename, 'w') as jsonfile:
                json.dump(data_dict, jsonfile, indent=2)
            
            print(f"✅ Data exported to JSON: {filename}")
            
        except Exception as e:
            print(f"❌ Error exporting to JSON: {e}")

def main():
    """Main function"""
    # Konfigurasi - sesuaikan dengan setup Anda
    HOST = '0.0.0.0'  # Listen pada semua network interface
    PORT = 5000  # Port untuk Flask server
    MODEL_PATH = 'food_model_250.tflite'  # Path ke model TensorFlow Lite
    SAVE_TO_FILE = True  # Set False jika tidak ingin save ke file
    MAX_HISTORY = 1000  # Maksimal data prediksi yang disimpan di memory
    
    # Buat processor
    processor = ESP32BidirectionalProcessor(
        host=HOST,
        port=PORT, 
        model_path=MODEL_PATH, 
        save_to_file=SAVE_TO_FILE,
        max_history=MAX_HISTORY
    )
    
    # Start REST API server
    processor.start_server()
    
    # Export to JSON setelah selesai (jika server dihentikan)
    if SAVE_TO_FILE and processor.sensor_data_log:
        processor.export_to_json()

if __name__ == "__main__":
    main()
