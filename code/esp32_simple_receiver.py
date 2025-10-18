#!/usr/bin/env python3
"""
ESP32 Simple Data Receiver - Minimal Version
Versi sederhana untuk menerima dan menampilkan data sensor ESP32
"""

import serial
import time
from datetime import datetime

def main():
    # Konfigurasi
    PORT = 'COM3'  # Sesuaikan dengan port ESP32 Anda
    BAUDRATE = 115200
    
    # Sensor names
    sensor_names = ["MQ2", "MQ3", "MQ4", "MQ135", "MQ6", "MQ7", "MQ8", "MQ9"]
    
    try:
        # Koneksi ke ESP32
        ser = serial.Serial(PORT, BAUDRATE, timeout=1)
        time.sleep(2)
        print(f"✅ Connected to ESP32 on {PORT}")
        print("🔄 Waiting for sensor data...")
        print("Press Ctrl+C to stop\n")
        
        data_count = 0
        
        while True:
            if ser.in_waiting > 0:
                # Baca data dari ESP32
                data_line = ser.readline().decode('utf-8').strip()
                
                if data_line.startswith('SENSOR_DATA'):
                    # Parse data
                    parts = data_line.split(',')
                    if len(parts) == 9:
                        data_count += 1
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        
                        print(f"\n[{timestamp}] 📊 Data #{data_count}")
                        print("-" * 40)
                        
                        # Tampilkan data sensor
                        for i in range(1, 9):  # Skip 'SENSOR_DATA'
                            sensor_name = sensor_names[i-1]
                            sensor_value = float(parts[i])
                            print(f"{sensor_name:>6}: {sensor_value:>8.6f}")
                        
                        print("-" * 40)
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print(f"\n🛑 Stopped. Total data received: {data_count}")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if 'ser' in locals():
            ser.close()
            print("✅ Serial connection closed")

if __name__ == "__main__":
    print("📡 ESP32 Simple Data Receiver")
    print("=" * 40)
    main()
