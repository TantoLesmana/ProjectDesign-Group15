#!/usr/bin/env python3
"""
ESP32 Bidirectional Communication - Sensor Data + Prediction Results
Menerima data sensor dari ESP32, jalankan inference, kirim hasil prediksi kembali ke ESP32
"""

import serial
import numpy as np
import time
import sys
from datetime import datetime
import csv
import json
import re

# TensorFlow Lite import
try:
    import tflite_runtime.interpreter as tflite
    TFLITE_AVAILABLE = True
except ImportError:
    print("⚠️ TensorFlow Lite not available. Install with: pip install tflite-runtime")
    TFLITE_AVAILABLE = False

class ESP32BidirectionalProcessor:
    def __init__(self, port='COM3', baudrate=115200, model_path='food_model_250.tflite', save_to_file=True):
        """
        Inisialisasi processor untuk komunikasi dua arah dengan ESP32
        
        Args:
            port: Port serial ESP32 (Windows: COM3, Linux: /dev/ttyUSB0)
            baudrate: Baud rate komunikasi serial
            model_path: Path ke file model TensorFlow Lite
            save_to_file: Apakah data disimpan ke file
        """
        self.port = port
        self.baudrate = baudrate
        self.model_path = model_path
        self.save_to_file = save_to_file
        
        # Setup serial connection
        self.serial_conn = None
        
        # Data storage
        self.sensor_data_log = []
        self.csv_filename = f"sensor_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        # Sensor names untuk display
        self.sensor_names = ["MQ2", "MQ3", "MQ4", "MQ135", "MQ6", "MQ7", "MQ8", "MQ9"]
        
        # Buffer untuk data sensor
        self.sensor_buffer = []
        
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
    
    def setup_model(self):
        """Setup TensorFlow Lite model"""
        try:
            self.interpreter = tflite.Interpreter(model_path=self.model_path)
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
    
    def connect_serial(self):
        """Koneksi ke ESP32 via Serial"""
        try:
            print(f"🔌 Attempting to connect to {self.port} at {self.baudrate} baud...")
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)  # Wait for connection
            print(f"✅ Connected to ESP32 on {self.port}")
            return True
        except serial.SerialException as e:
            print(f"❌ Serial connection error: {e}")
            print("💡 Check if:")
            print("   - ESP32 is connected via USB")
            print("   - Correct COM port is selected")
            print("   - No other program is using the port")
            return False
        except Exception as e:
            print(f"❌ Unexpected error connecting to ESP32: {e}")
            return False
    
    def parse_esp32_data(self, data_line):
        """
        Parse data dari ESP32 dalam format:
        ESP32 Raw: 226 | Raspberry Compatible: 3613.35 | Normalized: 0.0552
        """
        try:
            # Extract normalized value menggunakan regex
            pattern = r'Normalized:\s*([0-9.]+)'
            match = re.search(pattern, data_line)
            
            if match:
                normalized_value = float(match.group(1))
                return normalized_value
            else:
                return None
                
        except Exception as e:
            print(f"❌ Error parsing ESP32 data: {e}")
            return None
    
    def collect_sensor_data(self):
        """Kumpulkan data dari 8 sensor"""
        if len(self.sensor_buffer) >= 8:
            # Ambil 8 data terbaru
            sensor_data = np.array(self.sensor_buffer[-8:], dtype=np.float32)
            self.sensor_buffer.clear()  # Clear buffer
            return sensor_data
        return None
    
    def run_inference(self, sensor_data):
        """
        Jalankan inference dengan TensorFlow Lite
        
        Args:
            sensor_data: Array numpy dengan 8 nilai sensor
            
        Returns:
            prediction: Prediksi kelas (0=fresh, 1=degraded, 2=error)
            confidence: Confidence score
        """
        if self.interpreter is None:
            # Simulate prediction jika model tidak tersedia
            return 0, 0.85, np.array([0.85, 0.10, 0.05])
        
        try:
            # Reshape data untuk model (batch_size=1, features=8)
            input_data = np.expand_dims(sensor_data, axis=0)
            
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
            return None, None, None
    
    def interpret_prediction(self, prediction):
        """Interpretasi hasil prediksi"""
        interpretations = {
            0: "FRESH",
            1: "DEGRADED", 
            2: "ERROR"
        }
        return interpretations.get(prediction, "UNKNOWN")
    
    def send_prediction_to_esp32(self, prediction, confidence):
        """Kirim hasil prediksi ke ESP32"""
        try:
            # Format: PREDICTION,class,confidence
            prediction_str = f"PREDICTION,{prediction},{confidence:.3f}\n"
            self.serial_conn.write(prediction_str.encode('utf-8'))
            print(f"📤 Sent prediction to ESP32: {prediction} ({confidence:.3f})")
            
        except Exception as e:
            print(f"❌ Error sending prediction to ESP32: {e}")
    
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
        
        print(f"\n[{timestamp}] 📊 Sensor Data + Prediction:")
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
    
    def process_sensor_data(self):
        """Main loop untuk memproses data sensor"""
        if not self.connect_serial():
            return
        
        print("\n🔄 Starting bidirectional sensor data processing...")
        print("📝 Collecting data from 8 sensors...")
        print("🤖 Running AI inference...")
        print("📤 Sending predictions to ESP32...")
        print("Press Ctrl+C to stop\n")
        
        data_count = 0
        
        try:
            while True:
                if self.serial_conn.in_waiting > 0:
                    # Read data from ESP32
                    data_line = self.serial_conn.readline().decode('utf-8').strip()
                    
                    # Parse data ESP32
                    normalized_value = self.parse_esp32_data(data_line)
                    
                    if normalized_value is not None:
                        # Tambahkan ke buffer
                        self.sensor_buffer.append(normalized_value)
                        
                        print(f"📥 Sensor data received: {normalized_value:.6f} (Buffer: {len(self.sensor_buffer)}/8)")
                        
                        # Check jika sudah ada 8 data
                        if len(self.sensor_buffer) >= 8:
                            sensor_data = self.collect_sensor_data()
                            
                            if sensor_data is not None:
                                data_count += 1
                                
                                # Store data
                                self.sensor_data_log.append(sensor_data.copy())
                                
                                # Run inference
                                prediction, confidence, probabilities = self.run_inference(sensor_data)
                                
                                if prediction is not None:
                                    # Display results
                                    self.display_sensor_data(sensor_data, prediction, confidence)
                                    
                                    # Send prediction to ESP32
                                    self.send_prediction_to_esp32(prediction, confidence)
                                    
                                    # Save to CSV if enabled
                                    if self.save_to_file:
                                        self.save_data_to_csv(sensor_data, prediction, confidence)
                                    
                                    print(f"📝 Complete dataset #{data_count}")
                                    print(f"💾 Saved to: {self.csv_filename}")
                                    print("=" * 80)
                
                time.sleep(0.1)  # Small delay
                
        except KeyboardInterrupt:
            print("\n🛑 Stopping data processing...")
            print(f"📊 Total complete datasets processed: {data_count}")
            print(f"📊 Partial data in buffer: {len(self.sensor_buffer)}")
            
        except Exception as e:
            print(f"❌ Error in main loop: {e}")
        finally:
            if self.serial_conn:
                self.serial_conn.close()
                print("✅ Serial connection closed")
    
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
                    'port': self.port,
                    'baudrate': self.baudrate,
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
    print("🤖 ESP32 Bidirectional AI Processor")
    print("=" * 60)
    
    # Konfigurasi - sesuaikan dengan setup Anda
    PORT = 'COM3'  # Windows: COM3, Linux: /dev/ttyUSB0
    MODEL_PATH = 'food_model_250.tflite'  # Path ke model TensorFlow Lite
    SAVE_TO_FILE = True  # Set False jika tidak ingin save ke file
    
    # Buat processor
    processor = ESP32BidirectionalProcessor(
        port=PORT, 
        model_path=MODEL_PATH, 
        save_to_file=SAVE_TO_FILE
    )
    
    # Mulai data processing
    processor.process_sensor_data()
    
    # Export to JSON setelah selesai
    if SAVE_TO_FILE:
        processor.export_to_json()

if __name__ == "__main__":
    main()
