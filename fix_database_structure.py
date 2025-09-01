#!/usr/bin/env python3
"""
Fix Database Structure Script
This script will update the investment_files table to match the new structure
"""

import os
from supabase import create_client

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://rolcoegikoeblxzqgkix.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJvbGNvZWdpa29lYmx4enFna2l4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTY1NDM2MjUsImV4cCI6MjA3MjExOTYyNX0.Vwg2hgdKNQGizJiulgTlxXkTLfy-J3vFNkX8gA_6ul4')

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def print_fix_instructions():
    """Print instructions to fix the database structure"""
    print("🔧 Database Structure Fix Instructions")
    print("=" * 50)
    print()
    print("❌ ISSUE: The investment_files table has the old structure")
    print("✅ SOLUTION: Update the table structure in Supabase")
    print()
    print("📋 Follow these steps:")
    print()
    print("1. Go to your Supabase dashboard: https://supabase.com/dashboard")
    print("2. Select your project: rolcoegikoeblxzqgkix")
    print("3. Go to 'SQL Editor' in the left sidebar")
    print("4. Create a new query and paste the SQL commands below")
    print("5. Click 'Run' to execute the commands")
    print()

def get_fix_sql():
    """Get the SQL commands to fix the table structure"""
    
    sql_commands = """
-- =====================================================
-- Fix investment_files table structure
-- =====================================================

-- Step 1: Drop the existing investment_files table
DROP TABLE IF EXISTS investment_files CASCADE;

-- Step 2: Create the investment_files table with correct structure
CREATE TABLE investment_files (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    file_hash VARCHAR(64) UNIQUE NOT NULL,
    customer_name VARCHAR(100),
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'processed'
);

-- Step 3: Create index for better performance
CREATE INDEX idx_files_filename ON investment_files(filename);

-- Step 4: Enable Row Level Security
ALTER TABLE investment_files ENABLE ROW LEVEL SECURITY;

-- Step 5: Create RLS policy
CREATE POLICY "Enable all operations for files" ON investment_files
    FOR ALL USING (true) WITH CHECK (true);

-- =====================================================
-- Fix Complete!
-- =====================================================
"""
    
    return sql_commands

def test_fixed_structure():
    """Test the fixed table structure"""
    print("\n🔍 Testing fixed table structure...")
    
    try:
        # Test data
        filename = "test_file_fixed.csv"
        file_path = "/tmp/test_user_investments/test_file_fixed.csv"
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
        
        print(f"📝 Testing with data: {data}")
        
        result = supabase.table("investment_files").insert(data).execute()
        
        if result.data:
            print(f"✅ SUCCESS! File record saved: {result.data[0]}")
            return True
        else:
            print(f"❌ Still failed to save file record")
            return False
            
    except Exception as e:
        print(f"❌ Error testing fixed structure: {e}")
        return False

def main():
    """Main function"""
    print_fix_instructions()
    
    print("📝 SQL Commands to Execute:")
    print("=" * 30)
    print(get_fix_sql())
    
    print("\n⚠️  IMPORTANT NOTES:")
    print("- This will DELETE all existing file records")
    print("- Make sure you have a backup if needed")
    print("- After running the SQL, test the application again")
    
    print("\n💡 After fixing the database structure:")
    print("1. The file upload functionality should work")
    print("2. No more 'original_filename' constraint errors")
    print("3. The application will use the correct table structure")

if __name__ == "__main__":
    main()
