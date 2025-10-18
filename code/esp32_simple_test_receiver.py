#!/usr/bin/env python3
"""
ESP32 Simple Test Receiver - Minimal Version untuk Testing
Menerima data dari ESP32 dan tampilkan semua data mentah
"""

import serial
import time
from datetime import datetime

def main():
    # Konfigurasi
    PORT = 'COM3'  # Sesuaikan dengan port ESP32 Anda
    BAUDRATE = 115200
    
    print("📡 ESP32 Simple Test Receiver")
    print("=" * 40)
    print(f"Port: {PORT}")
    print(f"Baudrate: {BAUDRATE}")
    print("=" * 40)
    
    try:
        # Koneksi ke ESP32
        ser = serial.Serial(PORT, BAUDRATE, timeout=1)
        time.sleep(2)
        print(f"✅ Connected to ESP32 on {PORT}")
        print("🔄 Listening for data...")
        print("Press Ctrl+C to stop\n")
        
        data_count = 0
        
        while True:
            if ser.in_waiting > 0:
                # Baca data dari ESP32
                data_line = ser.readline().decode('utf-8').strip()
                
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                if data_line.startswith('SENSOR_DATA'):
                    data_count += 1
                    print(f"[{timestamp}] 📊 SENSOR_DATA #{data_count}")
                    
                    # Parse data
                    parts = data_line.split(',')
                    if len(parts) == 9:
                        print("✅ Valid format!")
                        sensor_names = ["MQ2", "MQ3", "MQ4", "MQ135", "MQ6", "MQ7", "MQ8", "MQ9"]
                        
                        for i in range(1, 9):  # Skip 'SENSOR_DATA'
                            sensor_name = sensor_names[i-1]
                            sensor_value = float(parts[i])
                            print(f"   {sensor_name}: {sensor_value:.6f}")
                    else:
                        print(f"❌ Invalid format: {len(parts)} parts")
                        print(f"   Data: {data_line}")
                else:
                    # Tampilkan data lain yang diterima
                    print(f"[{timestamp}] 📥 Other data: {data_line}")
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print(f"\n🛑 Stopped. Total SENSOR_DATA received: {data_count}")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if 'ser' in locals():
            ser.close()
            print("✅ Serial connection closed")

if __name__ == "__main__":
    main()
