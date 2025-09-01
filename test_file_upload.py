#!/usr/bin/env python3
"""
Test script for file upload functionality
"""

import os
import pandas as pd
from datetime import datetime

def create_test_csv():
    """Create a test CSV file for upload testing"""
    # Sample transaction data
    data = {
        'stock_name': ['Reliance Industries', 'TCS', 'HDFC Bank', 'Infosys'],
        'ticker': ['RELIANCE', 'TCS', 'HDFCBANK', 'INFY'],
        'quantity': [10, 5, 20, 15],
        'price': [2500, 3500, 1500, 1200],
        'transaction_type': ['buy', 'buy', 'buy', 'buy'],
        'date': ['2024-01-15', '2024-02-20', '2024-03-10', '2024-04-05'],
        'channel': ['Direct', 'Broker', 'Direct', 'Broker']
    }
    
    df = pd.DataFrame(data)
    df['date'] = pd.to_datetime(df['date'])
    
    # Save to CSV
    filename = f"test_portfolio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(filename, index=False)
    
    print(f"✅ Created test CSV file: {filename}")
    print(f"📊 Sample data:")
    print(df.head())
    
    return filename

def test_github_path_conversion():
    """Test the GitHub path conversion functionality"""
    from database_config_supabase import convert_to_github_path, get_user_folder_path
    
    # Test local development
    os.environ.pop('STREAMLIT_SERVER_RUN_ON_IP', None)
    local_path = convert_to_github_path('testuser', './my_portfolio')
    print(f"🔧 Local path: {local_path}")
    
    # Test Streamlit Cloud
    os.environ['STREAMLIT_SERVER_RUN_ON_IP'] = '0.0.0.0'
    cloud_path = convert_to_github_path('testuser', './my_portfolio')
    print(f"☁️ Cloud path: {cloud_path}")
    
    # Test with no folder path
    cloud_path_default = convert_to_github_path('testuser')
    print(f"☁️ Cloud path (default): {cloud_path_default}")

if __name__ == "__main__":
    print("🧪 Testing File Upload Functionality")
    print("=" * 50)
    
    # Test GitHub path conversion
    print("\n1. Testing GitHub Path Conversion:")
    test_github_path_conversion()
    
    # Create test CSV
    print("\n2. Creating Test CSV File:")
    test_file = create_test_csv()
    
    print("\n✅ All tests completed!")
    print(f"📁 Test file created: {test_file}")
    print("\n💡 You can now use this file to test the upload functionality in the Streamlit app.")
