import speedtest
import subprocess
import time
import statistics
import datetime
import pandas as pd
from pathlib import Path
import platform
import os

class InternetMonitor:
    def __init__(self, log_file="internet_stats.parquet", speed_test_interval=300):
        self.log_file = Path(log_file)
        self.speed_test_interval = speed_test_interval
        self.last_speed_test = 0
        self.log_count = 0
        
        # Initialize or load existing data
        if self.log_file.exists():
            self.df = pd.read_parquet(self.log_file)
            self.log_count = len(self.df)
        else:
            self.df = pd.DataFrame(columns=[
                "timestamp", "download_speed", "upload_speed",
                "ping", "packet_loss", "jitter"
            ])
        
    def measure_speed(self):
        """Measure download and upload speeds"""
        current_time = time.time()
        
        # Always return None if it's not time for a new speed test
        if (current_time - self.last_speed_test) < self.speed_test_interval:
            return None, None
            
        try:
            st = speedtest.Speedtest()
            download = st.download() / 1_000_000  # Convert to Mbps
            upload = st.upload() / 1_000_000      # Convert to Mbps
            self.last_speed_test = current_time
            return download, upload
        except Exception as e:
            print(f"Speed test failed: {e}")
            return None, None

    def ping_command(self, host="8.8.8.8", count=3):
        """Use system ping command instead of ping3"""
        system = platform.system().lower()
        
        try:
            if system == "windows":
                cmd = ["ping", "-n", str(count), host]
            else:  # Linux or MacOS
                cmd = ["ping", "-c", str(count), host]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # Parse the ping output
                output = result.stdout
                if system == "windows":
                    # Parse Windows ping output
                    times = [float(line.split("time=")[1].split("ms")[0].strip()) 
                            for line in output.splitlines() 
                            if "time=" in line]
                else:
                    # Parse Linux/MacOS ping output
                    times = [float(line.split("time=")[1].split(" ")[0]) 
                            for line in output.splitlines() 
                            if "time=" in line]
                
                if times:
                    avg_ping = statistics.mean(times)
                    jitter = statistics.stdev(times) if len(times) > 1 else 0
                    packet_loss = 100 - (len(times) / count * 100)
                    return avg_ping, jitter, packet_loss
            
            return None, None, 100
            
        except Exception as e:
            print(f"Ping failed: {e}")
            return None, None, 100

    def collect_metrics(self):
        """Collect all metrics and store them"""
        timestamp = pd.Timestamp.now()
        download, upload = self.measure_speed()
        ping, jitter, packet_loss = self.ping_command()

        new_row = pd.DataFrame([{
            "timestamp": timestamp,
            "download_speed": download,
            "upload_speed": upload,
            "ping": ping,
            "jitter": jitter,
            "packet_loss": packet_loss
        }])
        
        self.df = pd.concat([self.df, new_row], ignore_index=True)
        self.log_count += 1

    def save_stats(self):
        """Save stats to parquet file"""
        self.df.to_parquet(self.log_file, index=False)

    def print_latest_stats(self):
        """Print the most recent measurements"""
        if len(self.df) == 0:
            return "No measurements available"

        latest = self.df.iloc[-1]
        
        # Clear the terminal (platform independent)
        os.system('cls' if platform.system().lower() == "windows" else 'clear')
        
        output = [
            f"=== Latest Internet Connection Stats (Total Logs: {self.log_count}) ===",
            f"Timestamp: {latest['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}"
        ]
        
        if latest['download_speed'] is not None:
            output.extend([
                f"Download Speed: {latest['download_speed']:.2f} Mbps",
                f"Upload Speed: {latest['upload_speed']:.2f} Mbps"
            ])
        else:
            output.append("Speed test pending...")
        
        if latest['ping'] is not None:
            output.extend([
                f"Ping: {latest['ping']:.2f} ms",
                f"Jitter: {latest['jitter']:.2f} ms",
                f"Packet Loss: {latest['packet_loss']:.2f}%"
            ])
        else:
            output.append("Ping measurement failed")
        
        print("\n".join(output))

def main():
    monitor = InternetMonitor(speed_test_interval=300)
    
    try:
        while True:
            monitor.collect_metrics()
            monitor.print_latest_stats()
            monitor.save_stats()
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user")
        monitor.save_stats()

if __name__ == "__main__":
    main()