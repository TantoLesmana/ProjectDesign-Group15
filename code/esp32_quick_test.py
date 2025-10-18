#!/usr/bin/env python3
"""
ESP32 Quick Test Receiver - Versi Sederhana untuk Testing
Menerima data dari ESP32 dan tampilkan dalam format yang mudah dibaca
"""

import serial
import time
from datetime import datetime
import re

def main():
    # Konfigurasi
    PORT = 'COM3'  # Sesuaikan dengan port ESP32 Anda
    BAUDRATE = 115200
    
    print("📡 ESP32 Quick Test Receiver")
    print("=" * 40)
    print(f"Port: {PORT}")
    print(f"Baudrate: {BAUDRATE}")
    print("=" * 40)
    
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
                        print(f"📝 Dataset #{data_count} complete!")
                        print("=" * 60)
                        
                        # Clear buffer untuk dataset berikutnya
                        sensor_buffer.clear()
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print(f"\n🛑 Stopped.")
        print(f"📊 Complete datasets collected: {data_count}")
        print(f"📊 Partial data in buffer: {len(sensor_buffer)}")
        
        if sensor_buffer:
            print("\n📋 Partial data:")
            for i, value in enumerate(sensor_buffer):
                if i < len(sensor_names):
                    print(f"   {sensor_names[i]}: {value:.6f}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if 'ser' in locals():
            ser.close()
            print("✅ Serial connection closed")

if __name__ == "__main__":
    main()
