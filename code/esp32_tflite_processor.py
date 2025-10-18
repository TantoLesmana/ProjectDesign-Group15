#!/usr/bin/env python3
"""
ESP32 Sensor Data Receiver dengan TensorFlow Lite Inference
Menerima data sensor dari ESP32 via Serial dan melakukan inference
"""

import serial
import numpy as np
# import tflite_runtime.interpreter as tflite
import time
import sys
from datetime import datetime

class ESP32SensorProcessor:
    def __init__(self, port='COM3', baudrate=115200, model_path='food_model_250.tflite'):
        """
        Inisialisasi processor untuk menerima data ESP32 dan inference
        
        Args:
            port: Port serial ESP32 (Windows: COM3, Linux: /dev/ttyUSB0)
            baudrate: Baud rate komunikasi serial
            model_path: Path ke file model TensorFlow Lite
        """
        self.port = port
        self.baudrate = baudrate
        self.model_path = model_path
        
        # Inisialisasi TensorFlow Lite interpreter
        self.interpreter = None
        self.input_details = None
        self.output_details = None
        
        # Setup serial connection
        self.serial_conn = None
        
        # Setup model
        self.setup_model()
        
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
            sys.exit(1)
    
    def connect_serial(self):
        """Koneksi ke ESP32 via Serial"""
        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)  # Wait for connection
            print(f"✅ Connected to ESP32 on {self.port}")
            return True
        except Exception as e:
            print(f"❌ Error connecting to ESP32: {e}")
            return False
    
    def parse_sensor_data(self, data_line):
        """
        Parse data sensor dari ESP32
        
        Format expected: SENSOR_DATA,val1,val2,val3,val4,val5,val6,val7,val8
        """
        try:
            parts = data_line.strip().split(',')
            if len(parts) != 9 or parts[0] != 'SENSOR_DATA':
                return None
            
            # Extract sensor values
            sensor_values = []
            for i in range(1, 9):  # Skip first part (SENSOR_DATA)
                sensor_values.append(float(parts[i]))
            
            return np.array(sensor_values, dtype=np.float32)
            
        except Exception as e:
            print(f"❌ Error parsing data: {e}")
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
            0: "🟢 FRESH - Makanan masih segar",
            1: "🟡 DEGRADED - Makanan mulai rusak", 
            2: "🔴 ERROR - Status tidak dapat ditentukan"
        }
        return interpretations.get(prediction, "❓ UNKNOWN")
    
    def process_sensor_data(self):
        """Main loop untuk memproses data sensor"""
        if not self.connect_serial():
            return
        
        print("\n🔄 Starting sensor data processing...")
        print("Press Ctrl+C to stop\n")
        
        try:
            while True:
                if self.serial_conn.in_waiting > 0:
                    # Read data from ESP32
                    data_line = self.serial_conn.readline().decode('utf-8').strip()
                    
                    if data_line.startswith('SENSOR_DATA'):
                        # Parse sensor data
                        sensor_data = self.parse_sensor_data(data_line)
                        
                        if sensor_data is not None:
                            # Run inference
                            prediction, confidence, probabilities = self.run_inference(sensor_data)
                            
                            if prediction is not None:
                                # Display results
                                timestamp = datetime.now().strftime("%H:%M:%S")
                                interpretation = self.interpret_prediction(prediction)
                                
                                print(f"[{timestamp}] {interpretation}")
                                print(f"Confidence: {confidence:.3f}")
                                print(f"Sensor values: {sensor_data}")
                                print(f"Probabilities: {probabilities}")
                                print("-" * 50)
                
                time.sleep(0.1)  # Small delay
                
        except KeyboardInterrupt:
            print("\n🛑 Stopping sensor processing...")
        except Exception as e:
            print(f"❌ Error in main loop: {e}")
        finally:
            if self.serial_conn:
                self.serial_conn.close()
                print("✅ Serial connection closed")

def main():
    """Main function"""
    print("🍎 ESP32 Food Quality Assessment System")
    print("=" * 50)
    
    # Konfigurasi - sesuaikan dengan setup Anda
    PORT = 'COM3'  # Windows: COM3, Linux: /dev/ttyUSB0
    MODEL_PATH = 'food_model_250.tflite'  # Path ke model TensorFlow Lite
    
    # Buat processor
    processor = ESP32SensorProcessor(port=PORT, model_path=MODEL_PATH)
    
    # Mulai processing
    processor.process_sensor_data()

if __name__ == "__main__":
    main()
