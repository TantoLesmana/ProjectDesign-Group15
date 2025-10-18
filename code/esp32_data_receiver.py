#!/usr/bin/env python3
"""
ESP32 Sensor Data Receiver - Data Only (No Model Processing)
Menerima data sensor dari ESP32 via Serial tanpa inference
"""

try:
    import serial
except ImportError:
    print("❌ PySerial not installed. Install with: pip install pyserial")
    sys.exit(1)

import numpy as np
import time
import sys
from datetime import datetime
import csv
import json

class ESP32DataReceiver:
    def __init__(self, port='COM3', baudrate=115200, save_to_file=True):
        """
        Inisialisasi receiver untuk menerima data ESP32
        
        Args:
            port: Port serial ESP32 (Windows: COM3, Linux: /dev/ttyUSB0)
            baudrate: Baud rate komunikasi serial
            save_to_file: Apakah data disimpan ke file
        """
        self.port = port
        self.baudrate = baudrate
        self.save_to_file = save_to_file
        
        # Setup serial connection
        self.serial_conn = None
        
        # Data storage
        self.sensor_data_log = []
        self.csv_filename = f"sensor_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        # Sensor names untuk display
        self.sensor_names = ["MQ2", "MQ3", "MQ4", "MQ135", "MQ6", "MQ7", "MQ8", "MQ9"]
        
        # Setup CSV file jika diperlukan
        if self.save_to_file:
            self.setup_csv_file()
    
    def setup_csv_file(self):
        """Setup CSV file untuk menyimpan data"""
        try:
            with open(self.csv_filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                # Write header
                header = ['Timestamp', 'DateTime'] + self.sensor_names
                writer.writerow(header)
            print(f"✅ CSV file created: {self.csv_filename}")
        except Exception as e:
            print(f"❌ Error creating CSV file: {e}")
    
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
    
    def save_data_to_csv(self, sensor_data):
        """Simpan data ke CSV file"""
        try:
            timestamp = time.time()
            datetime_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            with open(self.csv_filename, 'a', newline='') as csvfile:
                writer = csv.writer(csvfile)
                row = [timestamp, datetime_str] + sensor_data.tolist()
                writer.writerow(row)
                
        except Exception as e:
            print(f"❌ Error saving to CSV: {e}")
    
    def display_sensor_data(self, sensor_data):
        """Display data sensor dengan format yang rapi"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        print(f"\n[{timestamp}] 📊 Sensor Data:")
        print("-" * 50)
        
        for i, (name, value) in enumerate(zip(self.sensor_names, sensor_data)):
            print(f"{name:>6}: {value:>8.6f}")
        
        print("-" * 50)
    
    def get_statistics(self, sensor_data):
        """Hitung statistik sederhana dari data sensor"""
        stats = {
            'min': np.min(sensor_data),
            'max': np.max(sensor_data),
            'mean': np.mean(sensor_data),
            'std': np.std(sensor_data)
        }
        return stats
    
    def display_statistics(self, stats):
        """Display statistik data"""
        print("📈 Statistics:")
        print(f"  Min:    {stats['min']:.6f}")
        print(f"  Max:    {stats['max']:.6f}")
        print(f"  Mean:   {stats['mean']:.6f}")
        print(f"  Std:    {stats['std']:.6f}")
    
    def process_sensor_data(self):
        """Main loop untuk memproses data sensor"""
        if not self.connect_serial():
            return
        
        print("\n🔄 Starting sensor data collection...")
        print("Press Ctrl+C to stop\n")
        
        data_count = 0
        
        try:
            while True:
                if self.serial_conn.in_waiting > 0:
                    # Read data from ESP32
                    data_line = self.serial_conn.readline().decode('utf-8').strip()
                    
                    if data_line.startswith('SENSOR_DATA'):
                        # Parse sensor data
                        sensor_data = self.parse_sensor_data(data_line)
                        
                        if sensor_data is not None:
                            data_count += 1
                            
                            # Store data
                            self.sensor_data_log.append(sensor_data.copy())
                            
                            # Display data
                            self.display_sensor_data(sensor_data)
                            
                            # Calculate and display statistics
                            stats = self.get_statistics(sensor_data)
                            self.display_statistics(stats)
                            
                            # Save to CSV if enabled
                            if self.save_to_file:
                                self.save_data_to_csv(sensor_data)
                            
                            print(f"📝 Data count: {data_count}")
                            print(f"💾 Saved to: {self.csv_filename}")
                            print("=" * 60)
                
                time.sleep(0.1)  # Small delay
                
        except KeyboardInterrupt:
            print("\n🛑 Stopping data collection...")
            print(f"📊 Total data collected: {data_count}")
            
            # Final statistics
            if self.sensor_data_log:
                all_data = np.array(self.sensor_data_log)
                print("\n📈 Overall Statistics:")
                print(f"  Total samples: {len(self.sensor_data_log)}")
                print(f"  Data shape: {all_data.shape}")
                
                for i, sensor_name in enumerate(self.sensor_names):
                    sensor_stats = {
                        'min': np.min(all_data[:, i]),
                        'max': np.max(all_data[:, i]),
                        'mean': np.mean(all_data[:, i]),
                        'std': np.std(all_data[:, i])
                    }
                    print(f"  {sensor_name}: min={sensor_stats['min']:.6f}, "
                          f"max={sensor_stats['max']:.6f}, "
                          f"mean={sensor_stats['mean']:.6f}")
            
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
                    'baudrate': self.baudrate
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
    print("📡 ESP32 Sensor Data Receiver - Data Collection Only")
    print("=" * 60)
    
    # Konfigurasi - sesuaikan dengan setup Anda
    PORT = 'COM3'  # Windows: COM3, Linux: /dev/ttyUSB0
    SAVE_TO_FILE = True  # Set False jika tidak ingin save ke file
    
    # Buat receiver
    receiver = ESP32DataReceiver(port=PORT, save_to_file=SAVE_TO_FILE)
    
    # Mulai data collection
    receiver.process_sensor_data()
    
    # Export to JSON setelah selesai
    if SAVE_TO_FILE:
        receiver.export_to_json()

if __name__ == "__main__":
    main()
