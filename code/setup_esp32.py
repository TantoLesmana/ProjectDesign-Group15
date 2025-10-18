#!/usr/bin/env python3
"""
Setup script untuk ESP32 TensorFlow Lite Food Quality Assessment
"""

import serial.tools.list_ports
import os
import sys

def list_serial_ports():
    """List semua port serial yang tersedia"""
    ports = serial.tools.list_ports.comports()
    
    print("🔍 Available Serial Ports:")
    print("-" * 40)
    
    if not ports:
        print("❌ No serial ports found!")
        return []
    
    for i, port in enumerate(ports):
        print(f"{i+1}. {port.device} - {port.description}")
    
    return [port.device for port in ports]

def check_model_file(model_path):
    """Check apakah model file ada"""
    if os.path.exists(model_path):
        print(f"✅ Model file found: {model_path}")
        return True
    else:
        print(f"❌ Model file not found: {model_path}")
        print("Please copy food_model_250.tflite to current directory")
        return False

def test_serial_connection(port):
    """Test koneksi serial ke ESP32"""
    try:
        ser = serial.Serial(port, 115200, timeout=2)
        time.sleep(2)
        
        # Send test command
        ser.write(b'a\n')
        
        # Read response
        response = ser.readline().decode('utf-8').strip()
        
        if response:
            print(f"✅ ESP32 responding on {port}")
            print(f"Response: {response}")
            ser.close()
            return True
        else:
            print(f"❌ No response from ESP32 on {port}")
            ser.close()
            return False
            
    except Exception as e:
        print(f"❌ Error testing {port}: {e}")
        return False

def main():
    """Main setup function"""
    print("🍎 ESP32 Food Quality Assessment - Setup")
    print("=" * 50)
    
    # Check model file
    model_path = 'food_model_250.tflite'
    if not check_model_file(model_path):
        return
    
    # List serial ports
    ports = list_serial_ports()
    if not ports:
        return
    
    # Test each port
    print("\n🔧 Testing ESP32 connection...")
    working_port = None
    
    for port in ports:
        print(f"\nTesting {port}...")
        if test_serial_connection(port):
            working_port = port
            break
    
    if working_port:
        print(f"\n✅ Setup complete!")
        print(f"Use port: {working_port}")
        print(f"Run: python esp32_tflite_processor.py")
        print("\nDon't forget to:")
        print("1. Upload esp32_sensor_sender.ino to your ESP32")
        print("2. Connect all 8 MQ sensors to ESP32")
        print("3. Update PORT variable in esp32_tflite_processor.py")
    else:
        print("\n❌ No working ESP32 connection found")
        print("Please check:")
        print("1. ESP32 is connected via USB")
        print("2. ESP32 code is uploaded")
        print("3. Correct COM port is selected")

if __name__ == "__main__":
    main()
