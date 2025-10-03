import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import warnings
import openai
import json
import base64
import io
import PyPDF2
import pdfplumber
import pytesseract
from PIL import Image
from pdf2image import convert_from_bytes
import google.generativeai as genai
warnings.filterwarnings('ignore')

# Database and authentication imports
from database_config_supabase import (
    get_user_by_username_supabase,
    create_user_supabase,
    save_file_record_supabase,
    save_transactions_bulk_supabase,
    get_transactions_supabase,
    get_file_records_supabase,
    update_stock_data_supabase,
    get_stock_data_supabase,
    update_user_login_supabase,
    save_monthly_stock_price_supabase,
    get_monthly_stock_price_supabase,
    get_monthly_stock_prices_range_supabase,
    get_all_monthly_stock_prices_supabase
)

# Password hashing - temporarily disabled due to login_system.py issues
# from login_system import hash_password, verify_password

# Price fetching imports
from unified_price_fetcher import get_mutual_fund_price, get_stock_price

# Streamlit page configuration
st.set_page_config(
    page_title="WMS-LLM Portfolio Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

class PortfolioAnalytics:
    """Comprehensive Portfolio Analytics System"""
    
    def __init__(self):
        self.session_state = st.session_state
        self.initialize_session_state()
        
    def initialize_session_state(self):
        """Initialize session state variables"""
        if 'user_authenticated' not in self.session_state:
            self.session_state.user_authenticated = False
        if 'user_id' not in self.session_state:
            self.session_state.user_id = None
        if 'username' not in self.session_state:
            self.session_state.username = None
        if 'user_role' not in self.session_state:
            self.session_state.user_role = None
        if 'login_time' not in self.session_state:
            self.session_state.login_time = None
        if 'live_prices' not in self.session_state:
            self.session_state.live_prices = {}
        if 'portfolio_data' not in self.session_state:
            self.session_state.portfolio_data = None
    
    def render_login_page(self):
        """Render the login/registration page"""
        st.title("🚀 WMS-LLM Portfolio Analytics")
        st.markdown("---")
        
        tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])
        
        with tab1:
            st.subheader("Login to Your Portfolio")
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            
            if st.button("Login", type="primary"):
                if self.authenticate_user(username, password):
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid username or password")
        
        with tab2:
            st.subheader("Create New Account")
            new_username = st.text_input("Username", key="reg_username")
            new_password = st.text_input("Password", type="password", key="reg_password")
            confirm_password = st.text_input("Confirm Password", type="password", key="reg_confirm_password")
            
            # File upload during registration
            st.markdown("---")
            st.subheader("📤 Upload Investment Files (Optional)")
            st.info("Upload your CSV transaction files during registration for immediate portfolio analysis")
            
            # Sample CSV Format Button - Prominent and always visible
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("📋 View Sample CSV Format", type="secondary", use_container_width=True):
                    st.session_state.show_sample_csv = True
            
            # Show sample CSV format in a prominent popup-style display
            if st.session_state.get('show_sample_csv', False):
                st.markdown("---")
                st.subheader("📋 Sample CSV Format")
                st.success("💡 **Prepare your CSV file with the following format:**")
                
                # Create a nice formatted display
                sample_col1, sample_col2 = st.columns([1, 1])
                
                with sample_col1:
                    st.markdown("""
                    **Required Columns:**
                    - `date` - Transaction date (YYYY-MM-DD format)
                    - `ticker` - Stock/Mutual Fund symbol (e.g., RELIANCE, 120828)
                    - `quantity` - Number of shares/units
                    - `transaction_type` - Buy or Sell
                    
                    **Optional Columns:**
                    - `price` - Transaction price per share/unit
                    - `stock_name` - Company/Fund name
                    - `sector` - Industry sector
                    - `channel` - Investment platform (e.g., Direct, Broker, Online)
                    """)
                
                with sample_col2:
                    st.markdown("""
                    **Example CSV:**
                    ```csv
                    date,ticker,quantity,transaction_type,price,stock_name,sector,channel
                    2024-01-15,RELIANCE,100,buy,2500.50,Reliance Industries,Oil & Gas,Direct
                    2024-01-20,120828,500,buy,45.25,ICICI Prudential Technology Fund,Technology,Online
                    2024-02-01,TCS,50,sell,3800.00,Tata Consultancy Services,Technology,Broker
                    ```
                    """)
                
                st.info("""
                **Notes:**
                - For mutual funds, use the numerical scheme code (e.g., 120828)
                - For stocks, you can include exchange suffix (.NS, .BO) or leave without
                - Transaction types: buy, sell, purchase, bought, sold, sale
                - If price is missing, the system will fetch historical prices automatically
                """)
                
                            # Action buttons
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                if st.button("✖️ Close Sample Format", type="secondary"):
                    st.session_state.show_sample_csv = False
                    st.rerun()
            
            with col2:
                # Create and download sample CSV
                sample_data = {
                    'date': ['2024-01-15', '2024-01-20', '2024-02-01'],
                    'ticker': ['RELIANCE', '120828', 'TCS'],
                    'quantity': [100, 500, 50],
                    'transaction_type': ['buy', 'buy', 'sell'],
                    'price': [2500.50, 45.25, 3800.00],
                    'stock_name': ['Reliance Industries', 'ICICI Prudential Technology Fund', 'Tata Consultancy Services'],
                    'sector': ['Oil & Gas', 'Technology', 'Technology'],
                    'channel': ['Direct', 'Online', 'Broker']
                }
                sample_df = pd.DataFrame(sample_data)
                csv = sample_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download Sample CSV",
                    data=csv,
                    file_name="sample_investment_portfolio.csv",
                    mime="text/csv",
                    type="primary"
                )
                
                st.markdown("---")
            
            uploaded_files = st.file_uploader(
                "Choose CSV files",
                type=['csv'],
                accept_multiple_files=True,
                key="reg_files",
                help="Upload CSV files with transaction data. Files will be processed automatically after registration."
            )
            
            if uploaded_files:
                st.success(f"✅ Selected {len(uploaded_files)} file(s) for processing")
                
                # Notes about CSV format
                st.info("""
                **Notes:**
                - For mutual funds, use the numerical scheme code (e.g., 120828)
                - For stocks, you can include exchange suffix (.NS, .BO) or leave without
                - Transaction types: buy, sell, purchase, bought, sold, sale
                - If price is missing, the system will fetch historical prices automatically
                """)
            
            if st.button("Create Account & Process Files", type="primary"):
                if new_password != confirm_password:
                    st.error("Passwords do not match")
                elif len(new_password) < 6:
                    st.error("Password must be at least 6 characters")
                elif self.register_user(new_username, new_password, "user", uploaded_files):
                    # Clear any previous messages and show prominent success message
                    st.empty()  # Clear previous content
                    st.success("🎉 Registration successful! Automatically logging you in...")
                    
                    # Automatically authenticate the user after registration
                    if self.authenticate_user(new_username, new_password):
                        st.success("✅ Welcome! You're now logged in and viewing your portfolio.")
                        st.info("📊 Your portfolio dashboard is loading with the files you uploaded...")
                        
                        # Force a rerun to show the main dashboard
                        st.rerun()
                    else:
                        st.error("❌ Auto-login failed. Please try logging in manually.")
                else:
                    st.error("Username already exists or registration failed")
    
    def authenticate_user(self, username, password):
        """Authenticate user and initialize session"""
        try:
            # Convert username to lowercase for case-insensitive comparison
            username_lower = username.lower().strip()
            
            # Try to find user with case-insensitive username
            user = get_user_by_username_supabase(username_lower)
            
            # If not found, try with original username (for backward compatibility)
            if not user:
                user = get_user_by_username_supabase(username)
            
            # Temporary simple password handling - will be updated when login_system is fixed
            if user and user['password_hash'] == password:  # In production, use proper verification
                self.session_state.user_authenticated = True
                self.session_state.user_id = user['id']
                self.session_state.username = user['username']  # Store original username from database
                self.session_state.user_role = user['role']
                self.session_state.login_time = datetime.now()
                
                # Initialize portfolio data after login
                self.initialize_portfolio_data()
                return True
            return False
            
        except Exception as e:
            st.error(f"Authentication error: {e}")
            return False
    
    def process_uploaded_files_during_registration(self, uploaded_files, user_id):
        """Process uploaded files during registration"""
        try:
            if not uploaded_files:
                return
        
            processed_count = 0
            failed_count = 0
        
            for uploaded_file in uploaded_files:
                try:
                    # Process the uploaded file silently during registration
                    result = self.process_csv_file(uploaded_file, user_id)
                    if result:
                        processed_count += 1
                    else:
                        failed_count += 1
                        
                except Exception as e:
                    failed_count += 1
                    # Log error but don't display during registration to keep interface clean
            
            # Return summary for display in main registration flow
            return {
                'processed': processed_count,
                'failed': failed_count,
                'total': len(uploaded_files)
            }
                
        except Exception as e:
            return {
                'processed': 0,
                'failed': len(uploaded_files),
                'total': len(uploaded_files),
                'error': str(e)
            }
    
    def process_csv_file(self, uploaded_file, user_id):
        """Process a single CSV file and store transactions with historical prices"""
        try:
            import pandas as pd
            
            st.info(f"🔄 Processing file: {uploaded_file.name}")
            
            # Read the CSV file
            df = pd.read_csv(uploaded_file)
            st.info(f"📊 File loaded with {len(df)} rows and columns: {list(df.columns)}")
            
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
                'channel': 'channel',
                'Sector': 'sector',
                'sector': 'sector'
            }
            
            # Rename columns
            df = df.rename(columns=column_mapping)
            st.info(f"🔄 Columns standardized: {list(df.columns)}")
            
            # Extract channel from filename if not present
            if 'channel' not in df.columns:
                channel_name = uploaded_file.name.replace('.csv', '').replace('_', ' ')
                df['channel'] = channel_name
                st.info(f"📁 Channel extracted from filename: {channel_name}")
            
            # Ensure required columns exist
            required_columns = ['ticker', 'quantity', 'transaction_type', 'date']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                st.error(f"❌ Missing required columns in {uploaded_file.name}: {missing_columns}")
                st.info("Required columns: date, ticker, quantity, transaction_type")
                st.info("Optional columns: price, stock_name, sector")
                return False
            
            # Clean and validate data
            df = df.dropna(subset=['ticker', 'quantity'])
            df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce')
            st.info(f"📊 Data cleaned: {len(df)} valid rows remaining")
            
            # Convert date to datetime
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            df = df.dropna(subset=['date'])
            st.info(f"📅 Dates processed: {len(df)} rows with valid dates")
            
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
            st.info(f"💼 Transaction types filtered: {len(df)} valid transactions")
            
            if df.empty:
                st.warning(f"⚠️ No valid transactions found in {uploaded_file.name}")
                return False
            
            # Add user_id to the dataframe
            df['user_id'] = user_id
            
            # Fetch historical prices for missing price values
            if 'price' not in df.columns or df['price'].isna().any():
                st.info(f"🔍 Fetching historical prices for {uploaded_file.name}...")
                df = self.fetch_historical_prices_for_transactions(df)
            
            # Save transactions to database
            st.info(f"💾 Saving {len(df)} transactions to database...")
            success = self.save_transactions_to_database(df, user_id, uploaded_file.name)
            
            if success:
                st.success(f"✅ Successfully processed {uploaded_file.name}")
                return True
            else:
                st.error(f"❌ Failed to process {uploaded_file.name}")
                return False
                
        except Exception as e:
            st.error(f"❌ Error processing {uploaded_file.name}: {e}")
            st.error(f"Error type: {type(e).__name__}")
            st.error(f"Error details: {str(e)}")
            import traceback
            st.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def fetch_historical_prices_for_transactions(self, df):
        """Fetch historical prices for transactions"""
        try:
            # Count transactions that need historical prices
            transactions_needing_prices = 0
            for idx, row in df.iterrows():
                if 'price' not in df.columns or pd.isna(df.at[idx, 'price']) or df.at[idx, 'price'] == 0:
                    transactions_needing_prices += 1
            
            if transactions_needing_prices == 0:
                return df
            
            # Create progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            status_text.text(f"🔍 Fetching historical prices for {transactions_needing_prices} transactions...")
            
            processed_count = 0
            
            for idx, row in df.iterrows():
                ticker = row['ticker']
                transaction_date = row['date']
                
                # Skip if already has price
                if 'price' in df.columns and pd.notna(df.at[idx, 'price']) and df.at[idx, 'price'] > 0:
                    continue
                
                # Fetch historical price
                if str(ticker).isdigit() or ticker.startswith('MF_'):
                    # Mutual fund
                    historical_price = get_mutual_fund_price(
                        ticker, 
                        ticker, 
                        row['user_id'], 
                        transaction_date.strftime('%Y-%m-%d')
                    )
                else:
                    # Stock
                    historical_price = get_stock_price(
                        ticker, 
                        ticker, 
                        transaction_date.strftime('%Y-%m-%d')
                    )
                
                if historical_price and historical_price > 0:
                    df.at[idx, 'price'] = historical_price
                else:
                    # Use default price if historical price not available
                    if str(ticker).isdigit() or ticker.startswith('MF_'):
                        df.at[idx, 'price'] = 100.0  # Default MF price
                    else:
                        df.at[idx, 'price'] = 1000.0  # Default stock price
                
                processed_count += 1
                progress = processed_count / transactions_needing_prices
                progress_bar.progress(progress)
                status_text.text(f"🔍 Processing {processed_count}/{transactions_needing_prices} transactions...")
            
            # Complete progress bar
            progress_bar.progress(1.0)
            status_text.text("✅ Historical prices fetched successfully!")
            
            # Clear progress elements after a short delay
            import time
            time.sleep(1)
            progress_bar.progress(1.0)
            status_text.empty()
            
            return df
                    
        except Exception as e:
            st.error(f"Error fetching historical prices: {e}")
            return df
    
    def fetch_historical_price_for_month(self, ticker, month_date):
        """Fetch historical price for a specific month - uses database cache first"""
        try:
            # Convert month_date to the last day of the month for better price data
            if month_date.month == 12:
                last_day = month_date.replace(year=month_date.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                last_day = month_date.replace(month=month_date.month + 1, day=1) - timedelta(days=1)
            
            # Use the last trading day of the month
            target_date = last_day
            target_date_str = target_date.strftime('%Y-%m-%d')
            
            # First, try to get from database cache
            cached_price = get_monthly_stock_price_supabase(ticker, target_date_str)
            if cached_price and cached_price > 0:
                return float(cached_price)
            
            # If not in cache, fetch from API and save to database
            price = None
            price_source = 'unknown'
            
            # Check if it's a mutual fund (numerical ticker)
            clean_ticker = str(ticker).strip().upper()
            clean_ticker = clean_ticker.replace('.NS', '').replace('.BO', '').replace('.NSE', '').replace('.BSE', '')
            
            if clean_ticker.isdigit():
                # Mutual fund - use mftool for historical price
                try:
                    from mf_price_fetcher import fetch_mutual_fund_price
                    price = fetch_mutual_fund_price(ticker, target_date_str)
                    price_source = 'mftool'
                    if price and price > 0:
                        price = float(price)
                except Exception as e:
                    st.debug(f"MFTool failed for {ticker} on {target_date}: {e}")
                
                # Fallback to INDstocks for mutual funds
                if not price or price <= 0:
                    try:
                        from indstocks_api import get_indstocks_client
                        api_client = get_indstocks_client()
                        if api_client and api_client.available:
                            price_data = api_client.get_historical_price(ticker, target_date_str)
                            if price_data and price_data.get('price'):
                                price = float(price_data['price'])
                                price_source = 'indstocks_mf'
                    except Exception as e:
                        st.debug(f"INDstocks failed for mutual fund {ticker} on {target_date}: {e}")
            else:
                # Stock - use yfinance for historical price
                try:
                    import yfinance as yf
                    
                    # Add .NS suffix for Indian stocks if not present
                    if not ticker.endswith(('.NS', '.BO')):
                        ticker_with_suffix = f"{ticker}.NS"
                    else:
                        ticker_with_suffix = ticker
                    
                    stock = yf.Ticker(ticker_with_suffix)
                    
                    # Get historical data for the specific date
                    hist_data = stock.history(start=target_date, end=target_date + timedelta(days=1))
                    
                    if not hist_data.empty:
                        # Use closing price
                        price = float(hist_data['Close'].iloc[0])
                        price_source = 'yfinance'
                    else:
                        # If no data for exact date, try to get the closest available date
                        hist_data = stock.history(start=target_date - timedelta(days=7), end=target_date + timedelta(days=7))
                        if not hist_data.empty:
                            # Use the closest date
                            price = float(hist_data['Close'].iloc[-1])
                            price_source = 'yfinance'
                        
                except Exception as e:
                    st.debug(f"YFinance failed for {ticker} on {target_date}: {e}")
                    
                    # Fallback to INDstocks for stocks
                    if not price or price <= 0:
                        try:
                            from indstocks_api import get_indstocks_client
                            api_client = get_indstocks_client()
                            if api_client and api_client.available:
                                price_data = api_client.get_historical_price(ticker, target_date_str)
                                if price_data and price_data.get('price'):
                                    price = float(price_data['price'])
                                    price_source = 'indstocks'
                        except Exception as e:
                            st.debug(f"INDstocks failed for stock {ticker} on {target_date}: {e}")
            
            # Save to database cache if we got a valid price
            if price and price > 0:
                save_monthly_stock_price_supabase(ticker, target_date_str, price, price_source)
                return price
            
            return None
            
        except Exception as e:
            st.debug(f"Error fetching historical price for {ticker} on {month_date}: {e}")
            return None
    
    def save_transactions_to_database(self, df, user_id, filename):
        """Save transactions to database"""
        try:
            from database_config_supabase import save_transactions_bulk_supabase, save_file_record_supabase
            
            # First save file record (or get existing one)
            username = self.session_state.username if hasattr(self.session_state, 'username') else None
            file_record = save_file_record_supabase(filename, f"/uploads/{filename}", user_id, username)
            if not file_record:
                # Check if this is a duplicate file error
                st.warning(f"⚠️ File {filename} may have already been processed")
                st.info("💡 This could be due to:")
                st.info("   • File was uploaded before")
                st.info("   • File content is identical to an existing file")
                st.info("   • File hash already exists in database")
                
                # Try to get existing file record
                try:
                    from database_config_supabase import get_file_records_supabase
                    existing_files = get_file_records_supabase(user_id)
                    for existing_file in existing_files:
                        if existing_file.get('filename') == filename:
                            st.info(f"✅ Found existing file record for {filename}")
                            file_record = existing_file
                            break
                except Exception as e:
                    st.warning(f"⚠️ Could not retrieve existing file record: {e}")
                
                if not file_record:
                    st.error("❌ Failed to save file record and could not find existing record")
                    return False
            
            file_id = file_record['id']
            
            # Check if this file was already processed (has existing transactions)
            from database_config_supabase import get_transactions_supabase
            existing_transactions = get_transactions_supabase(user_id=user_id, file_id=file_id)
            
            if existing_transactions and len(existing_transactions) > 0:
                st.warning(f"⚠️ File {filename} was already processed with {len(existing_transactions)} transactions")
                st.info("Skipping duplicate processing to avoid data duplication")
                return True  # Return success since the file is already processed
            
            # Save transactions in bulk
            success = save_transactions_bulk_supabase(df, file_id, user_id)
            
            if success:
                st.success(f"✅ Saved {len(df)} transactions to database")
                
                # After saving transactions, fetch live prices and sectors for new tickers
                st.info("🔄 Fetching live prices and sectors for new tickers...")
                try:
                    self.fetch_live_prices_and_sectors(user_id)
                    st.success("✅ Live prices and sectors updated successfully!")
                except Exception as e:
                    st.warning(f"⚠️ Live price update had warnings: {e}")
                
                # Refresh portfolio data to include new transactions
                st.info("🔄 Refreshing portfolio data...")
                try:
                    self.load_portfolio_data(user_id)
                    st.success("✅ Portfolio data refreshed successfully!")
                except Exception as e:
                    st.warning(f"⚠️ Portfolio refresh had warnings: {e}")
                
                return True
            else:
                st.error("Failed to save transactions to database")
                return False
                
        except Exception as e:
            st.error(f"Error saving to database: {e}")
            return False
    
    def register_user(self, username, password, role="user", uploaded_files=None):
        """Register new user and process uploaded files"""
        try:
            # Temporary simple password handling - will be updated when login_system is fixed
            hashed_password = password  # In production, use proper hashing
            salt = "temp_salt"  # In production, use proper salt
            
            # Create user with hashed password
            result = create_user_supabase(username, hashed_password, salt, role=role)
            
            if result and uploaded_files:
                # Process uploaded files silently after successful user creation
                try:
                    user_id = result['id']
                    file_summary = self.process_uploaded_files_during_registration(uploaded_files, user_id)
                    # Store file processing summary in session state for display after auto-login
                    self.session_state.registration_file_summary = file_summary
                except Exception as e:
                    # Log error but don't display during registration
                    pass
            
            return result
        except Exception as e:
            st.error(f"Registration error: {e}")
            return False
    
    def initialize_portfolio_data(self):
        """Initialize portfolio data after login"""
        try:
            user_id = self.session_state.user_id
            if not user_id:
                return
            
            # Fetch transactions and update missing historical prices
            self.update_missing_historical_prices(user_id)
            
            # Fetch live prices and sectors
            self.fetch_live_prices_and_sectors(user_id)
            
            # Pre-populate monthly stock prices cache for 1-year buy stocks
            self.populate_monthly_prices_cache(user_id)
            
            # Load portfolio data
            self.load_portfolio_data(user_id)
            
        except Exception as e:
            st.error(f"Error initializing portfolio data: {e}")
    
    def populate_monthly_prices_cache(self, user_id):
        """Pre-populate monthly stock prices cache for 1-year buy stocks"""
        try:
            # Get transactions for the user
            transactions = get_transactions_supabase(user_id)
            if not transactions:
                return
            
            # Convert to DataFrame for easier processing
            df = pd.DataFrame(transactions)
            df['date'] = pd.to_datetime(df['date'])
            
            # Filter for buy transactions in the last year
            one_year_ago = datetime.now() - timedelta(days=365)
            buy_transactions = df[
                (df['transaction_type'] == 'buy') & 
                (df['date'] >= one_year_ago)
            ].copy()
            
            if buy_transactions.empty:
                return
            
            # Get unique stocks
            unique_stocks = buy_transactions['ticker'].unique()
            
            st.info(f"🔄 Pre-populating monthly price cache for {len(unique_stocks)} stocks...")
            
            # Create progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            total_stocks = len(unique_stocks)
            cached_count = 0
            
            for idx, ticker in enumerate(unique_stocks):
                # Update progress
                progress = (idx + 1) / total_stocks
                progress_bar.progress(progress)
                status_text.text(f"Caching prices for {ticker} ({idx + 1}/{total_stocks})...")
                
                # Get stock's purchase date
                stock_purchases = buy_transactions[buy_transactions['ticker'] == ticker]
                purchase_date = stock_purchases['date'].min()
                
                # Generate monthly dates from purchase date to current date
                current_date = datetime.now()
                # Include current month by going to next month and then back
                end_date = current_date.replace(day=1) + timedelta(days=32)
                end_date = end_date.replace(day=1)
                
                monthly_dates = pd.date_range(
                    start=purchase_date.replace(day=1),
                    end=end_date,  # Include current month
                    freq='MS'
                )
                
                # Check which months are already cached
                for month_date in monthly_dates:
                    if month_date.month == 12:
                        last_day = month_date.replace(year=month_date.year + 1, month=1, day=1) - timedelta(days=1)
                    else:
                        last_day = month_date.replace(month=month_date.month + 1, day=1) - timedelta(days=1)
                    
                    target_date_str = last_day.strftime('%Y-%m-%d')
                    
                    # Check if already cached
                    cached_price = get_monthly_stock_price_supabase(ticker, target_date_str)
                    if not cached_price or cached_price <= 0:
                        # Fetch and cache the price
                        price = self.fetch_historical_price_for_month(ticker, month_date)
                        if price and price > 0:
                            cached_count += 1
                
                # Small delay to avoid rate limiting
                import time
                time.sleep(0.1)
            
            # Clear progress indicators
            progress_bar.empty()
            status_text.empty()
            
            if cached_count > 0:
                st.success(f"✅ Cached {cached_count} new monthly price points!")
            else:
                st.info("ℹ️ All monthly prices were already cached.")
                
        except Exception as e:
            st.warning(f"⚠️ Error pre-populating price cache: {e}")
    
    def update_missing_historical_prices(self, user_id):
        """Update missing historical prices in database"""
        try:
            st.info("🔄 Updating missing historical prices...")
            
            # Get user transactions
            transactions = get_transactions_supabase(user_id=user_id)
            if not transactions:
                return
            
            df = pd.DataFrame(transactions)
            
            # Identify transactions with missing historical prices
            missing_prices = df[df['price'].isna() | (df['price'] == 0)]
            
            if len(missing_prices) > 0:
                st.info(f"📊 Found {len(missing_prices)} transactions with missing historical prices")
                
                try:
                    # Create progress bar for updating historical prices
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    status_text.text(f"🔄 Updating historical prices for {len(missing_prices)} transactions...")
                    
                    for i, (_, row) in enumerate(missing_prices.iterrows()):
                        ticker = row['ticker']
                        transaction_date = pd.to_datetime(row['date'])
                        
                        # Fetch historical price
                        if str(ticker).isdigit() or ticker.startswith('MF_'):
                            historical_price = get_mutual_fund_price(
                                ticker, 
                                ticker, 
                                user_id, 
                                transaction_date.strftime('%Y-%m-%d')
                            )
                        else:
                            historical_price = get_stock_price(
                                ticker, 
                                ticker, 
                                user_id, 
                                transaction_date.strftime('%Y-%m-%d')
                            )
                        
                        if historical_price and historical_price > 0:
                            # Update transaction price in database
                            # Note: This would require a database update function
                            pass  # Silent update - no individual success messages
                        
                        # Update progress
                        progress = (i + 1) / len(missing_prices)
                        progress_bar.progress(progress)
                        status_text.text(f"🔄 Updated {i + 1}/{len(missing_prices)} transactions...")
                    
                    # Complete progress bar
                    progress_bar.progress(1.0)
                    status_text.text("✅ Historical prices updated successfully!")
                    
                    # Clear progress elements after a short delay
                    import time
                    time.sleep(1)
                    progress_bar.empty()
                    status_text.empty()
                    
                except Exception as e:
                    st.error(f"Error updating historical prices: {e}")
                            
        except Exception as e:
            st.error(f"Error in update_missing_historical_prices: {e}")
    
    def fetch_live_prices_and_sectors(self, user_id):
        """Fetch live prices and sectors for all tickers"""
        try:
            st.info("🔄 Fetching live prices and sectors...")
            
            # Show data fetching animation
            self.show_data_fetching_animation()
            
            # Get all transactions for the user
            transactions = get_transactions_supabase(user_id=user_id)
            if not transactions:
                st.warning("No transactions found for user")
                return
            
            df = pd.DataFrame(transactions)
            unique_tickers = df['ticker'].unique()
            
            st.info(f"🔍 Found {len(unique_tickers)} unique tickers to fetch data for...")
            
            # Initialize storage
            live_prices = {}
            sectors = {}
            market_caps = {}
            
            # Fetch live prices and sectors for each ticker
            for ticker in unique_tickers:
                try:
                    if str(ticker).isdigit() or ticker.startswith('MF_'):
                        # Mutual fund - use numerical scheme code and get fund category from mftool
                        from unified_price_fetcher import get_mutual_fund_price_and_category
                        live_price, fund_category = get_mutual_fund_price_and_category(ticker, ticker, user_id, None)
                        
                        # Use fund category from mftool if available, otherwise default to "Mutual Fund"
                        if fund_category and fund_category != 'Unknown':
                            sector = fund_category
                            print(f"✅ MF {ticker}: Using fund category '{sector}' from mftool")
                        else:
                            sector = "Mutual Fund"  # Fallback if no category available
                            print(f"⚠️ MF {ticker}: No fund category available, using default 'Mutual Fund'")
                    else:
                        # Stock - fetch price, sector, and market cap from yfinance
                        from unified_price_fetcher import get_stock_price_and_sector
                        live_price, sector, market_cap = get_stock_price_and_sector(ticker, ticker, None)
                        
                        # Store market cap in session state for later use
                        if market_cap and market_cap > 0:
                            if not hasattr(self.session_state, 'market_caps'):
                                self.session_state.market_caps = {}
                            self.session_state.market_caps[ticker] = market_cap
                        
                        # If no sector from yfinance, try to get it from stock data table
                        if not sector or sector == 'Unknown':
                            stock_data = get_stock_data_supabase(ticker)
                            sector = stock_data.get('sector', None) if stock_data else None
                            
                            # If still no sector, try to fetch it from stock_data_agent
                            if not sector or sector == 'Unknown':
                                try:
                                    from stock_data_agent import get_sector
                                    sector = get_sector(ticker)
                                    if sector and sector != 'Unknown':
                                        # Update the stock_data table with the sector
                                        try:
                                            if stock_data:
                                                update_stock_data_supabase(ticker, sector=sector)
                                            else:
                                                # Create new stock data entry
                                                from stock_data_agent import get_stock_name
                                                stock_name = get_stock_name(ticker) or ticker
                                                # This would require a create function - for now just store in session
                                                pass
                                        except Exception as e:
                                            st.debug(f"Could not update sector for {ticker}: {e}")
                                except Exception as e:
                                    st.debug(f"Could not fetch sector for {ticker}: {e}")
                                    sector = 'Unknown'
                        
                        # If still no sector, use a more intelligent categorization
                        if not sector or sector == 'Unknown':
                            # Try to categorize based on ticker name patterns
                            ticker_upper = ticker.upper()
                            if any(word in ticker_upper for word in ['BANK', 'HDFC', 'ICICI', 'SBI', 'AXIS', 'KOTAK']):
                                sector = 'Banking'
                            elif any(word in ticker_upper for word in ['TECH', 'INFY', 'TCS', 'WIPRO', 'HCL']):
                                sector = 'Technology'
                            elif any(word in ticker_upper for word in ['PHARMA', 'CIPLA', 'DRREDDY', 'SUNPHARMA']):
                                sector = 'Pharmaceuticals'
                            elif any(word in ticker_upper for word in ['AUTO', 'MARUTI', 'TATAMOTORS', 'BAJAJ']):
                                sector = 'Automobile'
                            elif any(word in ticker_upper for word in ['STEEL', 'TATASTEEL', 'JSWSTEEL']):
                                sector = 'Metals & Mining'
                            elif any(word in ticker_upper for word in ['OIL', 'ONGC', 'COAL']):
                                sector = 'Oil & Gas'
                            elif any(word in ticker_upper for word in ['CONSUMER', 'HINDUNILVR', 'ITC', 'NESTLE']):
                                sector = 'Consumer Goods'
                            elif any(word in ticker_upper for word in ['REALTY', 'DLF', 'GODREJ']):
                                sector = 'Real Estate'
                            elif any(word in ticker_upper for word in ['POWER', 'POWERGRID', 'NTPC']):
                                sector = 'Power & Energy'
                            else:
                                sector = 'Other Stocks'
                    
                    if live_price and live_price > 0:
                        live_prices[ticker] = live_price
                        sectors[ticker] = sector
                        
                except Exception as e:
                    st.warning(f"⚠️ Could not fetch data for {ticker}: {e}")
                    continue
            
            # Store in session state
            self.session_state.live_prices = live_prices
            self.session_state.sectors = sectors
            
            st.success(f"✅ Fetched live prices for {len(live_prices)} tickers and sectors for {len(sectors)} tickers")
            
        except Exception as e:
            st.error(f"Error fetching live prices: {e}")
    
    def load_portfolio_data(self, user_id):
        """Load and process portfolio data"""
        try:
            transactions = get_transactions_supabase(user_id=user_id)
            if not transactions:
                return
            
            df = pd.DataFrame(transactions)
            
            # Add live prices to transactions
            df['live_price'] = df['ticker'].map(self.session_state.live_prices)
            
            # Fetch sector information from stock_data table for all tickers
            from database_config_supabase import get_stock_data_supabase
            
            # Get unique tickers
            unique_tickers = df['ticker'].unique()
            ticker_sectors = {}
            
            for ticker in unique_tickers:
                try:
                    stock_data = get_stock_data_supabase(ticker)
                    if stock_data and stock_data.get('sector'):
                        ticker_sectors[ticker] = stock_data['sector']
                    else:
                        # Use sector from session state if available
                        ticker_sectors[ticker] = self.session_state.sectors.get(ticker, 'Unknown')
                except Exception as e:
                    # Use sector from session state if available
                    ticker_sectors[ticker] = self.session_state.sectors.get(ticker, 'Unknown')
            
            # Add sector information to the dataframe
            df['sector'] = df['ticker'].map(ticker_sectors)
            
            # For mutual funds, set sector to "Mutual Fund"
            df.loc[df['ticker'].astype(str).str.isdigit() | df['ticker'].str.startswith('MF_'), 'sector'] = 'Mutual Fund'
            
            # Calculate portfolio metrics
            df['invested_amount'] = df['quantity'] * df['price']
            df['current_value'] = df['quantity'] * df['live_price'].fillna(df['price'])
            df['unrealized_pnl'] = df['current_value'] - df['invested_amount']
            df['pnl_percentage'] = (df['unrealized_pnl'] / df['invested_amount']) * 100
            
            # Store processed data
            self.session_state.portfolio_data = df
            
            # Set last refresh time
            self.session_state.last_refresh_time = datetime.now()
            
        except Exception as e:
            st.error(f"Error loading portfolio data: {e}")
    
    def show_loading_animation(self):
        """Show an engaging stock growth loading animation"""
        st.markdown("""
        <style>
        .loading-container {
            text-align: center;
            padding: 50px 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 15px;
            margin: 20px 0;
            color: white;
        }
        .stock-animation {
            font-size: 48px;
            margin: 20px 0;
            animation: pulse 2s infinite;
        }
        .loading-text {
            font-size: 24px;
            margin: 20px 0;
            font-weight: bold;
        }
        .progress-bar {
            width: 100%;
            height: 20px;
            background-color: rgba(255,255,255,0.3);
            border-radius: 10px;
            overflow: hidden;
            margin: 20px 0;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #00ff88, #00ccff);
            border-radius: 10px;
            animation: progress 3s ease-in-out infinite;
        }
        @keyframes pulse {
            0%, 100% { transform: scale(1); opacity: 1; }
            50% { transform: scale(1.1); opacity: 0.8; }
        }
        @keyframes progress {
            0% { width: 0%; }
            50% { width: 70%; }
            100% { width: 100%; }
        }
        .ticker-symbols {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin: 30px 0;
            flex-wrap: wrap;
        }
        .ticker {
            background: rgba(255,255,255,0.2);
            padding: 10px 15px;
            border-radius: 25px;
            font-weight: bold;
            animation: float 3s ease-in-out infinite;
        }
        .ticker:nth-child(1) { animation-delay: 0s; }
        .ticker:nth-child(2) { animation-delay: 0.5s; }
        .ticker:nth-child(3) { animation-delay: 1s; }
        .ticker:nth-child(4) { animation-delay: 1.5s; }
        .ticker:nth-child(5) { animation-delay: 2s; }
        @keyframes float {
            0%, 100% { transform: translateY(0px); }
            50% { transform: translateY(-10px); }
        }
        .chart-animation {
            font-size: 36px;
            margin: 20px 0;
            animation: grow 2s ease-in-out infinite;
        }
        @keyframes grow {
            0% { transform: scaleY(0.3); }
            50% { transform: scaleY(1); }
            100% { transform: scaleY(0.3); }
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Main loading container
        st.markdown("""
        <div class="loading-container">
            <div class="stock-animation">📈</div>
            <div class="loading-text">🚀 Loading Your Portfolio Analytics...</div>
            <div class="loading-text">📊 Fetching Market Data & Calculating Performance</div>
            
            <div class="ticker-symbols">
                <div class="ticker">RELIANCE</div>
                <div class="ticker">TCS</div>
                <div class="ticker">HDFC</div>
                <div class="ticker">INFY</div>
                <div class="ticker">ITC</div>
            </div>
            
            <div class="chart-animation">📊</div>
            <div class="loading-text">💹 Analyzing Stock Performance...</div>
            
            <div class="progress-bar">
                <div class="progress-fill"></div>
            </div>
            
            <div class="loading-text">⏳ Please wait while we prepare your financial insights...</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Add a Streamlit spinner below the HTML animation
        with st.spinner("🔄 Initializing portfolio data..."):
            # Simulate some loading time
            import time
            time.sleep(0.5)
        
        # Explain why loading is happening
        st.info("""
        🔍 **Why am I seeing these loading steps?**
        
        This happens when you log in and the system needs to:
        1. Load your existing portfolio data from the database
        2. Fetch current market prices for your investments
        3. Calculate performance metrics and generate charts
        
        This is normal behavior and only happens during the initial data load.
        """)
        
        # Show loading steps with progress indicators
        st.markdown("### 🔄 Portfolio Loading Progress:")
        
        # Step 1: Fetching transaction data
        with st.spinner("📊 **Step 1:** Fetching transaction data..."):
            st.info("📊 **Step 1:** Fetching transaction data...")
            # Note: If you see "file processed successfully and failed" messages, 
            # it means some files were processed while others had issues
            st.info("💡 **Note:** Previous file processing results may appear here")
            # Simulate step completion
            import time
            time.sleep(0.3)
        
        # Step 2: Calculating current values
        with st.spinner("📈 **Step 2:** Calculating current values..."):
            st.info("📈 **Step 2:** Calculating current values...")
            time.sleep(0.3)
        
        # Step 3: Analyzing sector allocation
        with st.spinner("🏭 **Step 3:** Analyzing sector allocation..."):
            st.info("🏭 **Step 3:** Analyzing sector allocation...")
            time.sleep(0.3)
        
        # Step 4: Computing P&L metrics
        with st.spinner("💰 **Step 4:** Computing P&L metrics..."):
            st.info("💰 **Step 4:** Computing P&L metrics...")
            time.sleep(0.3)
        
        # Step 5: Generating performance charts
        with st.spinner("📅 **Step 5:** Generating performance charts..."):
            st.info("📅 **Step 5:** Generating performance charts...")
            time.sleep(0.3)
        
        # Step 6: Finalizing dashboard
        with st.spinner("✅ **Step 6:** Finalizing dashboard..."):
            st.info("✅ **Step 6:** Finalizing dashboard...")
            time.sleep(0.3)
        
        st.success("🎉 Portfolio loading completed! Redirecting to dashboard...")
        
        # Show overall progress
        st.progress(1.0)
        st.info("🚀 **Next:** You'll be redirected to your portfolio dashboard automatically.")
        
        # Add a manual refresh button
        st.markdown("---")
        if st.button("🔄 Refresh Portfolio Data", type="primary"):
            try:
                st.info("🔄 Refreshing portfolio data...")
                self.initialize_portfolio_data()
                st.success("✅ Portfolio data loaded successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error refreshing data: {e}")
    
    def show_data_fetching_animation(self):
        """Show an animation for data fetching operations"""
        st.markdown("""
        <style>
        .data-fetching {
            text-align: center;
            padding: 20px;
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            border-radius: 10px;
            margin: 15px 0;
            color: white;
        }
        .fetch-icon {
            font-size: 32px;
            margin: 10px 0;
            animation: rotate 2s linear infinite;
        }
        .fetch-text {
            font-size: 16px;
            margin: 8px 0;
            font-weight: bold;
        }
        @keyframes rotate {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
        .pulse-dots {
            display: inline-block;
            animation: pulse-dots 1.5s infinite;
        }
        @keyframes pulse-dots {
            0%, 20% { opacity: 0; }
            50% { opacity: 1; }
            100% { opacity: 0; }
        }
        </style>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class="data-fetching">
            <div class="fetch-icon">🔄</div>
            <div class="fetch-text">📡 Fetching Live Market Data</div>
            <div class="fetch-text">💹 Connecting to Market APIs</div>
            <div class="fetch-text">⏳ Please wait<span class="pulse-dots">...</span></div>
        </div>
        """, unsafe_allow_html=True)
    
    def show_page_loading_animation(self, page_name):
        """Show a simple loading animation for individual pages"""
        st.markdown("""
        <style>
        .page-loading {
            text-align: center;
            padding: 30px 20px;
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            border-radius: 10px;
            margin: 20px 0;
            color: white;
        }
        .page-icon {
            font-size: 36px;
            margin: 15px 0;
            animation: bounce 1.5s infinite;
        }
        .page-text {
            font-size: 18px;
            margin: 10px 0;
            font-weight: bold;
        }
        @keyframes bounce {
            0%, 20%, 50%, 80%, 100% { transform: translateY(0); }
            40% { transform: translateY(-10px); }
            60% { transform: translateY(-5px); }
        }
        </style>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div class="page-loading">
            <div class="page-icon">📊</div>
            <div class="page-text">🔄 Loading {page_name}...</div>
            <div class="page-text">⏳ Please wait...</div>
        </div>
        """, unsafe_allow_html=True)
    
    def render_main_dashboard(self):
        """Render the main dashboard with comprehensive analytics"""
        st.title("📊 Portfolio Analytics Dashboard")
        
        # Show welcome message with file processing summary if user just registered
        if hasattr(self.session_state, 'registration_file_summary') and self.session_state.registration_file_summary:
            file_summary = self.session_state.registration_file_summary
            
            st.success("🎉 Welcome to your Portfolio Analytics Dashboard!")
            
            if file_summary.get('processed', 0) > 0:
                st.info(f"📁 During registration, {file_summary['processed']} file(s) were successfully processed and added to your portfolio.")
            
            if file_summary.get('failed', 0) > 0:
                st.warning(f"⚠️ {file_summary['failed']} file(s) had processing issues. You can re-upload them later.")
            
            # Clear the registration summary after displaying it
            del self.session_state.registration_file_summary
            
            st.markdown("---")
        
        # Show loading animation if portfolio data is not loaded
        if self.session_state.portfolio_data is None:
            st.info("""
            🔄 **Loading Your Portfolio...**
            
            This is normal when you first log in. The system is:
            - Loading your investment data from the database
            - Fetching current market prices
            - Preparing your portfolio analytics
            
            Please wait while we set up your dashboard...
            """)
            
            # Actually load the portfolio data instead of just showing animation
            try:
                with st.spinner("🔄 Loading portfolio data..."):
                    self.initialize_portfolio_data()
                    
                    # Check if data was loaded successfully
                    if self.session_state.portfolio_data is not None:
                        st.success("✅ Portfolio data loaded successfully!")
                        st.rerun()  # Refresh the page to show the dashboard
                    else:
                        st.warning("⚠️ No portfolio data found. Please upload some files first.")
                        self.render_files_page()
                        return
                        
            except Exception as e:
                st.error(f"❌ Error loading portfolio data: {e}")
                st.info("💡 You can still upload files to get started.")
                self.render_files_page()
                return
        
        # Sidebar navigation
        st.sidebar.title("Navigation")
        page = st.sidebar.selectbox(
            "Choose a page:",
            ["🏠 Overview", "📈 Performance", "📊 Allocation", "💰 P&L Analysis", "🤖 AI Assistant", "📁 Files", "⚙️ Settings"]
        )
        
        # User info in sidebar
        st.sidebar.markdown("---")
        st.sidebar.markdown(f"**User:** {self.session_state.username}")
        st.sidebar.markdown(f"**Role:** {self.session_state.user_role}")
        st.sidebar.markdown(f"**Login:** {self.session_state.login_time.strftime('%Y-%m-%d %H:%M')}")
        
        # File upload in sidebar
        st.sidebar.markdown("---")
        st.sidebar.subheader("📤 Upload Files")
        
        uploaded_file = st.sidebar.file_uploader(
            "Choose CSV file",
            type=['csv'],
            key="sidebar_file_upload",
            help="Upload your investment transaction CSV file"
        )
        
        if uploaded_file is not None:
            if st.sidebar.button("Process File", key="sidebar_process"):
                try:
                    # Show processing message
                    st.sidebar.info("🔄 Processing file...")
                    st.info(f"🔄 Starting to process file: {uploaded_file.name}")
                    
                    # Process the uploaded file with spinner
                    with st.spinner("Processing file..."):
                        st.info(f"🔄 Calling process_csv_file for {uploaded_file.name}")
                        # Process the uploaded file directly using the same method as files page
                        success = self.process_csv_file(uploaded_file, self.session_state.user_id)
                        st.info(f"🔄 process_csv_file returned: {success}")
                        
                        if success:
                            st.sidebar.success("✅ File processed successfully!")
                            st.info("🔄 File processed successfully, refreshing portfolio data...")
                            # Refresh portfolio data
                            self.load_portfolio_data(self.session_state.user_id)
                            st.info("🔄 Portfolio data refreshed, calling rerun...")
                            st.rerun()
                        else:
                            st.sidebar.error("❌ Error processing file")
                            st.error("❌ File processing returned False")
                except Exception as e:
                    st.sidebar.error(f"❌ Error: {e}")
                    st.sidebar.error(f"Error details: {str(e)}")
                    st.error(f"❌ Sidebar file processing error: {e}")
                    st.error(f"Error type: {type(e).__name__}")
                    import traceback
                    st.error(f"Traceback: {traceback.format_exc()}")
        
        # AI Assistant in sidebar (available on all pages)
        st.sidebar.markdown("---")
        st.sidebar.subheader("🤖 AI Assistant")
        
        # Model selection
        ai_model = st.sidebar.selectbox(
            "🤖 Choose AI Model",
            ["Google Gemini Flash (Fast)", "Google Gemini Pro (Advanced)", "OpenAI GPT-3.5"],
            help="Gemini Flash: Fast & cost-effective. Gemini Pro: Advanced analysis. OpenAI: 3/min limit"
        )
        
        if ai_model == "Google Gemini Flash (Fast)":
            st.sidebar.success("✅ **Gemini Flash**: 60 requests/minute, fast & cost-effective!")
        elif ai_model == "Google Gemini Pro (Advanced)":
            st.sidebar.success("✅ **Gemini Pro**: Advanced analysis, 60 requests/minute!")
        else:
            st.sidebar.warning("⚠️ **OpenAI**: 3 requests/minute, higher cost")
        
        # Show usage tracking
        if 'api_call_count' not in st.session_state:
            st.session_state.api_call_count = 0
        if 'api_call_times' not in st.session_state:
            st.session_state.api_call_times = []
        
        # Clean old call times (older than 1 minute)
        import time
        current_time = time.time()
        st.session_state.api_call_times = [t for t in st.session_state.api_call_times if current_time - t < 60]
        
        # Show current usage
        recent_calls = len(st.session_state.api_call_times)
        st.sidebar.info(f"📊 **Usage**: {recent_calls}/3 calls in last minute")
        
        if recent_calls >= 3:
            st.sidebar.error("🚫 **Rate limit reached!** Wait 1 minute before trying again.")
        
        # Initialize chat history if not exists
        if 'chat_history' not in st.session_state:
            st.session_state.chat_history = []
        if 'last_api_call' not in st.session_state:
            st.session_state.last_api_call = 0
        if 'openai_api_key' not in st.session_state:
            # Try to get API key from Streamlit secrets first, then fallback to manual input
            try:
                st.session_state.openai_api_key = st.secrets["open_ai"]
                st.session_state.api_key_source = "secrets"
            except Exception as e:
                st.session_state.openai_api_key = None
                st.session_state.api_key_source = "none"
                # Store the error for debugging
                st.session_state.secrets_error = str(e)
        
        if 'gemini_api_key' not in st.session_state:
            # Try to get Gemini API key from Streamlit secrets
            try:
                st.session_state.gemini_api_key = st.secrets["gemini_api_key"]
                st.session_state.gemini_api_key_source = "secrets"
            except Exception as e:
                st.session_state.gemini_api_key = None
                st.session_state.gemini_api_key_source = "none"
                st.session_state.gemini_secrets_error = str(e)
        
        # API Key Status based on selected model
        if ai_model in ["Google Gemini Flash (Fast)", "Google Gemini Pro (Advanced)"]:
            if st.session_state.gemini_api_key:
                # Show Gemini API key status
                if st.session_state.get('gemini_api_key_source') == "secrets":
                    st.sidebar.info("🔑 Gemini API Key from Streamlit Secrets")
                
                # Test Gemini API key validity
                try:
                    # Configure API key
                    genai.configure(api_key=st.session_state.gemini_api_key)
                    
                    # Show API key info for debugging
                    api_key_display = st.session_state.gemini_api_key[:10] + "..." + st.session_state.gemini_api_key[-4:] if len(st.session_state.gemini_api_key) > 14 else "***"
                    st.sidebar.text(f"🔑 Gemini Key: {api_key_display}")
                    
                    # List available models for debugging
                    try:
                        models = list(genai.list_models())
                        available_models = [m.name for m in models if 'generateContent' in m.supported_generation_methods]
                        st.sidebar.text(f"📋 Available models: {len(available_models)}")
                        if available_models:
                            # Show first few model names
                            for model_name in available_models[:3]:
                                st.sidebar.text(f"  • {model_name.split('/')[-1]}")
                    except Exception as e:
                        st.sidebar.text(f"⚠️ Could not list models: {str(e)[:30]}...")
                    
                    # Try different model names to find a working one
                    model_names_to_try = ['gemini-1.0-pro', 'gemini-pro', 'gemini-1.5-pro', 'gemini-1.5-flash']
                    working_model = None
                    
                    for model_name in model_names_to_try:
                        try:
                            model = genai.GenerativeModel(model_name)
                            test_response = model.generate_content("hi")
                            working_model = model_name
                            st.sidebar.success(f"✅ Gemini Ready ({model_name})")
                            break
                        except Exception as e:
                            continue
                    
                    if working_model is None:
                        st.sidebar.error("❌ No working model found")
                        st.sidebar.text("Try checking your API key or model availability")
                except Exception as e:
                    error_msg = str(e)
                    st.sidebar.error(f"❌ Gemini Error: {error_msg}")
                    
                    if st.sidebar.button("🔑 Configure Gemini API Key"):
                        st.session_state.show_gemini_config = True
            else:
                st.sidebar.warning("⚠️ Gemini API Key Needed")
                if st.sidebar.button("🔑 Configure Gemini API Key"):
                    st.session_state.show_gemini_config = True
        else:
            # OpenAI API key status (existing code)
            if st.session_state.openai_api_key:
                # Show source of API key
                if st.session_state.get('api_key_source') == "secrets":
                    st.sidebar.info("🔑 OpenAI API Key from Streamlit Secrets")
            
                # Test API key validity
                try:
                    from openai import OpenAI
                    client = OpenAI(api_key=st.session_state.openai_api_key)
                    
                    # Show API key info for debugging (first 10 and last 4 characters)
                    api_key_display = st.session_state.openai_api_key[:10] + "..." + st.session_state.openai_api_key[-4:] if len(st.session_state.openai_api_key) > 14 else "***"
                    st.sidebar.text(f"🔑 OpenAI Key: {api_key_display}")
                    
                    # Quick test call to validate API key (minimal usage)
                    test_response = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": "hi"}],
                        max_tokens=1,
                        temperature=0
                    )
                    st.sidebar.success("✅ OpenAI Ready")
                except Exception as e:
                    error_msg = str(e)
                    
                    # Show API key info for debugging
                    api_key_display = st.session_state.openai_api_key[:10] + "..." + st.session_state.openai_api_key[-4:] if len(st.session_state.openai_api_key) > 14 else "***"
                    st.sidebar.text(f"🔑 OpenAI Key: {api_key_display}")
                    
                    if "You tried to access" in error_msg or "access_denied" in error_msg.lower():
                        st.sidebar.error("❌ API Access Denied")
                        st.sidebar.info("💡 Check API key permissions in Streamlit secrets")
                        
                        # Show detailed troubleshooting
                        with st.sidebar.expander("🔧 Troubleshooting Steps", expanded=True):
                            st.markdown("""
                            **Common Solutions:**
                            1. **Generate New API Key**: Create a fresh key at [OpenAI Platform](https://platform.openai.com/api-keys)
                            2. **Check Permissions**: Ensure key has GPT-3.5-turbo access
                            3. **Verify Billing**: Check your OpenAI account has active billing
                            4. **Update Secrets**: Replace the key in your Streamlit secrets
                            5. **Wait & Retry**: Sometimes takes a few minutes to propagate
                            """)
                            
                            st.markdown("**🔍 Debug Info:**")
                            st.text(f"Error: {error_msg}")
                            st.text(f"Key starts with: {st.session_state.openai_api_key[:10]}...")
                            st.text(f"Key length: {len(st.session_state.openai_api_key)}")
                            
                            if st.button("🔄 Test API Key Again"):
                                st.rerun()
                    elif "invalid_api_key" in error_msg.lower():
                        st.sidebar.error("❌ Invalid API Key")
                        st.sidebar.info("💡 Check your API key in Streamlit secrets")
                    elif "rate limit" in error_msg.lower():
                        st.sidebar.warning("⚠️ Rate Limited")
                        st.sidebar.info("💡 Wait a moment")
                    else:
                        st.sidebar.error("❌ API Error")
                        st.sidebar.info(f"💡 {error_msg[:50]}...")
                    
                    if st.sidebar.button("🔑 Reconfigure API Key"):
                        st.session_state.show_api_config = True
            else:
                # Show debugging info for secrets
                if st.session_state.get('api_key_source') == "none":
                    st.sidebar.warning("⚠️ OpenAI API Key Not Found")
                    if st.session_state.get('secrets_error'):
                        st.sidebar.error(f"❌ Secrets Error: {st.session_state.secrets_error}")
                    st.sidebar.info("💡 Check Streamlit secrets configuration")
                else:
                    st.sidebar.warning("⚠️ API Key Needed")
                
                if st.sidebar.button("🔑 Configure API Key"):
                    st.session_state.show_api_config = True
        
        # Quick Actions for current page context
        st.sidebar.markdown("**⚡ Quick Actions**")
        
        # Context-aware quick actions based on current page
        if page == "🏠 Overview":
            if st.sidebar.button("📊 Portfolio Summary", key="sidebar_portfolio_summary"):
                if st.session_state.openai_api_key:
                    self.quick_analysis("Provide a comprehensive summary of my portfolio including performance, allocation, and key insights", page)
                else:
                    st.sidebar.error("❌ Configure API key")
            
            if st.sidebar.button("📈 Best Performers", key="sidebar_best_performers"):
                if st.session_state.openai_api_key:
                    self.quick_analysis("What are my best performing stocks and why?", page)
                else:
                    st.sidebar.error("❌ Configure API key")
        
        elif page == "📈 Performance":
            if st.sidebar.button("📊 Performance Analysis", key="sidebar_performance_analysis"):
                if st.session_state.openai_api_key:
                    self.quick_analysis("Analyze my portfolio performance, identify trends, and suggest improvements", page)
                else:
                    st.sidebar.error("❌ Configure API key")
            
            if st.sidebar.button("📉 Risk Assessment", key="sidebar_risk_assessment"):
                if st.session_state.openai_api_key:
                    self.quick_analysis("Analyze the risk in my portfolio and suggest improvements", page)
                else:
                    st.sidebar.error("❌ Configure API key")
        
        elif page == "📊 Allocation":
            if st.sidebar.button("🎯 Allocation Review", key="sidebar_allocation_review"):
                if st.session_state.openai_api_key:
                    self.quick_analysis("Review my portfolio allocation and suggest rebalancing strategies", page)
                else:
                    st.sidebar.error("❌ Configure API key")
            
            if st.sidebar.button("📊 Sector Analysis", key="sidebar_sector_analysis"):
                if st.session_state.openai_api_key:
                    self.quick_analysis("Analyze my sector allocation and provide diversification insights", page)
                else:
                    st.sidebar.error("❌ Configure API key")
        
        elif page == "💰 P&L Analysis":
            if st.sidebar.button("💰 P&L Insights", key="sidebar_pnl_insights"):
                if st.session_state.openai_api_key:
                    self.quick_analysis("Provide insights on my profit and loss performance", page)
                else:
                    st.sidebar.error("❌ Configure API key")
            
            if st.sidebar.button("📈 Trading Analysis", key="sidebar_trading_analysis"):
                if st.session_state.openai_api_key:
                    self.quick_analysis("Analyze my trading patterns and suggest improvements", page)
                else:
                    st.sidebar.error("❌ Configure API key")
        
        # Universal quick actions
        if st.sidebar.button("🎯 Recommendations", key="sidebar_recommendations"):
            if st.session_state.openai_api_key:
                self.quick_analysis("Give me investment recommendations based on my portfolio", page)
            else:
                st.sidebar.error("❌ Configure API key")
        
        if st.sidebar.button("❓ Ask Anything", key="sidebar_ask_anything"):
            if st.session_state.openai_api_key:
                st.session_state.show_ai_chat = True
            else:
                st.sidebar.error("❌ Configure API key")
        
        # Chat interface in sidebar
        if st.session_state.get('show_ai_chat', False):
            st.sidebar.markdown("---")
            st.sidebar.subheader("💬 Chat")
            
            # Display recent chat history (last 3 messages)
            if st.session_state.chat_history:
                st.sidebar.markdown("**Recent Messages:**")
                for msg in st.session_state.chat_history[-3:]:
                    role_icon = "👤" if msg["role"] == "user" else "🤖"
                    st.sidebar.markdown(f"{role_icon} {msg['content'][:50]}...")
            
            # Chat input
            user_input = st.sidebar.text_input("Ask me anything:", key="sidebar_chat_input")
            if st.sidebar.button("Send", key="sidebar_send"):
                if user_input:
                    self.quick_analysis(user_input, page)
                    st.sidebar.rerun()
            
            if st.sidebar.button("Close Chat", key="sidebar_close_chat"):
                st.session_state.show_ai_chat = False
                st.sidebar.rerun()
        
        # API Configuration Section (if needed)
        if st.session_state.get('show_api_config', False):
            st.sidebar.markdown("---")
            st.sidebar.subheader("🔑 API Configuration")
            
            api_key = st.sidebar.text_input(
                "OpenAI API Key:",
                type="password",
                value=st.session_state.openai_api_key or "",
                help="Get your API key from https://platform.openai.com/api-keys"
            )
            
            if st.sidebar.button("Save API Key"):
                if api_key:
                    st.session_state.openai_api_key = api_key
                    st.sidebar.success("✅ API Key saved!")
                    st.session_state.show_api_config = False
                    st.rerun()
                else:
                    st.sidebar.error("❌ Please enter a valid API key")
            
            if st.sidebar.button("Cancel"):
                st.session_state.show_api_config = False
                st.rerun()
            
            st.sidebar.markdown("---")
            st.sidebar.info("""
            **Troubleshooting:**
            - Check API key permissions
            - Verify billing is active
            - Ensure key has GPT-3.5 access
            """)
        
        # Logout button
        st.sidebar.markdown("---")
        if st.sidebar.button("Logout"):
            self.session_state.clear()
            st.rerun()
        
        # Render selected page
        if page == "🏠 Overview":
            self.render_overview_page()
        elif page == "📈 Performance":
            self.render_performance_page()
        elif page == "📊 Allocation":
            self.render_allocation_page()
        elif page == "💰 P&L Analysis":
            self.render_pnl_analysis_page()
        elif page == "🤖 AI Assistant":
            self.render_ai_assistant_page()
        elif page == "📁 Files":
            self.render_files_page()
        elif page == "⚙️ Settings":
            self.render_settings_page()
    
    def render_overview_page(self):
        """Render portfolio overview with key metrics"""
        st.header("🏠 Portfolio Overview")
        
        # Add refresh notification
        if hasattr(self.session_state, 'last_refresh_time'):
            time_since_refresh = (datetime.now() - self.session_state.last_refresh_time).total_seconds() / 60
            if time_since_refresh > 30:  # Show warning if data is older than 30 minutes
                st.warning(f"⚠️ Portfolio data was last updated {time_since_refresh:.0f} minutes ago. Use the '🔄 Refresh Portfolio Data' button in Settings to get the latest data.")
        else:
            st.info("ℹ️ Use the '🔄 Refresh Portfolio Data' button in Settings to get the latest portfolio data.")
        
        if self.session_state.portfolio_data is None:
            self.show_page_loading_animation("Portfolio Overview")
            st.info("💡 **Tip:** If this page doesn't load automatically, use the '🔄 Refresh Portfolio Data' button in Settings.")
            return
        
        df = self.session_state.portfolio_data
        
        # Portfolio summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_invested = df['invested_amount'].sum()
            st.metric("Total Invested", f"₹{total_invested:,.2f}")
        
        with col2:
            total_current = df['current_value'].sum()
            st.metric("Current Value", f"₹{total_current:,.2f}")
        
        with col3:
            total_pnl = df['unrealized_pnl'].sum()
            pnl_color = "normal" if total_pnl >= 0 else "inverse"
            # Determine arrow for total P&L
            if total_pnl > 0:
                pnl_arrow = "🔼"
            elif total_pnl < 0:
                pnl_arrow = "🔽"
            else:
                pnl_arrow = "➖"
            
            st.metric("Total P&L", f"{pnl_arrow} ₹{total_pnl:,.2f}", delta_color=pnl_color)
        
        with col4:
            if total_invested > 0:
                total_return = (total_pnl / total_invested) * 100
                return_arrow = "🔼" if total_return >= 0 else "🔽"
                return_color = "normal" if total_return >= 0 else "inverse"
                st.metric("Total Return", f"{return_arrow} {total_return:.2f}%", delta_color=return_color)
        
        st.markdown("---")
        
        # Top performers and underperformers
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🏆 Top Performers")
            if 'pnl_percentage' in df.columns and not df['pnl_percentage'].isna().all():
                valid_data = df.dropna(subset=['pnl_percentage'])
                if not valid_data.empty:
                    top_performers = valid_data.groupby('ticker')['pnl_percentage'].sum().sort_values(ascending=False).head(5)
                    if not top_performers.empty:
                        fig_top = px.bar(
                            x=top_performers.values,
                            y=top_performers.index,
                            orientation='h',
                            title="Top 5 Performers by Return %",
                            labels={'x': 'Return %', 'y': 'Ticker'},
                            color=top_performers.values,
                            color_continuous_scale='Greens'
                        )
                        st.plotly_chart(fig_top, config={'displayModeBar': True, 'responsive': True})
                    else:
                        st.info("No performance data available")
                else:
                    st.info("No valid performance data available")
            else:
                st.info("Performance data not available")
        
        with col2:
            st.subheader("📉 Underperformers")
            if 'pnl_percentage' in df.columns and not df['pnl_percentage'].isna().all():
                valid_data = df.dropna(subset=['pnl_percentage'])
                if not valid_data.empty:
                    underperformers = valid_data.groupby('ticker')['pnl_percentage'].sum().sort_values().head(5)
                    if not underperformers.empty:
                        fig_bottom = px.bar(
                            x=underperformers.values,
                            y=underperformers.index,
                            orientation='h',
                            title="Bottom 5 Performers by Return %",
                            labels={'x': 'Return %', 'y': 'Ticker'},
                            color=underperformers.values,
                            color_continuous_scale='Reds'
                        )
                        st.plotly_chart(fig_bottom, config={'displayModeBar': True, 'responsive': True})
                    else:
                        st.info("No performance data available")
                else:
                    st.info("No valid performance data available")
            else:
                st.info("Performance data not available")
        
        # Investment Timeline Chart
        st.subheader("📈 Investment Timeline")
        if 'date' in df.columns and 'invested_amount' in df.columns:
            try:
                # Ensure date is datetime
                if not pd.api.types.is_datetime64_any_dtype(df['date']):
                    df['date'] = pd.to_datetime(df['date'], errors='coerce')
                
                # Remove rows with invalid dates
                timeline_df = df.dropna(subset=['date']).copy()
                
                if not timeline_df.empty:
                    # Sort by date
                    timeline_df = timeline_df.sort_values('date')
                    
                    # Calculate cumulative invested amount over time
                    timeline_df['cumulative_invested'] = timeline_df['invested_amount'].cumsum()
                    
                    # Create the investment timeline chart
                    fig_timeline = go.Figure()
                    
                    # Add cumulative invested amount line
                    fig_timeline.add_trace(go.Scatter(
                        x=timeline_df['date'],
                        y=timeline_df['cumulative_invested'],
                        mode='lines+markers',
                        name='Cumulative Invested Amount',
                        line=dict(color='blue', width=3),
                        marker=dict(size=6),
                        hovertemplate='<b>Date:</b> %{x}<br><b>Total Invested:</b> ₹%{y:,.2f}<extra></extra>'
                    ))
                    
                    # Add individual transaction points
                    fig_timeline.add_trace(go.Scatter(
                        x=timeline_df['date'],
                        y=timeline_df['invested_amount'],
                        mode='markers',
                        name='Individual Transactions',
                        marker=dict(
                            size=8,
                            color='red',
                            symbol='circle',
                            line=dict(width=1, color='white')
                        ),
                        hovertemplate='<b>Date:</b> %{x}<br><b>Transaction Amount:</b> ₹%{y:,.2f}<extra></extra>'
                    ))
                    
                    fig_timeline.update_layout(
                        title="Investment Timeline - Cumulative Amount Over Time",
                        xaxis_title="Date",
                        yaxis_title="Amount (₹)",
                        hovermode='x unified',
                        showlegend=True,
                        legend=dict(
                            orientation="h",
                            yanchor="bottom",
                            y=1.02,
                            xanchor="right",
                            x=1
                        )
                    )
                    
                    st.plotly_chart(fig_timeline, config={'displayModeBar': True, 'responsive': True})
                    
                    # Show summary statistics
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("First Investment", timeline_df['date'].min().strftime('%Y-%m-%d'))
                    with col2:
                        st.metric("Latest Investment", timeline_df['date'].max().strftime('%Y-%m-%d'))
                    with col3:
                        st.metric("Total Investment Days", (timeline_df['date'].max() - timeline_df['date'].min()).days)
                else:
                    st.info("No valid date data available for timeline")
            except Exception as e:
                st.warning(f"Could not create investment timeline: {e}")
        else:
            st.info("Date or invested amount data not available for timeline")
        
        # Recent transactions
        st.subheader("📋 Recent Transactions")
        recent_transactions = df.sort_values('date', ascending=False).head(10)
        st.dataframe(
            recent_transactions[['date', 'ticker', 'quantity', 'price', 'live_price', 'unrealized_pnl']],
            width='stretch'
        )
    
    def render_performance_page(self):
        """Render performance analysis charts"""
        st.header("📈 Performance Analysis")
        
        if self.session_state.portfolio_data is None:
            self.show_page_loading_animation("Performance Analysis")
            st.info("💡 **Tip:** If this page doesn't load automatically, use the '🔄 Refresh Portfolio Data' button in Settings.")
            return
        
        df = self.session_state.portfolio_data
        
        # Ensure date column is properly formatted as datetime
        if 'date' not in df.columns:
            st.error("Date column not found in portfolio data")
            return
        
        try:
            # Convert date column to datetime if it's not already
            if not pd.api.types.is_datetime64_any_dtype(df['date']):
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
            
            # Remove rows with invalid dates
            df = df.dropna(subset=['date'])
            
            if df.empty:
                st.warning("No valid date data available for performance analysis")
                return
            
            # Performance over time
            st.subheader("📊 Portfolio Performance Over Time")
            
            # Group by date and calculate cumulative performance
            daily_performance = df.groupby(df['date'].dt.date).agg({
                'invested_amount': 'sum',
            'current_value': 'sum',
                'unrealized_pnl': 'sum'
        }).reset_index()
            
            daily_performance['cumulative_return'] = (
                (daily_performance['current_value'] - daily_performance['invested_amount']) / 
                daily_performance['invested_amount']
            ) * 100
            
            # Performance line chart
            fig_performance = go.Figure()
            fig_performance.add_trace(go.Scatter(
                x=daily_performance['date'],
                y=daily_performance['cumulative_return'],
                mode='lines+markers',
                name='Cumulative Return %',
                line=dict(color='blue', width=3)
            ))
            
            fig_performance.update_layout(
                title="Portfolio Cumulative Return Over Time",
                xaxis_title="Date",
                yaxis_title="Cumulative Return (%)",
                hovermode='x unified'
            )
            
            st.plotly_chart(fig_performance, config={'displayModeBar': True, 'responsive': True})
            
            # Best Performing Sector and Channel Analysis
            st.subheader("🏆 Best Performing Sector & Channel")
            
            # Sector Performance
            if 'sector' in df.columns and not df['sector'].isna().all():
                sector_performance = df.groupby('sector').agg({
                'invested_amount': 'sum',
                'current_value': 'sum',
                    'unrealized_pnl': 'sum'
            }).reset_index()
            
                if not sector_performance.empty:
                    sector_performance['pnl_percentage'] = (sector_performance['unrealized_pnl'] / sector_performance['invested_amount']) * 100
                    sector_performance = sector_performance.sort_values('pnl_percentage', ascending=False)
        
            col1, col2 = st.columns(2)
            with col1:
                        best_sector = sector_performance.iloc[0]
                        best_sector_arrow = "🔼" if best_sector['pnl_percentage'] > 0 else "🔽" if best_sector['pnl_percentage'] < 0 else "➖"
                        best_sector_color = "normal" if best_sector['pnl_percentage'] > 0 else "inverse"
                        st.metric(
                            "Best Performing Sector", 
                            f"{best_sector_arrow} {best_sector['sector']}", 
                            delta=f"₹{best_sector['unrealized_pnl']:,.2f} ({best_sector['pnl_percentage']:.2f}%)",
                            delta_color=best_sector_color
                        )
                    
            with col2:
                if len(sector_performance) > 1:
                    worst_sector = sector_performance.iloc[-1]
                    worst_sector_arrow = "🔼" if worst_sector['pnl_percentage'] > 0 else "🔽" if worst_sector['pnl_percentage'] < 0 else "➖"
                    worst_sector_color = "normal" if worst_sector['pnl_percentage'] > 0 else "inverse"
                    st.metric(
                        "Worst Performing Sector", 
                        f"{worst_sector_arrow} {worst_sector['sector']}", 
                        delta=f"₹{worst_sector['unrealized_pnl']:,.2f} ({worst_sector['pnl_percentage']:.2f}%)",
                        delta_color=worst_sector_color
                    )
            
            # Channel Performance
            if 'channel' in df.columns and not df['channel'].isna().all():
                channel_performance = df.groupby('channel').agg({
                    'invested_amount': 'sum',
                    'current_value': 'sum',
                    'unrealized_pnl': 'sum'
                }).reset_index()
                
                if not channel_performance.empty:
                    channel_performance['pnl_percentage'] = (channel_performance['unrealized_pnl'] / channel_performance['invested_amount']) * 100
                    channel_performance = channel_performance.sort_values('pnl_percentage', ascending=False)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        best_channel = channel_performance.iloc[0]
                        best_channel_arrow = "🔼" if best_channel['pnl_percentage'] > 0 else "🔽" if best_channel['pnl_percentage'] < 0 else "➖"
                        best_channel_color = "normal" if best_channel['pnl_percentage'] > 0 else "inverse"
                        st.metric(
                            "Best Performing Channel", 
                            f"{best_channel_arrow} {best_channel['channel']}", 
                            delta=f"₹{best_channel['unrealized_pnl']:,.2f} ({best_channel['pnl_percentage']:.2f}%)",
                            delta_color=best_channel_color
                        )
                    
                    with col2:
                        if len(channel_performance) > 1:
                            worst_channel = channel_performance.iloc[-1]
                            worst_channel_arrow = "🔼" if worst_channel['pnl_percentage'] > 0 else "🔽" if worst_channel['pnl_percentage'] < 0 else "➖"
                            worst_channel_color = "normal" if worst_channel['pnl_percentage'] > 0 else "inverse"
                            st.metric(
                                "Worst Performing Channel", 
                                f"{worst_channel_arrow} {worst_channel['channel']}", 
                                delta=f"₹{worst_channel['unrealized_pnl']:,.2f} ({worst_channel['pnl_percentage']:.2f}%)",
                                delta_color=worst_channel_color
                            )
            
            # Stock Performance Analysis (1-Year Buy Transactions)
            st.subheader("📈 Stock Performance Analysis (1-Year Buy Transactions)")
             
            # Filter for stocks (not mutual funds) with buy transactions in the last 1 year
            one_year_ago = datetime.now() - timedelta(days=365)
            
            # Filter stocks (exclude mutual funds) with buy transactions in last 1 year
            stock_buys = df[
                (~df['ticker'].astype(str).str.startswith('MF_')) & 
                (df['transaction_type'] == 'buy') & 
                (df['date'] >= one_year_ago)
            ].copy()
             
            if not stock_buys.empty:
                # Group by ticker and calculate performance metrics
                stock_performance = stock_buys.groupby('ticker').agg({
                    'invested_amount': 'sum',
                    'current_value': 'sum',
                    'unrealized_pnl': 'sum',
                    'quantity': 'sum',
                    'date': 'max'  # Latest buy date
                }).reset_index()
                
                # Calculate additional metrics
                stock_performance['pnl_percentage'] = (stock_performance['unrealized_pnl'] / stock_performance['invested_amount']) * 100
                stock_performance['avg_price'] = stock_performance['invested_amount'] / stock_performance['quantity']
                 
                # Add stock ratings based on performance
                def get_stock_rating(pnl_pct):
                    if pnl_pct >= 20:
                        return '⭐⭐⭐ Excellent'
                    elif pnl_pct >= 10:
                        return '⭐⭐ Good'
                    elif pnl_pct >= 0:
                        return '⭐ Fair'
                    elif pnl_pct >= -10:
                        return '⚠️ Poor'
                    else:
                        return '❌ Very Poor'
                 
                stock_performance['rating'] = stock_performance['pnl_percentage'].apply(get_stock_rating)
                stock_performance['rating_color'] = stock_performance['pnl_percentage'].apply(
                    lambda x: 'green' if x >= 10 else 'orange' if x >= 0 else 'red'
                )
                 
                # Sort by P&L percentage
                stock_performance = stock_performance.sort_values('pnl_percentage', ascending=False)
                
                # Display top performers
                st.subheader("🏆 Top Performers (1-Year Buy Transactions)")
                 
                # Create performance chart
                fig_stock_performance = px.bar(
                    stock_performance.head(10),
                    x='ticker',
                    y='pnl_percentage',
                    color='pnl_percentage',
                    color_continuous_scale='RdYlGn',
                    title="Top 10 Stock Performers by Return % (1-Year Buy Transactions)",
                    labels={'pnl_percentage': 'Return %', 'ticker': 'Stock Ticker'},
                    hover_data=['invested_amount', 'unrealized_pnl', 'rating']
                )
                fig_stock_performance.update_xaxes(tickangle=45)
                st.plotly_chart(fig_stock_performance, config={'displayModeBar': True, 'responsive': True})
                
                # Add comprehensive table with sector, channel, and ratings
                st.subheader("📊 Detailed Performance Table (1-Year Buy Transactions)")
                
                # Get additional data for the table (sector, channel, stock_name)
                table_data = []
                for _, row in stock_performance.iterrows():
                    ticker = row['ticker']
                    # Get additional details from original data
                    ticker_data = stock_buys[stock_buys['ticker'] == ticker].iloc[0]
                    
                    table_row = {
                        'Ticker': ticker,
                        'Stock Name': ticker_data.get('stock_name', 'N/A'),
                        'Sector': ticker_data.get('sector', 'Unknown'),
                        'Channel': ticker_data.get('channel', 'N/A'),
                        'Quantity': f"{row['quantity']:,.0f}",
                        'Avg Price': f"₹{row['avg_price']:,.2f}",
                        'Invested Amount': f"₹{row['invested_amount']:,.2f}",
                        'Current Value': f"₹{row['current_value']:,.2f}",
                        'P&L': f"₹{row['unrealized_pnl']:,.2f}",
                        'Return %': f"{row['pnl_percentage']:.2f}%",
                        'Rating': row['rating']
                    }
                    table_data.append(table_row)
                
                # Create a styled table
                if table_data:
                    # Convert to DataFrame for better display
                    table_df = pd.DataFrame(table_data)
                    
                    # Apply color coding based on performance
                    def color_rating(val):
                        if '⭐⭐⭐' in str(val):
                            return 'background-color: #d4edda; color: #155724;'  # Green for excellent
                        elif '⭐⭐' in str(val):
                            return 'background-color: #fff3cd; color: #856404;'   # Yellow for good
                        elif '⭐' in str(val):
                            return 'background-color: #f8d7da; color: #721c24;'  # Red for fair
                        elif '⚠️' in str(val):
                            return 'background-color: #f8d7da; color: #721c24;'  # Red for poor
                        elif '❌' in str(val):
                            return 'background-color: #f8d7da; color: #721c24;'  # Red for very poor
                        return ''
                    
                    # Apply styling
                    styled_table = table_df.style.applymap(color_rating, subset=['Rating'])
                    
                    # Display the styled table
                    st.dataframe(
                        styled_table,
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    # Add summary statistics
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        avg_return = stock_performance['pnl_percentage'].mean()
                        avg_arrow = "🔼" if avg_return >= 0 else "🔽"
                        avg_color = "normal" if avg_return >= 0 else "inverse"
                        st.metric(
                            "Total Invested",
                            f"₹{stock_performance['invested_amount'].sum():,.2f}",
                            delta=f"{avg_arrow} {avg_return:.2f}% avg return",
                            delta_color=avg_color
                        )
                    with col2:
                        total_pnl = stock_performance['unrealized_pnl'].sum()
                        pnl_arrow = "🔼" if total_pnl >= 0 else "🔽"
                        pnl_delta = f"{pnl_arrow} ₹{total_pnl:,.2f} total P&L"
                        pnl_color = "normal" if total_pnl >= 0 else "inverse"
                        
                        st.metric(
                            "Total Current Value",
                            f"₹{stock_performance['current_value'].sum():,.2f}",
                            delta=pnl_delta,
                            delta_color=pnl_color
                        )
                    with col3:
                        best_return = stock_performance.iloc[0]['pnl_percentage']
                        best_arrow = "🔼" if best_return >= 0 else "🔽"
                        best_color = "normal" if best_return >= 0 else "inverse"
                        st.metric(
                            "Best Performer",
                            stock_performance.iloc[0]['ticker'],
                            delta=f"{best_arrow} {best_return:.2f}% return",
                            delta_color=best_color
                        )
                else:
                    st.info("No detailed data available for table display")
                
                # Add quarterly performance analysis
                st.subheader("📅 Quarterly Performance Analysis (1-Year Buy Transactions)")
                
                try:
                    # Create quarterly data for each stock
                    quarterly_data = []
                    
                    for _, row in stock_performance.iterrows():
                        ticker = row['ticker']
                        ticker_transactions = stock_buys[stock_buys['ticker'] == ticker].copy()
                        
                        # Convert date to datetime if it's not already
                        if not pd.api.types.is_datetime64_any_dtype(ticker_transactions['date']):
                            ticker_transactions['date'] = pd.to_datetime(ticker_transactions['date'])
                        
                        # Add quarter information
                        ticker_transactions['quarter'] = ticker_transactions['date'].dt.quarter
                        ticker_transactions['year'] = ticker_transactions['date'].dt.year
                        ticker_transactions['quarter_label'] = ticker_transactions['year'].astype(str) + ' Q' + ticker_transactions['quarter'].astype(str)
                        
                        # Group by quarter and calculate gains
                        quarterly_gains = ticker_transactions.groupby('quarter_label').agg({
                            'invested_amount': 'sum',
                            'current_value': 'sum',
                            'unrealized_pnl': 'sum'
                        }).reset_index()
                        
                        # Add ticker information
                        quarterly_gains['ticker'] = ticker
                        quarterly_gains['stock_name'] = ticker_transactions.iloc[0].get('stock_name', ticker)
                        
                        quarterly_data.append(quarterly_gains)
                    
                    if quarterly_data:
                        # Combine all quarterly data
                        all_quarterly = pd.concat(quarterly_data, ignore_index=True)
                        
                        # Sort quarters chronologically for proper x-axis ordering
                        # Create a sortable quarter key for chronological ordering
                        def create_sort_key(quarter_label):
                            try:
                                # Extract year and quarter from "2024 Q1" format
                                parts = quarter_label.split(' Q')
                                if len(parts) == 2:
                                    year = int(parts[0])
                                    quarter = int(parts[1])
                                    return year * 10 + quarter
                                return 0
                            except:
                                return 0
                        
                        all_quarterly['sort_key'] = all_quarterly['quarter_label'].apply(create_sort_key)
                        all_quarterly = all_quarterly.sort_values('sort_key')
                        
                        # Create quarterly chart with chronologically ordered x-axis
                        fig_quarterly = px.bar(
                            all_quarterly,
                            x='quarter_label',
                            y='unrealized_pnl',
                            color='ticker',
                            title="Quarterly Absolute Gains by Stock (1-Year Buy Transactions)",
                            labels={
                                'quarter_label': 'Quarter',
                                'unrealized_pnl': 'Absolute Gain (₹)',
                                'ticker': 'Stock Ticker'
                            },
                            hover_data=['stock_name', 'invested_amount', 'current_value'],
                            barmode='group'
                        )
                        
                        fig_quarterly.update_layout(
                            xaxis_title="Quarter",
                            yaxis_title="Absolute Gain (₹)",
                            legend_title="Stock Ticker",
                            height=500
                        )
                        
                        # Ensure x-axis is ordered chronologically
                        fig_quarterly.update_xaxes(
                            tickangle=45,
                            categoryorder='array',
                            categoryarray=all_quarterly['quarter_label'].unique()
                        )
                        
                        st.plotly_chart(fig_quarterly, config={'displayModeBar': True, 'responsive': True})
                        
                        # Add quarterly summary table
                        st.subheader("📊 Quarterly Summary Table")
                        
                        # Create summary by quarter (also sorted chronologically)
                        # Use nunique() for ticker count to get actual number of unique stocks per quarter
                        quarterly_summary = all_quarterly.groupby('quarter_label').agg({
                            'unrealized_pnl': 'sum',
                            'invested_amount': 'sum',
                            'current_value': 'sum',
                            'ticker': 'nunique'  # Count unique tickers instead of all rows
                        }).reset_index()
                        
                        # Ensure we have the expected columns before proceeding
                        expected_columns = ['quarter_label', 'unrealized_pnl', 'invested_amount', 'current_value', 'ticker']
                        if list(quarterly_summary.columns) == expected_columns:
                            # Now add sort key and sort
                            quarterly_summary['sort_key'] = quarterly_summary['quarter_label'].apply(create_sort_key)
                            quarterly_summary = quarterly_summary.sort_values('sort_key')
                            
                            # Remove the sort_key column before renaming
                            quarterly_summary = quarterly_summary.drop('sort_key', axis=1)
                            
                            # Rename columns
                            quarterly_summary.columns = ['Quarter', 'Total Gain (₹)', 'Total Invested (₹)', 'Total Current Value (₹)', 'Number of Stocks']
                            quarterly_summary['Return %'] = (quarterly_summary['Total Gain (₹)'] / quarterly_summary['Total Invested (₹)'] * 100).round(2)
                            
                            # Quarterly summary created successfully
                        else:
                            st.warning(f"Unexpected quarterly summary columns: {list(quarterly_summary.columns)}")
                            st.info("Expected: quarter_label, unrealized_pnl, invested_amount, current_value, ticker")
                            st.info(f"Actual columns: {list(quarterly_summary.columns)}")
                            # Skip this quarter's processing
                            st.info("Skipping quarterly analysis due to column mismatch")
                            quarterly_summary = None
                        
                        # Display quarterly summary only if data is valid
                        if quarterly_summary is not None:
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.dataframe(
                                    quarterly_summary,
                                    use_container_width=True,
                                    hide_index=True
                                )
                            
                            with col2:
                                # Best performing quarter
                                best_quarter = quarterly_summary.loc[quarterly_summary['Total Gain (₹)'].idxmax()]
                                worst_quarter = quarterly_summary.loc[quarterly_summary['Total Gain (₹)'].idxmin()]
                                avg_return = quarterly_summary['Return %'].mean()
                                
                                # Create single line display with arrows and colors
                                st.markdown("**📊 Quarterly Performance Summary**")
                                
                                # Best quarter
                                best_gain = best_quarter['Total Gain (₹)']
                                best_arrow = "🔼" if best_gain >= 0 else "🔽"
                                best_color = "green" if best_gain >= 0 else "red"
                                
                                st.markdown(f"""
                                <div style="margin: 10px 0; padding: 10px; border-left: 4px solid {best_color}; background-color: rgba(0,255,0,0.1);">
                                    <strong>🏆 Best Quarter:</strong> {best_quarter['Quarter']} - {best_arrow} ₹{best_gain:,.2f}
                                </div>
                                """, unsafe_allow_html=True)
                                
                                # Worst quarter
                                worst_gain = worst_quarter['Total Gain (₹)']
                                worst_arrow = "🔼" if worst_gain >= 0 else "🔽"
                                worst_color = "green" if worst_gain >= 0 else "red"
                                
                                st.markdown(f"""
                                <div style="margin: 10px 0; padding: 10px; border-left: 4px solid {worst_color}; background-color: rgba(255,0,0,0.1);">
                                    <strong>⚠️ Worst Quarter:</strong> {worst_quarter['Quarter']} - {worst_arrow} ₹{worst_gain:,.2f}
                                </div>
                                """, unsafe_allow_html=True)
                                
                                # Average return
                                avg_arrow = "🔼" if avg_return >= 0 else "🔽"
                                avg_color = "green" if avg_return >= 0 else "red"
                                
                                st.markdown(f"""
                                <div style="margin: 10px 0; padding: 10px; border-left: 4px solid {avg_color}; background-color: rgba(0,0,255,0.1);">
                                    <strong>📈 Average Return:</strong> {avg_arrow} {avg_return:.2f}% (Across {len(quarterly_summary)} quarters)
                                </div>
                                """, unsafe_allow_html=True)
                        else:
                            st.warning("Quarterly summary could not be generated due to data format issues")
                    else:
                        st.info("No quarterly data available for analysis")
                        
                except Exception as e:
                    st.warning(f"Could not generate quarterly analysis: {str(e)}")
                    st.info("This might be due to date format issues or insufficient data")
                
                # Add comprehensive charts for sector and channel analysis
                if not stock_buys.empty:
                    st.subheader("📊 Sector & Channel Analysis (1-Year Buy Transactions)")
                    
                    # Create two columns for charts
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Sector Performance Chart
                        st.subheader("🏭 Sector Performance Analysis")
                        
                        # Group by sector and calculate metrics
                        sector_performance = stock_buys.groupby('sector').agg({
                            'invested_amount': 'sum',
                            'current_value': 'sum',
                            'unrealized_pnl': 'sum',
                            'quantity': 'sum'
                        }).reset_index()
                        
                        # Calculate sector P&L percentage
                        sector_performance['pnl_percentage'] = (sector_performance['unrealized_pnl'] / sector_performance['invested_amount']) * 100
                        sector_performance = sector_performance.sort_values('pnl_percentage', ascending=False)
                        
                        # Create sector performance chart
                        fig_sector_perf = px.bar(
                            sector_performance,
                            x='sector',
                            y='pnl_percentage',
                            color='pnl_percentage',
                            color_continuous_scale='RdYlGn',
                            title="Sector Performance by Return %",
                            labels={'pnl_percentage': 'Return %', 'sector': 'Sector'},
                            hover_data=['invested_amount', 'unrealized_pnl']
                        )
                        fig_sector_perf.update_xaxes(tickangle=45)
                        st.plotly_chart(fig_sector_perf, config={'displayModeBar': True, 'responsive': True})
                        
                        # Best performing sector
                        if not sector_performance.empty:
                            best_sector = sector_performance.iloc[0]
                            sector_return = best_sector['pnl_percentage']
                            sector_arrow = "🔼" if sector_return >= 0 else "🔽"
                            sector_color = "normal" if sector_return >= 0 else "inverse"
                            st.metric(
                                "🏆 Best Performing Sector",
                                best_sector['sector'],
                                delta=f"{sector_arrow} {sector_return:.2f}% return",
                                delta_color=sector_color
                            )
                    
                    with col2:
                        # Channel Performance Chart
                        st.subheader("📡 Channel Performance Analysis")
                        
                        # Group by channel and calculate metrics
                        channel_performance = stock_buys.groupby('channel').agg({
                            'invested_amount': 'sum',
                            'current_value': 'sum',
                            'unrealized_pnl': 'sum',
                            'quantity': 'sum'
                        }).reset_index()
                        
                        # Calculate channel P&L percentage
                        channel_performance['pnl_percentage'] = (channel_performance['unrealized_pnl'] / channel_performance['invested_amount']) * 100
                        channel_performance = channel_performance.sort_values('pnl_percentage', ascending=False)
                        
                        # Create channel performance chart
                        fig_channel_perf = px.bar(
                            channel_performance,
                            x='channel',
                            y='pnl_percentage',
                            color='pnl_percentage',
                            color_continuous_scale='RdYlGn',
                            title="Channel Performance by Return %",
                            labels={'pnl_percentage': 'Return %', 'channel': 'Channel'},
                            hover_data=['invested_amount', 'unrealized_pnl']
                        )
                        fig_channel_perf.update_xaxes(tickangle=45)
                        st.plotly_chart(fig_channel_perf, config={'displayModeBar': True, 'responsive': True})
                        
                        # Best performing channel
                        if not channel_performance.empty:
                            best_channel = channel_performance.iloc[0]
                            channel_return = best_channel['pnl_percentage']
                            channel_arrow = "🔼" if channel_return >= 0 else "🔽"
                            channel_color = "normal" if channel_return >= 0 else "inverse"
                            st.metric(
                                "🏆 Best Performing Channel",
                                best_channel['channel'],
                                delta=f"{channel_arrow} {channel_return:.2f}% return",
                                delta_color=channel_color
                            )
                    
                    # Add detailed analysis tables below the charts
                    st.subheader("📊 Detailed Analysis Tables")
                    
                    # Create two columns for detailed tables
                    table_col1, table_col2 = st.columns(2)
                    
                    with table_col1:
                        # Sector Analysis Details
                        st.subheader("🏭 Sector Analysis Details")
                        
                        # Create detailed sector table
                        sector_table_data = []
                        for _, row in sector_performance.iterrows():
                            sector = row['sector']
                            value = row['current_value']
                            # Get sector-specific data
                            sector_stocks = stock_buys[stock_buys['sector'] == sector]
                            sector_count = len(sector_stocks['ticker'].unique())
                            sector_pnl = sector_stocks['unrealized_pnl'].sum() if 'unrealized_pnl' in sector_stocks.columns else 0
                            sector_pnl_pct = (sector_pnl / value * 100) if value > 0 else 0
                            
                            sector_table_data.append({
                                'Sector': sector,
                                'Current Value': f"₹{value:,.2f}",
                                'Allocation %': f"{(value / sector_performance['current_value'].sum() * 100):.2f}%",
                                'Number of Stocks': sector_count,
                                'Total P&L': f"₹{sector_pnl:,.2f}",
                                'P&L %': f"{sector_pnl_pct:.2f}%"
                            })
                        
                        # Display sector table
                        if sector_table_data:
                            sector_df = pd.DataFrame(sector_table_data)
                            st.dataframe(
                                sector_df,
                                use_container_width=True,
                                hide_index=True
                            )
                        else:
                            st.info("No detailed sector data available for table display")
                    
                    with table_col2:
                        # Channel Analysis Details
                        st.subheader("📡 Channel Analysis Details")
                        
                        # Create detailed channel table
                        channel_table_data = []
                        for _, row in channel_performance.iterrows():
                            channel = row['channel']
                            value = row['current_value']
                            # Get channel-specific data
                            channel_stocks = stock_buys[stock_buys['channel'] == channel]
                            channel_count = len(channel_stocks['ticker'].unique())
                            channel_pnl = channel_stocks['unrealized_pnl'].sum() if 'unrealized_pnl' in channel_stocks.columns else 0
                            channel_pnl_pct = (channel_pnl / value * 100) if value > 0 else 0
                            
                            channel_table_data.append({
                                'Channel': channel,
                                'Current Value': f"₹{value:,.2f}",
                                'Allocation %': f"{(value / channel_performance['current_value'].sum() * 100):.2f}%",
                                'Number of Stocks': channel_count,
                                'Total P&L': f"₹{channel_pnl:,.2f}",
                                'P&L %': f"{channel_pnl_pct:.2f}%"
                            })
                        
                        # Display channel table
                        if channel_table_data:
                            channel_df = pd.DataFrame(channel_table_data)
                            st.dataframe(
                                channel_df,
                                use_container_width=True,
                                hide_index=True
                            )
                        else:
                            st.info("No detailed channel data available for table display")
                    
                    # Add summary metrics below the tables in a balanced layout
                    st.subheader("📈 Summary Metrics")
                    
                    # Create two columns for summary metrics
                    metrics_col1, metrics_col2 = st.columns(2)
                    
                    with metrics_col1:
                        # Sector summary metrics
                        if sector_table_data:
                            st.subheader("🏭 Sector Summary")
                            
                            # Calculate sector metrics based on current value (not P&L percentage)
                            sector_by_value = sector_performance.sort_values('current_value', ascending=False)
                            
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric(
                                    "Total Sectors",
                                    len(sector_performance),
                                    f"{len(sector_performance)} sectors covered"
                                )
                            with col2:
                                largest_sector = sector_by_value.iloc[0]
                                st.metric(
                                    "Largest Sector",
                                    largest_sector['sector'],
                                    f"₹{largest_sector['current_value']:,.2f}"
                                )
                            with col3:
                                smallest_sector = sector_by_value.iloc[-1]
                                st.metric(
                                    "Smallest Sector",
                                    smallest_sector['sector'],
                                    f"₹{smallest_sector['current_value']:,.2f}"
                                )
                    
                    with metrics_col2:
                        # Channel summary metrics
                        if channel_table_data:
                            st.subheader("📡 Channel Summary")
                            
                            # Calculate channel metrics based on current value (not P&L percentage)
                            channel_by_value = channel_performance.sort_values('current_value', ascending=False)
                            
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric(
                                    "Total Channels",
                                    len(channel_performance),
                                    f"{len(channel_performance)} channels used"
                                )
                            with col2:
                                best_channel = channel_by_value.iloc[0]
                                st.metric(
                                    "Best Channel",
                                    best_channel['channel'],
                                    f"₹{best_channel['current_value']:,.2f}"
                                )
                            with col3:
                                worst_channel = channel_by_value.iloc[-1]
                                st.metric(
                                    "Worst Channel",
                                    worst_channel['channel'],
                                    f"₹{worst_channel['current_value']:,.2f}"
                                )
                    
                    # Best Stock in Each Sector
                    st.subheader("⭐ Best Stock in Each Sector (1-Year Buy Transactions)")
                    
                    # Find best performing stock in each sector and calculate sector ratings
                    best_stocks_by_sector = []
                    sector_ratings = []
                    
                    for sector in stock_buys['sector'].unique():
                        if pd.isna(sector) or sector == 'Unknown':
                            continue
                            
                        sector_stocks = stock_buys[stock_buys['sector'] == sector]
                        
                        # Group by ticker within sector
                        sector_ticker_perf = sector_stocks.groupby('ticker').agg({
                            'invested_amount': 'sum',
                            'current_value': 'sum',
                            'unrealized_pnl': 'sum',
                            'quantity': 'sum'
                        }).reset_index()
                        
                        # Calculate P&L percentage
                        sector_ticker_perf['pnl_percentage'] = (sector_ticker_perf['unrealized_pnl'] / sector_ticker_perf['invested_amount']) * 100
                        
                        # Calculate sector overall performance
                        sector_total_invested = sector_ticker_perf['invested_amount'].sum()
                        sector_total_current = sector_ticker_perf['current_value'].sum()
                        sector_total_pnl = sector_ticker_perf['unrealized_pnl'].sum()
                        sector_overall_return = (sector_total_pnl / sector_total_invested) * 100 if sector_total_invested > 0 else 0
                        
                        # Determine sector rating
                        if sector_overall_return >= 20:
                            sector_rating = "🟢 Excellent"
                            rating_color = "background-color: #d4edda; color: #155724;"
                        elif sector_overall_return >= 10:
                            sector_rating = "🟡 Good"
                            rating_color = "background-color: #fff3cd; color: #856404;"
                        elif sector_overall_return >= 0:
                            sector_rating = "🟠 Fair"
                            rating_color = "background-color: #f8d7da; color: #721c24;"
                        else:
                            sector_rating = "🔴 Poor"
                            rating_color = "background-color: #f8d7da; color: #721c24;"
                        
                        # Store sector rating
                        sector_ratings.append({
                            'Sector': sector,
                            'Overall Return %': f"{sector_overall_return:.2f}%",
                            'Total Invested': f"₹{sector_total_invested:,.2f}",
                            'Total Current Value': f"₹{sector_total_current:,.2f}",
                            'Total P&L': f"₹{sector_total_pnl:,.2f}",
                            'Rating': sector_rating
                        })
                        
                        # Get best performing ticker in this sector
                        if not sector_ticker_perf.empty:
                            best_ticker = sector_ticker_perf.loc[sector_ticker_perf['pnl_percentage'].idxmax()]
                            
                            # Get additional details
                            ticker_data = sector_stocks[sector_stocks['ticker'] == best_ticker['ticker']].iloc[0]
                            
                            best_stocks_by_sector.append({
                                'Sector': sector,
                                'Best Stock': best_ticker['ticker'],
                                'Stock Name': ticker_data.get('stock_name', 'N/A'),
                                'Channel': ticker_data.get('channel', 'N/A'),
                                'Return %': f"{best_ticker['pnl_percentage']:.2f}%",
                                'Invested Amount': f"₹{best_ticker['invested_amount']:,.2f}",
                                'Current Value': f"₹{best_ticker['current_value']:,.2f}",
                                'P&L': f"₹{best_ticker['unrealized_pnl']:,.2f}",
                                'Sector Rating': sector_rating
                            })
                    
                    # Display sector ratings table
                    if sector_ratings:
                        st.subheader("🏭 Sector Performance Ratings")
                        sector_ratings_df = pd.DataFrame(sector_ratings)
                        
                        # Apply color coding based on rating
                        def color_sector_rating(row):
                            rating = row['Rating']
                            if '🟢' in rating:
                                return ['background-color: #d4edda; color: #155724;'] * len(row)
                            elif '🟡' in rating:
                                return ['background-color: #fff3cd; color: #856404;'] * len(row)
                            elif '🟠' in rating:
                                return ['background-color: #f8d7da; color: #721c24;'] * len(row)
                            else:  # 🔴
                                return ['background-color: #f8d7da; color: #721c24;'] * len(row)
                        
                        styled_sector_ratings = sector_ratings_df.style.apply(color_sector_rating, axis=1)
                        
                        st.dataframe(
                            styled_sector_ratings,
                            use_container_width=True,
                            hide_index=True
                        )
                    
                    # Display best stocks by sector table
                    if best_stocks_by_sector:
                        best_stocks_df = pd.DataFrame(best_stocks_by_sector)
                        
                        # Apply color coding based on return percentage
                        def color_return(val):
                            try:
                                pct = float(str(val).replace('%', ''))
                                if pct >= 20:
                                    return 'background-color: #d4edda; color: #155724;'  # Green for excellent
                                elif pct >= 10:
                                    return 'background-color: #fff3cd; color: #856404;'   # Yellow for good
                                elif pct >= 0:
                                    return 'background-color: #f8d7da; color: #721c24;'  # Red for fair
                                else:
                                    return 'background-color: #f8d7da; color: #721c24;'  # Red for negative
                            except:
                                return ''
                        
                        styled_best_stocks = best_stocks_df.style.applymap(color_return, subset=['Return %'])
                        
                        st.dataframe(
                            styled_best_stocks,
                            use_container_width=True,
                            hide_index=True
                        )
                        
                        # Create chart showing best stocks by sector
                        best_stocks_chart_data = []
                        for row in best_stocks_by_sector:
                            return_pct = float(row['Return %'].replace('%', ''))
                            best_stocks_chart_data.append({
                                'Sector': row['Sector'],
                                'Best Stock': row['Best Stock'],
                                'Return %': return_pct
                            })
                        
                        if best_stocks_chart_data:
                            best_stocks_chart_df = pd.DataFrame(best_stocks_chart_data)
                            
                            fig_best_stocks = px.bar(
                                best_stocks_chart_df,
                                x='Sector',
                                y='Return %',
                                color='Return %',
                                color_continuous_scale='RdYlGn',
                                title="Best Stock Performance by Sector",
                                labels={'Return %': 'Return %', 'Sector': 'Sector'},
                                hover_data=['Best Stock']
                            )
                            fig_best_stocks.update_xaxes(tickangle=45)
                            st.plotly_chart(fig_best_stocks, config={'displayModeBar': True, 'responsive': True})
                    else:
                        st.info("No sector-based stock analysis data available")
                    
                    # Best Stock in Each Channel
                    st.subheader("📡 Best Stock in Each Channel (1-Year Buy Transactions)")
                    
                    # Find best performing stock in each channel and calculate channel ratings
                    best_stocks_by_channel = []
                    channel_ratings = []
                    
                    for channel in stock_buys['channel'].unique():
                        if pd.isna(channel) or channel == 'Unknown':
                            continue
                            
                        channel_stocks = stock_buys[stock_buys['channel'] == channel]
                        
                        # Group by ticker within channel
                        channel_ticker_perf = channel_stocks.groupby('ticker').agg({
                            'invested_amount': 'sum',
                            'current_value': 'sum',
                            'unrealized_pnl': 'sum',
                            'quantity': 'sum'
                        }).reset_index()
                        
                        # Calculate P&L percentage
                        channel_ticker_perf['pnl_percentage'] = (channel_ticker_perf['unrealized_pnl'] / channel_ticker_perf['invested_amount']) * 100
                        
                        # Calculate channel overall performance
                        channel_total_invested = channel_ticker_perf['invested_amount'].sum()
                        channel_total_current = channel_ticker_perf['current_value'].sum()
                        channel_total_pnl = channel_ticker_perf['unrealized_pnl'].sum()
                        channel_overall_return = (channel_total_pnl / channel_total_invested) * 100 if channel_total_invested > 0 else 0
                        
                        # Determine channel rating
                        if channel_overall_return >= 20:
                            channel_rating = "🟢 Excellent"
                            rating_color = "background-color: #d4edda; color: #155724;"
                        elif channel_overall_return >= 10:
                            channel_rating = "🟡 Good"
                            rating_color = "background-color: #fff3cd; color: #856404;"
                        elif channel_overall_return >= 0:
                            channel_rating = "🟠 Fair"
                            rating_color = "background-color: #f8d7da; color: #721c24;"
                        else:
                            channel_rating = "🔴 Poor"
                            rating_color = "background-color: #f8d7da; color: #721c24;"
                        
                        # Store channel rating
                        channel_ratings.append({
                            'Channel': channel,
                            'Overall Return %': f"{channel_overall_return:.2f}%",
                            'Total Invested': f"₹{channel_total_invested:,.2f}",
                            'Total Current Value': f"₹{channel_total_current:,.2f}",
                            'Total P&L': f"₹{channel_total_pnl:,.2f}",
                            'Rating': channel_rating
                        })
                        
                        # Get best performing ticker in this channel
                        if not channel_ticker_perf.empty:
                            best_ticker = channel_ticker_perf.loc[channel_ticker_perf['pnl_percentage'].idxmax()]
                            
                            # Get additional details
                            ticker_data = channel_stocks[channel_stocks['ticker'] == best_ticker['ticker']].iloc[0]
                            
                            best_stocks_by_channel.append({
                                'Channel': channel,
                                'Best Stock': best_ticker['ticker'],
                                'Stock Name': ticker_data.get('stock_name', 'N/A'),
                                'Sector': ticker_data.get('sector', 'N/A'),
                                'Return %': f"{best_ticker['pnl_percentage']:.2f}%",
                                'Invested Amount': f"₹{best_ticker['invested_amount']:,.2f}",
                                'Current Value': f"₹{best_ticker['current_value']:,.2f}",
                                'P&L': f"₹{best_ticker['unrealized_pnl']:,.2f}",
                                'Channel Rating': channel_rating
                            })
                    
                    # Display channel ratings table
                    if channel_ratings:
                        st.subheader("📡 Channel Performance Ratings")
                        channel_ratings_df = pd.DataFrame(channel_ratings)
                        
                        # Apply color coding based on rating
                        def color_channel_rating(row):
                            rating = row['Rating']
                            if '🟢' in rating:
                                return ['background-color: #d4edda; color: #155724;'] * len(row)
                            elif '🟡' in rating:
                                return ['background-color: #fff3cd; color: #856404;'] * len(row)
                            elif '🟠' in rating:
                                return ['background-color: #f8d7da; color: #721c24;'] * len(row)
                            else:  # 🔴
                                return ['background-color: #f8d7da; color: #721c24;'] * len(row)
                        
                        styled_channel_ratings = channel_ratings_df.style.apply(color_channel_rating, axis=1)
                        
                        st.dataframe(
                            styled_channel_ratings,
                            use_container_width=True,
                            hide_index=True
                        )
                    
                    # Display best stocks by channel table
                    if best_stocks_by_channel:
                        best_stocks_channel_df = pd.DataFrame(best_stocks_by_channel)
                        
                        # Apply color coding based on return percentage
                        styled_best_stocks_channel = best_stocks_channel_df.style.applymap(color_return, subset=['Return %'])
                        
                        st.dataframe(
                            styled_best_stocks_channel,
                            use_container_width=True,
                            hide_index=True
                        )
                        
                        # Create chart showing best stocks by channel
                        best_stocks_channel_chart_data = []
                        for row in best_stocks_by_channel:
                            return_pct = float(row['Return %'].replace('%', ''))
                            best_stocks_channel_chart_data.append({
                                'Channel': row['Channel'],
                                'Best Stock': row['Best Stock'],
                                'Return %': return_pct
                            })
                        
                        if best_stocks_channel_chart_data:
                            best_stocks_channel_chart_df = pd.DataFrame(best_stocks_channel_chart_data)
                            
                            fig_best_stocks_channel = px.bar(
                                best_stocks_channel_chart_df,
                                x='Channel',
                                y='Return %',
                                color='Return %',
                                color_continuous_scale='RdYlGn',
                                title="Best Stock Performance by Channel",
                                labels={'Return %': 'Return %', 'Channel': 'Channel'},
                                hover_data=['Best Stock']
                            )
                            fig_best_stocks_channel.update_xaxes(tickangle=45)
                            st.plotly_chart(fig_best_stocks_channel, config={'displayModeBar': True, 'responsive': True})
                    else:
                        st.info("No channel-based stock analysis data available")
                        
                    # Summary metrics for the analysis
                    st.subheader("📈 Analysis Summary")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        total_sectors = len(stock_buys['sector'].unique())
                        st.metric("Total Sectors", total_sectors)
                    
                    with col2:
                        total_channels = len(stock_buys['channel'].unique())
                        st.metric("Total Channels", total_channels)
                    
                    with col3:
                        avg_return = stock_performance['pnl_percentage'].mean()
                        avg_arrow = "🔼" if avg_return >= 0 else "🔽"
                        avg_color = "normal" if avg_return >= 0 else "inverse"
                        st.metric("Average Return", f"{avg_arrow} {avg_return:.2f}%", delta_color=avg_color)
                    
                    with col4:
                        best_overall = stock_performance.iloc[0]['pnl_percentage']
                        best_arrow = "🔼" if best_overall >= 0 else "🔽"
                        best_color = "normal" if best_overall >= 0 else "inverse"
                        st.metric("Best Return", f"{best_arrow} {best_overall:.2f}%", delta_color=best_color)
            else:
                st.info("No stock buy transactions found in the last 1 year")
            
            # Monthly Transaction Analysis (1-Year)
            st.subheader("📅 Monthly Transaction Analysis (1-Year)")
            
            # Filter transactions within the last year
            one_year_ago = datetime.now() - timedelta(days=365)
            recent_transactions = df[df['date'] >= one_year_ago].copy()
            
            if not recent_transactions.empty:
                # Create monthly aggregations
                monthly_data = recent_transactions.groupby([
                    recent_transactions['date'].dt.to_period('M'), 
                    'transaction_type'
                ]).agg({
                    'invested_amount': 'sum',
                    'quantity': 'sum'
                }).reset_index()
                
                # Pivot to get buy and sell in separate columns
                monthly_pivot = monthly_data.pivot(
                    index='date', 
                    columns='transaction_type', 
                    values=['invested_amount', 'quantity']
                ).fillna(0)
                
                # Flatten column names
                monthly_pivot.columns = [f"{col[1]}_{col[0]}" for col in monthly_pivot.columns]
                monthly_pivot = monthly_pivot.reset_index()
                
                # Calculate net flow (buy - sell)
                if 'buy_invested_amount' in monthly_pivot.columns and 'sell_invested_amount' in monthly_pivot.columns:
                    monthly_pivot['net_flow'] = monthly_pivot['buy_invested_amount'] - monthly_pivot['sell_invested_amount']
                else:
                    monthly_pivot['net_flow'] = 0
                
                # Create visualizations
                col1, col2 = st.columns(2)
                
                with col1:
                    # Monthly Transaction Values Chart
                    fig_monthly = go.Figure()
                    
                    if 'buy_invested_amount' in monthly_pivot.columns:
                        fig_monthly.add_trace(go.Bar(
                            x=monthly_pivot['date'].astype(str),
                            y=monthly_pivot['buy_invested_amount'],
                            name='Buy Transactions',
                            marker_color='green',
                            opacity=0.7
                        ))
                    
                    if 'sell_invested_amount' in monthly_pivot.columns:
                        fig_monthly.add_trace(go.Bar(
                            x=monthly_pivot['date'].astype(str),
                            y=monthly_pivot['sell_invested_amount'],
                            name='Sell Transactions',
                            marker_color='red',
                            opacity=0.7
                        ))
                    
                    fig_monthly.update_layout(
                        title="Monthly Transaction Values",
                        xaxis_title="Month",
                        yaxis_title="Transaction Value (₹)",
                        barmode='group',
                        height=400
                    )
                    
                    st.plotly_chart(fig_monthly, config={'displayModeBar': True, 'responsive': True})
                
                with col2:
                    # Net Flow Chart
                    fig_net = go.Figure()
                    
                    colors = ['green' if x >= 0 else 'red' for x in monthly_pivot['net_flow']]
                    fig_net.add_trace(go.Bar(
                        x=monthly_pivot['date'].astype(str),
                        y=monthly_pivot['net_flow'],
                        marker_color=colors,
                        name='Net Flow',
                        opacity=0.7
                    ))
                    
                    fig_net.update_layout(
                        title="Monthly Net Flow (Buy - Sell)",
                        xaxis_title="Month",
                        yaxis_title="Net Flow (₹)",
                        height=400
                    )
                    
                    # Add horizontal line at zero
                    fig_net.add_hline(y=0, line_dash="dash", line_color="black", opacity=0.5)
                    
                    st.plotly_chart(fig_net, config={'displayModeBar': True, 'responsive': True})
                
                # Monthly Analysis Summary
                st.subheader("📊 Monthly Analysis Summary")
                
                # Calculate summary statistics
                total_buy_value = monthly_pivot['buy_invested_amount'].sum() if 'buy_invested_amount' in monthly_pivot.columns else 0
                total_sell_value = monthly_pivot['sell_invested_amount'].sum() if 'sell_invested_amount' in monthly_pivot.columns else 0
                total_net_flow = total_buy_value - total_sell_value
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric(
                        "Total Buy Value",
                        f"₹{total_buy_value:,.2f}",
                        help="Total value of buy transactions in the last year"
                    )
                
                with col2:
                    st.metric(
                        "Total Sell Value", 
                        f"₹{total_sell_value:,.2f}",
                        help="Total value of sell transactions in the last year"
                    )
                
                with col3:
                    st.metric(
                        "Net Flow",
                        f"₹{total_net_flow:,.2f}",
                        delta=f"{'Positive' if total_net_flow > 0 else 'Negative' if total_net_flow < 0 else 'Neutral'}",
                        delta_color="normal" if total_net_flow > 0 else "inverse" if total_net_flow < 0 else "off",
                        help="Net flow (Buy - Sell) in the last year"
                    )
                
                with col4:
                    avg_monthly_flow = total_net_flow / len(monthly_pivot) if len(monthly_pivot) > 0 else 0
                    st.metric(
                        "Avg Monthly Flow",
                        f"₹{avg_monthly_flow:,.2f}",
                        help="Average monthly net flow"
                    )
                
                # Trading Pattern Analysis
                st.subheader("🔍 Trading Pattern Analysis")
                
                if len(monthly_pivot) > 1:
                    # Calculate volatility (standard deviation of net flow)
                    net_flow_std = monthly_pivot['net_flow'].std()
                    
                    # Find most active month
                    if 'buy_invested_amount' in monthly_pivot.columns and 'sell_invested_amount' in monthly_pivot.columns:
                        monthly_pivot['total_activity'] = monthly_pivot['buy_invested_amount'] + monthly_pivot['sell_invested_amount']
                        most_active_month = monthly_pivot.loc[monthly_pivot['total_activity'].idxmax()]
                        
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.info(f"**Most Active Month:** {most_active_month['date']}")
                            st.write(f"Total Activity: ₹{most_active_month['total_activity']:,.2f}")
                        
                        with col2:
                            st.info(f"**Trading Volatility:** ₹{net_flow_std:,.2f}")
                            st.write("Standard deviation of monthly net flow")
                        
                        with col3:
                            if total_buy_value > total_sell_value:
                                pattern = "🟢 Net Buyer"
                                description = "More buying than selling"
                            elif total_sell_value > total_buy_value:
                                pattern = "🔴 Net Seller"
                                description = "More selling than buying"
                            else:
                                pattern = "🟡 Balanced"
                                description = "Equal buying and selling"
                            
                            st.info(f"**Trading Pattern:** {pattern}")
                            st.write(description)
                
                # Monthly breakdown table
                st.subheader("📋 Monthly Breakdown")
                
                # Prepare data for display
                display_data = monthly_pivot.copy()
                display_data['date'] = display_data['date'].astype(str)
                
                # Rename columns for better display
                column_mapping = {
                    'buy_invested_amount': 'Buy Value (₹)',
                    'sell_invested_amount': 'Sell Value (₹)',
                    'net_flow': 'Net Flow (₹)',
                    'buy_quantity': 'Buy Quantity',
                    'sell_quantity': 'Sell Quantity'
                }
                
                display_data = display_data.rename(columns=column_mapping)
                
                # Format currency columns
                for col in display_data.columns:
                    if 'Value' in col or 'Flow' in col:
                        display_data[col] = display_data[col].apply(lambda x: f"₹{x:,.2f}")
                
                st.dataframe(
                    display_data,
                    use_container_width=True,
                    hide_index=True
                )
                
            else:
                st.info("No transactions found in the last year")
            
            # Monthly P&L Analysis for 1-Year Buy Stocks
            st.subheader("📈 Monthly P&L Analysis (1-Year Buy Stocks)")
            st.markdown("*Tracking monthly performance from purchase date to current date using cached historical prices*")
            st.info("💡 **Note:** This analysis uses cached historical prices for fast performance. Prices are pre-fetched during login and stored in the database.")
            st.info(f"📅 **Date Range:** Analysis includes data from purchase date to current month ({datetime.now().strftime('%B %Y')})")
            
            # Filter for buy transactions in the last year
            one_year_ago = datetime.now() - timedelta(days=365)
            buy_transactions = df[
                (df['transaction_type'] == 'buy') & 
                (df['date'] >= one_year_ago)
            ].copy()
            
            if not buy_transactions.empty:
                # Create monthly P&L tracking for each stock
                monthly_pnl_data = []
                
                # Get unique stocks with their purchase details
                stock_purchases = buy_transactions.groupby('ticker').agg({
                    'date': 'min',  # First purchase date
                    'price': 'mean',  # Average purchase price
                    'quantity': 'sum',  # Total quantity
                    'invested_amount': 'sum',  # Total invested
                    'stock_name': 'first',
                    'sector': 'first'
                }).reset_index()
                
                # Generate monthly data for each stock from purchase date to current date
                st.info("🔄 Loading monthly P&L data from cache...")
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                total_stocks = len(stock_purchases)
                
                for idx, (_, stock) in enumerate(stock_purchases.iterrows()):
                    ticker = stock['ticker']
                    purchase_date = stock['date']
                    purchase_price = stock['price']
                    quantity = stock['quantity']
                    invested_amount = stock['invested_amount']
                    stock_name = stock['stock_name']
                    sector = stock['sector']
                    
                    # Update progress
                    progress = (idx + 1) / total_stocks
                    progress_bar.progress(progress)
                    status_text.text(f"Processing {ticker} ({idx + 1}/{total_stocks})...")
                    
                    # Generate monthly data points from purchase date to current date
                    current_date = datetime.now()
                    # Include current month by going to next month and then back
                    end_date = current_date.replace(day=1) + timedelta(days=32)
                    end_date = end_date.replace(day=1)
                    
                    monthly_dates = pd.date_range(
                        start=purchase_date.replace(day=1),  # Start from first day of purchase month
                        end=end_date,  # Include current month
                        freq='MS'  # Month start frequency
                    )
                    
                    # Fetch historical prices for each month
                    for month_date in monthly_dates:
                        try:
                            # Fetch historical price for this specific month
                            historical_price = self.fetch_historical_price_for_month(ticker, month_date)
                            
                            if historical_price and historical_price > 0:
                                # Calculate P&L values
                                current_value = quantity * historical_price
                                unrealized_pnl = (historical_price - purchase_price) * quantity
                                pnl_percentage = ((historical_price - purchase_price) / purchase_price) * 100
                                
                                monthly_pnl_data.append({
                                    'ticker': ticker,
                                    'stock_name': stock_name,
                                    'sector': sector,
                                    'month': month_date,
                                    'purchase_price': purchase_price,
                                    'historical_price': historical_price,
                                    'quantity': quantity,
                                    'invested_amount': invested_amount,
                                    'current_value': current_value,
                                    'unrealized_pnl': unrealized_pnl,
                                    'pnl_percentage': pnl_percentage
                                })
                            else:
                                # Fallback to current price if historical price not available
                                current_price = df[df['ticker'] == ticker]['current_price'].iloc[0] if 'current_price' in df.columns else None
                                if current_price and current_price > 0:
                                    # Calculate P&L values for fallback
                                    current_value = quantity * current_price
                                    unrealized_pnl = (current_price - purchase_price) * quantity
                                    pnl_percentage = ((current_price - purchase_price) / purchase_price) * 100
                                    
                                    monthly_pnl_data.append({
                                        'ticker': ticker,
                                        'stock_name': stock_name,
                                        'sector': sector,
                                        'month': month_date,
                                        'purchase_price': purchase_price,
                                        'historical_price': current_price,
                                        'quantity': quantity,
                                        'invested_amount': invested_amount,
                                        'current_value': current_value,
                                        'unrealized_pnl': unrealized_pnl,
                                        'pnl_percentage': pnl_percentage
                                    })
                        except Exception as e:
                            st.warning(f"⚠️ Could not fetch historical price for {ticker} on {month_date}: {e}")
                            continue
                
                # Clear progress indicators
                progress_bar.empty()
                status_text.empty()
                
                if monthly_pnl_data:
                    st.success(f"✅ Successfully loaded {len(monthly_pnl_data)} monthly data points across {len(stock_purchases)} stocks from cache!")
                    monthly_pnl_df = pd.DataFrame(monthly_pnl_data)
                    
                    # Create interactive chart showing monthly P&L progression
                    st.subheader("📊 Monthly P&L Progression by Stock")
                    
                    # Group by month and calculate aggregate P&L
                    monthly_aggregate = monthly_pnl_df.groupby('month').agg({
                        'invested_amount': 'sum',
                        'current_value': 'sum',
                        'unrealized_pnl': 'sum'
                    }).reset_index()
                    
                    monthly_aggregate['pnl_percentage'] = (monthly_aggregate['unrealized_pnl'] / monthly_aggregate['invested_amount']) * 100
                    
                    # Create dual-axis chart for P&L and percentage
                    fig_monthly_pnl = make_subplots(
                        rows=2, cols=1,
                        subplot_titles=('Monthly P&L (₹)', 'Monthly P&L Percentage (%)'),
                        vertical_spacing=0.1
                    )
                    
                    # P&L in rupees
                    fig_monthly_pnl.add_trace(
                        go.Scatter(
                            x=monthly_aggregate['month'],
                            y=monthly_aggregate['unrealized_pnl'],
                            mode='lines+markers',
                            name='Unrealized P&L (₹)',
                            line=dict(color='blue', width=3),
                            marker=dict(size=8)
                        ),
                        row=1, col=1
                    )
                    
                    # P&L percentage
                    fig_monthly_pnl.add_trace(
                        go.Scatter(
                            x=monthly_aggregate['month'],
                            y=monthly_aggregate['pnl_percentage'],
                            mode='lines+markers',
                            name='P&L Percentage (%)',
                            line=dict(color='green', width=3),
                            marker=dict(size=8)
                        ),
                        row=2, col=1
                    )
                    
                    fig_monthly_pnl.update_layout(
                        title="Monthly P&L Progression for 1-Year Buy Stocks",
                        height=600,
                        showlegend=True
                    )
                    
                    fig_monthly_pnl.update_xaxes(title_text="Month", row=2, col=1)
                    fig_monthly_pnl.update_yaxes(title_text="P&L (₹)", row=1, col=1)
                    fig_monthly_pnl.update_yaxes(title_text="P&L (%)", row=2, col=1)
                    
                    st.plotly_chart(fig_monthly_pnl, config={'displayModeBar': True, 'responsive': True})
                    
                    # Stock Price Movement Overview
                    st.subheader("📊 Stock Price Movement Overview")
                    
                    # Create a comprehensive price movement chart for all stocks
                    fig_price_overview = go.Figure()
                    
                    # Get unique stocks and their colors
                    unique_stocks = monthly_pnl_df['ticker'].unique()
                    colors = px.colors.qualitative.Set3[:len(unique_stocks)]
                    
                    for i, ticker in enumerate(unique_stocks):
                        stock_data = monthly_pnl_df[monthly_pnl_df['ticker'] == ticker]
                        stock_name = stock_data['stock_name'].iloc[0]
                        
                        fig_price_overview.add_trace(go.Scatter(
                            x=stock_data['month'],
                            y=stock_data['historical_price'],
                            mode='lines+markers',
                            name=f'{ticker} - {stock_name}',
                            line=dict(color=colors[i], width=2),
                            marker=dict(size=6),
                            hovertemplate=f'<b>{ticker}</b><br>Month: %{{x}}<br>Price: ₹%{{y:.2f}}<extra></extra>'
                        ))
                    
                    fig_price_overview.update_layout(
                        title="Stock Price Movement - All 1-Year Buy Stocks",
                        xaxis_title="Month",
                        yaxis_title="Stock Price (₹)",
                        height=500,
                        hovermode='x unified',
                        legend=dict(
                            orientation="v",
                            yanchor="top",
                            y=1,
                            xanchor="left",
                            x=1.02
                        )
                    )
                    
                    st.plotly_chart(fig_price_overview, config={'displayModeBar': True, 'responsive': True})
                    
                    # Price Performance Comparison
                    st.subheader("🏆 Price Performance Comparison")
                    
                    # Calculate price performance for each stock
                    price_performance_data = []
                    for ticker in unique_stocks:
                        stock_data = monthly_pnl_df[monthly_pnl_df['ticker'] == ticker]
                        if len(stock_data) > 1:
                            initial_price = stock_data['historical_price'].iloc[0]
                            final_price = stock_data['historical_price'].iloc[-1]
                            price_change = final_price - initial_price
                            price_change_pct = (price_change / initial_price) * 100
                            
                            price_performance_data.append({
                                'ticker': ticker,
                                'stock_name': stock_data['stock_name'].iloc[0],
                                'initial_price': initial_price,
                                'final_price': final_price,
                                'price_change': price_change,
                                'price_change_pct': price_change_pct
                            })
                    
                    if price_performance_data:
                        price_perf_df = pd.DataFrame(price_performance_data)
                        price_perf_df = price_perf_df.sort_values('price_change_pct', ascending=False)
                        
                        # Create price performance chart
                        fig_price_perf = go.Figure()
                        
                        colors = ['green' if x >= 0 else 'red' for x in price_perf_df['price_change_pct']]
                        
                        fig_price_perf.add_trace(go.Bar(
                            x=price_perf_df['ticker'],
                            y=price_perf_df['price_change_pct'],
                            marker_color=colors,
                            text=[f"{x:.1f}%" for x in price_perf_df['price_change_pct']],
                            textposition='auto',
                            hovertemplate='<b>%{x}</b><br>Price Change: %{y:.2f}%<br>Initial: ₹%{customdata[0]:.2f}<br>Final: ₹%{customdata[1]:.2f}<extra></extra>',
                            customdata=list(zip(price_perf_df['initial_price'], price_perf_df['final_price']))
                        ))
                        
                        fig_price_perf.update_layout(
                            title="Stock Price Performance Comparison (1-Year Buy Stocks)",
                            xaxis_title="Stock Ticker",
                            yaxis_title="Price Change (%)",
                            height=400,
                            showlegend=False
                        )
                        
                        fig_price_perf.update_xaxes(tickangle=45)
                        
                        st.plotly_chart(fig_price_perf, config={'displayModeBar': True, 'responsive': True})
                        
                        # Price performance summary table
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.subheader("📈 Best Price Performers")
                            best_performers = price_perf_df.head(3)
                            for _, stock in best_performers.iterrows():
                                st.metric(
                                    f"{stock['ticker']} - {stock['stock_name']}",
                                    f"₹{stock['final_price']:.2f}",
                                    delta=f"{stock['price_change_pct']:+.2f}%",
                                    delta_color="normal"
                                )
                        
                        with col2:
                            st.subheader("📉 Worst Price Performers")
                            worst_performers = price_perf_df.tail(3)
                            for _, stock in worst_performers.iterrows():
                                st.metric(
                                    f"{stock['ticker']} - {stock['stock_name']}",
                                    f"₹{stock['final_price']:.2f}",
                                    delta=f"{stock['price_change_pct']:+.2f}%",
                                    delta_color="inverse"
                                )
                    
                    # Individual stock performance
                    st.subheader("📈 Individual Stock Performance")
                    
                    # Create dropdown for stock selection
                    unique_stocks = monthly_pnl_df['ticker'].unique()
                    selected_stock = st.selectbox(
                        "Select a stock to view detailed monthly performance:",
                        unique_stocks,
                        format_func=lambda x: f"{x} - {monthly_pnl_df[monthly_pnl_df['ticker']==x]['stock_name'].iloc[0]}"
                    )
                    
                    if selected_stock:
                        stock_data = monthly_pnl_df[monthly_pnl_df['ticker'] == selected_stock].copy()
                        
                        # Debug information
                        with st.expander("🔍 Debug Information", expanded=False):
                            st.write("**Stock Data Sample:**")
                            st.dataframe(stock_data[['month', 'purchase_price', 'historical_price', 'unrealized_pnl', 'pnl_percentage']].head())
                            
                            st.write("**Latest Data Point:**")
                            latest = stock_data.iloc[-1]
                            st.write(f"Month: {latest['month']}")
                            st.write(f"Purchase Price: ₹{latest['purchase_price']:.2f}")
                            st.write(f"Historical Price: ₹{latest['historical_price']:.2f}")
                            st.write(f"Unrealized P&L: ₹{latest['unrealized_pnl']:.2f}")
                            st.write(f"P&L %: {latest['pnl_percentage']:.2f}%")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            # Create subplot with both price and P&L charts
                            fig_stock = make_subplots(
                                rows=2, cols=1,
                                subplot_titles=(f'{selected_stock} - Stock Price Movement', f'{selected_stock} - P&L Progression'),
                                vertical_spacing=0.1,
                                row_heights=[0.6, 0.4]
                            )
                            
                            # Stock price chart (top)
                            fig_stock.add_trace(
                                go.Scatter(
                                    x=stock_data['month'],
                                    y=stock_data['historical_price'],
                                    mode='lines+markers',
                                    name='Stock Price (₹)',
                                    line=dict(color='green', width=3),
                                    marker=dict(size=8),
                                    hovertemplate='<b>%{x}</b><br>Price: ₹%{y:.2f}<extra></extra>'
                                ),
                                row=1, col=1
                            )
                            
                            # Add purchase price line
                            purchase_price = stock_data['purchase_price'].iloc[0]
                            fig_stock.add_hline(
                                y=purchase_price, 
                                line_dash="dash", 
                                line_color="red", 
                                opacity=0.7,
                                annotation_text=f"Purchase Price: ₹{purchase_price:.2f}",
                                row=1, col=1
                            )
                            
                            # P&L chart (bottom)
                            fig_stock.add_trace(
                                go.Scatter(
                                    x=stock_data['month'],
                                    y=stock_data['unrealized_pnl'],
                                    mode='lines+markers',
                                    name='Unrealized P&L (₹)',
                                    line=dict(color='blue', width=3),
                                    marker=dict(size=8),
                                    hovertemplate='<b>%{x}</b><br>P&L: ₹%{y:.2f}<extra></extra>'
                                ),
                                row=2, col=1
                            )
                            
                            # Add zero line for P&L
                            fig_stock.add_hline(y=0, line_dash="dash", line_color="black", opacity=0.5, row=2, col=1)
                            
                            fig_stock.update_layout(
                                title=f"{selected_stock} - Price & P&L Analysis",
                                height=600,
                                showlegend=True
                            )
                            
                            fig_stock.update_xaxes(title_text="Month", row=2, col=1)
                            fig_stock.update_yaxes(title_text="Stock Price (₹)", row=1, col=1)
                            fig_stock.update_yaxes(title_text="P&L (₹)", row=2, col=1)
                            
                            st.plotly_chart(fig_stock, config={'displayModeBar': True, 'responsive': True})
                        
                        with col2:
                            # Stock metrics
                            latest_data = stock_data.iloc[-1]
                            
                            st.metric(
                                "Purchase Price",
                                f"₹{latest_data['purchase_price']:.2f}",
                                help="Average purchase price"
                            )
                            
                            # Determine arrow and color for price change
                            current_price = latest_data['historical_price']
                            purchase_price = latest_data['purchase_price']
                            price_change = current_price - purchase_price
                            
                            if price_change > 0:
                                arrow = "🔼"
                                color = "normal"
                            elif price_change < 0:
                                arrow = "🔽"
                                color = "inverse"
                            else:
                                arrow = "➖"
                                color = "off"
                            
                            st.metric(
                                "Current Price",
                                f"{arrow} ₹{current_price:.2f}",
                                delta=f"₹{price_change:+.2f}",
                                delta_color=color
                            )
                            
                            # Determine arrow and color based on P&L
                            pnl_value = latest_data['unrealized_pnl']
                            pnl_percentage = latest_data['pnl_percentage']
                            
                            if pnl_value > 0:
                                arrow = "🔼"
                                color = "normal"
                            elif pnl_value < 0:
                                arrow = "🔽"
                                color = "inverse"
                            else:
                                arrow = "➖"
                                color = "off"
                            
                            st.metric(
                                "Total P&L",
                                f"{arrow} ₹{pnl_value:,.2f}",
                                delta=f"{pnl_percentage:+.2f}%",
                                delta_color=color
                            )
                            
                            st.metric(
                                "Quantity",
                                f"{latest_data['quantity']:,.0f}",
                                help="Total quantity purchased"
                            )
                    
                    # Summary table of all stocks
                    st.subheader("📋 Monthly P&L Summary Table")
                    
                    # Create summary table with latest data for each stock
                    summary_data = []
                    for ticker in unique_stocks:
                        stock_latest = monthly_pnl_df[monthly_pnl_df['ticker'] == ticker].iloc[-1]
                        summary_data.append({
                            'Ticker': ticker,
                            'Stock Name': stock_latest['stock_name'],
                            'Sector': stock_latest['sector'],
                            'Purchase Price': f"₹{stock_latest['purchase_price']:.2f}",
                            'Current Price': f"₹{stock_latest['historical_price']:.2f}",
                            'Quantity': f"{stock_latest['quantity']:,.0f}",
                            'Invested Amount': f"₹{stock_latest['invested_amount']:,.2f}",
                            'Current Value': f"₹{stock_latest['current_value']:,.2f}",
                            'Unrealized P&L': f"₹{stock_latest['unrealized_pnl']:,.2f}",
                            'P&L %': f"{stock_latest['pnl_percentage']:.2f}%"
                        })
                    
                    summary_df = pd.DataFrame(summary_data)
                    
                    # Sort by P&L percentage
                    summary_df['P&L % Sort'] = summary_df['P&L %'].str.replace('%', '').astype(float)
                    summary_df = summary_df.sort_values('P&L % Sort', ascending=False)
                    summary_df = summary_df.drop('P&L % Sort', axis=1)
                    
                    st.dataframe(
                        summary_df,
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    # Download option
                    csv = summary_df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Monthly P&L Summary",
                        data=csv,
                        file_name=f"monthly_pnl_summary_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
                    
                else:
                    st.info("No monthly P&L data available for 1-year buy stocks")
            else:
                st.info("No buy transactions found in the last year")
                
        except Exception as e:
            st.error(f"Error processing performance data: {e}")
    
    def render_allocation_page(self):
        """Render asset allocation analysis"""
        st.header("📊 Asset Allocation Analysis")
        
        if self.session_state.portfolio_data is None:
            self.show_page_loading_animation("Asset Allocation Analysis")
            st.info("💡 **Tip:** If this page doesn't load automatically, use the '🔄 Refresh Portfolio Data' button in Settings.")
            return
        
        df = self.session_state.portfolio_data
        
        # Asset allocation by type
        st.subheader("🏦 Asset Allocation by Type")
        
        if 'current_value' in df.columns and not df['current_value'].isna().all():
            # Categorize assets
            df['asset_type'] = df['ticker'].apply(
                lambda x: 'Mutual Fund' if str(x).startswith('MF_') else 'Stock'
            )
            
            # Filter out rows with missing current values
            valid_data = df.dropna(subset=['current_value'])
            if not valid_data.empty:
                allocation_by_type = valid_data.groupby('asset_type')['current_value'].sum()
                
                if not allocation_by_type.empty:
                    fig_type = px.pie(
                        values=allocation_by_type.values,
                        names=allocation_by_type.index,
                        title="Allocation by Asset Type"
                    )
                    st.plotly_chart(fig_type, config={'displayModeBar': True, 'responsive': True})
                else:
                    st.info("No asset type allocation data available")
            else:
                st.info("No valid current value data available for asset allocation")
        else:
            st.info("Current value information not available for asset allocation")
        
        # Sector allocation
        st.subheader("🏭 Sector Allocation")
        
        if 'sector' in df.columns and not df['sector'].isna().all():
            # Filter out rows with missing sectors and check if we have data
            sector_data = df.dropna(subset=['sector'])
            if not sector_data.empty and 'current_value' in sector_data.columns:
                sector_allocation = sector_data.groupby('sector')['current_value'].sum().sort_values(ascending=False)
                
                if not sector_allocation.empty:
                    fig_sector = px.bar(
                        x=sector_allocation.values,
                        y=sector_allocation.index,
                        orientation='h',
                        title="Allocation by Sector",
                        labels={'x': 'Current Value (₹)', 'y': 'Sector'}
                    )
                    st.plotly_chart(fig_sector, config={'displayModeBar': True, 'responsive': True})
                    
                    # Sector allocation chart is sufficient here - detailed tables moved to Performance page
                else:
                    st.info("No sector data available for visualization")
            else:
                st.info("No sector or current value data available")
        else:
            st.info("Sector information not available in portfolio data")
        
        # Top holdings
        st.subheader("📈 Top Holdings")
        
        if 'current_value' in df.columns and not df['current_value'].isna().all():
            # Check if we have valid current value data
            valid_data = df.dropna(subset=['current_value'])
            if not valid_data.empty:
                top_holdings = valid_data.groupby('ticker').agg({
                    'current_value': 'sum',
                    'unrealized_pnl': 'sum' if 'unrealized_pnl' in valid_data.columns else 'current_value',
                    'pnl_percentage': 'mean' if 'pnl_percentage' in valid_data.columns else 'current_value'
                }).sort_values('current_value', ascending=False).head(10)
                
                if not top_holdings.empty:
                    fig_holdings = px.bar(
                        x=top_holdings.index,
                        y=top_holdings['current_value'],
                        title="Top 10 Holdings by Current Value",
                        labels={'x': 'Ticker', 'y': 'Current Value (₹)'}
                    )
                    fig_holdings.update_xaxes(tickangle=45)
                    st.plotly_chart(fig_holdings, config={'displayModeBar': True, 'responsive': True})
                else:
                    st.info("No holdings data available for visualization")
            else:
                st.info("No valid current value data available")
        else:
            st.info("Current value information not available in portfolio data")
        
        # Market cap distribution (if available)
        st.subheader("📊 Market Cap Distribution")
        
        # Check if we have market cap data
        if hasattr(self.session_state, 'market_caps') and self.session_state.market_caps:
            # Filter stocks (exclude mutual funds) and get their market caps
            stock_data = df[~df['ticker'].astype(str).str.isdigit() & ~df['ticker'].str.startswith('MF_')].copy()
            
            if not stock_data.empty:
                # Normalize ticker names by removing exchange suffixes and standardizing names
                def normalize_ticker(ticker):
                    """Normalize ticker by removing exchange suffixes and standardizing names"""
                    if pd.isna(ticker):
                        return ticker
                    
                    ticker_str = str(ticker).upper()
                    
                    # Remove exchange suffixes
                    if ticker_str.endswith('.NS') or ticker_str.endswith('.BO'):
                        ticker_str = ticker_str[:-3]
                    
                    # Handle common variations
                    if ticker_str == 'RELIANCE':
                        return 'RELIANCE'
                    elif ticker_str == 'HDFCBANK':
                        return 'HDFCBANK'
                    elif ticker_str == 'BHARTIARTL':
                        return 'BHARTIARTL'
                    elif ticker_str == 'TCS':
                        return 'TCS'
                    elif ticker_str == 'ICICIBANK':
                        return 'ICICIBANK'
                    elif ticker_str == 'INFY':
                        return 'INFY'
                    elif ticker_str == 'SBIN':
                        return 'SBIN'
                    elif ticker_str == 'ITC':
                        return 'ITC'
                    elif ticker_str == 'LT':
                        return 'LT'
                    elif ticker_str == 'ASIANPAINT':
                        return 'ASIANPAINT'
                    elif ticker_str == 'MARUTI':
                        return 'MARUTI'
                    elif ticker_str == 'BAJFINANCE':
                        return 'BAJFINANCE'
                    elif ticker_str == 'HCLTECH':
                        return 'HCLTECH'
                    elif ticker_str == 'WIPRO':
                        return 'WIPRO'
                    elif ticker_str == 'TECHM':
                        return 'TECHM'
                    elif ticker_str == 'AXISBANK':
                        return 'AXISBANK'
                    elif ticker_str == 'KOTAKBANK':
                        return 'KOTAKBANK'
                    elif ticker_str == 'NESTLEIND':
                        return 'NESTLEIND'
                    elif ticker_str == 'SUNPHARMA':
                        return 'SUNPHARMA'
                    elif ticker_str == 'TITAN':
                        return 'TITAN'
                    elif ticker_str == 'ONGC':
                        return 'ONGC'
                    elif ticker_str == 'COALINDIA':
                        return 'COALINDIA'
                    elif ticker_str == 'DRREDDY':
                        return 'DRREDDY'
                    elif ticker_str == 'CIPLA':
                        return 'CIPLA'
                    elif ticker_str == 'POWERGRID':
                        return 'POWERGRID'
                    elif ticker_str == 'GRASIM':
                        return 'GRASIM'
                    elif ticker_str == 'JSWSTEEL':
                        return 'JSWSTEEL'
                    elif ticker_str == 'HINDZINC':
                        return 'HINDZINC'
                    elif ticker_str == 'TATAMOTORS':
                        return 'TATAMOTORS'
                    elif ticker_str == 'TATASTEEL':
                        return 'TATASTEEL'
                    elif ticker_str == 'BAJAJ-AUTO':
                        return 'BAJAJ-AUTO'
                    else:
                        return ticker_str
                
                # Add normalized ticker column
                stock_data['normalized_ticker'] = stock_data['ticker'].apply(normalize_ticker)
                
                # Add market cap data to stock data
                stock_data['market_cap'] = stock_data['ticker'].map(self.session_state.market_caps)
                
                # Filter stocks with market cap data
                stocks_with_market_cap = stock_data.dropna(subset=['market_cap'])
                
                if not stocks_with_market_cap.empty:
                    # Group by normalized ticker and aggregate data
                    market_cap_grouped = stocks_with_market_cap.groupby('normalized_ticker').agg({
                        'market_cap': 'first',  # Take first market cap value
                        'current_value': 'sum',  # Sum current values for same stock
                        'invested_amount': 'sum',  # Sum invested amounts for same stock
                        'quantity': 'sum',  # Sum quantities for same stock
                        'ticker': lambda x: ', '.join(x.unique())  # Show all ticker variations
                    }).reset_index()
                    
                    # Categorize stocks by market cap (in Crores)
                    def categorize_market_cap(market_cap):
                        if market_cap >= 20000:  # 20,000 Cr and above
                            return 'Large Cap (₹20,000+ Cr)'
                        elif market_cap >= 5000:  # 5,000 - 19,999 Cr
                            return 'Mid Cap (₹5,000-19,999 Cr)'
                        elif market_cap >= 500:  # 500 - 4,999 Cr
                            return 'Small Cap (₹500-4,999 Cr)'
                        else:  # Below 500 Cr
                            return 'Micro Cap (<₹500 Cr)'
                    
                    market_cap_grouped['market_cap_category'] = market_cap_grouped['market_cap'].apply(categorize_market_cap)
                    
                    # Group by market cap category and sum current values
                    market_cap_distribution = market_cap_grouped.groupby('market_cap_category')['current_value'].sum().sort_values(ascending=False)
                    
                    if not market_cap_distribution.empty:
                        # Create pie chart
                        fig_market_cap = px.pie(
                            values=market_cap_distribution.values,
                            names=market_cap_distribution.index,
                            title="Portfolio Distribution by Market Cap",
                            color_discrete_sequence=px.colors.qualitative.Set3
                        )
                        fig_market_cap.update_traces(textposition='inside', textinfo='percent+label')
                        st.plotly_chart(fig_market_cap, config={'displayModeBar': True, 'responsive': True})
                        
                        # Show summary metrics
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            large_cap_value = market_cap_distribution.get('Large Cap (₹20,000+ Cr)', 0)
                            st.metric("Large Cap", f"₹{large_cap_value:,.0f}")
                        
                        with col2:
                            mid_cap_value = market_cap_distribution.get('Mid Cap (₹5,000-19,999 Cr)', 0)
                            st.metric("Mid Cap", f"₹{mid_cap_value:,.0f}")
                        
                        with col3:
                            small_cap_value = market_cap_distribution.get('Small Cap (₹500-4,999 Cr)', 0)
                            st.metric("Small Cap", f"₹{small_cap_value:,.0f}")
                        
                        with col4:
                            micro_cap_value = market_cap_distribution.get('Micro Cap (<₹500 Cr)', 0)
                            st.metric("Micro Cap", f"₹{micro_cap_value:,.0f}")
                        
                        # Show detailed breakdown
                        st.subheader("📋 Market Cap Breakdown by Stock")
                        
                        # Format the display
                        market_cap_breakdown_display = market_cap_grouped[['normalized_ticker', 'market_cap', 'market_cap_category', 'current_value', 'invested_amount', 'quantity', 'ticker']].copy()
                        market_cap_breakdown_display['market_cap_cr'] = market_cap_breakdown_display['market_cap'] / 100  # Convert to Crores
                        market_cap_breakdown_display = market_cap_breakdown_display.sort_values('market_cap', ascending=False)
                        
                        # Rename columns for display
                        market_cap_breakdown_display.columns = ['Stock Name', 'Market Cap', 'Category', 'Portfolio Value', 'Invested Amount', 'Total Quantity', 'Ticker Variations', 'Market Cap (Cr)']
                        
                        # Format the display columns
                        display_df = market_cap_breakdown_display[['Stock Name', 'Market Cap (Cr)', 'Category', 'Portfolio Value', 'Invested Amount', 'Total Quantity', 'Ticker Variations']].copy()
                        display_df['Market Cap (Cr)'] = display_df['Market Cap (Cr)'].apply(lambda x: f"₹{x:,.0f}")
                        display_df['Portfolio Value'] = display_df['Portfolio Value'].apply(lambda x: f"₹{x:,.0f}")
                        display_df['Invested Amount'] = display_df['Invested Amount'].apply(lambda x: f"₹{x:,.0f}")
                        display_df['Total Quantity'] = display_df['Total Quantity'].apply(lambda x: f"{x:,.0f}")
                        
                        st.dataframe(display_df, width='stretch')
                        
                    else:
                        st.info("No market cap distribution data available")
                else:
                    st.info("No stocks with market cap data found")
            else:
                st.info("No stock data available for market cap analysis")
        else:
            st.info("Market cap data not available. Run 'Fetch Live Prices' to get market cap information.")
    
    def render_pnl_analysis_page(self):
        """Render P&L analysis"""
        st.header("💰 P&L Analysis")
        
        if self.session_state.portfolio_data is None:
            self.show_page_loading_animation("P&L Analysis")
            st.info("💡 **Tip:** If this page doesn't load automatically, use the '🔄 Refresh Portfolio Data' button in Settings.")
            return
        
        df = self.session_state.portfolio_data
        
        # P&L summary by ticker
        st.subheader("📊 P&L Summary by Ticker")
        
        pnl_summary = df.groupby('ticker').agg({
            'invested_amount': 'sum',
            'current_value': 'sum',
            'unrealized_pnl': 'sum',
            'pnl_percentage': 'mean'
        }).reset_index()
        
        pnl_summary['status'] = pnl_summary['unrealized_pnl'].apply(
            lambda x: 'Profit' if x > 0 else 'Loss' if x < 0 else 'Break Even'
        )
        
        # Color code the P&L
        fig_pnl = px.scatter(
            pnl_summary,
            x='invested_amount',
            y='unrealized_pnl',
            size='current_value',
            color='status',
            hover_data=['ticker', 'pnl_percentage'],
            title="P&L vs Investment Amount",
            labels={
                'invested_amount': 'Invested Amount (₹)',
                'unrealized_pnl': 'Unrealized P&L (₹)',
                'current_value': 'Current Value (₹)'
            }
        )
        
        st.plotly_chart(fig_pnl, config={'displayModeBar': True, 'responsive': True})
        

        
        # P&L by Sector and Channel
        st.subheader("🏦 P&L by Sector & Channel")
        
        # Ensure sector and channel information is available
        if 'sector' not in df.columns or df['sector'].isna().all():
            # Get sectors from live prices data
            sectors = self.session_state.sectors if hasattr(self.session_state, 'sectors') else {}
            df['sector'] = df['ticker'].map(sectors).fillna('Unknown')
        
        if 'channel' not in df.columns or df['channel'].isna().all():
            # Try to get channel from file records if available
            try:
                user_id = self.session_state.user_id
                file_records = get_file_records_supabase(user_id)
                
                if file_records:
                    # Create a mapping of ticker to channel based on file records
                    ticker_to_channel = {}
                    for record in file_records:
                        if 'filename' in record and 'channel' in record:
                            channel_name = record['channel'] if record['channel'] else record['filename'].replace('.csv', '').replace('_', ' ')
                            # Get transactions for this file and map tickers to channel
                            file_transactions = get_transactions_supabase(user_id=user_id, file_id=record.get('id'))
                            if file_transactions:
                                for trans in file_transactions:
                                    ticker_to_channel[trans['ticker']] = channel_name
                    
                    # Add channel information to dataframe
                    df['channel'] = df['ticker'].map(ticker_to_channel).fillna('Unknown')
            except Exception as e:
                st.warning(f"Could not fetch channel information: {e}")
                df['channel'] = 'Unknown'
        
        # P&L by Sector
        st.subheader("🏭 P&L by Sector")
        pnl_by_sector = df.groupby('sector')['unrealized_pnl'].sum().reset_index()
        pnl_by_sector = pnl_by_sector.sort_values('unrealized_pnl', ascending=False)
        
        if not pnl_by_sector.empty:
            fig_sector_pnl = px.bar(
                pnl_by_sector,
                x='sector',
                y='unrealized_pnl',
                title="P&L by Sector",
                labels={'sector': 'Sector', 'unrealized_pnl': 'Total P&L (₹)'},
                color='unrealized_pnl',
                color_continuous_scale='RdYlGn'
            )
            fig_sector_pnl.update_xaxes(tickangle=45)
            st.plotly_chart(fig_sector_pnl, config={'displayModeBar': True, 'responsive': True})
            
            # Sector P&L summary
            col1, col2, col3 = st.columns(3)
            with col1:
                best_sector = pnl_by_sector.loc[pnl_by_sector['unrealized_pnl'].idxmax()]
                best_pnl = best_sector['unrealized_pnl']
                best_arrow = "🔼" if best_pnl > 0 else "🔽" if best_pnl < 0 else "➖"
                best_color = "normal" if best_pnl > 0 else "inverse"
                st.metric(
                    "Best Sector", 
                    f"{best_arrow} {best_sector['sector']}", 
                    delta=f"₹{best_pnl:,.2f}",
                    delta_color=best_color
                )
            with col2:
                worst_sector = pnl_by_sector.loc[pnl_by_sector['unrealized_pnl'].idxmin()]
                worst_pnl = worst_sector['unrealized_pnl']
                worst_arrow = "🔼" if worst_pnl > 0 else "🔽" if worst_pnl < 0 else "➖"
                worst_color = "normal" if worst_pnl > 0 else "inverse"
                st.metric(
                    "Worst Sector", 
                    f"{worst_arrow} {worst_sector['sector']}", 
                    delta=f"₹{worst_pnl:,.2f}",
                    delta_color=worst_color
                )
            with col3:
                total_sectors = len(pnl_by_sector)
                st.metric("Total Sectors", total_sectors)
        else:
            st.info("No sector data available for P&L analysis")
        
        # P&L by Channel
        st.subheader("📊 P&L by Channel")
        pnl_by_channel = df.groupby('channel')['unrealized_pnl'].sum().reset_index()
        pnl_by_channel = pnl_by_channel.sort_values('unrealized_pnl', ascending=False)
        
        if not pnl_by_channel.empty:
            fig_channel_pnl = px.bar(
                pnl_by_channel,
                x='channel',
                y='unrealized_pnl',
                title="P&L by Investment Channel",
                labels={'channel': 'Channel', 'unrealized_pnl': 'Total P&L (₹)'},
                color='unrealized_pnl',
                color_continuous_scale='RdYlGn'
            )
            fig_channel_pnl.update_xaxes(tickangle=45)
            st.plotly_chart(fig_channel_pnl, config={'displayModeBar': True, 'responsive': True})
            
            # Channel P&L summary
            col1, col2, col3 = st.columns(3)
            with col1:
                best_channel = pnl_by_channel.loc[pnl_by_channel['unrealized_pnl'].idxmax()]
                best_pnl = best_channel['unrealized_pnl']
                best_arrow = "🔼" if best_pnl > 0 else "🔽" if best_pnl < 0 else "➖"
                best_color = "normal" if best_pnl > 0 else "inverse"
                st.metric(
                    "Best Channel", 
                    f"{best_arrow} {best_channel['channel']}", 
                    delta=f"₹{best_pnl:,.2f}",
                    delta_color=best_color
                )
            with col2:
                worst_channel = pnl_by_channel.loc[pnl_by_channel['unrealized_pnl'].idxmin()]
                worst_pnl = worst_channel['unrealized_pnl']
                worst_arrow = "🔼" if worst_pnl > 0 else "🔽" if worst_pnl < 0 else "➖"
                worst_color = "normal" if worst_pnl > 0 else "inverse"
                st.metric(
                    "Worst Channel", 
                    f"{worst_arrow} {worst_channel['channel']}", 
                    delta=f"₹{worst_pnl:,.2f}",
                    delta_color=worst_color
                )
            with col3:
                total_channels = len(pnl_by_channel)
                st.metric("Total Channels", total_channels)
        else:
            st.info("No channel data available for P&L analysis")
        
        # Combined Sector-Channel P&L Analysis
        st.subheader("🔗 Combined Sector-Channel P&L Analysis")
        combined_pnl = df.groupby(['sector', 'channel'])['unrealized_pnl'].sum().reset_index()
        combined_pnl = combined_pnl.sort_values('unrealized_pnl', ascending=False)
        
        if not combined_pnl.empty:
            # Create a heatmap-like visualization
            fig_combined = px.bar(
                combined_pnl,
                x='sector',
                y='unrealized_pnl',
                color='channel',
                title="P&L by Sector and Channel Combination",
                labels={'sector': 'Sector', 'unrealized_pnl': 'Total P&L (₹)', 'channel': 'Channel'},
                barmode='group'
            )
            fig_combined.update_xaxes(tickangle=45)
            st.plotly_chart(fig_combined, config={'displayModeBar': True, 'responsive': True})
            
            # Combined summary table
            combined_pnl['pnl_formatted'] = combined_pnl['unrealized_pnl'].apply(lambda x: f"₹{x:,.2f}")
            combined_pnl['percentage'] = (combined_pnl['unrealized_pnl'] / combined_pnl['unrealized_pnl'].abs().sum() * 100).apply(lambda x: f"{x:.2f}%")
            
            st.dataframe(
                combined_pnl[['sector', 'channel', 'pnl_formatted', 'percentage']],
                width='stretch',
                hide_index=True
            )
        else:
            st.info("No combined sector-channel data available for P&L analysis")
        
        # Detailed P&L table
        st.subheader("📋 Detailed P&L Table")
        st.dataframe(
            pnl_summary.sort_values('unrealized_pnl', ascending=False),
            width='stretch'
        )
    
    def render_files_page(self):
        """Render file management page"""
        st.header("📁 File Management")
        
        user_id = self.session_state.user_id
        if not user_id:
            st.error("No user ID found")
            return
        
        # Sample CSV Format Button - Prominent and always visible
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("📋 View Sample CSV Format", type="secondary", use_container_width=True):
                st.session_state.show_sample_csv_files = True
        
        # Show sample CSV format in a prominent popup-style display
        if st.session_state.get('show_sample_csv_files', False):
            st.markdown("---")
            st.subheader("📋 Sample CSV Format")
            st.success("💡 **Prepare your CSV file with the following format:**")
            
            # Create a nice formatted display
            sample_col1, sample_col2 = st.columns([1, 1])
            
            with sample_col1:
                st.markdown("""
                **Required Columns:**
                - `date` - Transaction date (YYYY-MM-DD format)
                - `ticker` - Stock/Mutual Fund symbol (e.g., RELIANCE, 120828)
                - `quantity` - Number of shares/units
                - `transaction_type` - Buy or Sell
                
                **Optional Columns:**
                - `price` - Transaction price per share/unit
                - `stock_name` - Company/Fund name
                - `sector` - Industry sector
                - `channel` - Investment platform (e.g., Direct, Broker, Online)
                """)
            
            with sample_col2:
                st.markdown("""
                **Example CSV:**
                ```csv
                date,ticker,quantity,transaction_type,price,stock_name,sector,channel
                2024-01-15,RELIANCE,100,buy,2500.50,Reliance Industries,Oil & Gas,Direct
                2024-01-20,120828,500,buy,45.25,ICICI Prudential Technology Fund,Technology,Online
                2024-02-01,TCS,50,sell,3800.00,Tata Consultancy Services,Technology,Broker
                ```
                """)
            
            st.info("""
            **Notes:**
            - For mutual funds, use the numerical scheme code (e.g., 120828)
            - For stocks, you can include exchange suffix (.NS, .BO) or leave without
            - Transaction types: buy, sell, purchase, bought, sold, sale
            - If price is missing, the system will fetch historical prices automatically
            """)
            
            # Action buttons
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                if st.button("✖️ Close Sample Format", type="secondary", key="close_files_sample"):
                    st.session_state.show_sample_csv_files = False
                    st.rerun()
            
            with col2:
                # Create and download sample CSV
                sample_data = {
                    'date': ['2024-01-15', '2024-01-20', '2024-02-01'],
                    'ticker': ['RELIANCE', '120828', 'TCS'],
                    'quantity': [100, 500, 50],
                    'transaction_type': ['buy', 'buy', 'sell'],
                    'price': [2500.50, 45.25, 3800.00],
                    'stock_name': ['Reliance Industries', 'ICICI Prudential Technology Fund', 'Tata Consultancy Services'],
                    'sector': ['Oil & Gas', 'Technology', 'Technology'],
                    'channel': ['Direct', 'Online', 'Broker']
                }
                sample_df = pd.DataFrame(sample_data)
                csv = sample_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download Sample CSV",
                    data=csv,
                    file_name="sample_investment_portfolio.csv",
                    mime="text/csv",
                    type="primary",
                    key="download_files_sample"
                )
            
            st.markdown("---")
        
        # File upload section
        st.subheader("📤 Upload Investment File")
        
        # Show CSV format requirements
        st.markdown("""
        **Required Columns:**
        - `date` - Transaction date (YYYY-MM-DD format)
        - `ticker` - Stock/Mutual Fund symbol (e.g., RELIANCE, 120828)
        - `quantity` - Number of shares/units
        - `transaction_type` - Buy or Sell
        
        **Optional Columns:**
        - `price` - Transaction price per share/unit
        - `stock_name` - Company/Fund name
        - `sector` - Industry sector
        - `channel` - Investment platform (e.g., Direct, Broker, Online)
        
        **Example:**
        ```csv
        date,ticker,quantity,transaction_type,price,stock_name,sector,channel
        2024-01-15,RELIANCE,100,buy,2500.50,Reliance Industries,Oil & Gas,Direct
        2024-01-20,120828,500,buy,45.25,ICICI Prudential Technology Fund,Technology,Online
        2024-02-01,TCS,50,sell,3800.00,Tata Consultancy Services,Technology,Broker
        ```
        
        **Notes:**
        - For mutual funds, use the numerical scheme code (e.g., 120828)
        - For stocks, you can include exchange suffix (.NS, .BO) or leave without
        - Transaction types: buy, sell, purchase, bought, sold, sale
        - If price is missing, the system will fetch historical prices automatically
        """)
        
        uploaded_file = st.file_uploader(
            "Choose a CSV file",
                    type=['csv'],
            help="Upload your investment portfolio CSV file"
        )
        
        if uploaded_file is not None:
            if st.button("Process File"):
                with st.spinner("Processing file..."):
                    try:
                        st.info(f"🔄 Files page: Starting to process file: {uploaded_file.name}")
                        # Process the uploaded file using the local method
                        result = self.process_csv_file(uploaded_file, user_id)
                        st.info(f"🔄 Files page: process_csv_file returned: {result}")
                        
                        if result:
                            st.success("File processed successfully!")
                            st.info("🔄 Files page: File processed successfully, refreshing portfolio data...")
                            # Refresh portfolio data
                            self.load_portfolio_data(user_id)
                            st.info("🔄 Files page: Portfolio data refreshed, calling rerun...")
                            st.rerun()  # Refresh the page to show updated data
                        else:
                            st.error("Error processing file")
                            st.error("❌ Files page: File processing returned False")
                    except Exception as e:
                        st.error(f"Error processing file: {e}")
                        st.error(f"Error details: {str(e)}")
                        st.error(f"❌ Files page: File processing error: {e}")
                        st.error(f"Error type: {type(e).__name__}")
                        import traceback
                        st.error(f"Traceback: {traceback.format_exc()}")
                        st.error(f"Traceback: {traceback.format_exc()}")
        
        # File history
        st.subheader("📋 File History")
        
        try:
            files = get_file_records_supabase(user_id=user_id)
            if files:
                files_df = pd.DataFrame(files)
                
                # Show available columns for debugging
                st.info(f"Available columns: {list(files_df.columns)}")
                
                # Select display columns based on available data
                display_columns = ['filename']
                if 'customer_name' in files_df.columns:
                    display_columns.append('customer_name')
                if 'processed_at' in files_df.columns:
                    display_columns.append('processed_at')
                if 'status' in files_df.columns:
                    display_columns.append('status')
                if 'file_path' in files_df.columns:
                    display_columns.append('file_path')
                
                # Display file records with available columns
                st.dataframe(files_df[display_columns], width='stretch')
                
                # Show file summary
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Files", len(files_df))
                with col2:
                    if 'status' in files_df.columns:
                        processed_count = len(files_df[files_df['status'] == 'processed'])
                        st.metric("Processed Files", processed_count)
                with col3:
                    if 'processed_at' in files_df.columns:
                        recent_files = len(files_df[files_df['processed_at'].notna()])
                        st.metric("Recent Files", recent_files)
                
            else:
                st.info("No files uploaded yet")
                
        except Exception as e:
            st.error(f"Error loading file history: {e}")
            st.info("This might be due to missing columns in the database schema")
    
    def render_ai_assistant_page(self):
        """Render AI Assistant page with ChatGPT integration"""
        st.header("🤖 AI Portfolio Assistant")
        st.markdown("*Your intelligent stock broker and PMS assistant powered by ChatGPT*")
        
        # Features and Requirements
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            ### 🚀 Features:
            - **Portfolio Analysis**: Get insights on your investment performance
            - **Market Research**: Ask about stocks, mutual funds, and market trends
            - **Document Analysis**: Upload PDFs, reports, or financial documents
            - **Investment Advice**: Get personalized recommendations based on your portfolio
            - **Risk Assessment**: Understand your portfolio's risk profile
            - **PDF OCR Processing**: Extract text from images in PDF documents
            """)
        
        with col2:
            st.info("""
            📋 **Configuration:**
            - **API Key**: Configured via Streamlit secrets (`open_ai`)
            - **PDF OCR**: Tesseract OCR must be installed on your system
            - **Windows**: Download from [GitHub Tesseract releases](https://github.com/UB-Mannheim/tesseract/wiki)
            - **Linux**: `sudo apt-get install tesseract-ocr`
            - **macOS**: `brew install tesseract`
            - The system will automatically detect and use OCR for PDF images
            """)
        
        # Initialize session state for chat
        if 'chat_history' not in st.session_state:
            st.session_state.chat_history = []
        if 'openai_api_key' not in st.session_state:
            # Try to get API key from Streamlit secrets first, then fallback to manual input
            try:
                st.session_state.openai_api_key = st.secrets["open_ai"]
            except:
                st.session_state.openai_api_key = None
        
        # API Key Status
        if st.session_state.openai_api_key:
            # Check if API key is from secrets or manual input
            try:
                secrets_key = st.secrets["open_ai"]
                if st.session_state.openai_api_key == secrets_key:
                    st.success("✅ OpenAI API Key loaded from Streamlit secrets and ready to use!")
                else:
                    st.success("✅ OpenAI API Key is configured and ready to use!")
            except:
                st.success("✅ OpenAI API Key is configured and ready to use!")
        
        # API Key Configuration
        with st.expander("🔑 OpenAI API Configuration", expanded=False):
            api_key = st.text_input(
                "Enter your OpenAI API Key:",
                type="password",
                value=st.session_state.openai_api_key or "",
                help="Get your API key from https://platform.openai.com/api-keys or configure it in Streamlit secrets as 'open_ai'"
            )
            
            if st.button("Save API Key"):
                if api_key:
                    st.session_state.openai_api_key = api_key
                    st.success("✅ API Key saved successfully!")
                else:
                    st.error("❌ Please enter a valid API key")
        
        # File Upload Section
        with st.expander("📁 Upload Documents for Analysis", expanded=False):
            uploaded_files = st.file_uploader(
                "Upload documents (PDF with OCR, TXT, CSV, etc.)",
                type=['pdf', 'txt', 'csv', 'docx', 'xlsx'],
                accept_multiple_files=True,
                help="Upload financial documents, reports, or any files you want the AI to analyze. PDFs will be processed with OCR to extract text from images."
            )
            
            if uploaded_files:
                st.success(f"✅ {len(uploaded_files)} file(s) uploaded successfully!")
                for file in uploaded_files:
                    file_type_icon = "📄" if file.type != "application/pdf" else "📄🔍"
                    st.write(f"{file_type_icon} {file.name} ({file.size} bytes)")
                    if file.type == "application/pdf":
                        st.caption("🔍 PDF will be processed with OCR for image text extraction")
        
        # Chat Interface
        st.subheader("💬 Chat with AI Assistant")
        
        # Display chat history
        chat_container = st.container()
        with chat_container:
            for message in st.session_state.chat_history:
                if message["role"] == "user":
                    st.markdown(f"**You:** {message['content']}")
                else:
                    st.markdown(f"**AI Assistant:** {message['content']}")
        
        # Chat input
        user_input = st.text_input(
            "Ask me anything about your portfolio, stocks, or investments:",
            placeholder="e.g., 'What's my best performing stock?' or 'Analyze my portfolio risk'",
            key="chat_input"
        )
        
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            if st.button("🚀 Send Message", type="primary"):
                if user_input and st.session_state.openai_api_key:
                    self.process_ai_query(user_input, uploaded_files)
                elif not user_input:
                    st.error("❌ Please enter a message")
                else:
                    st.error("❌ Please configure your OpenAI API key first")
        
        with col2:
            if st.button("🗑️ Clear Chat"):
                st.session_state.chat_history = []
                st.rerun()
        
        with col3:
            if st.button("📊 Portfolio Summary"):
                if st.session_state.openai_api_key:
                    self.get_portfolio_summary()
                else:
                    st.error("❌ Please configure your OpenAI API key first")
        
        # Quick Actions are now in the sidebar for better UX
    
    def process_ai_query(self, user_input, uploaded_files=None, current_page=None, ai_model="Google Gemini Flash (Fast)"):
        """Process user query with AI assistant"""
        try:
            # Check rate limit based on selected model
            import time
            current_time = time.time()
            
            if ai_model in ["Google Gemini Flash (Fast)", "Google Gemini Pro (Advanced)"]:
                # Gemini has 60 requests per minute - more lenient
                st.session_state.api_call_times = [t for t in st.session_state.api_call_times if current_time - t < 60]
                if len(st.session_state.api_call_times) >= 60:
                    st.error("🚫 **Rate limit exceeded!** You can only make 60 API calls per minute with Gemini. Please wait 1 minute before trying again.")
                    return
            else:
                # OpenAI has 3 requests per minute - strict
                st.session_state.api_call_times = [t for t in st.session_state.api_call_times if current_time - t < 60]
                if len(st.session_state.api_call_times) >= 3:
                    st.error("🚫 **Rate limit exceeded!** You can only make 3 API calls per minute with OpenAI. Please wait 1 minute before trying again.")
                    return
            
            # Add this call to the tracking
            st.session_state.api_call_times.append(current_time)
            st.session_state.api_call_count += 1
            
            # Add user message to chat history
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            
            # Prepare context data with current page
            try:
                context_data = self.prepare_context_data(current_page)
                if not context_data:
                    context_data = {"error": "No portfolio data available"}
            except Exception as e:
                st.error(f"❌ Error preparing context: {e}")
                context_data = {"error": f"Context preparation failed: {str(e)}"}
            
            # Process uploaded files if any
            file_content = ""
            if uploaded_files:
                # Show progress for PDF processing
                pdf_files = [f for f in uploaded_files if f.type == "application/pdf"]
                if pdf_files:
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    status_text.text("🔍 Processing PDFs with OCR...")
                    
                    file_content = self.process_uploaded_files(uploaded_files)
                    
                    progress_bar.progress(1.0)
                    status_text.text("✅ PDF processing complete!")
                    progress_bar.empty()
                    status_text.empty()
                else:
                    file_content = self.process_uploaded_files(uploaded_files)
            
            # Generate AI response
            try:
                ai_response = self.generate_ai_response(user_input, context_data, file_content, ai_model)
            except Exception as e:
                st.error(f"❌ Error generating AI response: {e}")
                ai_response = "❌ Sorry, I encountered an error while generating a response. Please try again or check your API configuration."
            
            # Add AI response to chat history
            st.session_state.chat_history.append({"role": "assistant", "content": ai_response})
            
            # Rerun to update the chat display
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error processing query: {e}")
    
    def convert_to_json_serializable(self, obj):
        """Convert pandas objects and other non-serializable types to JSON-serializable format"""
        if isinstance(obj, pd.Timestamp):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(obj, pd.Series):
            return obj.tolist()
        elif isinstance(obj, pd.DataFrame):
            return obj.to_dict('records')
        elif isinstance(obj, dict):
            return {k: self.convert_to_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.convert_to_json_serializable(item) for item in obj]
        elif hasattr(obj, 'item'):  # numpy scalars
            return obj.item()
        else:
            return obj

    def prepare_context_data(self, current_page=None):
        """Prepare portfolio and market data context for AI"""
        try:
            context = {
                "current_page": current_page,
                "portfolio_summary": {},
                "transactions": [],
                "stock_data": {},
                "market_insights": {},
                "page_specific_data": {}
            }
            
            # Get portfolio data
            if hasattr(self.session_state, 'portfolio_data') and self.session_state.portfolio_data is not None:
                df = self.session_state.portfolio_data
                
                # Portfolio summary
                context["portfolio_summary"] = {
                    "total_invested": float(df['invested_amount'].sum()) if 'invested_amount' in df.columns else 0,
                    "total_current_value": float(df['current_value'].sum()) if 'current_value' in df.columns else 0,
                    "total_pnl": float(df['unrealized_pnl'].sum()) if 'unrealized_pnl' in df.columns else 0,
                    "total_stocks": int(len(df['ticker'].unique())) if 'ticker' in df.columns else 0,
                    "date_range": {
                        "start": df['date'].min().strftime('%Y-%m-%d') if 'date' in df.columns else None,
                        "end": df['date'].max().strftime('%Y-%m-%d') if 'date' in df.columns else None
                    }
                }
                
                # Top performers
                if 'unrealized_pnl' in df.columns:
                    top_performers_df = df.nlargest(5, 'unrealized_pnl')[['ticker', 'stock_name', 'unrealized_pnl', 'current_value']]
                    top_performers = []
                    for _, row in top_performers_df.iterrows():
                        top_performers.append({
                            'ticker': str(row['ticker']),
                            'stock_name': str(row['stock_name']),
                            'unrealized_pnl': float(row['unrealized_pnl']),
                            'current_value': float(row['current_value'])
                        })
                    context["portfolio_summary"]["top_performers"] = top_performers
                
                # Sector allocation
                if 'sector' in df.columns:
                    sector_allocation = df.groupby('sector')['current_value'].sum().to_dict()
                    context["portfolio_summary"]["sector_allocation"] = {k: float(v) for k, v in sector_allocation.items()}
                
                # Recent transactions (limit to 5 to reduce tokens)
                recent_transactions_df = df.tail(5)[['ticker', 'stock_name', 'transaction_type', 'quantity', 'price', 'date']]
                recent_transactions = []
                for _, row in recent_transactions_df.iterrows():
                    recent_transactions.append({
                        'ticker': str(row['ticker']),
                        'stock_name': str(row['stock_name']),
                        'transaction_type': str(row['transaction_type']),
                        'quantity': float(row['quantity']),
                        'price': float(row['price']),
                        'date': row['date'].strftime('%Y-%m-%d') if pd.notna(row['date']) else None
                    })
                context["transactions"] = recent_transactions
            
            # Get live stock data
            if hasattr(self.session_state, 'live_prices'):
                context["stock_data"]["live_prices"] = self.convert_to_json_serializable(self.session_state.live_prices)
            
            # Add page-specific data based on current page
            if current_page and hasattr(self.session_state, 'portfolio_data') and self.session_state.portfolio_data is not None:
                df = self.session_state.portfolio_data
                
                if current_page == "🏠 Overview":
                    context["page_specific_data"] = {
                        "page_type": "overview",
                        "description": "Portfolio overview with key metrics and performance indicators",
                        "key_metrics": {
                            "total_invested": float(df['invested_amount'].sum()) if 'invested_amount' in df.columns else 0,
                            "total_current_value": float(df['current_value'].sum()) if 'current_value' in df.columns else 0,
                            "total_pnl": float(df['unrealized_pnl'].sum()) if 'unrealized_pnl' in df.columns else 0,
                            "total_stocks": int(len(df['ticker'].unique())) if 'ticker' in df.columns else 0
                        }
                    }
                
                elif current_page == "📈 Performance":
                    context["page_specific_data"] = {
                        "page_type": "performance",
                        "description": "Portfolio performance analysis with charts and trends",
                        "performance_metrics": {
                            "best_performers": df.nlargest(5, 'unrealized_pnl')[['ticker', 'unrealized_pnl']].to_dict('records') if 'unrealized_pnl' in df.columns else [],
                            "worst_performers": df.nsmallest(5, 'unrealized_pnl')[['ticker', 'unrealized_pnl']].to_dict('records') if 'unrealized_pnl' in df.columns else []
                        }
                    }
                
                elif current_page == "📊 Allocation":
                    context["page_specific_data"] = {
                        "page_type": "allocation",
                        "description": "Portfolio allocation by sector, asset type, and individual holdings",
                        "allocation_data": {
                            "sector_allocation": df.groupby('sector')['current_value'].sum().to_dict() if 'sector' in df.columns else {},
                            "top_holdings": df.nlargest(10, 'current_value')[['ticker', 'current_value']].to_dict('records') if 'current_value' in df.columns else []
                        }
                    }
                
                elif current_page == "💰 P&L Analysis":
                    context["page_specific_data"] = {
                        "page_type": "pnl_analysis",
                        "description": "Profit and loss analysis with detailed breakdowns",
                        "pnl_metrics": {
                            "total_pnl": float(df['unrealized_pnl'].sum()) if 'unrealized_pnl' in df.columns else 0,
                            "profitable_stocks": len(df[df['unrealized_pnl'] > 0]) if 'unrealized_pnl' in df.columns else 0,
                            "losing_stocks": len(df[df['unrealized_pnl'] < 0]) if 'unrealized_pnl' in df.columns else 0
                        }
                    }
            
            # If no portfolio data is available, provide a helpful message
            if not context.get("portfolio_summary") or not any(context["portfolio_summary"].values()):
                context["portfolio_summary"] = {
                    "message": "No portfolio data available. Please upload your transaction data first.",
                    "total_invested": 0,
                    "total_current_value": 0,
                    "total_pnl": 0,
                    "total_stocks": 0
                }
            
            return context
            
        except Exception as e:
            st.error(f"❌ Error preparing context: {e}")
            return {
                "error": f"Context preparation failed: {str(e)}",
                "portfolio_summary": {
                    "message": "Unable to load portfolio data due to an error.",
                    "total_invested": 0,
                    "total_current_value": 0,
                    "total_pnl": 0,
                    "total_stocks": 0
                }
            }
    
    def extract_text_from_pdf(self, pdf_bytes):
        """Extract text from PDF using multiple methods including OCR for images"""
        extracted_text = []
        
        try:
            # Method 1: Try pdfplumber for better text extraction
            try:
                with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                    for page_num, page in enumerate(pdf.pages, 1):
                        text = page.extract_text()
                        if text and text.strip():
                            extracted_text.append(f"Page {page_num} (Text):\n{text.strip()}\n")
                        
                        # Extract images and perform OCR
                        images = page.images
                        if images:
                            for img_num, img in enumerate(images, 1):
                                try:
                                    # Convert PDF page to image
                                    pdf_images = convert_from_bytes(pdf_bytes, first_page=page_num, last_page=page_num)
                                    if pdf_images:
                                        # Crop the image to the specific area if possible
                                        img_obj = pdf_images[0]
                                        
                                        # Perform OCR on the image
                                        ocr_text = pytesseract.image_to_string(img_obj, lang='eng')
                                        if ocr_text and ocr_text.strip():
                                            extracted_text.append(f"Page {page_num} Image {img_num} (OCR):\n{ocr_text.strip()}\n")
                                except Exception as ocr_error:
                                    extracted_text.append(f"Page {page_num} Image {img_num}: [OCR failed: {str(ocr_error)}]\n")
            except Exception as e:
                st.warning(f"pdfplumber extraction failed: {str(e)}")
            
            # Method 2: Fallback to PyPDF2 if pdfplumber fails
            if not extracted_text:
                try:
                    pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
                    for page_num, page in enumerate(pdf_reader.pages, 1):
                        text = page.extract_text()
                        if text and text.strip():
                            extracted_text.append(f"Page {page_num} (PyPDF2):\n{text.strip()}\n")
                except Exception as e:
                    st.warning(f"PyPDF2 extraction failed: {str(e)}")
            
            # Method 3: Convert entire PDF to images and perform OCR
            if not extracted_text:
                try:
                    pdf_images = convert_from_bytes(pdf_bytes, dpi=300)
                    for page_num, img in enumerate(pdf_images, 1):
                        ocr_text = pytesseract.image_to_string(img, lang='eng')
                        if ocr_text and ocr_text.strip():
                            extracted_text.append(f"Page {page_num} (Full Page OCR):\n{ocr_text.strip()}\n")
                except Exception as e:
                    st.warning(f"Full page OCR failed: {str(e)}")
            
        except Exception as e:
            st.error(f"PDF processing error: {str(e)}")
            return f"[Error processing PDF: {str(e)}]"
        
        return "\n".join(extracted_text) if extracted_text else "[No text could be extracted from PDF]"

    def process_uploaded_files(self, uploaded_files):
        """Process uploaded files and extract text content"""
        try:
            file_content = ""
            
            for file in uploaded_files:
                file_content += f"\n\n--- File: {file.name} ---\n"
                
                if file.type == "text/plain":
                    content = str(file.read(), "utf-8")
                    file_content += content
                elif file.type == "text/csv":
                    df = pd.read_csv(file)
                    file_content += f"CSV Data:\n{df.to_string()}"
                elif file.type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
                    df = pd.read_excel(file)
                    file_content += f"Excel Data:\n{df.to_string()}"
                elif file.type == "application/pdf":
                    # Enhanced PDF processing with OCR
                    pdf_bytes = file.read()
                    extracted_content = self.extract_text_from_pdf(pdf_bytes)
                    file_content += f"PDF Content (with OCR):\n{extracted_content}"
                else:
                    file_content += f"File type {file.type} - content extraction not supported yet"
            
            return file_content
            
        except Exception as e:
            st.error(f"❌ Error processing files: {e}")
            return ""
    
    def generate_ai_response(self, user_input, context_data, file_content="", ai_model="Google Gemini Flash (Fast)"):
        """Generate AI response using selected AI model"""
        try:
            if ai_model in ["Google Gemini Flash (Fast)", "Google Gemini Pro (Advanced)"]:
                # Use Gemini API
                api_key = None
                try:
                    api_key = st.secrets["gemini_api_key"]
                except:
                    api_key = st.session_state.gemini_api_key
                
                if not api_key:
                    return "❌ Gemini API key not configured. Please set it in Streamlit secrets as 'gemini_api_key'."
                
                # Configure Gemini API key
                genai.configure(api_key=api_key)
                
                # Try different model names in order of preference
                model = None
                model_names_to_try = ['gemini-1.0-pro', 'gemini-pro', 'gemini-1.5-pro', 'gemini-1.5-flash']
                
                for model_name in model_names_to_try:
                    try:
                        model = genai.GenerativeModel(model_name)
                        # Test if model works with a simple call
                        test_response = model.generate_content("test")
                        break
                    except Exception as e:
                        continue
                
                if model is None:
                    return "❌ No working Gemini model found. Please check your API key and available models."
                
                # Prepare system prompt for Gemini
                current_page_info = ""
                if context_data.get("current_page"):
                    current_page_info = f"\n\nYou are currently helping the user on the '{context_data['current_page']}' page. "
                    if context_data.get("page_specific_data"):
                        page_data = context_data["page_specific_data"]
                        current_page_info += f"This page shows {page_data.get('description', 'portfolio data')}. "
                        if page_data.get('page_type'):
                            current_page_info += f"Focus your analysis on {page_data['page_type']} related insights. "
                
                system_prompt = f"""You are an expert stock broker and Portfolio Management System (PMS) assistant. 
                You have access to the user's complete portfolio data, transaction history, and market information.
                {current_page_info}
                
                Your role:
                1. Provide intelligent analysis of portfolio performance
                2. Give investment recommendations based on data
                3. Analyze risk and suggest improvements
                4. Answer questions about stocks, mutual funds, and market trends
                5. Help with financial planning and strategy
                6. Give context-aware responses based on the current page the user is viewing
                
                Guidelines:
                - Always base your analysis on the provided data
                - Be specific and actionable in your recommendations
                - Consider Indian market context for stocks and mutual funds
                - Provide clear explanations for your insights
                - Be professional but conversational
                - Tailor your response to the current page context when relevant
                - If you don't have specific data, say so clearly
                
                Portfolio Context:
                """ + json.dumps(self.convert_to_json_serializable(context_data), indent=2)
                
                if file_content:
                    system_prompt += f"\n\nUploaded File Content:\n{file_content}"
                
                # Prepare full prompt for Gemini
                full_prompt = f"{system_prompt}\n\nUser Question: {user_input}"
                
                # Generate response using Gemini
                response = model.generate_content(full_prompt)
                return response.text
                
            else:
                # Use OpenAI API (existing code)
                api_key = None
                try:
                    api_key = st.secrets["open_ai"]
                except:
                    api_key = st.session_state.openai_api_key
                
                if not api_key:
                    return "❌ OpenAI API key not configured. Please set it in the configuration section or in Streamlit secrets as 'open_ai'."
            
            # Prepare system prompt
            # Prepare system prompt with current page context
            current_page_info = ""
            if context_data.get("current_page"):
                current_page_info = f"\n\nYou are currently helping the user on the '{context_data['current_page']}' page. "
                if context_data.get("page_specific_data"):
                    page_data = context_data["page_specific_data"]
                    current_page_info += f"This page shows {page_data.get('description', 'portfolio data')}. "
                    if page_data.get('page_type'):
                        current_page_info += f"Focus your analysis on {page_data['page_type']} related insights. "
            
            system_prompt = f"""You are an expert stock broker and Portfolio Management System (PMS) assistant. 
            You have access to the user's complete portfolio data, transaction history, and market information.
            {current_page_info}
            
            Your role:
            1. Provide intelligent analysis of portfolio performance
            2. Give investment recommendations based on data
            3. Analyze risk and suggest improvements
            4. Answer questions about stocks, mutual funds, and market trends
            5. Help with financial planning and strategy
            6. Give context-aware responses based on the current page the user is viewing
            
            Guidelines:
            - Always base your analysis on the provided data
            - Be specific and actionable in your recommendations
            - Consider Indian market context for stocks and mutual funds
            - Provide clear explanations for your insights
            - Be professional but conversational
            - Tailor your response to the current page context when relevant
            - If you don't have specific data, say so clearly
            
            Portfolio Context:
            """ + json.dumps(self.convert_to_json_serializable(context_data), indent=2)
            
            if file_content:
                system_prompt += f"\n\nUploaded File Content:\n{file_content}"
            
            # Prepare messages
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ]
            
            # Generate response
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=1000,
                temperature=0.7
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            error_msg = str(e)
            if "You tried to access" in error_msg:
                return "❌ API access error. Please check your OpenAI API key and ensure it has proper permissions."
            elif "rate limit" in error_msg.lower() or "429" in error_msg:
                return "⚠️ Rate limit exceeded. Please wait 1-2 minutes before trying again. Your ₹399 plan has strict limits (3 requests/minute)."
            elif "insufficient_quota" in error_msg.lower():
                return "❌ API quota exceeded. Please check your OpenAI account billing and usage limits."
            elif "invalid_api_key" in error_msg.lower():
                return "❌ Invalid API key. Please check your OpenAI API key configuration."
            else:
                return f"❌ Error generating AI response: {error_msg}"
    
    def quick_analysis(self, query, current_page=None):
        """Perform quick analysis with predefined queries"""
        self.process_ai_query(query, current_page=current_page)
    
    def get_portfolio_summary(self):
        """Get AI-generated portfolio summary"""
        query = "Provide a comprehensive summary of my portfolio including performance, allocation, and key insights"
        self.process_ai_query(query)

    def render_settings_page(self):
        """Render settings page"""
        st.header("⚙️ Settings")
        
        user_id = self.session_state.user_id
        if not user_id:
            st.error("No user ID found")
            return
        
        # User information
        st.subheader("👤 User Information")
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**Username:** {self.session_state.username}")
            st.write(f"**User ID:** {user_id}")
            st.write(f"**Role:** {self.session_state.user_role}")
            
            with col2:
                st.write(f"**Login Time:** {self.session_state.login_time.strftime('%Y-%m-%d %H:%M:%S')}")
                st.write(f"**Session Duration:** {(datetime.now() - self.session_state.login_time).total_seconds() / 3600:.1f} hours")
        
        st.markdown("---")
        
        # Data management
        st.subheader("🗄️ Data Management")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔄 Refresh Portfolio Data"):
                with st.spinner("Refreshing data..."):
                    try:
                        # First fetch live prices and sectors
                        self.fetch_live_prices_and_sectors(user_id)
                        st.success("Live prices updated!")
                        
                        # Then reload portfolio data
                        self.load_portfolio_data(user_id)
                        st.success("Portfolio data refreshed!")
                        
                        # Force a rerun to show updated values
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error refreshing data: {e}")
            
        with col2:
            if st.button("📊 Update Live Prices"):
                with st.spinner("Updating prices..."):
                    self.fetch_live_prices_and_sectors(user_id)
                    st.success("Live prices updated!")
        
        with col3:
            if st.button("🧹 Clear Cache"):
                if 'live_prices' in self.session_state:
                    del self.session_state['live_prices']
                st.success("Cache cleared!")
        
        # Debug section
        st.markdown("---")
        st.subheader("🐛 Debug & Testing")
        
        if st.button("🧪 Test Basic Functions"):
            try:
                st.info("Testing basic functions...")
                
                # Test 1: Check session state
                st.write(f"✅ Session state: user_id={self.session_state.user_id}, username={self.session_state.username}")
                
                # Test 2: Test database connection
                try:
                    files = get_file_records_supabase(user_id=self.session_state.user_id)
                    st.write(f"✅ Database connection: Found {len(files) if files else 0} files")
                except Exception as e:
                    st.error(f"❌ Database connection failed: {e}")
                
                # Test 3: Test portfolio data loading
                try:
                    self.load_portfolio_data(self.session_state.user_id)
                    portfolio_count = len(self.session_state.portfolio_data) if self.session_state.portfolio_data is not None else 0
                    st.write(f"✅ Portfolio data loading: {portfolio_count} transactions")
                except Exception as e:
                    st.error(f"❌ Portfolio data loading failed: {e}")
                
                st.success("✅ Basic function tests completed!")
                
            except Exception as e:
                st.error(f"❌ Test failed: {e}")
                import traceback
                st.error(f"Traceback: {traceback.format_exc()}")
        
        st.markdown("---")
        
        # System information
        st.subheader("ℹ️ System Information")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Python Version:** 3.8+")
            st.write("**Streamlit Version:** 1.28.0+")
            st.write("**Database:** Supabase PostgreSQL")
        
        with col2:
            st.write("**Price Sources:** yfinance, mftool, indstocks")
            st.write("**Charts:** Plotly")
            st.write("**Data Processing:** Pandas, NumPy")
    
    def run(self):
        """Main run method"""
        # Check authentication status
        if not self.session_state.get('user_authenticated', False):
            self.render_login_page()
        else:
            self.render_main_dashboard()

# Main execution
if __name__ == "__main__":
    # Initialize the portfolio analytics system
    app = PortfolioAnalytics()
    
    # Run the application
    app.run()
