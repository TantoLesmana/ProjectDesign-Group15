#!/usr/bin/env python3
"""
ESP32 Bidirectional Communication via REST API + Web GUI
Menerima data sensor dari ESP32 via HTTP POST, jalankan inference, 
dan tampilkan hasilnya secara realtime di web interface
"""

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import numpy as np
import time
import sys
from datetime import datetime
import csv
import json
import socket
import threading
import collections
import traceback

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
        Inisialisasi processor untuk komunikasi dua arah dengan ESP32 via REST API + Web GUI
        
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
        self.app.config['SECRET_KEY'] = 'esp32-secret-key-123'
        CORS(self.app)  # Enable CORS untuk cross-origin requests
        self.socketio = SocketIO(self.app, cors_allowed_origins="*", async_mode='threading')
        
        # Data storage untuk GUI
        self.sensor_data_log = []
        self.predictions_log = []
        self.max_data_points = 100  # Jumlah maksimum data point untuk chart
        
        # Buffer untuk chart data (gunakan deque untuk performa)
        self.chart_data = {
            'timestamps': collections.deque(maxlen=self.max_data_points),
            'mq2_values': collections.deque(maxlen=self.max_data_points),
            'mq3_values': collections.deque(maxlen=self.max_data_points),
            'predictions': collections.deque(maxlen=self.max_data_points),
            'confidences': collections.deque(maxlen=self.max_data_points)
        }
        
        # Data terbaru untuk real-time update
        self.latest_data = {
            'mq2': 0.0,
            'mq3': 0.0,
            'prediction': 0,
            'confidence': 0.0,
            'interpretation': 'UNKNOWN',
            'timestamp': datetime.now().strftime("%H:%M:%S")
        }
        
        # Statistics
        self.statistics = {
            'total_requests': 0,
            'fresh_count': 0,
            'degraded_count': 0,
            'error_count': 0,
            'avg_confidence': 0.0,
            'avg_mq2': 0.0,
            'avg_mq3': 0.0
        }
        
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
        
        # Setup SocketIO events
        self.setup_socketio_events()
        
        # Request counter
        self.request_count = 0
        
        # Lock untuk thread safety
        self.data_lock = threading.Lock()
    
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
        """Setup Flask routes untuk REST API dan Web GUI"""
        
        @self.app.route('/')
        def index():
            """Halaman utama dengan Web GUI"""
            return render_template('index.html', 
                                 host=self.host,
                                 port=self.port,
                                 sensor_names=self.sensor_names)
        
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
                
                with self.data_lock:
                    # Update statistics
                    self.update_statistics(prediction, confidence, sensor_data)
                    
                    # Store data
                    self.sensor_data_log.append(sensor_data.copy())
                    self.predictions_log.append(prediction)
                    
                    # Update latest data
                    current_time = datetime.now()
                    timestamp_str = current_time.strftime("%H:%M:%S")
                    
                    # Convert numpy values to Python native types
                    self.latest_data = {
                        'mq2': float(sensor_data[0]),
                        'mq3': float(sensor_data[1]),
                        'prediction': int(prediction),
                        'confidence': float(confidence),
                        'interpretation': self.interpret_prediction(prediction),
                        'timestamp': timestamp_str
                    }
                    
                    # Add to chart data
                    self.chart_data['timestamps'].append(timestamp_str)
                    self.chart_data['mq2_values'].append(float(sensor_data[0]))
                    self.chart_data['mq3_values'].append(float(sensor_data[1]))
                    self.chart_data['predictions'].append(int(prediction))
                    self.chart_data['confidences'].append(float(confidence))
                    
                    # Prepare data for WebSocket broadcast
                    broadcast_data = self.prepare_broadcast_data()
                
                # Broadcast data ke semua client via WebSocket
                self.broadcast_data_to_clients(broadcast_data)
                
                # Display results di console
                self.display_sensor_data(sensor_data, prediction, confidence)
                
                # Save to CSV if enabled
                if self.save_to_file:
                    self.save_data_to_csv(sensor_data, prediction, confidence)
                
                # Return JSON response ke ESP32
                response = {
                    'success': True,
                    'prediction': int(prediction),
                    'confidence': float(confidence),
                    'interpretation': self.interpret_prediction(prediction),
                    'request_id': self.request_count
                }
                
                print(f"📤 Sending response to ESP32: {response}")
                print("=" * 80)
                
                return jsonify(response), 200
                
            except Exception as e:
                print(f"❌ Error processing request: {e}")
                traceback.print_exc()
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/get-latest-data', methods=['GET'])
        def get_latest_data():
            """API untuk mendapatkan data terbaru"""
            try:
                with self.data_lock:
                    data = self.prepare_broadcast_data()
                
                return jsonify({
                    'success': True,
                    **data
                }), 200
            except Exception as e:
                print(f"❌ Error in get-latest-data: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/health', methods=['GET'])
        def health_check():
            """Health check endpoint"""
            return jsonify({
                'status': 'healthy',
                'model_loaded': self.interpreter is not None,
                'total_requests': self.request_count,
                'latest_data': self.latest_data,
                'server_time': datetime.now().isoformat()
            }), 200
        
        @self.app.route('/api/clear-data', methods=['POST'])
        def clear_data():
            """Clear semua data yang disimpan"""
            with self.data_lock:
                self.chart_data['timestamps'].clear()
                self.chart_data['mq2_values'].clear()
                self.chart_data['mq3_values'].clear()
                self.chart_data['predictions'].clear()
                self.chart_data['confidences'].clear()
                
                # Reset statistics
                self.statistics = {
                    'total_requests': self.request_count,  # Keep request count
                    'fresh_count': 0,
                    'degraded_count': 0,
                    'error_count': 0,
                    'avg_confidence': 0.0,
                    'avg_mq2': 0.0,
                    'avg_mq3': 0.0
                }
                
                # Keep latest data but reset others
                self.latest_data['mq2'] = 0.0
                self.latest_data['mq3'] = 0.0
                self.latest_data['prediction'] = 0
                self.latest_data['confidence'] = 0.0
                self.latest_data['interpretation'] = 'UNKNOWN'
                
                broadcast_data = self.prepare_broadcast_data()
            
            # Broadcast update
            self.broadcast_data_to_clients(broadcast_data)
            
            return jsonify({'success': True, 'message': 'Data cleared'}), 200
    
    def setup_socketio_events(self):
        """Setup SocketIO event handlers"""
        
        @self.socketio.on('connect')
        def handle_connect():
            """Handle new client connection"""
            print(f"🌐 Client connected: {request.sid}")
            
            # Kirim data saat ini ke client yang baru connect
            with self.data_lock:
                data = self.prepare_broadcast_data()
            
            emit('initial_data', data)
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Handle client disconnection"""
            print(f"🌐 Client disconnected: {request.sid}")
        
        @self.socketio.on('request_update')
        def handle_request_update():
            """Client request update data"""
            with self.data_lock:
                data = self.prepare_broadcast_data()
            
            emit('data_update', data)
    
    def prepare_broadcast_data(self):
        """Prepare data untuk broadcast ke clients"""
        # Convert all data to JSON-serializable types
        return {
            'latest_data': self.latest_data,
            'statistics': self.statistics,
            'chart_data': {
                'timestamps': list(self.chart_data['timestamps']),
                'mq2_values': [float(v) for v in self.chart_data['mq2_values']],
                'mq3_values': [float(v) for v in self.chart_data['mq3_values']],
                'predictions': [int(v) for v in self.chart_data['predictions']],
                'confidences': [float(v) for v in self.chart_data['confidences']]
            }
        }
    
    def broadcast_data_to_clients(self, data=None):
        """Broadcast data terbaru ke semua connected clients"""
        if data is None:
            with self.data_lock:
                data = self.prepare_broadcast_data()
        
        try:
            self.socketio.emit('data_update', data)
        except Exception as e:
            print(f"❌ Error broadcasting data: {e}")
    
    def update_statistics(self, prediction, confidence, sensor_data):
        """Update statistics berdasarkan data baru"""
        prev_total = max(self.statistics['total_requests'] - 1, 0)
        
        # Convert numpy values to Python floats
        confidence_float = float(confidence)
        mq2_float = float(sensor_data[0])
        mq3_float = float(sensor_data[1])
        
        # Update count berdasarkan prediksi
        if prediction == 0:
            self.statistics['fresh_count'] += 1
        elif prediction == 1:
            self.statistics['degraded_count'] += 1
        elif prediction == 2:
            self.statistics['error_count'] += 1
        
        # Update average confidence
        if prev_total > 0:
            total_conf = self.statistics['avg_confidence'] * prev_total + confidence_float
            self.statistics['avg_confidence'] = total_conf / (prev_total + 1)
            
            # Update average sensor values
            total_mq2 = self.statistics['avg_mq2'] * prev_total + mq2_float
            total_mq3 = self.statistics['avg_mq3'] * prev_total + mq3_float
            self.statistics['avg_mq2'] = total_mq2 / (prev_total + 1)
            self.statistics['avg_mq3'] = total_mq3 / (prev_total + 1)
        else:
            self.statistics['avg_confidence'] = confidence_float
            self.statistics['avg_mq2'] = mq2_float
            self.statistics['avg_mq3'] = mq3_float
        
        self.statistics['total_requests'] = self.request_count
    
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
            
            return int(prediction), float(confidence), output_data[0]
            
        except Exception as e:
            print(f"❌ Error during inference: {e}")
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
                row = [timestamp, datetime_str] + [float(v) for v in sensor_data] + [prediction, float(confidence)]
                writer.writerow(row)
                
        except Exception as e:
            print(f"❌ Error saving to CSV: {e}")
    
    def display_sensor_data(self, sensor_data, prediction, confidence):
        """Display data sensor dengan format yang rapi di console"""
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
        """Start Flask REST API server dengan WebSocket"""
        local_ip = self.get_local_ip()
        
        print("\n" + "=" * 80)
        print("🤖 ESP32 Bidirectional AI Processor - REST API + Web GUI Server")
        print("=" * 80)
        print(f"📡 Server starting on: http://{self.host}:{self.port}")
        print(f"🌐 Local IP Address: {local_ip}")
        print(f"🌍 Web Interface: http://{local_ip}:{self.port}")
        print(f"📋 ESP32 API: http://{local_ip}:{self.port}/api/sensor-data")
        print(f"💾 CSV file: {self.csv_filename}")
        print(f"🤖 Model: {self.model_path} ({'✅ Loaded' if self.interpreter else '❌ Not loaded'})")
        print("=" * 80)
        print("\n🔄 Server is running...")
        print("📝 Waiting for sensor data from ESP32...")
        print("🤖 Running AI inference on each request...")
        print("📤 Sending predictions back via JSON response...")
        print("🌐 Web GUI is available at the address above")
        print("Press Ctrl+C to stop\n")
        
        try:
            # Run Flask server dengan SocketIO
            self.socketio.run(self.app, host=self.host, port=self.port, debug=False, allow_unsafe_werkzeug=True)
        except KeyboardInterrupt:
            print("\n🛑 Stopping server...")
            print(f"📊 Total requests processed: {self.request_count}")
        except Exception as e:
            print(f"❌ Error running server: {e}")
            traceback.print_exc()
    
    def export_to_json(self, filename=None):
        """Export data ke JSON format"""
        if not self.sensor_data_log:
            print("❌ No data to export")
            return
        
        if filename is None:
            filename = f"sensor_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with self.data_lock:
                data_dict = {
                    'metadata': {
                        'timestamp': datetime.now().isoformat(),
                        'total_samples': len(self.sensor_data_log),
                        'sensor_names': self.sensor_names,
                        'host': self.host,
                        'port': self.port,
                        'model_path': self.model_path,
                        'statistics': self.statistics
                    },
                    'latest_data': self.latest_data,
                    'sensor_data': [[float(v) for v in sensor_data] for sensor_data in self.sensor_data_log],
                    'predictions': [int(p) for p in self.predictions_log],
                    'chart_data': {
                        'timestamps': list(self.chart_data['timestamps']),
                        'mq2_values': [float(v) for v in self.chart_data['mq2_values']],
                        'mq3_values': [float(v) for v in self.chart_data['mq3_values']],
                        'predictions': [int(v) for v in self.chart_data['predictions']],
                        'confidences': [float(v) for v in self.chart_data['confidences']]
                    }
                }
            
            with open(filename, 'w') as jsonfile:
                json.dump(data_dict, jsonfile, indent=2)
            
            print(f"✅ Data exported to JSON: {filename}")
            
        except Exception as e:
            print(f"❌ Error exporting to JSON: {e}")
            traceback.print_exc()


def create_templates_folder():
    """Create templates folder with HTML file jika belum ada"""
    import os
    
    # Create templates directory jika belum ada
    if not os.path.exists('templates'):
        os.makedirs('templates')
        print("✅ Created templates directory")
    
    # Create HTML template file
    html_content = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ESP32 Sensor Monitor - Real-time AI Prediction</title>
    <script src="https://cdn.socket.io/4.5.0/socket.io.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .status-fresh { background-color: #10B981; }
        .status-degraded { background-color: #F59E0B; }
        .status-error { background-color: #EF4444; }
        .gauge-container {
            width: 200px;
            height: 200px;
            position: relative;
        }
        .gauge {
            width: 100%;
            height: 100%;
        }
        .gauge-value {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 24px;
            font-weight: bold;
        }
        .blink {
            animation: blinker 1s linear infinite;
        }
        @keyframes blinker {
            50% { opacity: 0.5; }
        }
    </style>
</head>
<body class="bg-gray-900 text-white min-h-screen">
    <div class="container mx-auto p-4">
        <!-- Header -->
        <div class="text-center mb-8">
            <h1 class="text-4xl font-bold text-blue-400 mb-2">🤖 ESP32 Sensor Monitor</h1>
            <p class="text-gray-300">Real-time AI Prediction Dashboard</p>
            <div class="flex justify-center space-x-4 mt-4 text-sm">
                <div class="bg-gray-800 p-2 rounded">
                    <span class="text-gray-400">Server:</span> 
                    <span id="server-info" class="text-blue-300">http://{{ host }}:{{ port }}</span>
                </div>
                <div class="bg-gray-800 p-2 rounded">
                    <span class="text-gray-400">Status:</span> 
                    <span id="connection-status" class="text-green-400">● Connected</span>
                </div>
                <div class="bg-gray-800 p-2 rounded">
                    <span class="text-gray-400">Last Update:</span> 
                    <span id="last-update" class="text-yellow-300">Just now</span>
                </div>
            </div>
        </div>

        <!-- Main Dashboard -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
            <!-- Latest Data Card -->
            <div class="bg-gray-800 rounded-xl p-6 shadow-lg">
                <h2 class="text-2xl font-bold text-blue-300 mb-4">📊 Latest Sensor Data</h2>
                <div class="space-y-4">
                    <div class="flex justify-between items-center p-3 bg-gray-700 rounded">
                        <span class="text-lg">MQ2 Value:</span>
                        <span id="mq2-value" class="text-2xl font-bold text-green-400">0.000</span>
                    </div>
                    <div class="flex justify-between items-center p-3 bg-gray-700 rounded">
                        <span class="text-lg">MQ3 Value:</span>
                        <span id="mq3-value" class="text-2xl font-bold text-blue-400">0.000</span>
                    </div>
                    <div class="flex justify-between items-center p-3 bg-gray-700 rounded">
                        <span class="text-lg">Timestamp:</span>
                        <span id="timestamp" class="text-xl font-mono">00:00:00</span>
                    </div>
                </div>
            </div>

            <!-- AI Prediction Card -->
            <div class="bg-gray-800 rounded-xl p-6 shadow-lg">
                <h2 class="text-2xl font-bold text-purple-300 mb-4">🤖 AI Prediction</h2>
                <div class="text-center">
                    <div id="prediction-status" class="text-4xl font-bold mb-4 p-4 rounded-lg status-fresh">
                        FRESH
                    </div>
                    <div class="gauge-container mx-auto mb-4">
                        <canvas id="confidence-gauge" class="gauge"></canvas>
                        <div id="confidence-value" class="gauge-value">85%</div>
                    </div>
                    <div class="text-gray-300">
                        Confidence Level
                    </div>
                </div>
            </div>

            <!-- Statistics Card -->
            <div class="bg-gray-800 rounded-xl p-6 shadow-lg">
                <h2 class="text-2xl font-bold text-green-300 mb-4">📈 Statistics</h2>
                <div class="space-y-3">
                    <div class="flex justify-between">
                        <span>Total Requests:</span>
                        <span id="total-requests" class="font-bold">0</span>
                    </div>
                    <div class="flex justify-between">
                        <span>Fresh Count:</span>
                        <span id="fresh-count" class="font-bold text-green-400">0</span>
                    </div>
                    <div class="flex justify-between">
                        <span>Degraded Count:</span>
                        <span id="degraded-count" class="font-bold text-yellow-400">0</span>
                    </div>
                    <div class="flex justify-between">
                        <span>Error Count:</span>
                        <span id="error-count" class="font-bold text-red-400">0</span>
                    </div>
                    <div class="flex justify-between">
                        <span>Avg Confidence:</span>
                        <span id="avg-confidence" class="font-bold">0.0%</span>
                    </div>
                    <div class="flex justify-between">
                        <span>Avg MQ2:</span>
                        <span id="avg-mq2" class="font-bold">0.000</span>
                    </div>
                    <div class="flex justify-between">
                        <span>Avg MQ3:</span>
                        <span id="avg-mq3" class="font-bold">0.000</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Charts Section -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            <!-- Sensor Values Chart -->
            <div class="bg-gray-800 rounded-xl p-6 shadow-lg">
                <h2 class="text-2xl font-bold text-blue-300 mb-4">📈 Sensor Values Over Time</h2>
                <div class="h-64">
                    <canvas id="sensor-chart"></canvas>
                </div>
            </div>

            <!-- Predictions Chart -->
            <div class="bg-gray-800 rounded-xl p-6 shadow-lg">
                <h2 class="text-2xl font-bold text-purple-300 mb-4">📊 Prediction History</h2>
                <div class="h-64">
                    <canvas id="prediction-chart"></canvas>
                </div>
            </div>
        </div>

        <!-- Control Panel -->
        <div class="bg-gray-800 rounded-xl p-6 shadow-lg">
            <h2 class="text-2xl font-bold text-yellow-300 mb-4">⚙️ Control Panel</h2>
            <div class="flex flex-wrap gap-4">
                <button id="refresh-btn" class="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded">
                    🔄 Refresh Data
                </button>
                <button id="clear-btn" class="bg-red-600 hover:bg-red-700 px-4 py-2 rounded">
                    🗑️ Clear All Data
                </button>
                <button id="export-btn" class="bg-green-600 hover:bg-green-700 px-4 py-2 rounded">
                    📥 Export Data
                </button>
                <div class="ml-auto">
                    <label class="text-gray-300 mr-2">Max Data Points:</label>
                    <select id="data-limit" class="bg-gray-700 text-white px-3 py-1 rounded">
                        <option value="50">50</option>
                        <option value="100" selected>100</option>
                        <option value="200">200</option>
                        <option value="500">500</option>
                    </select>
                </div>
            </div>
        </div>

        <!-- Footer -->
        <div class="text-center mt-8 text-gray-500 text-sm">
            <p>ESP32 Sensor Monitor Dashboard v1.0 | Real-time AI Inference System</p>
            <p class="mt-1">Connected to: <span id="api-endpoint" class="text-blue-300">http://{{ host }}:{{ port }}/api/sensor-data</span></p>
        </div>
    </div>

    <script>
        // Socket.IO Connection
        const socket = io();
        let chartData = {
            timestamps: [],
            mq2_values: [],
            mq3_values: [],
            predictions: [],
            confidences: []
        };
        
        let sensorChart, predictionChart, confidenceGauge;

        // Update UI with latest data
        function updateUI(data) {
            // Update latest data
            document.getElementById('mq2-value').textContent = data.latest_data.mq2.toFixed(6);
            document.getElementById('mq3-value').textContent = data.latest_data.mq3.toFixed(6);
            document.getElementById('timestamp').textContent = data.latest_data.timestamp;
            
            // Update prediction status
            const predictionStatus = document.getElementById('prediction-status');
            predictionStatus.textContent = data.latest_data.interpretation;
            
            // Set color based on prediction
            predictionStatus.className = 'text-4xl font-bold mb-4 p-4 rounded-lg ';
            if (data.latest_data.prediction === 0) {
                predictionStatus.classList.add('status-fresh');
            } else if (data.latest_data.prediction === 1) {
                predictionStatus.classList.add('status-degraded');
            } else {
                predictionStatus.classList.add('status-error');
            }
            
            // Update confidence
            const confidencePercent = (data.latest_data.confidence * 100).toFixed(1);
            document.getElementById('confidence-value').textContent = confidencePercent + '%';
            updateGauge(data.latest_data.confidence);
            
            // Update statistics
            document.getElementById('total-requests').textContent = data.statistics.total_requests;
            document.getElementById('fresh-count').textContent = data.statistics.fresh_count;
            document.getElementById('degraded-count').textContent = data.statistics.degraded_count;
            document.getElementById('error-count').textContent = data.statistics.error_count;
            document.getElementById('avg-confidence').textContent = 
                (data.statistics.avg_confidence * 100).toFixed(1) + '%';
            document.getElementById('avg-mq2').textContent = data.statistics.avg_mq2.toFixed(6);
            document.getElementById('avg-mq3').textContent = data.statistics.avg_mq3.toFixed(6);
            
            // Update last update time
            document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
            
            // Update chart data
            if (data.chart_data) {
                chartData = data.chart_data;
                updateCharts();
            }
        }

        // Initialize confidence gauge
        function initGauge() {
            const ctx = document.getElementById('confidence-gauge').getContext('2d');
            confidenceGauge = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    datasets: [{
                        data: [85, 15],
                        backgroundColor: ['#10B981', '#374151'],
                        borderWidth: 0
                    }]
                },
                options: {
                    cutout: '80%',
                    rotation: -90,
                    circumference: 180,
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: { enabled: false }
                    }
                }
            });
        }

        // Update confidence gauge
        function updateGauge(confidence) {
            if (confidenceGauge) {
                const confidencePercent = confidence * 100;
                confidenceGauge.data.datasets[0].data = [confidencePercent, 100 - confidencePercent];
                confidenceGauge.update();
            }
        }

        // Initialize charts
        function initCharts() {
            const sensorCtx = document.getElementById('sensor-chart').getContext('2d');
            const predictionCtx = document.getElementById('prediction-chart').getContext('2d');
            
            sensorChart = new Chart(sensorCtx, {
                type: 'line',
                data: {
                    labels: chartData.timestamps,
                    datasets: [
                        {
                            label: 'MQ2',
                            data: chartData.mq2_values,
                            borderColor: '#10B981',
                            backgroundColor: 'rgba(16, 185, 129, 0.1)',
                            tension: 0.4,
                            fill: true
                        },
                        {
                            label: 'MQ3',
                            data: chartData.mq3_values,
                            borderColor: '#3B82F6',
                            backgroundColor: 'rgba(59, 130, 246, 0.1)',
                            tension: 0.4,
                            fill: true
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            grid: { color: 'rgba(255,255,255,0.1)' },
                            ticks: { color: '#9CA3AF' }
                        },
                        y: {
                            grid: { color: 'rgba(255,255,255,0.1)' },
                            ticks: { color: '#9CA3AF' }
                        }
                    },
                    plugins: {
                        legend: { labels: { color: '#9CA3AF' } }
                    }
                }
            });
            
            predictionChart = new Chart(predictionCtx, {
                type: 'bar',
                data: {
                    labels: chartData.timestamps,
                    datasets: [{
                        label: 'Prediction',
                        data: chartData.predictions,
                        backgroundColor: chartData.predictions.map(p => {
                            if (p === 0) return '#10B981';
                            if (p === 1) return '#F59E0B';
                            return '#EF4444';
                        }),
                        borderColor: chartData.predictions.map(p => {
                            if (p === 0) return '#059669';
                            if (p === 1) return '#D97706';
                            return '#DC2626';
                        }),
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            grid: { color: 'rgba(255,255,255,0.1)' },
                            ticks: { color: '#9CA3AF' }
                        },
                        y: {
                            grid: { color: 'rgba(255,255,255,0.1)' },
                            ticks: { 
                                color: '#9CA3AF',
                                callback: function(value) {
                                    if (value === 0) return 'FRESH';
                                    if (value === 1) return 'DEGRADED';
                                    if (value === 2) return 'ERROR';
                                    return value;
                                }
                            }
                        }
                    },
                    plugins: {
                        legend: { labels: { color: '#9CA3AF' } }
                    }
                }
            });
        }

        // Update charts
        function updateCharts() {
            if (sensorChart) {
                sensorChart.data.labels = chartData.timestamps;
                sensorChart.data.datasets[0].data = chartData.mq2_values;
                sensorChart.data.datasets[1].data = chartData.mq3_values;
                sensorChart.update();
            }
            
            if (predictionChart) {
                predictionChart.data.labels = chartData.timestamps;
                predictionChart.data.datasets[0].data = chartData.predictions;
                predictionChart.data.datasets[0].backgroundColor = chartData.predictions.map(p => {
                    if (p === 0) return '#10B981';
                    if (p === 1) return '#F59E0B';
                    return '#EF4444';
                });
                predictionChart.update();
            }
        }

        // Socket.IO event handlers
        socket.on('connect', () => {
            console.log('Connected to server');
            document.getElementById('connection-status').textContent = '● Connected';
            document.getElementById('connection-status').className = 'text-green-400';
        });

        socket.on('disconnect', () => {
            console.log('Disconnected from server');
            document.getElementById('connection-status').textContent = '○ Disconnected';
            document.getElementById('connection-status').className = 'text-red-400 blink';
        });

        socket.on('initial_data', (data) => {
            console.log('Received initial data');
            updateUI(data);
        });

        socket.on('data_update', (data) => {
            console.log('Received data update');
            updateUI(data);
        });

        // Button event listeners
        document.getElementById('refresh-btn').addEventListener('click', () => {
            socket.emit('request_update');
        });

        document.getElementById('clear-btn').addEventListener('click', () => {
            if (confirm('Are you sure you want to clear all data?')) {
                fetch('/api/clear-data', { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            alert('Data cleared successfully');
                        }
                    });
            }
        });

        document.getElementById('export-btn').addEventListener('click', () => {
            alert('Export feature will be available in the next update');
        });

        // Initialize everything when page loads
        document.addEventListener('DOMContentLoaded', () => {
            initGauge();
            initCharts();
            
            // Initial data fetch
            fetch('/api/get-latest-data')
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        updateUI(data);
                    }
                });
        });
    </script>
</body>
</html>'''
    
    # Write HTML file
    with open('templates/index.html', 'w') as f:
        f.write(html_content)
    
    print("✅ Created HTML template file")

def main():
    """Main function"""
    # Install dependencies jika belum ada
    print("🔧 Checking dependencies...")
    try:
        import flask_socketio
    except ImportError:
        print("⚠️ Flask-SocketIO not found. Installing...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "flask-socketio"])
        print("✅ Flask-SocketIO installed")
    
    # Create templates folder dan HTML file
    create_templates_folder()
    
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
    
    # Start REST API server dengan WebSocket
    processor.start_server()
    
    # Export to JSON setelah selesai (jika server dihentikan)
    if SAVE_TO_FILE and processor.sensor_data_log:
        processor.export_to_json()

if __name__ == "__main__":
    main()