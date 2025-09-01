#!/usr/bin/env python3
"""
Simple script to create tables in Supabase
"""

from supabase import create_client, Client

# Supabase configuration (using your credentials)
SUPABASE_URL = "https://rolcoegikoeblxzqgkix.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJvbGNvZWdpa29lYmx4enFna2l4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTY1NDM2MjUsImV4cCI6MjA3MjExOTYyNX0.Vwg2hgdKNQGizJiulgTlxXkTLfy-J3vFNkX8gA_6ul4"

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def create_tables():
    """Create the required tables in Supabase"""
    print("🗄️  Creating tables in Supabase...")
    
    # SQL commands to create tables
    sql_commands = [
        """
        CREATE TABLE IF NOT EXISTS investment_files (
            id BIGSERIAL PRIMARY KEY,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            file_hash TEXT UNIQUE NOT NULL,
            customer_name TEXT,
            customer_id TEXT,
            customer_email TEXT,
            customer_phone TEXT,
            file_path TEXT NOT NULL,
            upload_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            file_size INTEGER,
            status TEXT DEFAULT 'active'
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS investment_transactions (
            id BIGSERIAL PRIMARY KEY,
            file_id INTEGER REFERENCES investment_files(id),
            user_id INTEGER,
            channel TEXT,
            stock_name TEXT,
            ticker TEXT,
            quantity DECIMAL,
            price DECIMAL,
            transaction_type TEXT,
            date TEXT,
            amount DECIMAL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS user_login (
            id BIGSERIAL PRIMARY KEY,
            username TEXT UNIQUE,
            email TEXT UNIQUE,
            password_hash TEXT,
            password_salt TEXT,
            role TEXT DEFAULT 'user',
            folder_path TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            last_login TIMESTAMP WITH TIME ZONE,
            is_active BOOLEAN DEFAULT TRUE,
            failed_attempts INTEGER DEFAULT 0,
            locked_until TIMESTAMP WITH TIME ZONE
        );
        """
    ]
    
    try:
        # Execute each SQL command
        for i, sql in enumerate(sql_commands, 1):
            print(f"Creating table {i}/3...")
            result = supabase.rpc('exec_sql', {'sql': sql}).execute()
            print(f"✅ Table {i} created successfully")
        
        print("\n🎉 All tables created successfully!")
        print("You can now run: streamlit run simple_app_supabase.py")
        
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        print("\n📋 Manual Instructions:")
        print("1. Go to your Supabase dashboard")
        print("2. Click on 'SQL Editor'")
        print("3. Create a new query")
        print("4. Copy and paste the SQL commands from the README_SUPABASE.md file")
        print("5. Click 'Run' to execute the commands")

def test_connection():
    """Test Supabase connection"""
    print("🔍 Testing Supabase connection...")
    try:
        # Try to access a table to test connection
        result = supabase.table('user_login').select('count').limit(1).execute()
        print("✅ Supabase connection successful!")
        return True
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 WMS Portfolio Analytics - Table Creation")
    print("=" * 50)
    
    if test_connection():
        create_tables()
    else:
        print("\n❌ Cannot create tables - connection failed")
        print("Please check your Supabase credentials and try again.")
