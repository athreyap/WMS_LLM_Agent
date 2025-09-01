#!/usr/bin/env python3
"""
Login System for WMS-LLM Portfolio Analyzer
Handles user authentication, registration, and session management
"""

import streamlit as st
import hashlib
import secrets
import string
import re
from datetime import datetime, timedelta
import pandas as pd
from database_config_supabase import (
    create_user_supabase,
    get_user_by_username_supabase,
    get_user_by_id_supabase,
    update_user_login_supabase,
    update_user_password_supabase,
    delete_user_supabase,
    get_all_users_supabase,
    create_database
)
from sqlalchemy.exc import IntegrityError
import os

# --- Configuration ---
SESSION_DURATION_HOURS = 24  # Session expires after 24 hours
MAX_LOGIN_ATTEMPTS = 5  # Maximum failed login attempts
LOCKOUT_DURATION_MINUTES = 30  # Account lockout duration

def hash_password(password, salt=None):
    """Hash password with salt using SHA-256"""
    if salt is None:
        salt = secrets.token_hex(16)
    
    # Combine password and salt
    salted_password = password + salt
    # Hash the salted password
    hashed = hashlib.sha256(salted_password.encode()).hexdigest()
    
    return hashed, salt

def verify_password(password, hashed_password, salt):
    """Verify password against stored hash"""
    input_hash, _ = hash_password(password, salt)
    return input_hash == hashed_password

def generate_strong_password(length=12):
    """Generate a strong password with mixed characters"""
    characters = string.ascii_letters + string.digits + string.punctuation
    # Ensure at least one of each type
    password = [
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.digits),
        secrets.choice(string.punctuation)
    ]
    # Fill the rest randomly
    password.extend(secrets.choice(characters) for _ in range(length - 4))
    # Shuffle the password
    password_list = list(password)
    secrets.SystemRandom().shuffle(password_list)
    return ''.join(password_list)

def validate_password_strength(password):
    """Validate password strength requirements"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit"
    
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character"
    
    return True, "Password meets strength requirements"

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def create_user(username, email, password, role="user", folder_path=None):
    """Create a new user account using Supabase client"""
    try:
        # Check if username already exists
        existing_user = get_user_by_username_supabase(username)
        if existing_user:
            return False, "Username already exists"
        
        # Validate password strength
        is_valid, message = validate_password_strength(password)
        if not is_valid:
            return False, message
        
        # For Streamlit Cloud, we don't validate local folder paths
        # The GitHub path conversion will handle this automatically
        is_streamlit_cloud = os.getenv('STREAMLIT_SERVER_RUN_ON_IP', '').startswith('0.0.0.0')
        
        if not is_streamlit_cloud:
            # Only validate folder path for local development
            if not folder_path or not folder_path.strip():
                return False, "Folder path is required for local development"
            
            folder_path = folder_path.strip()
            
            # Check if folder exists (only for local development)
            if not os.path.exists(folder_path):
                return False, f"Folder path does not exist: {folder_path}"
            
            # Check if it's a directory
            if not os.path.isdir(folder_path):
                return False, f"Path is not a directory: {folder_path}"
        
        # Hash password
        hashed_password, salt = hash_password(password)
        
        # Create new user using Supabase client
        user_data = create_user_supabase(
            username=username,
            password_hash=hashed_password,
            email=email,
            role=role,
            folder_path=folder_path
        )
        
        if user_data:
            return True, "User account created successfully"
        else:
            return False, "Failed to create user account"
        
    except Exception as e:
        return False, f"Error creating user: {str(e)}"

def authenticate_user(username, password):
    """Authenticate user login using Supabase client"""
    try:
        # Find user by username
        user = get_user_by_username_supabase(username)
        
        if not user:
            return False, "Invalid username or password"
        
        # Check if account is locked
        if user.get('is_locked', False):
            return False, "Account is locked. Please contact administrator"
        
        # Verify password
        if not verify_password(password, user['password_hash'], user.get('password_salt', '')):
            # Increment failed attempts
            login_attempts = user.get('login_attempts', 0) + 1
            is_locked = login_attempts >= MAX_LOGIN_ATTEMPTS
            
            # Update user login info
            update_user_login_supabase(
                user_id=user['id'],
                login_attempts=login_attempts,
                is_locked=is_locked
            )
            
            if is_locked:
                return False, f"Account locked due to too many failed attempts. Try again in {LOCKOUT_DURATION_MINUTES} minutes"
            else:
                remaining_attempts = MAX_LOGIN_ATTEMPTS - login_attempts
                return False, f"Invalid password. {remaining_attempts} attempts remaining"
        
        # Reset failed attempts on successful login
        update_user_login_supabase(
            user_id=user['id'],
            login_attempts=0,
            is_locked=False
        )
        
        return True, "Login successful"
        
    except Exception as e:
        return False, f"Authentication error: {str(e)}"

def get_user_by_username(username):
    """Get user details by username using Supabase client"""
    try:
        user = get_user_by_username_supabase(username)
        if user:
            return {
                'id': user['id'],
                'username': user['username'],
                'email': user.get('email'),
                'role': user.get('role', 'user'),
                'folder_path': user.get('folder_path'),
                'created_at': user.get('created_at'),
                'last_login': user.get('last_login'),
                'is_active': user.get('is_active', True)
            }
        return None
    except Exception as e:
        print(f"Error getting user by username: {e}")
        return None

def get_user_by_id(user_id):
    """Get user details by user ID using Supabase client"""
    try:
        user = get_user_by_id_supabase(user_id)
        if user:
            return {
                'id': user['id'],
                'username': user['username'],
                'email': user.get('email'),
                'role': user.get('role', 'user'),
                'folder_path': user.get('folder_path'),
                'created_at': user.get('created_at'),
                'last_login': user.get('last_login'),
                'is_active': user.get('is_active', True)
            }
        return None
    except Exception as e:
        print(f"Error getting user by ID: {e}")
        return None

def update_user_password(username, new_password):
    """Update user password using Supabase client"""
    try:
        user = get_user_by_username_supabase(username)
        if not user:
            return False, "User not found"
        
        # Validate password strength
        is_valid, message = validate_password_strength(new_password)
        if not is_valid:
            return False, message
        
        # Hash new password
        hashed_password, salt = hash_password(new_password)
        
        # Update password using Supabase
        success = update_user_password_supabase(user['id'], hashed_password, salt)
        
        if success:
            return True, "Password updated successfully"
        else:
            return False, "Failed to update password"
        
    except Exception as e:
        return False, f"Error updating password: {str(e)}"

def reset_user_password(username):
    """Reset user password to a new strong password"""
    new_password = generate_strong_password()
    success, message = update_user_password(username, new_password)
    
    if success:
        return True, f"Password reset successfully. New password: {new_password}"
    else:
        return False, message

def delete_user_account(username):
    """Delete user account using Supabase client"""
    try:
        user = get_user_by_username_supabase(username)
        if not user:
            return False, "User not found"
        
        # Delete user using Supabase
        success = delete_user_supabase(user['id'])
        
        if success:
            return True, "User account deleted successfully"
        else:
            return False, "Failed to delete user account"
        
    except Exception as e:
        return False, f"Error deleting user: {str(e)}"

def get_all_users():
    """Get all users using Supabase client"""
    try:
        users = get_all_users_supabase()
        return [
            {
                'id': user['id'],
                'username': user['username'],
                'email': user.get('email'),
                'role': user.get('role', 'user'),
                'created_at': user.get('created_at'),
                'last_login': user.get('last_login'),
                'is_active': user.get('is_active', True),
                'failed_attempts': user.get('login_attempts', 0)
            }
            for user in users
        ]
    except Exception as e:
        print(f"Error getting all users: {e}")
        return []

def is_session_valid():
    """Check if current session is valid"""
    if 'user_authenticated' not in st.session_state:
        return False
    
    if not st.session_state['user_authenticated']:
        return False
    
    if 'login_time' not in st.session_state:
        return False
    
    # Check if session has expired
    login_time = st.session_state['login_time']
    if datetime.now() - login_time > timedelta(hours=SESSION_DURATION_HOURS):
        # Clear session
        clear_session()
        return False
    
    return True

def clear_session():
    """Clear user session"""
    if 'user_authenticated' in st.session_state:
        del st.session_state['user_authenticated']
    if 'username' in st.session_state:
        del st.session_state['username']
    if 'user_role' in st.session_state:
        del st.session_state['user_role']
    if 'login_time' in st.session_state:
        del st.session_state['login_time']

def login_page():
    """Display login page"""
    st.markdown("""
    <style>
    .login-container {
        max-width: 400px;
        margin: 0 auto;
        padding: 2rem;
        border: 1px solid #ddd;
        border-radius: 10px;
        background-color: #f9f9f9;
    }
    .login-header {
        text-align: center;
        margin-bottom: 2rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.markdown('<h2 class="login-header">🔐 Portfolio Analyzer Login</h2>', unsafe_allow_html=True)
    
    # Create tabs for login and registration
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        st.markdown("### Sign In")
        
        with st.form("login_form"):
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            
            col1, col2 = st.columns(2)
            with col1:
                login_button = st.form_submit_button("Login", type="primary")
            with col2:
                forgot_password = st.form_submit_button("Forgot Password")
            
            if login_button:
                if username and password:
                    success, message = authenticate_user(username, password)
                    if success:
                        # Set session variables
                        st.session_state['user_authenticated'] = True
                        st.session_state['username'] = username
                        st.session_state['login_time'] = datetime.now()
                        
                        # Get user info and set user_id
                        user_info = get_user_by_username(username)
                        if user_info:
                            st.session_state['user_id'] = user_info['id']
                            st.session_state['user_role'] = user_info['role']
                        
                        st.success("Login successful! Redirecting...")
                        st.rerun()
                    else:
                        st.error(message)
                else:
                    st.error("Please enter both username and password")
            
            if forgot_password:
                st.info("Please contact your administrator to reset your password.")
    
    with tab2:
        st.markdown("### Create Account")
        
        with st.form("register_form"):
            new_username = st.text_input("Username", key="register_username")
            new_email = st.text_input("Email", key="register_email")
            new_password = st.text_input("Password", type="password", key="register_password")
            confirm_password = st.text_input("Confirm Password", type="password", key="confirm_password")
            # Check if running on Streamlit Cloud
            is_streamlit_cloud = os.getenv('STREAMLIT_SERVER_RUN_ON_IP', '').startswith('0.0.0.0')
            
            if is_streamlit_cloud:
                st.info("🌐 **Streamlit Cloud Mode**: Your files will be stored in a cloud-based folder structure.")
                folder_path = st.text_input(
                    "Local Folder Name (Optional)",
                    key="register_folder_path",
                    placeholder="e.g., my_portfolio or investments",
                    help="Optional: Provide a folder name for your files. If left empty, a default folder will be created."
                )
            else:
                folder_path = st.text_input(
                    "Transaction Folder Path *",
                    key="register_folder_path",
                    placeholder="e.g., C:/MyPortfolio or ./my_transactions",
                    help="Path to folder containing your transaction CSV files. This folder will be used to automatically process your transaction files."
                )
            
            # Password strength indicator
            if new_password:
                is_valid, message = validate_password_strength(new_password)
                if is_valid:
                    st.success("✅ " + message)
                else:
                    st.error("❌ " + message)
            
            # Generate strong password button
            if st.form_submit_button("Generate Strong Password"):
                strong_password = generate_strong_password()
                st.session_state['register_password'] = strong_password
                st.session_state['confirm_password'] = strong_password
                st.rerun()
            
            register_button = st.form_submit_button("Register", type="primary")
            
            if register_button:
                if not all([new_username, new_email, new_password, confirm_password]):
                    st.error("Please fill in all required fields")
                elif not validate_email(new_email):
                    st.error("Please enter a valid email address")
                elif new_password != confirm_password:
                    st.error("Passwords do not match")
                else:
                    # Use folder_path if provided, otherwise empty string
                    # GitHub path conversion will happen in create_user function
                    user_folder_path = folder_path.strip() if folder_path.strip() else ""
                    success, message = create_user(new_username, new_email, new_password, folder_path=user_folder_path)
                    if success:
                        st.success("Account created successfully! You can now login.")
                    else:
                        st.error(message)
    
    st.markdown('</div>', unsafe_allow_html=True)

def admin_panel():
    """Display admin panel for user management"""
    if not is_session_valid():
        st.error("Please login to access admin panel")
        return
    
    if st.session_state.get('user_role') != 'admin':
        st.error("Access denied. Admin privileges required.")
        return
    
    st.markdown("## 👨‍💼 Admin Panel")
    
    # Get all users
    users = get_all_users()
    
    if not users:
        st.info("No users found")
        return
    
    # Display users in a table
    df = pd.DataFrame(users)
    df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M')
    df['last_login'] = pd.to_datetime(df['last_login']).dt.strftime('%Y-%m-%d %H:%M')
    
    st.dataframe(df, use_container_width=True)
    
    # User management actions
    st.markdown("### User Management")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("#### Reset Password")
        reset_username = st.text_input("Username to reset password", key="reset_username")
        if st.button("Reset Password"):
            if reset_username:
                success, message = reset_user_password(reset_username)
                if success:
                    st.success("Password reset successfully!")
                    st.info(f"New password: {message.split('New password: ')[1]}")
                else:
                    st.error(message)
            else:
                st.error("Please enter a username")
    
    with col2:
        st.markdown("#### Delete Account")
        delete_username = st.text_input("Username to delete", key="delete_username")
        if st.button("Delete Account", type="secondary"):
            if delete_username:
                if st.checkbox("I understand this action cannot be undone"):
                    success, message = delete_user_account(delete_username)
                    if success:
                        st.success("Account deleted successfully!")
                        st.rerun()
                    else:
                        st.error(message)
                else:
                    st.warning("Please confirm the deletion")
            else:
                st.error("Please enter a username")
    
    with col3:
        st.markdown("#### Session Info")
        st.write(f"**Current User:** {st.session_state.get('username', 'Unknown')}")
        st.write(f"**Role:** {st.session_state.get('user_role', 'Unknown')}")
        if 'login_time' in st.session_state:
            login_time = st.session_state['login_time']
            st.write(f"**Login Time:** {login_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if st.button("Logout"):
            clear_session()
            st.success("Logged out successfully!")
            st.rerun()

def require_login():
    """Decorator to require login for specific pages/functions"""
    if not is_session_valid():
        st.error("Please login to access this feature")
        st.stop()

def require_admin():
    """Decorator to require admin privileges"""
    require_login()
    if st.session_state.get('user_role') != 'admin':
        st.error("Admin privileges required")
        st.stop()

def main_login_system():
    """Main function to run the login system"""
    st.set_page_config(page_title="Login - Portfolio Analyzer", layout="centered")
    
    # Initialize database
    try:
        create_database()
    except Exception as e:
        st.error(f"Database initialization failed: {e}")
        return
    
    # Check if user is already logged in
    if is_session_valid():
        st.success(f"Welcome back, {st.session_state['username']}!")
        
        # Show logout option
        if st.button("Logout"):
            clear_session()
            st.rerun()
        
        # Show admin panel if user is admin
        if st.session_state.get('user_role') == 'admin':
            admin_panel()
    else:
        login_page()

if __name__ == "__main__":
    main_login_system()
