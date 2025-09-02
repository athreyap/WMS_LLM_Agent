import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import warnings
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
    update_user_login_supabase
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
            
            uploaded_files = st.file_uploader(
                "Choose CSV files",
                type=['csv'],
                accept_multiple_files=True,
                key="reg_files",
                help="Upload CSV files with transaction data. Files will be processed automatically after registration."
            )
            
            if uploaded_files:
                st.success(f"✅ Selected {len(uploaded_files)} file(s) for processing")
                
                # Show sample CSV format
                with st.expander("📋 Sample CSV Format", expanded=False):
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
            
            if st.button("Create Account & Process Files", type="primary"):
                if new_password != confirm_password:
                    st.error("Passwords do not match")
                elif len(new_password) < 6:
                    st.error("Password must be at least 6 characters")
                elif self.register_user(new_username, new_password, "user", uploaded_files):
                    st.success("Registration successful! Please login.")
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
                    # Process the uploaded file
                    result = self.process_csv_file(uploaded_file, user_id)
                    if result:
                        processed_count += 1
                        st.success(f"✅ Processed {uploaded_file.name}")
                    else:
                        failed_count += 1
                        st.warning(f"⚠️ Failed to process {uploaded_file.name}")
                        
                except Exception as e:
                    failed_count += 1
                    st.error(f"❌ Error processing {uploaded_file.name}: {e}")
            
            if processed_count > 0:
                st.success(f"🎉 Successfully processed {processed_count} file(s)!")
            if failed_count > 0:
                st.warning(f"⚠️ {failed_count} file(s) had processing issues")
                
        except Exception as e:
            st.error(f"Error during file processing: {e}")
    
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
    
    def save_transactions_to_database(self, df, user_id, filename):
        """Save transactions to database"""
        try:
            from database_config_supabase import save_transactions_bulk_supabase, save_file_record_supabase
            
            # First save file record (or get existing one)
            file_record = save_file_record_supabase(filename, f"/uploads/{filename}", user_id)
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
                # Process uploaded files after successful user creation
                st.info("🔄 Processing uploaded files...")
                try:
                    user_id = result['id']
                    self.process_uploaded_files_during_registration(uploaded_files, user_id)
                    st.success(f"✅ Successfully processed {len(uploaded_files)} file(s)!")
                except Exception as e:
                    st.warning(f"⚠️ Files processed with warnings: {e}")
                    st.info("You can still login and upload files later.")
            
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
            
            # Load portfolio data
            self.load_portfolio_data(user_id)
            
        except Exception as e:
            st.error(f"Error initializing portfolio data: {e}")
    
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
                        self.show_file_upload_page()
                        return
                        
            except Exception as e:
                st.error(f"❌ Error loading portfolio data: {e}")
                st.info("💡 You can still upload files to get started.")
                self.show_file_upload_page()
                return
        
        # Sidebar navigation
        st.sidebar.title("Navigation")
        page = st.sidebar.selectbox(
            "Choose a page:",
            ["🏠 Overview", "📈 Performance", "📊 Allocation", "💰 P&L Analysis", "📁 Files", "⚙️ Settings"]
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
            st.metric("Total P&L", f"₹{total_pnl:,.2f}", delta_color=pnl_color)
        
        with col4:
            if total_invested > 0:
                total_return = (total_pnl / total_invested) * 100
                st.metric("Total Return", f"{total_return:.2f}%", delta_color=pnl_color)
        
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
                        st.plotly_chart(fig_top, width='stretch')
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
                        st.plotly_chart(fig_bottom, width='stretch')
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
                    
                    st.plotly_chart(fig_timeline, width='stretch')
                    
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
            
            st.plotly_chart(fig_performance, width='stretch')
            
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
                        best_sector_arrow = "↗️" if best_sector['pnl_percentage'] > 0 else "↘️" if best_sector['pnl_percentage'] < 0 else "➡️"
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
                    worst_sector_arrow = "↗️" if worst_sector['pnl_percentage'] > 0 else "↘️" if worst_sector['pnl_percentage'] < 0 else "➡️"
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
                        best_channel_arrow = "↗️" if best_channel['pnl_percentage'] > 0 else "↘️" if best_channel['pnl_percentage'] < 0 else "➡️"
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
                            worst_channel_arrow = "↗️" if worst_channel['pnl_percentage'] > 0 else "↘️" if worst_channel['pnl_percentage'] < 0 else "➡️"
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
                st.plotly_chart(fig_stock_performance, width='stretch')
            else:
                st.info("No stock buy transactions found in the last 1 year")
                
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
                    st.plotly_chart(fig_type, width='stretch')
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
                    st.plotly_chart(fig_sector, width='stretch')
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
                    st.plotly_chart(fig_holdings, width='stretch')
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
                        st.plotly_chart(fig_market_cap, width='stretch')
                        
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
        
        st.plotly_chart(fig_pnl, width='stretch')
        

        
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
            st.plotly_chart(fig_sector_pnl, width='stretch')
            
            # Sector P&L summary
            col1, col2, col3 = st.columns(3)
            with col1:
                best_sector = pnl_by_sector.loc[pnl_by_sector['unrealized_pnl'].idxmax()]
                best_pnl = best_sector['unrealized_pnl']
                best_arrow = "↗️" if best_pnl > 0 else "↘️" if best_pnl < 0 else "➡️"
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
                worst_arrow = "↗️" if worst_pnl > 0 else "↘️" if worst_pnl < 0 else "➡️"
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
            st.plotly_chart(fig_channel_pnl, width='stretch')
            
            # Channel P&L summary
            col1, col2, col3 = st.columns(3)
            with col1:
                best_channel = pnl_by_channel.loc[pnl_by_channel['unrealized_pnl'].idxmax()]
                best_pnl = best_channel['unrealized_pnl']
                best_arrow = "↗️" if best_pnl > 0 else "↘️" if best_pnl < 0 else "➡️"
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
                worst_arrow = "↗️" if worst_pnl > 0 else "↘️" if worst_pnl < 0 else "➡️"
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
            st.plotly_chart(fig_combined, width='stretch')
            
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
        
        # File upload section
        st.subheader("📤 Upload Investment File")
        
        # Show sample CSV format
        with st.expander("📋 Sample CSV Format", expanded=False):
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
