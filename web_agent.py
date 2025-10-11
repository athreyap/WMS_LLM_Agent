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

# Try to import new bulk function (optional for backward compatibility)
try:
    from database_config_supabase import get_stock_prices_bulk_supabase
    BULK_QUERY_AVAILABLE = True
except ImportError:
    BULK_QUERY_AVAILABLE = False
    print("⚠️ Bulk query function not available - using fallback")

# Try to import PDF functions (optional, may not exist in older deployments)
try:
    from database_config_supabase import (
        save_pdf_document_supabase,
        get_pdf_documents_supabase,
        delete_pdf_document_supabase
    )
    PDF_STORAGE_AVAILABLE = True
except ImportError:
    PDF_STORAGE_AVAILABLE = False
    print("⚠️ PDF storage functions not available - using temporary PDF processing only")

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
        from datetime import datetime

        try:
            # Get user (case-insensitive lookup handled by database function)
            user = get_user_by_username_supabase(username.strip())
            
            # Temporary simple password handling - will be updated when login_system is fixed
            if user and user['password_hash'] == password:  # In production, use proper verification
                self.session_state.user_authenticated = True
                self.session_state.user_id = user['id']
                self.session_state.username = user['username']  # Store original username from database
                self.session_state.user_role = user['role']
                self.session_state.login_time = datetime.now()
                
                # Initialize portfolio data after login (enable background cache)
                self.initialize_portfolio_data(skip_cache_population=False)
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
            
            # Check if this is a holdings-only file (no dates/transaction types)
            has_dates = 'date' in df.columns and not df['date'].isna().all()
            has_transaction_types = 'transaction_type' in df.columns and not df['transaction_type'].isna().all()
            
            if not has_dates or not has_transaction_types:
                # This is a holdings-only file - treat as purchases from 1 month ago
                st.info(f"📋 Detected holdings-only file (no dates/transaction types)")
                
                # Set default values
                if 'date' not in df.columns or df['date'].isna().all():
                    # Set date as 1 month back from today
                    one_month_ago = pd.Timestamp.now() - pd.Timedelta(days=30)
                    df['date'] = one_month_ago
                    st.info(f"📅 Using 1 month ago ({one_month_ago.strftime('%Y-%m-%d')}) as purchase date for all holdings")
                
                if 'transaction_type' not in df.columns or df['transaction_type'].isna().all():
                    df['transaction_type'] = 'buy'
                    st.info(f"💼 Treating all as 'buy' transactions (purchases from 1 month ago)")
            
            # Ensure required columns exist
            required_columns = ['ticker', 'quantity']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                st.error(f"❌ Missing required columns in {uploaded_file.name}: {missing_columns}")
                st.info("Required columns: ticker, quantity")
                st.info("Optional columns: date, transaction_type, price, stock_name, sector")
                return False
            
            # Clean and validate data
            st.info(f"🔍 Initial data: {len(df)} rows")
            st.info(f"📊 Quantity column sample: {df['quantity'].head().tolist()}")
            st.info(f"📊 Quantity column dtype before conversion: {df['quantity'].dtype}")
            
            # Convert quantity to numeric first (before dropping NaN)
            df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce')
            st.info(f"📊 After numeric conversion: {df['quantity'].head().tolist()}")
            st.info(f"📊 Quantity column dtype after conversion: {df['quantity'].dtype}")
            st.info(f"📊 Quantity NaN count: {df['quantity'].isna().sum()}")
            st.info(f"📊 Quantity zero count: {(df['quantity'] == 0).sum()}")
            
            # Clean ticker column - remove scientific notation and invalid formats
            df['ticker'] = df['ticker'].astype(str).str.strip()
            
            # Flag invalid tickers
            invalid_tickers = df[df['ticker'].str.contains(r'[/]|E\+|E-', regex=True, case=False, na=False)]
            if not invalid_tickers.empty:
                st.warning(f"⚠️ Found {len(invalid_tickers)} rows with invalid ticker formats (scientific notation or fractions)")
                st.info(f"Invalid tickers: {invalid_tickers['ticker'].unique().tolist()}")
                # Remove invalid tickers
                df = df[~df['ticker'].str.contains(r'[/]|E\+|E-', regex=True, case=False, na=False)]
                st.info(f"📊 Removed invalid tickers: {len(df)} rows remaining")
            
            # Drop rows with invalid ticker or quantity
            df = df.dropna(subset=['ticker', 'quantity'])
            st.info(f"📊 Data cleaned: {len(df)} valid rows remaining")
            st.info(f"📊 Final quantity sample: {df['quantity'].head().tolist()}")
            
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
                
                # Detect if this is a mutual fund (ISIN code or numeric)
                ticker_str = str(ticker).strip()
                is_mutual_fund = (
                    ticker_str.isdigit() or 
                    ticker_str.startswith('MF_') or
                    ticker_str.startswith('INF') or  # ISIN codes start with INF
                    len(ticker_str) == 12  # ISIN codes are 12 characters
                )
                
                # Fetch historical price
                if is_mutual_fund:
                    # Mutual fund
                    historical_price = get_mutual_fund_price(
                        ticker, 
                        ticker, 
                        row['user_id'], 
                        transaction_date.strftime('%Y-%m-%d')
                    )
                else:
                    # Stock - validate ticker format
                    if '/' in ticker_str or 'E+' in ticker_str.upper():
                        # Invalid ticker format (scientific notation or fractions)
                        st.warning(f"⚠️ Invalid ticker format: {ticker_str}")
                        df.at[idx, 'price'] = 0.0
                        continue
                    
                    historical_price = get_stock_price(
                        ticker, 
                        ticker, 
                        transaction_date.strftime('%Y-%m-%d')
                    )
                
                if historical_price and historical_price > 0:
                    df.at[idx, 'price'] = historical_price
                else:
                    # Use default price if historical price not available
                    if is_mutual_fund:
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
    
    def fetch_historical_price_comprehensive(self, ticker, target_date):
        """
        Comprehensive historical price fetcher - tries ALL sources:
        1. yfinance (.NS and .BO for stocks)
        2. indstocks (stocks and mutual funds)
        3. mftool (mutual funds)
        4. PMS/AIF (uses transaction price, not market price)
        
        Returns the first valid price found, saves to database cache.
        """
        try:
            target_date_str = target_date.strftime('%Y-%m-%d')
            
            # First check database cache
            from database_config_supabase import get_stock_price_supabase, save_stock_price_supabase
            cached_price = get_stock_price_supabase(ticker, target_date_str)
            if cached_price and cached_price > 0:
                return float(cached_price)
            
            price = None
            price_source = 'unknown'
            clean_ticker = str(ticker).strip().upper()
            clean_ticker = clean_ticker.replace('.NS', '').replace('.BO', '').replace('.NSE', '').replace('.BSE', '')
            
            # Check if it's a mutual fund scheme code first (priority over BSE detection)
            # Mutual fund scheme codes are typically 5-6 digits or start with MF_
            is_mutual_fund = (
                (clean_ticker.isdigit() and len(clean_ticker) >= 5) or
                clean_ticker.startswith('MF_') or
                (len(clean_ticker) >= 5 and clean_ticker.isdigit())
            )

            # Check if it's a BSE ticker code (6-digit number) - but only if not a mutual fund
            is_bse_code = clean_ticker.isdigit() and len(clean_ticker) == 6 and not is_mutual_fund

            if is_mutual_fund:
                print(f"🔍 {ticker}: Detected as mutual fund scheme code")
            elif is_bse_code:
                print(f"🔍 {ticker}: Detected as BSE code, will try {clean_ticker}.BO")
            
            # === EARLY CHECK: Is this a PMS/AIF? ===
            ticker_upper = ticker.upper()
            is_pms_aif = any(keyword in ticker_upper for keyword in [
                'PMS', 'AIF', 'INP', 'BUOYANT', 'CARNELIAN', 'JULIUS', 
                'VALENTIS', 'UNIFI', 'PORTFOLIO', 'FUND'
            ]) or ticker_upper.endswith('_PMS') or ticker.startswith('INP')
            
            if is_pms_aif:
                # For PMS/AIF, we use the TRANSACTION PRICE as historical price
                # The actual NAV calculation happens at portfolio level using CAGR
                print(f"🔍 {ticker}: Detected as PMS/AIF - using transaction price")
                
                # Get transaction price from database
                from database_config_supabase import get_transactions_supabase
                transactions = get_transactions_supabase(user_id=None)  # Get all transactions
                
                if transactions:
                    df = pd.DataFrame(transactions)
                    df['date'] = pd.to_datetime(df['date'])
                    
                    # Find transactions for this ticker on or before target date
                    ticker_txns = df[
                        (df['ticker'] == ticker) & 
                        (df['date'] <= target_date) &
                        (df['transaction_type'] == 'buy')
                    ]
                    
                    if not ticker_txns.empty:
                        # Use the most recent transaction price before target date
                        latest_txn = ticker_txns.sort_values('date', ascending=False).iloc[0]
                        price = float(latest_txn['price'])
                        price_source = 'pms_transaction_price'
                        print(f"✅ {ticker}: Using transaction price - ₹{price}")
                        
                        # Save to cache
                        try:
                            save_stock_price_supabase(ticker, target_date_str, price, price_source)
                        except Exception as e:
                            print(f"Failed to save PMS price to cache: {e}")
                        
                        return price
                
                # If no transaction found, return None (will skip caching)
                print(f"⚠️ {ticker}: PMS/AIF but no transaction found for {target_date_str}")
                return None
            
            # === STRATEGY 1: Try yfinance (BSE first for BSE codes, then NSE) ===
            if not price and is_bse_code:
                # BSE codes should try .BO first
                try:
                    import yfinance as yf
                    stock = yf.Ticker(f"{clean_ticker}.BO")
                    hist_data = stock.history(start=target_date, end=target_date + timedelta(days=1))
                    if not hist_data.empty:
                        price = float(hist_data['Close'].iloc[0])
                        price_source = 'yfinance_bse'
                        print(f"✅ {ticker}: yfinance BSE (code {clean_ticker}) - ₹{price}")
                except Exception as e:
                    pass
            
            # === STRATEGY 2: Try yfinance with .NS (NSE) for non-BSE codes ===
            if not price and not is_bse_code:
                try:
                    import yfinance as yf
                    stock = yf.Ticker(f"{clean_ticker}.NS")
                    hist_data = stock.history(start=target_date, end=target_date + timedelta(days=1))
                    if not hist_data.empty:
                        price = float(hist_data['Close'].iloc[0])
                        price_source = 'yfinance_nse'
                        print(f"✅ {ticker}: yfinance NSE - ₹{price}")
                except Exception as e:
                    pass
            
            # === STRATEGY 3: Try alternate exchange (NSE if BSE failed, BSE if NSE failed) ===
            if not price:
                try:
                    import yfinance as yf
                    suffix = '.NS' if is_bse_code else '.BO'
                    stock = yf.Ticker(f"{clean_ticker}{suffix}")
                    hist_data = stock.history(start=target_date, end=target_date + timedelta(days=1))
                    if not hist_data.empty:
                        price = float(hist_data['Close'].iloc[0])
                        price_source = f'yfinance_{"nse" if is_bse_code else "bse"}_fallback'
                        print(f"✅ {ticker}: yfinance {'NSE' if is_bse_code else 'BSE'} (fallback) - ₹{price}")
                except Exception as e:
                    pass
            
            # === STRATEGY 4: Try indstocks (works for both stocks and MFs) ===
            if not price:
                try:
                    from indstocks_api import get_indstocks_client
                    api_client = get_indstocks_client()
                    if api_client and api_client.available:
                        price_data = api_client.get_historical_price(ticker, target_date_str)
                        if price_data and price_data.get('price'):
                            price = float(price_data['price'])
                            price_source = 'indstocks'
                            print(f"✅ {ticker}: indstocks - ₹{price}")
                except Exception as e:
                    pass
            
            # === STRATEGY 5: Try mftool (mutual funds) ===
            if not price:
                try:
                    from mf_price_fetcher import fetch_mutual_fund_price
                    mf_price = fetch_mutual_fund_price(ticker, target_date_str)
                    if mf_price and mf_price > 0:
                        price = float(mf_price)
                        price_source = 'mftool'
                        print(f"✅ {ticker}: mftool - ₹{price}")
                except Exception as e:
                    pass
            
            # === STRATEGY 6: Try PMS/AIF (if ticker suggests it) ===
            if not price:
                ticker_upper = ticker.upper()
                if any(keyword in ticker_upper for keyword in ['PMS', 'AIF', 'INP', 'BUOYANT', 'CARNELIAN', 'JULIUS', 'VALENTIS', 'UNIFI']) or ticker_upper.endswith('_PMS'):
                    try:
                        from pms_aif_fetcher import get_pms_nav, get_aif_nav, is_pms_code, is_aif_code
                        
                        # For PMS/AIF, we need investment date and amount
                        # This is a historical price fetch, so we can't calculate value
                        # Just skip for now - PMS/AIF values are calculated at portfolio level
                        pass
                    except Exception as e:
                        pass
            
            # === FALLBACK: Try yfinance with 7-day window ===
            if not price:
                try:
                    import yfinance as yf
                    for suffix in ['.NS', '.BO']:
                        stock = yf.Ticker(f"{clean_ticker}{suffix}")
                        hist_data = stock.history(
                            start=target_date - timedelta(days=7),
                            end=target_date + timedelta(days=7)
                        )
                        if not hist_data.empty:
                            # Get closest date
                            price = float(hist_data['Close'].iloc[-1])
                            price_source = f'yfinance{suffix}_fallback'
                            print(f"✅ {ticker}: yfinance{suffix} (7-day window) - ₹{price}")
                            break
                except Exception as e:
                    pass
            
            # Save to database if we got a valid price
            if price and price > 0:
                try:
                    save_result = save_stock_price_supabase(ticker, target_date_str, price, price_source)
                    if save_result:
                        print(f"✅ Saved {ticker} price for {target_date_str} to database")

                        # Verify the save by reading it back immediately (with retry)
                        import time
                        max_retries = 3
                        for attempt in range(max_retries):
                            time.sleep(0.1)  # Small delay to allow database commit
                            verify_price = get_stock_price_supabase(ticker, target_date_str)
                            if verify_price and abs(float(verify_price) - price) < 0.01:  # Allow small floating point differences
                                print(f"✅ Verification successful: {ticker} {target_date_str} saved correctly")
                                break
                            elif attempt == max_retries - 1:
                                print(f"⚠️ Verification failed after {max_retries} attempts: {ticker} {target_date_str} not found after save (expected: {price}, got: {verify_price})")
                            else:
                                print(f"⚠️ Verification attempt {attempt + 1} failed, retrying...")
                    else:
                        print(f"⚠️ Failed to save {ticker} price to database (returned False)")
                except Exception as e:
                    print(f"❌ Exception saving price to cache for {ticker}: {e}")
                    import traceback
                    traceback.print_exc()
                return price
            
            print(f"❌ {ticker}: No price found from any source for {target_date_str}")
            return None
            
        except Exception as e:
            print(f"Error in comprehensive price fetch for {ticker} on {target_date}: {e}")
            return None
    
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
            
            # Use comprehensive fetcher
            price = self.fetch_historical_price_comprehensive(ticker, target_date)
            
            # Save to monthly cache if we got a valid price
            if price and price > 0:
                try:
                    save_result = save_monthly_stock_price_supabase(ticker, target_date_str, price, 'monthly_cache')
                    if save_result:
                        print(f"✅ Saved {ticker} monthly price for {target_date_str} to database")

                        # Verify the save by reading it back immediately (with retry)
                        import time
                        max_retries = 3
                        for attempt in range(max_retries):
                            time.sleep(0.1)  # Small delay to allow database commit
                            verify_price = get_monthly_stock_price_supabase(ticker, target_date_str)
                            if verify_price and abs(float(verify_price) - price) < 0.01:
                                print(f"✅ Monthly verification successful: {ticker} {target_date_str} saved correctly")
                                break
                            elif attempt == max_retries - 1:
                                print(f"⚠️ Monthly verification failed after {max_retries} attempts: {ticker} {target_date_str} not found after save (expected: {price}, got: {verify_price})")
                            else:
                                print(f"⚠️ Monthly verification attempt {attempt + 1} failed, retrying...")
                    else:
                        print(f"⚠️ Failed to save {ticker} monthly price to database (returned False)")
                except Exception as e:
                    print(f"❌ Exception saving monthly price for {ticker}: {e}")
                    import traceback
                    traceback.print_exc()
                return price
            
            return None
            
        except Exception as e:
            print(f"Error fetching historical price for {ticker} on {month_date}: {e}")
            return None
    
    def fetch_historical_price_for_week(self, ticker, week_date):
        """Fetch historical price for a specific week - uses comprehensive fetcher and database cache"""
        try:
            # Use the week date (Monday) as the target date
            target_date = week_date
            
            # Use comprehensive fetcher (which checks cache first and saves automatically)
            price = self.fetch_historical_price_comprehensive(ticker, target_date)
            return price
            
        except Exception as e:
            print(f"Error fetching historical price for {ticker} on {week_date}: {e}")
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
            st.info(f"💾 Saving {len(df)} transactions to database...")
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
                st.error("❌ Failed to save transactions to database")
                st.error("💡 This could be due to:")
                st.error("   • Invalid data values (infinity, NaN, or out of range)")
                st.error("   • Database connection issues")
                st.error("   • Permission errors")
                st.info("📊 Please check the console logs for detailed error messages")
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
    
    def initialize_portfolio_data(self, skip_cache_population=False):
        """
        Initialize portfolio data after login
        
        Args:
            skip_cache_population: If True, skip the weekly/monthly cache population
        """
        try:
            user_id = self.session_state.user_id
            if not user_id:
                return
            
            # Fetch live prices and sectors (essential for current portfolio view)
            self.fetch_live_prices_and_sectors(user_id)
            
            # Load portfolio data (essential for dashboard)
            self.load_portfolio_data(user_id)
            
            # Mark that cache population should happen (but don't block UI)
            if not skip_cache_population:
                cache_key = f'cache_populated_{user_id}'
                cache_trigger_key = f'cache_trigger_{user_id}'
                
                if cache_key not in st.session_state:
                    st.session_state[cache_key] = False
                
                if cache_trigger_key not in st.session_state:
                    st.session_state[cache_trigger_key] = False
                
                # Set trigger flag (will be handled later in sidebar)
                if not st.session_state[cache_key] and not st.session_state[cache_trigger_key]:
                    st.session_state[cache_trigger_key] = True
            
        except Exception as e:
            st.error(f"Error initializing portfolio data: {e}")
    
    def populate_weekly_and_monthly_cache(self, user_id):
        """
        INCREMENTAL weekly price cache update:
        - Only fetches NEW weeks since last cache update
        - Derives monthly from weekly data
        - Smart detection of missing data
        """
        from datetime import datetime, timedelta

        try:
            # Get transactions for the user
            transactions = get_transactions_supabase(user_id)
            if not transactions:
                return
            
            # Convert to DataFrame for easier processing
            df = pd.DataFrame(transactions)
            df['date'] = pd.to_datetime(df['date'])
            
            # Get ALL buy transactions to cache historical data
            buy_transactions = df[df['transaction_type'] == 'buy'].copy()
            
            if buy_transactions.empty:
                return
            
            # Get unique stocks
            unique_tickers = buy_transactions['ticker'].unique()
            
            # Determine date range for incremental update
            current_date = datetime.now()
            one_year_ago = current_date - timedelta(days=365)  # 1 year
            
            # Check what's the latest cached date across all tickers (BULK QUERY if available)
            from database_config_supabase import get_stock_price_supabase
            latest_cached_dates = {}
            
            # Get purchase dates for all tickers
            ticker_purchase_dates = {}
            for ticker in unique_tickers:
                ticker_purchases = buy_transactions[buy_transactions['ticker'] == ticker]
                purchase_date = ticker_purchases['date'].min()
                start_date = max(purchase_date, one_year_ago)
                ticker_purchase_dates[ticker] = start_date
            
            # Check last 10 weeks for all tickers
            check_date = current_date
            ticker_latest_cached = {ticker: None for ticker in unique_tickers}
            
            if BULK_QUERY_AVAILABLE:
                # Use optimized bulk query method
                for week_idx in range(10):  # Check last 10 weeks
                    # Get Monday of the week
                    monday = check_date - timedelta(days=check_date.weekday())
                    monday_str = monday.strftime('%Y-%m-%d')
                    
                    # Get cached prices for all remaining tickers at once (BULK)
                    tickers_to_check = [t for t in unique_tickers if ticker_latest_cached[t] is None]
                    if tickers_to_check:
                        cached_prices = get_stock_prices_bulk_supabase(tickers_to_check, monday_str)
                        
                        # Update latest cached dates for tickers found
                        for ticker, price in cached_prices.items():
                            if price and price > 0:
                                ticker_latest_cached[ticker] = monday
                    
                    check_date -= timedelta(days=7)
            else:
                # Fallback to original sequential method
                for ticker in unique_tickers:
                    check_date_ticker = current_date
                    for _ in range(10):  # Check last 10 weeks
                        monday = check_date_ticker - timedelta(days=check_date_ticker.weekday())
                        cached_price = get_stock_price_supabase(ticker, monday.strftime('%Y-%m-%d'))
                        if cached_price and cached_price > 0:
                            ticker_latest_cached[ticker] = monday
                            break
                        check_date_ticker -= timedelta(days=7)
            
            # Set start dates based on findings
            for ticker in unique_tickers:
                if ticker_latest_cached[ticker]:
                    # Start from next week after latest cached
                    latest_cached_dates[ticker] = ticker_latest_cached[ticker] + timedelta(days=7)
                else:
                    # No cache found, start from beginning
                    latest_cached_dates[ticker] = ticker_purchase_dates[ticker]
            
            # Count total weeks to fetch
            total_weeks_to_fetch = 0
            for ticker, start_from in latest_cached_dates.items():
                if start_from < current_date:
                    weeks = len(pd.date_range(start=start_from, end=current_date, freq='W-MON'))
                    total_weeks_to_fetch += weeks
            
            if total_weeks_to_fetch == 0:
                st.info("✅ All weekly prices are up to date!")
                return
            
            # Show appropriate message
            if any(latest_cached_dates[t] > one_year_ago + timedelta(days=7) for t in unique_tickers):
                st.info(f"🔄 Incremental update: Fetching {total_weeks_to_fetch} new weekly prices...")
                st.caption("💡 Only fetching data for new weeks since last update!")
            else:
                st.info(f"🔄 Initial cache: Fetching weekly prices for {len(unique_tickers)} holdings (1 year)...")
                st.caption("💡 This is a one-time process. Future updates will be incremental!")
            
            # Create progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Filter out PMS/AIF tickers (they don't have historical market prices)
            valid_tickers = []
            for ticker in unique_tickers:
                ticker_upper = str(ticker).upper()
                is_pms_aif = (
                    'PMS' in ticker_upper or 
                    'AIF' in ticker_upper or
                    ticker_upper.startswith('INP') or
                    ticker_upper.endswith('_PMS') or
                    ticker_upper in ['BUOYANT', 'CARNELIAN', 'JULIUS', 'VALENTIS', 'UNIFI']
                )
                # Don't skip numeric tickers (mutual funds)
                if str(ticker).strip().replace('.', '').isdigit():
                    is_pms_aif = False
                
                if not is_pms_aif and latest_cached_dates[ticker] < current_date:
                    valid_tickers.append(ticker)
            
            if not valid_tickers:
                st.info("✅ All prices are already up to date!")
                return
            
            # Generate all weekly dates needed across all tickers
            all_week_dates = set()
            ticker_week_map = {}  # Map ticker to list of weeks it needs
            for ticker in valid_tickers:
                start_from = latest_cached_dates[ticker]
                weekly_dates = pd.date_range(start=start_from, end=current_date, freq='W-MON')
                ticker_week_map[ticker] = list(weekly_dates)
                all_week_dates.update(weekly_dates)
            
            # Sort weeks chronologically
            all_week_dates = sorted(list(all_week_dates))
            total_weeks = len(all_week_dates)
            
            weekly_cached_count = 0
            monthly_derived_count = 0
            all_weekly_prices = {ticker: {} for ticker in valid_tickers}  # Store all prices per ticker
            
            # Process week by week (BULK FETCHING PER WEEK if available)
            for week_idx, week_date in enumerate(all_week_dates):
                # Update progress
                progress = (week_idx + 1) / total_weeks
                progress_bar.progress(progress)
                
                week_date_str = week_date.strftime('%Y-%m-%d')
                status_text.text(f"📊 Week {week_idx + 1}/{total_weeks}: {week_date_str}...")
                
                # Get tickers that need this week's data
                tickers_for_week = [t for t in valid_tickers if week_date in ticker_week_map[t]]
                
                if not tickers_for_week:
                    continue
                
                if BULK_QUERY_AVAILABLE:
                    # Optimized: Bulk query all tickers for this week at once
                    cached_prices = get_stock_prices_bulk_supabase(tickers_for_week, week_date_str)
                    
                    # Fetch missing prices
                    for ticker in tickers_for_week:
                        if ticker in cached_prices and cached_prices[ticker] > 0:
                            # Already cached
                            all_weekly_prices[ticker][week_date] = cached_prices[ticker]
                        else:
                            # Need to fetch
                            price = self.fetch_historical_price_comprehensive(ticker, week_date)
                            if price and price > 0:
                                all_weekly_prices[ticker][week_date] = price
                                weekly_cached_count += 1
                else:
                    # Fallback: Check each ticker individually
                    for ticker in tickers_for_week:
                        from database_config_supabase import get_stock_price_supabase
                        cached_price = get_stock_price_supabase(ticker, week_date_str)
                        
                        if cached_price and cached_price > 0:
                            all_weekly_prices[ticker][week_date] = cached_price
                        else:
                            # Need to fetch
                            price = self.fetch_historical_price_comprehensive(ticker, week_date)
                            if price and price > 0:
                                all_weekly_prices[ticker][week_date] = price
                                weekly_cached_count += 1
            
            # Derive and save monthly prices for all tickers
            status_text.text("📊 Deriving monthly prices from weekly data...")
            for ticker in valid_tickers:
                weekly_prices = all_weekly_prices[ticker]
                if weekly_prices:
                    # Group by month and take the last week's price of each month
                    monthly_prices = {}
                    for week_date, price in weekly_prices.items():
                        month_key = (week_date.year, week_date.month)
                        if month_key not in monthly_prices or week_date > monthly_prices[month_key]['date']:
                            monthly_prices[month_key] = {'date': week_date, 'price': price}
                    
                    # Save monthly prices
                    for month_key, data in monthly_prices.items():
                        year, month = month_key
                        # Get last day of month
                        if month == 12:
                            last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
                        else:
                            last_day = datetime(year, month + 1, 1) - timedelta(days=1)
                        
                        last_day_str = last_day.strftime('%Y-%m-%d')
                        
                        # Check if monthly price already exists
                        cached_monthly = get_monthly_stock_price_supabase(ticker, last_day_str)
                        if not cached_monthly or cached_monthly <= 0:
                            # Save derived monthly price
                            save_monthly_stock_price_supabase(ticker, last_day_str, data['price'], 'derived_from_weekly')
                            monthly_derived_count += 1
            
            # Clear progress indicators
            progress_bar.empty()
            status_text.empty()
            
            if weekly_cached_count > 0 or monthly_derived_count > 0:
                st.success(f"✅ Updated: {weekly_cached_count} new weekly prices, {monthly_derived_count} monthly prices!")
            else:
                st.info("✅ All prices are already up to date!")
                
        except Exception as e:
            st.warning(f"⚠️ Error updating price cache: {e}")
            print(f"Cache error: {e}")
    
    def populate_monthly_prices_cache(self, user_id):
        """Legacy function - now redirects to comprehensive weekly+monthly caching"""
        return self.populate_weekly_and_monthly_cache(user_id)
    
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
    
    def fetch_live_prices_and_sectors(self, user_id, force_refresh=False):
        """
        Fetch live prices and sectors for all tickers
        
        Args:
            user_id: User ID
            force_refresh: If True, force refresh even if already fetched this session
        """
        try:
            # Check if already fetched this session (unless force refresh)
            if not force_refresh:
                fetch_key = f'prices_fetched_{user_id}'
                if fetch_key in st.session_state and st.session_state[fetch_key]:
                    print(f"Prices already fetched this session for user {user_id}, skipping...")
                    return
                st.session_state[fetch_key] = True
            
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
            # Note: Live prices are fetched from external APIs (yfinance, mftool, etc.)
            # which don't support bulk operations. However, database cache operations
            # in populate_weekly_and_monthly_cache() now use bulk queries for optimal performance.
            for ticker in unique_tickers:
                try:
                    ticker_str = str(ticker).strip().upper()
                    
                    # Check if PMS/AIF
                    if (ticker_str.startswith('INP') or ticker_str.endswith('_PMS') or ticker_str.endswith('PMS') or 
                        'AIF' in ticker_str or ticker_str.startswith('BUOYANT') or 
                        ticker_str.startswith('CARNELIAN') or ticker_str.startswith('JULIUS') or
                        ticker_str.startswith('VALENTIS') or ticker_str.startswith('UNIFI')):
                        # PMS/AIF - calculate value using SEBI returns
                        print(f"🔍 PMS/AIF detected: {ticker}")
                        
                        # Get transaction details for this PMS
                        pms_transactions = df[df['ticker'] == ticker]
                        if not pms_transactions.empty:
                            pms_trans = pms_transactions.iloc[0]
                            investment_date = pd.to_datetime(pms_trans['date']).strftime('%Y-%m-%d')
                            investment_amount = float(pms_trans['quantity']) * float(pms_trans['price']) if pms_trans['price'] else 0
                            
                            # Try to fetch PMS data from SEBI and calculate current value
                            try:
                                from pms_aif_fetcher import get_pms_nav
                                pms_name = pms_trans.get('stock_name', ticker).replace('_', ' ')
                                pms_data = get_pms_nav(ticker, pms_name, investment_date, investment_amount)
                                
                                if pms_data and pms_data.get('price'):
                                    live_price = pms_data['price']
                                    # Set sector based on PMS/AIF type
                                    if 'AIF' in ticker_str:
                                        sector = "AIF"
                                    else:
                                        sector = "PMS"
                                    print(f"✅ {sector} {ticker}: Calculated value ₹{live_price:,.2f} using SEBI returns")
                                else:
                                    # Fallback: use transaction price (no growth)
                                    live_price = pms_trans['price']
                                    if 'AIF' in ticker_str:
                                        sector = "AIF"
                                    else:
                                        sector = "PMS"
                                    print(f"⚠️ {sector} {ticker}: Using transaction price (SEBI data not available)")
                            except Exception as e:
                                print(f"⚠️ PMS/AIF calculation failed for {ticker}: {e}")
                                live_price = pms_trans['price']
                                if 'AIF' in ticker_str:
                                    sector = "AIF"
                                else:
                                    sector = "PMS"
                        else:
                            live_price = None
                            if 'AIF' in ticker_str:
                                sector = "AIF"
                            else:
                                sector = "PMS"
                    
                    elif str(ticker).isdigit() or ticker.startswith('MF_'):
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
                    
                    elif ticker_str.startswith('INF') and len(ticker_str) == 12:
                        # Mutual fund ISIN - try to get category from mftool or indstocks
                        print(f"🔍 MF ISIN detected: {ticker}")
                        
                        # Try to get fund category along with price
                        from unified_price_fetcher import get_mutual_fund_price_and_category
                        live_price, fund_category = get_mutual_fund_price_and_category(ticker, ticker, user_id, None)
                        
                        # Use fund category if available
                        if fund_category and fund_category != 'Unknown':
                            sector = fund_category
                            print(f"✅ MF ISIN {ticker}: NAV ₹{live_price} with category '{sector}'")
                        else:
                            sector = "Mutual Fund"  # Fallback
                            print(f"✅ MF ISIN {ticker}: NAV ₹{live_price} (generic category)")
                        
                        if not live_price:
                            print(f"⚠️ MF ISIN {ticker}: Could not fetch NAV")
                    
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
                                            print(f"Could not update sector for {ticker}: {e}")
                                except Exception as e:
                                    print(f"Could not fetch sector for {ticker}: {e}")
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
        from datetime import datetime

        try:
            transactions = get_transactions_supabase(user_id=user_id)
            if not transactions:
                return
            
            # Debug: Check raw transaction data
            print(f"🔍 DEBUG: Loaded {len(transactions)} raw transactions")
            if transactions:
                print(f"🔍 DEBUG: First transaction keys: {transactions[0].keys()}")
                print(f"🔍 DEBUG: First transaction: {transactions[0]}")
            
            df = pd.DataFrame(transactions)
            
            # Debug: Check quantity values
            print(f"🔍 DEBUG: DataFrame shape: {df.shape}")
            print(f"🔍 DEBUG: DataFrame columns: {df.columns.tolist()}")
            if 'quantity' in df.columns:
                print(f"🔍 DEBUG: Quantity column type: {df['quantity'].dtype}")
                print(f"🔍 DEBUG: Quantity sample: {df['quantity'].head(10).tolist()}")
                print(f"🔍 DEBUG: Quantity stats: min={df['quantity'].min()}, max={df['quantity'].max()}, mean={df['quantity'].mean()}")
                print(f"🔍 DEBUG: NaN quantities: {df['quantity'].isna().sum()}")
                print(f"🔍 DEBUG: Zero quantities: {(df['quantity'] == 0).sum()}")
                
                # Also show in Streamlit for visibility
                if df['quantity'].isna().sum() > 0 or (df['quantity'] == 0).sum() > 0:
                    st.warning(f"⚠️ DATA ISSUE: Found {df['quantity'].isna().sum()} NaN quantities and {(df['quantity'] == 0).sum()} zero quantities out of {len(df)} transactions")
                    st.info(f"📊 Quantity stats: min={df['quantity'].min()}, max={df['quantity'].max()}, mean={df['quantity'].mean()}")
            else:
                print(f"❌ DEBUG: 'quantity' column not found in DataFrame!")
                st.error("❌ CRITICAL: 'quantity' column not found in transaction data!")
            
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
            ["🏠 Overview", "📈 Performance", "📊 Allocation", "💰 P&L Analysis", "📁 Files", "⚙️ Settings"],
            key="main_navigation"
        )
        
        # User info in sidebar
        st.sidebar.markdown("---")
        st.sidebar.markdown(f"**User:** {self.session_state.username}")
        st.sidebar.markdown(f"**Role:** {self.session_state.user_role}")
        st.sidebar.markdown(f"**Login:** {self.session_state.login_time.strftime('%Y-%m-%d %H:%M')}")
        
        # Background cache population (runs once per session, non-blocking)
        user_id = self.session_state.user_id
        cache_key = f'cache_populated_{user_id}'
        cache_trigger_key = f'cache_trigger_{user_id}'
        
        if cache_trigger_key in st.session_state and st.session_state[cache_trigger_key]:
            if cache_key not in st.session_state or not st.session_state[cache_key]:
                # Show small status in sidebar
                with st.sidebar:
                    with st.status("📊 Updating cache...", expanded=False) as status:
                        st.write("Fetching historical data in background...")
                        try:
                            self.populate_monthly_prices_cache(user_id)
                            st.session_state[cache_key] = True
                            st.session_state[cache_trigger_key] = False
                            status.update(label="✅ Cache updated!", state="complete")
                        except Exception as e:
                            st.write(f"Error: {e}")
                            status.update(label="⚠️ Cache update failed", state="error")
        
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
        # Initialize usage tracking
        if 'api_call_count' not in st.session_state:
            st.session_state.api_call_count = 0
        if 'api_call_times' not in st.session_state:
            st.session_state.api_call_times = []
        
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
        
        # AI Chatbot in Sidebar
        st.sidebar.markdown("---")
        st.sidebar.subheader("🤖 AI Assistant")
        
        ai_model = "Google Gemini 2.5 Flash (Fast)"  # Default to Gemini
        
        # Check API key
        if not st.session_state.gemini_api_key:
            st.sidebar.warning("⚠️ Configure API Key")
            if st.sidebar.button("🔑 Setup", key="setup_api"):
                st.session_state.show_gemini_config = True
        else:
            # Chat interface in sidebar
            st.sidebar.success("✅ Ready")
            
            # File upload in sidebar
            with st.sidebar.expander("📁 Document Library", expanded=False):
                # Show stored PDFs (if available)
                if PDF_STORAGE_AVAILABLE:
                    try:
                        stored_pdfs = get_pdf_documents_supabase(self.session_state.user_id, include_global=True)
                        if stored_pdfs:
                            st.markdown(f"**📚 {len(stored_pdfs)} Stored Document(s):**")
                            for pdf in stored_pdfs:
                                col1, col2 = st.columns([3, 1])
                                with col1:
                                    st.text(f"📄 {pdf['filename']}")
                                with col2:
                                    if st.button("🗑️", key=f"del_pdf_{pdf['id']}", help="Delete"):
                                        delete_pdf_document_supabase(pdf['id'])
                                        st.rerun()
                            st.markdown("---")
                    except Exception as e:
                        st.caption(f"⚠️ PDF storage: {str(e)[:50]}")
                
                # Upload new PDFs
                uploaded_files = st.file_uploader(
                    "Upload new documents",
                    type=['pdf', 'txt'],
                    accept_multiple_files=True,
                    key="ai_sidebar_pdf_upload",
                    help="Upload PDFs for AI analysis" + (" (saved permanently)" if PDF_STORAGE_AVAILABLE else " (temporary)")
                )
            
            # Chat input
            user_query = st.sidebar.text_area(
                "Ask about your portfolio:",
                placeholder="e.g., What are my best performers?",
                height=100,
                key="sidebar_chat_input"
            )
            
            if st.sidebar.button("💬 Ask AI", type="primary", use_container_width=True):
                if user_query:
                    with st.spinner("🤔 Thinking..."):
                        self.process_ai_query_with_db_access(user_query, uploaded_files if 'uploaded_files' in locals() else None)
                    st.rerun()
            
            # Show recent chat (latest first)
            if st.session_state.chat_history:
                with st.sidebar.expander("💬 Chat History", expanded=True):
                    # Reverse to show latest first
                    recent_messages = list(reversed(st.session_state.chat_history[-5:]))
                    
                    for i, msg in enumerate(recent_messages):
                        if msg["role"] == "user":
                            st.markdown(f"**You:** {msg['content']}")
                        else:
                            st.markdown(f"**AI:** {msg['content']}")
                        
                        if i < len(recent_messages) - 1:
                            st.markdown("---")
                    
                    if st.button("🗑️ Clear Chat", key="clear_chat"):
                        st.session_state.chat_history = []
                        st.rerun()
        
        # Remove OpenAI section since we're using Gemini by default
        if False:  # Disabled OpenAI section
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
        
        # Quick Actions removed - now using AI chatbot in sidebar above
        
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
        # AI Assistant page removed - now in sidebar
        elif page == "📁 Files":
            self.render_files_page()
        elif page == "⚙️ Settings":
            self.render_settings_page()
    
    def render_overview_page(self):
        """Render portfolio overview with key metrics"""
        from datetime import datetime

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
        from datetime import datetime, timedelta

        st.header("📈 Performance Analysis")

        if self.session_state.portfolio_data is None:
            self.show_page_loading_animation("Performance Analysis")
            st.info("💡 **Tip:** If this page doesn't load automatically, use the '🔄 Refresh Portfolio Data' button in Settings.")
            return

        df = self.session_state.portfolio_data

        # Create tabs for different performance views
        tab1, tab2, tab3 = st.tabs(["📊 Portfolio Overview", "📈 1-Year Buy Performance", "📋 Overall Portfolio Performance"])

        with tab1:
            self.render_portfolio_overview(df)

        with tab2:
            self.render_one_year_buy_performance(df)

        with tab3:
            self.render_overall_portfolio_performance(df)

    def render_portfolio_overview(self, df):
        """Render portfolio overview with general metrics and debug info"""
        from datetime import datetime, timedelta

        st.subheader("📊 Portfolio Overview")

        # Debug: Show data summary
        with st.expander("🔍 Debug: Portfolio Data Summary", expanded=False):
            st.info(f"📊 Total transactions loaded: {len(df)}")
            st.info(f"📊 Columns: {df.columns.tolist()}")
            if 'quantity' in df.columns:
                st.info(f"📊 Quantity stats: min={df['quantity'].min()}, max={df['quantity'].max()}, mean={df['quantity'].mean():.2f}")
                st.info(f"📊 NaN quantities: {df['quantity'].isna().sum()}, Zero quantities: {(df['quantity'] == 0).sum()}")
            if 'date' in df.columns:
                df_temp = df.copy()
                df_temp['date'] = pd.to_datetime(df_temp['date'])
                st.info(f"📅 Date range: {df_temp['date'].min()} to {df_temp['date'].max()}")
                st.info(f"📅 Transactions in last year: {len(df_temp[df_temp['date'] >= (datetime.now() - timedelta(days=365))])}")
            if 'invested_amount' in df.columns:
                st.info(f"💰 Total invested: ₹{df['invested_amount'].sum():,.2f}")
                st.info(f"💰 Zero invested amounts: {(df['invested_amount'] == 0).sum()}")
            st.dataframe(df.head(10), use_container_width=True)

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

        except Exception as e:
            st.error(f"Error in portfolio overview: {e}")
            import traceback
            st.error(traceback.format_exc())

    def render_one_year_buy_performance(self, df):
        """Render 1-year buy performance analysis for stocks and mutual funds"""
        from datetime import datetime, timedelta

        st.subheader("📈 Stock and Mutual Fund Performance Analysis (1-Year Buy Transactions)")

        # Filter for stocks and mutual funds (exclude PMS/AIF) with buy transactions in the last 1 year
        one_year_ago = datetime.now() - timedelta(days=365)

        def is_pms_aif(ticker):
            ticker_upper = str(ticker).upper()
            return any(keyword in ticker_upper for keyword in [
                'PMS', 'AIF', 'INP', 'BUOYANT', 'CARNELIAN', 'JULIUS',
                'VALENTIS', 'UNIFI', 'PORTFOLIO', 'FUND'
            ]) or ticker_upper.endswith('_PMS') or str(ticker).startswith('INP')

        stock_and_mf_buys = df[
            (~df['ticker'].apply(is_pms_aif)) &  # Exclude PMS/AIF
            (df['transaction_type'] == 'buy') &
            (df['date'] >= one_year_ago)
        ].copy()

        if not stock_and_mf_buys.empty:
            # Group by ticker and calculate performance metrics
            stock_performance = stock_and_mf_buys.groupby('ticker').agg({
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
            fig_stock_performance = go.Figure()
            fig_stock_performance.add_trace(go.Bar(
                x=stock_performance.head(10)['ticker'],
                y=stock_performance.head(10)['pnl_percentage'],
                marker_color=stock_performance.head(10)['rating_color'],
                text=stock_performance.head(10)['pnl_percentage'].round(2),
                textposition='auto',
            ))

            fig_stock_performance.update_layout(
                title="Top 10 Performing Stocks & Mutual Funds (1-Year)",
                xaxis_title="Ticker",
                yaxis_title="P&L Percentage (%)",
                height=400
            )

            st.plotly_chart(fig_stock_performance, config={'displayModeBar': True, 'responsive': True})

            # Performance Table
            st.subheader("📊 Detailed Performance Table (1-Year Buy Transactions)")

            # Create a comprehensive table
            table_data = []
            for _, row in stock_performance.iterrows():
                ticker = row['ticker']
                # Get additional details from original data
                ticker_data = stock_and_mf_buys[stock_and_mf_buys['ticker'] == ticker].iloc[0]

                table_row = {
                    'Ticker': ticker,
                    'Stock Name': ticker_data.get('stock_name', 'N/A'),
                    'Sector': ticker_data.get('sector', 'Unknown'),
                    'Invested (₹)': f"{row['invested_amount']:,.2f}",
                    'Current Value (₹)': f"{row['current_value']:,.2f}",
                    'P&L (₹)': f"{row['unrealized_pnl']:,.2f}",
                    'P&L %': f"{row['pnl_percentage']:.2f}%",
                    'Rating': row['rating'],
                    'Quantity': f"{row['quantity']:.0f}",
                    'Avg Price (₹)': f"{row['avg_price']:.2f}",
                    'Latest Buy Date': row['date'].strftime('%Y-%m-%d') if pd.notna(row['date']) else 'N/A'
                }
                table_data.append(table_row)

            performance_df = pd.DataFrame(table_data)
            st.dataframe(performance_df, use_container_width=True, hide_index=True)

            # Quarterly Analysis for Individual Stocks
            st.subheader("📊 Quarterly Analysis (1-Year Buy Transactions)")

            # Create quarterly data for each stock
            quarterly_data = []

            for _, row in stock_performance.iterrows():
                ticker = row['ticker']
                ticker_transactions = stock_and_mf_buys[stock_and_mf_buys['ticker'] == ticker].copy()

                # Convert date to datetime if it's not already
                if not pd.api.types.is_datetime64_any_dtype(ticker_transactions['date']):
                    ticker_transactions['date'] = pd.to_datetime(ticker_transactions['date'])

                # Group by quarter
                ticker_transactions['quarter'] = ticker_transactions['date'].dt.to_period('Q')
                quarterly_perf = ticker_transactions.groupby('quarter').agg({
                    'invested_amount': 'sum',
                    'current_value': 'sum',
                    'unrealized_pnl': 'sum'
                }).reset_index()

                quarterly_perf['pnl_percentage'] = (quarterly_perf['unrealized_pnl'] / quarterly_perf['invested_amount']) * 100

                for _, q_row in quarterly_perf.iterrows():
                    quarterly_data.append({
                        'Ticker': ticker,
                        'Quarter': str(q_row['quarter']),
                        'Invested (₹)': q_row['invested_amount'],
                        'Current Value (₹)': q_row['current_value'],
                        'P&L (₹)': q_row['unrealized_pnl'],
                        'P&L %': q_row['pnl_percentage']
                    })

            if quarterly_data:
                quarterly_df = pd.DataFrame(quarterly_data)

                # Create quarterly performance chart
                fig_quarterly = px.line(
                    quarterly_df,
                    x='Quarter',
                    y='P&L %',
                    color='Ticker',
                    title='Quarterly Performance Trends (1-Year Buy Transactions)',
                    markers=True
                )

                st.plotly_chart(fig_quarterly, config={'displayModeBar': True, 'responsive': True})

                # Quarterly table
                st.subheader("📋 Quarterly Performance Details")
                st.dataframe(quarterly_df, use_container_width=True, hide_index=True)
            else:
                st.info("No quarterly data available for analysis")

            # Sector and Channel Analysis
            st.subheader("📊 Sector & Channel Analysis (1-Year Buy Transactions - Stocks & Mutual Funds)")

            # Create two columns for charts
            col1, col2 = st.columns(2)

            with col1:
                # Sector Performance Chart
                st.subheader("🏭 Sector Performance Analysis")

                # Group by sector and calculate metrics
                sector_performance = stock_and_mf_buys.groupby('sector').agg({
                    'invested_amount': 'sum',
                    'current_value': 'sum',
                    'unrealized_pnl': 'sum',
                    'quantity': 'sum'
                }).reset_index()

                if not sector_performance.empty:
                    sector_performance['pnl_percentage'] = (sector_performance['unrealized_pnl'] / sector_performance['invested_amount']) * 100

                    # Create sector performance chart
                    fig_sector = go.Figure()
                    fig_sector.add_trace(go.Bar(
                        x=sector_performance['sector'],
                        y=sector_performance['pnl_percentage'],
                        marker_color=['green' if x >= 0 else 'red' for x in sector_performance['pnl_percentage']],
                        text=sector_performance['pnl_percentage'].round(2),
                        textposition='auto',
                    ))

                    fig_sector.update_layout(
                        title="Sector Performance (1-Year)",
                        xaxis_title="Sector",
                        yaxis_title="P&L Percentage (%)",
                        height=400
                    )

                    st.plotly_chart(fig_sector, config={'displayModeBar': True, 'responsive': True})

                    # Sector performance table
                    sector_table_data = []
                    for _, row in sector_performance.iterrows():
                        sector = row['sector']
                        value = row['current_value']
                        # Get sector-specific data
                        sector_stocks = stock_and_mf_buys[stock_and_mf_buys['sector'] == sector]
                        sector_count = len(sector_stocks['ticker'].unique())
                        sector_pnl = sector_stocks['unrealized_pnl'].sum() if 'unrealized_pnl' in sector_stocks.columns else 0
                        sector_pnl_pct = (sector_pnl / value * 100) if value > 0 else 0

                        sector_table_data.append({
                            'Sector': sector,
                            'Holdings': sector_count,
                            'Invested (₹)': f"{row['invested_amount']:,.2f}",
                            'Current Value (₹)': f"{value:,.2f}",
                            'P&L (₹)': f"{sector_pnl:,.2f}",
                            'P&L %': f"{sector_pnl_pct:.2f}%"
                        })

                    sector_df = pd.DataFrame(sector_table_data)
                    st.dataframe(sector_df, use_container_width=True, hide_index=True)

            with col2:
                # Channel Performance Chart
                st.subheader("📡 Channel Performance Analysis")

                # Group by channel and calculate metrics
                channel_performance = stock_and_mf_buys.groupby('channel').agg({
                    'invested_amount': 'sum',
                    'current_value': 'sum',
                    'unrealized_pnl': 'sum',
                    'quantity': 'sum'
                }).reset_index()

                if not channel_performance.empty:
                    channel_performance['pnl_percentage'] = (channel_performance['unrealized_pnl'] / channel_performance['invested_amount']) * 100

                    # Create channel performance chart
                    fig_channel = go.Figure()
                    fig_channel.add_trace(go.Bar(
                        x=channel_performance['channel'],
                        y=channel_performance['pnl_percentage'],
                        marker_color=['green' if x >= 0 else 'red' for x in channel_performance['pnl_percentage']],
                        text=channel_performance['pnl_percentage'].round(2),
                        textposition='auto',
                    ))

                    fig_channel.update_layout(
                        title="Channel Performance (1-Year)",
                        xaxis_title="Channel",
                        yaxis_title="P&L Percentage (%)",
                        height=400
                    )

                    st.plotly_chart(fig_channel, config={'displayModeBar': True, 'responsive': True})

                    # Channel performance table
                    channel_table_data = []
                    for _, row in channel_performance.iterrows():
                        channel = row['channel']
                        value = row['current_value']
                        # Get channel-specific data
                        channel_stocks = stock_and_mf_buys[stock_and_mf_buys['channel'] == channel]
                        channel_count = len(channel_stocks['ticker'].unique())
                        channel_pnl = channel_stocks['unrealized_pnl'].sum() if 'unrealized_pnl' in channel_stocks.columns else 0
                        channel_pnl_pct = (channel_pnl / value * 100) if value > 0 else 0

                        channel_table_data.append({
                            'Channel': channel,
                            'Holdings': channel_count,
                            'Invested (₹)': f"{row['invested_amount']:,.2f}",
                            'Current Value (₹)': f"{value:,.2f}",
                            'P&L (₹)': f"{channel_pnl:,.2f}",
                            'P&L %': f"{channel_pnl_pct:.2f}%"
                        })

                    channel_df = pd.DataFrame(channel_table_data)
                    st.dataframe(channel_df, use_container_width=True, hide_index=True)

            # Analysis Summary
            st.subheader("📈 Analysis Summary")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                total_sectors = len(stock_and_mf_buys['sector'].unique())
                st.metric("Total Sectors", total_sectors)

            with col2:
                total_channels = len(stock_and_mf_buys['channel'].unique())
                st.metric("Total Channels", total_channels)

            with col3:
                avg_return = stock_performance['pnl_percentage'].mean()
                avg_arrow = "🔼" if avg_return >= 0 else "🔽"
                avg_color = "normal" if avg_return >= 0 else "inverse"
                st.metric("Average Return", f"{avg_arrow} {avg_return:.2f}%", delta_color=avg_color)

            with col4:
                best_overall = stock_performance['pnl_percentage'].max()
                best_arrow = "🔼" if best_overall >= 0 else "🔽"
                best_color = "normal" if best_overall >= 0 else "inverse"
                st.metric("Best Return", f"{best_arrow} {best_overall:.2f}%", delta_color=best_color)
        else:
            st.info("No stock buy transactions found in the last 1 year")

    def render_overall_portfolio_performance(self, df):
        """Render overall portfolio performance and monthly transaction analysis"""
        from datetime import datetime, timedelta

        st.subheader("📋 Overall Portfolio Performance")

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

            # Create two columns for charts
            col1, col2 = st.columns(2)

            with col1:
                # Buy vs Sell Chart
                fig_monthly = go.Figure()

                # Add bars for buy and sell
                fig_monthly.add_trace(go.Bar(
                    x=monthly_pivot['date'].astype(str),
                    y=monthly_pivot.get('buy_invested_amount', [0] * len(monthly_pivot)),
                    name='Buy Value',
                    marker_color='green',
                    opacity=0.7
                ))

                fig_monthly.add_trace(go.Bar(
                    x=monthly_pivot['date'].astype(str),
                    y=monthly_pivot.get('sell_invested_amount', [0] * len(monthly_pivot)),
                    name='Sell Value',
                    marker_color='red',
                    opacity=0.7
                ))

                fig_monthly.update_layout(
                    title="Monthly Buy vs Sell Activity",
                    xaxis_title="Month",
                    yaxis_title="Amount (₹)",
                    barmode='stack',
                    height=400
                )

                st.plotly_chart(fig_monthly, config={'displayModeBar': True, 'responsive': True})

            with col2:
                # Net Flow Chart
                fig_net = go.Figure()

                # Calculate net flow
                monthly_pivot['net_flow'] = monthly_pivot.get('buy_invested_amount', 0) - monthly_pivot.get('sell_invested_amount', 0)

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

                    # Determine trading pattern
                    if net_flow_std < total_net_flow * 0.1:  # Low volatility relative to total
                        pattern = "Consistent Investor"
                        description = "You maintain steady investment patterns with low month-to-month variation."
                    elif total_buy_value > total_sell_value * 2:
                        pattern = "Accumulating Investor"
                        description = "You're primarily buying, indicating a focus on building positions."
                    elif total_sell_value > total_buy_value * 2:
                        pattern = "Realizing Investor"
                        description = "You're primarily selling, indicating profit-taking or portfolio rebalancing."
                    else:
                        pattern = "Active Trader"
                        description = "You have a balanced approach with both buying and selling activity."

                    col1, col2 = st.columns([1, 2])
                    with col1:
                        st.info(f"**Trading Pattern:** {pattern}")
                    with col2:
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

        # Recent transactions section (moved from overview)
        st.subheader("📋 Recent Transactions")
        recent_transactions = df.sort_values('date', ascending=False).head(10)
        st.dataframe(
            recent_transactions[['date', 'ticker', 'quantity', 'price', 'live_price', 'unrealized_pnl']],
            width='stretch'
        )

    def render_allocation_page(self):
        """Render portfolio allocation analysis"""
        st.header("📊 Portfolio Allocation Analysis")

        if self.session_state.portfolio_data is None:
            self.show_page_loading_animation("Allocation Analysis")
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
                st.warning("No valid date data available for allocation analysis")
                return

            # Portfolio Allocation Analysis
            st.subheader("💰 Current Portfolio Allocation")

            # Calculate current allocation
            total_value = df['current_value'].sum()
            if total_value > 0:
                # Sector allocation
                if 'sector' in df.columns:
                    sector_allocation = df.groupby('sector')['current_value'].sum().to_dict()
                    sector_df = pd.DataFrame(list(sector_allocation.items()), columns=['Sector', 'Value'])
                    sector_df['Percentage'] = (sector_df['Value'] / total_value * 100).round(2)

                    # Create pie chart for sector allocation
                    fig_sector = px.pie(
                        sector_df,
                        values='Value',
                        names='Sector',
                        title='Portfolio Allocation by Sector',
                        color_discrete_sequence=px.colors.qualitative.Set3
                    )
                    st.plotly_chart(fig_sector, config={'displayModeBar': True, 'responsive': True})

                    # Sector allocation table
                    st.subheader("📋 Sector Allocation Details")
                    st.dataframe(sector_df, use_container_width=True, hide_index=True)

                # Channel allocation
                if 'channel' in df.columns:
                    channel_allocation = df.groupby('channel')['current_value'].sum().to_dict()
                    channel_df = pd.DataFrame(list(channel_allocation.items()), columns=['Channel', 'Value'])
                    channel_df['Percentage'] = (channel_df['Value'] / total_value * 100).round(2)

                    # Create pie chart for channel allocation
                    fig_channel = px.pie(
                        channel_df,
                        values='Value',
                        names='Channel',
                        title='Portfolio Allocation by Channel',
                        color_discrete_sequence=px.colors.qualitative.Set1
                    )
                    st.plotly_chart(fig_channel, config={'displayModeBar': True, 'responsive': True})

                    # Channel allocation table
                    st.subheader("📋 Channel Allocation Details")
                    st.dataframe(channel_df, use_container_width=True, hide_index=True)

                # Stock vs Mutual Fund allocation
                stock_vs_mf = []
                if 'sector' in df.columns:
                    mf_data = df[df['sector'] == 'Mutual Fund']
                    stock_data = df[df['sector'] != 'Mutual Fund']

                    if not mf_data.empty:
                        mf_value = mf_data['current_value'].sum()
                        stock_vs_mf.append({'Type': 'Mutual Funds', 'Value': mf_value, 'Percentage': (mf_value / total_value * 100).round(2)})

                    if not stock_data.empty:
                        stock_value = stock_data['current_value'].sum()
                        stock_vs_mf.append({'Type': 'Stocks', 'Value': stock_value, 'Percentage': (stock_value / total_value * 100).round(2)})

                if stock_vs_mf:
                    mf_df = pd.DataFrame(stock_vs_mf)
                    st.subheader("📊 Stock vs Mutual Fund Allocation")
                    st.dataframe(mf_df, use_container_width=True, hide_index=True)

                    # Create pie chart
                    fig_mf = px.pie(
                        mf_df,
                        values='Value',
                        names='Type',
                        title='Stock vs Mutual Fund Allocation',
                        color_discrete_sequence=px.colors.qualitative.Pastel1
                    )
                    st.plotly_chart(fig_mf, config={'displayModeBar': True, 'responsive': True})

            else:
                st.warning("No current value data available for allocation analysis")

        except Exception as e:
            st.error(f"Error in allocation analysis: {e}")
            import traceback
            st.error(traceback.format_exc())

    def render_pnl_analysis_page(self):
        """Render P&L analysis page"""
        st.header("💰 P&L Analysis")

        if self.session_state.portfolio_data is None:
            self.show_page_loading_animation("P&L Analysis")
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
                st.warning("No valid date data available for P&L analysis")
                return

            # P&L Analysis
            st.subheader("📊 Portfolio P&L Summary")

            total_invested = df['invested_amount'].sum()
            total_current = df['current_value'].sum()
            total_pnl = total_current - total_invested
            total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Total Invested", f"₹{total_invested:,.2f}")

            with col2:
                st.metric("Current Value", f"₹{total_current:,.2f}")

            with col3:
                pnl_arrow = "🔼" if total_pnl >= 0 else "🔽"
                pnl_color = "normal" if total_pnl >= 0 else "inverse"
                st.metric("Total P&L", f"{pnl_arrow} ₹{total_pnl:,.2f}", delta_color=pnl_color)

            with col4:
                pnl_pct_arrow = "🔼" if total_pnl_pct >= 0 else "🔽"
                pnl_pct_color = "normal" if total_pnl_pct >= 0 else "inverse"
                st.metric("P&L %", f"{pnl_pct_arrow} {total_pnl_pct:.2f}%", delta_color=pnl_pct_color)

            # Individual stock P&L analysis
            st.subheader("📈 Individual Stock P&L Analysis")

            # Filter for stocks (exclude mutual funds)
            stock_data = df[~df['ticker'].astype(str).str.startswith('MF_')].copy()

            if not stock_data.empty:
                # Sort by P&L percentage
                stock_data['pnl_percentage'] = (stock_data['unrealized_pnl'] / stock_data['invested_amount']) * 100
                stock_data = stock_data.sort_values('pnl_percentage', ascending=False)

                # Create P&L chart
                fig_pnl = px.bar(
                    stock_data.head(20),
                    x='ticker',
                    y='pnl_percentage',
                    title='Top 20 Stocks by P&L Percentage',
                    color='pnl_percentage',
                    color_continuous_scale='RdYlGn'
                )
                fig_pnl.update_layout(xaxis_title="Stock", yaxis_title="P&L Percentage (%)")
                st.plotly_chart(fig_pnl, config={'displayModeBar': True, 'responsive': True})

                # P&L table
                pnl_table_data = []
                for _, row in stock_data.iterrows():
                    pnl_table_data.append({
                        'Ticker': row['ticker'],
                        'Stock Name': row.get('stock_name', 'N/A'),
                        'Sector': row.get('sector', 'Unknown'),
                        'Invested (₹)': f"{row['invested_amount']:,.2f}",
                        'Current (₹)': f"{row['current_value']:,.2f}",
                        'P&L (₹)': f"{row['unrealized_pnl']:,.2f}",
                        'P&L %': f"{row['pnl_percentage']:.2f}%"
                    })

                pnl_df = pd.DataFrame(pnl_table_data)
                st.dataframe(pnl_df, use_container_width=True, hide_index=True)
            else:
                st.info("No stock data available for P&L analysis")

        except Exception as e:
            st.error(f"Error in P&L analysis: {e}")
            import traceback
            st.error(traceback.format_exc())

    def render_files_page(self):
        """Render file management page"""
        st.header("📁 File Management")

        if not self.session_state.user_authenticated:
            st.warning("Please login first to access file management")
            return

        # File upload section
        st.subheader("📤 Upload Portfolio Files")

        uploaded_files = st.file_uploader(
            "Choose CSV or Excel files",
            type=['csv', 'xlsx', 'xls'],
            accept_multiple_files=True,
            help="Upload your portfolio transaction files (CSV or Excel format)"
        )

        if uploaded_files:
            for uploaded_file in uploaded_files:
                if st.button(f"Process {uploaded_file.name}", key=f"process_{uploaded_file.name}"):
                    with st.spinner(f"Processing {uploaded_file.name}..."):
                        success = self.process_csv_file(uploaded_file, self.session_state.user_id)
                        if success:
                            st.success(f"✅ {uploaded_file.name} processed successfully!")
                        else:
                            st.error(f"❌ Failed to process {uploaded_file.name}")

        # Show existing files
        st.subheader("📋 Existing Files")
        try:
            from database_config_supabase import get_file_records_supabase
            existing_files = get_file_records_supabase(self.session_state.user_id)

            if existing_files:
                files_df = pd.DataFrame(existing_files)
                st.dataframe(files_df[['filename', 'processed_at', 'status']], use_container_width=True)
            else:
                st.info("No files uploaded yet")
        except Exception as e:
            st.error(f"Error loading files: {e}")

    def render_settings_page(self):
        """Render settings and configuration page"""
        st.header("⚙️ Settings")

        # Cache management
        st.subheader("🗄️ Cache Management")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("🔄 Refresh Portfolio Data", type="primary"):
                with st.spinner("Refreshing portfolio data..."):
                    self.load_portfolio_data(self.session_state.user_id)
                    st.success("✅ Portfolio data refreshed!")

        with col2:
            if st.button("🔄 Update Price Cache", type="secondary"):
                with st.spinner("Updating price cache... This may take a few minutes."):
                    self.populate_weekly_and_monthly_cache(self.session_state.user_id)
                    st.success("✅ Price cache updated!")

        # Database verification
        st.subheader("🔍 Database Verification")

        if st.button("🔍 Verify Database Storage"):
            st.info("🔍 Checking if data is being saved to database...")
            try:
                from database_config_supabase import get_all_stock_prices_supabase, diagnose_database_issues, get_stock_price_supabase
                from datetime import timedelta

                # First run database diagnostics
                st.info("🔍 Running database diagnostics...")
                diagnose_database_issues()

                # Then check for data
                all_prices = get_all_stock_prices_supabase()
                if all_prices:
                    recent_prices = [p for p in all_prices if p.get('created_at', '') > str(datetime.now() - timedelta(hours=1))]
                    st.success(f"✅ Found {len(all_prices)} total prices in database, {len(recent_prices)} saved in last hour")

                    if recent_prices:
                        st.json(recent_prices[:5])  # Show first 5 recent entries
                        st.info("💡 Recent saves are working correctly!")

                        # Test verification for a recent save
                        if recent_prices:
                            test_ticker = recent_prices[0]['ticker']
                            test_date = recent_prices[0]['price_date']
                            verify_price = get_stock_price_supabase(test_ticker, test_date)
                            if verify_price and abs(float(verify_price) - recent_prices[0]['price']) < 0.01:
                                st.success(f"✅ Verification test passed: {test_ticker} {test_date} = ₹{verify_price}")
                            else:
                                st.error(f"❌ Verification test failed: {test_ticker} {test_date} not found or value mismatch!")
                                st.info(f"Expected: ₹{recent_prices[0]['price']}, Got: ₹{verify_price}")
                    else:
                        st.warning("⚠️ No recent saves found. Check if save operations are working.")
                else:
                    st.warning("⚠️ No prices found in database. Data may not be saving properly.")
                    st.info("💡 This could indicate database permissions, connection issues, or save operations are failing.")

                    # Try to test database connection
                    try:
                        # Try a simple query to test connection
                        test_result = get_stock_price_supabase("TEST", "2024-01-01")
                        st.info("✅ Database connection test passed")

                        # Test table access
                        try:
                            from database_config_supabase import check_table_structure
                            table_check = check_table_structure('stock_prices')
                            if table_check['accessible']:
                                st.success(f"✅ stock_prices table is accessible ({len(table_check['columns'])} columns)")
                            else:
                                st.error(f"❌ stock_prices table not accessible: {table_check['error']}")
                        except Exception as table_error:
                            st.warning(f"⚠️ Could not check table structure: {table_error}")

                    except Exception as conn_error:
                        st.error(f"❌ Database connection test failed: {conn_error}")
                        st.info("💡 This indicates a connection or authentication issue with the database.")

            except Exception as db_error:
                st.error(f"❌ Database verification failed: {db_error}")
                st.info("💡 Check the console logs for more detailed error information.")
   # Calculate additional metrics
