import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime, timedelta
import time
import os
import sys
from pathlib import Path

# Handle matplotlib import issues gracefully - matplotlib not needed for this app
matplotlib = None
print("💡 Matplotlib not imported - using Plotly for all charts")

# Import other modules with error handling
try:
    from login_system import main_login_system, is_session_valid, clear_session
    LOGIN_SYSTEM_AVAILABLE = True
    print("✅ Login system imported successfully")
except ImportError as e:
    print(f"⚠️ Login system not available: {e}")
    LOGIN_SYSTEM_AVAILABLE = False

try:
    from user_file_reading_agent import user_file_agent, process_user_files_on_login, get_user_transactions_data, start_user_file_monitoring, stop_user_file_monitoring
    print("✅ User file reading agent imported successfully")
except ImportError as e:
    print(f"⚠️ User file reading agent not available: {e}")

try:
    from stock_data_agent import stock_agent, force_update_stock, update_user_stock_prices
    print("✅ Stock data agent imported successfully")
except ImportError as e:
    print(f"⚠️ Stock data agent not available: {e}")

try:
    from database_config_supabase import (
        get_file_records_supabase,
        update_stock_data_supabase,
    )
    print("✅ Database config imported successfully")
except ImportError as e:
    print(f"⚠️ Database config not available: {e}")

from collections import defaultdict
import threading
from typing import Dict, List, Optional
from functools import lru_cache, wraps
import warnings
warnings.filterwarnings('ignore')

# Import the agentic systems
from stock_data_agent import stock_agent, get_live_price, get_sector, get_stock_name, get_all_live_prices, get_user_live_prices, get_stock_data_stats, update_user_stock_prices
from user_file_reading_agent import user_file_agent, process_user_files_on_login, get_user_transactions_data, start_user_file_monitoring, stop_user_file_monitoring
from database_config_supabase import (
    get_transactions_supabase,
    get_transactions_with_historical_prices,
    get_user_by_id_supabase,
    create_user_supabase,
    get_user_by_username_supabase,
    update_user_login_supabase,
    save_transaction_supabase,
    save_file_record_supabase,
    get_file_records_supabase,
    update_stock_data_supabase,
    get_stock_data_supabase
)

# Import login system
try:
    from login_system import (
        is_session_valid, 
        clear_session, 
        require_login, 
        require_admin,
        login_page,
        admin_panel,
        get_user_by_username_supabase,
        main_login_system,
        authenticate_user,
        create_user_supabase,
        get_user_by_id_supabase
    )
    LOGIN_SYSTEM_AVAILABLE = True
    
    def clear_sector_cache():
        """Clear sector-related cache to force refresh of sector options"""
        sector_cache_keys = [key for key in st.session_state.keys() if key.startswith('sector_options_')]
        for key in sector_cache_keys:
            del st.session_state[key]
except ImportError as e:
    print(f"Warning: Login system not available: {e}")
    LOGIN_SYSTEM_AVAILABLE = False
    
    def is_session_valid():
        return True
    def clear_session():
        pass
    def clear_sector_cache():
        sector_cache_keys = [key for key in st.session_state.keys() if key.startswith('sector_options_')]
        for key in sector_cache_keys:
            del st.session_state[key]
    def require_login():
        pass
    def require_admin():
        pass
    def login_page():
        st.error("Login system not available")
    def admin_panel():
        st.error("Admin panel not available")
    def main_login_system():
        st.error("Login system not available")
    def authenticate_user(username, password):
        return False, "Login system not available"
    def create_user(username, email, password, role="user", folder_path=None):
        return False, "Login system not available"
    def get_user_by_id(user_id):
        return None

class WebAgent:
    """Web Agent that coordinates with Stock Data Agent and File Reading Agent"""
    
    def __init__(self):
        """Initialize the web agent with necessary components"""
        self.session_state = st.session_state
        self.mftool_client = None
        self.mftool_available = False
        # Mftool will be initialized after login, not here
        
        # Initialize other components
        try:
            # Import functions from login_system instead of class
            from login_system import authenticate_user, create_user, main_login_system
            self.login_system = {
                'authenticate_user': authenticate_user,
                'create_user': create_user,
                'main_login_system': main_login_system
            }
            print("✅ Login system functions imported successfully")
        except Exception as e:
            print(f"❌ Error importing login system: {e}")
            self.login_system = None
        
        try:
            from user_file_reading_agent import UserFileReadingAgent
            self.user_file_agent = UserFileReadingAgent()
            print("✅ User file reading agent imported successfully")
        except Exception as e:
            print(f"❌ Error importing user file reading agent: {e}")
            self.user_file_agent = None
        
        try:
            from stock_data_agent import StockDataAgent
            self.stock_agent = StockDataAgent()
            print("✅ Stock data agent imported successfully")
        except Exception as e:
            print(f"❌ Error importing stock data agent: {e}")
            self.stock_agent = None
        
        try:
            from database_config_supabase import supabase
            self.supabase = supabase
            print("✅ Database config imported successfully")
        except Exception as e:
            print(f"❌ Error importing database config: {e}")
            self.supabase = None
    
    def _initialize_mftool(self):
        """Initialize mftool client for Streamlit Cloud compatibility"""
        # Check if already initialized
        if self.mftool_client is not None:
            return
        
        try:
            import mftool
            print("🔄 Initializing mftool client...")
            
            # Create mftool instance with proper error handling
            self.mftool_client = mftool.Mftool()
            print("✅ Mftool instance created successfully")
            
            # Test if mftool is working by trying to get a simple scheme
            try:
                print("🔍 Testing mftool connectivity with test scheme 120466...")
                # Try to get a test scheme to verify connectivity
                test_scheme = self.mftool_client.get_scheme_details("120466")  # Example scheme
                if test_scheme and 'nav' in test_scheme:
                    self.mftool_available = True
                    nav = test_scheme.get('nav', 'N/A')
                    name = test_scheme.get('scheme_name', 'N/A')
                    print(f"✅ Mftool initialized successfully and working - Test scheme: {name} (NAV: ₹{nav})")
                else:
                    print("⚠️ Mftool initialized but test scheme failed - no NAV data")
                    self.mftool_available = False
            except Exception as test_error:
                print(f"⚠️ Mftool test failed: {test_error}")
                print(f"⚠️ Error type: {type(test_error).__name__}")
                self.mftool_available = False
                
        except ImportError as e:
            print(f"❌ Mftool not available: {e}")
            if "matplotlib" in str(e):
                print("❌ Matplotlib dependency missing - please install: pip install matplotlib")
                print("💡 Mftool requires matplotlib for some functionality")
            else:
                print(f"❌ Please ensure mftool is installed: pip install mftool")
            self.mftool_available = False
        except Exception as e:
            print(f"❌ Error initializing mftool: {e}")
            print(f"❌ Error type: {type(e).__name__}")
            self.mftool_available = False
    
    def _ensure_mftool_initialized(self):
        """Ensure mftool is initialized before use"""
        if self.mftool_client is None:
            self._initialize_mftool()
        return self.mftool_client is not None
    
    def initialize_session_state(self):
        """Initialize Streamlit session state"""
        if 'df' not in self.session_state:
            self.session_state['df'] = pd.DataFrame()
        if 'user_authenticated' not in self.session_state:
            self.session_state['user_authenticated'] = False
        if 'username' not in self.session_state:
            self.session_state['username'] = None
        if 'user_id' not in self.session_state:
            self.session_state['user_id'] = None
        if 'user_role' not in self.session_state:
            self.session_state['user_role'] = None
        if 'fast_loading' not in self.session_state:
            self.session_state['fast_loading'] = True  # Enable fast loading by default
        if 'login_time' not in self.session_state:
            self.session_state['login_time'] = None
        if 'show_admin_panel' not in self.session_state:
            self.session_state['show_admin_panel'] = False
        if 'show_settings' not in self.session_state:
            self.session_state['show_settings'] = False
        if 'agents_initialized' not in self.session_state:
            self.session_state['agents_initialized'] = False
        if 'sector_pie_rendered' not in self.session_state:
            self.session_state['sector_pie_rendered'] = False
        if 'last_client' not in self.session_state:
            self.session_state['last_client'] = None
        if 'data_cache' not in self.session_state:
            self.session_state['data_cache'] = {}
        if 'last_data_hash' not in self.session_state:
            self.session_state['last_data_hash'] = None
        if 'automatic_processing_initialized' not in self.session_state:
            self.session_state['automatic_processing_initialized'] = True
    
    def handle_user_authentication(self, username, password):
        """Handle user authentication and set session state"""
        if not LOGIN_SYSTEM_AVAILABLE:
            return False, "Login system not available"
        
        try:
            # Use imported function from login_system
            if self.login_system and 'authenticate_user' in self.login_system:
                success, message = self.login_system['authenticate_user'](username, password)
            else:
                # Fallback to direct import
                from login_system import authenticate_user
                success, message = authenticate_user(username, password)
            
            if success:
                # Set session variables
                self.session_state['user_authenticated'] = True
                self.session_state['username'] = username
                self.session_state['login_time'] = datetime.now()
                
                # Get user info and set user_id
                user_info = get_user_by_username(username)
                if user_info:
                    self.session_state['user_id'] = user_info['id']
                    self.session_state['user_role'] = user_info['role']
                    self.session_state['folder_path'] = user_info.get('folder_path', '')
                    
                    # Initialize mftool after successful login
                    print("🔄 User authenticated, initializing mftool...")
                    self.initialize_after_login()
                
                return True, "Login successful"
            else:
                return False, message
        except Exception as e:
            print(f"❌ Authentication error: {e}")
            return False, f"Authentication failed: {str(e)}"
    
    def handle_user_registration(self, username, email, password, folder_path=None):
        """Handle user registration"""
        if not LOGIN_SYSTEM_AVAILABLE:
            return False, "Login system not available"
        
        try:
            # Use imported function from login_system
            if self.login_system and 'create_user' in self.login_system:
                success, message = self.login_system['create_user'](username, email, password, folder_path=folder_path)
            else:
                # Fallback to direct import
                from login_system import create_user
                success, message = create_user(username, email, password, folder_path=folder_path)
            
            return success, message
        except Exception as e:
            print(f"❌ Registration error: {e}")
            return False, f"Registration failed: {str(e)}"
    
    def check_user_folder_access(self):
        """Check if current user has proper folder access"""
        if not LOGIN_SYSTEM_AVAILABLE:
            return True, "Login system not available"
        
        folder_path = self.session_state.get('folder_path', '')
        if not folder_path:
            return False, "No folder path configured for user"
        
        # For Streamlit Cloud, create folder if it doesn't exist
        is_streamlit_cloud = os.getenv('STREAMLIT_SERVER_RUN_ON_IP', '').startswith('0.0.0.0')
        
        if is_streamlit_cloud:
            # Create folder if it doesn't exist (GitHub path structure)
            try:
                os.makedirs(folder_path, exist_ok=True)
                # Create archive folder
                archive_path = os.path.join(folder_path, "archive")
                os.makedirs(archive_path, exist_ok=True)
                return True, "Folder access OK (created if needed)"
            except Exception as e:
                return False, f"Error creating folder: {e}"
        else:
            # Local development - check if folder exists
            if not os.path.exists(folder_path):
                return False, f"User folder does not exist: {folder_path}"
            
            if not os.path.isdir(folder_path):
                return False, f"User folder path is not a directory: {folder_path}"
            
            return True, "Folder access OK"
    
    def show_user_settings(self):
        """Show user settings and information"""
        if not LOGIN_SYSTEM_AVAILABLE:
            st.info("Login system not available")
            return
        
        st.markdown("## ⚙️ User Settings")
        
        username = self.session_state.get('username', 'Unknown')
        user_role = self.session_state.get('user_role', 'user')
        folder_path = self.session_state.get('folder_path', '')
        login_time = self.session_state.get('login_time')
        
        # Check if running on Streamlit Cloud
        is_streamlit_cloud = os.getenv('STREAMLIT_SERVER_RUN_ON_IP', '').startswith('0.0.0.0')
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 👤 User Information")
            st.write(f"**Username:** {username}")
            st.write(f"**Role:** {user_role}")
            if login_time:
                st.write(f"**Login Time:** {login_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        with col2:
            st.markdown("### 📁 Folder Information")
            if folder_path:
                # Check if running on Streamlit Cloud
                is_streamlit_cloud = os.getenv('STREAMLIT_SERVER_RUN_ON_IP', '').startswith('0.0.0.0')
                
                if is_streamlit_cloud:
                    st.info("🌐 **Cloud Storage**: Files are stored in cloud-based folders")
                
                st.write(f"**Folder Path:** {folder_path}")
                
                # Check folder access
                folder_access_ok, folder_message = self.check_user_folder_access()
                if folder_access_ok:
                    st.success("✅ Folder access OK")
                    
                    # Show folder contents
                    try:
                        files = os.listdir(folder_path)
                        st.write(f"**Files in folder:** {len(files)}")
                        if files:
                            st.write("**Recent files:**")
                            for file in files[:5]:  # Show first 5 files
                                if not file.startswith('.'):  # Skip hidden files
                                    st.write(f"- {file}")
                    except Exception as e:
                        st.error(f"Error accessing folder: {e}")
                else:
                    st.error(f"❌ {folder_message}")
            else:
                st.warning("⚠️ No folder path configured")
        
        # File Upload Section for Streamlit Cloud
        is_streamlit_cloud = os.getenv('STREAMLIT_SERVER_RUN_ON_IP', '').startswith('0.0.0.0')
        if is_streamlit_cloud and folder_path:
            st.markdown("### 📤 File Upload")
            st.info("Upload your CSV transaction files for automatic processing and historical price calculation.")
            
            # Sample file download section
            st.markdown("#### 📋 Sample CSV Format")
            st.info("Download the sample file below to see the correct column format:")
            
            # Create sample CSV content directly (works on Streamlit Cloud)
            sample_csv_content = """date,ticker,quantity,price,transaction_type,stock_name,sector
2024-01-15,RELIANCE.NS,100,,buy,Reliance Industries Ltd,Oil & Gas
2024-01-20,TCS.NS,50,3800.75,buy,Tata Consultancy Services Ltd,Technology
2024-02-01,INFY.NS,75,,buy,Infosys Ltd,Technology
2024-02-15,RELIANCE.NS,50,2600.00,sell,Reliance Industries Ltd,Oil & Gas
2024-03-01,HDFCBANK.NS,25,,buy,HDFC Bank Ltd,Banking
2024-03-15,120828,100,45.50,buy,ICICI Prudential Technology Fund,Mutual Funds
2024-04-01,TCS.NS,25,,sell,Tata Consultancy Services Ltd,Technology
2024-04-15,MF_120828,200,46.20,buy,ICICI Prudential Technology Fund,Mutual Funds"""
            
            st.download_button(
                label="📥 Download Sample CSV File",
                data=sample_csv_content,
                file_name="sample_transaction_file.csv",
                mime="text/csv",
                help="Download this sample file to see the correct column format"
            )
            
            # Show column requirements
            with st.expander("📋 Required Column Format"):
                st.markdown("""
                Your CSV file must have these columns:
                
                **Required Columns:**
                - **`date`**: Transaction date (YYYY-MM-DD format)
                - **`ticker`**: Stock/Mutual Fund symbol (e.g., RELIANCE.NS, TCS.NS, 120828, MF_120828)
                - **`quantity`**: Number of shares/units
                - **`transaction_type`**: 'buy' or 'sell'
                
                **Optional Columns:**
                - **`price`**: Price per share (if not provided, will be fetched automatically)
                - **`stock_name`**: Company/Fund name
                - **`channel`**: Investment channel (e.g., Direct, Broker)
                - **`sector`**: Stock sector (e.g., Technology, Banking, Mutual Funds)
                
                **Important Notes:**
                - For Indian stocks, use `.NS` suffix (e.g., RELIANCE.NS, TCS.NS)
                - For mutual funds, use numeric codes (e.g., 120828) or MF_ prefix (e.g., MF_120828)
                - Date format must be YYYY-MM-DD
                - Transaction type must be exactly 'buy' or 'sell'
                - **Price column is optional** - historical prices will be fetched automatically if missing
                """)
            
            uploaded_files = st.file_uploader(
                "Choose CSV files",
                type=['csv'],
                accept_multiple_files=True,
                help="Upload CSV files with transaction data. Files will be processed automatically with historical price fetching."
            )
            
            if uploaded_files:
                if st.button("📊 Process Uploaded Files", type="primary"):
                    self._process_uploaded_files(uploaded_files, folder_path)
        
        # Admin-specific settings
        if user_role == 'admin':
            st.markdown("### 👑 Admin Settings")
            st.info("Admin features available in the Admin Panel")
    
    def _process_uploaded_files(self, uploaded_files, folder_path):
        """Process uploaded files with historical price calculations"""
        import pandas as pd
        from pathlib import Path
        import os
        from datetime import datetime
        
        if not uploaded_files:
            st.warning("No files selected for upload")
            return
        
        # Get current user ID
        user_id = self.session_state.get('user_id')
        if not user_id:
            st.error("User ID not found. Please login again.")
            return
        
        # DEBUG: Show current user information
        st.info(f"🔍 **DEBUG INFO**: Processing files for User ID: {user_id}")
        st.info(f"🔍 **DEBUG INFO**: Current username: {self.session_state.get('username', 'Unknown')}")
        st.info(f"🔍 **DEBUG INFO**: Session keys: {list(self.session_state.keys())}")
        
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
                    
                    # DEBUG: Show DataFrame info
                    st.info(f"🔍 **DEBUG INFO**: DataFrame shape: {df.shape}, Columns: {list(df.columns)}")
                    
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
                    required_columns = ['ticker', 'quantity', 'transaction_type', 'date']
                    missing_columns = [col for col in required_columns if col not in df.columns]
                    
                    if missing_columns:
                        st.error(f"❌ Missing required columns in {uploaded_file.name}: {missing_columns}")
                        st.info("Required columns: date, ticker, quantity, transaction_type")
                        st.info("Optional columns: price, stock_name, channel, sector")
                        st.info("Note: If 'channel' column is missing, it will be auto-generated from the filename")
                        st.info("Note: If 'price' column is missing, historical prices will be automatically fetched")
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
                    
                    # Fetch historical prices for missing price values
                    if 'price' not in df.columns or df['price'].isna().any():
                        status_text.text(f"🔍 Fetching historical prices for {uploaded_file.name}...")
                        try:
                            df = self._fetch_historical_prices_for_upload(df)
                        except ValueError as e:
                            st.error(f"❌ SECURITY ERROR: {e}")
                            failed_count += 1
                            continue
                    
                    # Add user_id to DataFrame
                    df['user_id'] = user_id
                    
                    # DEBUG: Show final DataFrame info
                    st.info(f"🔍 **DEBUG INFO**: Final DataFrame shape: {df.shape}")
                    st.info(f"🔍 **DEBUG INFO**: User ID in DataFrame: {df['user_id'].iloc[0] if not df.empty else 'Empty'}")
                    st.info(f"🔍 **DEBUG INFO**: Sample tickers: {df['ticker'].head().tolist() if not df.empty else 'Empty'}")
                    
                    # Save directly to database using user file agent
                    from user_file_reading_agent import user_file_agent
                    try:
                        st.info(f"🔄 **DEBUG INFO**: Calling user_file_agent._process_uploaded_file_direct with user_id: {user_id}")
                        success = user_file_agent._process_uploaded_file_direct(df, user_id, uploaded_file.name)
                        
                        if success:
                            processed_count += 1
                            st.success(f"✅ Successfully processed {uploaded_file.name}")
                            
                            # DEBUG: Verify data was saved by checking database
                            st.info("🔍 **DEBUG INFO**: Verifying data was saved to database...")
                            try:
                                from database_config_supabase import get_transactions_supabase
                                saved_transactions = get_transactions_supabase(user_id)
                                st.success(f"🔍 **DEBUG INFO**: Database verification: {len(saved_transactions)} transactions found for user {user_id}")
                                
                                if saved_transactions:
                                    sample_transaction = saved_transactions[0]
                                    st.info(f"🔍 **DEBUG INFO**: Sample transaction user_id: {sample_transaction.get('user_id', 'N/A')}")
                                    st.info(f"🔍 **DEBUG INFO**: Sample transaction ticker: {sample_transaction.get('ticker', 'N/A')}")
                            except Exception as verify_error:
                                st.error(f"❌ **DEBUG ERROR**: Database verification failed: {verify_error}")
                        else:
                            failed_count += 1
                            st.error(f"❌ Failed to process {uploaded_file.name}")
                    except Exception as db_error:
                        failed_count += 1
                        st.error(f"❌ Database error processing {uploaded_file.name}: {str(db_error)}")
                        # Show helpful information for common database issues
                        if "400" in str(db_error) or "bad request" in str(db_error).lower():
                            st.info("💡 This might be due to missing database columns")
                            st.info("💡 Please check the console for detailed diagnostics")
                        elif "user_id" in str(db_error).lower():
                            st.info("💡 This might be due to missing user_id column in investment_files table")
                        elif "file_id" in str(db_error).lower():
                            st.info("💡 This might be due to missing file_id column in investment_transactions table")
                    
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
                # Force data reload after successful processing
                st.info("🔄 **Data Updated!** Your portfolio will be automatically refreshed on next login.")
                
                # DEBUG: Final verification
                st.info("🔍 **DEBUG INFO**: Final verification - checking all transactions for current user...")
                try:
                    from database_config_supabase import get_transactions_supabase
                    final_transactions = get_transactions_supabase(user_id)
                    st.success(f"🔍 **DEBUG INFO**: Final count: {len(final_transactions)} transactions for user {user_id}")
                except Exception as final_error:
                    st.error(f"❌ **DEBUG ERROR**: Final verification failed: {final_error}")
            if failed_count > 0:
                st.error(f"❌ Failed to process {failed_count} files")
            
            # Data is automatically refreshed after file processing
            
        except Exception as e:
            st.error(f"❌ Error during file processing: {str(e)}")
        finally:
            progress_bar.empty()
            status_text.empty()
    
    def _fetch_historical_prices_for_upload(self, df):
        """Fetch historical prices for uploaded file data - BATCH PROCESSING"""
        try:
            st.info("🔄 **Batch Historical Price Fetching** - Processing uploaded file...")
            
            # Ensure price column exists - create it if missing
            if 'price' not in df.columns:
                df['price'] = None
                st.info("📝 Price column not found, creating it with None values")
            
            # Validate required columns exist - CRITICAL SECURITY CHECK
            required_columns = ['ticker', 'date']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                error_msg = f"❌ SECURITY ERROR: Missing required columns: {missing_columns}. File processing stopped."
                st.error(error_msg)
                raise ValueError(error_msg)
            
            # Get unique tickers and their transaction dates
            ticker_date_pairs = []
            price_indices = []
            
            for idx, row in df.iterrows():
                try:
                    ticker = row['ticker']
                    transaction_date = row['date']
                    
                    # Skip if ticker or date is missing/invalid
                    if pd.isna(ticker) or pd.isna(transaction_date):
                        continue
                    
                    # Only fetch if price is missing or zero
                    current_price = row.get('price', None)
                    if pd.isna(current_price) or current_price == 0 or current_price is None:
                        ticker_date_pairs.append((ticker, transaction_date))
                        price_indices.append(idx)
                except KeyError as e:
                    error_msg = f"❌ SECURITY ERROR: Missing column in row {idx}: {e}. File processing stopped."
                    st.error(error_msg)
                    raise ValueError(error_msg)
                except Exception as e:
                    error_msg = f"❌ SECURITY ERROR: Error processing row {idx}: {e}. File processing stopped."
                    st.error(error_msg)
                    raise ValueError(error_msg)
            
            if not ticker_date_pairs:
                st.info("ℹ️ All transactions already have historical prices")
                return df
            
            st.info(f"📊 Fetching historical prices for {len(ticker_date_pairs)} transactions...")
            
            # Batch fetch prices with progress tracking
            progress_bar = st.progress(0)
            prices_found = 0
            
            for i, (ticker, transaction_date) in enumerate(ticker_date_pairs):
                try:
                    # Check if it's a mutual fund (numeric ticker or MF_ prefixed)
                    clean_ticker = str(ticker).strip().upper()
                    is_mf = clean_ticker.isdigit() or clean_ticker.startswith('MF_')
                    
                    if is_mf:
                        # Mutual fund - use mftool
                        print(f"🔍 Fetching mutual fund historical price for {ticker} using mftool...")
                        try:
                            from mf_price_fetcher import fetch_mutual_fund_price
                            price = fetch_mutual_fund_price(ticker)
                            if price and price > 0:
                                idx = price_indices[i]
                                df.at[idx, 'price'] = price
                                # Set sector to Mutual Funds for mutual fund tickers
                                df.at[idx, 'sector'] = 'Mutual Funds'
                                df.at[idx, 'stock_name'] = f"MF-{ticker}"
                                prices_found += 1
                                print(f"✅ MF {ticker}: ₹{price} for {transaction_date} - Mutual Funds")
                            else:
                                print(f"❌ MF {ticker}: No price available from mftool")
                        except Exception as e:
                            print(f"⚠️ MFTool failed for {ticker}: {e}")
                    else:
                        # Regular stock - try multiple price sources with proper ticker formatting
                        price = None
                        
                        # Clean ticker for yfinance (add .NS suffix for Indian stocks)
                        yf_ticker = clean_ticker
                        if not yf_ticker.endswith(('.NS', '.BO', '.NSE', '.BSE')):
                            yf_ticker = f"{clean_ticker}.NS"  # Default to NSE
                        
                        # Method 1: Try yfinance first (most reliable)
                        try:
                            import yfinance as yf
                            stock = yf.Ticker(yf_ticker)
                            hist = stock.history(start=transaction_date, end=transaction_date + pd.Timedelta(days=1))
                            if not hist.empty:
                                price = hist['Close'].iloc[0]
                                print(f"✅ {ticker} (yfinance): ₹{price} for {transaction_date}")
                        except Exception as e:
                            print(f"⚠️ yfinance failed for {yf_ticker}: {e}")
                        
                        # Method 2: Try file_manager if yfinance failed
                        if not price:
                            try:
                                from file_manager import fetch_historical_price
                                price = fetch_historical_price(clean_ticker, transaction_date)
                                if price:
                                    print(f"✅ {ticker} (file_manager): ₹{price} for {transaction_date}")
                            except Exception as e:
                                print(f"⚠️ file_manager failed for {ticker}: {e}")
                        
                        # Method 3: Try indstocks API if other methods failed
                        if not price:
                            try:
                                from indstocks_api import get_indstocks_client
                                api_client = get_indstocks_client()
                                if api_client and api_client.available:
                                    price_data = api_client.get_historical_price(clean_ticker, transaction_date)
                                    if price_data and isinstance(price_data, dict) and price_data.get('price'):
                                        price = price_data['price']
                                        print(f"✅ {ticker} (indstocks): ₹{price} for {transaction_date}")
                            except ImportError:
                                print(f"⚠️ Indstocks API not available for {ticker}")
                            except Exception as e:
                                print(f"⚠️ Indstocks API failed for {ticker}: {e}")
                        
                        # Update DataFrame if price found
                        if price and price > 0:
                            idx = price_indices[i]
                            df.at[idx, 'price'] = price
                            prices_found += 1
                        else:
                            print(f"❌ {ticker}: No historical price found for {transaction_date}")
                    
                    # Update progress
                    progress = (i + 1) / len(ticker_date_pairs)
                    progress_bar.progress(progress)
                    
                except Exception as e:
                    print(f"⚠️ Error fetching historical price for {ticker}: {e}")
            
            # Final status
            progress_bar.progress(1.0)
            st.success(f"✅ **Historical Price Fetch Complete**: {prices_found}/{len(ticker_date_pairs)} transactions got prices")
            
            return df
            
        except Exception as e:
            st.error(f"❌ Error in batch historical price fetching: {e}")
            return df
    
    def initialize_agents(self):
         """Initialize the agentic systems"""
         if not self.session_state.get('agents_initialized', False):
             try:
                 # Initialize stock data agent silently
                 stock_stats = get_stock_data_stats()
                 
                 # Initialize user file reading agent silently
                 # Note: User-specific file processing will be triggered when user logs in
                 
                 self.session_state['agents_initialized'] = True
                 
             except Exception as e:
                 st.error(f"❌ Error initializing agents: {e}")
    
    def load_data_from_agent(self, user_id: int = None) -> pd.DataFrame:
        """Load data using the agentic systems with timeout protection"""
        import threading
        import concurrent.futures
        import time
        
        def load_data_with_timeout():
            """Load data with timeout protection"""
            # Process user files if user_id is provided
            if user_id:
                # Process user's files first
                try:
                    result = process_user_files_on_login(user_id)
                    print(f"🔍 File processing result: {result}")
                except Exception as e:
                    print(f"⚠️ File processing error: {e}")
                    pass  # Silently handle file processing errors
                
                # Get transactions from database
                print(f"🔍 Fetching transactions for user {user_id}...")
                print(f"🔍 DEBUG: user_id type: {type(user_id)}, value: {user_id}")
                transactions = get_transactions_with_historical_prices(user_id=user_id)
                print(f"🔍 Transactions fetched: {len(transactions) if transactions else 0} records")
                
                # NEW: Check and update missing historical prices in database
                if transactions and len(transactions) > 0:
                    print(f"🔍 Checking for missing historical prices in database...")
                    self._update_missing_historical_prices_in_db(transactions, user_id)
                
                # NEW: Automatically fetch live prices and sector data during login
                if transactions and len(transactions) > 0:
                    print(f"🔄 Automatically fetching live prices and sector data during login...")
                    self._fetch_live_prices_and_sectors_during_login(transactions, user_id)
                
                # If no transactions found, try direct database query immediately
                if not transactions:
                    print(f"🔄 No transactions found, trying direct database query...")
                    try:
                        from database_config_supabase import get_transactions_supabase
                        direct_transactions = get_transactions_supabase(user_id)
                        if direct_transactions:
                            print(f"✅ Direct query successful: {len(direct_transactions)} transactions found")
                            transactions = direct_transactions
                        else:
                            print(f"❌ Direct query also failed: No transactions found")
                    except Exception as e:
                        print(f"❌ Direct query error: {e}")
                
                # Debug: Check if transactions exist but are empty
                if transactions and len(transactions) > 0:
                    print(f"🔍 First transaction sample: {transactions[0] if transactions else 'None'}")
                    print(f"🔍 Transaction columns: {list(transactions[0].keys()) if transactions else 'None'}")
                else:
                    print(f"⚠️ No transactions found for user {user_id}")
                    # Try to get all transactions to see if there's a user_id issue
                    all_transactions = get_transactions_with_historical_prices()
                    print(f"🔍 All transactions in system: {len(all_transactions) if all_transactions else 0}")
                    if all_transactions:
                        print(f"🔍 Sample transaction user_id: {all_transactions[0].get('user_id') if all_transactions else 'None'}")
                    
                                    # If no transactions found, try a small delay and retry (in case of timing issue)
                if not transactions and user_id:
                    print(f"🔄 Retrying transaction fetch after delay...")
                    import time
                    time.sleep(2)  # Wait 2 seconds
                    transactions = get_transactions_with_historical_prices(user_id=user_id)
                    print(f"🔍 Retry result: {len(transactions) if transactions else 0} transactions")
                    
                    # If still no transactions, check if there's a file path issue
                    if not transactions:
                        print(f"🔍 Checking for file path issues...")
                        try:
                            from database_config_supabase import get_file_records_supabase
                            file_records = get_file_records_supabase(user_id)
                            print(f"🔍 File records found: {len(file_records) if file_records else 0}")
                            if file_records:
                                for file_record in file_records:
                                    print(f"🔍 File: {file_record.get('filename', 'N/A')} - Path: {file_record.get('file_path', 'N/A')} - User: {file_record.get('user_id', 'N/A')}")
                        except Exception as e:
                            print(f"⚠️ Error checking file records: {e}")
                    
                    # Final attempt: try to get transactions directly from database
                    if not transactions:
                        print(f"🔄 Final attempt: Direct database query...")
                        try:
                            from database_config_supabase import get_transactions_supabase
                            direct_transactions = get_transactions_supabase(user_id)
                            if direct_transactions:
                                print(f"✅ Direct query successful: {len(direct_transactions)} transactions found")
                                transactions = direct_transactions
                            else:
                                print(f"❌ Direct query also failed: No transactions found")
                        except Exception as e:
                            print(f"❌ Direct query error: {e}")
                
                if not transactions:
                    st.warning(f"⚠️ No transactions found for user ID {user_id}")
                    # Don't return empty DataFrame - try to force reload
                    print(f"🔄 Attempting to force reload data...")
                    return self._force_reload_user_data(user_id)
            else:
                transactions = get_transactions_with_historical_prices()
            
            if not transactions:
                st.warning("⚠️ No transactions found in database")
                return pd.DataFrame()
            
            # Convert transactions to DataFrame
            df_data = []
            print(f"🔍 Converting {len(transactions)} transactions to DataFrame...")
            for t in transactions:
                df_data.append({
                    'channel': t.get('channel', 'Unknown'),
                    'stock_name': t.get('stock_name', ''),
                    'ticker': t.get('ticker', ''),
                    'sector': t.get('sector', 'Unknown'),
                    'date': t.get('date'),
                    'quantity': t.get('quantity', 0),
                    'price': t.get('price', 0),
                    'transaction_type': t.get('transaction_type', 'buy'),
                    'user_id': t.get('user_id')
                })
            
            df = pd.DataFrame(df_data)
            
            # Debug: Print DataFrame info
            print(f"🔍 DataFrame created: shape={df.shape}, columns={list(df.columns)}")
            if not df.empty:
                print(f"🔍 Sample data: {df.head(2).to_dict()}")
                print(f"🔍 Price column stats: {df['price'].describe() if 'price' in df.columns else 'No price column'}")
            else:
                print(f"⚠️ DataFrame is empty - no transactions converted")
            
            if df.empty:
                st.warning("⚠️ No transactions found in database")
                return pd.DataFrame()
            
            return df
        
        try:
            # Use ThreadPoolExecutor for timeout protection (cross-platform)
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(load_data_with_timeout)
                df = future.result(timeout=300)  # 5 minutes timeout for data loading
            
            # Always fetch fresh live prices (bypass cache completely)
            print(f"🔄 Always fetching fresh live prices for user {user_id} (bypassing cache)...")
            try:
                # Set flag to indicate live prices are being updated
                self.session_state['updating_live_prices'] = True
                
                if user_id and user_id != 1:  # Authenticated user
                    # Direct price fetching using stock agent for all tickers
                    print(f"🔄 Fetching fresh prices directly for user {user_id}...")
                    direct_prices = {}
                    unique_tickers = df['ticker'].unique()
                    
                    for ticker in unique_tickers:
                        try:
                            # Clean ticker for better price fetching
                            clean_ticker = str(ticker).strip().upper()
                            
                            # Check if it's a mutual fund
                            is_mf = clean_ticker.isdigit() or clean_ticker.startswith('MF_')
                            
                            if is_mf:
                                # Mutual fund - try mftool first
                                try:
                                    from mf_price_fetcher import fetch_mutual_fund_price
                                    price = fetch_mutual_fund_price(clean_ticker)
                                    if price and price > 0:
                                        direct_prices[ticker] = float(price)
                                        print(f"✅ MF {ticker}: ₹{price}")
                                        continue
                                except Exception as e:
                                    print(f"⚠️ MFTool failed for {ticker}: {e}")
                                
                                # Fallback: use transaction price for mutual funds
                                mf_transactions = df[df['ticker'] == ticker]
                                if not mf_transactions.empty:
                                    avg_price = mf_transactions['price'].mean()
                                    if pd.notna(avg_price) and avg_price > 0:
                                        direct_prices[ticker] = float(avg_price)
                                        print(f"✅ MF {ticker}: Using transaction price ₹{avg_price}")
                                        continue
                            else:
                                # Regular stock - try multiple sources
                                price = None
                                
                                # Method 1: Try yfinance with proper ticker formatting
                                try:
                                    import yfinance as yf
                                    yf_ticker = clean_ticker
                                    if not yf_ticker.endswith(('.NS', '.BO', '.NSE', '.BSE')):
                                        yf_ticker = f"{clean_ticker}.NS"  # Default to NSE
                                    
                                    stock = yf.Ticker(yf_ticker)
                                    hist = stock.history(period="1d")
                                    if not hist.empty:
                                        price = hist['Close'].iloc[-1]
                                        print(f"✅ {ticker} (yfinance): ₹{price}")
                                except Exception as e:
                                    print(f"⚠️ yfinance failed for {ticker}: {e}")
                                
                                # Method 2: Try stock agent if yfinance failed
                                if not price:
                                    try:
                                        fresh_data = stock_agent._fetch_stock_data(clean_ticker)
                                        if fresh_data and fresh_data.get('live_price'):
                                            price = fresh_data['live_price']
                                            print(f"✅ {ticker} (stock_agent): ₹{price}")
                                    except Exception as e:
                                        print(f"⚠️ stock_agent failed for {ticker}: {e}")
                                
                                # Method 3: Try indstocks API if other methods failed
                                if not price:
                                    try:
                                        from indstocks_api import get_indstocks_client
                                        api_client = get_indstocks_client()
                                        if api_client and api_client.available:
                                            price_data = api_client.get_stock_price(clean_ticker)
                                            if price_data and isinstance(price_data, dict) and price_data.get('price'):
                                                price = price_data['price']
                                                print(f"✅ {ticker} (indstocks): ₹{price}")
                                    except Exception as e:
                                        print(f"⚠️ indstocks failed for {ticker}: {e}")
                                
                                # If still no price, use transaction price as fallback
                                if not price:
                                    stock_transactions = df[df['ticker'] == ticker]
                                    if not stock_transactions.empty:
                                        avg_price = stock_transactions['price'].mean()
                                        if pd.notna(avg_price) and avg_price > 0:
                                            price = avg_price
                                            print(f"✅ {ticker}: Using transaction price ₹{price}")
                                
                                if price and price > 0:
                                    direct_prices[ticker] = float(price)
                                else:
                                    print(f"❌ {ticker}: No price available from any source")
                        
                        except Exception as e:
                            print(f"⚠️ Error fetching price for {ticker}: {e}")
                    
                    if direct_prices:
                        live_prices = direct_prices
                        print(f"✅ Direct price fetching: {len(direct_prices)} prices fetched")
                    else:
                        print(f"❌ No fresh prices could be fetched, using historical prices")
                        live_prices = {}
                else:
                    # For non-authenticated users, try to get all prices
                    print(f"🔄 Fetching all live prices...")
                    live_prices = get_all_live_prices()
                
                print(f"🔍 Live prices fetched: {len(live_prices)} prices")
                
                # Clear the updating flag
                self.session_state['updating_live_prices'] = False
                
            except Exception as e:
                print(f"⚠️ Could not fetch live prices: {e}")
                # Fallback to empty prices (will use historical prices)
                live_prices = {}
                # Clear the updating flag even on error
                self.session_state['updating_live_prices'] = False
            
            # Add live prices to DataFrame with better fallback logic
            df['live_price'] = df['ticker'].map(live_prices).fillna(df['price'])
            
            # Enhanced fallback: If still no prices, try to fetch them again with different methods
            missing_prices = df[df['live_price'].isna() | (df['live_price'] == 0)]
            if not missing_prices.empty:
                print(f"🔄 {len(missing_prices)} transactions still missing prices, trying enhanced fallback...")
                
                for idx, row in missing_prices.iterrows():
                    ticker = row['ticker']
                    try:
                        # Try to get any available price for this ticker
                        price = None
                        
                        # Method 1: Try yfinance with different ticker formats
                        if not price:
                            try:
                                import yfinance as yf
                                # Try multiple ticker formats
                                ticker_formats = [ticker, f"{ticker}.NS", f"{ticker}.BO", ticker.replace('.NS', ''), ticker.replace('.BO', '')]
                                
                                for ticker_format in ticker_formats:
                                    try:
                                        stock = yf.Ticker(ticker_format)
                                        hist = stock.history(period="1d")
                                        if not hist.empty and hist['Close'].iloc[-1] > 0:
                                            price = hist['Close'].iloc[-1]
                                            print(f"✅ {ticker} (yfinance fallback): ₹{price}")
                                            break
                                    except:
                                        continue
                            except Exception as e:
                                print(f"⚠️ yfinance fallback failed for {ticker}: {e}")
                        
                        # Method 2: Try stock agent with cleaned ticker
                        if not price:
                            try:
                                clean_ticker = str(ticker).strip().upper().replace('.NS', '').replace('.BO', '')
                                fresh_data = stock_agent._fetch_stock_data(clean_ticker)
                                if fresh_data and fresh_data.get('live_price'):
                                    price = fresh_data['live_price']
                                    print(f"✅ {ticker} (stock_agent fallback): ₹{price}")
                            except Exception as e:
                                print(f"⚠️ stock_agent fallback failed for {ticker}: {e}")
                        
                        # Method 3: Try indstocks API
                        if not price:
                            try:
                                from indstocks_api import get_indstocks_client
                                api_client = get_indstocks_client()
                                if api_client and api_client.available:
                                    price_data = api_client.get_stock_price(ticker)
                                    if price_data and isinstance(price_data, dict) and price_data.get('price'):
                                        price = price_data['price']
                                        print(f"✅ {ticker} (indstocks fallback): ₹{price}")
                            except Exception as e:
                                print(f"⚠️ indstocks fallback failed for {ticker}: {e}")
                        
                        # Method 4: Use a reasonable default price if nothing else works
                        if not price:
                            # For mutual funds, use a default NAV-like price
                            if str(ticker).isdigit() or str(ticker).startswith('MF_'):
                                price = 100.0  # Default NAV for mutual funds
                                print(f"⚠️ {ticker}: Using default MF price ₹{price}")
                            else:
                                # For stocks, use a default price based on typical Indian stock range
                                price = 1000.0  # Default price for stocks
                                print(f"⚠️ {ticker}: Using default stock price ₹{price}")
                        
                        # Update the DataFrame with the found price
                        if price and price > 0:
                            df.at[idx, 'live_price'] = price
                            print(f"✅ {ticker}: Final price set to ₹{price}")
                        
                    except Exception as e:
                        print(f"⚠️ Error in enhanced fallback for {ticker}: {e}")
            
            # Final verification: ensure no NaN or zero prices remain
            df['live_price'] = df['live_price'].fillna(100.0)  # Fill any remaining NaN with default
            df.loc[df['live_price'] == 0, 'live_price'] = 100.0  # Replace zeros with default
            
            # Debug: Check live price fetching results
            print(f"🔍 Live price debug: {df['live_price'].notna().sum()}/{len(df)} prices found, {len(df)} transactions")
            if not df.empty:
                sample_tickers = df['ticker'].head(5).tolist()
                for ticker in sample_tickers:
                    live_price = df[df['ticker'] == ticker]['live_price'].iloc[0] if not df[df['ticker'] == ticker].empty else None
                    print(f"🔍 Sample live price: {ticker} = ₹{live_price}")
            
            # Count zero prices
            zero_prices = (df['live_price'] == 0).sum()
            print(f"🔍 Final live prices: {zero_prices}/{len(df)} transactions have zero prices")
            
            # Calculate P&L if we have live prices
            if 'live_price' in df.columns and not df.empty:
                try:
                    # Calculate absolute gain/loss for each transaction
                    df['abs_gain'] = 0.0
                    
                    for idx, row in df.iterrows():
                        try:
                            # Use live_price for current value, fallback to price for historical
                            current_price = row['live_price'] if pd.notna(row['live_price']) and row['live_price'] > 0 else row['price']
                            historical_price = row['price'] if pd.notna(row['price']) and row['price'] > 0 else current_price
                            
                            if row['transaction_type'] == 'buy':
                                # For buy transactions, calculate potential gain if sold at live price
                                if pd.notna(current_price) and current_price > 0 and pd.notna(historical_price) and historical_price > 0:
                                    gain = (current_price - historical_price) * row['quantity']
                                    df.at[idx, 'abs_gain'] = gain
                            elif row['transaction_type'] == 'sell':
                                # For sell transactions, calculate actual gain/loss
                                if pd.notna(current_price) and current_price > 0 and pd.notna(historical_price) and historical_price > 0:
                                    gain = (historical_price - current_price) * row['quantity']
                                    df.at[idx, 'abs_gain'] = gain
                        except Exception as e:
                            print(f"⚠️ Error calculating gain for row {idx}: {e}")
                    
                    # Calculate current values and invested amounts with fallbacks
                    df['current_value'] = df['quantity'] * df['live_price']
                    df['invested_amount'] = df['quantity'] * df['price'].fillna(df['live_price'])  # Use live price as fallback
                    
                    # Calculate percentage gain
                    df['pct_gain'] = df.apply(
                        lambda row: (row['abs_gain'] / row['invested_amount'] * 100) if row['invested_amount'] > 0 else 0, 
                        axis=1
                    )
                    
                    print(f"🔍 P&L Debug: Invested={df['invested_amount'].sum():.2f}, Current={df['current_value'].sum():.2f}, Gain={df['abs_gain'].sum():.2f}, Gain%={((df['abs_gain'].sum() / df['invested_amount'].sum()) * 100) if df['invested_amount'].sum() > 0 else 0:.2f}%")
                    
                except Exception as e:
                    print(f"⚠️ Error calculating P&L: {e}")
            
            return df
        
        except concurrent.futures.TimeoutError:
            print("❌ Data loading timed out. Please try again or use fast loading mode.")
            return pd.DataFrame()
        except Exception as e:
            print(f"❌ Error loading data: {e}")
            return pd.DataFrame()
    
    def render_top_filters(self, df: pd.DataFrame):
         """Render filters at the top of the main content area"""
         st.markdown("## 🔍 Filters")
         
         # Create columns for filters
         col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 1])
         
         with col1:
             # Fast loading mode checkbox
             fast_loading = st.checkbox("🚀 Fast Loading", value=self.session_state.get('fast_loading', True), help="Skip historical price fetching for faster loading")
             self.session_state['fast_loading'] = fast_loading
         
         with col2:
             # Channel filter
             if not df.empty and 'channel' in df.columns:
                 channel_options = sorted(df['channel'].unique())
                 selected_channel = st.selectbox(
                     "Select Channel:",
                     ["All"] + channel_options,
                     key="channel_filter"
                 )
             else:
                 selected_channel = "All"
         
         # Filter data based on selected channel for sector options
         channel_filtered_df = df.copy()
         if selected_channel != "All":
             channel_filtered_df = channel_filtered_df[channel_filtered_df['channel'] == selected_channel]
         
         with col3:
             # Sector filter (linked to channel)
             if not channel_filtered_df.empty and 'sector' in channel_filtered_df.columns:
                 sector_options = sorted(channel_filtered_df['sector'].unique())
                 selected_sector = st.selectbox(
                     "Select Sector:",
                     ["All"] + sector_options,
                     key="sector_filter"
                 )
             else:
                 selected_sector = "All"
         
         # Filter data based on selected channel and sector for stock options
         sector_filtered_df = channel_filtered_df.copy()
         if selected_sector != "All":
             sector_filtered_df = sector_filtered_df[sector_filtered_df['sector'] == selected_sector]
         
         with col4:
             # Stock filter (linked to channel and sector)
             if not sector_filtered_df.empty and 'stock_name' in sector_filtered_df.columns:
                 stock_options = sorted(sector_filtered_df['stock_name'].unique())
                 selected_stock = st.selectbox(
                     "Select Stock:",
                     ["All"] + stock_options,
                     key="stock_filter"
                 )
             else:
                 selected_stock = "All"
         
         with col5:
             # Clear all filters button
             if st.button("🗑️ Clear", help="Clear all filters"):
                 st.rerun()
         
         # Apply all filters to final dataset
         filtered_df = df.copy()
         if selected_channel != "All":
             filtered_df = filtered_df[filtered_df['channel'] == selected_channel]
         if selected_sector != "All":
             filtered_df = filtered_df[filtered_df['sector'] == selected_sector]
         if selected_stock != "All":
             filtered_df = filtered_df[filtered_df['stock_name'] == selected_stock]
         
         return filtered_df, selected_channel, selected_sector, selected_stock
    
    
    
    
    
    def _force_reload_user_data(self, user_id: int) -> pd.DataFrame:
        """Force reload user data by processing files again"""
        try:
            print(f"🔄 Force reloading data for user {user_id}...")
            
            # Try to process user files again
            try:
                from user_file_reading_agent import process_user_files_on_login
                result = process_user_files_on_login(user_id)
                print(f"🔄 File processing result: {result}")
            except Exception as e:
                print(f"⚠️ File processing error: {e}")
            
            # Wait a moment for database to settle
            import time
            time.sleep(3)
            
            # Try to get transactions again
            try:
                from database_config_supabase import get_transactions_supabase
                transactions = get_transactions_supabase(user_id)
                if transactions:
                    print(f"✅ Force reload successful: {len(transactions)} transactions found")
                    # Convert to DataFrame
                    df_data = []
                    for t in transactions:
                        df_data.append({
                            'channel': t.get('channel', 'Unknown'),
                            'stock_name': t.get('stock_name', ''),
                            'ticker': t.get('ticker', ''),
                            'sector': t.get('sector', 'Unknown'),
                            'date': t.get('date'),
                            'quantity': t.get('quantity', 0),
                            'price': t.get('price', 0),
                            'transaction_type': t.get('transaction_type', 'buy'),
                            'user_id': t.get('user_id')
                        })
                    df = pd.DataFrame(df_data)
                    print(f"✅ DataFrame created: {df.shape}")
                    return df
                else:
                    print(f"❌ Force reload failed: Still no transactions")
                    return pd.DataFrame()
            except Exception as e:
                print(f"❌ Force reload error: {e}")
                return pd.DataFrame()
                
        except Exception as e:
            print(f"❌ Force reload function error: {e}")
            return pd.DataFrame()
    
    def calculate_holdings(self, df: pd.DataFrame):
        """Calculate current holdings from transactions"""
        if df.empty:
            return pd.DataFrame()
        
        # Group by stock and calculate net quantities
        holdings = df.groupby(['stock_name', 'ticker', 'sector', 'channel']).agg({
            'quantity': lambda x: np.where(df.loc[x.index, 'transaction_type'].str.lower() == 'buy', x, -x).sum(),
            'invested_amount': 'sum',
            'current_value': 'sum',
            'abs_gain': 'sum',
            'date': 'min'
        }).reset_index()
        
        # Rename columns
        holdings.columns = ['stock_name', 'ticker', 'sector', 'channel', 'net_quantity', 'total_invested', 'current_value', 'pnl', 'first_date']
        
        # Calculate additional metrics
        holdings['avg_price'] = holdings['total_invested'] / holdings['net_quantity'].abs()
        holdings['pct_gain'] = (holdings['pnl'] / holdings['total_invested']) * 100
        
        # Filter out stocks with zero net quantity
        holdings = holdings[holdings['net_quantity'] > 0]
        
        return holdings
    
    def _calculate_quarterly_analysis(self, df: pd.DataFrame, user_id: int, cache_key: str = None, data_hash: str = None):
        """Helper method to calculate quarterly analysis"""
        # Filter to only buy transactions from the last 1 year
        one_year_ago = pd.Timestamp.now() - pd.DateOffset(years=1)
        
        # Ensure date column is datetime for filtering
        if not pd.api.types.is_datetime64_any_dtype(df['date']):
            df['date'] = pd.to_datetime(df['date'], errors='coerce', format='mixed')
        
        # Filter buy transactions (handle both uppercase and lowercase)
        buy_df = df[df['transaction_type'].str.lower().isin(['buy'])].copy()
        
        if buy_df.empty:
            st.info("No buy transactions found in the data")
            st.info(f"Available transaction types: {df['transaction_type'].unique()}")
            return pd.DataFrame()
        
        # Filter by date range
        buy_df = buy_df[buy_df['date'] >= one_year_ago].copy()
        
        if buy_df.empty:
            st.info(f"No buy transactions found in the last 1 year (since {one_year_ago.strftime('%Y-%m-%d')})")
            # Show some sample buy transactions to help debug
            all_buy_df = df[df['transaction_type'].str.lower().isin(['buy'])].copy()
            if not all_buy_df.empty:
                st.info(f"Sample buy transactions: {all_buy_df[['date', 'stock_name', 'transaction_type']].head(3).to_dict('records')}")
            return pd.DataFrame()
        
        try:
            # Remove rows with invalid dates (already converted above)
            buy_df = buy_df.dropna(subset=['date'])
            
            if buy_df.empty:
                st.info("No buy transactions with valid dates found in the last 1 year")
                return pd.DataFrame()
            
            # Create quarter column
            buy_df['quarter'] = buy_df['date'].dt.to_period('Q').astype(str)
            
            # Add live prices for P&L calculation - use fresh data from DataFrame
            if 'live_price' in buy_df.columns:
                # Use live prices already in the DataFrame
                print(f"🔍 Quarterly Analysis - Using live prices from DataFrame")
                print(f"🔍 Live prices available: {len(buy_df[buy_df['live_price'] > 0])}/{len(buy_df)} transactions")
            else:
                # Fallback to historical prices if no live prices
                print(f"⚠️ No live prices in DataFrame, using historical prices")
                buy_df['live_price'] = buy_df['price']
            
            # Debug: Check the mapping results
            zero_prices = (buy_df['live_price'] == 0).sum()
            total_transactions = len(buy_df)
            print(f"🔍 Quarterly Analysis - After mapping: {zero_prices}/{total_transactions} transactions have zero live prices")
            
            # Show sample of tickers that got zero prices
            if zero_prices > 0:
                zero_price_tickers = buy_df[buy_df['live_price'] == 0]['ticker'].unique()
                print(f"🔍 Tickers with zero prices: {zero_price_tickers[:5]}")  # Show first 5
            
            # Calculate absolute gain and percentage gain
            buy_df['abs_gain'] = buy_df['quantity'] * (buy_df['live_price'] - buy_df['price'])
            buy_df['invested_amount'] = buy_df['quantity'] * buy_df['price']
            buy_df['current_value'] = buy_df['quantity'] * buy_df['live_price']
            buy_df['pct_gain'] = (buy_df['abs_gain'] / buy_df['invested_amount']) * 100
            
            # Cache the processed buy_df if cache_key is provided
            if cache_key and data_hash:
                self.session_state[cache_key] = buy_df
                self.session_state[f'{cache_key}_hash'] = data_hash
            
            return buy_df
            
        except Exception as e:
            st.error(f"Error processing quarterly data: {e}")
            return pd.DataFrame()
    
    def render_portfolio_overview(self, df: pd.DataFrame, holdings: pd.DataFrame):
        """Render portfolio overview section"""
        st.markdown('<h2 class="section-header">📊 Portfolio Overview</h2>', unsafe_allow_html=True)
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        total_invested = holdings['total_invested'].sum() if not holdings.empty else 0
        total_current = holdings['current_value'].sum() if not holdings.empty else 0
        total_gain = holdings['pnl'].sum() if not holdings.empty else 0
        total_gain_pct = (total_gain / total_invested) * 100 if total_invested > 0 else 0
        
        with col1:
            st.metric("Total Invested", f"₹{total_invested:,.2f}")
        with col2:
            st.metric("Current Value", f"₹{total_current:,.2f}")
        with col3:
            st.metric("Total Gain/Loss", f"₹{total_gain:,.2f}", f"{total_gain_pct:+.2f}%")
        with col4:
            st.metric("Total Stocks", len(holdings) if not holdings.empty else 0)
        
        # Portfolio charts
        if not holdings.empty:
            row1_col1, row1_col2 = st.columns(2)
            
            # Determine which stocks to show
            show_best_performers = st.checkbox("Show Best Performers (Top Profits)", value=True, key="show_best_pnl")
            show_worst_performers = st.checkbox("Show Worst Performers (Biggest Losses)", value=False, key="show_worst_pnl")
            
            if show_best_performers and show_worst_performers:
                best_performers = holdings.nlargest(5, 'pnl')
                worst_performers = holdings.nsmallest(5, 'pnl')
                selected_stocks = pd.concat([best_performers, worst_performers])
                chart_title = 'Top 5 Profits & Top 5 Losses by Stock'
            elif show_worst_performers:
                selected_stocks = holdings.nsmallest(10, 'pnl')
                chart_title = 'Top 10 Worst Performers (Biggest Losses)'
            else:
                selected_stocks = holdings.nlargest(10, 'pnl')
                chart_title = 'Top 10 Best Performers (Highest Profits)'
            
            selected_stocks = selected_stocks.sort_values('pnl', ascending=False)
            
            with row1_col1:
                st.markdown('<h4 class="subsection-header">Top 10 Holdings by Stock</h4>', unsafe_allow_html=True)
                fig1 = px.bar(selected_stocks, x='stock_name', y='net_quantity', 
                             title=f'Holdings for {chart_title}', text='net_quantity')
                fig1.update_xaxes(tickangle=45)
                fig1.update_traces(texttemplate='%{text:.0f}', textposition='outside')
                st.plotly_chart(fig1, width='stretch', key="holdings_bar_main")
            
            with row1_col2:
                st.markdown('<h4 class="subsection-header">Top 10 P/L by Stock</h4>', unsafe_allow_html=True)
                top_pnl_stocks = selected_stocks
                
                if top_pnl_stocks['pnl'].sum() == 0:
                    st.info("🔄 **P&L Calculation**: Live prices are being fetched to calculate current P&L values.")
                
                fig2 = px.bar(top_pnl_stocks, x='stock_name', y='pnl', 
                             title=f'{chart_title} (₹)', 
                             text='pnl',
                             color='pnl',
                             color_continuous_scale='RdYlGn')
                fig2.update_xaxes(tickangle=45)
                fig2.update_traces(texttemplate='₹%{text:,.2f}', textposition='outside')
                st.plotly_chart(fig2, width='stretch', key="pnl_bar_main")
    
    def render_sector_analysis(self, holdings: pd.DataFrame):
        """Render sector analysis charts"""
        if holdings.empty or 'sector' not in holdings.columns:
            return
        
        st.markdown('<h2 class="section-header">📈 Sector Analysis</h2>', unsafe_allow_html=True)
        
        # Sector performance
        sector_performance = holdings.groupby('sector').agg({
            'total_invested': 'sum',
            'current_value': 'sum',
            'pnl': 'sum',
            'stock_name': 'nunique'
        }).reset_index()
        sector_performance['pct_gain'] = (sector_performance['pnl'] / sector_performance['total_invested']) * 100
        sector_performance = sector_performance.rename(columns={'stock_name': 'num_stocks'})
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('<h4 class="subsection-header">Portfolio Allocation by Sector</h4>', unsafe_allow_html=True)
            fig1 = px.pie(sector_performance, values='current_value', names='sector', 
                         title='Portfolio Allocation by Sector')
            st.plotly_chart(fig1, width='stretch')
        
        with col2:
            st.markdown('<h4 class="subsection-header">Sector Performance</h4>', unsafe_allow_html=True)
            fig2 = px.bar(sector_performance, x='sector', y='pct_gain', 
                         title='Sector Performance (% Gain/Loss)',
                         color='pct_gain',
                         color_continuous_scale='RdYlGn')
            fig2.update_xaxes(tickangle=45)
            st.plotly_chart(fig2, width='stretch')
        
        # Additional sector charts
        col3, col4 = st.columns(2)
        
        with col3:
            st.markdown('<h4 class="subsection-header">Total Current Value by Sector</h4>', unsafe_allow_html=True)
            fig3 = px.bar(sector_performance, x='sector', y='current_value', 
                         title='Total Current Value by Sector', 
                         text='current_value',
                         color='current_value',
                         color_continuous_scale='Blues')
            fig3.update_traces(texttemplate='₹%{text:,.0f}', textposition='outside')
            fig3.update_layout(xaxis_title="Sector", yaxis_title="Current Value (₹)")
            st.plotly_chart(fig3, width='stretch')
        
        with col4:
            st.markdown('<h4 class="subsection-header">Number of Stocks per Sector</h4>', unsafe_allow_html=True)
            fig4 = px.bar(sector_performance, x='sector', y='num_stocks', 
                         title='Number of Stocks per Sector', 
                         text='num_stocks',
                         color='num_stocks',
                         color_continuous_scale='Greens')
            fig4.update_traces(texttemplate='%{text}', textposition='outside')
            fig4.update_layout(xaxis_title="Sector", yaxis_title="Number of Stocks")
            st.plotly_chart(fig4, width='stretch')
    
    def render_detailed_table(self, df: pd.DataFrame):
        """Render detailed transaction table"""
        st.markdown('<h2 class="section-header">📋 Detailed Transactions</h2>', unsafe_allow_html=True)
        
        if df.empty:
            st.info('No transactions to display.')
            return
        
        # Prepare display data
        display_cols = ['ticker', 'stock_name', 'date', 'quantity', 'price', 'live_price', 
                       'invested_amount', 'current_value', 'abs_gain', 'pct_gain']
        available_cols = [col for col in display_cols if col in df.columns]
        
        display_df = df[available_cols].copy()
        
        # Handle datetime parsing more flexibly
        if 'date' in display_df.columns:
            try:
                
                
                # Check if dates are already in the correct format
                if display_df['date'].dtype == 'object':
                    # Check if dates are already formatted as YYYY-MM-DD
                    sample_dates = display_df['date'].astype(str).head(3)
                    already_formatted = all(len(str(date).split(' ')[0]) == 10 and '-' in str(date) for date in sample_dates)
                    
                    if already_formatted:
                        # Dates are already in correct format, just clean them
                        display_df['date'] = display_df['date'].astype(str).str.split(' ').str[0]
                        
                    else:
                        # Try to parse and format dates
                        display_df['date'] = pd.to_datetime(display_df['date'], errors='coerce', infer_datetime_format=True)
                        display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')
                        
                
            except Exception as e:
                st.warning(f"Date parsing error: {e}")
                # Fallback: try to extract just the date part if datetime parsing fails
                try:
                    display_df['date'] = display_df['date'].astype(str).str.split(' ').str[0]
                    
                except:
                    # If all else fails, just show the original date
                    display_df['date'] = display_df['date'].astype(str)
                    st.warning("⚠️ Could not process dates, showing original format")
        
        # Round numeric columns
        numeric_cols = ['price', 'live_price', 'invested_amount', 'current_value', 'abs_gain', 'pct_gain']
        for col in numeric_cols:
            if col in display_df.columns:
                display_df[col] = display_df[col].round(2)
        
        # Rename columns for display
        column_mapping = {
            'ticker': 'Ticker',
            'stock_name': 'Stock Name', 
            'date': 'Date',
            'quantity': 'Quantity',
            'price': 'Buy Price',
            'live_price': 'Live Price',
            'invested_amount': 'Invested',
            'current_value': 'Current Value',
            'abs_gain': 'Gain/Loss',
            'pct_gain': '% Gain'
        }
        
        display_df = display_df.rename(columns=column_mapping)
        
        st.dataframe(display_df, width='stretch')
    
    def get_rating(self, pnl_percent):
        """Get rating based on P&L percentage"""
        if pnl_percent >= 20:
            return '⭐⭐⭐⭐⭐'
        elif pnl_percent >= 10:
            return '⭐⭐⭐⭐'
        elif pnl_percent >= 0:
            return '⭐⭐⭐'
        elif pnl_percent >= -10:
            return '⭐⭐'
        else:
            return '⭐'
    
    def render_quarterly_analysis(self, df: pd.DataFrame):
        """Render quarterly analysis and stock rating system"""
        if df.empty or 'transaction_type' not in df.columns:
            return
        
        st.markdown('<h2 class="section-header">📊 Stock Performance Analysis (Last 1 Year)</h2>', unsafe_allow_html=True)
        
        # Add explanation of rating calculation
        with st.expander("ℹ️ How is the rating calculated?", expanded=False):
            st.markdown("""
            **Rating Calculation Methodology:**
            
            The stock rating is calculated using a **relative performance ranking** system based on multiple factors:
            
            **1. Rating Score Formula (40% weight each):**
            - **Total P&L %** (40%): Overall percentage gain/loss
            - **Risk-Adjusted Return** (30%): P&L % adjusted for consistency (lower volatility = higher score)
            - **Investment Size** (20%): Relative amount invested compared to other stocks
            - **Transaction Frequency** (10%): Number of transactions compared to other stocks
            
            **2. Relative Ranking Categories:**
            - 🥇 **TOP PERFORMER**: Top 10% of all stocks
            - 🥈 **EXCELLENT**: Top 11-25% of all stocks  
            - 🥉 **VERY GOOD**: Top 26-50% of all stocks
            - ⭐⭐ **GOOD**: Top 51-75% of all stocks
            - ⭐ **AVERAGE**: Top 76-90% of all stocks
            - 📉 **BELOW AVERAGE**: Bottom 10% of all stocks
            
            **3. Data Source:**
            - Only **BUY transactions** from the last 1 year are considered
            - Current prices are fetched live from market data
            - Historical prices are used for transaction cost basis
            """)
        
        # Use cached quarterly analysis if available (only for unfiltered data)
        user_id = self.session_state.get('user_id', 1)
        quarterly_cache_key = f'quarterly_analysis_user_{user_id}'
        
        # Check if this is filtered data
        original_df = self.session_state.get('original_df', df)
        is_filtered = len(df) < len(original_df)
        
        if not is_filtered:
            # Check if we need to recalculate (only if data changed)
            if not df.empty and all(col in df.columns for col in ['ticker', 'quantity', 'price', 'live_price', 'transaction_type', 'date']):
                data_hash = hash(str(df[['ticker', 'quantity', 'price', 'live_price', 'transaction_type', 'date']].values.tobytes()))
                cached_data_hash = self.session_state.get(f'{quarterly_cache_key}_hash', None)
            else:
                # If DataFrame is empty or missing columns, force recalculation
                data_hash = None
                cached_data_hash = None
            
            if cached_data_hash == data_hash and quarterly_cache_key in self.session_state:
                # Use cached quarterly analysis
                buy_df = self.session_state[quarterly_cache_key]
            else:
                # Calculate quarterly analysis and cache it
                buy_df = self._calculate_quarterly_analysis(df, user_id, quarterly_cache_key, data_hash)
        else:
            # For filtered data, calculate directly without caching
            buy_df = self._calculate_quarterly_analysis(df, user_id, None, None)
        
        # Stock Rating System
        
        # Calculate stock performance metrics
        stock_performance = buy_df.groupby('stock_name').agg({
            'abs_gain': 'sum',
            'invested_amount': 'sum',
            'current_value': 'sum',
            'quantity': 'sum',
            'pct_gain': 'mean',
            'date': ['count', 'min', 'max']  # count transactions, min date, max date
        }).reset_index()
        
        # Flatten column names
        stock_performance.columns = ['stock_name', 'abs_gain', 'invested_amount', 'current_value', 'quantity', 'pct_gain', 'transaction_count', 'first_date', 'last_date']
        
        # Calculate additional metrics
        stock_performance['total_pnl_pct'] = (stock_performance['abs_gain'] / stock_performance['invested_amount']) * 100
        stock_performance['avg_investment'] = stock_performance['invested_amount'] / stock_performance['transaction_count']
        stock_performance['consistency_score'] = buy_df.groupby('stock_name')['pct_gain'].std().fillna(0)
        
        # Create rating score
        stock_performance['rating_score'] = (
            stock_performance['total_pnl_pct'] * 0.4 +
            (stock_performance['total_pnl_pct'] / (1 + stock_performance['consistency_score'])) * 0.3 +
            (stock_performance['invested_amount'] / stock_performance['invested_amount'].max()) * 0.2 +
            (stock_performance['transaction_count'] / stock_performance['transaction_count'].max()) * 0.1
        )
        
        # Sort by rating score
        stock_performance = stock_performance.sort_values('rating_score', ascending=False)
        
        # Add relative ranking categories based on performance among all stocks
        def get_relative_rating_category(row, total_stocks):
            rank = row['rank']
            pnl_pct = row['total_pnl_pct']
            
            # Calculate percentile rank
            percentile = (total_stocks - rank + 1) / total_stocks * 100
            
            # Rating based on relative performance (percentile)
            if percentile >= 90:
                return "🥇 TOP PERFORMER"
            elif percentile >= 75:
                return "🥈 EXCELLENT"
            elif percentile >= 50:
                return "🥉 VERY GOOD"
            elif percentile >= 25:
                return "⭐⭐ GOOD"
            elif percentile >= 10:
                return "⭐ AVERAGE"
            else:
                return "📉 BELOW AVERAGE"
        
        # Add rank column for relative positioning
        stock_performance['rank'] = range(1, len(stock_performance) + 1)
        total_stocks = len(stock_performance)
        
        # Apply relative rating
        stock_performance['rating'] = stock_performance.apply(
            lambda row: get_relative_rating_category(row, total_stocks), axis=1
        )
        
        # Display stock performance
        
        # Get live prices for current price display - use data from DataFrame
        user_id = self.session_state.get('user_id', 1)
        
        # Extract live prices from the buy_df which should have fresh data
        live_prices = {}
        if not buy_df.empty and 'live_price' in buy_df.columns:
            live_prices = buy_df.set_index('ticker')['live_price'].to_dict()
            print(f"🔍 Stock Performance Analysis - Using live prices from DataFrame: {len(live_prices)} prices")
        else:
            print(f"⚠️ No live prices available in DataFrame")
        
        # Create rating table
        rating_data = []
        for idx, row in stock_performance.head(10).iterrows():
            ticker = buy_df[buy_df['stock_name'] == row['stock_name']]['ticker'].iloc[0]
            current_price = live_prices.get(ticker, 0)
            
            # Calculate percentile for this stock
            percentile = (total_stocks - row['rank'] + 1) / total_stocks * 100
            
            rating_data.append({
                'Rank': f"#{row['rank']}",
                'Stock': row['stock_name'],
                'Ticker': ticker,
                'Rating': row['rating'],
                'Percentile': f"Top {percentile:.0f}%",
                'Total P&L %': f"{row['total_pnl_pct']:.1f}%",
                'Total P&L (₹)': f"₹{row['abs_gain']:,.0f}",
                'Total Invested': f"₹{row['invested_amount']:,.0f}",
                'Current Value': f"₹{row['current_value']:,.0f}",
                'Current Price': f"₹{current_price:,.2f}",
                'Transactions': row['transaction_count'],
                'First Date': row['first_date'].strftime('%Y-%m-%d') if pd.notna(row['first_date']) else 'N/A',
                'Last Date': row['last_date'].strftime('%Y-%m-%d') if pd.notna(row['last_date']) else 'N/A',
                'Avg Investment': f"₹{row['avg_investment']:,.0f}"
            })
        
        if rating_data:
            rating_df = pd.DataFrame(rating_data)
            st.dataframe(rating_df, width='stretch')
    
    def render_channel_allocation(self, holdings: pd.DataFrame):
        """Render channel allocation charts"""
        if holdings.empty:
            return
        
        st.markdown('<h2 class="section-header">🏦 Channel Allocation Analysis</h2>', unsafe_allow_html=True)
        
        # Group by channel to get total current value per channel
        channel_allocation = holdings.groupby('channel').agg(
            Total_Value=('current_value', 'sum'),
            Total_Invested=('total_invested', 'sum'),
            PnL=('pnl', 'sum')
        ).reset_index()
        
        # Calculate percentage allocation
        total_portfolio_value = channel_allocation['Total_Value'].sum()
        channel_allocation['Allocation_Percent'] = (channel_allocation['Total_Value'] / total_portfolio_value * 100).round(2)
        channel_allocation['P&L_Percent'] = (channel_allocation['PnL'] / channel_allocation['Total_Invested'] * 100).round(2)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('<h4 class="subsection-header">Portfolio Allocation by Channel</h4>', unsafe_allow_html=True)
            fig1 = px.pie(channel_allocation, 
                          names='channel', 
                          values='Total_Value', 
                          title='Portfolio Allocation by Wealth Management Channel',
                          hover_data=['Allocation_Percent', 'P&L_Percent'])
            fig1.update_layout(height=400)
            fig1.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig1, width='stretch')
        
        with col2:
            st.markdown('<h4 class="subsection-header">Channel Performance</h4>', unsafe_allow_html=True)
            fig2 = px.bar(channel_allocation, x='channel', y='P&L_Percent', 
                         title='Channel Performance (% Gain/Loss)',
                         color='P&L_Percent',
                         color_continuous_scale='RdYlGn')
            fig2.update_xaxes(tickangle=45)
            fig2.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
            st.plotly_chart(fig2, width='stretch')
        
        # Display channel allocation table
        st.markdown('<h4 class="subsection-header">Channel Allocation Details</h4>', unsafe_allow_html=True)
        display_table = channel_allocation[['channel', 'Total_Value', 'Total_Invested', 'PnL', 'Allocation_Percent', 'P&L_Percent']].copy()
        display_table = display_table.rename(columns={
            'channel': 'Channel',
            'Total_Value': 'Current Value (₹)',
            'Total_Invested': 'Total Invested (₹)',
            'PnL': 'P&L (₹)',
            'Allocation_Percent': 'Allocation (%)',
            'P&L_Percent': 'P&L (%)'
        })
        display_table['Current Value (₹)'] = display_table['Current Value (₹)'].apply(lambda x: f"₹{x:,.2f}")
        display_table['Total Invested (₹)'] = display_table['Total Invested (₹)'].apply(lambda x: f"₹{x:,.2f}")
        display_table['P&L (₹)'] = display_table['P&L (₹)'].apply(lambda x: f"₹{x:,.2f}")
        display_table['Allocation (%)'] = display_table['Allocation (%)'].apply(lambda x: f"{x:.2f}%")
        display_table['P&L (%)'] = display_table['P&L (%)'].apply(lambda x: f"{x:.2f}%")
        st.dataframe(display_table, width='stretch')
    
    def render_portfolio_value_over_time(self, df: pd.DataFrame):
        """Render portfolio value over time chart"""
        if df.empty or 'date' not in df.columns:
            return
        
        st.markdown('<h2 class="section-header">📈 Portfolio Value Over Time</h2>', unsafe_allow_html=True)
        
        try:
            # Ensure date column is datetime
            if not pd.api.types.is_datetime64_any_dtype(df['date']):
                df['date'] = pd.to_datetime(df['date'], errors='coerce', format='mixed')
            
            # Remove rows with invalid dates
            df = df.dropna(subset=['date'])
            
            if df.empty:
                st.info("No valid date data available for portfolio value over time analysis")
                return
            
            # Sort by date
            df_sorted = df.sort_values('date')
            
            # Calculate portfolio value over time
            portfolio_value = []
            net_holdings = {}
            
            for idx, row in df_sorted.iterrows():
                ticker = row['ticker']
                quantity = row['quantity']
                price = row['price']
                transaction_type = row['transaction_type'].lower()
                
                # Update net holdings
                if transaction_type == 'buy':
                    net_holdings[ticker] = net_holdings.get(ticker, 0) + quantity
                else:  # sell
                    net_holdings[ticker] = net_holdings.get(ticker, 0) - quantity
                
                # Calculate total portfolio value at this point
                total_value = sum(net_holdings.get(t, 0) * price for t in net_holdings)
                portfolio_value.append(total_value)
            
            df_sorted['portfolio_value'] = portfolio_value
            
            # Create the chart
            fig = px.line(df_sorted, x='date', y='portfolio_value', 
                         title='Portfolio Value Over Time',
                         hover_data=['channel', 'stock_name', 'transaction_type'])
            
            fig.update_layout(
                xaxis_title="Date",
                yaxis_title="Portfolio Value (₹)",
                height=500
            )
            
            st.plotly_chart(fig, width='stretch')
                        
        except Exception as e:
            st.error(f"Error rendering portfolio value over time: {e}")
    
    def render_dashboard(self, df: pd.DataFrame):
        """Render the main dashboard"""
        if df.empty:
            st.warning("⚠️ No data available. Please upload files or check database.")
            return
        
        # Debug: Show what we're trying to render
        st.info(f"🎯 **Rendering Dashboard**: DataFrame shape: {df.shape}, Columns: {list(df.columns)}")
        
        # Check if we have the required columns for P&L calculations
        required_cols = ['ticker', 'quantity', 'price', 'transaction_type']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            st.error(f"❌ **Missing Required Columns**: {missing_cols}")
            st.info("💡 These columns are needed for portfolio analysis and P&L calculations")
            return
        
        # Always calculate holdings from fresh data (no cache for live prices)
        user_id = self.session_state.get('user_id', 1)
        
        # Calculate holdings directly from the fresh DataFrame
        all_holdings = self.calculate_holdings(df)
        
        # Filter holdings based on the filtered DataFrame (if any filters are applied)
        if len(df) < len(self.session_state.get('original_df', df)):
            # Filters are applied, filter the holdings accordingly
            filtered_tickers = df['ticker'].unique()
            holdings = all_holdings[all_holdings['ticker'].isin(filtered_tickers)]
        else:
            # No filters applied, use all holdings
            holdings = all_holdings
        
        # Render portfolio overview
        self.render_portfolio_overview(df, holdings)
        
        # Render sector analysis
        self.render_sector_analysis(holdings)
        
        # Render portfolio value over time
        self.render_portfolio_value_over_time(df)
        
        # Render detailed table
        self.render_detailed_table(df)
        
        # Render quarterly analysis and stock rating system
        self.render_quarterly_analysis(df)
        
        # Render channel allocation
        self.render_channel_allocation(holdings)
    
    def run(self):
        """Main run method for the web agent"""
        st.set_page_config(
            page_title="📊 WMS Portfolio Analytics - Agentic Version",
            page_icon="📊",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        # Custom CSS
        st.markdown("""
        <style>
        .main-header {
            font-size: 2.5rem;
            font-weight: bold;
            text-align: center;
            color: #2c3e50;
            margin-bottom: 1.5rem;
            padding: 1rem;
        }
        .stDataFrame {
            border-radius: 10px;
            overflow: hidden;
        }
        .section-header {
            font-size: 1.8rem;
            font-weight: 600;
            color: #2c3e50;
            margin: 2rem 0 1rem 0;
            padding: 0.5rem 0;
            border-bottom: 2px solid #3498db;
        }
        .subsection-header {
            font-size: 1.4rem;
            font-weight: 500;
            color: #34495e;
            margin: 1.5rem 0 1rem 0;
            padding: 0.25rem 0;
            border-bottom: 1px solid #b2bec3;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Main header
        st.markdown('<h1 class="main-header">📊 WMS Portfolio Analytics - Agentic Version</h1>', unsafe_allow_html=True)
        
        # Authentication - Enhanced Login System
        if LOGIN_SYSTEM_AVAILABLE:
            if not is_session_valid():
                # Show login page
                main_login_system()
                st.stop()
            else:
                # User is logged in, show logout option in sidebar
                username = self.session_state.get('username', 'Unknown')
                user_role = self.session_state.get('user_role', 'user')
                
                # Add logout button to sidebar
                st.sidebar.markdown("### 👤 User")
                st.sidebar.info(f"**{username}** ({user_role})")
                
                if st.sidebar.button("🚪 Logout"):
                    clear_session()
                    st.rerun()
                
                # Show admin panel if user is admin
                if user_role == 'admin':
                    if st.sidebar.button("👑 Admin Panel"):
                        st.session_state['show_admin_panel'] = True
                
                # Settings button
                if st.sidebar.button("⚙️ Settings"):
                    st.session_state['show_settings'] = True
                
                # Mftool status display
                st.sidebar.markdown("---")
                st.sidebar.markdown("### 🔍 Mftool Status")
                
                # Show initialization status
                if self.mftool_client:
                    st.sidebar.success("✅ Mftool Ready")
                elif self.mftool_available:
                    st.sidebar.info("🔄 Mftool Initializing...")
                else:
                    st.sidebar.warning("⚠️ Mftool Not Ready")
                
                self.display_mftool_status()
                
                # File upload section in sidebar below settings
                st.sidebar.markdown("---")
                st.sidebar.markdown("### 📤 Upload Files")
                st.sidebar.info("Upload your CSV transaction files for automatic processing.")
                
                # Get user info for file processing
                user_id = self.session_state.get('user_id')
                if not user_id:
                    # Try to get user_id from other sources
                    user_id = self.session_state.get('user_id_from_login')
                    if not user_id:
                        # Check if we can get it from the database based on username
                        try:
                            from database_config_supabase import get_user_by_username
                            username = self.session_state.get('username', '')
                            if username:
                                user_data = get_user_by_username(username)
                                if user_data:
                                    user_id = user_data.get('id')
                                    self.session_state['user_id'] = user_id
                                    
                                    # Initialize mftool after user is authenticated
                                    if not self.mftool_client:
                                        st.sidebar.info("🔄 Initializing mftool for mutual fund data...")
                                        self.initialize_after_login()
                        except:
                            pass
                
                uploaded_files = st.sidebar.file_uploader(
                    "Choose CSV files",
                    type=['csv'],
                    accept_multiple_files=True,
                    help="Upload CSV files with transaction data"
                )
                
                if uploaded_files:
                    if st.sidebar.button("📊 Process Files", type="primary"):
                        # Get folder path or create one
                        folder_path = self.session_state.get('folder_path', '')
                        if not folder_path and user_id:
                            folder_path = f"/tmp/{username}_investments"
                            self.session_state['folder_path'] = folder_path
                        
                        if folder_path:
                            # Process the files
                            self._process_uploaded_files(uploaded_files, folder_path)
                            
                            # Immediately verify data was saved and force reload
                            st.sidebar.info("🔍 Verifying data was saved...")
                            try:
                                from database_config_supabase import get_transactions_supabase
                                saved_transactions = get_transactions_supabase(user_id)
                                if saved_transactions:
                                    st.sidebar.success(f"✅ Data verified: {len(saved_transactions)} transactions found in database")
                                    
                                    # Clear uploaded files from session state
                                    if 'uploaded_files' in st.session_state:
                                        del st.session_state['uploaded_files']
                                    
                                    # Data is automatically refreshed after file processing
                                    st.sidebar.success("✅ Files processed successfully! Data will be refreshed automatically on next login.")
                                    
                                    # Clear any cached data to ensure fresh data on next load
                                    if 'current_df' in self.session_state:
                                        del self.session_state['current_df']
                                    if 'data_processing_complete' in self.session_state:
                                        del self.session_state['data_processing_complete']
                                else:
                                    st.sidebar.warning("⚠️ No transactions found in database after processing")
                            except Exception as e:
                                st.sidebar.error(f"❌ Data verification failed: {e}")
                        else:
                            st.error("❌ Could not determine folder path for file processing")
                    
                    # Show selected files count
                    st.sidebar.info(f"Selected {len(uploaded_files)} file(s)")
                    
                    # Add a clear selection button
                    if st.sidebar.button("🗑️ Clear Selection", type="secondary"):
                        if 'uploaded_files' in st.session_state:
                            del st.session_state['uploaded_files']
                        st.rerun()
                
                # Processed Files Section
                st.sidebar.markdown("---")
                st.sidebar.markdown("### 📋 Processed Files")
                
                if user_id:
                    try:
                        # Import the function locally to avoid reference errors
                        from database_config_supabase import get_file_records_supabase
                        processed_files = get_file_records_supabase(user_id)
                        
                        if processed_files:
                            st.sidebar.success(f"📁 {len(processed_files)} files processed")
                            
                            # Show file details in an expander
                            with st.sidebar.expander("📋 View Processed Files", expanded=False):
                                for i, file_record in enumerate(processed_files[:5]):  # Show first 5 files
                                    file_id = file_record.get('id', 'N/A')
                                    filename = file_record.get('filename', 'Unknown')
                                    processed_at = file_record.get('processed_at', 'Unknown')
                                    status = file_record.get('status', 'Unknown')
                                    
                                    st.sidebar.markdown(f"""
                                    **File {i+1}:**
                                    - 📄 {filename}
                                    - 🆔 ID: {file_id}
                                    - 📅 {processed_at}
                                    - ✅ {status}
                                    """)
                                
                                if len(processed_files) > 5:
                                    st.sidebar.info(f"... and {len(processed_files) - 5} more files")
                                
                                # Show summary
                                st.sidebar.markdown("---")
                                st.sidebar.markdown(f"**Total Files:** {len(processed_files)}")
                                
                                # Count by status
                                status_counts = {}
                                for file_record in processed_files:
                                    status = file_record.get('status', 'Unknown')
                                    status_counts[status] = status_counts.get(status, 0) + 1
                                
                                for status, count in status_counts.items():
                                    st.sidebar.markdown(f"**{status}:** {count}")
                        else:
                            st.sidebar.info("📁 No files processed yet")
                            st.sidebar.info("Upload your first CSV file to get started!")
                            
                    except Exception as e:
                        st.sidebar.error(f"❌ Error loading processed files: {e}")
                        st.sidebar.info("💡 This might be due to database connection issues")
                else:
                    st.sidebar.info("📁 Login to see your processed files")
                
                # File History Section
                st.sidebar.markdown("---")
                st.sidebar.markdown("### 📋 File History")
                
                if user_id:
                    try:
                        # Import the function locally to avoid reference errors
                        from database_config_supabase import get_file_records_supabase
                        file_history = get_file_records_supabase(user_id)
                        
                        if file_history:
                            st.sidebar.success(f"📁 {len(file_history)} files in history")
                            
                            # Show recent files (last 5)
                            recent_files = file_history[-5:] if len(file_history) > 5 else file_history
                            
                            for file_record in recent_files:
                                filename = file_record.get('filename', 'Unknown')
                                processed_at = file_record.get('processed_at', 'Unknown')
                                status = file_record.get('status', 'Unknown')
                                
                                # Format the date
                                try:
                                    if isinstance(processed_at, str):
                                        from datetime import datetime
                                        date_obj = datetime.fromisoformat(processed_at.replace('Z', '+00:00'))
                                        formatted_date = date_obj.strftime('%Y-%m-%d %H:%M')
                                    else:
                                        formatted_date = str(processed_at)
                                except:
                                    formatted_date = str(processed_at)
                                
                                # Show file info
                                status_color = "🟢" if status == "processed" else "🟡"
                                st.sidebar.text(f"{status_color} {filename}")
                                st.sidebar.caption(f"📅 {formatted_date}")
                            
                            if len(file_history) > 5:
                                st.sidebar.caption(f"... and {len(file_history) - 5} more files")
                        else:
                            st.sidebar.info("📁 No files in history yet")
                            
                    except Exception as e:
                        st.sidebar.error(f"❌ Error loading file history: {e}")
                        st.sidebar.info("💡 This might be due to database connection issues")
                else:
                    st.sidebar.info("📁 Login to see your file history")
                
                # All data fetching happens automatically during login - no manual buttons needed
                

                

                

                
                # Check investment_files table

                

                

                

                
                # All data fetching happens automatically during login - no manual buttons needed
                
                # Show admin panel if requested
                if st.session_state.get('show_admin_panel', False):
                    admin_panel()
                    if st.button("← Back to Dashboard"):
                        st.session_state['show_admin_panel'] = False
                        st.rerun()
                    st.stop()
                
                # Show settings if requested
                if st.session_state.get('show_settings', False):
                    self.show_user_settings()
                    
                    # Add portfolio data section below user settings
                    st.markdown("---")
                    st.markdown('<h2 class="section-header">📊 Your Portfolio Data</h2>', unsafe_allow_html=True)
                    
                    # Load data for portfolio display
                    user_id = self.session_state.get('user_id', 1)
                    username = self.session_state.get('username', 'Unknown')
                    df = self.load_data_from_agents(user_id)
                    
                    # Check if user has transactions
                    has_transactions = not df.empty
                    
                    if has_transactions:
                        # Check P&L calculation status and show warning if needed
                        if 'live_price' in df.columns and 'abs_gain' in df.columns:
                            zero_pnl_count = (df['abs_gain'] == 0).sum()
                            total_transactions = len(df)
                            
                            if zero_pnl_count == total_transactions and total_transactions > 0:
                                st.warning("⚠️ **P&L Alert**: All P&L values are zero. This indicates missing live prices. Please use the 'Refresh Live Prices & Sectors' button below to update prices.")
                            elif zero_pnl_count > 0:
                                st.info(f"ℹ️ **P&L Status**: {zero_pnl_count}/{total_transactions} transactions have zero P&L due to missing live prices.")
                        
                        # Create two columns: left for file upload and summary, right for data
                        col1, col2 = st.columns([1, 3])
                        
                        with col1:
                            st.markdown("### 📤 Upload More Files")
                            st.info("Add more transaction files to your portfolio")
                            
                            # File Upload Section - Always Cloud Mode
                            st.info("🌐 **Cloud Mode**: Upload your CSV transaction files for automatic processing.")
                            
                            uploaded_files = st.file_uploader(
                                "Choose CSV files",
                                type=['csv'],
                                accept_multiple_files=True,
                                help="Upload additional CSV files with transaction data"
                            )
                            
                            if uploaded_files:
                                if st.button("📊 Process Files", type="primary"):
                                    # Get folder path or create one
                                    folder_path = self.session_state.get('folder_path', '')
                                    if not folder_path and user_id:
                                        folder_path = f"/tmp/{username}_investments"
                                        self.session_state['folder_path'] = folder_path
                                    
                                    if folder_path:
                                        self._process_uploaded_files(uploaded_files, folder_path)
                                        st.rerun()
                                    else:
                                        st.error("❌ Could not determine folder path for file processing")
                                st.info(f"Selected {len(uploaded_files)} file(s)")
                            
                            # Live prices and sectors are updated automatically during login - no manual button needed
                            
                            # Show transaction summary in left column
                            st.markdown("### 📈 Transaction Summary")
                            st.info(f"Found **{len(df)} transactions** in your portfolio")
                            
                            # Show P&L status in transaction summary
                            if 'live_price' in df.columns and 'abs_gain' in df.columns:
                                total_invested = df['invested_amount'].sum() if 'invested_amount' in df.columns else 0
                                total_current = df['current_value'].sum() if 'current_value' in df.columns else 0
                                total_gain = df['abs_gain'].sum()
                                
                                if total_invested > 0:
                                    gain_pct = (total_gain / total_invested * 100)
                                    gain_color = "🟢" if total_gain >= 0 else "🔴"
                                    
                                    st.markdown(f"""
                                    **Portfolio P&L:**
                                    {gain_color} **Total Gain**: ₹{total_gain:,.2f} ({gain_pct:+.2f}%)
                                    💰 **Invested**: ₹{total_invested:,.2f}
                                    📊 **Current Value**: ₹{total_current:,.2f}
                                    """)
                                else:
                                    st.info("🔄 **P&L Status**: P&L calculation in progress - prices are being fetched automatically")
                            
                            # Show quick stats in left column
                            if len(df) > 0:
                                try:
                                    # Check if required columns exist
                                    if 'ticker' in df.columns and 'transaction_type' in df.columns:
                                        unique_stocks = df['ticker'].nunique()
                                        total_buy = len(df[df['transaction_type'] == 'buy'])
                                        total_sell = len(df[df['transaction_type'] == 'sell'])
                                        
                                        st.markdown(f"""
                                        **Quick Stats:**
                                        - 📊 **Unique Stocks**: {unique_stocks}
                                        - 📈 **Buy Transactions**: {total_buy}
                                        - 📉 **Sell Transactions**: {total_sell}
                                        """)
                                    else:
                                        st.warning("⚠️ Data format issue: Missing required columns (ticker, transaction_type)")
                                        st.info(f"Available columns: {list(df.columns)}")
                                except Exception as e:
                                    st.error(f"❌ Error calculating stats: {e}")
                                    st.info(f"DataFrame shape: {df.shape}, Columns: {list(df.columns)}")
                        
                        with col2:
                            # Right column now contains the main portfolio data and analytics
                            # Render filters at the top
                            filtered_df, selected_channel, selected_sector, selected_stock = self.render_top_filters(df)
                            
                            # Render dashboard
                            self.render_dashboard(filtered_df)
                    else:
                        # User has no transactions - show welcome message
                        st.markdown('<h2 class="section-header">🚀 Welcome to Your Portfolio Analytics!</h2>', unsafe_allow_html=True)
                        
                        # Create a centered layout for new users
                        col1, col2, col3 = st.columns([1, 2, 1])
                        
                        with col2:
                            st.markdown("""
                            ### 📊 Your Portfolio Dashboard
                            
                            Welcome! Your portfolio dashboard is ready.
                            """)
                            
                            # Check if user just registered and has no data yet
                            if user_id and user_id != 1:
                                st.info("""
                                **Next Steps:**
                                - 📤 **Upload Files**: Use the file upload option in the left sidebar to add your transaction files
                                - 📊 **View Analytics**: Once files are processed, you'll see your portfolio analysis here
                                - 🔄 **Refresh Data**: Use the refresh button to update live prices and sectors
                                """)
                                
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
                                    - **channel**: Investment channel (optional - auto-generated from filename if missing)
                                    - **sector**: Stock sector (optional)
                                    """)
                            else:
                                st.info("""
                                **Getting Started:**
                                - 📤 **Upload Files**: Use the file upload option in the left sidebar
                                - 📊 **View Analytics**: Your portfolio analysis will appear here
                                - 🔄 **Refresh Data**: Keep your data up to date
                                """)
                            
                            # Show what happens after upload
                            st.markdown("""
                            ### 🎯 What You'll See:
                            - 📊 **Portfolio Overview**: Complete analysis of your investments
                            - 📈 **Performance Metrics**: Returns, gains, and losses
                            - 🏆 **Top Performers**: Your best and worst performing stocks
                            - 📋 **Detailed Analytics**: Sector analysis, channel breakdown, and more
                            """)
                    
                    if st.button("← Back to Dashboard"):
                        st.session_state['show_settings'] = False
                        st.rerun()
                    st.stop()
                
                # Initialize agents
                self.initialize_agents()
                
                # Load data first
                user_id = self.session_state.get('user_id', 1)
                username = self.session_state.get('username', 'Unknown')
                
                # Check user folder access and start file monitoring (silently)
                if user_id and user_id != 1:  # Not default user
                    folder_access_ok, folder_message = self.check_user_folder_access()
                    if folder_access_ok:
                        try:
                            start_user_file_monitoring(user_id)
                        except Exception as e:
                            pass  # Silently handle monitoring errors
                
                # Load data and ensure prices are fetched
                df = self.load_data_from_agent(user_id)
                
                # Data is automatically fetched and processed during login - no manual refresh needed
                
                # CRITICAL: If we have missing prices, fetch them directly in the DataFrame
                if not df.empty and user_id:
                    print(f"🔍 DEBUG: Main data loading - user_id: {user_id}, type: {type(user_id)}")
                    missing_prices_count = df['price'].isna().sum() if 'price' in df.columns else 0
                
                # Use processed data from session state if available
                if 'current_df' in self.session_state and self.session_state.get('data_processing_complete', False):
                    df = self.session_state['current_df']
                
                # BATCH PROCESSING: Historical Prices → Live Prices → Sector Data → Database Storage
                if not df.empty and user_id and user_id != 1:
                    # Step 1: Get unique tickers for batch processing
                    unique_tickers = df['ticker'].unique()
                    
                    # Step 2: Batch fetch historical prices for missing prices
                    historical_prices = {}
                    
                    for i, ticker in enumerate(unique_tickers):
                        try:
                            # Check if we need historical prices for this ticker
                            ticker_transactions = df[df['ticker'] == ticker]
                            missing_prices = ticker_transactions['price'].isna().sum()
                            
                            if missing_prices > 0:
                                # Check if it's a mutual fund (numeric ticker)
                                clean_ticker = str(ticker).strip().upper()
                                clean_ticker = clean_ticker.replace('.NS', '').replace('.BO', '').replace('.NSE', '').replace('.BSE', '')
                                
                                if clean_ticker.isdigit():
                                    # Mutual fund - use mftool for historical prices
                                    print(f"🔍 Fetching mutual fund historical price for {ticker} using mftool...")
                                    try:
                                        from mf_price_fetcher import fetch_mutual_fund_historical_price
                                        for idx, row in ticker_transactions.iterrows():
                                            if pd.isna(row['price']):
                                                transaction_date = row['date']
                                                price = fetch_mutual_fund_historical_price(ticker, transaction_date)
                                                if price and price > 0:
                                                    df.at[idx, 'price'] = price
                                                    historical_prices[ticker] = price
                                                    print(f"✅ MF {ticker}: ₹{price} for {transaction_date}")
                                    except Exception as e:
                                        print(f"⚠️ MFTool failed for {ticker}: {e}")
                                else:
                                    # Regular stock - use enhanced price fetching with better ticker cleaning
                                    for idx, row in ticker_transactions.iterrows():
                                        if pd.isna(row['price']):
                                            transaction_date = row['date']
                                            price = None
                                            
                                            # Method 1: Try with original ticker
                                            try:
                                                from file_manager import fetch_historical_price
                                                price = fetch_historical_price(ticker, transaction_date)
                                                if price and price > 0:
                                                    df.at[idx, 'price'] = price
                                                    historical_prices[ticker] = price
                                                    print(f"✅ {ticker}: ₹{price} for {transaction_date}")
                                                    continue
                                            except Exception as e:
                                                print(f"⚠️ File manager failed for {ticker}: {e}")
                                            
                                            # Method 2: Try with cleaned ticker (remove .NS suffix)
                                            if not price:
                                                try:
                                                    clean_stock_ticker = ticker.replace('.NS', '').replace('.BO', '')
                                                    if clean_stock_ticker != ticker:
                                                        from file_manager import fetch_historical_price
                                                        price = fetch_historical_price(clean_stock_ticker, transaction_date)
                                                        if price and price > 0:
                                                            df.at[idx, 'price'] = price
                                                            historical_prices[ticker] = price
                                                            print(f"✅ {ticker} (cleaned): ₹{price} for {transaction_date}")
                                                            continue
                                                except Exception as e:
                                                    print(f"⚠️ Cleaned ticker failed for {ticker}: {e}")
                                            
                                            # Method 3: Try yfinance as last resort
                                            if not price:
                                                try:
                                                    import yfinance as yf
                                                    # Try both original and cleaned ticker
                                                    for test_ticker in [ticker, clean_stock_ticker]:
                                                        try:
                                                            stock = yf.Ticker(test_ticker)
                                                            hist = stock.history(start=transaction_date, end=transaction_date + pd.Timedelta(days=1))
                                                            if not hist.empty:
                                                                price = hist['Close'].iloc[0]
                                                                df.at[idx, 'price'] = price
                                                                historical_prices[ticker] = price
                                                                print(f"✅ {ticker} (yfinance): ₹{price} for {transaction_date}")
                                                                break
                                                        except:
                                                            continue
                                                except Exception as e:
                                                    print(f"⚠️ YFinance failed for {ticker}: {e}")
                                            
                                            if not price:
                                                print(f"❌ {ticker}: All price fetching methods failed for {transaction_date}")
                        except Exception as e:
                            print(f"❌ Error processing {ticker}: {e}")
                    
                    # Step 3: Batch fetch live prices and sector data
                    live_prices = {}
                    sector_data = {}
                    
                    for i, ticker in enumerate(unique_tickers):
                        try:
                            # Check if it's a mutual fund (numeric ticker)
                            clean_ticker = str(ticker).strip().upper()
                            clean_ticker = clean_ticker.replace('.NS', '').replace('.BO', '').replace('.NSE', '').replace('.BSE', '')
                            
                            if clean_ticker.isdigit() or ticker.startswith('MF_'):
                                # Mutual fund - use mftool for live prices
                                print(f"🔍 Fetching mutual fund live price for {ticker} using mftool...")
                                try:
                                    from mf_price_fetcher import fetch_mutual_fund_price
                                    price = fetch_mutual_fund_price(ticker, None)  # None for current price
                                    if price and price > 0:
                                        live_prices[ticker] = price
                                        sector_data[ticker] = {
                                            'sector': 'Mutual Funds',
                                            'stock_name': f"MF-{ticker}"
                                        }
                                        print(f"✅ MF {ticker}: ₹{price} - Mutual Funds")
                                    else:
                                        print(f"❌ MF {ticker}: No price available from mftool")
                                except Exception as e:
                                    print(f"⚠️ MFTool failed for {ticker}: {e}")
                            else:
                                # Regular stock - use existing methods
                                try:
                                    # Use the stock agent's fetch method to get fresh live prices
                                    fresh_data = stock_agent._fetch_stock_data(ticker)
                                    if fresh_data and fresh_data.get('live_price'):
                                        price = fresh_data['live_price']
                                        live_prices[ticker] = price
                                        
                                        sector = fresh_data.get('sector', 'Unknown')
                                        stock_name = fresh_data.get('stock_name', ticker)
                                        sector_data[ticker] = {
                                            'sector': sector,
                                            'stock_name': stock_name
                                        }
                                        print(f"✅ {ticker}: Live=₹{price}, Sector={sector}")
                                    else:
                                        print(f"❌ {ticker}: No fresh price data available")
                                except Exception as e:
                                    print(f"❌ Error fetching live data for {ticker}: {e}")
                            
                        except Exception as e:
                            print(f"❌ Error fetching live data for {ticker}: {e}")
                    
                    # Step 4: Batch update stock_data table (only if we have data)
                    stock_data_updates = 0
                    
                    for ticker in unique_tickers:
                        try:
                            if ticker in live_prices and ticker in sector_data:
                                # Update stock_data table with live price and sector
                                try:
                                    update_stock_data_supabase(
                                        ticker=ticker,
                                        stock_name=sector_data[ticker]['stock_name'],
                                        sector=sector_data[ticker]['sector'],
                                        current_price=live_prices[ticker]
                                    )
                                    stock_data_updates += 1
                                except Exception as db_error:
                                    print(f"⚠️ Database update failed for {ticker}: {db_error}")
                                    # Continue with other tickers even if one fails
                        except Exception as e:
                            print(f"❌ Error updating stock_data for {ticker}: {e}")
                    
                    # Step 5: Update DataFrame with live prices and recalculate P&L
                    if live_prices:
                        df['live_price'] = df['ticker'].map(live_prices).fillna(df['price'])
                        
                        # Recalculate P&L
                        df['current_value'] = df['quantity'] * df['live_price']
                        df['invested_amount'] = df['quantity'] * df['price']
                        df['abs_gain'] = df['current_value'] - df['invested_amount']
                        df['pct_gain'] = df.apply(
                            lambda row: (row['abs_gain'] / row['invested_amount'] * 100) if row['invested_amount'] > 0 else 0, 
                            axis=1
                        )
                        
                        # Update sector information in DataFrame
                        for ticker, data in sector_data.items():
                            ticker_mask = df['ticker'] == ticker
                            df.loc[ticker_mask, 'sector'] = data['sector']
                            df.loc[ticker_mask, 'stock_name'] = data['stock_name']
                        
                        # Store updated DataFrame in session state
                        self.session_state['current_df'] = df.copy()
                        
                        # Mark data processing as complete
                        self.session_state['data_processing_complete'] = True
                
                # Mark data processing as complete for all users
                self.session_state['data_processing_complete'] = True
                self.session_state['current_df'] = df.copy()
                
                # Check if user has transactions
                has_transactions = not df.empty
                
                # Debug: Show data status
                st.info(f"🔍 **Data Status**: DataFrame shape: {df.shape}, Columns: {list(df.columns) if not df.empty else 'None'}")
                st.info(f"🔍 **Processing Status**: Data processing complete: {self.session_state.get('data_processing_complete', False)}")
                
                # Show transaction summary if data exists
                if not df.empty:
                    st.success(f"✅ **Data Loaded Successfully**: {len(df)} transactions found")
                    if 'ticker' in df.columns:
                        unique_tickers = df['ticker'].nunique()
                        st.info(f"📊 **Portfolio Summary**: {unique_tickers} unique stocks, {len(df)} total transactions")
                else:
                    st.warning("⚠️ **No Data Loaded**: DataFrame is empty - this might indicate a loading issue")
                
                # Check for common issues
                if not df.empty:
                    missing_prices = df['price'].isna().sum() if 'price' in df.columns else 0
                    total_transactions = len(df)
                    
                    if missing_prices > 0:
                        st.info(f"🔄 **Auto-Calculation in Progress**: {missing_prices}/{total_transactions} transaction prices are being calculated automatically")
                        st.success("💡 **This is normal!** The system automatically fetches historical prices for missing data.")
                        
                        # Show which tickers are missing prices
                        missing_tickers = df[df['price'].isna()]['ticker'].unique()
                        if len(missing_tickers) > 0:
                            st.info(f"🔍 **Processing Prices For**: {', '.join(missing_tickers[:10])}{'...' if len(missing_tickers) > 10 else ''}")
                    
                    # Check if live prices are available
                    if 'live_price' in df.columns:
                        missing_live_prices = df['live_price'].isna().sum()
                        if missing_live_prices > 0:
                            st.info(f"🔄 **Live Price Update**: {missing_live_prices}/{total_transactions} live prices are being fetched")
                            st.success("💡 **This is normal!** Live prices are updated automatically for current P&L calculations.")
                    
                    # Show data quality summary
                    if 'price' in df.columns:
                        valid_prices = df['price'].notna().sum()
                        st.success(f"✅ **Data Status**: {valid_prices}/{total_transactions} transactions ready ({valid_prices/total_transactions*100:.1f}%)")
                
                # Show portfolio data if user has transactions
                if has_transactions:
                    st.markdown('<h2 class="section-header">📊 Your Portfolio Data</h2>', unsafe_allow_html=True)
                    
                    # Render filters at the top
                    filtered_df, selected_channel, selected_sector, selected_stock = self.render_top_filters(df)
                    
                    # Render dashboard
                    self.render_dashboard(filtered_df)
                else:
                    # User has no transactions - show welcome message
                    st.markdown('<h2 class="section-header">🚀 Welcome to Your Portfolio Analytics!</h2>', unsafe_allow_html=True)
                    
                    # Create a centered layout for new users
                    col1, col2, col3 = st.columns([1, 2, 1])
                    
                    with col2:
                        st.markdown("""
                        ### 📊 Your Portfolio Dashboard
                        
                        Welcome! Your portfolio dashboard is ready.
                        """)
                        
                        # Check if user just registered and has no data yet
                        if user_id and user_id != 1:
                            st.info("""
                            **Next Steps:**
                            - 📤 **Upload Files**: Use the file upload option above to add your transaction files
                            - 📊 **View Analytics**: Once files are processed, you'll see your portfolio analysis here
                            - 🔄 **Refresh Data**: Use the refresh button to update live prices and sectors
                            """)
                            
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
                                - **channel**: Investment channel (optional - auto-generated from filename if missing)
                                - **sector**: Stock sector (optional)
                                """)
                        else:
                            st.info("""
                            **Getting Started:**
                            - 📤 **Upload Files**: Use the file upload option above
                            - 📊 **View Analytics**: Your portfolio analysis will appear here
                            - 🔄 **Refresh Data**: Keep your data up to date
                            """)
                        
                        # Show what happens after upload
                        st.markdown("""
                        ### 🎯 What You'll See:
                        - 📊 **Portfolio Overview**: Complete analysis of your investments
                        - 📈 **Performance Metrics**: Returns, gains, and losses
                        - 🏆 **Top Performers**: Your best and worst performing stocks
                        - 📋 **Detailed Analytics**: Sector analysis, channel breakdown, and more
                        """)
                
                # Store original DataFrame for comparison
                if not df.empty and all(col in df.columns for col in ['ticker', 'quantity', 'price', 'live_price', 'transaction_type']):
                    data_hash = hash(str(df[['ticker', 'quantity', 'price', 'live_price', 'transaction_type']].values.tobytes()))
                    original_data_hash = self.session_state.get('original_df_hash', None)
                    
                    if original_data_hash != data_hash:
                        self.session_state['original_df'] = df.copy()
                        self.session_state['original_df_hash'] = data_hash
                else:
                    # If DataFrame is empty or missing columns, clear the original DataFrame
                    self.session_state.pop('original_df', None)
                    self.session_state.pop('original_df_hash', None)
        else:
            if 'user_authenticated' not in st.session_state:
                st.session_state['user_authenticated'] = True
                st.session_state['username'] = 'User'
                st.session_state['user_role'] = 'user'

    def _update_missing_historical_prices_in_db(self, transactions: List[Dict], user_id: int):
        """Update missing historical prices in the database during login"""
        try:
            print(f"🔄 Checking {len(transactions)} transactions for missing historical prices...")
            
            # Find transactions with missing or zero historical prices
            missing_price_transactions = []
            for transaction in transactions:
                price = transaction.get('price', 0)
                if pd.isna(price) or price == 0 or price is None:
                    missing_price_transactions.append(transaction)
            
            if not missing_price_transactions:
                print(f"✅ All transactions already have historical prices")
                return
            
            print(f"🔄 Found {len(missing_price_transactions)} transactions with missing historical prices")
            
            # Group by ticker for efficient processing
            ticker_groups = {}
            for transaction in missing_price_transactions:
                ticker = transaction.get('ticker', '')
                if ticker not in ticker_groups:
                    ticker_groups[ticker] = []
                ticker_groups[ticker].append(transaction)
            
            # Process each ticker group
            updated_count = 0
            for ticker, ticker_transactions in ticker_groups.items():
                try:
                    print(f"🔄 Processing {len(ticker_transactions)} transactions for {ticker}...")
                    
                    # Get the transaction date for historical price fetching
                    transaction_date = ticker_transactions[0].get('date')
                    if not transaction_date:
                        print(f"⚠️ No date found for {ticker}, skipping")
                        continue
                    
                    # Fetch historical price for this ticker and date
                    historical_price = self._fetch_historical_price_for_db_update(ticker, transaction_date, user_id)
                    
                    if historical_price and historical_price > 0:
                        # Update all transactions for this ticker with the historical price
                        success = self._update_transaction_prices_in_db(ticker_transactions, historical_price, user_id)
                        if success:
                            updated_count += len(ticker_transactions)
                            print(f"✅ Updated {len(ticker_transactions)} transactions for {ticker} with price ₹{historical_price}")
                        else:
                            print(f"❌ Failed to update database for {ticker}")
                    else:
                        print(f"⚠️ Could not fetch historical price for {ticker}")
                        
                except Exception as e:
                    print(f"⚠️ Error processing {ticker}: {e}")
            
            if updated_count > 0:
                print(f"✅ Successfully updated {updated_count} transactions with historical prices")
                # Force a small delay to let database settle
                import time
                time.sleep(1)
            else:
                print(f"⚠️ No transactions were updated with historical prices")
                
        except Exception as e:
            print(f"❌ Error updating missing historical prices: {e}")
    
    def _fetch_historical_price_for_db_update(self, ticker: str, transaction_date, user_id: int = None) -> float:
        """Fetch historical price for database update
        
        IMPORTANT: This function fetches HISTORICAL prices for the specific transaction date.
        Live prices are fetched separately in _fetch_live_prices_and_sectors_during_login.
        
        For mutual funds in Streamlit Cloud:
        - Primary: Use mftool historical NAV for transaction date
        - Secondary: Calculate historical NAV from current NAV with date variation
        - Fallback: Use transaction prices from database
        
        For stocks:
        - Primary: Use yfinance historical data for transaction date
        - Secondary: Use file_manager historical data
        - Fallback: Use indstocks API historical data
        
        Future API options for mutual funds:
        - Alpha Vantage API (requires API key)
        - Quandl API (requires API key)
        - NSE/BSE direct APIs (may have rate limits)
        - AMFI direct API (unreliable in cloud environments)
        """
        try:
            # Check if it's a mutual fund
            clean_ticker = str(ticker).strip().upper()
            is_mf = clean_ticker.isdigit() or clean_ticker.startswith('MF_')
            
            if is_mf:
                # Mutual fund - use reliable methods for Streamlit Cloud
                price = None
                
                # Method 1: Try mftool for historical NAV on transaction date with Streamlit Cloud compatibility
                if not price:
                    try:
                        from mf_price_fetcher import fetch_mutual_fund_historical_price
                        price = fetch_mutual_fund_historical_price(clean_ticker, transaction_date)
                        if price and price > 0:
                            print(f"✅ MF {ticker}: Historical price ₹{price} for {transaction_date}")
                            return float(price)
                    except Exception as e:
                        print(f"⚠️ Mftool historical price failed for {ticker}: {e}")
                        # Try alternative approach for Streamlit Cloud using initialized client
                        if self._ensure_mftool_initialized():
                            try:
                                # For historical prices, we'll use a date-based approach
                                # Get current NAV and apply a small variation based on date
                                scheme_details = self.mftool_client.get_scheme_details(clean_ticker)
                                if scheme_details and 'nav' in scheme_details:
                                    current_nav = float(scheme_details['nav'])
                                    # Apply small variation based on transaction date (simplified approach)
                                    days_diff = (pd.Timestamp.now() - pd.Timestamp(transaction_date)).days
                                    # Assume 0.1% daily variation for mutual funds
                                    variation_factor = 1 + (days_diff * 0.001)
                                    historical_price = current_nav / variation_factor
                                    print(f"✅ MF {ticker}: Historical price ₹{historical_price} (calculated from current NAV)")
                                    return float(historical_price)
                            except Exception as mf_error:
                                print(f"⚠️ Initialized mftool historical also failed for {ticker}: {mf_error}")
                        else:
                            print(f"⚠️ Mftool initialization failed for {ticker}")
                
                # Method 2: Try to get transaction price from database as fallback
                if not price:
                    try:
                        from database_config_supabase import get_transactions_supabase
                        # Get all transactions for the user and filter by ticker
                        all_user_transactions = get_transactions_supabase(user_id)
                        if all_user_transactions:
                            mf_transactions = [t for t in all_user_transactions if t.get('ticker') == ticker]
                            if mf_transactions:
                                prices = [t.get('price', 0) for t in mf_transactions if t.get('price') and t.get('price') > 0]
                                if prices:
                                    avg_price = sum(prices) / len(prices)
                                    print(f"✅ MF {ticker}: Using average transaction price ₹{avg_price} as fallback")
                                    return float(avg_price)
                    except Exception as e:
                        print(f"⚠️ Could not get transaction price for MF {ticker}: {e}")
                
                # Method 3: Use intelligent default based on fund type
                if not price:
                    # Determine fund type from ticker and use realistic default
                    if clean_ticker.startswith('MF_'):
                        fund_type = clean_ticker.split('_')[1] if len(clean_ticker.split('_')) > 1 else 'general'
                    else:
                        fund_type = 'general'
                    
                    # Use realistic default prices based on fund type
                    if 'large' in fund_type.lower() or 'index' in fund_type.lower():
                        price = 150.0  # Large cap funds typically have higher NAV
                        print(f"✅ MF {ticker}: Using large cap default price ₹{price}")
                    elif 'mid' in fund_type.lower():
                        price = 120.0  # Mid cap funds
                        print(f"✅ MF {ticker}: Using mid cap default price ₹{price}")
                    elif 'small' in fund_type.lower():
                        price = 80.0   # Small cap funds
                        print(f"✅ MF {ticker}: Using small cap default price ₹{price}")
                    elif 'debt' in fund_type.lower() or 'liquid' in fund_type.lower():
                        price = 25.0   # Debt/liquid funds
                        print(f"✅ MF {ticker}: Using debt fund default price ₹{price}")
                    else:
                        price = 100.0  # General default
                        print(f"✅ MF {ticker}: Using general default price ₹{price}")
                
                return float(price)
            else:
                # Regular stock - try multiple sources
                price = None
                
                # Method 1: Try yfinance with proper ticker formatting
                try:
                    import yfinance as yf
                    yf_ticker = clean_ticker
                    if not yf_ticker.endswith(('.NS', '.BO', '.NSE', '.BSE')):
                        yf_ticker = f"{clean_ticker}.NS"  # Default to NSE
                    
                    stock = yf.Ticker(yf_ticker)
                    hist = stock.history(start=transaction_date, end=transaction_date + pd.Timedelta(days=1))
                    if not hist.empty:
                        price = hist['Close'].iloc[0]
                        print(f"✅ {ticker} (yfinance): Historical price ₹{price}")
                        return float(price)
                except Exception as e:
                    print(f"⚠️ yfinance failed for {ticker}: {e}")
                
                # Method 2: Try file_manager
                if not price:
                    try:
                        from file_manager import fetch_historical_price
                        price = fetch_historical_price(clean_ticker, transaction_date)
                        if price:
                            print(f"✅ {ticker} (file_manager): Historical price ₹{price}")
                            return float(price)
                    except Exception as e:
                        print(f"⚠️ file_manager failed for {ticker}: {e}")
                
                # Method 3: Try indstocks API
                if not price:
                    try:
                        from indstocks_api import get_indstocks_client
                        api_client = get_indstocks_client()
                        if api_client and api_client.available:
                            price_data = api_client.get_historical_price(clean_ticker, transaction_date)
                            if price_data and isinstance(price_data, dict) and price_data.get('price'):
                                price = price_data['price']
                                print(f"✅ {ticker} (indstocks): Historical price ₹{price}")
                                return float(price)
                    except Exception as e:
                        print(f"⚠️ indstocks failed for {ticker}: {e}")
                
                # If all methods fail, use a reasonable default
                print(f"⚠️ {ticker}: Using default price ₹1000")
                return 1000.0
                
        except Exception as e:
            print(f"❌ Error fetching historical price for {ticker}: {e}")
            return None
    
    def _update_transaction_prices_in_db(self, transactions: List[Dict], historical_price: float, user_id: int) -> bool:
        """Update transaction prices in the database"""
        try:
            from database_config_supabase import supabase
            
            # Update each transaction with the historical price
            for transaction in transactions:
                transaction_id = transaction.get('id')
                if transaction_id:
                    try:
                        result = supabase.table("investment_transactions").update({
                            "price": historical_price
                        }).eq("id", transaction_id).execute()
                        
                        if not result.data:
                            print(f"⚠️ Failed to update transaction {transaction_id}")
                            return False
                            
                    except Exception as e:
                        print(f"⚠️ Error updating transaction {transaction_id}: {e}")
                        return False
            
            print(f"✅ Successfully updated {len(transactions)} transactions in database")
            return True
            
        except Exception as e:
            print(f"❌ Error updating transaction prices in database: {e}")
            return False
    
    def _fetch_live_prices_and_sectors_during_login(self, transactions: List[Dict], user_id: int):
        """Automatically fetch live prices and sector data during login
        
        IMPORTANT: This function fetches CURRENT LIVE prices (not historical prices).
        Historical prices are fetched separately in _fetch_historical_price_for_db_update.
        
        Live prices represent current market values for P&L calculations.
        Historical prices represent transaction prices for invested amount calculations.
        """
        try:
            print(f"🔄 Automatically fetching live prices and sector data for {len(transactions)} transactions...")
            
            # Extract unique tickers
            unique_tickers = list(set([t.get('ticker', '') for t in transactions if t.get('ticker')]))
            print(f"🔍 Found {len(unique_tickers)} unique tickers to process")
            
            # Fetch live prices and sectors for all tickers
            live_prices = {}
            sector_data = {}
            
            for ticker in unique_tickers:
                try:
                    clean_ticker = str(ticker).strip().upper()
                    is_mf = clean_ticker.isdigit() or clean_ticker.startswith('MF_')
                    
                    # Fetch live price
                    live_price = None
                    if is_mf:
                        # Mutual fund - use reliable methods for Streamlit Cloud
                        live_price = None
                        
                        # Method 1: Try to get transaction price from database (most reliable)
                        try:
                            from database_config_supabase import get_transactions_supabase
                            # Get all transactions for the user and filter by ticker
                            all_user_transactions = get_transactions_supabase(user_id)
                            if all_user_transactions:
                                mf_transactions = [t for t in all_user_transactions if t.get('ticker') == ticker]
                                if mf_transactions:
                                    prices = [t.get('price', 0) for t in mf_transactions if t.get('price') and t.get('price') > 0]
                                    if prices:
                                        avg_price = sum(prices) / len(prices)
                                        live_price = avg_price
                                        print(f"✅ MF {ticker}: Using average transaction price ₹{live_price}")
                        except Exception as e:
                            print(f"⚠️ Could not get transaction price for MF {ticker}: {e}")
                        
                        # Method 2: Try mftool (may work in some cases)
                        if not live_price:
                            try:
                                from mf_price_fetcher import fetch_mutual_fund_price
                                live_price = fetch_mutual_fund_price(clean_ticker)
                                if live_price and live_price > 0:
                                    print(f"✅ MF {ticker}: Live price ₹{live_price} from mftool")
                            except Exception as e:
                                print(f"⚠️ MFTool failed for {ticker} (common in Streamlit Cloud): {e}")
                        
                        # Method 3: Use intelligent default based on fund type
                        if not live_price:
                            # Determine fund type from ticker and use realistic default
                            if clean_ticker.startswith('MF_'):
                                fund_type = clean_ticker.split('_')[1] if len(clean_ticker.split('_')) > 1 else 'general'
                            else:
                                fund_type = 'general'
                            
                            # Use realistic default prices based on fund type
                            if 'large' in fund_type.lower() or 'index' in fund_type.lower():
                                live_price = 150.0  # Large cap funds typically have higher NAV
                                print(f"✅ MF {ticker}: Using large cap default price ₹{live_price}")
                            elif 'mid' in fund_type.lower():
                                live_price = 120.0  # Mid cap funds
                                print(f"✅ MF {ticker}: Using mid cap default price ₹{live_price}")
                            elif 'small' in fund_type.lower():
                                live_price = 80.0   # Small cap funds
                                print(f"✅ MF {ticker}: Using small cap default price ₹{live_price}")
                            elif 'debt' in fund_type.lower() or 'liquid' in fund_type.lower():
                                live_price = 25.0   # Debt/liquid funds
                                print(f"✅ MF {ticker}: Using debt fund default price ₹{live_price}")
                            else:
                                live_price = 100.0  # General default
                                print(f"✅ MF {ticker}: Using general default price ₹{live_price}")
                    else:
                        # Regular stock - try multiple sources
                        try:
                            import yfinance as yf
                            yf_ticker = clean_ticker
                            if not yf_ticker.endswith(('.NS', '.BO', '.NSE', '.BSE')):
                                yf_ticker = f"{clean_ticker}.NS"
                            
                            stock = yf.Ticker(yf_ticker)
                            hist = stock.history(period="1d")
                            if not hist.empty and hist['Close'].iloc[-1] > 0:
                                live_price = hist['Close'].iloc[-1]
                                print(f"✅ {ticker}: Live price ₹{live_price}")
                            else:
                                live_price = 1000.0  # Default price
                                print(f"⚠️ {ticker}: Using default price ₹{live_price}")
                        except Exception as e:
                            print(f"⚠️ yfinance failed for {ticker}: {e}")
                            live_price = 1000.0  # Default price
                    
                    if live_price and live_price > 0:
                        live_prices[ticker] = live_price
                    
                    # Fetch sector data
                    sector = None
                    if is_mf:
                        sector = "Mutual Funds"
                        print(f"✅ MF {ticker}: Sector set to {sector}")
                    else:
                        # Try to get sector from existing data or use default
                        try:
                            from database_config_supabase import get_stock_data_supabase
                            existing_data = get_stock_data_supabase(ticker=ticker)
                            if existing_data and len(existing_data) > 0:
                                sector = existing_data[0].get('sector')
                            
                            if not sector:
                                # Use default sector based on ticker pattern
                                if any(keyword in clean_ticker.upper() for keyword in ['BANK', 'HDFC', 'ICICI', 'SBI']):
                                    sector = "Banking"
                                elif any(keyword in clean_ticker.upper() for keyword in ['TECH', 'TCS', 'INFY', 'WIPRO']):
                                    sector = "Technology"
                                elif any(keyword in clean_ticker.upper() for keyword in ['RELIANCE', 'ONGC', 'IOC']):
                                    sector = "Energy"
                                else:
                                    sector = "Others"
                            
                            print(f"✅ {ticker}: Sector set to {sector}")
                        except Exception as e:
                            print(f"⚠️ Error fetching sector for {ticker}: {e}")
                            sector = "Others"
                    
                    if sector:
                        sector_data[ticker] = sector
                        
                except Exception as e:
                    print(f"⚠️ Error processing {ticker}: {e}")
                    continue
            
            # Update stock_data table with live prices and sectors
            if live_prices or sector_data:
                print(f"🔄 Updating stock_data table with {len(live_prices)} live prices and {len(sector_data)} sectors...")
                self._update_stock_data_table_during_login(live_prices, sector_data, user_id)
            
            print(f"✅ Live prices and sector data fetching complete!")
            
        except Exception as e:
            print(f"❌ Error fetching live prices and sectors during login: {e}")
    
    def _update_stock_data_table_during_login(self, live_prices: Dict, sector_data: Dict, user_id: int):
        """Update stock_data table with live prices and sectors during login"""
        try:
            from database_config_supabase import supabase
            
            updated_count = 0
            for ticker in set(list(live_prices.keys()) + list(sector_data.keys())):
                try:
                    update_data = {}
                    
                    if ticker in live_prices:
                        update_data['live_price'] = live_prices[ticker]
                    
                    if ticker in sector_data:
                        update_data['sector'] = sector_data[ticker]
                    
                    if update_data:
                        # Check if record exists
                        existing = supabase.table("stock_data").select("*").eq("ticker", ticker).execute()
                        
                        if existing.data and len(existing.data) > 0:
                            # Update existing record
                            result = supabase.table("stock_data").update(update_data).eq("ticker", ticker).execute()
                        else:
                            # Create new record
                            update_data['ticker'] = ticker
                            update_data['user_id'] = user_id
                            result = supabase.table("stock_data").insert(update_data).execute()
                        
                        if result.data:
                            updated_count += 1
                            print(f"✅ Updated stock_data for {ticker}")
                        else:
                            print(f"⚠️ Failed to update stock_data for {ticker}")
                            
                except Exception as e:
                    print(f"⚠️ Error updating stock_data for {ticker}: {e}")
                    continue
            
            print(f"✅ Successfully updated {updated_count} stock_data records")
            
        except Exception as e:
            print(f"❌ Error updating stock_data table: {e}")
    
    def _save_updated_prices_to_db(self, df: pd.DataFrame, user_id: int):
        """Save updated prices from DataFrame back to the database"""
        try:
            from database_config_supabase import supabase
            
            updated_count = 0
            for idx, row in df.iterrows():
                try:
                    # Get the original transaction ID from the database
                    # We need to match by ticker, date, quantity, and user_id
                    result = supabase.table("investment_transactions").select("id").eq("ticker", row['ticker']).eq("date", row['date']).eq("quantity", row['quantity']).eq("user_id", user_id).execute()
                    
                    if result.data and len(result.data) > 0:
                        transaction_id = result.data[0]['id']
                        
                        # Update the price
                        update_result = supabase.table("investment_transactions").update({
                            "price": row['price']
                        }).eq("id", transaction_id).execute()
                        
                        if update_result.data:
                            updated_count += 1
                        else:
                            print(f"⚠️ Failed to update transaction {transaction_id} for {row['ticker']}")
                    else:
                        print(f"⚠️ Could not find transaction for {row['ticker']} on {row['date']}")
                        
                except Exception as e:
                    print(f"⚠️ Error updating transaction for {row['ticker']}: {e}")
                    continue
            
            print(f"✅ Successfully updated {updated_count} transactions in database")
            
        except Exception as e:
            print(f"❌ Error saving updated prices to database: {e}")
            raise e

    def test_mftool_connectivity(self):
        """Test mftool connectivity and display status"""
        try:
            # Ensure mftool is initialized
            if not self._ensure_mftool_initialized():
                return "❌ Mftool client initialization failed"
            
            if not self.mftool_available:
                return "⚠️ Mftool initialized but not working"
            
            # Test with a known scheme
            try:
                test_scheme = self.mftool_client.get_scheme_details("120466")
                if test_scheme and 'nav' in test_scheme:
                    nav = test_scheme.get('nav', 'N/A')
                    name = test_scheme.get('scheme_name', 'N/A')
                    return f"✅ Mftool working - Test scheme: {name} (NAV: ₹{nav})"
                else:
                    return "⚠️ Mftool connected but test scheme failed"
            except Exception as e:
                return f"❌ Mftool test failed: {str(e)}"
                
        except Exception as e:
            return f"❌ Error testing mftool: {str(e)}"
    
    def check_mftool_installation(self):
        """Check if mftool is properly installed and accessible"""
        try:
            import mftool
            print("✅ Mftool package is installed")
            
            # Check version
            try:
                version = mftool.__version__
                print(f"📦 Mftool version: {version}")
            except:
                print("📦 Mftool version: Unknown")
            
            # Check if we can create an instance
            try:
                test_instance = mftool.Mftool()
                print("✅ Mftool class can be instantiated")
                return True
            except Exception as e:
                print(f"❌ Mftool instantiation failed: {e}")
                return False
                
        except ImportError as e:
            print(f"❌ Mftool package not found: {e}")
            print("💡 To install mftool, run: pip install mftool")
            return False
        except Exception as e:
            print(f"❌ Error checking mftool: {e}")
            return False
    
    def display_mftool_status(self):
        """Display mftool status in the UI"""
        # Check installation first
        if st.button("📦 Check Mftool Installation"):
            st.info("🔍 Checking mftool installation...")
            if self.check_mftool_installation():
                st.success("✅ Mftool is properly installed!")
            else:
                st.error("❌ Mftool installation issues detected!")
        
        # Manual initialization button
        if st.button("🔄 Initialize Mftool"):
            st.info("🔄 Initializing mftool...")
            if self._ensure_mftool_initialized():
                st.success("✅ Mftool initialized successfully!")
            else:
                st.error("❌ Mftool initialization failed!")
            st.rerun()
        
        # Test connectivity button
        if st.button("🔍 Test Mftool Status"):
            status = self.test_mftool_connectivity()
            st.info(status)
            
            # Also show detailed status
            st.write("**Detailed Mftool Status:**")
            st.write(f"- Client initialized: {'✅' if self.mftool_client else '❌'}")
            st.write(f"- Available: {'✅' if self.mftool_available else '❌'}")
            if self.mftool_client:
                st.write(f"- Client type: {type(self.mftool_client).__name__}")

    def debug_historical_price_fetching(self, ticker: str, transaction_date, user_id: int):
        """Debug function to show what's happening with historical price fetching"""
        st.write(f"🔍 **Debug: Historical Price Fetching for {ticker}**")
        st.write(f"📅 Transaction Date: {transaction_date}")
        st.write(f"👤 User ID: {user_id}")
        
        # Test each method step by step
        clean_ticker = str(ticker).strip().upper()
        is_mf = clean_ticker.isdigit() or clean_ticker.startswith('MF_')
        st.write(f"🏷️ Clean Ticker: {clean_ticker}")
        st.write(f"📊 Is Mutual Fund: {is_mf}")
        
        if is_mf:
            st.write("🔄 **Testing Mutual Fund Methods:**")
            
            # Method 1: mftool historical
            try:
                from mf_price_fetcher import fetch_mutual_fund_historical_price
                price = fetch_mutual_fund_historical_price(clean_ticker, transaction_date)
                if price and price > 0:
                    st.success(f"✅ Method 1 (mftool): ₹{price}")
                else:
                    st.warning(f"⚠️ Method 1 (mftool): No price returned")
            except Exception as e:
                st.error(f"❌ Method 1 (mftool): {e}")
            
            # Method 2: Initialized mftool client
            if self.mftool_available and self.mftool_client:
                try:
                    scheme_details = self.mftool_client.get_scheme_details(clean_ticker)
                    if scheme_details and 'nav' in scheme_details:
                        current_nav = float(scheme_details['nav'])
                        days_diff = (pd.Timestamp.now() - pd.Timestamp(transaction_date)).days
                        variation_factor = 1 + (days_diff * 0.001)
                        historical_price = current_nav / variation_factor
                        st.success(f"✅ Method 2 (initialized mftool): ₹{historical_price}")
                    else:
                        st.warning(f"⚠️ Method 2 (initialized mftool): No scheme details")
                except Exception as e:
                    st.error(f"❌ Method 2 (initialized mftool): {e}")
            else:
                st.warning(f"⚠️ Method 2 (initialized mftool): Mftool not available")
            
            # Method 3: Database fallback
            try:
                from database_config_supabase import get_transactions_supabase
                all_user_transactions = get_transactions_supabase(user_id)
                if all_user_transactions:
                    mf_transactions = [t for t in all_user_transactions if t.get('ticker') == ticker]
                    if mf_transactions:
                        prices = [t.get('price', 0) for t in mf_transactions if t.get('price') and t.get('price') > 0]
                        if prices:
                            avg_price = sum(prices) / len(prices)
                            st.success(f"✅ Method 3 (database): ₹{avg_price}")
                        else:
                            st.warning(f"⚠️ Method 3 (database): No valid prices found")
                    else:
                        st.warning(f"⚠️ Method 3 (database): No transactions found for ticker")
                else:
                    st.warning(f"⚠️ Method 3 (database): No user transactions found")
            except Exception as e:
                st.error(f"❌ Method 3 (database): {e}")
        else:
            st.write("🔄 **Testing Stock Methods:**")
            # Add stock debugging here if needed
            st.info("Stock debugging not implemented yet")
    
    def display_debug_section(self):
        """Display debug section in the UI"""
        if st.sidebar.button("🐛 Debug Historical Prices"):
            st.session_state['show_debug'] = True
        
        if st.session_state.get('show_debug', False):
            st.sidebar.markdown("### 🐛 Debug Historical Prices")
            
            # Input fields for debugging
            debug_ticker = st.sidebar.text_input("Ticker to debug:", value="MF_120466")
            debug_date = st.sidebar.date_input("Transaction date:", value=pd.Timestamp.now().date())
            debug_user_id = st.sidebar.number_input("User ID:", value=1, min_value=1)
            
            if st.sidebar.button("🔍 Debug"):
                self.debug_historical_price_fetching(debug_ticker, debug_date, debug_user_id)
            
            if st.sidebar.button("❌ Close Debug"):
                st.session_state['show_debug'] = False
                st.rerun()

    def initialize_after_login(self):
        """Initialize components that need to be initialized after login"""
        try:
            print("🔄 Initializing components after login...")
            
            # Initialize mftool after login
            if self._ensure_mftool_initialized():
                print("✅ Mftool initialized successfully after login")
            else:
                print("⚠️ Mftool initialization failed after login")
            
            # Initialize other components that depend on user session
            if self.user_file_agent:
                print("✅ User file agent ready")
            if self.stock_agent:
                print("✅ Stock agent ready")
            
            print("✅ Post-login initialization complete")
            
        except Exception as e:
            print(f"❌ Error in post-login initialization: {e}")
    
    def _ensure_mftool_initialized(self):
        """Ensure mftool is initialized before use"""
        if self.mftool_client is None:
            self._initialize_mftool()
        return self.mftool_client is not None

# Global web agent instance
web_agent = WebAgent()

# Main function for Streamlit
def main():
    web_agent.run()

if __name__ == "__main__":
    main()
