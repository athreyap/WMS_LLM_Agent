#!/usr/bin/env python3
"""
Test script to debug password verification issue
"""

import os
from supabase import create_client

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://rolcoegikoeblxzqgkix.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJvbGNvZWdpa29lYmx4enFna2l4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTY1NDM2MjUsImV4cCI6MjA3MjExOTYyNX0.Vwg2hgdKNQGizJiulgTlxXkTLfy-J3vFNkX8gA_6ul4')

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def test_user_data():
    """Test what user data is actually stored in the database"""
    print("🔍 Testing user data structure...")
    
    try:
        # Get a user from the database
        result = supabase.table("users").select("*").limit(1).execute()
        
        if result.data:
            user = result.data[0]
            print(f"✅ Found user: {user['username']}")
            print(f"📋 User data keys: {list(user.keys())}")
            print(f"🔑 Password hash: {user.get('password_hash', 'NOT_FOUND')}")
            print(f"🧂 Password salt: {user.get('password_salt', 'NOT_FOUND')}")
            print(f"📧 Email: {user.get('email', 'NOT_FOUND')}")
            print(f"👤 Role: {user.get('role', 'NOT_FOUND')}")
            print(f"📁 Folder path: {user.get('folder_path', 'NOT_FOUND')}")
            
            return user
        else:
            print("❌ No users found in database")
            return None
            
    except Exception as e:
        print(f"❌ Error getting user data: {e}")
        return None

def test_password_verification():
    """Test password verification logic"""
    print("\n🔍 Testing password verification...")
    
    # Import the password functions
    import hashlib
    import secrets
    
    def hash_password(password):
        """Hash password with salt"""
        salt = secrets.token_hex(16)
        salted_password = password + salt
        hashed = hashlib.sha256(salted_password.encode()).hexdigest()
        return hashed, salt
    
    def verify_password(password, hashed_password, salt):
        """Verify password against stored hash"""
        input_hash, _ = hash_password(password, salt)
        return input_hash == hashed_password
    
    # Test with a known password
    test_password = "TestPassword123!"
    print(f"🔑 Testing with password: {test_password}")
    
    # Hash the password
    hashed, salt = hash_password(test_password)
    print(f"🧂 Generated salt: {salt}")
    print(f"🔐 Generated hash: {hashed}")
    
    # Verify the password
    is_valid = verify_password(test_password, hashed, salt)
    print(f"✅ Password verification result: {is_valid}")
    
    # Test with wrong password
    wrong_password = "WrongPassword123!"
    is_valid_wrong = verify_password(wrong_password, hashed, salt)
    print(f"❌ Wrong password verification result: {is_valid_wrong}")
    
    return hashed, salt

def test_existing_user_password():
    """Test password verification with existing user"""
    print("\n🔍 Testing existing user password...")
    
    # Get existing user
    user = test_user_data()
    if not user:
        return
    
    # Test password verification
    test_password = "TestPassword123!"  # This might be the actual password
    
    # Import the verification function
    import hashlib
    import secrets
    
    def verify_password(password, hashed_password, salt):
        """Verify password against stored hash"""
        input_hash, _ = hash_password(password, salt)
        return input_hash == hashed_password
    
    def hash_password(password):
        """Hash password with salt"""
        salt = secrets.token_hex(16)
        salted_password = password + salt
        hashed = hashlib.sha256(salted_password.encode()).hexdigest()
        return hashed, salt
    
    # Get stored password data
    stored_hash = user.get('password_hash', '')
    stored_salt = user.get('password_salt', '')
    
    print(f"🔑 Testing password: {test_password}")
    print(f"🧂 Stored salt: {stored_salt}")
    print(f"🔐 Stored hash: {stored_hash}")
    
    if stored_hash and stored_salt:
        is_valid = verify_password(test_password, stored_hash, stored_salt)
        print(f"✅ Password verification result: {is_valid}")
    else:
        print("❌ Missing password hash or salt in database")

def main():
    """Main test function"""
    print("🧪 Password Verification Debug Script")
    print("=" * 50)
    
    # Test user data structure
    test_user_data()
    
    # Test password verification logic
    test_password_verification()
    
    # Test existing user password
    test_existing_user_password()

if __name__ == "__main__":
    main()
