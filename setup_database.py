#!/usr/bin/env python3
"""
Database Setup Script for WMS-LLM
This script provides the SQL commands needed to create the database tables in Supabase
"""

def print_setup_instructions():
    """Print setup instructions and SQL commands"""
    print("🔧 WMS-LLM Database Setup Instructions")
    print("=" * 50)
    print()
    print("📋 Follow these steps to set up your database:")
    print()
    print("1. Go to your Supabase dashboard: https://supabase.com/dashboard")
    print("2. Select your project: rolcoegikoeblxzqgkix")
    print("3. Go to 'SQL Editor' in the left sidebar")
    print("4. Create a new query and paste the SQL commands below")
    print("5. Click 'Run' to execute the commands")
    print()
    print("⚠️  IMPORTANT: Make sure you're in the correct project!")
    print()

def get_sql_commands():
    """Return the SQL commands for creating all tables"""
    
    sql_commands = """
-- =====================================================
-- WMS-LLM Database Tables Setup
-- =====================================================

-- 1. Create users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    password_salt VARCHAR(32),
    email VARCHAR(100),
    role VARCHAR(20) DEFAULT 'user',
    folder_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    login_attempts INTEGER DEFAULT 0,
    is_locked BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE
);

-- 2. Create investment_transactions table
CREATE TABLE IF NOT EXISTS investment_transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    file_id INTEGER,
    stock_name VARCHAR(100) NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    quantity DECIMAL(10,2) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    transaction_type VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    channel VARCHAR(50),
    sector VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Create investment_files table
CREATE TABLE IF NOT EXISTS investment_files (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    file_hash VARCHAR(64) UNIQUE NOT NULL,
    customer_name VARCHAR(100),
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'processed'
);

-- 4. Create stock_data table
CREATE TABLE IF NOT EXISTS stock_data (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) UNIQUE NOT NULL,
    stock_name VARCHAR(100),
    sector VARCHAR(50),
    current_price DECIMAL(10,2),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON investment_transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_ticker ON investment_transactions(ticker);
CREATE INDEX IF NOT EXISTS idx_transactions_date ON investment_transactions(date);
CREATE INDEX IF NOT EXISTS idx_files_filename ON investment_files(filename);
CREATE INDEX IF NOT EXISTS idx_stock_data_ticker ON stock_data(ticker);

-- 6. Enable Row Level Security (RLS) for user data isolation
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE investment_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE investment_files ENABLE ROW LEVEL SECURITY;
ALTER TABLE stock_data ENABLE ROW LEVEL SECURITY;

-- 7. Create RLS policies for users table
CREATE POLICY "Users can view their own data" ON users
    FOR SELECT USING (auth.uid()::text = id::text);

CREATE POLICY "Users can update their own data" ON users
    FOR UPDATE USING (auth.uid()::text = id::text);

-- 8. Create RLS policies for investment_transactions table
CREATE POLICY "Users can view their own transactions" ON investment_transactions
    FOR SELECT USING (user_id IN (
        SELECT id FROM users WHERE username = current_user
    ));

CREATE POLICY "Users can insert their own transactions" ON investment_transactions
    FOR INSERT WITH CHECK (user_id IN (
        SELECT id FROM users WHERE username = current_user
    ));

-- 9. Create RLS policies for investment_files table
CREATE POLICY "Enable all operations for files" ON investment_files
    FOR ALL USING (true) WITH CHECK (true);

-- 10. Create RLS policies for stock_data table (read-only for all users)
CREATE POLICY "All users can view stock data" ON stock_data
    FOR SELECT USING (true);

-- 11. Insert a default admin user (optional)
-- Uncomment the lines below if you want to create a default admin user
-- INSERT INTO users (username, password_hash, email, role) VALUES 
-- ('admin', 'your_hashed_password_here', 'admin@example.com', 'admin')
-- ON CONFLICT (username) DO NOTHING;

-- =====================================================
-- Setup Complete!
-- =====================================================
"""
    
    return sql_commands

def print_verification_queries():
    """Print queries to verify the setup"""
    print("🔍 Verification Queries")
    print("=" * 30)
    print()
    print("After running the setup, you can verify the tables were created with these queries:")
    print()
    
    verification_queries = """
-- Check if tables exist
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('users', 'investment_transactions', 'investment_files', 'stock_data');

-- Check table structure
\\d users
\\d investment_transactions
\\d investment_files
\\d stock_data

-- Check RLS policies
SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual 
FROM pg_policies 
WHERE schemaname = 'public';
"""
    
    print(verification_queries)

def main():
    """Main function to run the setup"""
    print_setup_instructions()
    
    print("📝 SQL Commands to Execute:")
    print("=" * 30)
    print(get_sql_commands())
    
    print_verification_queries()
    
    print("✅ Setup instructions complete!")
    print()
    print("💡 After setting up the database, restart your Streamlit app.")
    print("🚀 The app should now work without 404 errors!")

if __name__ == "__main__":
    main()
