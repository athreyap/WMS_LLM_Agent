#!/usr/bin/env python3
"""
Test script to check database connectivity and table structure
"""

import os
from supabase import create_client

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://rolcoegikoeblxzqgkix.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJvbGNvZWdpa29lYmx4enFna2l4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTY1NDM2MjUsImV4cCI6MjA3MjExOTYyNX0.Vwg2hgdKNQGizJiulgTlxXkTLfy-J3vFNkX8gA_6ul4')

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def test_database_connection():
    """Test basic database connectivity"""
    print("🔍 Testing database connection...")
    
    try:
        # Test users table
        result = supabase.table("users").select("*").limit(1).execute()
        print(f"✅ Users table accessible: {len(result.data)} records found")
        
        # Test investment_transactions table
        result = supabase.table("investment_transactions").select("*").limit(1).execute()
        print(f"✅ Investment transactions table accessible: {len(result.data)} records found")
        
        # Test investment_files table
        result = supabase.table("investment_files").select("*").limit(1).execute()
        print(f"✅ Investment files table accessible: {len(result.data)} records found")
        
        # Test stock_data table
        result = supabase.table("stock_data").select("*").limit(1).execute()
        print(f"✅ Stock data table accessible: {len(result.data)} records found")
        
        return True
        
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return False

def test_file_record_save():
    """Test saving a file record"""
    print("\n🔍 Testing file record save...")
    
    try:
        # Test data
        filename = "test_file.csv"
        file_path = "/tmp/test_user_investments/test_file.csv"
        user_id = 1
        
        # Generate file hash
        import hashlib
        file_hash = hashlib.md5(file_path.encode()).hexdigest()
        
        data = {
            "filename": filename,
            "file_path": file_path,
            "file_hash": file_hash,
            "customer_name": f"user_{user_id}",
            "status": "processed"
        }
        
        print(f"📝 Attempting to save: {data}")
        
        result = supabase.table("investment_files").insert(data).execute()
        
        if result.data:
            print(f"✅ File record saved successfully: {result.data[0]}")
            return result.data[0]
        else:
            print(f"❌ Failed to save file record")
            return None
            
    except Exception as e:
        print(f"❌ Error saving file record: {e}")
        return None

def test_user_creation():
    """Test user creation"""
    print("\n🔍 Testing user creation...")
    
    try:
        # Test data
        username = "testuser123"
        password_hash = "test_hash_123"
        email = "test@example.com"
        
        data = {
            "username": username,
            "password_hash": password_hash,
            "email": email,
            "role": "user"
        }
        
        print(f"📝 Attempting to create user: {username}")
        
        result = supabase.table("users").insert(data).execute()
        
        if result.data:
            print(f"✅ User created successfully: {result.data[0]}")
            return result.data[0]
        else:
            print(f"❌ Failed to create user")
            return None
            
    except Exception as e:
        print(f"❌ Error creating user: {e}")
        return None

def check_table_structure():
    """Check table structure"""
    print("\n🔍 Checking table structure...")
    
    try:
        # Check users table structure
        result = supabase.table("users").select("*").limit(0).execute()
        print(f"✅ Users table structure: {result.columns if hasattr(result, 'columns') else 'Unknown'}")
        
        # Check investment_files table structure
        result = supabase.table("investment_files").select("*").limit(0).execute()
        print(f"✅ Investment files table structure: {result.columns if hasattr(result, 'columns') else 'Unknown'}")
        
    except Exception as e:
        print(f"❌ Error checking table structure: {e}")

def main():
    """Main test function"""
    print("🧪 Database Test Script")
    print("=" * 40)
    
    # Test database connection
    if test_database_connection():
        # Test table structure
        check_table_structure()
        
        # Test file record save
        test_file_record_save()
        
        # Test user creation
        test_user_creation()
    else:
        print("❌ Cannot proceed with tests due to connection issues")

if __name__ == "__main__":
    main()
