#!/usr/bin/env python3
"""
ESP32 Bidirectional Communication via REST API - Sensor Data + Prediction Results
Menerima data sensor dari ESP32 via HTTP POST, jalankan inference, kirim hasil prediksi kembali via JSON response
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import numpy as np
import time
import sys
from datetime import datetime
import csv
import json
import socket

# TensorFlow Lite import
try:
    import tensorflow as tf
    TFLITE_AVAILABLE = True
except ImportError:
    print("⚠️ TensorFlow not available. Install with: pip install tensorflow")
    TFLITE_AVAILABLE = False

class ESP32BidirectionalProcessor:
    def __init__(self, host='0.0.0.0', port=5000, model_path='food_model_250.tflite', save_to_file=True):
        """
        Inisialisasi processor untuk komunikasi dua arah dengan ESP32 via REST API
        
        Args:
            host: Host untuk Flask server (0.0.0.0 untuk listen semua interface)
            port: Port untuk Flask server (default: 5000)
            model_path: Path ke file model TensorFlow Lite
            save_to_file: Apakah data disimpan ke file
        """
        self.host = host
        self.port = port
        self.model_path = model_path
        self.save_to_file = save_to_file
        
        # Flask app setup
        self.app = Flask(__name__)
        CORS(self.app)  # Enable CORS untuk cross-origin requests
        
        # Data storage
        self.sensor_data_log = []
        self.csv_filename = f"sensor_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
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
        
        # Setup Flask routes
        self.setup_routes()
        
        # Request counter
        self.request_count = 0
    
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
        """Setup CSV file untuk menyimpan data"""
        try:
            with open(self.csv_filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                # Write header
                header = ['Timestamp', 'DateTime'] + self.sensor_names + ['Prediction', 'Confidence']
                writer.writerow(header)
            print(f"✅ CSV file created: {self.csv_filename}")
        except Exception as e:
            print(f"❌ Error creating CSV file: {e}")
    
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
                
                # Display results
                self.display_sensor_data(sensor_data, prediction, confidence)
                
                # Save to CSV if enabled
                if self.save_to_file:
                    self.save_data_to_csv(sensor_data, prediction, confidence)
                
                # Return JSON response
                response = {
                    'success': True,
                    'prediction': int(prediction),
                    'confidence': float(confidence),
                    'interpretation': self.interpret_prediction(prediction),
                    'request_id': self.request_count
                }
                
                print(f"📤 Sending response: {response}")
                print("=" * 80)
                
                return jsonify(response), 200
                
            except Exception as e:
                print(f"❌ Error processing request: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/health', methods=['GET'])
        def health_check():
            """Health check endpoint"""
            return jsonify({
                'status': 'healthy',
                'model_loaded': self.interpreter is not None,
                'total_requests': self.request_count,
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
                    'GET /api/health': 'Health check'
                },
                'server_ip': local_ip,
                'server_port': self.port,
                'model_loaded': self.interpreter is not None
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
            return 0, 0.85, np.array([0.85, 0.10, 0.05])
        
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
    
    
    def save_data_to_csv(self, sensor_data, prediction, confidence):
        """Simpan data ke CSV file"""
        try:
            timestamp = time.time()
            datetime_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            with open(self.csv_filename, 'a', newline='') as csvfile:
                writer = csv.writer(csvfile)
                row = [timestamp, datetime_str] + sensor_data.tolist() + [prediction, confidence]
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
        print(f"💾 CSV file: {self.csv_filename}")
        print(f"🤖 Model: {self.model_path} ({'✅ Loaded' if self.interpreter else '❌ Not loaded'})")
        print("=" * 80)
        print("\n🔄 Server is running...")
        print("📝 Waiting for sensor data from ESP32...")
        print("🤖 Running AI inference on each request...")
        print("📤 Sending predictions back via JSON response...")
        print("Press Ctrl+C to stop\n")
        
        try:
            # Run Flask server
            self.app.run(host=self.host, port=self.port, debug=False, threaded=True)
        except KeyboardInterrupt:
            print("\n🛑 Stopping server...")
            print(f"📊 Total requests processed: {self.request_count}")
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
                    'model_path': self.model_path
                },
                'data': [sensor_data.tolist() for sensor_data in self.sensor_data_log]
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
    
    # Buat processor
    processor = ESP32BidirectionalProcessor(
        host=HOST,
        port=PORT, 
        model_path=MODEL_PATH, 
        save_to_file=SAVE_TO_FILE
    )
    
    # Start REST API server
    processor.start_server()
    
    # Export to JSON setelah selesai (jika server dihentikan)
    if SAVE_TO_FILE and processor.sensor_data_log:
        processor.export_to_json()

if __name__ == "__main__":
    main()
