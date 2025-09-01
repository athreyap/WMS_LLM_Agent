-- Disable Row Level Security (RLS) for all tables in WMS Portfolio System
-- Run these commands in your Supabase SQL Editor

-- First, let's check which tables actually exist
SELECT 
    schemaname,
    tablename,
    rowsecurity
FROM pg_tables 
WHERE schemaname = 'public' 
AND tablename IN ('users', 'investment_transactions', 'stock_data')
ORDER BY tablename;

-- Disable RLS for users table (if it exists)
ALTER TABLE users DISABLE ROW LEVEL SECURITY;

-- Disable RLS for investment_transactions table (if it exists)
ALTER TABLE investment_transactions DISABLE ROW LEVEL SECURITY;

-- Disable RLS for stock_data table (if it exists)
ALTER TABLE stock_data DISABLE ROW LEVEL SECURITY;

-- Verify RLS is disabled for existing tables
SELECT 
    schemaname,
    tablename,
    rowsecurity,
    CASE 
        WHEN rowsecurity = false THEN '✅ RLS Disabled'
        ELSE '❌ RLS Still Enabled'
    END as status
FROM pg_tables 
WHERE schemaname = 'public' 
AND tablename IN ('users', 'investment_transactions', 'stock_data')
ORDER BY tablename;

-- Optional: Drop any existing RLS policies if they exist
-- (This is safe to run even if no policies exist)

-- Drop policies for users table
DROP POLICY IF EXISTS "Enable read access for all users" ON users;
DROP POLICY IF EXISTS "Enable insert for authenticated users only" ON users;
DROP POLICY IF EXISTS "Enable update for users based on user_id" ON users;
DROP POLICY IF EXISTS "Enable delete for users based on user_id" ON users;

-- Drop policies for investment_transactions table
DROP POLICY IF EXISTS "Enable read access for all users" ON investment_transactions;
DROP POLICY IF EXISTS "Enable insert for authenticated users only" ON investment_transactions;
DROP POLICY IF EXISTS "Enable update for users based on user_id" ON investment_transactions;
DROP POLICY IF EXISTS "Enable delete for users based on user_id" ON investment_transactions;

-- Drop policies for stock_data table
DROP POLICY IF EXISTS "Enable read access for all users" ON stock_data;
DROP POLICY IF EXISTS "Enable insert for authenticated users only" ON stock_data;
DROP POLICY IF EXISTS "Enable update for users based on user_id" ON stock_data;
DROP POLICY IF EXISTS "Enable delete for users based on user_id" ON stock_data;

-- Final verification - should show all tables with rowsecurity = false
SELECT 
    schemaname,
    tablename,
    rowsecurity,
    CASE 
        WHEN rowsecurity = false THEN '✅ RLS Disabled'
        ELSE '❌ RLS Still Enabled'
    END as status
FROM pg_tables 
WHERE schemaname = 'public' 
AND tablename IN ('users', 'investment_transactions', 'stock_data')
ORDER BY tablename;
