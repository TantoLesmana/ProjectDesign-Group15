#!/usr/bin/env python3
"""
Setup script untuk ESP32 Data Receiver
Install dependencies dan check setup
"""

import subprocess
import sys
import os

def install_package(package):
    """Install package menggunakan pip"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        return True
    except subprocess.CalledProcessError:
        return False

def check_package(package):
    """Check apakah package sudah terinstall"""
    try:
        __import__(package)
        return True
    except ImportError:
        return False

def main():
    print("🔧 ESP32 Data Receiver Setup")
    print("=" * 40)
    
    # List packages yang diperlukan
    required_packages = [
        ('pyserial', 'serial'),
        ('numpy', 'numpy')
    ]
    
    print("📦 Checking required packages...")
    
    missing_packages = []
    
    for pip_name, import_name in required_packages:
        if check_package(import_name):
            print(f"✅ {pip_name} - OK")
        else:
            print(f"❌ {pip_name} - Missing")
            missing_packages.append(pip_name)
    
    if missing_packages:
        print(f"\n📥 Installing missing packages: {', '.join(missing_packages)}")
        
        for package in missing_packages:
            print(f"Installing {package}...")
            if install_package(package):
                print(f"✅ {package} installed successfully")
            else:
                print(f"❌ Failed to install {package}")
                return False
    
    print("\n✅ All packages installed!")
    
    # Check serial ports
    print("\n🔍 Checking serial ports...")
    try:
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        
        if ports:
            print("Available ports:")
            for port in ports:
                print(f"  - {port.device}: {port.description}")
        else:
            print("❌ No serial ports found")
            print("💡 Make sure ESP32 is connected via USB")
    except Exception as e:
        print(f"❌ Error checking ports: {e}")
    
    print("\n🚀 Setup complete!")
    print("Run: python esp32_data_receiver_fixed.py")

if __name__ == "__main__":
    main()
