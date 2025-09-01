#!/usr/bin/env python3
"""
Utility script to find the IPv4 address for your Supabase database
Run this locally to get the IP address, then update the hardcoded IP in database_config_supabase.py
"""

import socket
import subprocess
import sys

def find_supabase_ip():
    """Find the IPv4 address for your Supabase database"""
    
    # Your Supabase hostname
    hostname = "db.rolcoegikoeblxzqgkix.supabase.co"
    
    print(f"🔍 Finding IPv4 address for: {hostname}")
    print("=" * 50)
    
    # Method 1: Using socket.getaddrinfo
    try:
        print("Method 1: socket.getaddrinfo")
        addresses = socket.getaddrinfo(hostname, None, socket.AF_INET)
        for addr in addresses:
            ip = addr[4][0]
            print(f"  ✅ IPv4: {ip}")
    except Exception as e:
        print(f"  ❌ Failed: {e}")
    
    # Method 2: Using nslookup (if available)
    try:
        print("\nMethod 2: nslookup")
        result = subprocess.run(['nslookup', hostname], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(result.stdout)
        else:
            print(f"  ❌ nslookup failed: {result.stderr}")
    except Exception as e:
        print(f"  ❌ nslookup not available: {e}")
    
    # Method 3: Using ping to get IP
    try:
        print("\nMethod 3: ping (to get IP)")
        result = subprocess.run(['ping', '-n', '1', hostname], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            for line in lines:
                if 'Pinging' in line and '[' in line and ']' in line:
                    # Extract IP from ping output
                    start = line.find('[') + 1
                    end = line.find(']')
                    if start > 0 and end > start:
                        ip = line[start:end]
                        print(f"  ✅ IPv4: {ip}")
                        break
        else:
            print(f"  ❌ ping failed: {result.stderr}")
    except Exception as e:
        print(f"  ❌ ping not available: {e}")
    
    print("\n" + "=" * 50)
    print("📝 Instructions:")
    print("1. Copy one of the IPv4 addresses above")
    print("2. Update the 'supabase_ipv4' variable in database_config_supabase.py")
    print("3. Replace the example IP '35.200.186.57' with your actual IP")

if __name__ == "__main__":
    find_supabase_ip()
