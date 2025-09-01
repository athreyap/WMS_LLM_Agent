#!/usr/bin/env python3
"""
Create a test admin user for testing the login system
"""

import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def create_test_admin():
    """Create a test admin user"""
    print("🔧 Creating test admin user...")
    
    try:
        from login_system import create_user_supabase, hash_password
        from database_config_supabase import get_user_by_username_supabase, update_user_login_supabase
        
        # Test admin credentials
        username = "admin"
        email = "admin@test.com"
        password = "Admin123!"
        folder_path = "./test_admin_folder"
        
        # Create folder if it doesn't exist
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            print(f"✅ Created folder: {folder_path}")
        
        # Check if user already exists
        existing_user = get_user_by_username_supabase(username)
        
        if existing_user:
            print(f"⚠️ User '{username}' already exists")
            
            # Update the existing user's password
            print("🔄 Updating existing user's password...")
            hashed_password, salt = hash_password(password)
            
            # Update user using Supabase
            update_user_login_supabase(
                user_id=existing_user['id'],
                login_attempts=0,
                is_locked=False
            )
            
            print(f"✅ Updated user '{username}' with new password")
        else:
            # Create new user
            print(f"📝 Creating new admin user: {username}")
            success, message = create_user_supabase(username, email, password, role="admin", folder_path=folder_path)
            
            if success:
                print(f"✅ User created successfully: {message}")
            else:
                print(f"❌ Failed to create user: {message}")
        
        print(f"\n📋 Test Admin Credentials:")
        print(f"Username: {username}")
        print(f"Password: {password}")
        print(f"Email: {email}")
        print(f"Role: admin")
        print(f"Folder: {folder_path}")
        
    except Exception as e:
        print(f"❌ Error creating test admin: {e}")
        import traceback
        traceback.print_exc()

def create_test_user():
    """Create a test regular user"""
    print("\n🔧 Creating test regular user...")
    
    try:
        from login_system import create_user_supabase, hash_password
        from database_config_supabase import get_user_by_username_supabase, update_user_login_supabase
        
        # Test user credentials
        username = "testuser"
        email = "testuser@test.com"
        password = "Test123!"
        folder_path = "./test_user_folder"
        
        # Create folder if it doesn't exist
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            print(f"✅ Created folder: {folder_path}")
        
        # Check if user already exists
        existing_user = get_user_by_username_supabase(username)
        
        if existing_user:
            print(f"⚠️ User '{username}' already exists")
            
            # Update the existing user's password
            print("🔄 Updating existing user's password...")
            hashed_password, salt = hash_password(password)
            
            # Update user using Supabase
            update_user_login_supabase(
                user_id=existing_user['id'],
                login_attempts=0,
                is_locked=False
            )
            
            print(f"✅ Updated user '{username}' with new password")
        else:
            # Create new user
            print(f"📝 Creating new user: {username}")
            success, message = create_user_supabase(username, email, password, role="user", folder_path=folder_path)
            
            if success:
                print(f"✅ User created successfully: {message}")
            else:
                print(f"❌ Failed to create user: {message}")
        
        print(f"\n📋 Test User Credentials:")
        print(f"Username: {username}")
        print(f"Password: {password}")
        print(f"Email: {email}")
        print(f"Role: user")
        print(f"Folder: {folder_path}")
        
    except Exception as e:
        print(f"❌ Error creating test user: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🧪 Creating Test Users for Login System")
    print("=" * 50)
    
    create_test_admin()
    create_test_user()
    
    print("\n✅ Test users created/updated!")
    print("\n🚀 You can now test the login system with these credentials.")
