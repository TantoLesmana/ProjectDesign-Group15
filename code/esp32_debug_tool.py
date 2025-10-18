#!/usr/bin/env python3
"""
ESP32 Debug Receiver - Troubleshooting Tool
Untuk debugging komunikasi ESP32 dan melihat data mentah
"""

import serial
import time
from datetime import datetime

def debug_esp32_connection(port='COM3', baudrate=115200):
    """Debug koneksi ESP32 dan lihat semua data yang masuk"""
    
    print("🔍 ESP32 Debug Tool")
    print("=" * 40)
    print(f"Port: {port}")
    print(f"Baudrate: {baudrate}")
    print("=" * 40)
    
    try:
        # Koneksi ke ESP32
        ser = serial.Serial(port, baudrate, timeout=1)
        time.sleep(2)
        print(f"✅ Connected to ESP32 on {port}")
        
        print("\n🔄 Listening for data...")
        print("Press Ctrl+C to stop\n")
        
        data_count = 0
        raw_data_count = 0
        
        while True:
            if ser.in_waiting > 0:
                # Baca semua data yang tersedia
                raw_data = ser.read(ser.in_waiting)
                raw_data_count += 1
                
                try:
                    # Decode data
                    data_str = raw_data.decode('utf-8', errors='ignore')
                    
                    # Tampilkan data mentah
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    print(f"[{timestamp}] Raw #{raw_data_count}: {repr(data_str)}")
                    
                    # Check jika ada data sensor
                    if 'SENSOR_DATA' in data_str:
                        data_count += 1
                        print(f"🎯 Found SENSOR_DATA #{data_count}")
                        
                        # Parse dan tampilkan
                        lines = data_str.strip().split('\n')
                        for line in lines:
                            if line.startswith('SENSOR_DATA'):
                                parts = line.split(',')
                                if len(parts) == 9:
                                    print(f"   ✅ Valid format: {len(parts)} parts")
                                    for i, part in enumerate(parts):
                                        if i == 0:
                                            print(f"   {part}")
                                        else:
                                            try:
                                                val = float(part)
                                                print(f"   Sensor {i}: {val}")
                                            except:
                                                print(f"   Sensor {i}: {part} (invalid)")
                                else:
                                    print(f"   ❌ Invalid format: {len(parts)} parts")
                                    print(f"   Data: {line}")
                
                except Exception as e:
                    print(f"❌ Error processing data: {e}")
                    print(f"Raw bytes: {raw_data}")
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print(f"\n🛑 Stopped.")
        print(f"📊 Raw data received: {raw_data_count}")
        print(f"📊 SENSOR_DATA found: {data_count}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        
    finally:
        if 'ser' in locals():
            ser.close()
            print("✅ Serial connection closed")

def test_esp32_communication(port='COM3', baudrate=115200):
    """Test komunikasi dengan ESP32"""
    
    print("🧪 ESP32 Communication Test")
    print("=" * 40)
    
    try:
        ser = serial.Serial(port, baudrate, timeout=2)
        time.sleep(2)
        print(f"✅ Connected to ESP32 on {port}")
        
        # Test 1: Send command 'a'
        print("\n📤 Sending command 'a'...")
        ser.write(b'a\n')
        time.sleep(1)
        
        # Check response
        if ser.in_waiting > 0:
            response = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
            print(f"📥 Response: {repr(response)}")
        else:
            print("❌ No response received")
        
        # Test 2: Wait for any data
        print("\n⏳ Waiting for any data (5 seconds)...")
        start_time = time.time()
        
        while time.time() - start_time < 5:
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                print(f"📥 Data received: {repr(data)}")
                break
            time.sleep(0.1)
        else:
            print("❌ No data received in 5 seconds")
        
        ser.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    """Main function"""
    print("🔧 ESP32 Debug & Troubleshooting Tool")
    print("=" * 50)
    
    # Konfigurasi
    PORT = 'COM3'  # Sesuaikan dengan port ESP32
    
    print("Choose option:")
    print("1. Debug connection (see all raw data)")
    print("2. Test communication")
    print("3. Both")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == '1':
        debug_esp32_connection(PORT)
    elif choice == '2':
        test_esp32_communication(PORT)
    elif choice == '3':
        test_esp32_communication(PORT)
        print("\n" + "="*50)
        debug_esp32_connection(PORT)
    else:
        print("Invalid choice")

if __name__ == "__main__":
    main()
