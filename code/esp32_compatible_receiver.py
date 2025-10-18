#!/usr/bin/env python3
"""
ESP32 Data Receiver - Compatible dengan Format ESP32 yang Sebenarnya
Menerima data sensor dari ESP32 dalam format yang benar
"""

import serial
import numpy as np
import time
import sys
from datetime import datetime
import csv
import json
import re

class ESP32CompatibleReceiver:
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
        
        # Buffer untuk data sensor
        self.sensor_buffer = []
        
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
        print("📝 Collecting data from 8 sensors...")
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
                                
                                # Display data
                                self.display_sensor_data(sensor_data)
                                
                                # Calculate and display statistics
                                stats = self.get_statistics(sensor_data)
                                self.display_statistics(stats)
                                
                                # Save to CSV if enabled
                                if self.save_to_file:
                                    self.save_data_to_csv(sensor_data)
                                
                                print(f"📝 Complete dataset #{data_count}")
                                print(f"💾 Saved to: {self.csv_filename}")
                                print("=" * 60)
                
                time.sleep(0.1)  # Small delay
                
        except KeyboardInterrupt:
            print("\n🛑 Stopping data collection...")
            print(f"📊 Total complete datasets collected: {data_count}")
            print(f"📊 Partial data in buffer: {len(self.sensor_buffer)}")
            
            # Final statistics
            if self.sensor_data_log:
                all_data = np.array(self.sensor_data_log)
                print("\n📈 Overall Statistics:")
                print(f"  Total complete datasets: {len(self.sensor_data_log)}")
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
    print("📡 ESP32 Compatible Data Receiver")
    print("=" * 50)
    
    # Konfigurasi - sesuaikan dengan setup Anda
    PORT = 'COM3'  # Windows: COM3, Linux: /dev/ttyUSB0
    SAVE_TO_FILE = True  # Set False jika tidak ingin save ke file
    
    # Buat receiver
    receiver = ESP32CompatibleReceiver(port=PORT, save_to_file=SAVE_TO_FILE)
    
    # Mulai data collection
    receiver.process_sensor_data()
    
    # Export to JSON setelah selesai
    if SAVE_TO_FILE:
        receiver.export_to_json()

if __name__ == "__main__":
    main()
