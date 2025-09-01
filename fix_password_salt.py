#!/usr/bin/env python3
"""
Fix Password Salt Column Script
This script will add the missing password_salt column to the users table
"""

import os
from supabase import create_client

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://rolcoegikoeblxzqgkix.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJvbGNvZWdpa29lYmx4enFna2l4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTY1NDM2MjUsImV4cCI6MjA3MjExOTYyNX0.Vwg2hgdKNQGizJiulgTlxXkTLfy-J3vFNkX8gA_6ul4')

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def print_fix_instructions():
    """Print instructions to fix the password salt issue"""
    print("🔧 Password Salt Fix Instructions")
    print("=" * 50)
    print()
    print("❌ ISSUE: The users table is missing the password_salt column")
    print("✅ SOLUTION: Add the password_salt column to the users table")
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
    """Get the SQL commands to fix the password salt issue"""
    
    sql_commands = """
-- =====================================================
-- Fix users table - Add missing password_salt column
-- =====================================================

-- Step 1: Add password_salt column to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_salt VARCHAR(32);

-- Step 2: Update existing users with a default salt (temporary fix)
-- Note: This will make existing passwords invalid, users will need to reset passwords
UPDATE users SET password_salt = 'default_salt_placeholder' WHERE password_salt IS NULL;

-- Step 3: Make password_salt NOT NULL for future users
ALTER TABLE users ALTER COLUMN password_salt SET NOT NULL;

-- =====================================================
-- Fix Complete!
-- =====================================================

-- IMPORTANT: After running this, existing users will need to reset their passwords
-- because we don't have their original salts. You can either:
-- 1. Ask users to use "Forgot Password" feature
-- 2. Manually update their passwords in the database
-- 3. Create new user accounts
"""
    
    return sql_commands

def test_fixed_structure():
    """Test the fixed table structure"""
    print("\n🔍 Testing fixed table structure...")
    
    try:
        # Get a user from the database
        result = supabase.table("users").select("*").limit(1).execute()
        
        if result.data:
            user = result.data[0]
            print(f"✅ Found user: {user['username']}")
            print(f"📋 User data keys: {list(user.keys())}")
            print(f"🔑 Password hash: {user.get('password_hash', 'NOT_FOUND')}")
            print(f"🧂 Password salt: {user.get('password_salt', 'NOT_FOUND')}")
            
            if 'password_salt' in user:
                print("✅ SUCCESS! password_salt column now exists")
                return True
            else:
                print("❌ password_salt column still missing")
                return False
        else:
            print("❌ No users found in database")
            return False
            
    except Exception as e:
        print(f"❌ Error testing fixed structure: {e}")
        return False

def create_test_user_with_salt():
    """Create a test user with proper salt for testing"""
    print("\n🔍 Creating test user with proper salt...")
    
    import hashlib
    import secrets
    
    def hash_password(password):
        """Hash password with salt"""
        salt = secrets.token_hex(16)
        salted_password = password + salt
        hashed = hashlib.sha256(salted_password.encode()).hexdigest()
        return hashed, salt
    
    try:
        # Test user data
        username = "testuser_salt"
        password = "TestPassword123!"
        email = "test_salt@example.com"
        
        # Hash password with salt
        hashed_password, salt = hash_password(password)
        
        # Create user data
        user_data = {
            "username": username,
            "password_hash": hashed_password,
            "password_salt": salt,
            "email": email,
            "role": "user",
            "folder_path": "/tmp/testuser_salt_investments"
        }
        
        print(f"📝 Creating test user: {username}")
        print(f"🧂 Generated salt: {salt}")
        print(f"🔐 Generated hash: {hashed_password}")
        
        # Insert user
        result = supabase.table("users").insert(user_data).execute()
        
        if result.data:
            print(f"✅ Test user created successfully: {result.data[0]}")
            print(f"🔑 Test password: {password}")
            return True
        else:
            print(f"❌ Failed to create test user")
            return False
            
    except Exception as e:
        print(f"❌ Error creating test user: {e}")
        return False

def main():
    """Main function"""
    print_fix_instructions()
    
    print("📝 SQL Commands to Execute:")
    print("=" * 30)
    print(get_fix_sql())
    
    print("\n⚠️  IMPORTANT NOTES:")
    print("- This will add the missing password_salt column")
    print("- Existing users will need to reset their passwords")
    print("- After running the SQL, test the application again")
    
    print("\n💡 After fixing the database structure:")
    print("1. The password verification should work correctly")
    print("2. New users will have proper salt storage")
    print("3. Existing users may need password reset")

if __name__ == "__main__":
    main()
