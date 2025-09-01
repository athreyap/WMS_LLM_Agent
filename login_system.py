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
    create_database,
    save_transaction_supabase,
    save_file_record_supabase
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
    # Handle missing or empty salt
    if not salt or salt.strip() == '':
        print("⚠️  Warning: Missing password salt, using empty string")
        salt = ''
    
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
        
        # Make folder path optional - will be auto-generated if not provided
        if folder_path and folder_path.strip():
            folder_path = folder_path.strip()
            
            # Only validate folder path for local development if it's provided
            is_streamlit_cloud = os.getenv('STREAMLIT_SERVER_RUN_ON_IP', '').startswith('0.0.0.0')
            
            if not is_streamlit_cloud:
                # Check if folder exists (only for local development)
                if not os.path.exists(folder_path):
                    return False, f"Folder path does not exist: {folder_path}"
                
                # Check if it's a directory
                if not os.path.isdir(folder_path):
                    return False, f"Path is not a directory: {folder_path}"
        else:
            # No folder path provided - will be auto-generated
            folder_path = None
        
        # Hash password
        hashed_password, salt = hash_password(password)
        
        # Create new user using Supabase client
        user_data = create_user_supabase(
            username=username,
            password_hash=hashed_password,
            password_salt=salt,
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
        password_salt = user.get('password_salt', '')
        if not verify_password(password, user['password_hash'], password_salt):
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
        
    with tab2:
        st.markdown("### Create Account")
        
        # Registration form with file upload
        new_username = st.text_input("Username", key="register_username")
        new_email = st.text_input("Email", key="register_email")
        new_password = st.text_input("Password", type="password", key="register_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="confirm_password")
        
        # File upload section during registration
        st.markdown("### 📤 Upload Your Transaction Files")
        st.info("🌐 **Upload your CSV transaction files during registration for immediate portfolio analysis.**")
        
        uploaded_files = st.file_uploader(
            "Choose CSV files (optional)",
            type=['csv'],
            accept_multiple_files=True,
            help="Upload CSV files with transaction data. Files will be processed automatically after registration."
        )
        
        if uploaded_files:
            st.success(f"✅ Selected {len(uploaded_files)} file(s) for processing")
            
            # Show sample CSV format
            with st.expander("📋 Sample CSV Format"):
                st.markdown("""
                Your CSV file should have these columns:
                - **date**: Transaction date (YYYY-MM-DD)
                - **ticker**: Stock symbol (e.g., AAPL, MSFT)
                - **quantity**: Number of shares
                - **price**: Price per share
                - **transaction_type**: 'buy' or 'sell'
                - **stock_name**: Company name (optional)
                - **channel**: Investment channel (optional)
                - **sector**: Stock sector (optional)
                """)
        
        # Password strength indicator
        if new_password:
            is_valid, message = validate_password_strength(new_password)
            if is_valid:
                st.success("✅ " + message)
            else:
                st.error("❌ " + message)
        
        # Generate strong password button
        if st.button("Generate Strong Password"):
            strong_password = generate_strong_password()
            st.session_state['register_password'] = strong_password
            st.session_state['confirm_password'] = strong_password
            st.rerun()
        
        # Registration button
        if st.button("Create Account & Process Files", type="primary", use_container_width=True):
            if not all([new_username, new_email, new_password, confirm_password]):
                st.error("Please fill in all required fields")
            elif not validate_email(new_email):
                st.error("Please enter a valid email address")
            elif new_password != confirm_password:
                st.error("Passwords do not match")
            else:
                # Create user account
                success, message = create_user(new_username, new_email, new_password, folder_path=None)
                if success:
                    st.success("✅ Account created successfully!")
                    
                    # Process uploaded files if any
                    if uploaded_files:
                        st.info("🔄 Processing uploaded files...")
                        
                        # Get user info to get user_id
                        user_info = get_user_by_username(new_username)
                        if user_info:
                            user_id = user_info['id']
                            
                                                        # Create folder path for the user
                            folder_path = f"/tmp/{new_username}_investments"
                            
                            # Process the uploaded files
                            try:
                                process_uploaded_files_during_registration(uploaded_files, folder_path, user_id)
                                st.success(f"✅ Successfully processed {len(uploaded_files)} file(s)!")
                                st.success("🎉 Your portfolio is ready for analysis!")
                                
                                # Auto-login the user
                                st.session_state['user_authenticated'] = True
                                st.session_state['username'] = new_username
                                st.session_state['user_id'] = user_id
                                st.session_state['user_role'] = user_info['role']
                                st.session_state['login_time'] = datetime.now()
                                
                                # Set flag to trigger dashboard refresh
                                st.session_state['refresh_dashboard'] = True
                                st.session_state['show_portfolio_after_upload'] = True
                                
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error processing files: {e}")
                                st.info("You can still login and upload files later.")
                        else:
                            st.error("❌ Could not retrieve user information")
                    else:
                        st.success("🎉 Account created! You can login and upload files later.")
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

def process_uploaded_files_during_registration(uploaded_files, folder_path, user_id):
    """Process uploaded files during registration without circular imports"""
    import pandas as pd
    from pathlib import Path
    import os
    from datetime import datetime
    import streamlit as st
    
    if not uploaded_files:
        st.warning("No files selected for upload")
        return False
    
    # Create progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    processed_count = 0
    failed_count = 0
    
    try:
        for i, uploaded_file in enumerate(uploaded_files):
            status_text.text(f"Processing {uploaded_file.name}...")
            
            try:
                # Read the uploaded file
                df = pd.read_csv(uploaded_file)
                
                # Standardize column names
                column_mapping = {
                    'Stock Name': 'stock_name',
                    'Stock_Name': 'stock_name',
                    'stock_name': 'stock_name',
                    'Ticker': 'ticker',
                    'ticker': 'ticker',
                    'Quantity': 'quantity',
                    'quantity': 'quantity',
                    'Price': 'price',
                    'price': 'price',
                    'Transaction Type': 'transaction_type',
                    'Transaction_Type': 'transaction_type',
                    'transaction_type': 'transaction_type',
                    'Date': 'date',
                    'date': 'date',
                    'Channel': 'channel',
                    'channel': 'channel'
                }
                
                # Rename columns
                df = df.rename(columns=column_mapping)
                
                # Extract channel from filename if not present
                if 'channel' not in df.columns:
                    channel_name = uploaded_file.name.replace('.csv', '').replace('_', ' ')
                    df['channel'] = channel_name
                
                # Ensure required columns exist
                required_columns = ['stock_name', 'ticker', 'quantity', 'transaction_type', 'date']
                missing_columns = [col for col in required_columns if col not in df.columns]
                
                if missing_columns:
                    st.error(f"❌ Missing required columns in {uploaded_file.name}: {missing_columns}")
                    failed_count += 1
                    continue
                
                # Clean and validate data
                df = df.dropna(subset=['ticker', 'quantity'])
                df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce')
                
                # Convert date to datetime
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
                df = df.dropna(subset=['date'])
                
                # Standardize transaction types
                df['transaction_type'] = df['transaction_type'].str.lower().str.strip()
                df['transaction_type'] = df['transaction_type'].replace({
                    'buy': 'buy',
                    'purchase': 'buy',
                    'bought': 'buy',
                    'sell': 'sell',
                    'sold': 'sell',
                    'sale': 'sell'
                })
                
                # Filter valid transaction types
                df = df[df['transaction_type'].isin(['buy', 'sell'])]
                
                if df.empty:
                    st.warning(f"⚠️ No valid transactions found in {uploaded_file.name}")
                    failed_count += 1
                    continue
                
                # Add user_id to the dataframe
                df['user_id'] = user_id
                
                # Fetch historical prices for missing price values
                if 'price' not in df.columns or df['price'].isna().any():
                    status_text.text(f"🔍 Fetching historical prices for {uploaded_file.name}...")
                    df = fetch_historical_prices_for_upload(df)
                
                # Save to database using Supabase client
                
                # Save file record
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{uploaded_file.name.replace('.csv', '')}_{timestamp}.csv"
                file_path = os.path.join(folder_path, filename)
                
                # Save file record
                file_record = save_file_record_supabase(filename, file_path, user_id)
                
                # Save transactions
                transactions_saved = 0
                for _, row in df.iterrows():
                    success = save_transaction_supabase(
                        user_id=user_id,
                        stock_name=row.get('stock_name', ''),
                        ticker=row['ticker'],
                        quantity=float(row['quantity']),
                        price=float(row.get('price', 0)),
                        transaction_type=row['transaction_type'],
                        date=row['date'].strftime('%Y-%m-%d'),
                        channel=row.get('channel', ''),
                        sector=row.get('sector', '')
                    )
                    if success:
                        transactions_saved += 1
                
                if transactions_saved > 0:
                    processed_count += 1
                    st.success(f"✅ Successfully processed {uploaded_file.name} ({transactions_saved} transactions)")
                else:
                    failed_count += 1
                    st.error(f"❌ Failed to save transactions from {uploaded_file.name}")
                
            except Exception as e:
                st.error(f"❌ Error processing {uploaded_file.name}: {str(e)}")
                failed_count += 1
            
            # Update progress
            progress = (i + 1) / len(uploaded_files)
            progress_bar.progress(progress)
        
        # Final status
        status_text.text("Processing complete!")
        progress_bar.progress(1.0)
        
        if processed_count > 0:
            st.success(f"✅ Successfully processed {processed_count} files")
            return True
        if failed_count > 0:
            st.error(f"❌ Failed to process {failed_count} files")
            return False
        
    except Exception as e:
        st.error(f"❌ Error during file processing: {str(e)}")
        return False
    finally:
        progress_bar.empty()
        status_text.empty()

def fetch_historical_prices_for_upload(df):
    """Fetch historical prices for uploaded file data"""
    try:
        import yfinance as yf
        from mftool import Mftool
        import streamlit as st
        
        # Initialize mftool for mutual funds
        mf = Mftool()
        
        # Prepare tickers and dates for bulk fetching
        tickers_with_dates = []
        price_indices = []
        
        for idx, row in df.iterrows():
            ticker = row['ticker']
            transaction_date = row['date']
            
            tickers_with_dates.append((ticker, transaction_date))
            price_indices.append(idx)
        
        if not tickers_with_dates:
            return df
        
        # Add price column if it doesn't exist
        if 'price' not in df.columns:
            df['price'] = None
        
        # Fetch prices for each ticker
        prices_found = 0
        for i, (ticker, transaction_date) in enumerate(tickers_with_dates):
            idx = price_indices[i]
            price = None
            
            try:
                # Try yfinance first (for stocks)
                stock = yf.Ticker(ticker)
                hist = stock.history(start=transaction_date, end=transaction_date + pd.Timedelta(days=1))
                
                if not hist.empty:
                    price = hist['Close'].iloc[0]
                else:
                    # Try mftool for mutual funds
                    try:
                        mf_info = mf.get_scheme_details(ticker)
                        if mf_info and 'nav' in mf_info:
                            price = float(mf_info['nav'])
                    except:
                        pass
                
                if price:
                    df.at[idx, 'price'] = price
                    prices_found += 1
                    
            except Exception as e:
                st.warning(f"⚠️ Could not fetch price for {ticker}: {e}")
                continue
        
        # Show summary
        st.info(f"🔍 Price summary: {prices_found}/{len(tickers_with_dates)} transactions got historical prices")
        
        return df
        
    except Exception as e:
        st.error(f"❌ Error fetching historical prices: {e}")
        return df

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
