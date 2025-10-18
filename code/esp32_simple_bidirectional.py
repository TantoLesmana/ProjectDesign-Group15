#!/usr/bin/env python3
"""
ESP32 Simple Bidirectional Test - Versi Sederhana untuk Testing
Menerima data sensor, kirim prediksi sederhana ke ESP32
"""

import serial
import time
from datetime import datetime
import re

def main():
    # Konfigurasi
    PORT = 'COM3'  # Sesuaikan dengan port ESP32 Anda
    BAUDRATE = 115200
    
    print("🤖 ESP32 Simple Bidirectional Test")
    print("=" * 50)
    print(f"Port: {PORT}")
    print(f"Baudrate: {BAUDRATE}")
    print("=" * 50)
    
    # Buffer untuk data sensor
    sensor_buffer = []
    sensor_names = ["MQ2", "MQ3", "MQ4", "MQ135", "MQ6", "MQ7", "MQ8", "MQ9"]
    data_count = 0
    
    try:
        # Koneksi ke ESP32
        ser = serial.Serial(PORT, BAUDRATE, timeout=1)
        time.sleep(2)
        print(f"✅ Connected to ESP32 on {PORT}")
        print("🔄 Collecting data from 8 sensors...")
        print("🤖 Running simple AI prediction...")
        print("📤 Sending predictions to ESP32...")
        print("Press Ctrl+C to stop\n")
        
        while True:
            if ser.in_waiting > 0:
                # Baca data dari ESP32
                data_line = ser.readline().decode('utf-8').strip()
                
                # Parse data ESP32 menggunakan regex
                pattern = r'Normalized:\s*([0-9.]+)'
                match = re.search(pattern, data_line)
                
                if match:
                    normalized_value = float(match.group(1))
                    sensor_buffer.append(normalized_value)
                    
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    print(f"[{timestamp}] Sensor {len(sensor_buffer)}: {normalized_value:.6f}")
                    
                    # Check jika sudah ada 8 data
                    if len(sensor_buffer) >= 8:
                        data_count += 1
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        
                        print(f"\n[{timestamp}] 📊 Complete Dataset #{data_count}")
                        print("-" * 50)
                        
                        # Tampilkan semua data sensor
                        for i, (name, value) in enumerate(zip(sensor_names, sensor_buffer)):
                            print(f"{name:>6}: {value:>8.6f}")
                        
                        print("-" * 50)
                        
                        # Simple AI Prediction (berdasarkan rata-rata)
                        avg_value = sum(sensor_buffer) / len(sensor_buffer)
                        
                        if avg_value < 0.05:
                            prediction = 0  # FRESH
                            confidence = 0.9
                            status = "FRESH"
                            emoji = "🟢"
                        elif avg_value < 0.08:
                            prediction = 1  # DEGRADED
                            confidence = 0.8
                            status = "DEGRADED"
                            emoji = "🟡"
                        else:
                            prediction = 2  # ERROR
                            confidence = 0.7
                            status = "ERROR"
                            emoji = "🔴"
                        
                        print(f"🤖 AI Prediction: {status}")
                        print(f"📊 Confidence: {confidence:.3f}")
                        print(f"{emoji} Status: {status}")
                        
                        # Kirim prediksi ke ESP32
                        prediction_str = f"PREDICTION,{prediction},{confidence:.3f}\n"
                        ser.write(prediction_str.encode('utf-8'))
                        print(f"📤 Sent to ESP32: {prediction} ({confidence:.3f})")
                        
                        print("-" * 50)
                        print(f"📝 Dataset #{data_count} complete!")
                        print("=" * 70)
                        
                        # Clear buffer untuk dataset berikutnya
                        sensor_buffer.clear()
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print(f"\n🛑 Stopped.")
        print(f"📊 Complete datasets processed: {data_count}")
        print(f"📊 Partial data in buffer: {len(sensor_buffer)}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if 'ser' in locals():
            ser.close()
            print("✅ Serial connection closed")

if __name__ == "__main__":
    main()
