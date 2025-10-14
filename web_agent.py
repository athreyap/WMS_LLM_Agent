import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import time
import warnings
import openai
import json
import base64
import io
import PyPDF2
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False
from PIL import Image
try:
    from pdf2image import convert_from_bytes
    PDF_TO_IMAGE_AVAILABLE = True
except ImportError:
    PDF_TO_IMAGE_AVAILABLE = False
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
    get_all_monthly_stock_prices_supabase,
    # Batch operations for performance
    bulk_update_stock_data,
    bulk_save_historical_prices,
    bulk_get_stock_data
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

# Import price fetching functions
from unified_price_fetcher import (
    get_stock_price,
    get_mutual_fund_price,
    get_stock_price_and_sector,
    get_mutual_fund_price_and_category
)

# Import BULK price fetching functions (NEW - 20x faster!)
try:
    from bulk_integration import (
        fetch_historical_prices_bulk,
        fetch_weekly_prices_bulk,
        fetch_live_prices_bulk,
        categorize_tickers
    )
    BULK_FETCH_AVAILABLE = True
    print("✅ Bulk price fetching enabled (20x faster!)")
except ImportError:
    BULK_FETCH_AVAILABLE = False
    print("⚠️ Bulk price fetching not available - using individual calls")

# Import optimized data loader
try:
    from optimized_data_loader import (
        get_portfolio_fast,
        get_chatbot_context,
        clear_portfolio_cache
    )
    OPTIMIZED_LOADER_AVAILABLE = True
    print("✅ Optimized portfolio loader available")
except ImportError:
    OPTIMIZED_LOADER_AVAILABLE = False
    print("⚠️ Optimized portfolio loader not available - using legacy methods")

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
        
        # Check if registration is in progress
        if self.session_state.get('registration_in_progress', False):
            self.handle_registration_with_files()
            return
        
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
                # Validate inputs
                if not new_username or not new_password:
                    st.error("❌ Please fill in all fields")
                elif new_password != confirm_password:
                    st.error("❌ Passwords do not match")
                elif len(new_password) < 6:
                    st.error("❌ Password must be at least 6 characters")
                elif not uploaded_files:
                    st.error("❌ Please upload at least one CSV file")
                else:
                    # Start registration flow with files
                    self.session_state.registration_in_progress = True
                    self.session_state.registration_username = new_username
                    self.session_state.registration_password = new_password
                    self.session_state.pending_files = uploaded_files
                    st.rerun()
    
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
                
                # Update PMS/AIF values from factsheets (background task)
                self.update_pms_aif_values_background(user['id'])
                
                return True
            return False
            
        except Exception as e:
            st.error(f"Authentication error: {e}")
            return False
    
    def update_pms_aif_values_background(self, user_id):
        """
        Update PMS/AIF values using AI (Gemini/ChatGPT) during login
        Runs in background to not block login process
        """
        try:
            import threading
            from database_config_supabase import get_transactions_supabase, update_stock_data_supabase, save_stock_price_supabase
            from pms_aif_fetcher import is_pms_code, is_aif_code
            from ai_price_fetcher import get_pms_aif_performance_with_ai
            from datetime import datetime
            
            def fetch_and_update():
                """Background thread to fetch PMS/AIF values"""
                try:
                    # Get user's transactions
                    transactions = get_transactions_supabase(user_id=user_id)
                    if not transactions:
                        return
                    
                    df = pd.DataFrame(transactions)
                    
                    # Identify PMS/AIF holdings
                    pms_aif_tickers = []
                    for ticker in df['ticker'].unique():
                        ticker_str = str(ticker).strip()
                        if is_pms_code(ticker_str) or is_aif_code(ticker_str):
                            pms_aif_tickers.append(ticker_str)
                    
                    if not pms_aif_tickers:
                        return  # No PMS/AIF holdings
                    
                    print(f"🔄 Background: Updating {len(pms_aif_tickers)} PMS/AIF value(s) using AI...")
                    print(f"💡 Using Gemini/ChatGPT to fetch latest performance data...")
                    
                    for ticker in pms_aif_tickers:
                        try:
                            # Get investment details first
                            ticker_trans = df[df['ticker'] == ticker]
                            if ticker_trans.empty:
                                continue
                            
                            first_trans = ticker_trans.iloc[0]
                            fund_name = first_trans.get('stock_name', ticker)
                            
                            # Use AI to fetch performance data
                            print(f"🤖 {ticker}: Fetching performance data using AI...")
                            returns_data = get_pms_aif_performance_with_ai(ticker, fund_name)
                            
                            if not returns_data:
                                print(f"❌ {ticker}: AI could not find performance data - will show 0% return")
                                continue
                            
                            print(f"✅ {ticker}: AI found returns data: {returns_data}")
                            
                            # Calculate investment details
                            investment_date = pd.to_datetime(first_trans['date'])
                            investment_amount = float(ticker_trans['quantity'].sum() * first_trans['price'])
                            
                            # Calculate current value using CAGR
                            years_elapsed = (datetime.now() - investment_date).days / 365.25
                            current_value = investment_amount
                            
                            print(f"📊 {ticker}: Investment ₹{investment_amount:,.0f}, Years: {years_elapsed:.2f}")
                            
                            if years_elapsed >= 5 and '5y_cagr' in returns_data:
                                cagr = returns_data['5y_cagr'] / 100
                                current_value = investment_amount * ((1 + cagr) ** years_elapsed)
                                print(f"   Using 5Y CAGR: {returns_data['5y_cagr']}% → Current: ₹{current_value:,.0f}")
                            elif years_elapsed >= 3 and '3y_cagr' in returns_data:
                                cagr = returns_data['3y_cagr'] / 100
                                current_value = investment_amount * ((1 + cagr) ** years_elapsed)
                                print(f"   Using 3Y CAGR: {returns_data['3y_cagr']}% → Current: ₹{current_value:,.0f}")
                            elif years_elapsed >= 1 and '1y_return' in returns_data:
                                annual_return = returns_data['1y_return'] / 100
                                current_value = investment_amount * ((1 + annual_return) ** years_elapsed)
                                print(f"   Using 1Y Return: {returns_data['1y_return']}% → Current: ₹{current_value:,.0f}")
                            else:
                                print(f"⚠️ {ticker}: No applicable CAGR for {years_elapsed:.2f} years")
                            
                            # Determine sector
                            if is_aif_code(ticker):
                                sector = "Alternative Investments"
                            else:
                                sector = "PMS Equity"
                            
                            # Update database
                            stock_name = first_trans.get('stock_name', ticker)
                            update_stock_data_supabase(
                                ticker=ticker,
                                stock_name=stock_name,
                                sector=sector,
                                current_price=current_value
                            )
                            
                            # Save as historical price
                            today = datetime.now().strftime('%Y-%m-%d')
                            save_stock_price_supabase(ticker, today, current_value)
                            
                            print(f"✅ Updated {ticker}: ₹{current_value:,.0f}")
                            
                        except Exception as e:
                            print(f"⚠️ Error updating {ticker}: {e}")
                            continue
                    
                    print(f"✅ Background: PMS/AIF values updated")
                    
                except Exception as e:
                    print(f"❌ Background PMS/AIF update error: {e}")
            
            # Start background thread
            thread = threading.Thread(target=fetch_and_update, daemon=True)
            thread.start()
            
        except Exception as e:
            print(f"⚠️ Could not start PMS/AIF update: {e}")
    
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
    
    def process_csv_file(self, uploaded_file, user_id, skip_weekly_cache=False, skip_live_prices=False):
        """
        Process a single CSV file and store transactions with historical prices
        
        Args:
            uploaded_file: The CSV file to process
            user_id: User ID
            skip_weekly_cache: If True, skip weekly cache population (useful during registration)
            skip_live_prices: If True, skip live price fetch (useful during registration - fetch at login instead)
        """
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
                'sector': 'sector',
                'Invested Amount': 'invested_amount',
                'Invested_Amount': 'invested_amount',
                'invested_amount': 'invested_amount',
                'Amount': 'invested_amount',
                'amount': 'invested_amount'
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
            # Store original date column before conversion for error reporting
            original_dates = df['date'].copy() if 'date' in df.columns else None
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            
            # Handle invalid dates with average date from valid dates
            invalid_date_mask = df['date'].isna()
            invalid_dates_count = invalid_date_mask.sum()
            
            if invalid_dates_count > 0:
                from datetime import datetime
                
                # Get valid dates to calculate average
                valid_dates = df[~invalid_date_mask]['date']
                
                if len(valid_dates) > 0:
                    # Calculate average date from valid dates
                    avg_timestamp = valid_dates.astype('int64').mean()
                    avg_date = pd.Timestamp(avg_timestamp)
                    df.loc[invalid_date_mask, 'date'] = avg_date
                    
                    # Show warning with invalid dates
                    st.warning(f"⚠️ {invalid_dates_count} rows had invalid dates - using average date ({avg_date.strftime('%Y-%m-%d')}) as fallback")
                else:
                    # No valid dates available, use current date
                    df['date'] = df['date'].fillna(pd.Timestamp(datetime.now().date()))
                    st.warning(f"⚠️ {invalid_dates_count} rows had invalid dates - using current date as fallback (no valid dates in file)")
                
                # Print the invalid dates for debugging
                if original_dates is not None:
                    invalid_date_values = original_dates[invalid_date_mask].unique()
                    with st.expander(f"🔍 Show {invalid_dates_count} Invalid Date(s)"):
                        st.write("**Invalid date values found:**")
                        for idx, invalid_val in enumerate(invalid_date_values[:20], 1):  # Limit to first 20
                            st.write(f"{idx}. `{invalid_val}`")
                        if len(invalid_date_values) > 20:
                            st.write(f"... and {len(invalid_date_values) - 20} more")
            
            # ✅ FIX FUTURE DATES: Auto-correct dates that are in the future using average date
            from datetime import datetime, timedelta
            today = pd.Timestamp(datetime.now().date())
            future_date_mask = df['date'] > today
            future_dates_count = future_date_mask.sum()
            
            if future_dates_count > 0:
                # Store original future dates for reporting
                original_future_dates = df.loc[future_date_mask, 'date'].copy()
                
                # Get valid (non-future) dates to calculate average
                valid_past_dates = df[~future_date_mask]['date']
                
                if len(valid_past_dates) > 0:
                    # Calculate average date from valid past dates
                    avg_timestamp = valid_past_dates.astype('int64').mean()
                    avg_date = pd.Timestamp(avg_timestamp)
                    
                    # Replace future dates with average date
                    df.loc[future_date_mask, 'date'] = avg_date
                    
                    st.warning(f"🔧 Auto-corrected {future_dates_count} FUTURE dates using average date from file ({avg_date.strftime('%Y-%m-%d')})")
                else:
                    # No valid past dates, subtract 1 year as fallback
                    df.loc[future_date_mask, 'date'] = df.loc[future_date_mask, 'date'] - pd.DateOffset(years=1)
                    st.warning(f"🔧 Auto-corrected {future_dates_count} FUTURE dates by subtracting 1 year (no valid past dates in file)")
                
                with st.expander(f"🔍 Show {future_dates_count} Auto-Corrected Date(s)"):
                    st.write("**Future dates detected and corrected:**")
                    correction_df = pd.DataFrame({
                        'Original (Future) Date': original_future_dates.dt.strftime('%Y-%m-%d'),
                        'Corrected Date': df.loc[future_date_mask, 'date'].dt.strftime('%Y-%m-%d')
                    })
                    st.dataframe(correction_df.head(20))
                    if len(correction_df) > 20:
                        st.write(f"... and {len(correction_df) - 20} more corrections")
            
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
            
            # For rows with unrecognized transaction types, default to 'buy' (to avoid dropping rows)
            invalid_types = ~df['transaction_type'].isin(['buy', 'sell'])
            invalid_count = invalid_types.sum()
            if invalid_count > 0:
                df.loc[invalid_types, 'transaction_type'] = 'buy'
                st.warning(f"⚠️ {invalid_count} rows had invalid transaction types - defaulting to 'buy'")
            
            st.info(f"💼 Transaction types standardized: {len(df)} valid transactions")
            
            if df.empty:
                st.warning(f"⚠️ No valid transactions found in {uploaded_file.name}")
                return False
            
            # Add user_id to the dataframe
            df['user_id'] = user_id
            
            # ✅ ALWAYS fetch prices (ignore CSV price column)
            st.info(f"🔍 Fetching prices for ALL transactions in {uploaded_file.name}...")
            df = self.fetch_historical_prices_for_transactions(df)
            
            # Save transactions to database
            st.info(f"💾 Saving {len(df)} transactions to database...")
            success = self.save_transactions_to_database(
                df, 
                user_id, 
                uploaded_file.name,
                skip_weekly_cache=skip_weekly_cache,
                skip_live_prices=skip_live_prices
            )
            
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
        """
        ✅ ENHANCED: Fetch historical prices for transactions with AI fallback
        - Tries API first (yfinance/mftool) - FREE
        - Falls back to AI if API fails
        - Updates DataFrame AND stores in transactions table
        """
        try:
            # Count transactions that need historical prices
            transactions_needing_prices = 0
            for idx, row in df.iterrows():
                if 'price' not in df.columns or pd.isna(df.at[idx, 'price']) or df.at[idx, 'price'] == 0:
                    transactions_needing_prices += 1
            
            if transactions_needing_prices == 0:
                st.info("✅ All transactions already have prices")
                return df
            
            st.info(f"🔍 Found {transactions_needing_prices} transactions with missing prices - fetching now...")
            
            # Create progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            status_text.text(f"🔍 Fetching historical prices for {transactions_needing_prices} transactions...")
            
            processed_count = 0
            api_success = 0
            ai_success = 0
            failed_count = 0
            
            # Initialize AI fetcher
            try:
                from ai_price_fetcher import AIPriceFetcher
                ai_fetcher = AIPriceFetcher()
                ai_available = ai_fetcher.is_available()
            except Exception as e:
                print(f"⚠️ AI fetcher not available: {e}")
                ai_available = False
            
            for idx, row in df.iterrows():
                ticker = row['ticker']
                transaction_date = row['date']
                date_str = transaction_date.strftime('%Y-%m-%d')
                
                # Skip if already has price
                if 'price' in df.columns and pd.notna(df.at[idx, 'price']) and df.at[idx, 'price'] > 0:
                    continue
                
                # Get stock/fund name if available
                stock_name = row.get('stock_name', ticker)
                
                # Detect asset type
                ticker_str = str(ticker).strip()
                is_bse_code = (ticker_str.isdigit() and len(ticker_str) == 6 and ticker_str.startswith('5'))
                is_mutual_fund = (
                    (ticker_str.isdigit() and len(ticker_str) >= 5 and len(ticker_str) <= 6 and not is_bse_code) or
                    ticker_str.startswith('MF_')
                )
                is_pms_aif = ticker_str.startswith('INP') or ticker_str.startswith('INA') or 'PMS' in ticker_str.upper() or 'AIF' in ticker_str.upper()
                
                historical_price = None
                fetch_method = None
                
                # ✅ STEP 1: Try API first (FREE)
                if is_mutual_fund:
                    # Mutual fund - try mftool API
                    try:
                        historical_price = get_mutual_fund_price(
                            ticker, 
                            stock_name, 
                            row['user_id'], 
                            date_str
                        )
                        if historical_price and historical_price > 0:
                            fetch_method = 'mftool_api'
                            api_success += 1
                    except Exception as e:
                        print(f"⚠️ mftool failed for {ticker}: {e}")
                
                elif is_pms_aif:
                    # ✅ PMS/AIF: Use invested amount and calculate using CAGR
                    print(f"📊 {ticker}: PMS/AIF detected, calculating from invested amount")
                    
                    # Get invested amount from CSV
                    invested_amount = row.get('invested_amount', 0) or row.get('amount', 0)
                    if not invested_amount or invested_amount <= 0:
                        # Fallback: price * quantity
                        csv_price = row.get('price', 0)
                        quantity = row.get('quantity', 1)
                        if csv_price and csv_price > 0:
                            invested_amount = csv_price * quantity
                    
                    quantity = row.get('quantity', 1)
                    if quantity <= 0:
                        quantity = 1
                    
                    # Calculate per-unit price from invested amount
                    transaction_price = invested_amount / quantity
                    
                    # Try to get CURRENT NAV from AI
                    try:
                        if ai_available:
                            print(f"🤖 Fetching current NAV for {ticker} to calculate CAGR")
                            current_nav_result = ai_fetcher.get_pms_aif_nav(ticker, stock_name)  # No date = current
                            
                            if current_nav_result and isinstance(current_nav_result, dict) and current_nav_result.get('price', 0) > 0:
                                current_nav = current_nav_result['price']
                                
                                # Calculate CAGR from transaction date to today
                                from datetime import datetime
                                today = datetime.now()
                                days_elapsed = (today - transaction_date).days
                                years_elapsed = days_elapsed / 365.25
                                
                                if years_elapsed > 0.01:  # At least a few days
                                    # CAGR formula: ((Current/Initial)^(1/years)) - 1
                                    cagr = ((current_nav / transaction_price) ** (1 / years_elapsed)) - 1
                                    print(f"✅ PMS/AIF CAGR: {cagr*100:.2f}% per year for {ticker}")
                                    
                                    # Use transaction price (this will be stored in DB)
                                    historical_price = transaction_price
                                    fetch_method = 'pms_aif_amount'
                                    ai_success += 1
                                    
                                    # Store CAGR for future calculations (we'll add this to the row)
                                    df.at[idx, 'cagr'] = cagr
                                    df.at[idx, 'current_nav'] = current_nav
                                else:
                                    # Recent transaction, use current NAV
                                    historical_price = current_nav
                                    fetch_method = 'pms_aif_current'
                                    ai_success += 1
                            else:
                                # AI failed, use transaction price as-is
                                historical_price = transaction_price
                                fetch_method = 'pms_aif_amount_only'
                                print(f"⚠️ Could not fetch current NAV for {ticker}, using transaction price")
                        else:
                            # AI not available, use transaction price
                            historical_price = transaction_price
                            fetch_method = 'pms_aif_amount_only'
                            print(f"⚠️ AI not available for {ticker}, using transaction price")
                    except Exception as e:
                        print(f"⚠️ Error calculating PMS/AIF price for {ticker}: {e}")
                        historical_price = transaction_price
                        fetch_method = 'pms_aif_amount_only'
                
                else:
                    # Stock - try yfinance API
                    try:
                        # Validate ticker format first
                        if '/' in ticker_str or 'E+' in ticker_str.upper():
                            st.warning(f"⚠️ Invalid ticker format: {ticker_str}")
                            df.at[idx, 'price'] = 0.0
                            failed_count += 1
                            continue
                        
                        historical_price = get_stock_price(
                            ticker, 
                            stock_name, 
                            date_str
                        )
                        if historical_price and historical_price > 0:
                            fetch_method = 'yfinance_api'
                            api_success += 1
                    except Exception as e:
                        print(f"⚠️ yfinance failed for {ticker}: {e}")
                
                # ✅ STEP 2: If API failed, try AI
                if not historical_price or historical_price <= 0:
                    if ai_available:
                        try:
                            print(f"🤖 AI fallback for {ticker} ({stock_name}) on {date_str}")
                            
                            if is_mutual_fund:
                                result = ai_fetcher.get_mutual_fund_nav(ticker, stock_name, date_str)
                            elif is_pms_aif:
                                result = ai_fetcher.get_pms_aif_nav(ticker, stock_name, date_str)
                            else:
                                result = ai_fetcher.get_stock_price(ticker, stock_name, date_str)
                            
                            if result and isinstance(result, dict) and result.get('price', 0) > 0:
                                historical_price = result['price']
                                fetch_method = 'ai_fallback'
                                ai_success += 1
                                print(f"✅ AI found price: ₹{historical_price} for {ticker}")
                        except Exception as ai_error:
                            print(f"⚠️ AI also failed for {ticker}: {ai_error}")
                
                # ✅ STEP 3: Update DataFrame with fetched price
                if historical_price and historical_price > 0:
                    df.at[idx, 'price'] = historical_price
                    print(f"✅ [{fetch_method}] {ticker}: ₹{historical_price} on {date_str}")
                else:
                    # If all methods failed, set to 0 (will be filtered by validation)
                    df.at[idx, 'price'] = 0.0
                    failed_count += 1
                    st.warning(f"⚠️ Could not fetch price for {ticker} ({stock_name}) on {date_str}")
                
                processed_count += 1
                progress = processed_count / transactions_needing_prices
                progress_bar.progress(progress)
                status_text.text(f"🔍 Processing {processed_count}/{transactions_needing_prices}: {ticker}")
            
            # Complete progress bar
            progress_bar.progress(1.0)
            
            # Summary
            summary_msg = f"✅ Price fetch complete: {api_success} via API (FREE), {ai_success} via AI, {failed_count} failed"
            status_text.text(summary_msg)
            st.success(summary_msg)
            
            # Clear progress elements after a short delay
            import time
            time.sleep(2)
            progress_bar.empty()
            status_text.empty()
            
            return df
                    
        except Exception as e:
            st.error(f"Error fetching historical prices: {e}")
            import traceback
            st.error(f"Traceback: {traceback.format_exc()}")
            return df
    
    def bulk_fetch_and_cache_all_prices(self, user_id, show_ui=True):
        """
        🆕 BATCH FETCH: Get ALL prices (historical, weekly, live) in ONE AI call
        Then cache everything to database so no repeated fetching needed
        
        Args:
            user_id: User ID to fetch prices for
            show_ui: If True, show UI messages. If False, run silently (for auto-fetch)
        """
        # ✅ LOCK: Prevent concurrent bulk fetches for same user
        lock_key = f"bulk_fetch_lock_{user_id}"
        
        if lock_key in st.session_state and st.session_state[lock_key]:
            print(f"⚠️ Bulk fetch already running for user {user_id}, skipping duplicate call...")
            if show_ui:
                st.info("⏳ Bulk fetch is already in progress, please wait...")
            return
        
        # Set lock
        st.session_state[lock_key] = True
        print(f"🔒 Acquired bulk fetch lock for user {user_id}")
        
        try:
            from datetime import datetime, timedelta
            
            if show_ui:
                st.info("🤖 Using AI to fetch ALL prices in batch (historical + weekly + live)...")
            
            # Get all transactions to find tickers and dates
            from database_config_supabase import get_transactions_supabase, save_stock_price_supabase, get_stock_price_supabase
            transactions = get_transactions_supabase(user_id=user_id)
            
            if not transactions:
                if show_ui:
                    st.warning("No transactions found")
                return
            
            df = pd.DataFrame(transactions)
            
            # Collect all unique tickers with names
            tickers_with_names = {}
            for _, row in df.iterrows():
                ticker = row['ticker']
                name = row.get('stock_name', ticker)
                if ticker not in tickers_with_names:
                    tickers_with_names[ticker] = name
            
            # ✅ STEP 1: Check cache first to find what's MISSING
            dates_needed = {}  # {ticker: [dates]}
            
            # Transaction dates (historical)
            df['date'] = pd.to_datetime(df['date'])
            for ticker in tickers_with_names.keys():
                ticker_dates = df[df['ticker'] == ticker]['date'].unique()
                missing_dates = []
                for date in ticker_dates:
                    date_str = date.strftime('%Y-%m-%d')
                    # Check if price exists in cache
                    cached = get_stock_price_supabase(ticker, date_str)
                    if not cached:
                        missing_dates.append(date_str)
                if missing_dates:
                    dates_needed[ticker] = missing_dates
            
            # Weekly dates (only check for tickers that have holdings, limit to last 12 weeks to save costs)
            today = datetime.now()
            for ticker in tickers_with_names.keys():
                for i in range(12):  # Reduced from 26 to 12 weeks
                    week_date = today - timedelta(weeks=i)
                    week_monday = week_date - timedelta(days=week_date.weekday())
                    date_str = week_monday.strftime('%Y-%m-%d')
                    cached = get_stock_price_supabase(ticker, date_str)
                    if not cached:
                        if ticker not in dates_needed:
                            dates_needed[ticker] = []
                        if date_str not in dates_needed[ticker]:
                            dates_needed[ticker].append(date_str)
            
            # Latest price (always fetch)
            for ticker in tickers_with_names.keys():
                if ticker not in dates_needed:
                    dates_needed[ticker] = []
                dates_needed[ticker].append('LATEST')
            
            # Count missing prices
            total_missing = sum(len(dates) for dates in dates_needed.values())
            
            if total_missing == 0:
                if show_ui:
                    st.success(f"✅ All prices already cached! No fetching needed.")
                print("✅ All prices in cache, skipping fetch")
                return
            
            if show_ui:
                st.info(f"📊 Need to fetch {total_missing} missing prices")
                st.caption(f"Cache hit rate: {((len(tickers_with_names) * 13) - total_missing) / (len(tickers_with_names) * 13) * 100:.1f}%")
            
            # ✅ STEP 2: Use AI (Gemini FREE) with WEEKLY RANGE queries
            print(f"📊 Fetching {total_missing} prices using AI weekly range queries (Gemini FREE)...")
            
            from ai_price_fetcher import AIPriceFetcher
            ai_fetcher = AIPriceFetcher()
            
            if not ai_fetcher.is_available():
                if show_ui:
                    st.error("❌ AI not available. Configure Gemini or OpenAI API key.")
                print("❌ No AI available")
                return
            
            # ✅ INCREMENTAL FETCH & SAVE: Fetch one ticker, save immediately, repeat
            print(f"🤖 Incremental AI fetch: Fetching and saving prices one ticker at a time...")
            all_tickers = list(dates_needed.keys())
            
            saved_count = 0
            skipped_count = 0
            total_tickers_processed = 0
            tickers_already_cached = 0
            
            for idx, ticker in enumerate(all_tickers):
                name = tickers_with_names[ticker]
                
                if show_ui:
                    progress = (idx + 1) / len(all_tickers)
                    st.progress(progress, text=f"🤖 [{idx + 1}/{len(all_tickers)}] Fetching & Saving: {name}")
                
                # ✅ RESUMPTION LOGIC: Check if this ticker already has sufficient data in DB
                # This allows resuming from interruptions without re-fetching already processed tickers
                try:
                    # Check if we have recent data for this ticker (within last week)
                    recent_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
                    recent_cached = get_stock_price_supabase(ticker, recent_date)
                    
                    # Also check if we have live/latest data
                    latest_date = datetime.now().strftime('%Y-%m-%d')
                    latest_cached = get_stock_price_supabase(ticker, latest_date)
                    
                    if recent_cached and recent_cached > 0 and latest_cached and latest_cached > 0:
                        # This ticker already has recent data, skip it (likely processed in previous session)
                        print(f"✅ [{idx + 1}/{len(all_tickers)}] {ticker}: Already cached (recent & latest data found), skipping")
                        tickers_already_cached += 1
                        total_tickers_processed += 1
                        continue
                except Exception as check_error:
                    # If check fails, proceed with fetch to be safe
                    pass
                
                # Calculate date range: if historical is older than 1 year, use historical date; else use 1 year ago
                ticker_transactions = df[df['ticker'] == ticker]['date']
                if not ticker_transactions.empty:
                    oldest_date = ticker_transactions.min()
                    one_year_ago = datetime.now() - timedelta(days=365)
                    
                    # If historical is older than 1 year, use historical date; else use 1 year ago
                    if oldest_date < one_year_ago:
                        start_date = oldest_date.strftime('%Y-%m-%d')
                        print(f"   📅 Using historical date: {start_date} (older than 1 year)")
                    else:
                        start_date = one_year_ago.strftime('%Y-%m-%d')
                        print(f"   📅 Using 1-year lookback: {start_date}")
                else:
                    # Default to 1 year if no transactions
                    start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
                    print(f"   📅 No transactions, using 1-year lookback: {start_date}")
                
                end_date = 'TODAY'
                
                # Detect asset type
                is_pms_aif = (
                    ticker.startswith('INP') or ticker.startswith('INA') or
                    'PMS' in ticker.upper() or 'AIF' in ticker.upper()
                )
                is_mutual_fund = str(ticker).isdigit() or ticker.startswith('MF_')
                
                try:
                    weekly_prices = {}
                    
                    # ✅ HYBRID STRATEGY: FREE API FIRST → AI FALLBACK
                    if is_pms_aif:
                        # PMS/AIF: No free API available, AI ONLY
                        print(f"🤖 AI [{idx + 1}/{len(all_tickers)}] {ticker} (PMS/AIF): {start_date} to {end_date}")
                        weekly_prices = ai_fetcher.get_weekly_prices_in_range(
                            ticker=ticker,
                            name=name,
                            start_date=start_date,
                            end_date=end_date,
                            asset_type='PMS/AIF'
                        )
                    
                    elif is_mutual_fund:
                        # Mutual Fund: Try FREE mftool API first, AI fallback
                        print(f"📊 API [{idx + 1}/{len(all_tickers)}] {ticker} (MF): Trying mftool (FREE)...")
                        
                        try:
                            # Try yfinance for weekly data (some MFs available)
                            import yfinance as yf
                            yf_ticker = f"{ticker}.NS"
                            stock = yf.Ticker(yf_ticker)
                            
                            from datetime import datetime
                            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                            end_dt = datetime.now()
                            
                            hist = stock.history(start=start_dt, end=end_dt, interval='1wk')
                            
                            if not hist.empty and len(hist) > 0:
                                weekly_prices = {}
                                for date_idx, price in zip(hist.index, hist['Close']):
                                    date_str = date_idx.strftime('%Y-%m-%d')
                                    weekly_prices[date_str] = {'price': float(price), 'sector': 'Mutual Fund'}
                                print(f"✅ yfinance (FREE): Got {len(weekly_prices)} prices for {ticker}")
                            else:
                                raise Exception("No data from yfinance")
                                
                        except Exception as api_error:
                            print(f"⚠️ FREE API failed: {api_error}, trying AI...")
                            # Fallback to AI
                            weekly_prices = ai_fetcher.get_weekly_prices_in_range(
                                ticker=ticker,
                                name=name,
                                start_date=start_date,
                                end_date=end_date,
                                asset_type='Mutual Fund'
                            )
                    
                    else:
                        # Stock/ETF/Bond: Try FREE yfinance API first, AI fallback
                        print(f"📊 API [{idx + 1}/{len(all_tickers)}] {ticker} (Stock): Trying yfinance (FREE)...")
                        
                        try:
                            import yfinance as yf
                            
                            # Add NSE/BSE suffix
                            yf_ticker = f"{ticker}.NS" if not ticker.endswith(('.NS', '.BO')) else ticker
                            stock = yf.Ticker(yf_ticker)
                            
                            from datetime import datetime
                            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                            end_dt = datetime.now()
                            
                            hist = stock.history(start=start_dt, end=end_dt, interval='1wk')
                            
                            if not hist.empty and len(hist) > 0:
                                weekly_prices = {}
                                sector_info = stock.info.get('sector', 'Other Stocks')
                                
                                for date_idx, price in zip(hist.index, hist['Close']):
                                    date_str = date_idx.strftime('%Y-%m-%d')
                                    weekly_prices[date_str] = {'price': float(price), 'sector': sector_info}
                                print(f"✅ yfinance (FREE): Got {len(weekly_prices)} prices for {ticker}")
                            else:
                                raise Exception("No data from yfinance")
                                
                        except Exception as api_error:
                            print(f"⚠️ yfinance failed: {api_error}")
                            
                            # Try BSE if NSE failed
                            if '.NS' in yf_ticker:
                                try:
                                    print(f"   🔄 Trying BSE (.BO) for {ticker}...")
                                    yf_ticker = f"{ticker}.BO"
                                    stock = yf.Ticker(yf_ticker)
                                    hist = stock.history(start=start_dt, end=end_dt, interval='1wk')
                                    
                                    if not hist.empty and len(hist) > 0:
                                        weekly_prices = {}
                                        sector_info = stock.info.get('sector', 'Other Stocks')
                                        
                                        for date_idx, price in zip(hist.index, hist['Close']):
                                            date_str = date_idx.strftime('%Y-%m-%d')
                                            weekly_prices[date_str] = {'price': float(price), 'sector': sector_info}
                                        print(f"✅ yfinance BSE (FREE): Got {len(weekly_prices)} prices for {ticker}")
                                    else:
                                        raise Exception("No data from BSE either")
                                except Exception as bse_error:
                                    print(f"⚠️ BSE also failed: {bse_error}, trying AI...")
                                    # Fallback to AI
                                    weekly_prices = ai_fetcher.get_weekly_prices_in_range(
                                        ticker=ticker,
                                        name=name,
                                        start_date=start_date,
                                        end_date=end_date,
                                        asset_type='Stock'
                                    )
                            else:
                                # Direct to AI fallback
                                print(f"   🤖 Falling back to AI for {ticker}...")
                                weekly_prices = ai_fetcher.get_weekly_prices_in_range(
                                    ticker=ticker,
                                    name=name,
                                    start_date=start_date,
                                    end_date=end_date,
                                    asset_type='Stock'
                                )
                    
                    # ✅ IMMEDIATELY SAVE THIS TICKER'S PRICES TO DATABASE
                    if weekly_prices:
                        print(f"✅ [{idx + 1}/{len(all_tickers)}] {ticker}: {len(weekly_prices)} prices fetched")
                        print(f"   💾 Saving {len(weekly_prices)} prices to database...")
                        
                        ticker_saved = 0
                        ticker_skipped = 0
                        
                        for date, price_data in weekly_prices.items():
                            try:
                                # Handle dict format: {'price': float, 'sector': str}
                                if isinstance(price_data, dict):
                                    price = price_data.get('price')
                                    sector = price_data.get('sector', 'Unknown')
                                else:
                                    # Fallback for old format (just float)
                                    price = price_data
                                    sector = 'Unknown'
                                
                                # Convert LATEST to today's date for storage
                                if date == 'LATEST':
                                    date_str = datetime.now().strftime('%Y-%m-%d')
                                else:
                                    date_str = date
                                
                                # ✅ VALIDATE: Skip NaN, inf, and invalid prices
                                import math
                                if not isinstance(price, (int, float)) or math.isnan(price) or math.isinf(price) or price <= 0:
                                    print(f"   ⚠️ Skipping invalid price for {ticker} on {date}: {price}")
                                    ticker_skipped += 1
                                    continue
                                
                                # Save to cache immediately
                                save_stock_price_supabase(ticker, date_str, price, 'ai_bulk_fetch')
                                ticker_saved += 1
                                
                            except Exception as save_error:
                                print(f"   ⚠️ Failed to save {ticker} on {date}: {save_error}")
                                ticker_skipped += 1
                        
                        saved_count += ticker_saved
                        skipped_count += ticker_skipped
                        total_tickers_processed += 1
                        
                        print(f"   ✅ Saved {ticker_saved} prices for {ticker} (skipped {ticker_skipped})")
                        print(f"   📊 Progress: {total_tickers_processed}/{len(all_tickers)} tickers, {saved_count} total prices saved")
                        
                    else:
                        print(f"⚠️ [{idx + 1}/{len(all_tickers)}] {ticker}: No data returned, skipping")
                    
                except Exception as e:
                    print(f"⚠️ [{idx + 1}/{len(all_tickers)}] {ticker}: Fetch failed - {e}")
                    # Continue with next ticker even if one fails
            
            # ✅ INCREMENTAL FETCH COMPLETE - Show summary
            print(f"✅ Incremental fetch complete: {total_tickers_processed} tickers processed")
            print(f"   ✅ Already cached: {tickers_already_cached} tickers (skipped)")
            print(f"   💾 Total saved: {saved_count} prices")
            print(f"   ⚠️ Total skipped: {skipped_count} prices")
            
            if total_tickers_processed == 0:
                if show_ui:
                    st.warning("⚠️ No tickers were successfully processed")
                print("⚠️ Fetch failed: No tickers processed")
                return
            
            if show_ui:
                # Success message
                st.success(f"✅ Incremental fetch & save complete!")
                st.info(f"📊 Summary:")
                st.caption(f"   • Total tickers: {len(all_tickers)}")
                st.caption(f"   • Already cached (resumed): {tickers_already_cached}")
                st.caption(f"   • Newly fetched: {total_tickers_processed - tickers_already_cached}")
                st.caption(f"   • Prices saved to DB: {saved_count}")
                st.caption(f"   • Prices skipped (invalid): {skipped_count}")
                if (total_tickers_processed - tickers_already_cached) > 0:
                    st.caption(f"   • Avg prices per new ticker: {saved_count / (total_tickers_processed - tickers_already_cached):.1f}")
                st.success("💾 All prices cached! Future fetches will be instant from database.")
                
                if tickers_already_cached > 0:
                    st.info(f"🔄 Resumed from previous session: {tickers_already_cached} tickers were already processed and skipped.")
            else:
                print(f"✅ Incremental fetch complete: {saved_count} saved, {skipped_count} skipped, {tickers_already_cached} already cached")
            
            # ✅ Mark bulk fetch as complete for this session
            st.session_state[f"bulk_fetch_done_{user_id}"] = True
            print(f"✅ Set bulk fetch flag for user {user_id}")
            
        except Exception as e:
            if show_ui:
                st.error(f"❌ Batch fetch failed: {e}")
                import traceback
                st.error(traceback.format_exc())
            else:
                print(f"❌ Silent batch fetch failed: {e}")
                import traceback
                print(traceback.format_exc())
        
        finally:
            # ✅ ALWAYS release lock, even if error occurred
            st.session_state[lock_key] = False
            print(f"🔓 Released bulk fetch lock for user {user_id}")
    
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
            
            # Check if it's a mutual fund scheme code first (priority over stock detection)
            # Mutual fund scheme codes are typically 5-6 digits (not traded on NSE/BSE)
            # Valid MF scheme codes are usually 5-6 digits starting with 1-2
            # Exclude BSE codes (6 digits starting with 5, e.g., 500414)
            is_bse_code = (clean_ticker.isdigit() and len(clean_ticker) == 6 and clean_ticker.startswith('5'))
            is_mutual_fund = (
                (clean_ticker.isdigit() and len(clean_ticker) >= 5 and len(clean_ticker) <= 6 and not is_bse_code) or
                clean_ticker.startswith('MF_')
            )

            # Check if it's a stock ticker (NSE/BSE symbols)
            is_stock_ticker = (
                not is_mutual_fund and
                (len(clean_ticker) <= 10) and  # Reasonable stock ticker length
                (clean_ticker.isalpha() or (clean_ticker.isalnum() and not clean_ticker.isdigit()))
            )

            if is_mutual_fund:
                print(f"🔍 {ticker}: Detected as mutual fund scheme code - will use MF APIs only")
            elif is_stock_ticker:
                print(f"🔍 {ticker}: Detected as stock ticker - will try NSE/BSE")
            else:
                print(f"🔍 {ticker}: Unknown ticker type - will try all sources")
            
            # === EARLY CHECK: Is this a PMS/AIF? ===
            # Check for SEBI registration codes and common PMS/AIF patterns
            from pms_aif_fetcher import is_pms_code, is_aif_code
            ticker_str = str(ticker).strip()
            ticker_upper = ticker_str.upper()
            
            is_pms_aif = (
                is_pms_code(ticker_str) or  # Detects INP... codes
                is_aif_code(ticker_str) or  # Detects AIF_IN_... codes
                'PMS' in ticker_upper or 
                'AIF' in ticker_upper or
                any(keyword in ticker_upper for keyword in [
                    'BUOYANT', 'CARNELIAN', 'JULIUS', 'VALENTIS', 
                    'UNIFI', 'NUVAMA', 'PORTFOLIO MANAGEMENT'
                ])
            )
            
            if is_pms_aif:
                # ✅ For PMS/AIF, calculate NAV using CAGR if available
                print(f"🔍 {ticker}: Detected as PMS/AIF - calculating NAV using CAGR")
                
                # Get transaction data from database
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
                        transaction_price = float(latest_txn['price'])
                        transaction_date = pd.to_datetime(latest_txn['date'])
                        
                        # Check if we have CAGR data stored
                        cagr = latest_txn.get('cagr', None)
                        
                        if cagr and pd.notna(cagr):
                            # ✅ Calculate NAV using CAGR
                            from datetime import datetime
                            days_diff = (target_date - transaction_date).days
                            years_diff = days_diff / 365.25
                            
                            # NAV at target date = Transaction NAV × (1 + CAGR)^years
                            calculated_nav = transaction_price * ((1 + float(cagr)) ** years_diff)
                            price = calculated_nav
                            price_source = 'pms_cagr_calculated'
                            print(f"✅ {ticker}: Calculated NAV using CAGR ({float(cagr)*100:.2f}%) = ₹{price:.2f}")
                        else:
                            # No CAGR, use transaction price
                            price = transaction_price
                            price_source = 'pms_transaction_price'
                            print(f"✅ {ticker}: Using transaction price (no CAGR) - ₹{price}")
                        
                        # Save to cache
                        try:
                            save_stock_price_supabase(ticker, target_date_str, price, price_source)
                        except Exception as e:
                            print(f"Failed to save PMS price to cache: {e}")
                        
                        return price
                
                # If no transaction found, return None (will skip caching)
                print(f"⚠️ {ticker}: PMS/AIF but no transaction found for {target_date_str}")
                return None
            
            # === STRATEGY 1: Try yfinance (only for stock tickers, not MF scheme codes) ===
            if not price and is_stock_ticker:
                try:
                    import yfinance as yf
                    # Try NSE first for most Indian stocks
                    stock = yf.Ticker(f"{clean_ticker}.NS")
                    hist_data = stock.history(start=target_date, end=target_date + timedelta(days=1))
                    if not hist_data.empty:
                        price = float(hist_data['Close'].iloc[0])
                        price_source = 'yfinance_nse'
                        print(f"✅ {ticker}: yfinance NSE - ₹{price}")
                    else:
                        # Try BSE as fallback
                        stock = yf.Ticker(f"{clean_ticker}.BO")
                        hist_data = stock.history(start=target_date, end=target_date + timedelta(days=1))
                        if not hist_data.empty:
                            price = float(hist_data['Close'].iloc[0])
                            price_source = 'yfinance_bse'
                            print(f"✅ {ticker}: yfinance BSE - ₹{price}")
                except Exception as e:
                    print(f"⚠️ {ticker}: yfinance failed - {e}")
            
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
                    else:
                        print(f"⚠️ MF {ticker}: mftool returned no price or zero price")
                except ImportError as ie:
                    print(f"⚠️ MF {ticker}: mftool import failed: {ie}")
                except Exception as e:
                    print(f"⚠️ MF {ticker}: mftool error: {e}")
                    # Don't pass - let other strategies try
            
            # === STRATEGY 5.5: Try AI for mutual funds (fallback when mftool fails) ===
            if not price and is_mutual_fund:  # ✅ FIXED: Works for BOTH live AND historical
                try:
                    from ai_price_fetcher import AIPriceFetcher
                    from database_config_supabase import get_transactions_supabase
                    
                    # Get fund name from transactions
                    fund_name = None
                    transactions = get_transactions_supabase(user_id=None)
                    if transactions:
                        df_trans = pd.DataFrame(transactions)
                        ticker_trans = df_trans[df_trans['ticker'] == ticker]
                        if not ticker_trans.empty:
                            fund_name = ticker_trans.iloc[0].get('stock_name', ticker)
                    
                    if fund_name:
                        print(f"🤖 MF {ticker}: Trying AI as fallback for {target_date_str}...")
                        ai_fetcher = AIPriceFetcher()
                        
                        if ai_fetcher.is_available():
                            result = ai_fetcher.get_mutual_fund_nav(ticker, fund_name, target_date_str)
                            if result and isinstance(result, dict) and result.get('price', 0) > 0:
                                price = float(result['price'])
                                price_source = 'ai_fallback'
                                print(f"✅ {ticker}: AI found NAV - ₹{price} (Date: {result.get('date', 'N/A')})")
                except Exception as e:
                    print(f"⚠️ MF {ticker}: AI fallback failed: {e}")
            
            # === STRATEGY 6: Try PMS/AIF (if ticker suggests it) ===
            if not price:
                ticker_upper = ticker.upper()
                if any(keyword in ticker_upper for keyword in ['PMS', 'AIF', 'INP', 'BUOYANT', 'CARNELIAN', 'JULIUS', 'VALENTIS', 'UNIFI']) or ticker_upper.endswith('_PMS'):
                    try:
                        from pms_aif_fetcher import get_pms_nav, get_aif_nav, is_pms_code, is_aif_code
                        print(f"🔍 {ticker}: PMS/AIF detected - using transaction price for historical data")
                        # For PMS/AIF, we use the TRANSACTION PRICE as historical price
                        # The actual NAV calculation happens at portfolio level using CAGR
                        # Don't try to fetch live prices for historical dates
                    except ImportError as ie:
                        print(f"⚠️ PMS {ticker}: pms_aif_fetcher import failed: {ie}")
                    except Exception as e:
                        print(f"⚠️ PMS {ticker}: PMS/AIF fetcher error: {e}")
                        # Don't pass - let transaction price be used
            
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
            
            # === FINAL FALLBACK: Try AI for stocks (when all else fails) ===
            if not price and is_stock_ticker:  # ✅ FIXED: Works for BOTH live AND historical
                try:
                    from ai_price_fetcher import AIPriceFetcher
                    from database_config_supabase import get_transactions_supabase
                    
                    # Get stock name from transactions
                    stock_name = None
                    transactions = get_transactions_supabase(user_id=None)
                    if transactions:
                        df_trans = pd.DataFrame(transactions)
                        ticker_trans = df_trans[df_trans['ticker'] == ticker]
                        if not ticker_trans.empty:
                            stock_name = ticker_trans.iloc[0].get('stock_name', ticker)
                    
                    if stock_name:
                        print(f"🤖 Stock {ticker}: All FREE APIs failed, trying AI as fallback for {target_date_str}...")
                        ai_fetcher = AIPriceFetcher()
                        
                        if ai_fetcher.is_available():
                            result = ai_fetcher.get_stock_price(ticker, stock_name, target_date_str)
                            if result and isinstance(result, dict) and result.get('price', 0) > 0:
                                price = float(result['price'])
                                price_source = 'ai_fallback'
                                print(f"✅ {ticker}: AI found price - ₹{price} (Date: {result.get('date', 'N/A')})")
                        else:
                            print(f"⚠️ Stock {ticker}: AI not available, no fallback possible")
                except Exception as e:
                    print(f"⚠️ Stock {ticker}: AI fallback failed: {e}")
            
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
            
            print(f"❌ {ticker}: No price found from any source (including AI) for {target_date_str}")
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
    
    def save_transactions_to_database(self, df, user_id, filename, skip_weekly_cache=False, skip_live_prices=False):
        """
        Save transactions to database
        
        Args:
            df: DataFrame with transactions
            user_id: User ID
            filename: File name
            skip_weekly_cache: If True, skip weekly cache population
            skip_live_prices: If True, skip live price fetch
        """
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
            
            # ✅ VALIDATE DATA BEFORE SAVING: Remove NaN, inf, and out-of-range values
            st.info(f"🔍 Validating {len(df)} transactions before saving...")
            
            import math
            import numpy as np
            
            # Store original count
            original_count = len(df)
            
            # 1. Replace NaN with safe defaults
            df['price'] = df['price'].replace([np.inf, -np.inf], np.nan)  # Convert inf to NaN first
            df['quantity'] = df['quantity'].replace([np.inf, -np.inf], np.nan)
            
            # 2. Drop rows with NaN in critical columns
            critical_columns = ['ticker', 'quantity', 'price', 'date']
            before_drop = len(df)
            df = df.dropna(subset=critical_columns)
            after_drop = len(df)
            
            if before_drop > after_drop:
                st.warning(f"⚠️ Removed {before_drop - after_drop} rows with missing/invalid data (NaN/inf)")
            
            # 3. Validate numeric ranges
            # Remove rows with zero or negative quantities
            df = df[df['quantity'] > 0]
            
            # Remove rows with zero or negative prices
            df = df[df['price'] > 0]
            
            # Remove rows with unreasonably large values (overflow protection)
            MAX_PRICE = 1_000_000  # Max price: 10 lakhs
            MAX_QUANTITY = 10_000_000  # Max quantity: 1 crore units
            
            df = df[df['price'] <= MAX_PRICE]
            df = df[df['quantity'] <= MAX_QUANTITY]
            
            final_count = len(df)
            
            if original_count > final_count:
                st.warning(f"⚠️ Data cleaned: {original_count} → {final_count} valid transactions")
                st.caption(f"Removed {original_count - final_count} rows with invalid values")
            
            if final_count == 0:
                st.error("❌ No valid transactions remaining after validation")
                return False
            
            # Save transactions in bulk
            st.info(f"💾 Saving {len(df)} transactions to database...")
            success = save_transactions_bulk_supabase(df, file_id, user_id)
            
            if success:
                st.success(f"✅ Saved {len(df)} transactions to database")
                
                # STEP 1: Fetch and cache historical prices for transaction dates
                if BULK_FETCH_AVAILABLE:
                    # NEW: Use BULK fetching (20x faster!)
                    st.info("📥 Fetching historical prices in BULK mode (20x faster)...")
                    try:
                        fetch_historical_prices_bulk(
                            df=df,
                            user_id=user_id,
                            progress_callback=lambda msg: st.caption(msg)
                        )
                        st.success("✅ Historical prices cached (bulk mode)!")
                    except Exception as e:
                        st.warning(f"⚠️ Bulk historical fetch failed, using fallback: {e}")
                        try:
                            self.update_missing_historical_prices(user_id)
                            st.success("✅ Historical prices cached (fallback mode)!")
                        except Exception as e2:
                            st.warning(f"⚠️ Historical price caching had warnings: {e2}")
                else:
                    # FALLBACK: Use old method
                    st.info("🔄 Caching historical prices for transaction dates...")
                    try:
                        self.update_missing_historical_prices(user_id)
                        st.success("✅ Historical prices cached!")
                    except Exception as e:
                        st.warning(f"⚠️ Historical price caching had warnings: {e}")
                
                # STEP 2: Fetch live prices and sectors for new tickers (skip if requested)
                if not skip_live_prices:
                    st.info("🔄 Fetching live prices and sectors for new tickers...")
                    try:
                        # Smart refresh: only fetch tickers without prices (not force refresh)
                        # This avoids re-fetching prices for tickers from previous files
                        self.fetch_live_prices_and_sectors(user_id, force_refresh=False)
                        st.success("✅ Live prices and sectors updated successfully!")
                    except Exception as e:
                        st.warning(f"⚠️ Live price update had warnings: {e}")
                else:
                    st.caption("⏩ Skipping live prices (will be fetched at login for current market prices)")
                
                # STEP 3: Cache weekly AND monthly price data for charts (skip if requested)
                if not skip_weekly_cache:
                    if BULK_FETCH_AVAILABLE:
                        # NEW: Use BULK fetching for weekly prices (20x faster!)
                        st.info("📈 Fetching weekly prices in BULK mode (20x faster)...")
                        try:
                            fetch_weekly_prices_bulk(
                                df=df,
                                user_id=user_id,
                                weeks=26,  # 6 months
                                progress_callback=lambda msg: st.caption(msg)
                            )
                            st.success("✅ Weekly price data cached (bulk mode)!")
                        except Exception as e:
                            st.warning(f"⚠️ Bulk weekly fetch failed, using fallback: {e}")
                            try:
                                with st.spinner("⏳ Building weekly cache (fallback)..."):
                                    self.populate_weekly_and_monthly_cache(user_id)
                                st.success("✅ Weekly data cached (fallback mode)!")
                            except Exception as e2:
                                st.warning(f"⚠️ Weekly cache had warnings: {e2}")
                                st.info("💡 You can manually refresh the cache later from Settings → Refresh Cache")
                    else:
                        # FALLBACK: Use old method
                        st.info("🔄 Caching weekly and monthly price data for charts...")
                        try:
                            with st.spinner("⏳ Building weekly price cache..."):
                                self.populate_weekly_and_monthly_cache(user_id)
                            st.success("✅ Weekly and monthly price data cached successfully!")
                        except Exception as e:
                            st.warning(f"⚠️ Weekly/monthly cache had warnings: {e}")
                            st.info("💡 You can manually refresh the cache later from Settings → Refresh Cache")
                else:
                    st.caption("⏩ Skipping weekly cache (will be populated after all files are processed)")
                
                # STEP 3.5: PMS/AIF values will be updated during login using AI
                # (Old PDF-based updater removed - was failing to extract returns)
                # AI-based update happens in background during login for better accuracy
                st.info("💡 PMS/AIF values will be updated during login using AI")
                
                # STEP 4: Refresh portfolio data to include new transactions
                st.info("🔄 Refreshing portfolio data...")
                try:
                    # Clear cache before loading to ensure fresh data after upload
                    clear_portfolio_cache(user_id)
                    
                    self.load_portfolio_data(user_id, force_refresh=True)
                    st.success("✅ Portfolio data refreshed successfully!")
                except Exception as e:
                    # Portfolio refresh failed - error already shown by load_portfolio_data
                    # Just provide additional context about the file upload status
                    st.info("💡 File was uploaded successfully, but portfolio display needs attention")
                    print(f"⚠️ Portfolio refresh failed after file upload: {e}")
                    return False  # Return False to indicate partial failure
                
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
    
    def handle_registration_with_files(self):
        """Handle registration with file processing - shows progress and waits for completion"""
        st.markdown("### 🔄 Processing Your Account and Files")
        st.markdown(f"**Username:** {self.session_state.registration_username}")
        st.markdown(f"**Files to Process:** {len(self.session_state.pending_files)}")
        st.markdown("---")
        
        # Step 1: Create user account
        st.info("**Step 1:** Creating your account...")
        
        try:
            result = create_user_supabase(
                self.session_state.registration_username,
                self.session_state.registration_password,
                "salt",
                role="user"
            )
            
            if not result:
                st.error("❌ Username already exists. Please choose another username.")
                if st.button("← Back to Registration"):
                    self.session_state.registration_in_progress = False
                    self.session_state.pending_files = []
                    st.rerun()
                return
            
            user_id = result['id']
            st.success(f"✅ Account created successfully!")
            
            # Step 2: Process all files
            st.markdown("---")
            st.info(f"**Step 2:** Processing {len(self.session_state.pending_files)} file(s)...")
            
            processed_count = 0
            failed_count = 0
            failed_files = []
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for idx, uploaded_file in enumerate(self.session_state.pending_files):
                try:
                    status_text.text(f"Processing {idx+1}/{len(self.session_state.pending_files)}: {uploaded_file.name}")
                    progress_bar.progress(idx / len(self.session_state.pending_files))
                    
                    # Process the file with comprehensive error handling
                    # ✅ NEW: Fetch weekly prices IMMEDIATELY after each file
                    # This ensures data is complete right away, no need to re-read DB later
                    try:
                        # Step 1: Process transactions from CSV
                        success = self.process_csv_file(
                            uploaded_file, 
                            user_id, 
                            skip_weekly_cache=True,  # We'll do it manually below
                            skip_live_prices=True     # Live prices at login only
                        )
                    
                        if success:
                            st.success(f"✅ {uploaded_file.name} - Transactions saved")
                            
                            # Step 2: Immediately fetch weekly prices for THIS file's tickers
                            try:
                                st.info(f"🔄 Fetching weekly prices for {uploaded_file.name}...")
                                
                                # Get transactions from this file to know which tickers to fetch
                                from database_config_supabase import get_transactions_supabase
                                all_transactions = get_transactions_supabase(user_id=user_id)
                                
                                if all_transactions:
                                    df_all = pd.DataFrame(all_transactions)
                                    # Get only tickers from this file (most recent transactions)
                                    file_tickers = df_all['ticker'].unique()[-15:]  # Assume last 15 are from this file
                                    
                                    # Use optimized bulk fetch for this file's tickers
                                    from datetime import datetime, timedelta
                                    import yfinance as yf
                                    
                                    for ticker in file_tickers:
                                        try:
                                            # Fetch ALL 52 weeks in ONE call (fast!)
                                            one_year_ago = datetime.now() - timedelta(days=365)
                                            yf_ticker = f"{ticker}.NS" if not str(ticker).isdigit() else f"{ticker}.NS"
                                            stock = yf.Ticker(yf_ticker)
                                            hist = stock.history(start=one_year_ago, end=datetime.now(), interval='1wk')
                                            
                                            if not hist.empty:
                                                # Save all weeks to DB
                                                from database_config_supabase import save_stock_price_supabase
                                                for date_idx, price in zip(hist.index, hist['Close']):
                                                    date_str = date_idx.strftime('%Y-%m-%d')
                                                    save_stock_price_supabase(ticker, date_str, float(price), 'yfinance_weekly')
                                                print(f"✅ {ticker}: {len(hist)} weekly prices cached")
                                        except Exception as ticker_err:
                                            print(f"⚠️ {ticker}: Weekly fetch failed, will use AI fallback at login")
                                    
                                    st.success(f"✅ {uploaded_file.name} - Weekly prices cached!")
                            except Exception as weekly_err:
                                print(f"⚠️ Weekly cache error for {uploaded_file.name}: {weekly_err}")
                                # Continue anyway - weekly prices can be fetched at login
                            
                            processed_count += 1
                        else:
                            st.error(f"❌ {uploaded_file.name}")
                            failed_count += 1
                            failed_files.append(uploaded_file.name)
                    except Exception as process_error:
                        st.error(f"❌ {uploaded_file.name}: {str(process_error)}")
                        failed_count += 1
                        failed_files.append(f"{uploaded_file.name} ({str(process_error)})")
                        # Don't stop processing - continue with next file
                        import traceback
                        print(f"Error processing {uploaded_file.name}:")
                        print(traceback.format_exc())
                    
                    time.sleep(0.2)  # Visual feedback
                    
                except Exception as e:
                    st.error(f"❌ Unexpected error with {uploaded_file.name}: {str(e)}")
                    failed_count += 1
                    failed_files.append(f"{uploaded_file.name} (Unexpected: {str(e)})")
                    import traceback
                    print(f"Unexpected error processing {uploaded_file.name}:")
                    print(traceback.format_exc())
                    continue
            
            # Complete progress
            progress_bar.progress(1.0)
            status_text.text("✅ File processing complete!")
            time.sleep(0.5)
            progress_bar.empty()
            status_text.empty()
            
            # ✅ REMOVED: Bulk fetch at end - now done per-file above
            # Weekly prices are fetched immediately after each file is processed
            # This is faster and more reliable than batch processing at the end
            
            # Step 3: Show summary
            st.markdown("---")
            st.markdown("### 📊 Processing Summary")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("✅ Files Processed", processed_count)
            with col2:
                st.metric("❌ Failed", failed_count)
            with col3:
                st.metric("📁 Total", len(self.session_state.pending_files))
            
            if failed_files:
                with st.expander("❌ Failed Files"):
                    for failed_file in failed_files:
                        st.write(f"- {failed_file}")
            
            if processed_count > 0:
                st.success(f"🎉 Registration complete! {processed_count} file(s) processed successfully!")
                
                # ✅ Check if bulk fetch completed successfully
                bulk_fetch_done = st.session_state.get(f"bulk_fetch_done_{user_id}", False)
                
                if bulk_fetch_done:
                    st.success("✅ All prices have been cached successfully!")
                    st.info("👉 Click below to log in to your account")
                else:
                    st.warning("⚠️ Price caching is in progress or incomplete.")
                    st.info("💡 You can login now and the system will continue fetching prices in the background, or wait for completion.")
                
                if st.button("🚀 Log In to Your Account", type="primary", use_container_width=True):
                    # Complete login
                    self.session_state.user_authenticated = True
                    self.session_state.user_id = user_id
                    self.session_state.username = self.session_state.registration_username
                    self.session_state.user_role = "user"
                    self.session_state.login_time = datetime.now()
                    
                    # Clear registration state
                    self.session_state.registration_in_progress = False
                    self.session_state.registration_username = None
                    self.session_state.registration_password = None
                    self.session_state.pending_files = []
                    
                    # Update last login
                    update_user_login_supabase(user_id)
                    
                    # Initialize portfolio data after registration (CRITICAL FIX - load portfolio before showing dashboard)
                    st.info("🔄 Loading your portfolio data...")
                    # Skip cache population here - already done at line 1324 during registration
                    self.initialize_portfolio_data(skip_cache_population=True)
                    
                    st.rerun()
            else:
                st.error("❌ All files failed to process. Please check your files and try again.")
                if st.button("← Back to Registration"):
                    self.session_state.registration_in_progress = False
                    self.session_state.pending_files = []
                    st.rerun()
        
        except Exception as e:
            st.error(f"❌ Registration error: {e}")
            import traceback
            st.error(traceback.format_exc())
            if st.button("← Back to Registration"):
                self.session_state.registration_in_progress = False
                self.session_state.pending_files = []
                st.rerun()
    
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
            
            # CRITICAL: Load portfolio data FIRST (before cache) for immediate dashboard access
            # This ensures the dashboard works even if cache is still populating
            
            # Load portfolio data (essential for dashboard) - uses existing prices from DB
            self.load_portfolio_data(user_id)
            
            # Fetch live prices and sectors (updates prices in background)
            # Always fetch live prices for portfolio calculations, but don't force refresh unless needed
            self.fetch_live_prices_and_sectors(user_id, force_refresh=False)
            
            # Refresh portfolio with updated live prices - MUST use force_refresh to bypass cache!
            self.load_portfolio_data(user_id, force_refresh=True)
            
            # ✅ INCREMENTAL WEEKLY CACHE: Triggered during login
            # - Checks max date from DB for each ticker
            # - Fetches ONLY missing weeks since last update
            # - Uses AI for all asset types
            if not skip_cache_population:
                cache_key = f'incremental_cache_done_{user_id}'
                
                # Only run once per session
                if cache_key not in st.session_state:
                    st.info("🔄 Checking for missing weekly prices...")
                    try:
                        # This will only fetch NEW weeks based on max DB date
                        self.populate_weekly_and_monthly_cache(user_id)
                        st.session_state[cache_key] = True
                        st.success("✅ Weekly price cache updated!")
                    except Exception as cache_error:
                        print(f"⚠️ Incremental cache warning: {cache_error}")
                        st.session_state[cache_key] = True  # Mark done to avoid retry loop
                        st.info("💡 Some weekly data may be fetched on-demand later")
            
        except Exception as e:
            st.error(f"Error initializing portfolio data: {e}")
    
    def populate_weekly_and_monthly_cache(self, user_id):
        """
        INCREMENTAL weekly price cache update:
        - Only fetches NEW weeks since last cache update
        - Derives monthly from weekly data (NO separate monthly fetch)
        - Smart detection of missing data
        - Automatically triggered during login and file upload
        - Weekly data saved to historical_prices table
        - Monthly data derived from weekly cache and saved
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
                # Always fetch full 1 year of data (not just from purchase date)
                start_date = one_year_ago
                ticker_purchase_dates[ticker] = start_date
            
            # Check last 10 weeks for all tickers
            check_date = current_date
            ticker_latest_cached = {ticker: None for ticker in unique_tickers}
            
            if BULK_QUERY_AVAILABLE:
                # Use optimized bulk query method
                for week_idx in range(10):  # Check last 10 weeks
                    # Get Monday of the week
                    monday = check_date - timedelta(days=check_date.weekday())
                    
                    # ✅ FIX: Check ALL 7 days in week (not just Monday)
                    # This ensures we detect bulk fetch data saved on any day
                    tickers_to_check = [t for t in unique_tickers if ticker_latest_cached[t] is None]
                    if tickers_to_check:
                        # Check each day of the week
                        for day_offset in range(7):
                            check_day = monday + timedelta(days=day_offset)
                            check_day_str = check_day.strftime('%Y-%m-%d')
                            
                            cached_prices = get_stock_prices_bulk_supabase(tickers_to_check, check_day_str)
                            
                            # Update latest cached dates for tickers found
                            if cached_prices:
                                for ticker, price in cached_prices.items():
                                    if price and price > 0:
                                        ticker_latest_cached[ticker] = monday
                                        # Remove from check list
                                        if ticker in tickers_to_check:
                                            tickers_to_check.remove(ticker)
                            
                            # If all tickers found, no need to check remaining days
                            if not tickers_to_check:
                                break
                    
                    check_date -= timedelta(days=7)
            else:
                # Fallback to original sequential method
                for ticker in unique_tickers:
                    check_date_ticker = current_date
                    for _ in range(10):  # Check last 10 weeks
                        monday = check_date_ticker - timedelta(days=check_date_ticker.weekday())
                        
                        # ✅ FIX: Check ALL 7 days in week (not just Monday)
                        found = False
                        for day_offset in range(7):
                            check_day = monday + timedelta(days=day_offset)
                            cached_price = get_stock_price_supabase(ticker, check_day.strftime('%Y-%m-%d'))
                            if cached_price and cached_price > 0:
                                ticker_latest_cached[ticker] = monday
                                found = True
                                break
                        
                        if found:
                            break  # Move to next ticker
                        
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
            pms_count = sum(1 for t in unique_tickers if any(keyword in str(t).upper() for keyword in [
                'PMS', 'AIF', 'INP', 'BUOYANT', 'CARNELIAN', 'JULIUS', 'VALENTIS', 'UNIFI'
            ]) or str(t).upper().endswith('_PMS') or str(t).startswith('INP'))

            if any(latest_cached_dates[t] > one_year_ago + timedelta(days=7) for t in unique_tickers):
                st.info(f"🔄 Incremental update: Fetching {total_weeks_to_fetch} new weekly prices for {len(unique_tickers)} holdings...")
                st.caption("💡 Only fetching data for new weeks since last update!")
            else:
                st.info(f"🔄 Initial cache: Fetching weekly prices for {len(unique_tickers)} holdings ({pms_count} PMS/AIF, {len(unique_tickers) - pms_count} stocks/MF) (1 year)...")
                st.caption("💡 This is a one-time process. Future updates will be incremental!")
            
            # Create progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Separate tickers into: NEVER cached (new) vs. needs update (incremental)
            new_tickers = []  # Tickers with NO cache at all
            update_tickers = []  # Tickers with some cache but needs more

            for ticker in unique_tickers:
                if latest_cached_dates[ticker] < current_date:
                    if ticker_latest_cached[ticker] is None:
                        # Never cached before - must process
                        new_tickers.append(ticker)
                    else:
                        # Has some cache, needs update - can limit
                        update_tickers.append(ticker)
            
            # Always process ALL new tickers (no limit)
            # Only limit incremental updates for existing tickers
            max_update_tickers = 20  # Limit for incremental updates only
            
            if new_tickers:
                st.info(f"🚀 **First-time setup:** Processing all {len(new_tickers)} holdings to build complete price cache.")
                st.caption("⏱️ This one-time process ensures optimal performance for all future sessions!")
            
            # Process all new tickers + limited update tickers
            if len(update_tickers) > max_update_tickers:
                st.caption(f"💡 Also updating {max_update_tickers} existing holdings (incremental). Remaining will be updated next time.")
                valid_tickers = new_tickers + update_tickers[:max_update_tickers]
            else:
                valid_tickers = new_tickers + update_tickers
            
            if not valid_tickers:
                st.info("✅ All prices are already up to date!")
                return
            
            # Generate all weekly dates needed across all tickers (with reasonable limits)
            all_week_dates = set()
            ticker_week_map = {}  # Map ticker to list of weeks it needs
            max_weeks_per_ticker = 52  # Limit to prevent infinite loops

            for ticker in valid_tickers:
                start_from = latest_cached_dates[ticker]

                # Limit the date range to prevent excessive processing
                # If start_from is very old, only go back 1 year max
                one_year_ago = current_date - timedelta(days=365)
                effective_start = max(start_from, one_year_ago)

                if effective_start >= current_date:
                    continue  # No weeks to fetch

                weekly_dates = pd.date_range(start=effective_start, end=current_date, freq='W-MON')

                # Limit to prevent excessive API calls
                if len(weekly_dates) > max_weeks_per_ticker:
                    weekly_dates = weekly_dates[-max_weeks_per_ticker:]  # Only fetch last 52 weeks

                ticker_week_map[ticker] = list(weekly_dates)
                all_week_dates.update(weekly_dates)
            
            # Sort weeks chronologically
            all_week_dates = sorted(list(all_week_dates))
            total_weeks = len(all_week_dates)
            
            # Additional safeguard: if too many weeks, limit to prevent system hanging
            max_total_weeks = 200  # Reasonable limit for batch processing
            if total_weeks > max_total_weeks:
                st.warning(f"⚠️ Too many weeks to fetch ({total_weeks}). Limiting to {max_total_weeks} most recent weeks.")
                all_week_dates = all_week_dates[-max_total_weeks:]
                total_weeks = max_total_weeks
            
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
                    
                    # Fetch missing prices using AI
                    tickers_to_fetch = []
                    for ticker in tickers_for_week:
                        if ticker in cached_prices and cached_prices[ticker] > 0:
                            # Already cached
                            all_weekly_prices[ticker][week_date] = cached_prices[ticker]
                        else:
                            tickers_to_fetch.append(ticker)
                    
                    # ✅ OPTIMIZED: Fetch ALL weeks for each ticker in ONE call (18x faster!)
                    if tickers_to_fetch:
                        print(f"🚀 OPTIMIZED: Fetching ALL weeks for {len(tickers_to_fetch)} tickers in ONE call each...")
                        
                        # Group by weeks needed
                        ticker_date_ranges = {}
                        for ticker in tickers_to_fetch:
                            # Find min/max dates needed for this ticker
                            ticker_weeks = [w for w in week_list if ticker in tickers_for_week]
                            if ticker_weeks:
                                ticker_date_ranges[ticker] = (min(ticker_weeks), max(ticker_weeks))
                        
                        api_failed_tickers = []
                        
                        for ticker, (start, end) in ticker_date_ranges.items():
                            ticker_trans = buy_transactions[buy_transactions['ticker'] == ticker]
                            name = ticker_trans.iloc[0].get('stock_name', ticker) if not ticker_trans.empty else ticker
                            
                            is_pms_aif = (ticker.startswith('INP') or ticker.startswith('INA') or 'PMS' in ticker.upper() or 'AIF' in ticker.upper())
                            is_mutual_fund = str(ticker).isdigit() or ticker.startswith('MF_')
                            
                            if is_pms_aif:
                                api_failed_tickers.append((ticker, name, 'PMS/AIF', start, end))
                            elif is_mutual_fund:
                                # Try yfinance for MF (gets all weeks at once)
                                try:
                                    import yfinance as yf
                                    yf_ticker = f"{ticker}.NS"
                                    stock = yf.Ticker(yf_ticker)
                                    hist = stock.history(start=start, end=end + timedelta(days=7), interval='1wk')
                                    if not hist.empty:
                                        for date_idx, price in zip(hist.index, hist['Close']):
                                            date_str = date_idx.strftime('%Y-%m-%d')
                                            all_weekly_prices[ticker][pd.to_datetime(date_str)] = float(price)
                                            weekly_cached_count += 1
                                            from database_config_supabase import save_stock_price_supabase
                                            save_stock_price_supabase(ticker, date_str, float(price), 'api_bulk')
                                        print(f"✅ yfinance BULK (FREE): {ticker} = {len(hist)} weeks fetched!")
                                    else:
                                        api_failed_tickers.append((ticker, name, 'Mutual Fund', start, end))
                                except:
                                    api_failed_tickers.append((ticker, name, 'Mutual Fund', start, end))
                            else:
                                # Try yfinance for Stocks (gets all weeks at once)
                                try:
                                    import yfinance as yf
                                    yf_ticker = f"{ticker}.NS" if not ticker.endswith(('.NS', '.BO')) else ticker
                                    stock = yf.Ticker(yf_ticker)
                                    hist = stock.history(start=start, end=end + timedelta(days=7), interval='1wk')
                                    if not hist.empty:
                                        for date_idx, price in zip(hist.index, hist['Close']):
                                            date_str = date_idx.strftime('%Y-%m-%d')
                                            all_weekly_prices[ticker][pd.to_datetime(date_str)] = float(price)
                                            weekly_cached_count += 1
                                            from database_config_supabase import save_stock_price_supabase
                                            save_stock_price_supabase(ticker, date_str, float(price), 'api_bulk')
                                        print(f"✅ yfinance BULK (FREE): {ticker} = {len(hist)} weeks fetched!")
                                    else:
                                        api_failed_tickers.append((ticker, name, 'Stock', start, end))
                                except:
                                    api_failed_tickers.append((ticker, name, 'Stock', start, end))
                        
                        # AI fallback for failed tickers (week-by-week for these only)
                        if api_failed_tickers:
                            try:
                                from ai_price_fetcher import AIPriceFetcher
                                ai_fetcher = AIPriceFetcher()
                                
                                if ai_fetcher.is_available():
                                    print(f"🤖 AI: Fetching {len(api_failed_tickers)} API-failed tickers...")
                                    for ticker, name, asset_type, start, end in api_failed_tickers:
                                        # Use AI week-by-week only for failed ones
                                        current = start
                                        while current <= end:
                                            week_str = current.strftime('%Y-%m-%d')
                                            if 'Mutual Fund' in asset_type:
                                                result = ai_fetcher.get_mutual_fund_nav(ticker, name, week_str)
                                            elif 'PMS' in asset_type or 'AIF' in asset_type:
                                                result = ai_fetcher.get_pms_aif_nav(ticker, name, week_str)
                                            else:
                                                result = ai_fetcher.get_stock_price(ticker, name, week_str)
                                            
                                            if result and isinstance(result, dict) and result.get('price', 0) > 0:
                                                price = result['price']
                                                all_weekly_prices[ticker][current] = price
                                                weekly_cached_count += 1
                                                from database_config_supabase import save_stock_price_supabase
                                                save_stock_price_supabase(ticker, week_str, price, 'ai_fallback')
                                            current += timedelta(days=7)
                                else:
                                    print(f"⚠️ AI not available")
                            except Exception as e:
                                print(f"⚠️ AI fallback error: {e}")
                else:
                    # Fallback: Check each ticker individually
                    for ticker in tickers_for_week:
                        from database_config_supabase import get_stock_price_supabase
                        cached_price = get_stock_price_supabase(ticker, week_date_str)
                        
                        if cached_price and cached_price > 0:
                            all_weekly_prices[ticker][week_date] = cached_price
                        else:
                            # ✅ USE FREE API FIRST, AI FALLBACK for missing price
                            ticker_trans = buy_transactions[buy_transactions['ticker'] == ticker]
                            name = ticker_trans.iloc[0].get('stock_name', ticker) if not ticker_trans.empty else ticker
                            
                            # Determine asset type
                            is_pms_aif = (ticker.startswith('INP') or ticker.startswith('INA') or 'PMS' in ticker.upper() or 'AIF' in ticker.upper())
                            is_mutual_fund = str(ticker).isdigit() or ticker.startswith('MF_')
                            
                            price = None
                            
                            # Try FREE APIs first
                            if is_pms_aif:
                                # PMS/AIF: No free API, skip to AI
                                pass
                            elif is_mutual_fund:
                                # Try mftool (FREE)
                                try:
                                    from mf_price_fetcher import MFPriceFetcher
                                    mf_fetcher = MFPriceFetcher()
                                    nav_data = mf_fetcher.get_mutual_fund_nav(ticker, week_date_str)
                                    if nav_data and nav_data.get('nav', 0) > 0:
                                        price = float(nav_data['nav'])
                                        print(f"✅ mftool (FREE): {ticker} = ₹{price} on {week_date_str}")
                                except:
                                    pass
                            else:
                                # Try yfinance (FREE)
                                try:
                                    import yfinance as yf
                                    yf_ticker = f"{ticker}.NS" if not ticker.endswith(('.NS', '.BO')) else ticker
                                    stock = yf.Ticker(yf_ticker)
                                    hist = stock.history(start=week_date, end=week_date + timedelta(days=1))
                                    if not hist.empty:
                                        price = float(hist['Close'].iloc[0])
                                        print(f"✅ yfinance (FREE): {ticker} = ₹{price} on {week_date_str}")
                                except:
                                    pass
                            
                            # If API failed or PMS/AIF, use AI
                            if not price or price <= 0:
                                try:
                                    from ai_price_fetcher import AIPriceFetcher
                                    ai_fetcher = AIPriceFetcher()
                                    
                                    if ai_fetcher.is_available():
                                        # Get price via AI
                                        if is_mutual_fund:
                                            result = ai_fetcher.get_mutual_fund_nav(ticker, name, week_date_str)
                                        elif is_pms_aif:
                                            result = ai_fetcher.get_pms_aif_nav(ticker, name, week_date_str)
                                        else:
                                            result = ai_fetcher.get_stock_price(ticker, name, week_date_str)
                                        
                                        if result and isinstance(result, dict) and result.get('price', 0) > 0:
                                            price = result['price']
                                            print(f"✅ AI: {ticker} = ₹{price} on {week_date_str}")
                                except Exception as e:
                                    print(f"⚠️ AI fetch failed for {ticker} on {week_date_str}: {e}")
                            
                            # Save if we got a price
                            if price and price > 0:
                                all_weekly_prices[ticker][week_date] = price
                                weekly_cached_count += 1
                                from database_config_supabase import save_stock_price_supabase
                                save_stock_price_supabase(ticker, week_date_str, price, 'api_or_ai_incremental')

            
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
    
    def cache_transaction_historical_prices(self, df, user_id):
        """
        Cache historical prices for all transactions to historical_prices table.
        This ensures we have price data for transaction dates for charts and analysis.
        
        Args:
            df: DataFrame with transaction data (must have 'ticker', 'date' columns)
            user_id: User ID
        """
        try:
            from database_config_supabase import save_stock_price_supabase
            from datetime import datetime
            
            # Get unique ticker-date combinations
            unique_transactions = df[['ticker', 'date']].drop_duplicates()
            
            success_count = 0
            skip_count = 0
            error_count = 0
            
            for _, row in unique_transactions.iterrows():
                ticker = row['ticker']
                transaction_date = pd.to_datetime(row['date'])
                date_str = transaction_date.strftime('%Y-%m-%d')
                
                try:
                    # Fetch historical price using comprehensive fetcher
                    historical_price = self.fetch_historical_price_comprehensive(ticker, transaction_date)
                        
                    if historical_price and historical_price > 0:
                        success_count += 1
                    else:
                        skip_count += 1
                        
                except Exception as e:
                    error_count += 1
                    print(f"⚠️ Error caching price for {ticker} on {date_str}: {e}")
            
            print(f"📊 Historical price caching: {success_count} cached, {skip_count} skipped, {error_count} errors")
            return success_count
        except Exception as e:
            print(f"❌ Error in cache_transaction_historical_prices: {e}")
            return 0
    
    def update_missing_historical_prices(self, user_id):
        """Update missing historical prices in database"""
        try:
            # Get user transactions
            transactions = get_transactions_supabase(user_id=user_id)
            if not transactions:
                return
            
            df = pd.DataFrame(transactions)
            
            # Cache historical prices for all transactions
            return self.cache_transaction_historical_prices(df, user_id)
                            
        except Exception as e:
            print(f"❌ Error in update_missing_historical_prices: {e}")
            raise
    
    def fetch_live_prices_and_sectors(self, user_id, force_refresh=False):
        """
        Fetch live prices and sectors for all tickers
        
        Args:
            user_id: User ID
            force_refresh: If True, force refresh even if already fetched this session
        """
        from datetime import datetime, timedelta
        try:
            # Note: We no longer use session-level caching
            # Instead, we check at ticker level to only fetch missing prices
            # This allows multiple file uploads in sequence to work correctly
            
            st.info("🔄 Fetching live prices and sectors...")
            
            # Show data fetching animation
            self.show_data_fetching_animation()
            
            # Get all transactions for the user
            transactions = get_transactions_supabase(user_id=user_id)
            if not transactions:
                st.warning("No transactions found for user")
                return
            
            df = pd.DataFrame(transactions)
            all_tickers = df['ticker'].unique()
            
            # Filter out tickers that already have valid live prices (unless force_refresh)
            from database_config_supabase import get_stock_data_supabase
            
            # First, show total count
            st.caption(f"📊 Total tickers in portfolio: {len(all_tickers)}")
            
            if force_refresh:
                # Force refresh: fetch all tickers
                unique_tickers = all_tickers
                st.info(f"🔄 Refreshing prices for all {len(unique_tickers)} tickers...")
            else:
                # Smart refresh: only fetch tickers without live prices
                # Use BATCH query instead of individual queries (60x faster!)
                tickers_needing_fetch = []
                progress_text = st.empty()
                progress_text.text("🔍 Checking which tickers need price updates (batch mode)...")
                
                try:
                    # Single batch query for all tickers
                    stock_data_dict = bulk_get_stock_data(list(all_tickers))
                    
                    # Check which ones need fetching
                    for ticker in all_tickers:
                        stock_info = stock_data_dict.get(ticker)
                        if not stock_info or not stock_info.get('live_price') or stock_info.get('live_price') <= 0:
                            tickers_needing_fetch.append(ticker)
                    
                    print(f"✅ Batch check complete: {len(tickers_needing_fetch)}/{len(all_tickers)} need updates")
                except Exception as e:
                    print(f"⚠️ Batch check failed, falling back to all tickers: {e}")
                    tickers_needing_fetch = list(all_tickers)
                
                unique_tickers = tickers_needing_fetch
                progress_text.empty()  # Clear progress message
                
                if len(tickers_needing_fetch) == 0:
                    st.success(f"✅ All {len(all_tickers)} tickers already have cached prices!")
                    return  # Nothing to fetch
                elif len(tickers_needing_fetch) < len(all_tickers):
                    already_cached = len(all_tickers) - len(tickers_needing_fetch)
                    st.info(f"🔍 Fetching prices for {len(unique_tickers)} new tickers (✅ {already_cached} already cached)")
                else:
                    st.info(f"🔍 Fetching prices for all {len(unique_tickers)} tickers...")
            
            # Initialize storage
            live_prices = {}
            sectors = {}
            market_caps = {}
            
            # Check if BULK fetching is available (20x faster!)
            if BULK_FETCH_AVAILABLE and len(unique_tickers) > 0:
                # NEW: Use BULK price fetching (20x faster!)
                st.info(f"💰 Fetching live prices for {len(unique_tickers)} tickers (BULK mode - 20x faster)...")
                print("=" * 80)
                print("🚀 BULK LIVE PRICE FETCH - STARTING")
                print("=" * 80)
                print(f"📊 Total tickers: {len(unique_tickers)}")
                print(f"📋 Tickers: {list(unique_tickers)[:10]}{'...' if len(unique_tickers) > 10 else ''}")
                
                try:
                    # Create DataFrame for bulk fetch
                    trans_map = {t: df[df['ticker']==t].iloc[0].to_dict() for t in unique_tickers if t in df['ticker'].values}
                    df_tickers = pd.DataFrame({
                        'ticker': list(unique_tickers),
                        'stock_name': [trans_map.get(t, {}).get('stock_name', t) for t in unique_tickers]
                    })
                    
                    print(f"📊 DataFrame created with {len(df_tickers)} rows")
                    print(f"📋 Columns: {list(df_tickers.columns)}")
                    
                    # Bulk fetch
                    print("🔄 Calling fetch_live_prices_bulk()...")
                    bulk_prices = fetch_live_prices_bulk(
                        df=df_tickers,
                        user_id=user_id,
                        progress_callback=lambda msg: st.caption(msg)
                    )
                    
                    print(f"✅ Bulk fetch returned {len(bulk_prices)} prices")
                    
                    # Convert to session format
                    for ticker, (price, sector) in bulk_prices.items():
                        live_prices[ticker] = price
                        sectors[ticker] = sector
                    
                    # Store in session state
                    self.session_state.live_prices = live_prices
                    self.session_state.sectors = sectors
                    
                    print(f"✅ Stored in session: {len(live_prices)} live prices, {len(sectors)} sectors")
                    print("=" * 80)
                    
                    st.success(f"✅ Live prices fetched successfully (bulk mode): {len(live_prices)} tickers")
                    return  # Done! Exit early
                    
                except Exception as e:
                    st.warning(f"⚠️ Bulk fetch failed ({e}), falling back to individual fetching...")
                    print("=" * 80)
                    print(f"❌ BULK FETCH ERROR: {e}")
                    print("=" * 80)
                    import traceback
                    print(traceback.format_exc())
                    print("=" * 80)
                    # Fall through to individual fetching
            
            # FALLBACK: Individual fetching (when bulk not available or failed)
            # Fetch live prices and sectors for each ticker
            # Note: Live prices are fetched from external APIs (yfinance, mftool, etc.)
            # which don't support bulk operations. However, database cache operations
            # in populate_weekly_and_monthly_cache() now use bulk queries for optimal performance.

            # Add rate limiting to prevent API overload
            import time
            successful_fetches = 0
            max_consecutive_failures = 5
            consecutive_failures = 0

            # Add progress bar for live updates
            progress_bar = st.progress(0)
            status_text = st.empty()
            total_tickers = len(unique_tickers)

            for idx, ticker in enumerate(unique_tickers):
                # Update progress
                progress = (idx + 1) / total_tickers
                progress_bar.progress(progress)
                status_text.text(f"💹 Fetching {idx + 1}/{total_tickers}: {ticker}...")
                # Rate limiting: small delay between requests
                if successful_fetches > 0:
                    time.sleep(0.5)  # 500ms between requests
                
                try:
                    ticker_str = str(ticker).strip()
                    ticker_upper = ticker_str.upper()
                    
                    # Improved PMS/AIF detection using dedicated functions + name patterns
                    from pms_aif_fetcher import is_pms_code, is_aif_code
                    
                    is_pms_aif = (
                        is_pms_code(ticker_str) or  # Detects INP... SEBI codes
                        is_aif_code(ticker_str) or  # Detects AIF_IN_... SEBI codes
                        'PMS' in ticker_upper or 'AIF' in ticker_upper or
                        'BUOYANT' in ticker_upper or 'CARNELIAN' in ticker_upper or
                        'JULIUS BAER' in ticker_upper or 'VALENTIS' in ticker_upper or
                        'UNIFI' in ticker_upper or 'NUVAMA' in ticker_upper or
                        'PORTFOLIO MANAGEMENT' in ticker_upper or
                        'ALTERNATIVE INVESTMENT' in ticker_upper
                    )
                    
                    # Check if PMS/AIF (by SEBI codes or name patterns, not by value)
                    if is_pms_aif:
                        # 🤖 PMS/AIF - USE AI ONLY (Gemini FREE)
                        print(f"🤖 {ticker}: PMS/AIF detected, using AI (Gemini)")
                        
                        # Get transaction details
                        pms_transactions = df[df['ticker'] == ticker]
                        if not pms_transactions.empty:
                            pms_trans = pms_transactions.iloc[0]
                            pms_name = pms_trans.get('stock_name', ticker).replace('_', ' ')
                            
                            # Determine type
                            if is_aif_code(ticker_str) or 'AIF' in ticker_upper:
                                sector = "AIF"
                            else:
                                sector = "PMS"
                            
                            # Use AI to get NAV (returns {'date', 'price', 'sector'})
                            try:
                                from ai_price_fetcher import AIPriceFetcher
                                ai_fetcher = AIPriceFetcher()
                                
                                if ai_fetcher.is_available():
                                    print(f"🤖 AI: Fetching NAV for '{pms_name}' (Code: {ticker})")
                                    result = ai_fetcher.get_pms_aif_nav(ticker, pms_name)
                                    
                                    if result and isinstance(result, dict) and result.get('price', 0) > 0:
                                        live_price = result['price']
                                        sector = result.get('sector', sector)  # Use AI sector or fallback
                                        print(f"✅ AI found {sector} NAV: ₹{live_price} for {pms_name} (Date: {result.get('date', 'N/A')})")
                                    else:
                                        raise Exception("AI returned no price")
                                else:
                                    raise Exception("AI not available")
                                    
                            except Exception as ai_error:
                                print(f"⚠️ AI failed for {ticker} ({ai_error}), using transaction price")
                                # Fallback: transaction price
                                live_price = pms_trans['price']
                                print(f"   📊 Transaction Price Fallback: ₹{live_price}")
                        else:
                            live_price = None
                            if is_aif_code(ticker_str) or 'AIF' in ticker_upper:
                                sector = "AIF"
                            else:
                                sector = "PMS"
                    
                    elif str(ticker).isdigit() or ticker.startswith('MF_'):
                        # 📊 Mutual fund - Try FREE mftool API first, then AI fallback
                        print(f"📊 {ticker}: Mutual Fund detected, trying mftool (FREE)")
                        live_price = None
                        sector = "Mutual Fund"
                        
                        # Get fund name from transactions
                        mf_trans = df[df['ticker'] == ticker].iloc[0] if not df[df['ticker'] == ticker].empty else None
                        fund_name = mf_trans.get('stock_name', ticker) if mf_trans is not None else ticker
                    
                        # Try mftool FREE API first
                        try:
                            from mf_price_fetcher import MFPriceFetcher
                            mf_fetcher = MFPriceFetcher()
                            
                            # Get current NAV using mftool
                            scheme_code = str(ticker).replace('MF_', '')
                            nav_data = mf_fetcher.get_current_nav(scheme_code)
                            
                            if nav_data and nav_data > 0:
                                live_price = nav_data
                                print(f"✅ mftool (FREE): ₹{live_price} for {fund_name}")
                            else:
                                raise Exception("mftool returned no NAV")
                                
                        except Exception as api_error:
                            print(f"⚠️ mftool failed ({api_error}), trying AI...")
                            # Fallback to AI
                            try:
                                from ai_price_fetcher import AIPriceFetcher
                                ai_fetcher = AIPriceFetcher()
                                
                                if ai_fetcher.is_available():
                                    print(f"🤖 AI: Fetching NAV for '{fund_name}' (Code: {ticker})")
                                    result = ai_fetcher.get_mutual_fund_nav(ticker, fund_name)
                                    
                                    if result and isinstance(result, dict) and result.get('price', 0) > 0:
                                        live_price = result['price']
                                        sector = result.get('sector', 'Mutual Fund')
                                        print(f"✅ AI found MF NAV: ₹{live_price} for {fund_name} (Date: {result.get('date', 'N/A')}, Category: {sector})")
                                    else:
                                        raise Exception("AI returned no price")
                                else:
                                    raise Exception("AI not available")
                                    
                            except Exception as ai_error:
                                print(f"⚠️ AI also failed ({ai_error}), using transaction price")
                                # Last fallback: transaction price
                                if mf_trans is not None and 'price' in mf_trans:
                                    live_price = float(mf_trans['price'])
                                    print(f"   📊 Transaction Price Fallback: ₹{live_price}")
                                else:
                                    live_price = None
                                    print(f"   ❌ No price available for {ticker}")
                    
                    else:
                        # 📊 Stock, ETF, Bonds - USE AI FIRST, yfinance fallback
                        is_etf = ticker_upper.endswith('BEES') or ticker_upper.endswith('ETF')
                        is_bond = 'BOND' in ticker_upper or 'GILT' in ticker_upper or 'GSEC' in ticker_upper
                        
                        # Get asset name from transactions
                        asset_trans = df[df['ticker'] == ticker].iloc[0] if not df[df['ticker'] == ticker].empty else None
                        asset_name = asset_trans.get('stock_name', ticker) if asset_trans is not None else ticker
                        
                        asset_type = 'Bond' if is_bond else ('ETF' if is_etf else 'Stock')
                        print(f"📊 {ticker}: {asset_type} detected, using yfinance API")
                        
                        live_price = None
                        sector = None
                        market_cap = None
                        
                        # Try yfinance FREE API first
                        try:
                            import yfinance as yf
                            
                            # Add NSE/BSE suffix for Indian stocks
                            yf_ticker = ticker
                            if not any(suffix in ticker_upper for suffix in ['.NS', '.BO', '.BSE']):
                                yf_ticker = f"{ticker}.NS"
                            
                            stock = yf.Ticker(yf_ticker)
                            info = stock.info
                            
                            # Get current price
                            live_price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
                            
                            if live_price and live_price > 0:
                                sector = info.get('sector', 'Other Stocks')
                                market_cap = info.get('marketCap')
                                print(f"✅ yfinance (FREE): ₹{live_price} for {asset_name} (Sector: {sector})")
                            else:
                                raise Exception("yfinance returned no price")
                                
                        except Exception as api_error:
                            # Fallback to AI if yfinance fails
                            print(f"⚠️ yfinance failed ({api_error}), trying AI...")
                            try:
                                from ai_price_fetcher import AIPriceFetcher
                                ai_fetcher = AIPriceFetcher()
                                
                                if ai_fetcher.is_available():
                                    print(f"🤖 AI: Fetching price for '{asset_name}' (Ticker: {ticker})")
                                    result = ai_fetcher.get_stock_price(ticker, asset_name)
                                    
                                    if result and isinstance(result, dict) and result.get('price', 0) > 0:
                                        live_price = result['price']
                                        sector = result.get('sector', 'Other Stocks')
                                        print(f"✅ AI found {asset_type} price: ₹{live_price} for {asset_name} (Date: {result.get('date', 'N/A')}, Sector: {sector})")
                                        market_cap = None
                                    else:
                                        raise Exception("AI returned no price")
                                else:
                                    raise Exception("AI not available")
                                    
                            except Exception as ai_error:
                                print(f"⚠️ AI also failed ({ai_error})")
                                live_price = None
                                sector = 'Unknown'

                            # If no sector from yfinance, try to get it from stock data table
                            if not sector or sector == 'Unknown':
                                stock_data = get_stock_data_supabase(ticker)
                                # get_stock_data_supabase returns a list, get first item if available
                                if stock_data and isinstance(stock_data, list) and len(stock_data) > 0:
                                    sector = stock_data[0].get('sector', None)
                                else:
                                    sector = None

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
                        except Exception as e:
                            print(f"⚠️ {ticker}: yfinance/stock fetch failed: {e}")
                            live_price = None
                            sector = 'Unknown'
                except Exception as e:
                    print(f"⚠️ {ticker}: fetch failed: {e}")
                    live_price = None
                    sector = 'Unknown'
                
                print(f"🔍 DEBUG: {ticker} - live_price={live_price}, sector={sector}")

                # Store successful fetch (MUST be inside the for loop)
                if live_price and live_price > 0:
                    live_prices[ticker] = live_price
                    sectors[ticker] = sector
                    successful_fetches += 1
                    consecutive_failures = 0
                    print(f"✅ STORED: {ticker} -> ₹{live_price}")
                    
                    # 💾 SAVE TO DATABASE
                    # Note: unique_tickers was already filtered to only include tickers without prices
                    # So we can save directly without double-checking
                    try:
                        from database_config_supabase import save_stock_price_supabase
                        today = datetime.now().strftime('%Y-%m-%d')
                        
                        # Save live price to historical_prices table
                        print(f"💾 Saving live price for {ticker} (₹{live_price}) with today's date: {today}")
                        save_stock_price_supabase(ticker, today, live_price, 'live_fetch')
                        print(f"✅ Live price saved to historical_prices with date {today}")
                        
                        # Update stock_data table with latest metadata
                        update_stock_data_supabase(
                            ticker=ticker,
                            sector=sector or "Unknown",
                            current_price=live_price  # Maps to live_price column
                        )
                        print(f"💾 Saved {ticker} to database (price + metadata)")
                    except Exception as db_error:
                        print(f"⚠️ Could not save {ticker} to DB: {db_error}")
                        # Continue anyway - at least we have it in session
                else:
                    consecutive_failures += 1
                    print(f"❌ SKIPPED: {ticker} - invalid price or sector")

            # Clear progress indicators
            progress_bar.empty()
            status_text.empty()
            
            # Store in session state
            self.session_state.live_prices = live_prices
            self.session_state.sectors = sectors
            
            # Store the fetch timestamp for cache management
            fetch_key = f'prices_fetched_{user_id}'
            last_fetch_key = f'prices_last_fetch_{user_id}'
            st.session_state[last_fetch_key] = datetime.now().isoformat()

            # Mark that portfolio data should be refreshed since we have new live prices
            portfolio_refresh_key = f'portfolio_needs_refresh_{user_id}'
            st.session_state[portfolio_refresh_key] = True

            # Show results summary
            total_tickers = len(unique_tickers)
            successful_tickers = len(live_prices)
            success_rate = (successful_tickers / total_tickers * 100) if total_tickers > 0 else 0
            
            # Find failed tickers
            failed_tickers = [ticker for ticker in unique_tickers if ticker not in live_prices]

            if successful_tickers > 0:
                st.success(f"✅ Fetched live prices for {successful_tickers}/{total_tickers} tickers ({success_rate:.1f}%)")
                print(f"📊 Live price fetch summary: {successful_tickers}/{total_tickers} successful ({success_rate:.1f}%)")
                
                # Print failed tickers
                if failed_tickers:
                    st.warning(f"⚠️ Failed to fetch prices for {len(failed_tickers)} ticker(s)")
                    print(f"\n❌ Failed to fetch live prices for {len(failed_tickers)} ticker(s):")
                    for ticker in failed_tickers:
                        print(f"   • {ticker}")
                    print("")
                    
                    # Show in expandable section in UI
                    with st.expander(f"🔍 Show {len(failed_tickers)} Failed Ticker(s)"):
                        st.write("**Could not fetch live prices for:**")
                        for idx, ticker in enumerate(failed_tickers, 1):
                            st.write(f"{idx}. `{ticker}`")
                        st.info("💡 These tickers will use historical transaction prices as fallback")
            else:
                st.warning("⚠️ No live prices could be fetched. Portfolio will use historical prices.")
                print("⚠️ No live prices fetched - all tickers failed or were invalid")
                if failed_tickers:
                    print(f"\n❌ All {len(failed_tickers)} tickers failed:")
                    for ticker in failed_tickers:
                        print(f"   • {ticker}")
                    print("")
            
        except Exception as e:
            st.error(f"Error fetching live prices: {e}")
    
    def load_portfolio_data(self, user_id, force_refresh=False):
        """Load and process portfolio data - uses optimized loader if available"""
        from datetime import datetime

        try:
            # Check if optimized loader is available
            if OPTIMIZED_LOADER_AVAILABLE:
                print(f"🚀 Using optimized portfolio loader for user {user_id}")
                
                # Check if portfolio needs refresh (from session state OR parameter)
                portfolio_refresh_key = f'portfolio_needs_refresh_{user_id}'
                force_refresh_session = portfolio_refresh_key in st.session_state and st.session_state[portfolio_refresh_key]
                force_refresh = force_refresh or force_refresh_session  # Combine both
                
                if force_refresh_session:
                    print(f"🔄 Portfolio refresh triggered for user {user_id}")
                    clear_portfolio_cache(user_id)
                    del st.session_state[portfolio_refresh_key]
                
                # Get portfolio data with retry logic for connection errors
                portfolio_data = None
                max_retries = 5  # Increased from 3 to 5 for better reliability
                for attempt in range(max_retries):
                    try:
                        portfolio_data = get_portfolio_fast(user_id, force_refresh=force_refresh)
                        break  # Success, exit retry loop
                    except Exception as e:
                        error_type = type(e).__name__
                        error_msg = str(e)
                        
                        # Check if it's a connection-related error (by type or message)
                        is_connection_error = (
                            'RemoteProtocolError' in error_type or
                            'disconnect' in error_msg.lower() or
                            'timeout' in error_msg.lower() or
                            'connection' in error_msg.lower() or
                            'reset' in error_msg.lower()
                        )
                        
                        if is_connection_error and attempt < max_retries - 1:
                            wait_time = 3 * (2 ** attempt)  # Exponential backoff: 3s, 6s, 12s, 24s, 48s
                            # Use st.warning for visibility in Streamlit
                            st.warning(f"⚠️ Connection error (attempt {attempt + 1}/{max_retries}). Retrying in {wait_time}s...")
                            print(f"⚠️ Connection error loading portfolio (attempt {attempt + 1}/{max_retries})")
                            print(f"   Error: {error_type}: {error_msg}")
                            print(f"   Waiting {wait_time}s before retry...")
                            time.sleep(wait_time)
                            # Add small delay after sleep to ensure connection is fully reset
                            print(f"   Retry attempt {attempt + 2} starting...")
                            continue
                        elif is_connection_error:
                            # Max retries reached
                            error_detail = f'Connection failed after {max_retries} attempts'
                            st.error(f"❌ {error_detail}")
                            print(f"❌ Max retries ({max_retries}) reached for connection error")
                            portfolio_data = {'error': error_detail}
                            break
                        else:
                            # Not a connection error, don't retry
                            error_msg_str = str(e) if str(e) else f"{error_type} (no details)"
                            portfolio_data = {'error': error_msg_str}
                            print(f"❌ Non-connection error in portfolio load: {error_msg_str}")
                            break
                
                # Check for errors: portfolio_data is None, empty, or has 'error' key with a value
                if not portfolio_data or (portfolio_data.get('error') is not None):
                    if portfolio_data and portfolio_data.get('error'):
                        error_detail = portfolio_data.get('error')
                    elif not portfolio_data:
                        error_detail = 'Failed to load portfolio data'
                    else:
                        error_detail = 'Unknown error occurred'
                    
                    # Don't show error here - let the outer exception handler do it
                    # This prevents duplicate error messages
                    raise Exception(error_detail)
                
                # Convert transactions to DataFrame for use by rendering code
                df = pd.DataFrame(portfolio_data['transactions'])
                
                # Debug: Check raw data
                print(f"🔍 DEBUG: Loaded {len(df)} transactions from database")
                if len(df) > 0:
                    print(f"🔍 DEBUG: Columns: {df.columns.tolist()}")
                    print(f"🔍 DEBUG: Sample tickers: {df['ticker'].head(10).tolist()}")
                    print(f"🔍 DEBUG: Sample prices: {df['price'].head(10).tolist()}")
                    print(f"🔍 DEBUG: Sample quantities: {df['quantity'].head(10).tolist()}")
                
                # Add calculated columns for rendering (invested_amount, current_value, unrealized_pnl, pnl_percentage)
                # Identify PMS/AIF tickers for special handling
                from pms_aif_fetcher import is_pms_code, is_aif_code
                
                def detect_pms_aif(ticker):
                    ticker_str = str(ticker).strip()
                    ticker_upper = ticker_str.upper()
                    return (
                        is_pms_code(ticker_str) or
                        is_aif_code(ticker_str) or
                        'PMS' in ticker_upper or
                        'AIF' in ticker_upper or
                        any(keyword in ticker_upper for keyword in [
                            'BUOYANT', 'CARNELIAN', 'JULIUS', 'VALENTIS', 
                            'UNIFI', 'NUVAMA', 'PORTFOLIO MANAGEMENT'
                        ])
                    )
                
                df['is_pms'] = df['ticker'].apply(detect_pms_aif)
                
                # Debug PMS detection
                pms_tickers = df[df['is_pms']]['ticker'].unique()
                if len(pms_tickers) > 0:
                    print(f"🔍 DEBUG: Detected {len(pms_tickers)} PMS/AIF tickers: {pms_tickers}")
                
                # Map live prices - use live_price_db from database first, then session state
                if 'live_price_db' in df.columns:
                    # Use live_price_db from database (already joined from stock_data table)
                    df['live_price'] = df['live_price_db']
                    print(f"🔍 DEBUG: Using live_price_db from database")
                elif hasattr(self.session_state, 'live_prices') and self.session_state.live_prices:
                    df['live_price'] = df['ticker'].map(self.session_state.live_prices)
                    print(f"🔍 DEBUG: Using live_prices from session state")
                else:
                    df['live_price'] = None
                    print(f"⚠️ DEBUG: No live prices available")
                
                # Calculate portfolio metrics
                # Use invested_amount from file if available (for PMS), otherwise calculate
                if 'invested_amount' not in df.columns or df['invested_amount'].isna().all():
                    df['invested_amount'] = df['quantity'] * df['price']
                else:
                    # Fill missing invested_amount values with calculated values
                    df['invested_amount'] = df['invested_amount'].fillna(df['quantity'] * df['price'])
                
                # For PMS: Calculate current value based on NAV percentage change
                # For others: Use live_price or transaction price
                def calculate_current_value_and_pnl(row):
                    invested = row['invested_amount']
                    
                    if row['is_pms']:
                        # PMS: Calculate based on live_price (current value) vs invested_amount
                        ticker = row['ticker']
                        
                        # Debug PMS calculation
                        print(f"🔍 PMS DEBUG: {ticker}")
                        print(f"   - is_pms: {row['is_pms']}")
                        print(f"   - invested: {invested}")
                        print(f"   - quantity: {row['quantity']}")
                        print(f"   - price: {row['price']}")
                        print(f"   - live_price: {row.get('live_price', 'N/A')}")
                        
                        # Check if we have a live_price from PMS fetch
                        if pd.notna(row['live_price']) and row['live_price'] > 0:
                            # Check if live_price is NOT the same as original price
                            # (If they're the same, SEBI fetch likely failed and fell back to transaction price)
                            price_diff_percent = abs((row['live_price'] - row['price']) / row['price'] * 100) if row['price'] > 0 else 0
                            
                            if price_diff_percent < 0.01:  # Less than 0.01% difference
                                # SEBI data not available - use transaction price (shows 0% return)
                                # This is more honest than showing fake estimated returns
                                current_value = invested
                                print(f"⚠️ {ticker}: SEBI data unavailable, using transaction value (0% return)")
                                print(f"   💡 Real-time PMS/AIF NAV data could not be fetched from SEBI")
                                print(f"   💰 Showing invested amount: ₹{invested:,.0f} (no growth calculated)")
                            else:
                                # We have actual NAV data
                                # For PMS, live_price from pms_aif_fetcher is the TOTAL current value (not per unit)
                                # But for safety, check if it needs to be multiplied by quantity
                                
                                # If live_price is much larger than price, it's likely total value already
                                # Otherwise it might be per-unit NAV that needs to be multiplied by quantity
                                if row['live_price'] > row['price'] * 10:  # Heuristic: if live_price >> price, it's total value
                                    current_value = row['live_price']
                                    print(f"✅ {ticker}: Using total value ₹{current_value:,.0f}")
                                else:
                                    # It's per-unit NAV, multiply by quantity
                                    current_value = row['quantity'] * row['live_price']
                                    print(f"✅ {ticker}: Using per-unit NAV × quantity = ₹{current_value:,.0f}")
                        else:
                            # Fallback: Try to calculate from transaction history
                            # Get all transactions for this PMS and calculate based on latest NAV if available
                            try:
                                pms_transactions = df[df['ticker'] == ticker].sort_values('date')
                                
                                # Check if there's NAV change info in any transaction
                                if 'nav_change_percent' in row and pd.notna(row['nav_change_percent']):
                                    pct_change = float(row['nav_change_percent'])
                                    current_value = invested * (1 + pct_change / 100)
                                elif len(pms_transactions) > 1:
                                    # Calculate based on earliest vs latest price
                                    earliest_price = pms_transactions.iloc[0]['price']
                                    latest_price = pms_transactions.iloc[-1]['price']
                                    if earliest_price > 0:
                                        pct_change = ((latest_price - earliest_price) / earliest_price) * 100
                                        current_value = invested * (1 + pct_change / 100)
                                    else:
                                        current_value = invested  # No change
                                else:
                                    # Single transaction, no change data - assume no growth
                                    current_value = invested
                            except Exception as e:
                                print(f"⚠️ PMS calculation error for {ticker}: {e}")
                                current_value = invested  # Fallback to break-even
                        
                        pnl = current_value - invested
                        pnl_pct = (pnl / invested * 100) if invested > 0 else 0
                        
                        return pd.Series({
                            'current_value': current_value,
                            'unrealized_pnl': pnl,
                            'pnl_percentage': pnl_pct
                        })
                    else:
                        # Stocks/MF/ETF: Use live price or fallback to transaction price
                        live_price = row['live_price'] if pd.notna(row['live_price']) else row['price']
                        current_value = row['quantity'] * live_price
                        pnl = current_value - invested
                        pnl_pct = (pnl / invested * 100) if invested > 0 else 0
                        
                        return pd.Series({
                            'current_value': current_value,
                            'unrealized_pnl': pnl,
                            'pnl_percentage': pnl_pct
                        })
                
                # Apply the calculation
                df[['current_value', 'unrealized_pnl', 'pnl_percentage']] = df.apply(calculate_current_value_and_pnl, axis=1)
                
                # Add sector and channel information
                stock_metadata = portfolio_data.get('stock_metadata', {})
                
                # Map sector - use from metadata, or from session state, or default based on type
                def get_sector(ticker, is_pms):
                    ticker_str = str(ticker).strip()
                    ticker_upper = ticker_str.upper()
                    
                    # Priority 1: PMS/AIF
                    if is_pms:
                        if 'AIF' in ticker_upper:
                            return "AIF"
                        else:
                            return "PMS"
                    
                    # Priority 2: Mutual Funds (by ticker pattern)
                    # Exclude BSE codes (6 digits starting with 5, e.g., 500414)
                    is_bse_code = (ticker_str.isdigit() and len(ticker_str) == 6 and ticker_str.startswith('5'))
                    if ((ticker_str.isdigit() and len(ticker_str) >= 5 and len(ticker_str) <= 6 and not is_bse_code) or 
                        ticker_str.startswith('MF_')):
                        return "Mutual Fund"
                    
                    # Priority 3: ETFs (by ticker pattern)
                    if ticker_upper.endswith('BEES') or ticker_upper.endswith('ETF'):
                        return "ETF"
                    
                    # Priority 4: Try stock_metadata from database
                    sector = stock_metadata.get(ticker, {}).get('sector')
                    if sector and sector not in ['Unknown', None, '']:
                        return sector
                    
                    # Priority 5: Try session state (from live fetch)
                    if hasattr(self.session_state, 'sectors') and self.session_state.sectors:
                        sector = self.session_state.sectors.get(ticker)
                        if sector and sector not in ['Unknown', None, '']:
                            return sector
                    
                    # Priority 6: Default to Unknown
                    return "Unknown"
                
                # Handle sector column - use sector_db from database if available
                if 'sector_db' in df.columns and 'sector' not in df.columns:
                    df['sector'] = df['sector_db']
                    print(f"🔍 DEBUG: Using sector_db from database")
                elif 'sector' not in df.columns:
                    df['sector'] = df.apply(lambda row: get_sector(row['ticker'], row['is_pms']), axis=1)
                    print(f"🔍 DEBUG: Calculating sectors from ticker patterns")
                
                # Fill missing sectors with calculated values
                if 'sector' in df.columns:
                    missing_sectors = df['sector'].isna() | (df['sector'] == 'Unknown') | (df['sector'] == '')
                    if missing_sectors.any():
                        print(f"🔍 DEBUG: Filling {missing_sectors.sum()} missing sectors")
                        df.loc[missing_sectors, 'sector'] = df[missing_sectors].apply(
                            lambda row: get_sector(row['ticker'], row['is_pms']), axis=1
                        )
                
                # Ensure channel column exists (from transactions)
                if 'channel' not in df.columns:
                    df['channel'] = 'Unknown'
                
                # Store in session state for use by other parts of the app
                self.session_state.portfolio_data = df  # Store as DataFrame, not dict
                # Optimized loader doesn't return 'summary' and 'holdings' - use .get() with defaults
                self.session_state.portfolio_summary = portfolio_data.get('summary', {})
                self.session_state.portfolio_holdings = portfolio_data.get('holdings', [])
                self.session_state.stock_metadata = portfolio_data.get('stock_metadata', {})
                self.session_state.price_history = portfolio_data.get('price_history', {})
                
                # Set last refresh time
                self.session_state.last_refresh_time = datetime.now()
                
                # Calculate unique holdings count from transactions
                unique_holdings = df.groupby('ticker').size().shape[0] if not df.empty else 0
                print(f"✅ Optimized portfolio loaded: {len(df)} transactions, {unique_holdings} unique holdings")
                return
            
            # Fallback to legacy method if optimized loader not available
            print(f"📊 Using legacy portfolio loader for user {user_id}")
            
            # Check if portfolio needs refresh due to updated live prices
            portfolio_refresh_key = f'portfolio_needs_refresh_{user_id}'
            if portfolio_refresh_key in st.session_state and st.session_state[portfolio_refresh_key]:
                print(f"🔄 Portfolio refresh triggered for user {user_id}")
                del st.session_state[portfolio_refresh_key]
            else:
                print(f"📊 Loading portfolio data for user {user_id}")

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

            # Debug live price mapping
            live_price_count = df['live_price'].notna().sum()
            total_count = len(df)
            print(f"🔍 DEBUG: Live prices mapped: {live_price_count}/{total_count} transactions")
            
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
            df.loc[(df['ticker'].astype(str).str.isdigit() & (df['ticker'].astype(str).str.len() >= 5) & (df['ticker'].astype(str).str.len() <= 6)) | df['ticker'].str.startswith('MF_'), 'sector'] = 'Mutual Fund'
            
            # Calculate portfolio metrics
            df['invested_amount'] = df['quantity'] * df['price']
            df['current_value'] = df['quantity'] * df['live_price'].fillna(df['price'])
            df['unrealized_pnl'] = df['current_value'] - df['invested_amount']
            df['pnl_percentage'] = (df['unrealized_pnl'] / df['invested_amount']) * 100

            # Debug portfolio calculations
            total_invested = df['invested_amount'].sum()
            total_current = df['current_value'].sum()
            total_pnl = df['unrealized_pnl'].sum()
            print(f"🔍 DEBUG: Portfolio totals - Invested: ₹{total_invested:,.2f}, Current: ₹{total_current:,.2f}, P&L: ₹{total_pnl:,.2f}")
            
            # Store processed data
            self.session_state.portfolio_data = df
            
            # Set last refresh time
            self.session_state.last_refresh_time = datetime.now()
            
        except Exception as e:
            # Show error with helpful context
            error_msg = str(e) if str(e) else "Unknown error occurred"
            st.error(f"❌ Error loading portfolio: {error_msg}")
            st.info("💡 Tip: Try logging out and back in, or refresh the page")
            print(f"❌ Portfolio load failed: {error_msg}")
            raise  # Re-raise exception to notify calling function
    
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
            ["🏠 Portfolio Overview", "🎯 Performance Analysis", "💰 P&L Analysis", "📁 Files", "⚙️ Settings"],
            key="main_navigation"
        )
        
        # User info in sidebar
        st.sidebar.markdown("---")
        st.sidebar.markdown(f"**User:** {self.session_state.username}")
        st.sidebar.markdown(f"**Role:** {self.session_state.user_role}")
        st.sidebar.markdown(f"**Login:** {self.session_state.login_time.strftime('%Y-%m-%d %H:%M')}")
        
        # ✅ NEW STRATEGY: Weekly/Historical cache ONLY during file upload
        # - At login: ONLY live prices are fetched (in initialize_portfolio_data)
        # - At file upload: bulk_fetch_and_cache_all_prices handles historical + weekly
        # This prevents duplicate fetches and speeds up login
        
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
                            
                            # 🆕 AUTO BATCH FETCH: Get all prices after file upload (silent)
                            try:
                                print("🤖 Auto-fetching prices via AI (silent batch)...")
                                self.bulk_fetch_and_cache_all_prices(self.session_state.user_id, show_ui=False)
                                print("✅ Silent batch fetch complete!")
                            except Exception as batch_error:
                                print(f"⚠️ AI batch fetch warning: {batch_error}")
                                # Silently skip if batch fetch fails
                            
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
                
                # Upload new documents (PDF, TXT, CSV)
                uploaded_files = st.file_uploader(
                    "Upload new documents",
                    type=['pdf', 'txt', 'csv'],
                    accept_multiple_files=True,
                    key="ai_sidebar_pdf_upload",
                    help="Upload PDFs for analysis, or CSV for transactions" + (" (saved permanently)" if PDF_STORAGE_AVAILABLE else " (temporary)")
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
        if page == "🏠 Portfolio Overview":
            self.render_overview_page()
        elif page == "🎯 Performance Analysis":
            self.render_performance_analysis_page()
        elif page == "💰 P&L Analysis":
            self.render_pnl_analysis_page()
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
        
        # 🆕 AUTO-DETECT MISSING PRICES: If current_value is 0 or NaN, trigger batch fetch
        # ✅ FIX: Check session state properly, not object attribute
        if 'auto_batch_fetch_done' not in st.session_state:
            missing_prices = (
                (df['current_value'].isna()).any() or 
                (df['current_value'] == 0).any()
            )
            
            if missing_prices:
                print("🤖 Detected missing prices, triggering auto batch fetch...")
                try:
                    # Run silently in background
                    self.bulk_fetch_and_cache_all_prices(self.session_state.user_id, show_ui=False)
                    st.session_state.auto_batch_fetch_done = True
                    # Reload portfolio after fetching
                    print("🔄 Reloading portfolio after batch fetch...")
                    self.load_portfolio_data(self.session_state.user_id, force_refresh=True)
                    st.rerun()
                except Exception as e:
                    print(f"⚠️ Auto batch fetch failed: {e}")
                    # Mark as done anyway to avoid infinite loops
                    st.session_state.auto_batch_fetch_done = True
        
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
            if 'unrealized_pnl' in df.columns and 'invested_amount' in df.columns:
                # Aggregate by ticker to get total P&L
                performer_data = df.groupby('ticker').agg({
                    'stock_name': 'first',
                    'invested_amount': 'sum',
                    'unrealized_pnl': 'sum'
                }).reset_index()
                
                # Calculate weighted P&L percentage
                performer_data['pnl_percentage'] = (
                    performer_data['unrealized_pnl'] / performer_data['invested_amount'] * 100
                ).fillna(0)
                
                # Get top 5 performers
                top_performers = performer_data.nlargest(5, 'pnl_percentage')
                
                if not top_performers.empty:
                    # Sort by pnl_percentage ascending for better visual (top at bottom)
                    top_performers = top_performers.sort_values('pnl_percentage', ascending=True)
                    
                    # Ensure ticker is string and create display label
                    top_performers['ticker_str'] = top_performers['ticker'].astype(str)
                    top_performers['display_label'] = top_performers['ticker_str'] + ' - ' + top_performers['stock_name'].str[:20]
                    
                    fig_top = go.Figure()
                    
                    fig_top.add_trace(go.Bar(
                        x=top_performers['pnl_percentage'],
                        y=top_performers['display_label'],
                            orientation='h',
                        marker=dict(
                            color=top_performers['pnl_percentage'],
                            colorscale='Greens',
                            showscale=False
                        ),
                        text=top_performers['pnl_percentage'].round(2),
                        texttemplate='%{text:.2f}%',
                        textposition='outside',
                        hovertemplate='<b>%{y}</b><br>Return: %{x:.2f}%<br>P&L: ₹%{customdata:,.0f}<extra></extra>',
                        customdata=top_performers['unrealized_pnl']
                    ))
                    
                    fig_top.update_layout(
                            title="Top 5 Performers by Return %",
                        xaxis_title="Return %",
                        yaxis_title="",
                        height=300,
                        showlegend=False,
                        margin=dict(l=200)  # More space for labels
                    )
                    
                    st.plotly_chart(fig_top, use_container_width=True, key="top_performers_chart")
            else:
                st.info("Performance data not available")
        
        with col2:
            st.subheader("📉 Underperformers")
            if 'unrealized_pnl' in df.columns and 'invested_amount' in df.columns:
                # Aggregate by ticker to get total P&L
                performer_data = df.groupby('ticker').agg({
                    'stock_name': 'first',
                    'invested_amount': 'sum',
                    'unrealized_pnl': 'sum'
                }).reset_index()
                
                # Calculate weighted P&L percentage
                performer_data['pnl_percentage'] = (
                    performer_data['unrealized_pnl'] / performer_data['invested_amount'] * 100
                ).fillna(0)
                
                # Get bottom 5 performers
                underperformers = performer_data.nsmallest(5, 'pnl_percentage')
                
                if not underperformers.empty:
                    # Sort by pnl_percentage descending for better visual (worst at bottom)
                    underperformers = underperformers.sort_values('pnl_percentage', ascending=False)
                    
                    # Ensure ticker is string and create display label
                    underperformers['ticker_str'] = underperformers['ticker'].astype(str)
                    underperformers['display_label'] = underperformers['ticker_str'] + ' - ' + underperformers['stock_name'].str[:20]
                    
                    fig_bottom = go.Figure()
                    
                    fig_bottom.add_trace(go.Bar(
                        x=underperformers['pnl_percentage'],
                        y=underperformers['display_label'],
                            orientation='h',
                        marker=dict(
                            color=underperformers['pnl_percentage'],
                            colorscale='Reds',
                            showscale=False,
                            reversescale=True  # Darker red for worse performance
                        ),
                        text=underperformers['pnl_percentage'].round(2),
                        texttemplate='%{text:.2f}%',
                        textposition='outside',
                        hovertemplate='<b>%{y}</b><br>Return: %{x:.2f}%<br>P&L: ₹%{customdata:,.0f}<extra></extra>',
                        customdata=underperformers['unrealized_pnl']
                    ))
                    
                    fig_bottom.update_layout(
                            title="Bottom 5 Performers by Return %",
                        xaxis_title="Return %",
                        yaxis_title="",
                        height=300,
                        showlegend=False,
                        margin=dict(l=200)  # More space for labels
                    )
                    
                    st.plotly_chart(fig_bottom, use_container_width=True, key="underperformers_chart")
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
    
    def render_performance_analysis_page(self):
        """Render performance analysis for ALL holdings with sector/channel details"""
        from datetime import datetime, timedelta

        st.header("🎯 Performance Analysis - All Holdings")

        if self.session_state.portfolio_data is None:
            self.show_page_loading_animation("Performance Analysis")
            st.info("💡 **Tip:** If this page doesn't load automatically, use the '🔄 Refresh Portfolio Data' button in Settings.")
            return

        df = self.session_state.portfolio_data
        
        st.markdown("""
        **This page shows performance analysis for ALL holdings in your portfolio**
        - Sector-wise performance breakdown
        - Channel-wise performance analysis
        - Top gainers and losers
        - Overall portfolio metrics
        """)
        
        st.markdown("---")

        # Create tabs for different performance views
        tab1, tab2 = st.tabs(["📊 Overall Performance", "📊 Sector & Channel Analysis"])

        with tab1:
            self.render_overall_portfolio_performance(df)

        with tab2:
            self.render_sector_performance_analysis(df)  # Contains both Sector and Channel tabs inside

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
            import plotly.express as px
            import plotly.graph_objects as go
            
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
            
            # ===== COMPREHENSIVE ANALYSIS SECTION =====
            st.markdown("---")
            st.subheader("📈 Performance Distribution")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Asset allocation by current value
                if 'sector' in stock_and_mf_buys.columns and not stock_and_mf_buys['sector'].isna().all():
                    sector_allocation = stock_and_mf_buys.groupby('sector').agg({
                        'current_value': 'sum'
                    }).reset_index()
                    sector_allocation = sector_allocation.sort_values('current_value', ascending=False)
                    
                    fig_allocation = px.pie(
                        sector_allocation,
                        values='current_value',
                        names='sector',
                        title='1-Year Buy Portfolio Allocation by Sector',
                        hole=0.3
                    )
                    st.plotly_chart(fig_allocation, use_container_width=True, key="1year_sector_allocation_pie")
            
            with col2:
                # P&L Distribution
                holdings_pnl = stock_and_mf_buys.groupby('ticker').agg({
                    'unrealized_pnl': 'sum',
                    'stock_name': 'first'
                }).reset_index()
                holdings_pnl['pnl_type'] = holdings_pnl['unrealized_pnl'].apply(lambda x: 'Profit' if x > 0 else 'Loss' if x < 0 else 'Break-even')
                
                pnl_summary = holdings_pnl.groupby('pnl_type').size().reset_index(name='count')
                
                fig_pnl_dist = px.pie(
                    pnl_summary,
                    values='count',
                    names='pnl_type',
                    title='Holdings P&L Distribution (1-Year)',
                    color='pnl_type',
                    color_discrete_map={'Profit': 'green', 'Loss': 'red', 'Break-even': 'gray'}
                )
                st.plotly_chart(fig_pnl_dist, use_container_width=True, key="1year_pnl_distribution_pie")
            
            st.markdown("---")
            
            # ===== Top and Bottom Performers =====
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("🚀 Top 10 Gainers (1-Year)")
                gainers = stock_and_mf_buys.groupby('ticker').agg({
                    'stock_name': 'first',
                    'unrealized_pnl': 'sum',
                    'invested_amount': 'sum',
                    'current_value': 'sum'
                }).reset_index()
                gainers['pnl_percentage'] = (gainers['unrealized_pnl'] / gainers['invested_amount'] * 100)
                gainers = gainers[gainers['unrealized_pnl'] > 0].nlargest(10, 'pnl_percentage')
                
                if not gainers.empty:
                    for idx, row in gainers.iterrows():
                        with st.container():
                            st.markdown(f"**{row.get('stock_name', row['ticker'])}** ({row['ticker']})")
                            st.markdown(f"💰 P&L: ₹{row['unrealized_pnl']:,.0f} | 📊 {row['pnl_percentage']:.2f}%")
                            st.progress(min(row['pnl_percentage'] / 100, 1.0))
                            st.markdown("---")
                else:
                    st.info("No gainers yet")
            
            with col2:
                st.subheader("📉 Top 10 Losers (1-Year)")
                losers = stock_and_mf_buys.groupby('ticker').agg({
                    'stock_name': 'first',
                    'unrealized_pnl': 'sum',
                    'invested_amount': 'sum',
                    'current_value': 'sum'
                }).reset_index()
                losers['pnl_percentage'] = (losers['unrealized_pnl'] / losers['invested_amount'] * 100)
                losers = losers[losers['unrealized_pnl'] < 0].nsmallest(10, 'pnl_percentage')
                
                if not losers.empty:
                    for idx, row in losers.iterrows():
                        with st.container():
                            st.markdown(f"**{row.get('stock_name', row['ticker'])}** ({row['ticker']})")
                            st.markdown(f"💸 Loss: ₹{row['unrealized_pnl']:,.0f} | 📊 {row['pnl_percentage']:.2f}%")
                            st.progress(min(abs(row['pnl_percentage']) / 100, 1.0))
                            st.markdown("---")
                else:
                    st.info("No losers - Excellent performance!")
            
            st.markdown("---")
            
            # ===== Performance by Sector and Channel =====
            st.subheader("📊 Performance Breakdown")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if 'sector' in stock_and_mf_buys.columns and not stock_and_mf_buys['sector'].isna().all():
                    st.markdown("### 🏢 By Sector")
                    sector_perf = stock_and_mf_buys.groupby('sector').agg({
                        'invested_amount': 'sum',
                        'current_value': 'sum',
                        'unrealized_pnl': 'sum'
                    }).reset_index()
                    sector_perf['pnl_percentage'] = (sector_perf['unrealized_pnl'] / sector_perf['invested_amount'] * 100)
                    sector_perf = sector_perf.sort_values('pnl_percentage', ascending=False)
                    
                    fig_sector_bar = go.Figure()
                    fig_sector_bar.add_trace(go.Bar(
                        x=sector_perf['sector'],
                        y=sector_perf['pnl_percentage'],
                        marker_color=['green' if x >= 0 else 'red' for x in sector_perf['pnl_percentage']],
                        text=sector_perf['pnl_percentage'].round(2),
                        textposition='auto'
                    ))
                    fig_sector_bar.update_layout(
                        title="Sector Performance % (1-Year)",
                        xaxis_title="Sector",
                        yaxis_title="P&L %",
                        height=400
                    )
                    st.plotly_chart(fig_sector_bar, use_container_width=True, key="1year_sector_performance_bar")
            
            with col2:
                if 'channel' in stock_and_mf_buys.columns and not stock_and_mf_buys['channel'].isna().all():
                    st.markdown("### 📡 By Channel")
                    channel_perf = stock_and_mf_buys.groupby('channel').agg({
                        'invested_amount': 'sum',
                        'current_value': 'sum',
                        'unrealized_pnl': 'sum'
                    }).reset_index()
                    channel_perf['pnl_percentage'] = (channel_perf['unrealized_pnl'] / channel_perf['invested_amount'] * 100)
                    channel_perf = channel_perf.sort_values('pnl_percentage', ascending=False)
                    
                    fig_channel_bar = go.Figure()
                    fig_channel_bar.add_trace(go.Bar(
                        x=channel_perf['channel'],
                        y=channel_perf['pnl_percentage'],
                        marker_color=['green' if x >= 0 else 'red' for x in channel_perf['pnl_percentage']],
                        text=channel_perf['pnl_percentage'].round(2),
                        textposition='auto'
                    ))
                    fig_channel_bar.update_layout(
                        title="Channel Performance % (1-Year)",
                        xaxis_title="Channel",
                        yaxis_title="P&L %",
                        height=400
                    )
                    st.plotly_chart(fig_channel_bar, use_container_width=True, key="1year_channel_performance_bar")
            
            st.markdown("---")
            
            # ===== Portfolio Statistics =====
            st.subheader("📊 Portfolio Statistics (1-Year Buys)")
            
            # Calculate statistics
            total_holdings = len(stock_performance)
            winning_holdings = len(stock_performance[stock_performance['unrealized_pnl'] > 0])
            losing_holdings = len(stock_performance[stock_performance['unrealized_pnl'] < 0])
            win_rate = (winning_holdings / total_holdings * 100) if total_holdings > 0 else 0
            avg_return = stock_performance['pnl_percentage'].mean()
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Avg Return per Holding", f"{avg_return:.2f}%")
            with col2:
                st.metric("Win Rate", f"{win_rate:.1f}%")
            with col3:
                if 'sector' in stock_and_mf_buys.columns:
                    num_sectors = stock_and_mf_buys['sector'].nunique()
                    st.metric("Sectors", f"{num_sectors}")
            with col4:
                if 'channel' in stock_and_mf_buys.columns:
                    num_channels = stock_and_mf_buys['channel'].nunique()
                    st.metric("Channels", f"{num_channels}")
            
            st.markdown("---")

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

            # Sector and Channel Analysis with Interactive Drill-Down
            st.markdown("---")
            st.subheader("📊 Sector & Channel Drill-Down Analysis (1-Year Buy Transactions)")

            # Create tabs for Sector and Channel analysis
            tab1, tab2 = st.tabs(["🏭 By Sector", "📡 By Channel"])

            with tab1:
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
                    sector_performance = sector_performance.sort_values('pnl_percentage', ascending=False)

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
                        title="Sector Performance (1-Year Buy Transactions)",
                        xaxis_title="Sector",
                        yaxis_title="P&L Percentage (%)",
                        height=400
                    )

                    st.plotly_chart(fig_sector, use_container_width=True, key="1year_sector_chart", config={'displayModeBar': True})
                    
                    st.markdown("---")
                    st.markdown("### 🔍 Drill-Down by Sector (Multiple Selections Allowed)")
                    
                    # Sector multiselect
                    sector_options = sector_performance['sector'].tolist()
                    selected_sectors_1y = st.multiselect(
                        "Select Sector(s) to view holdings (multiple selections allowed):",
                        options=sector_options,
                        default=[],
                        key="1year_sector_multiselect"
                    )
                    
                    if not selected_sectors_1y or len(selected_sectors_1y) == 0:
                        # Show all sectors summary
                        st.markdown("#### 📊 All Sectors Summary")
                    sector_table_data = []
                    for _, row in sector_performance.iterrows():
                        sector = row['sector']
                        sector_stocks = stock_and_mf_buys[stock_and_mf_buys['sector'] == sector]
                        sector_count = len(sector_stocks['ticker'].unique())

                        sector_table_data.append({
                            'Sector': sector,
                            'Holdings': sector_count,
                                'Invested (₹)': f"₹{row['invested_amount']:,.0f}",
                                'Current Value (₹)': f"₹{row['current_value']:,.0f}",
                                'P&L (₹)': f"₹{row['unrealized_pnl']:,.0f}",
                                'P&L %': f"{row['pnl_percentage']:.2f}%"
                        })

                    sector_df = pd.DataFrame(sector_table_data)
                    st.dataframe(sector_df, use_container_width=True, hide_index=True)
                    
                else:
                        # Show holdings in selected sectors
                        sector_holdings = stock_and_mf_buys[stock_and_mf_buys['sector'].isin(selected_sectors_1y)]
                        
                        if not sector_holdings.empty:
                            sectors_str = ", ".join(selected_sectors_1y)
                            st.markdown(f"#### 📈 Holdings in {sectors_str}")
                            
                            # Show sector-by-sector breakdown if multiple sectors selected
                            if len(selected_sectors_1y) > 1:
                                st.markdown("### 📊 Performance Comparison by Selected Sectors")
                                sector_breakdown = sector_holdings.groupby('sector').agg({
                                    'invested_amount': 'sum',
                                    'current_value': 'sum',
                                    'unrealized_pnl': 'sum'
                                }).reset_index()
                                sector_breakdown['pnl_percentage'] = (
                                    sector_breakdown['unrealized_pnl'] / sector_breakdown['invested_amount'] * 100
                                )
                                sector_breakdown = sector_breakdown.sort_values('pnl_percentage', ascending=False)
                                
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.dataframe(
                                        sector_breakdown.style.format({
                                            'invested_amount': '₹{:,.0f}',
                                            'current_value': '₹{:,.0f}',
                                            'unrealized_pnl': '₹{:,.0f}',
                                            'pnl_percentage': '{:.2f}%'
                                        }),
                                        use_container_width=True,
                                        hide_index=True
                                    )

                                with col2:
                                    # Bar chart comparing sectors
                                    fig_sector_compare = px.bar(
                                        sector_breakdown,
                                        x='sector',
                                        y='pnl_percentage',
                                        title='Sector P&L Comparison (1-Year Buys)',
                                        color='pnl_percentage',
                                        color_continuous_scale='RdYlGn',
                                        text='pnl_percentage'
                                    )
                                fig_sector_compare.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
                                fig_sector_compare.update_layout(height=300)
                                st.plotly_chart(fig_sector_compare, use_container_width=True, key="1year_multi_sector_compare")
                                
                            st.markdown("---")
                            
                            # Aggregate by ticker
                            holdings_in_sector = sector_holdings.groupby('ticker').agg({
                                'stock_name': 'first',
                                'invested_amount': 'sum',
                                'current_value': 'sum',
                                'unrealized_pnl': 'sum'
                            }).reset_index()
                            
                            holdings_in_sector['pnl_percentage'] = (
                                holdings_in_sector['unrealized_pnl'] / holdings_in_sector['invested_amount'] * 100
                            )
                            holdings_in_sector = holdings_in_sector.sort_values('pnl_percentage', ascending=False)
                            
                            st.markdown(f"#### 📋 {len(holdings_in_sector)} Individual Holding(s)")
                            
                            # Display holdings table
                            st.dataframe(
                                holdings_in_sector[[
                                    'ticker', 'stock_name', 'invested_amount', 
                                    'current_value', 'unrealized_pnl', 'pnl_percentage'
                                ]].rename(columns={
                                    'ticker': 'Ticker',
                                    'stock_name': 'Name',
                                    'invested_amount': 'Invested (₹)',
                                    'current_value': 'Current Value (₹)',
                                    'unrealized_pnl': 'P&L (₹)',
                                    'pnl_percentage': 'P&L %'
                                }).style.format({
                                    'Invested (₹)': '₹{:,.0f}',
                                    'Current Value (₹)': '₹{:,.0f}',
                                    'P&L (₹)': '₹{:,.0f}',
                                    'P&L %': '{:.2f}%'
                                }),
                                use_container_width=True,
                                hide_index=True
                            )
                            
                            # Multi-select for weekly comparison
                            st.markdown("---")
                            st.markdown("#### 📊 Compare Holdings in This Sector")
                            
                            selected_holdings_sector = st.multiselect(
                                "Select holding(s) to view weekly trends:",
                                options=holdings_in_sector['ticker'].tolist(),
                                default=[holdings_in_sector['ticker'].tolist()[0]] if len(holdings_in_sector) > 0 else [],
                                format_func=lambda x: f"{x} - {holdings_in_sector[holdings_in_sector['ticker']==x]['stock_name'].iloc[0] if not holdings_in_sector[holdings_in_sector['ticker']==x].empty else x}",
                                key="1year_sector_holdings_multi"
                            )
                            
                            if selected_holdings_sector:
                                self.render_weekly_values_multi(
                                    selected_holdings_sector, 
                                    self.session_state.user_id, 
                                    context="1year_sector"
                                )
            
            with tab2:
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
                    channel_performance = channel_performance.sort_values('pnl_percentage', ascending=False)

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
                        title="Channel Performance (1-Year Buy Transactions)",
                        xaxis_title="Channel",
                        yaxis_title="P&L Percentage (%)",
                        height=400
                    )

                    st.plotly_chart(fig_channel, use_container_width=True, key="1year_channel_chart", config={'displayModeBar': True})
                    
                    st.markdown("---")
                    st.markdown("### 🔍 Drill-Down by Channel (Multiple Selections Allowed)")
                    
                    # Channel multiselect
                    channel_options = channel_performance['channel'].tolist()
                    selected_channels_1y = st.multiselect(
                        "Select Channel(s) to view holdings (multiple selections allowed):",
                        options=channel_options,
                        default=[],
                        key="1year_channel_multiselect"
                    )
                    
                    if not selected_channels_1y or len(selected_channels_1y) == 0:
                        # Show all channels summary
                        st.markdown("#### 📊 All Channels Summary")
                    channel_table_data = []
                    for _, row in channel_performance.iterrows():
                        channel = row['channel']
                        channel_stocks = stock_and_mf_buys[stock_and_mf_buys['channel'] == channel]
                        channel_count = len(channel_stocks['ticker'].unique())

                        channel_table_data.append({
                            'Channel': channel,
                            'Holdings': channel_count,
                                'Invested (₹)': f"₹{row['invested_amount']:,.0f}",
                                'Current Value (₹)': f"₹{row['current_value']:,.0f}",
                                'P&L (₹)': f"₹{row['unrealized_pnl']:,.0f}",
                                'P&L %': f"{row['pnl_percentage']:.2f}%"
                        })

                    channel_df = pd.DataFrame(channel_table_data)
                    st.dataframe(channel_df, use_container_width=True, hide_index=True)
                    
                else:
                        # Show holdings in selected channels
                        channel_holdings = stock_and_mf_buys[stock_and_mf_buys['channel'].isin(selected_channels_1y)]
                        
                        if not channel_holdings.empty:
                            channels_str = ", ".join(selected_channels_1y)
                            st.markdown(f"#### 📈 Holdings in {channels_str}")
                            
                            # Show channel-by-channel breakdown if multiple channels selected
                            if len(selected_channels_1y) > 1:
                                st.markdown("### 📊 Performance Comparison by Selected Channels")
                                channel_breakdown = channel_holdings.groupby('channel').agg({
                                    'invested_amount': 'sum',
                                    'current_value': 'sum',
                                    'unrealized_pnl': 'sum'
                                }).reset_index()
                                channel_breakdown['pnl_percentage'] = (
                                    channel_breakdown['unrealized_pnl'] / channel_breakdown['invested_amount'] * 100
                                )
                                channel_breakdown = channel_breakdown.sort_values('pnl_percentage', ascending=False)
                                
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.dataframe(
                                        channel_breakdown.style.format({
                                            'invested_amount': '₹{:,.0f}',
                                            'current_value': '₹{:,.0f}',
                                            'unrealized_pnl': '₹{:,.0f}',
                                            'pnl_percentage': '{:.2f}%'
                                        }),
                                        use_container_width=True,
                                        hide_index=True
                                    )
                                
                                with col2:
                                    # Bar chart comparing channels
                                    fig_channel_compare = px.bar(
                                        channel_breakdown,
                                        x='channel',
                                        y='pnl_percentage',
                                        title='Channel P&L Comparison (1-Year Buys)',
                                        color='pnl_percentage',
                                        color_continuous_scale='RdYlGn',
                                        text='pnl_percentage'
                                    )
                                    fig_channel_compare.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
                                    fig_channel_compare.update_layout(height=300)
                                    st.plotly_chart(fig_channel_compare, use_container_width=True, key="1year_multi_channel_compare")
                                
                                st.markdown("---")
                            
                            # Aggregate by ticker
                            holdings_in_channel = channel_holdings.groupby('ticker').agg({
                                'stock_name': 'first',
                                'sector': 'first',
                                'invested_amount': 'sum',
                                'current_value': 'sum',
                                'unrealized_pnl': 'sum'
                            }).reset_index()
                            
                            holdings_in_channel['pnl_percentage'] = (
                                holdings_in_channel['unrealized_pnl'] / holdings_in_channel['invested_amount'] * 100
                            )
                            holdings_in_channel = holdings_in_channel.sort_values('pnl_percentage', ascending=False)
                            
                            st.markdown(f"#### 📋 {len(holdings_in_channel)} Individual Holding(s)")
                            
                            # Display holdings table
                            st.dataframe(
                                holdings_in_channel[[
                                    'ticker', 'stock_name', 'sector', 'invested_amount', 
                                    'current_value', 'unrealized_pnl', 'pnl_percentage'
                                ]].rename(columns={
                                    'ticker': 'Ticker',
                                    'stock_name': 'Name',
                                    'sector': 'Sector',
                                    'invested_amount': 'Invested (₹)',
                                    'current_value': 'Current Value (₹)',
                                    'unrealized_pnl': 'P&L (₹)',
                                    'pnl_percentage': 'P&L %'
                                }).style.format({
                                    'Invested (₹)': '₹{:,.0f}',
                                    'Current Value (₹)': '₹{:,.0f}',
                                    'P&L (₹)': '₹{:,.0f}',
                                    'P&L %': '{:.2f}%'
                                }),
                                use_container_width=True,
                                hide_index=True
                            )
                            
                            # Multi-select for weekly comparison
                            st.markdown("---")
                            st.markdown("#### 📊 Compare Holdings in This Channel")
                            
                            selected_holdings_channel = st.multiselect(
                                "Select holding(s) to view weekly trends:",
                                options=holdings_in_channel['ticker'].tolist(),
                                default=[holdings_in_channel['ticker'].tolist()[0]] if len(holdings_in_channel) > 0 else [],
                                format_func=lambda x: f"{x} - {holdings_in_channel[holdings_in_channel['ticker']==x]['stock_name'].iloc[0] if not holdings_in_channel[holdings_in_channel['ticker']==x].empty else x}",
                                key="1year_channel_holdings_multi"
                            )
                            
                            if selected_holdings_channel:
                                self.render_weekly_values_multi(
                                    selected_holdings_channel, 
                                    self.session_state.user_id, 
                                    context="1year_channel"
                                )

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
            
            # ===== NEW: Holdings Multi-Select with Weekly Values Comparison =====
            st.markdown("---")
            st.subheader("📈 Compare 1-Year Buy Holdings - Weekly Trends")
            
            # Get list of unique holdings bought in last year
            holdings_list = stock_performance['ticker'].tolist()
            
            if holdings_list:
                selected_holdings = st.multiselect(
                    "Select holding(s) to compare (multiple selections allowed):",
                    options=holdings_list,
                    default=[holdings_list[0]] if holdings_list else [],
                    format_func=lambda x: f"{x} - {stock_and_mf_buys[stock_and_mf_buys['ticker']==x]['stock_name'].iloc[0]}" if not stock_and_mf_buys[stock_and_mf_buys['ticker']==x].empty else x,
                    key="oneyear_holding_weekly_multi_dropdown"
                )
                
                if selected_holdings and len(selected_holdings) > 0:
                    # Show aggregate stats for selected holdings
                    selected_data = stock_performance[stock_performance['ticker'].isin(selected_holdings)]
                    total_invested = selected_data['invested_amount'].sum()
                    total_current = selected_data['current_value'].sum()
                    total_pnl = selected_data['unrealized_pnl'].sum()
                    avg_pnl_pct = selected_data['pnl_percentage'].mean()
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Invested", f"₹{total_invested:,.0f}")
                    with col2:
                        st.metric("Total Current Value", f"₹{total_current:,.0f}")
                    with col3:
                        st.metric("Total P&L", f"₹{total_pnl:,.0f}")
                    with col4:
                        st.metric("Avg P&L %", f"{avg_pnl_pct:.2f}%", delta=f"{avg_pnl_pct:.2f}%")
                    
                    # Render weekly values comparison
                    self.render_weekly_values_multi(selected_holdings, self.session_state.user_id, context="1year_buy")
        else:
            st.info("No stock buy transactions found in the last 1 year")

    def render_overall_portfolio_performance(self, df):
            """Render comprehensive overall portfolio performance metrics and analysis"""
            import plotly.express as px
            import plotly.graph_objects as go
            from datetime import datetime, timedelta
            
            st.subheader("📊 Overall Portfolio Performance")
            
            try:
                # Calculate overall metrics
                total_invested = df['invested_amount'].sum()
                total_current = df['current_value'].sum()
                total_pnl = df['unrealized_pnl'].sum()
                total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0
                
                # Key metrics row
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("💰 Total Invested", f"₹{total_invested:,.0f}")

                with col2:
                    st.metric("📈 Current Value", f"₹{total_current:,.0f}")
                
                with col3:
                    pnl_color = "normal" if total_pnl >= 0 else "inverse"
                    st.metric("💵 Total P&L", f"₹{total_pnl:,.0f}", delta=f"{total_pnl_pct:.2f}%", delta_color=pnl_color)
                
                with col4:
                    num_holdings = len(df['ticker'].unique())
                    st.metric("📊 Total Holdings", f"{num_holdings}")
                
                st.markdown("---")
                
                # ===== Performance Charts =====
                st.subheader("📈 Performance Distribution")
                
                col1, col2 = st.columns(2)

                with col1:
                    # Asset allocation by current value
                    if 'sector' in df.columns and not df['sector'].isna().all():
                        sector_allocation = df.groupby('sector').agg({
                            'current_value': 'sum'
                        }).reset_index()
                        sector_allocation = sector_allocation.sort_values('current_value', ascending=False)
                        
                        import plotly.express as px
                        fig_allocation = px.pie(
                            sector_allocation,
                            values='current_value',
                            names='sector',
                            title='Portfolio Allocation by Sector',
                            hole=0.3
                        )
                        st.plotly_chart(fig_allocation, use_container_width=True, key="overall_sector_allocation_pie")

                with col2:
                    # P&L Distribution
                    holdings_pnl = df.groupby('ticker').agg({
                        'unrealized_pnl': 'sum',
                        'stock_name': 'first'
                    }).reset_index()
                    holdings_pnl['pnl_type'] = holdings_pnl['unrealized_pnl'].apply(lambda x: 'Profit' if x > 0 else 'Loss' if x < 0 else 'Break-even')
                    
                    pnl_summary = holdings_pnl.groupby('pnl_type').size().reset_index(name='count')
                    
                    fig_pnl_dist = px.pie(
                        pnl_summary,
                        values='count',
                        names='pnl_type',
                        title='Holdings P&L Distribution',
                        color='pnl_type',
                        color_discrete_map={'Profit': 'green', 'Loss': 'red', 'Break-even': 'gray'}
                    )
                    st.plotly_chart(fig_pnl_dist, use_container_width=True, key="overall_pnl_distribution_pie")
                
                st.markdown("---")
                
                # ===== Top and Bottom Performers =====
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("🚀 Top 10 Gainers")
                    gainers = df.groupby('ticker').agg({
                        'stock_name': 'first',
                        'unrealized_pnl': 'sum',
                        'invested_amount': 'sum',
                        'current_value': 'sum'
                    }).reset_index()
                    gainers['pnl_percentage'] = (gainers['unrealized_pnl'] / gainers['invested_amount'] * 100)
                    gainers = gainers[gainers['unrealized_pnl'] > 0].nlargest(10, 'pnl_percentage')
                    
                    if not gainers.empty:
                        for idx, row in gainers.iterrows():
                            with st.container():
                                st.markdown(f"**{row.get('stock_name', row['ticker'])}** ({row['ticker']})")
                                st.markdown(f"💰 P&L: ₹{row['unrealized_pnl']:,.0f} | 📊 {row['pnl_percentage']:.2f}%")
                                st.progress(min(row['pnl_percentage'] / 100, 1.0))
                                st.markdown("---")
                    else:
                            st.info("No gainers yet")

                with col2:
                    st.subheader("📉 Top 10 Losers")
                    losers = df.groupby('ticker').agg({
                        'stock_name': 'first',
                        'unrealized_pnl': 'sum',
                        'invested_amount': 'sum',
                        'current_value': 'sum'
                    }).reset_index()
                    losers['pnl_percentage'] = (losers['unrealized_pnl'] / losers['invested_amount'] * 100)
                    losers = losers[losers['unrealized_pnl'] < 0].nsmallest(10, 'pnl_percentage')
                    
                    if not losers.empty:
                        for idx, row in losers.iterrows():
                            with st.container():
                                st.markdown(f"**{row.get('stock_name', row['ticker'])}** ({row['ticker']})")
                                st.markdown(f"💸 Loss: ₹{row['unrealized_pnl']:,.0f} | 📊 {row['pnl_percentage']:.2f}%")
                                st.progress(min(abs(row['pnl_percentage']) / 100, 1.0))
                                st.markdown("---")
                    else:
                        st.info("No losers - Excellent performance!")
                
                st.markdown("---")
                
                # ===== Performance by Sector and Channel =====
                st.subheader("📊 Performance Breakdown")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if 'sector' in df.columns and not df['sector'].isna().all():
                        st.markdown("### 🏢 By Sector")
                        sector_perf = df.groupby('sector').agg({
                            'invested_amount': 'sum',
                            'current_value': 'sum',
                            'unrealized_pnl': 'sum'
                        }).reset_index()
                        sector_perf['pnl_percentage'] = (sector_perf['unrealized_pnl'] / sector_perf['invested_amount'] * 100)
                        sector_perf = sector_perf.sort_values('pnl_percentage', ascending=False)
                        
                        fig_sector_bar = go.Figure()
                        fig_sector_bar.add_trace(go.Bar(
                            x=sector_perf['sector'],
                            y=sector_perf['pnl_percentage'],
                            marker_color=['green' if x >= 0 else 'red' for x in sector_perf['pnl_percentage']],
                            text=sector_perf['pnl_percentage'].round(2),
                            textposition='auto'
                        ))
                        fig_sector_bar.update_layout(
                            title="Sector Performance (%)",
                            xaxis_title="Sector",
                            yaxis_title="P&L %",
                            height=400
                        )
                        st.plotly_chart(fig_sector_bar, use_container_width=True, key="overall_sector_performance_bar")
                
                with col2:
                    if 'channel' in df.columns and not df['channel'].isna().all():
                        st.markdown("### 📡 By Channel")
                        channel_perf = df.groupby('channel').agg({
                            'invested_amount': 'sum',
                            'current_value': 'sum',
                            'unrealized_pnl': 'sum'
                        }).reset_index()
                        channel_perf['pnl_percentage'] = (channel_perf['unrealized_pnl'] / channel_perf['invested_amount'] * 100)
                        channel_perf = channel_perf.sort_values('pnl_percentage', ascending=False)
                        
                        fig_channel_bar = go.Figure()
                        fig_channel_bar.add_trace(go.Bar(
                            x=channel_perf['channel'],
                            y=channel_perf['pnl_percentage'],
                            marker_color=['green' if x >= 0 else 'red' for x in channel_perf['pnl_percentage']],
                            text=channel_perf['pnl_percentage'].round(2),
                            textposition='auto'
                        ))
                        fig_channel_bar.update_layout(
                            title="Channel Performance (%)",
                            xaxis_title="Channel",
                            yaxis_title="P&L %",
                            height=400
                        )
                        st.plotly_chart(fig_channel_bar, use_container_width=True, key="overall_channel_performance_bar")
                
                st.markdown("---")
                
                # ===== Portfolio Statistics =====
                st.subheader("📊 Portfolio Statistics")
                
                col1, col2, col3, col4 = st.columns(4)
            
                with col1:
                    avg_pnl_pct = df.groupby('ticker')['pnl_percentage'].first().mean()
                    st.metric("📈 Avg Return per Holding", f"{avg_pnl_pct:.2f}%")
            
                with col2:
                    winning_holdings = len(df[df['unrealized_pnl'] > 0].groupby('ticker'))
                    total_holdings_count = len(df.groupby('ticker'))
                    win_rate = (winning_holdings / total_holdings_count * 100) if total_holdings_count > 0 else 0
                    st.metric("🎯 Win Rate", f"{win_rate:.1f}%", delta=f"{winning_holdings}/{total_holdings_count}")
            
                with col3:
                    if 'sector' in df.columns:
                        sector_count = len(df['sector'].dropna().unique())
                        st.metric("🏢 Sectors", f"{sector_count}")
                    else:
                        st.metric("🏢 Sectors", "N/A")
            
                with col4:
                    if 'channel' in df.columns:
                        channel_count = len(df['channel'].dropna().unique())
                        st.metric("📡 Channels", f"{channel_count}")
                    else:
                        st.metric("📡 Channels", "N/A")
            
                st.markdown("---")
                
                # ===== Holdings Multi-Select with Weekly Values Comparison =====
                st.subheader("📈 Compare Holdings - Weekly Price Charts")
                
                # Get all unique holdings
                all_holdings = df.groupby('ticker').agg({
                    'stock_name': 'first',
                    'unrealized_pnl': 'sum',
                    'pnl_percentage': 'first',
                    'current_value': 'sum'
                }).reset_index().sort_values('pnl_percentage', ascending=False)
                
                if not all_holdings.empty:
                    # Add "Select All" option
                    selected_holdings = st.multiselect(
                        "Select holding(s) to compare (multiple selections allowed):",
                        options=all_holdings['ticker'].tolist(),
                        default=[all_holdings['ticker'].tolist()[0]] if len(all_holdings) > 0 else [],
                        format_func=lambda x: f"{x} - {all_holdings[all_holdings['ticker']==x]['stock_name'].iloc[0]} ({all_holdings[all_holdings['ticker']==x]['pnl_percentage'].iloc[0]:.2f}%)" if not all_holdings[all_holdings['ticker']==x].empty else x,
                        key="overall_holding_weekly_multi_dropdown"
                    )
                    
                    if selected_holdings and len(selected_holdings) > 0:
                        # Show aggregate stats for selected holdings
                        selected_holdings_data = all_holdings[all_holdings['ticker'].isin(selected_holdings)]
                        total_value = selected_holdings_data['current_value'].sum()
                        total_pnl = selected_holdings_data['unrealized_pnl'].sum()
                        avg_pnl_pct = selected_holdings_data['pnl_percentage'].mean()
                        
                        st.markdown(f"**Selected Holdings:** {len(selected_holdings)} | **Total Value:** ₹{total_value:,.0f} | **Total P&L:** ₹{total_pnl:,.0f} | **Avg P&L:** {avg_pnl_pct:.2f}%")
                        
                        # Render weekly values comparison
                        self.render_weekly_values_multi(selected_holdings, self.session_state.user_id, context="overall_performance")
                
                st.markdown("---")
                
                # ===== Detailed Holdings Table =====
                st.subheader("📋 All Holdings Performance Table")
                
                # Create comprehensive holdings table
                holdings_table = df.groupby('ticker').agg({
                    'stock_name': 'first',
                    'sector': 'first',
                    'channel': 'first',
                    'quantity': 'sum',
                    'invested_amount': 'sum',
                    'current_value': 'sum',
                    'unrealized_pnl': 'sum',
                    'pnl_percentage': 'first'
                }).reset_index().sort_values('pnl_percentage', ascending=False)
                
                # Format for display
                st.dataframe(
                    holdings_table.style.format({
                        'quantity': '{:,.2f}',
                        'invested_amount': '₹{:,.0f}',
                        'current_value': '₹{:,.0f}',
                        'unrealized_pnl': '₹{:,.0f}',
                        'pnl_percentage': '{:.2f}%'
                    }),
                    use_container_width=True,
                    height=400
                )
            
            except Exception as e:
                st.error(f"Error in overall performance: {e}")
                import traceback
                st.error(traceback.format_exc())   
    
    def render_sector_performance_analysis(self, df):
        """Render sector-wise performance breakdown with interactive drill-down"""
        st.subheader("📊 Performance Analysis - Sector & Channel Drill-Down")
        
        # Create tabs for Sector and Channel analysis  
        tab1, tab2 = st.tabs(["🏢 By Sector", "📡 By Channel"])
        
        with tab1:
            st.subheader("🏢 Sector-Wise Performance")
            
            try:
                # Debug: Check what's in the sector column
                print(f"🔍 DEBUG: df.columns = {df.columns.tolist()}")
                
                # Check for sector column - try multiple variations
                sector_col = None
                if 'sector' in df.columns and not df['sector'].isna().all():
                    sector_col = 'sector'
                elif 'sector_db' in df.columns and not df['sector_db'].isna().all():
                    sector_col = 'sector_db'
                    # Copy sector_db to sector for consistency
                    df['sector'] = df['sector_db']
                    sector_col = 'sector'
                
                if sector_col:
                    print(f"🔍 DEBUG: Using sector column: {sector_col}")
                    print(f"🔍 DEBUG: df['{sector_col}'].unique() = {df[sector_col].unique()}")
                    print(f"🔍 DEBUG: df['{sector_col}'].value_counts() = {df[sector_col].value_counts()}")
                    print(f"🔍 DEBUG: df['{sector_col}'].isna().sum() = {df[sector_col].isna().sum()}")
                    
                if not sector_col or df['sector'].isna().all():
                    st.warning("⚠️ Sector information not available in portfolio data")
                    st.info("💡 Sectors are automatically fetched when prices are loaded. Reload data to populate sectors.")
                    # Show what we have for debugging
                    with st.expander("🔍 Debug: Show available columns"):
                        st.json(df.columns.tolist())
                    return
                
                # Check if all sectors are Unknown
                valid_sectors = df[~df['sector'].isin(['Unknown', '', None])]['sector'].dropna()
                if len(valid_sectors) == 0:
                    st.warning("⚠️ No sector information available - all holdings show as 'Unknown'")
                    st.info("💡 Please use the '🔄 Refresh Portfolio Data' button in Settings to fetch sector information.")
                    
                    # Show breakdown by ticker instead
                    st.subheader("📊 Holdings Breakdown (Without Sectors)")
                    holdings_summary = df.groupby('ticker').agg({
                        'stock_name': 'first',
                        'invested_amount': 'sum',
                        'current_value': 'sum',
                        'unrealized_pnl': 'sum'
                    }).reset_index()
                    holdings_summary['pnl_percentage'] = (holdings_summary['unrealized_pnl'] / holdings_summary['invested_amount'] * 100)
                    holdings_summary = holdings_summary.sort_values('pnl_percentage', ascending=False)
                    
                    st.dataframe(
                        holdings_summary.style.format({
                            'invested_amount': '₹{:,.0f}',
                            'current_value': '₹{:,.0f}',
                            'unrealized_pnl': '₹{:,.0f}',
                            'pnl_percentage': '{:.2f}%'
                        }),
                        use_container_width=True
                    )
                    return
                
                # Group by sector (exclude Unknown if there are other sectors)
                sector_data = df.groupby('sector').agg({
                    'invested_amount': 'sum',
                    'current_value': 'sum',
                    'unrealized_pnl': 'sum'
                }).reset_index()
                
                # Filter out 'Unknown' if we have other sectors
                if len(sector_data) > 1 and 'Unknown' in sector_data['sector'].values:
                    print(f"🔍 DEBUG: Filtering out 'Unknown' sector, keeping {len(sector_data)-1} known sectors")
                    sector_data = sector_data[sector_data['sector'] != 'Unknown']
                
                sector_data['pnl_percentage'] = (sector_data['unrealized_pnl'] / sector_data['invested_amount'] * 100)
                sector_data = sector_data.sort_values('pnl_percentage', ascending=False)
                
                print(f"🔍 DEBUG: Final sector_data:\n{sector_data}")
                
                # Display sector performance table
                st.dataframe(
                    sector_data.style.format({
                        'invested_amount': '₹{:,.0f}',
                        'current_value': '₹{:,.0f}',
                        'unrealized_pnl': '₹{:,.0f}',
                        'pnl_percentage': '{:.2f}%'
                    }),
                    use_container_width=True
                )
                
                # Sector pie chart
                import plotly.express as px
                fig = px.pie(
                    sector_data,
                    values='current_value',
                    names='sector',
                    title='Portfolio Allocation by Sector'
                )
                st.plotly_chart(fig, use_container_width=True, key="sector_analysis_pie")
                
                # ===== NEW: Sector Multi-Select Filter =====
                st.markdown("---")
                st.subheader("🔍 Drill-Down by Sector (Multiple Selections Allowed)")
                
                # Sector selection multiselect
                sector_list = sorted(df['sector'].dropna().unique().tolist())
                selected_sectors = st.multiselect(
                    "Select Sector(s) to view holdings (multiple selections allowed):",
                    options=sector_list,
                    default=[],
                    key="sector_filter_multiselect"
                )
                
                if selected_sectors and len(selected_sectors) > 0:
                    # Filter holdings by selected sectors
                    sector_holdings = df[df['sector'].isin(selected_sectors)].copy()
                    
                    if not sector_holdings.empty:
                        sectors_str = ", ".join(selected_sectors)
                        st.info(f"📊 Showing {len(sector_holdings)} holding(s) in **{sectors_str}**")
                            
                            # Show sector-by-sector breakdown if multiple sectors selected
                        if len(selected_sectors) > 1:
                                st.markdown("### 📊 Performance by Selected Sectors")
                                sector_breakdown = sector_holdings.groupby('sector').agg({
                                    'invested_amount': 'sum',
                                    'current_value': 'sum',
                                    'unrealized_pnl': 'sum'
                                }).reset_index()
                                sector_breakdown['pnl_percentage'] = (
                                    sector_breakdown['unrealized_pnl'] / sector_breakdown['invested_amount'] * 100
                                )
                                
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.dataframe(
                                        sector_breakdown.style.format({
                                            'invested_amount': '₹{:,.0f}',
                                            'current_value': '₹{:,.0f}',
                                            'unrealized_pnl': '₹{:,.0f}',
                                            'pnl_percentage': '{:.2f}%'
                                        }),
                                        use_container_width=True,
                                        hide_index=True
                                    )
                                
                                with col2:
                                    # Bar chart comparing sectors
                                    fig_sector_compare = px.bar(
                                        sector_breakdown,
                                        x='sector',
                                        y='pnl_percentage',
                                        title='Sector P&L Comparison',
                                        color='pnl_percentage',
                                        color_continuous_scale='RdYlGn',
                                        text='pnl_percentage'
                                    )
                                    fig_sector_compare.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
                                    fig_sector_compare.update_layout(height=300)
                                    st.plotly_chart(fig_sector_compare, use_container_width=True, key="multi_sector_compare")
                                
                                st.markdown("---")
                                
                                # Group by ticker
                                holdings_summary = sector_holdings.groupby('ticker').agg({
                                    'stock_name': 'first',
                                    'quantity': 'sum',
                                    'invested_amount': 'sum',
                                    'current_value': 'sum',
                                    'unrealized_pnl': 'sum',
                                    'price': 'mean',
                                    'live_price': 'mean'
                                }).reset_index()
                                
                                holdings_summary['pnl_percentage'] = (holdings_summary['unrealized_pnl'] / holdings_summary['invested_amount'] * 100)
                                holdings_summary = holdings_summary.sort_values('pnl_percentage', ascending=False)
                                
                                # Display holdings table
                                st.dataframe(
                                    holdings_summary[['ticker', 'stock_name', 'quantity', 'invested_amount', 'current_value', 'unrealized_pnl', 'pnl_percentage']].style.format({
                                        'quantity': '{:,.2f}',
                                        'invested_amount': '₹{:,.0f}',
                                        'current_value': '₹{:,.0f}',
                                        'unrealized_pnl': '₹{:,.0f}',
                                        'pnl_percentage': '{:.2f}%'
                                    }),
                                    use_container_width=True
                                )
                                
                                # Stock multi-select for weekly values comparison
                                st.markdown("---")
                                st.subheader("📈 Weekly Values Comparison")
                                
                                stock_list = holdings_summary['ticker'].tolist()
                                selected_stocks = st.multiselect(
                                    "Select Stock(s)/Fund(s) to compare (multiple selections allowed):",
                                    options=stock_list,
                                    default=[stock_list[0]] if stock_list else [],
                                    format_func=lambda x: f"{x} - {holdings_summary[holdings_summary['ticker']==x]['stock_name'].iloc[0]}" if not holdings_summary[holdings_summary['ticker']==x].empty else x,
                                    key="stock_weekly_multi_dropdown"
                                )
                                
                                if selected_stocks and len(selected_stocks) > 0:
                                    self.render_weekly_values_multi(selected_stocks, self.session_state.user_id, context="sector_analysis")
            
            except Exception as e:
                st.error(f"Error in sector analysis: {e}")
        
        with tab2:
            st.subheader("📡 Channel-Wise Performance")
            
            try:
                if 'channel' not in df.columns or df['channel'].isna().all():
                    st.warning("Channel information not available")
                    return
                
                # Check if all channels are Unknown or empty
                valid_channels = df[~df['channel'].isin(['Unknown', '', None])]['channel'].dropna()
                if len(valid_channels) == 0:
                    st.warning("⚠️ No channel information available - all holdings show as 'Unknown'")
                    st.info("💡 Channels are set from the CSV file's 'channel' column. Please ensure your CSV has channel information.")
                    
                    # Show breakdown by ticker instead  
                    st.subheader("📊 Holdings Breakdown (Without Channels)")
                    holdings_summary = df.groupby('ticker').agg({
                        'stock_name': 'first',
                        'invested_amount': 'sum',
                        'current_value': 'sum',
                        'unrealized_pnl': 'sum'
                    }).reset_index()
                    holdings_summary['pnl_percentage'] = (holdings_summary['unrealized_pnl'] / holdings_summary['invested_amount'] * 100)
                    holdings_summary = holdings_summary.sort_values('pnl_percentage', ascending=False)
                    
                    st.dataframe(
                        holdings_summary.style.format({
                            'invested_amount': '₹{:,.0f}',
                            'current_value': '₹{:,.0f}',
                            'unrealized_pnl': '₹{:,.0f}',
                            'pnl_percentage': '{:.2f}%'
                        }),
                        use_container_width=True
                    )
                    return
                
                # Group by channel
                channel_data = df.groupby('channel').agg({
                    'invested_amount': 'sum',
                    'current_value': 'sum',
                    'unrealized_pnl': 'sum'
                }).reset_index()
                
                channel_data['pnl_percentage'] = (channel_data['unrealized_pnl'] / channel_data['invested_amount'] * 100)
                channel_data = channel_data.sort_values('pnl_percentage', ascending=False)
                
                # Display channel performance table
                st.dataframe(
                    channel_data.style.format({
                        'invested_amount': '₹{:,.0f}',
                        'current_value': '₹{:,.0f}',
                        'unrealized_pnl': '₹{:,.0f}',
                        'pnl_percentage': '{:.2f}%'
                    }),
                    use_container_width=True
                )
                
                # Channel bar chart
                import plotly.express as px
                fig = px.bar(
                    channel_data,
                    x='channel',
                    y='pnl_percentage',
                    title='Performance by Channel (%)',
                    color='pnl_percentage',
                    color_continuous_scale=['red', 'yellow', 'green']
                )
                st.plotly_chart(fig, use_container_width=True, key="channel_analysis_bar")
                
                # ===== NEW: Hierarchical Channel > Sector > Holding Multi-Select =====
                st.markdown("---")
                st.subheader("🔍 Drill-Down by Channel(s) → Sector(s) → Holdings (Multiple Selections Allowed)")
                
                # Step 1: Channel multi-selection
                channel_list = sorted(df['channel'].dropna().unique().tolist())
                selected_channels = st.multiselect(
                    "1️⃣ Select Channel(s) (leave empty for all):",
                    options=channel_list,
                    default=[],
                    key="channel_filter_multiselect"
                )
                
                if not selected_channels or len(selected_channels) == 0:
                        # Show all data across all channels
                        st.info(f"📊 Viewing: **All Channels** - {len(df)} transaction(s)")
                        
                        # Check for sector column - use sector_db if sector is not available
                        if 'sector' not in df.columns or df['sector'].isna().all():
                            if 'sector_db' in df.columns and not df['sector_db'].isna().all():
                                df['sector'] = df['sector_db']
                        
                        if 'sector' in df.columns and not df['sector'].isna().all():
                            # Show sector dropdown for all data
                            sector_list = sorted(df['sector'].dropna().unique().tolist())
                            
                            if sector_list:
                                selected_sector = st.selectbox(
                                    "2️⃣ Select Sector (across all channels):",
                                    options=["All Sectors"] + sector_list,
                                    key="all_channels_sector_dropdown"
                                )
                                
                                if selected_sector != "All Sectors":
                                    # Filter by sector
                                    sector_df = df[df['sector'] == selected_sector].copy()
                                    st.info(f"📊 Sector: **{selected_sector}** - {len(sector_df)} transaction(s)")
                                    
                                    # Show holdings in this sector
                                    holdings_summary = sector_df.groupby('ticker').agg({
                                        'stock_name': 'first',
                                        'channel': lambda x: ', '.join(x.unique()[:3]) + ('...' if len(x.unique()) > 3 else ''),
                                        'quantity': 'sum',
                                        'invested_amount': 'sum',
                                        'current_value': 'sum',
                                        'unrealized_pnl': 'sum'
                                    }).reset_index()
                                    
                                    holdings_summary['pnl_percentage'] = (holdings_summary['unrealized_pnl'] / holdings_summary['invested_amount'] * 100)
                                    holdings_summary = holdings_summary.sort_values('pnl_percentage', ascending=False)
                                    
                                    st.dataframe(
                                        holdings_summary[['ticker', 'stock_name', 'channel', 'quantity', 'invested_amount', 'current_value', 'unrealized_pnl', 'pnl_percentage']].style.format({
                                            'quantity': '{:,.2f}',
                                            'invested_amount': '₹{:,.0f}',
                                            'current_value': '₹{:,.0f}',
                                            'unrealized_pnl': '₹{:,.0f}',
                                            'pnl_percentage': '{:.2f}%'
                                        }),
                                        use_container_width=True
                                    )
                                    
                                    # Multi-select for holdings comparison
                                    st.markdown("---")
                                    st.subheader("📈 Compare Holdings - Weekly Price Trends")
                                    
                                    holding_list = holdings_summary['ticker'].tolist()
                                    selected_holdings = st.multiselect(
                                        "3️⃣ Select Holding(s) to compare:",
                                        options=holding_list,
                                        default=[holding_list[0]] if holding_list else [],
                                        format_func=lambda x: f"{x} - {holdings_summary[holdings_summary['ticker']==x]['stock_name'].iloc[0]}" if not holdings_summary[holdings_summary['ticker']==x].empty else x,
                                        key="all_channels_sector_holding_multi"
                                    )
                                    
                                    if selected_holdings and len(selected_holdings) > 0:
                                        # Show aggregate stats
                                        selected_data = holdings_summary[holdings_summary['ticker'].isin(selected_holdings)]
                                        total_invested = selected_data['invested_amount'].sum()
                                        total_current = selected_data['current_value'].sum()
                                        total_pnl = selected_data['unrealized_pnl'].sum()
                                        avg_pnl_pct = selected_data['pnl_percentage'].mean()
                                        
                                        col1, col2, col3, col4 = st.columns(4)
                                        with col1:
                                            st.metric("Total Invested", f"₹{total_invested:,.0f}")
                                        with col2:
                                            st.metric("Total Current", f"₹{total_current:,.0f}")
                                        with col3:
                                            st.metric("Total P&L", f"₹{total_pnl:,.0f}")
                                        with col4:
                                            st.metric("Avg P&L %", f"{avg_pnl_pct:.2f}%", delta=f"{avg_pnl_pct:.2f}%")
                                        
                                        # Render weekly values comparison
                                        self.render_weekly_values_multi(selected_holdings, self.session_state.user_id, context="all_channels_sector")
                                
                                else:
                                    # All Sectors selected - show all holdings
                                    st.info(f"📊 Viewing: **All Sectors** across all channels")
                                    
                                    holdings_summary = df.groupby('ticker').agg({
                                        'stock_name': 'first',
                                        'sector': 'first',
                                        'channel': lambda x: ', '.join(x.unique()[:3]) + ('...' if len(x.unique()) > 3 else ''),
                                        'quantity': 'sum',
                                        'invested_amount': 'sum',
                                        'current_value': 'sum',
                                        'unrealized_pnl': 'sum'
                                    }).reset_index()
                                    
                                    holdings_summary['pnl_percentage'] = (holdings_summary['unrealized_pnl'] / holdings_summary['invested_amount'] * 100)
                                    holdings_summary = holdings_summary.sort_values('pnl_percentage', ascending=False)
                                    
                                    st.dataframe(
                                        holdings_summary[['ticker', 'stock_name', 'sector', 'channel', 'quantity', 'invested_amount', 'current_value', 'unrealized_pnl', 'pnl_percentage']].style.format({
                                            'quantity': '{:,.2f}',
                                            'invested_amount': '₹{:,.0f}',
                                            'current_value': '₹{:,.0f}',
                                            'unrealized_pnl': '₹{:,.0f}',
                                            'pnl_percentage': '{:.2f}%'
                                        }),
                                        use_container_width=True
                                    )
                                    
                                    # Multi-select for all holdings
                                    st.markdown("---")
                                    st.subheader("📈 Compare Any Holdings - Weekly Price Trends")
                                    
                                    holding_list = holdings_summary['ticker'].tolist()
                                    selected_holdings = st.multiselect(
                                        "Select Holding(s) to compare:",
                                        options=holding_list,
                                        default=[holding_list[0]] if holding_list else [],
                                        format_func=lambda x: f"{x} - {holdings_summary[holdings_summary['ticker']==x]['stock_name'].iloc[0]} ({holdings_summary[holdings_summary['ticker']==x]['sector'].iloc[0]})" if not holdings_summary[holdings_summary['ticker']==x].empty else x,
                                        key="all_channels_all_sectors_holding_multi"
                                    )
                                    
                                    if selected_holdings and len(selected_holdings) > 0:
                                        # Show aggregate stats
                                        selected_data = holdings_summary[holdings_summary['ticker'].isin(selected_holdings)]
                                        total_invested = selected_data['invested_amount'].sum()
                                        total_current = selected_data['current_value'].sum()
                                        total_pnl = selected_data['unrealized_pnl'].sum()
                                        avg_pnl_pct = selected_data['pnl_percentage'].mean()
                                        
                                        col1, col2, col3, col4 = st.columns(4)
                                        with col1:
                                            st.metric("Total Invested", f"₹{total_invested:,.0f}")
                                        with col2:
                                            st.metric("Total Current", f"₹{total_current:,.0f}")
                                        with col3:
                                            st.metric("Total P&L", f"₹{total_pnl:,.0f}")
                                        with col4:
                                            st.metric("Avg P&L %", f"{avg_pnl_pct:.2f}%", delta=f"{avg_pnl_pct:.2f}%")
                                        
                                        # Render weekly values comparison
                                        self.render_weekly_values_multi(selected_holdings, self.session_state.user_id, context="all_channels_all_sectors")
                        else:
                            st.info("💡 No sector data available. Showing all holdings without sector breakdown.")
                            
                            # Show all holdings without sector filter
                            holdings_summary = df.groupby('ticker').agg({
                                'stock_name': 'first',
                                'channel': lambda x: ', '.join(x.unique()[:3]) + ('...' if len(x.unique()) > 3 else ''),
                                'quantity': 'sum',
                                'invested_amount': 'sum',
                                'current_value': 'sum',
                                'unrealized_pnl': 'sum'
                            }).reset_index()
                            
                            holdings_summary['pnl_percentage'] = (holdings_summary['unrealized_pnl'] / holdings_summary['invested_amount'] * 100)
                            holdings_summary = holdings_summary.sort_values('pnl_percentage', ascending=False)
                            
                            st.dataframe(
                                holdings_summary[['ticker', 'stock_name', 'channel', 'quantity', 'invested_amount', 'current_value', 'unrealized_pnl', 'pnl_percentage']].style.format({
                                    'quantity': '{:,.2f}',
                                    'invested_amount': '₹{:,.0f}',
                                    'current_value': '₹{:,.0f}',
                                    'unrealized_pnl': '₹{:,.0f}',
                                    'pnl_percentage': '{:.2f}%'
                                }),
                                use_container_width=True
                            )
                            
                            # Multi-select for holdings
                            st.markdown("---")
                            st.subheader("📈 Compare Holdings - Weekly Price Trends")
                            
                            holding_list = holdings_summary['ticker'].tolist()
                            selected_holdings = st.multiselect(
                                "Select Holding(s) to compare:",
                                options=holding_list,
                                default=[holding_list[0]] if holding_list else [],
                                format_func=lambda x: f"{x} - {holdings_summary[holdings_summary['ticker']==x]['stock_name'].iloc[0]}" if not holdings_summary[holdings_summary['ticker']==x].empty else x,
                                key="all_channels_no_sector_holding_multi"
                            )
                            
                            if selected_holdings and len(selected_holdings) > 0:
                                # Show aggregate stats
                                selected_data = holdings_summary[holdings_summary['ticker'].isin(selected_holdings)]
                                total_invested = selected_data['invested_amount'].sum()
                                total_current = selected_data['current_value'].sum()
                                total_pnl = selected_data['unrealized_pnl'].sum()
                                avg_pnl_pct = selected_data['pnl_percentage'].mean()
                                
                                col1, col2, col3, col4 = st.columns(4)
                                with col1:
                                    st.metric("Total Invested", f"₹{total_invested:,.0f}")
                                with col2:
                                    st.metric("Total Current", f"₹{total_current:,.0f}")
                                with col3:
                                    st.metric("Total P&L", f"₹{total_pnl:,.0f}")
                                with col4:
                                    st.metric("Avg P&L %", f"{avg_pnl_pct:.2f}%", delta=f"{avg_pnl_pct:.2f}%")
                                
                                # Render weekly values comparison
                                self.render_weekly_values_multi(selected_holdings, self.session_state.user_id, context="all_channels_no_sector")
                    
                else:
                        # Filter by selected channels
                        channel_df = df[df['channel'].isin(selected_channels)].copy()
                        
                        channels_str = ", ".join(selected_channels)
                        st.info(f"📊 Channel(s): **{channels_str}** - {len(channel_df)} transaction(s)")
                        
                        # Show channel-by-channel breakdown if multiple channels selected
                        if len(selected_channels) > 1:
                            st.markdown("### 📊 Performance by Selected Channels")
                            channel_breakdown = channel_df.groupby('channel').agg({
                                'invested_amount': 'sum',
                                'current_value': 'sum',
                                'unrealized_pnl': 'sum'
                            }).reset_index()
                            channel_breakdown['pnl_percentage'] = (
                                channel_breakdown['unrealized_pnl'] / channel_breakdown['invested_amount'] * 100
                            )
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                st.dataframe(
                                    channel_breakdown.style.format({
                                        'invested_amount': '₹{:,.0f}',
                                        'current_value': '₹{:,.0f}',
                                        'unrealized_pnl': '₹{:,.0f}',
                                        'pnl_percentage': '{:.2f}%'
                                    }),
                                    use_container_width=True,
                                    hide_index=True
                                )
                            
                            with col2:
                                # Bar chart comparing channels
                                fig_channel_compare = px.bar(
                                    channel_breakdown,
                                    x='channel',
                                    y='pnl_percentage',
                                    title='Channel P&L Comparison',
                                    color='pnl_percentage',
                                    color_continuous_scale='RdYlGn',
                                    text='pnl_percentage'
                                )
                                fig_channel_compare.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
                                fig_channel_compare.update_layout(height=300)
                                st.plotly_chart(fig_channel_compare, use_container_width=True, key="multi_channel_compare")
                            
                            st.markdown("---")
                        
                        # Step 2: Sector selection within channel
                        # Check for sector column - try sector or sector_db
                        if 'sector' not in channel_df.columns or channel_df['sector'].isna().all():
                            if 'sector_db' in channel_df.columns and not channel_df['sector_db'].isna().all():
                                channel_df['sector'] = channel_df['sector_db']
                        
                        # Show sector breakdown for this channel
                        if 'sector' in channel_df.columns and not channel_df['sector'].isna().all():
                            st.markdown("### 📊 Sector Breakdown in this Channel")
                            
                            # Aggregate by sector within channel
                            sector_breakdown = channel_df.groupby('sector').agg({
                                'invested_amount': 'sum',
                                'current_value': 'sum',
                                'unrealized_pnl': 'sum'
                            }).reset_index()
                            
                            sector_breakdown['pnl_percentage'] = (
                                sector_breakdown['unrealized_pnl'] / sector_breakdown['invested_amount'] * 100
                            )
                            sector_breakdown = sector_breakdown.sort_values('pnl_percentage', ascending=False)
                            
                            # Display sector summary table
                            col1, col2 = st.columns([2, 1])
                            
                            with col1:
                                st.dataframe(
                                    sector_breakdown.style.format({
                                        'invested_amount': '₹{:,.0f}',
                                        'current_value': '₹{:,.0f}',
                                        'unrealized_pnl': '₹{:,.0f}',
                                        'pnl_percentage': '{:.2f}%'
                                    }),
                                    use_container_width=True,
                                    hide_index=True
                                )
                            
                            with col2:
                                # Pie chart showing sector allocation in these channels
                                fig_sector_pie = px.pie(
                                    sector_breakdown,
                                    values='current_value',
                                    names='sector',
                                    title=f'Sector Allocation in {channels_str}'
                                )
                                fig_sector_pie.update_layout(height=250, showlegend=True)
                                # Generate unique key from selected channels
                                channels_key = "_".join(sorted(selected_channels))
                                st.plotly_chart(fig_sector_pie, use_container_width=True, key=f"channel_sector_pie_{channels_key}")
                            
                            st.markdown("---")
                        
                        if 'sector' in channel_df.columns and not channel_df['sector'].isna().all():
                            sector_list = sorted(channel_df['sector'].dropna().unique().tolist())
                            
                            if sector_list:
                                selected_sectors_in_channel = st.multiselect(
                                    "2️⃣ Select Sector(s) within channel(s) (multiple selections allowed):",
                                    options=sector_list,
                                    default=[],
                                    key="channel_sector_multiselect"
                                )
                                
                                if selected_sectors_in_channel and len(selected_sectors_in_channel) > 0:
                                    # Filter by sectors
                                    sector_df = channel_df[channel_df['sector'].isin(selected_sectors_in_channel)].copy()
                                    
                                    sectors_str = ", ".join(selected_sectors_in_channel)
                                    st.info(f"📊 Sector(s): **{sectors_str}** - {len(sector_df)} transaction(s)")
                                    
                                    # Step 3: Show holdings and allow selection
                                    if not sector_df.empty:
                                        # Group by ticker
                                        holdings_summary = sector_df.groupby('ticker').agg({
                                            'stock_name': 'first',
                                            'quantity': 'sum',
                                            'invested_amount': 'sum',
                                            'current_value': 'sum',
                                            'unrealized_pnl': 'sum'
                                        }).reset_index()
                                        
                                        holdings_summary['pnl_percentage'] = (holdings_summary['unrealized_pnl'] / holdings_summary['invested_amount'] * 100)
                                        holdings_summary = holdings_summary.sort_values('pnl_percentage', ascending=False)
                                        
                                        st.dataframe(
                                            holdings_summary[['ticker', 'stock_name', 'quantity', 'invested_amount', 'current_value', 'unrealized_pnl', 'pnl_percentage']].style.format({
                                                'quantity': '{:,.2f}',
                                                'invested_amount': '₹{:,.0f}',
                                                'current_value': '₹{:,.0f}',
                                                'unrealized_pnl': '₹{:,.0f}',
                                                'pnl_percentage': '{:.2f}%'
                                            }),
                                            use_container_width=True
                                        )
                                        
                                        # Step 4: Select holdings for weekly values comparison
                                        st.markdown("---")
                                        st.subheader("📈 Weekly Values Comparison")
                                        
                                        holding_list = holdings_summary['ticker'].tolist()
                                        selected_holdings = st.multiselect(
                                            "3️⃣ Select Holding(s) to compare (multiple selections allowed):",
                                            options=holding_list,
                                            default=[holding_list[0]] if holding_list else [],
                                            format_func=lambda x: f"{x} - {holdings_summary[holdings_summary['ticker']==x]['stock_name'].iloc[0]}" if not holdings_summary[holdings_summary['ticker']==x].empty else x,
                                            key="channel_holding_weekly_multi_dropdown"
                                        )
                                        
                                        if selected_holdings and len(selected_holdings) > 0:
                                            self.render_weekly_values_multi(selected_holdings, self.session_state.user_id, context="channel_sector")
                                else:
                                    # Show all holdings in channel across all sectors
                                    holdings_summary = channel_df.groupby('ticker').agg({
                                        'stock_name': 'first',
                                        'sector': 'first',
                                        'quantity': 'sum',
                                        'invested_amount': 'sum',
                                        'current_value': 'sum',
                                        'unrealized_pnl': 'sum'
                                    }).reset_index()
                                    
                                    holdings_summary['pnl_percentage'] = (holdings_summary['unrealized_pnl'] / holdings_summary['invested_amount'] * 100)
                                    holdings_summary = holdings_summary.sort_values('pnl_percentage', ascending=False)
                                    
                                    st.dataframe(
                                        holdings_summary[['ticker', 'stock_name', 'sector', 'quantity', 'invested_amount', 'current_value', 'unrealized_pnl', 'pnl_percentage']].style.format({
                                            'quantity': '{:,.2f}',
                                            'invested_amount': '₹{:,.0f}',
                                            'current_value': '₹{:,.0f}',
                                            'unrealized_pnl': '₹{:,.0f}',
                                            'pnl_percentage': '{:.2f}%'
                                        }),
                                        use_container_width=True
                                    )
                            else:
                                st.info("💡 No sector data available for this channel. Showing all holdings.")
                                # Show all holdings without sector breakdown
                                holdings_summary = channel_df.groupby('ticker').agg({
                                    'stock_name': 'first',
                                    'quantity': 'sum',
                                    'invested_amount': 'sum',
                                    'current_value': 'sum',
                                    'unrealized_pnl': 'sum'
                                }).reset_index()
                                
                                holdings_summary['pnl_percentage'] = (holdings_summary['unrealized_pnl'] / holdings_summary['invested_amount'] * 100)
                                holdings_summary = holdings_summary.sort_values('pnl_percentage', ascending=False)
                                
                                st.dataframe(
                                    holdings_summary[['ticker', 'stock_name', 'quantity', 'invested_amount', 'current_value', 'unrealized_pnl', 'pnl_percentage']].style.format({
                                        'quantity': '{:,.2f}',
                                        'invested_amount': '₹{:,.0f}',
                                        'current_value': '₹{:,.0f}',
                                        'unrealized_pnl': '₹{:,.0f}',
                                        'pnl_percentage': '{:.2f}%'
                                    }),
                                    use_container_width=True
                                )
            
            except Exception as e:
                st.error(f"Error in channel analysis: {e}")
                import traceback
                st.error(f"Details: {traceback.format_exc()}")
    
    def render_one_year_performance_page(self):
        """Render 1-year performance page for holdings purchased in last 12 months"""
        from datetime import datetime, timedelta
        
        st.header("📈 1-Year Performance")
        
        if self.session_state.portfolio_data is None:
            self.show_page_loading_animation("1-Year Performance")
            st.info("💡 **Tip:** If this page doesn't load automatically, use the '🔄 Refresh Portfolio Data' button in Settings.")
            return
        
        df = self.session_state.portfolio_data
        
        st.markdown("""
        **This page shows performance of holdings purchased in the last 12 months**
        - Track recent investments
        - Compare with older holdings
        - Analyze new investment performance
        """)
        
        st.markdown("---")
        
        try:
            # Filter for holdings purchased in last 12 months
            one_year_ago = datetime.now() - timedelta(days=365)
            df['date'] = pd.to_datetime(df['date'])
            recent_holdings = df[df['date'] >= one_year_ago].copy()
            
            if recent_holdings.empty:
                st.info("No holdings purchased in the last 12 months")
                return
            
            # Summary metrics
            col1, col2, col3 = st.columns(3)
            
            with col1:
                recent_invested = recent_holdings['invested_amount'].sum()
                st.metric("💰 Invested (Last Year)", f"₹{recent_invested:,.0f}")
            
            with col2:
                recent_current = recent_holdings['current_value'].sum()
                st.metric("📈 Current Value", f"₹{recent_current:,.0f}")
            
            with col3:
                recent_pnl = recent_holdings['unrealized_pnl'].sum()
                recent_pnl_pct = (recent_pnl / recent_invested * 100) if recent_invested > 0 else 0
                st.metric("💵 P&L", f"₹{recent_pnl:,.0f}", delta=f"{recent_pnl_pct:.2f}%")
            
            st.markdown("---")
            
            # Holdings table
            st.subheader("📋 Holdings Purchased in Last 12 Months")
            display_df = recent_holdings[['date', 'ticker', 'stock_name', 'invested_amount', 'current_value', 'unrealized_pnl', 'pnl_percentage']].copy()
            st.dataframe(
                display_df.style.format({
                    'date': lambda x: x.strftime('%Y-%m-%d'),
                    'invested_amount': '₹{:,.0f}',
                    'current_value': '₹{:,.0f}',
                    'unrealized_pnl': '₹{:,.0f}',
                    'pnl_percentage': '{:.2f}%'
                }),
                use_container_width=True
            )
            
        except Exception as e:
            st.error(f"Error in 1-year performance: {e}")
            import traceback
            st.error(traceback.format_exc())

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
            st.info(f"📁 {len(uploaded_files)} file(s) ready to upload")
            
            if st.button("🚀 Process All Files", type="primary", use_container_width=True):
                processed_count = 0
                failed_count = 0
                failed_files = []
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for idx, uploaded_file in enumerate(uploaded_files):
                    try:
                        status_text.text(f"Processing {idx+1}/{len(uploaded_files)}: {uploaded_file.name}")
                        progress_bar.progress((idx) / len(uploaded_files))
                        
                        with st.spinner(f"Processing {uploaded_file.name}..."):
                            success = self.process_csv_file(uploaded_file, self.session_state.user_id)
                            if success:
                                st.success(f"✅ {uploaded_file.name} processed successfully!")
                                processed_count += 1
                            else:
                                st.error(f"❌ Failed to process {uploaded_file.name}")
                                failed_count += 1
                                failed_files.append(uploaded_file.name)
                                
                    except Exception as e:
                        st.error(f"❌ Error processing {uploaded_file.name}: {str(e)}")
                        failed_count += 1
                        failed_files.append(f"{uploaded_file.name} ({str(e)})")
                        # Continue to next file instead of stopping
                        continue
                
                # Clear progress indicators
                progress_bar.progress(1.0)
                status_text.empty()
                progress_bar.empty()
                
                # Show summary
                st.markdown("---")
                st.subheader("📊 Upload Summary")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("✅ Successful", processed_count)
                with col2:
                    st.metric("❌ Failed", failed_count)
                with col3:
                    st.metric("📁 Total", len(uploaded_files))
                
                if failed_files:
                    st.error("**Failed files:**")
                    for failed_file in failed_files:
                        st.write(f"- {failed_file}")
                
                if processed_count > 0:
                    st.success(f"✅ Successfully processed {processed_count} file(s)!")
                    # Refresh portfolio data
                    with st.spinner("Refreshing portfolio data..."):
                        self.load_portfolio_data(self.session_state.user_id)
                    st.rerun()

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
        
        st.info("""
        **💡 Tip:** Historical price cache is built on-demand.
        - Your portfolio loads instantly with live prices
        - Historical charts and analysis will use cached data
        - Click "Update Price Cache" below to pre-fetch historical data for faster charts
        """)

        col1, col2 = st.columns(2)

        with col1:
            if st.button("🔄 Refresh Portfolio Data", type="primary"):
                with st.spinner("Refreshing portfolio data..."):
                    self.load_portfolio_data(self.session_state.user_id)
                    st.success("✅ Portfolio data refreshed!")

        with col2:
            if st.button("🔄 Update Price Cache", type="secondary"):
                st.warning("⏳ This will fetch historical data for all holdings. It may take 5-10 minutes for large portfolios.")
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
                    ticker_data = stock_and_mf_buys[stock_and_mf_buys['ticker'] == ticker].iloc[0]
                    
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
                        ticker_transactions = stock_and_mf_buys[stock_and_mf_buys['ticker'] == ticker].copy()
                        
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
        if not stock_and_mf_buys.empty:
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
                        channel_performance = stock_and_mf_buys.groupby('channel').agg({
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
                            sector_stocks = stock_and_mf_buys[stock_and_mf_buys['sector'] == sector]
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
                            channel_stocks = stock_and_mf_buys[stock_and_mf_buys['channel'] == channel]
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
                    
                    for sector in stock_and_mf_buys['sector'].unique():
                        if pd.isna(sector) or sector == 'Unknown':
                            continue
                            
                        sector_stocks = stock_and_mf_buys[stock_and_mf_buys['sector'] == sector]
                        
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
                    
                    for channel in stock_and_mf_buys['channel'].unique():
                        if pd.isna(channel) or channel == 'Unknown':
                            continue
                            
                        channel_stocks = stock_and_mf_buys[stock_and_mf_buys['channel'] == channel]
                        
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
            
            # Cache refresh button
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
                if st.button("🔄 Refresh Historical Price Cache", type="secondary", help="Fetch and cache historical prices for all stocks"):
                    user_id = self.session_state.user_id
                    with st.spinner("🔄 Refreshing historical price cache... This may take a few minutes."):
                        self.populate_monthly_prices_cache(user_id)
                    st.success("✅ Historical price cache refreshed!")
                    st.rerun()  # Refresh the page to show updated data
            
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
                
                # Check for available historical data in database (informational only)
                st.info("🔍 Checking for available historical data in database...")
                from database_config_supabase import get_stock_prices_range_supabase
                
                stocks_with_data = []
                stocks_without_data = []
                
                for _, stock in stock_purchases.iterrows():
                    ticker = stock['ticker']
                    purchase_date = stock['date']
                    
                    # Check if we have any historical data for this ticker
                    try:
                        # Try to get data for the last month as a test
                        test_date = datetime.now().replace(day=1)
                        test_date_str = test_date.strftime('%Y-%m-%d')
                        historical_data = get_stock_prices_range_supabase(
                            ticker, 
                            purchase_date.strftime('%Y-%m-%d'),
                            test_date_str
                        )
                        
                        if historical_data and len(historical_data) > 0:
                            stocks_with_data.append(ticker)
                        else:
                            stocks_without_data.append(ticker)
                    except Exception as e:
                        stocks_without_data.append(ticker)
                
                # Show status but don't filter out stocks - let them be processed
                if stocks_with_data:
                    st.success(f"✅ Found historical data for {len(stocks_with_data)} stocks")
                
                if stocks_without_data:
                    st.warning(f"⚠️ No historical data available for: {', '.join(stocks_without_data)}")
                    st.info("💡 Historical data will be fetched and cached during processing. This may take a few minutes.")
                
                # Generate monthly data for each stock from purchase date to current date
                if not stock_purchases.empty:
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
                        
                        # Skip if no data for this ticker
                        if stock_data.empty or len(stock_data) == 0:
                            continue
                        
                        stock_name = stock_data['stock_name'].iloc[0] if 'stock_name' in stock_data.columns else ticker
                        
                        fig_price_overview.add_trace(go.Scatter(
                            x=stock_data['month'],
                            y=stock_data['historical_price'],
                            mode='lines+markers',
                            name=f'{ticker} - {stock_name}',
                            line=dict(color=colors[i % len(colors)], width=2),
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
                        
                        # Skip if insufficient data
                        if stock_data.empty or len(stock_data) < 2:
                            continue
                        
                        initial_price = stock_data['historical_price'].iloc[0]
                        final_price = stock_data['historical_price'].iloc[-1]
                        price_change = final_price - initial_price
                        price_change_pct = (price_change / initial_price) * 100 if initial_price > 0 else 0
                        
                        stock_name = stock_data['stock_name'].iloc[0] if 'stock_name' in stock_data.columns else ticker
                        
                        price_performance_data.append({
                            'ticker': ticker,
                            'stock_name': stock_name,
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
                                # Determine color based on actual percentage value
                                change_color = "normal" if stock['price_change_pct'] > 0 else "inverse" if stock['price_change_pct'] < 0 else "off"
                                st.metric(
                                    f"{stock['ticker']} - {stock['stock_name']}",
                                    f"₹{stock['final_price']:.2f}",
                                    delta=f"{stock['price_change_pct']:+.2f}%",
                                    delta_color=change_color
                                )
                        
                        with col2:
                            st.subheader("📉 Worst Price Performers")
                            worst_performers = price_perf_df.tail(3)
                            for _, stock in worst_performers.iterrows():
                                # Determine color based on actual percentage value
                                change_color = "normal" if stock['price_change_pct'] > 0 else "inverse" if stock['price_change_pct'] < 0 else "off"
                                st.metric(
                                    f"{stock['ticker']} - {stock['stock_name']}",
                                    f"₹{stock['final_price']:.2f}",
                                    delta=f"{stock['price_change_pct']:+.2f}%",
                                    delta_color=change_color
                                )
                    
                    # Individual stock performance
                    st.subheader("📈 Individual Stock Performance")
                    
                    # Create dropdown for stock selection
                    unique_stocks = monthly_pnl_df['ticker'].unique()
                    
                    # Create a safe format function
                    def format_stock_name(ticker):
                        try:
                            stock_data = monthly_pnl_df[monthly_pnl_df['ticker']==ticker]
                            if not stock_data.empty and 'stock_name' in stock_data.columns:
                                return f"{ticker} - {stock_data['stock_name'].iloc[0]}"
                            return ticker
                        except:
                            return ticker
                    
                    selected_stock = st.selectbox(
                        "Select a stock to view detailed monthly performance:",
                        unique_stocks,
                        format_func=format_stock_name,
                        key="monthly_stock_select"
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
            
            # Historical Performance Tracking for All Holdings
        st.markdown("---")
        st.subheader("📊 Historical Performance Tracking (All Holdings)")
        st.info("💡 Track monthly/weekly performance for all your stocks and mutual funds over the past year")
            
            # Check if cache is still populating
        user_id = self.session_state.user_id
        cache_key = f'cache_populated_{user_id}'
        cache_trigger_key = f'cache_trigger_{user_id}'
            
        if cache_trigger_key in st.session_state and st.session_state[cache_trigger_key]:
                st.warning("⏳ **Historical cache is currently populating in the sidebar.** Charts will load faster once complete!")
                st.caption("You can still view historical data, but it may take longer as data is fetched on-demand.")
        elif cache_key in st.session_state and st.session_state[cache_key]:
                st.success("✅ **Historical cache is ready!** Charts will load instantly from database.")
            
            # Time period selection
        col1, col2 = st.columns([1, 3])
        with col1:
            tracking_period = st.selectbox(
                    "Select Tracking Period",
                    ["Monthly", "Weekly"],
                    help="Choose how frequently to track performance",
                    key="tracking_period_select"
                )
            
            try:
                # Get all unique tickers from portfolio
                all_tickers = df['ticker'].unique()
                
                if len(all_tickers) > 0:
                    # Date range for 1 year back
                    end_date = pd.Timestamp.now()
                    start_date = end_date - timedelta(days=365)
                    
                    # Generate date range based on selected period
                    if tracking_period == "Monthly":
                        date_range = pd.date_range(start=start_date, end=end_date, freq='MS')  # Month start
                        period_label = "Month"
                    else:
                        date_range = pd.date_range(start=start_date, end=end_date, freq='W-MON')  # Weekly on Monday
                        period_label = "Week"
                    
                    st.info(f"📅 Tracking {len(all_tickers)} holdings over {len(date_range)} {period_label.lower()}s")
                    
                    # Create tabs for different views
                    tab1, tab2, tab3 = st.tabs(["📈 Performance Chart", "📊 Comparison Table", "🔍 Individual Analysis"])
                    
                    with tab1:
                        st.subheader(f"{period_label}ly Performance Overview")
                        
                        # Collect historical data for all tickers
                        st.info("📊 Loading historical data (stocks from cache, PMS/MF calculated)...")
                        historical_data = []
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        # Import database function for bulk queries
                        from database_config_supabase import get_stock_prices_range_supabase
                        
                        for idx, ticker in enumerate(all_tickers[:20]):  # Limit to first 20 for performance
                            status_text.text(f"Loading data for {ticker}... ({idx+1}/{min(len(all_tickers), 20)})")
                            
                            ticker_data = df[df['ticker'] == ticker].iloc[0]
                            stock_name = ticker_data.get('stock_name', ticker)
                            
                            # === CHECK IF PMS/AIF ===
                            ticker_upper = str(ticker).upper()
                            is_pms_aif = any(keyword in ticker_upper for keyword in [
                                'PMS', 'AIF', 'INP', 'BUOYANT', 'CARNELIAN', 'JULIUS', 
                                'VALENTIS', 'UNIFI', 'PORTFOLIO', 'FUND'
                            ]) or ticker_upper.endswith('_PMS') or str(ticker).startswith('INP')
                            
                            if is_pms_aif:
                                # For PMS/AIF, calculate value growth based on CAGR
                                try:
                                    # Get investment details
                                    investment_date = pd.to_datetime(ticker_data.get('date', datetime.now()))
                                    initial_investment = float(ticker_data.get('invested_value', 0))
                                    
                                    if initial_investment > 0:
                                        # Get PMS returns data
                                        from pms_aif_fetcher import get_pms_nav
                                        pms_data = get_pms_nav(
                                            ticker=ticker,
                                            pms_name=stock_name,
                                            investment_date=investment_date.strftime('%Y-%m-%d'),
                                            investment_amount=initial_investment
                                        )
                                        
                                        if pms_data and 'returns_data' in pms_data:
                                            returns = pms_data['returns_data']
                                            
                                            # Calculate value for each date using appropriate CAGR
                                            for date in date_range:
                                                months_elapsed = (date.year - investment_date.year) * 12 + (date.month - investment_date.month)
                                                
                                                if months_elapsed >= 0:
                                                    # Select appropriate return metric
                                                    if months_elapsed >= 60:  # 5+ years
                                                        cagr_str = returns.get('5Y CAGR', '0%')
                                                    elif months_elapsed >= 36:  # 3+ years
                                                        cagr_str = returns.get('3Y CAGR', '0%')
                                                    elif months_elapsed >= 12:  # 1+ year
                                                        cagr_str = returns.get('1Y Return', '0%')
                                                    elif months_elapsed >= 1:  # 1+ month
                                                        cagr_str = returns.get('1M Return', '0%')
                                                    else:
                                                        cagr_str = '0%'
                                                    
                                                    # Parse and calculate
                                                    cagr = float(cagr_str.replace('%', '')) / 100
                                                    years = months_elapsed / 12
                                                    calculated_value = initial_investment * ((1 + cagr) ** years)
                                                    
                                                    # Normalize to show growth (1.0 = initial investment)
                                                    normalized_value = calculated_value / initial_investment if initial_investment > 0 else 1
                                                    
                                                    historical_data.append({
                                                        'Date': date,
                                                        'Ticker': ticker,
                                                        'Stock Name': stock_name,
                                                        'Price': normalized_value
                                                    })
                                        else:
                                            st.warning(f"⚠️ {ticker}: PMS data not available, skipping historical tracking")
                                except Exception as e:
                                    st.warning(f"⚠️ {ticker}: Error calculating PMS performance - {e}")
                                    print(f"PMS calculation error for {ticker}: {e}")
                            else:
                                # Regular stock/MF - use cached prices
                                start_date_str = date_range[0].strftime('%Y-%m-%d')
                                end_date_str = date_range[-1].strftime('%Y-%m-%d')
                                
                                cached_prices = get_stock_prices_range_supabase(ticker, start_date_str, end_date_str)
                                
                                if cached_prices:
                                    # Use cached data
                                    for price_record in cached_prices:
                                        historical_data.append({
                                            'Date': pd.to_datetime(price_record['price_date']),
                                            'Ticker': ticker,
                                            'Stock Name': stock_name,
                                            'Price': float(price_record['price'])
                                        })
                                else:
                                    # Fallback: Fetch from API if not in cache
                                    # Check if it's a mutual fund (numeric ticker or starts with MF_)
                                    # Exclude BSE codes (6 digits starting with 5, e.g., 500414)
                                    clean_ticker = str(ticker).strip()
                                    is_bse_code = (clean_ticker.isdigit() and len(clean_ticker) == 6 and clean_ticker.startswith('5'))
                                    is_mutual_fund = (
                                        (clean_ticker.isdigit() and len(clean_ticker) >= 5 and len(clean_ticker) <= 6 and not is_bse_code) or
                                        clean_ticker.startswith('MF_')
                                    )

                                    if is_mutual_fund:
                                        st.info(f"📊 {ticker}: Mutual fund detected, fetching NAV history...")
                                    else:
                                        st.warning(f"⚠️ No cached data for {ticker}, fetching from API...")
                                    
                                    fetched_count = 0
                                    save_errors = []
                                    
                                    for date_idx, date in enumerate(date_range):
                                        status_text.text(f"Fetching {ticker} ({idx+1}/{min(len(all_tickers), 20)}) - {date.strftime('%b %Y')} ({date_idx+1}/{len(date_range)})...")
                                        
                                        hist_price = self.fetch_historical_price_for_month(ticker, date)
                                        
                                        if hist_price and hist_price > 0:
                                            historical_data.append({
                                                'Date': date,
                                                'Ticker': ticker,
                                                'Stock Name': stock_name,
                                                'Price': hist_price
                                            })
                                            fetched_count += 1
                                        else:
                                            # Track failed dates
                                            save_errors.append(date.strftime('%b %Y'))
                                    
                                    # Show results
                                    if fetched_count > 0:
                                        st.success(f"✅ {ticker}: Fetched and cached {fetched_count}/{len(date_range)} prices")
                                    
                                    if save_errors and len(save_errors) <= 5:
                                        st.warning(f"⚠️ {ticker}: Could not fetch data for: {', '.join(save_errors)}")
                                    
                                    if fetched_count == 0:
                                        # Check if it's a delisted or invalid ticker
                                        ticker_str = str(ticker).strip()
                                        
                                        # Provide helpful error messages
                                        if ticker_str.isdigit() and len(ticker_str) == 6:
                                            # Check if it's actually a mutual fund (some 6-digit codes are MF scheme codes)
                                            if len(ticker_str) >= 5:  # Most MF codes are 5+ digits
                                                st.error(f"⚠️ {ticker}: Mutual fund scheme not found. Please verify the scheme code.")
                                            else:
                                                st.error(f"⚠️ {ticker}: BSE code - may be delisted or data unavailable. Try adding ticker symbol instead.")
                                        elif ticker_str.upper() in ['OBEROIRLTY', 'TANFACIND']:
                                            st.error(f"⚠️ {ticker}: Stock may be delisted or suspended. No historical data available.")
                                        elif ticker_str.isdigit() and len(ticker_str) >= 5:
                                            st.error(f"⚠️ {ticker}: Mutual fund scheme not found. Please verify the scheme code.")
                                        else:
                                            st.warning(f"⚠️ {ticker}: Could not fetch any historical data. Ticker may be invalid, delisted, or temporarily unavailable.")
                            
                            progress_bar.progress((idx + 1) / min(len(all_tickers), 20))
                        
                        progress_bar.empty()
                        status_text.empty()
                        
                        # Verify data was actually saved to database
                        if historical_data:
                            st.info("🔍 Verifying saved data in database...")
                            unique_fetched_tickers = list(set([d['Ticker'] for d in historical_data]))
                            
                            # Sample verification: check if first ticker's data is in database
                            if unique_fetched_tickers:
                                sample_ticker = unique_fetched_tickers[0]
                                sample_date = date_range[0].strftime('%Y-%m-%d')
                                
                                try:
                                    from database_config_supabase import get_stock_price_supabase
                                    verified_price = get_stock_price_supabase(sample_ticker, sample_date)
                                    
                                    if verified_price and verified_price > 0:
                                        st.success(f"✅ Database verification passed: {sample_ticker} data is properly cached")
                                    else:
                                        st.error(f"⚠️ Database verification failed: {sample_ticker} data not found in cache after save!")
                                        st.info("💡 This might indicate a database permissions or connection issue. Check logs for errors.")
                                except Exception as verify_error:
                                    st.error(f"❌ Database verification error: {verify_error}")
                        
                        # Add retry button for failed tickers
                        failed_tickers = list(set(all_tickers[:20]) - set([d['Ticker'] for d in historical_data]))
                        if failed_tickers and len(failed_tickers) > 0:
                            st.warning(f"⚠️ {len(failed_tickers)} tickers failed to load: {', '.join(failed_tickers[:5])}{'...' if len(failed_tickers) > 5 else ''}")
                            
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                st.info("💡 **Tip**: Run 'Update Price Cache' from the main menu to populate missing historical data.")
                            with col2:
                                if st.button("🔄 Go to Cache Update", key="goto_cache_update"):
                                    st.session_state.page = "Dashboard"
                                    st.rerun()

                        # Add database verification button
                        if st.button("🔍 Verify Database Storage", key="verify_db_storage"):
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

                                    # Try to test database connection and table access
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
                        
                        if historical_data:
                            hist_df = pd.DataFrame(historical_data)
                            st.success(f"✅ Loaded {len(historical_data)} data points for {len(hist_df['Ticker'].unique())} holdings")
                            
                            # Create interactive line chart
                            fig = go.Figure()
                            
                            for ticker in hist_df['Ticker'].unique():
                                ticker_hist = hist_df[hist_df['Ticker'] == ticker]
                                stock_name = ticker_hist['Stock Name'].iloc[0]
                                
                                fig.add_trace(go.Scatter(
                                    x=ticker_hist['Date'],
                                    y=ticker_hist['Price'],
                                    mode='lines+markers',
                                    name=f"{stock_name} ({ticker})",
                                    hovertemplate=f"<b>{stock_name}</b><br>Date: %{{x}}<br>Price: ₹%{{y:.2f}}<extra></extra>"
                                ))
                            
                            fig.update_layout(
                                title=f"{period_label}ly Price Movement - All Holdings",
                                xaxis_title="Date",
                                yaxis_title="Price (₹)",
                                hovermode='x unified',
                                height=600,
                                showlegend=True,
                                legend=dict(
                                    yanchor="top",
                                    y=0.99,
                                    xanchor="left",
                                    x=0.01
                                )
                            )
                            
                            st.plotly_chart(fig, config={'displayModeBar': True, 'responsive': True})
                            
                            # Download option
                            csv = hist_df.to_csv(index=False)
                            st.download_button(
                                label=f"📥 Download {period_label}ly Data",
                                data=csv,
                                file_name=f"historical_performance_{tracking_period.lower()}_{datetime.now().strftime('%Y%m%d')}.csv",
                                mime="text/csv"
                            )
                        else:
                            st.warning("No historical data available")
                    
                    with tab2:
                        st.subheader(f"{period_label}ly Performance Comparison")
                        
                        if historical_data:
                            # Calculate performance metrics
                            comparison_data = []
                            
                            for ticker in hist_df['Ticker'].unique():
                                ticker_hist = hist_df[hist_df['Ticker'] == ticker].sort_values('Date')
                                
                                if len(ticker_hist) >= 2:
                                    first_price = ticker_hist['Price'].iloc[0]
                                    last_price = ticker_hist['Price'].iloc[-1]
                                    max_price = ticker_hist['Price'].max()
                                    min_price = ticker_hist['Price'].min()
                                    
                                    price_change = last_price - first_price
                                    price_change_pct = (price_change / first_price) * 100 if first_price > 0 else 0
                                    
                                    comparison_data.append({
                                        'Ticker': ticker,
                                        'Stock Name': ticker_hist['Stock Name'].iloc[0],
                                        'Start Price': f"₹{first_price:.2f}",
                                        'Current Price': f"₹{last_price:.2f}",
                                        'Highest': f"₹{max_price:.2f}",
                                        'Lowest': f"₹{min_price:.2f}",
                                        'Change': f"₹{price_change:+.2f}",
                                        'Change %': f"{price_change_pct:+.2f}%",
                                        'Sort': price_change_pct
                                    })
                            
                            if comparison_data:
                                comp_df = pd.DataFrame(comparison_data)
                                comp_df = comp_df.sort_values('Sort', ascending=False)
                                comp_df = comp_df.drop('Sort', axis=1)
                                
                                st.dataframe(
                                    comp_df,
                                    use_container_width=True,
                                    hide_index=True
                                )
                                
                                # Best and worst performers
                                col1, col2 = st.columns(2)
                                
                                with col1:
                                    st.success(f"🏆 Best Performer: {comp_df.iloc[0]['Stock Name']} ({comp_df.iloc[0]['Change %']})")
                                
                                with col2:
                                    st.error(f"📉 Worst Performer: {comp_df.iloc[-1]['Stock Name']} ({comp_df.iloc[-1]['Change %']})")
                        else:
                            st.info("No comparison data available")
                    
                    with tab3:
                        st.subheader("Individual Stock Analysis")
                        
                        selected_ticker = st.selectbox(
                            "Select a stock/MF to analyze",
                            all_tickers,
                            format_func=lambda x: f"{df[df['ticker']==x]['stock_name'].iloc[0]} ({x})" if len(df[df['ticker']==x]) > 0 else x,
                            key="historical_ticker_select"
                        )
                        
                        if selected_ticker and historical_data:
                            ticker_hist = hist_df[hist_df['Ticker'] == selected_ticker].sort_values('Date')
                            
                            if not ticker_hist.empty:
                                # Individual stock chart
                                fig_individual = go.Figure()
                                
                                fig_individual.add_trace(go.Scatter(
                                    x=ticker_hist['Date'],
                                    y=ticker_hist['Price'],
                                    mode='lines+markers',
                                    name=ticker_hist['Stock Name'].iloc[0],
                                    line=dict(color='blue', width=3),
                                    marker=dict(size=8),
                                    fill='tonexty',
                                    hovertemplate="Date: %{x}<br>Price: ₹%{y:.2f}<extra></extra>"
                                ))
                                
                                fig_individual.update_layout(
                                    title=f"{ticker_hist['Stock Name'].iloc[0]} - {period_label}ly Performance",
                                    xaxis_title="Date",
                                    yaxis_title="Price (₹)",
                                    hovermode='x unified',
                                    height=500
                                )
                                
                                st.plotly_chart(fig_individual, config={'displayModeBar': True, 'responsive': True})
                                
                                # Statistics
                                col1, col2, col3, col4 = st.columns(4)
                                
                                with col1:
                                    st.metric("Start Price", f"₹{ticker_hist['Price'].iloc[0]:.2f}")
                                
                                with col2:
                                    st.metric("Current Price", f"₹{ticker_hist['Price'].iloc[-1]:.2f}")
                                
                                with col3:
                                    st.metric("Highest", f"₹{ticker_hist['Price'].max():.2f}")
                                
                                with col4:
                                    st.metric("Lowest", f"₹{ticker_hist['Price'].min():.2f}")
                                
                                # Detailed data table
                                st.subheader(f"{period_label}ly Price Data")
                                st.dataframe(
                                    ticker_hist[['Date', 'Price']].sort_values('Date', ascending=False),
                                    use_container_width=True,
                                    hide_index=True
                                )
                            else:
                                st.warning(f"No historical data available for {selected_ticker}")
                else:
                    st.info("No holdings found in portfolio")
                    
            except Exception as e:
                st.error(f"Error in historical tracking: {e}")
                import traceback
                st.error(traceback.format_exc())
            
            # Weekly Analysis Section
            st.markdown("---")
            st.subheader("📅 Weekly Stock Analysis")
            st.info("💡 Detailed weekly price tracking for all your stocks and mutual funds over the last 1 year")
            
            with st.expander("📊 View Weekly Analysis", expanded=False):
                try:
                    # Get all unique tickers
                    all_tickers = df['ticker'].unique()
                    
                    if len(all_tickers) > 0:
                        # Date range for 1 year back
                        end_date = pd.Timestamp.now()
                        start_date = end_date - timedelta(days=365)  # 1 year = 365 days
                        
                        # Generate weekly date range (Mondays)
                        weekly_dates = pd.date_range(start=start_date, end=end_date, freq='W-MON')
                        
                        st.info(f"📅 Tracking {len(all_tickers)} holdings over {len(weekly_dates)} weeks (1 year)")
                        
                        # Collect weekly data for all tickers using bulk database queries
                        st.info("📊 Loading weekly data from cache...")
                        weekly_data = []
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        # Import database function for bulk queries
                        from database_config_supabase import get_stock_prices_range_supabase
                        
                        for idx, ticker in enumerate(all_tickers):
                            status_text.text(f"Loading {ticker}... ({idx+1}/{len(all_tickers)})")
                            
                            ticker_data = df[df['ticker'] == ticker].iloc[0]
                            stock_name = ticker_data.get('stock_name', ticker)
                            
                            # Get all prices for this ticker in one bulk query
                            start_date_str = weekly_dates[0].strftime('%Y-%m-%d')
                            end_date_str = weekly_dates[-1].strftime('%Y-%m-%d')
                            
                            cached_prices = get_stock_prices_range_supabase(ticker, start_date_str, end_date_str)
                            
                            if cached_prices:
                                # Use cached data
                                for price_record in cached_prices:
                                    weekly_data.append({
                                        'Date': pd.to_datetime(price_record['price_date']),
                                        'Ticker': ticker,
                                        'Stock Name': stock_name,
                                        'Price': float(price_record['price'])
                                    })
                            else:
                                # Fallback: Fetch from API if not in cache
                                st.warning(f"⚠️ No cached data for {ticker}, fetching from API...")
                                for week_date in weekly_dates:
                                    week_price = self.fetch_historical_price_for_week(ticker, week_date)
                                    
                                    if week_price and week_price > 0:
                                        weekly_data.append({
                                            'Date': week_date,
                                            'Ticker': ticker,
                                            'Stock Name': stock_name,
                                            'Price': week_price
                                        })
                            
                            progress_bar.progress((idx + 1) / len(all_tickers))
                        
                        progress_bar.empty()
                        status_text.empty()
                        
                        if weekly_data:
                            weekly_df = pd.DataFrame(weekly_data)
                            
                            # Create tabs for different views
                            tab1, tab2, tab3 = st.tabs(["📈 Price Movement", "📊 Performance Table", "🔍 Individual Stock"])
                            
                            with tab1:
                                st.subheader("📊 Stock Price Movement Overview")
                                
                                # Create interactive line chart
                                fig = go.Figure()
                                
                                for ticker in weekly_df['Ticker'].unique():
                                    ticker_weekly = weekly_df[weekly_df['Ticker'] == ticker]
                                    stock_name = ticker_weekly['Stock Name'].iloc[0]
                                    
                                    fig.add_trace(go.Scatter(
                                        x=ticker_weekly['Date'],
                                        y=ticker_weekly['Price'],
                                        mode='lines+markers',
                                        name=f"{stock_name} ({ticker})",
                                        hovertemplate=f"<b>{stock_name}</b><br>Date: %{{x}}<br>Price: ₹%{{y:.2f}}<extra></extra>"
                                    ))
                                
                                fig.update_layout(
                                    title="Weekly Price Movement - All Holdings",
                                    xaxis_title="Week",
                                    yaxis_title="Price (₹)",
                                    hovermode='x unified',
                                    height=600,
                                    showlegend=True,
                                    legend=dict(
                                        yanchor="top",
                                        y=0.99,
                                        xanchor="left",
                                        x=0.01
                                    )
                                )
                                
                                st.plotly_chart(fig, config={'displayModeBar': True, 'responsive': True})
                                
                                # Download option
                                csv = weekly_df.to_csv(index=False)
                                st.download_button(
                                    label="📥 Download Weekly Data",
                                    data=csv,
                                    file_name=f"weekly_analysis_{datetime.now().strftime('%Y%m%d')}.csv",
                                    mime="text/csv"
                                )
                            
                            with tab2:
                                st.subheader("📊 Weekly Performance Comparison")
                                
                                # Calculate performance metrics
                                comparison_data = []
                                
                                for ticker in weekly_df['Ticker'].unique():
                                    ticker_weekly = weekly_df[weekly_df['Ticker'] == ticker].sort_values('Date')
                                    
                                    if len(ticker_weekly) >= 2:
                                        first_price = ticker_weekly['Price'].iloc[0]
                                        last_price = ticker_weekly['Price'].iloc[-1]
                                        max_price = ticker_weekly['Price'].max()
                                        min_price = ticker_weekly['Price'].min()
                                        avg_price = ticker_weekly['Price'].mean()
                                        
                                        price_change = last_price - first_price
                                        price_change_pct = (price_change / first_price) * 100 if first_price > 0 else 0
                                        
                                        comparison_data.append({
                                            'Ticker': ticker,
                                            'Stock Name': ticker_weekly['Stock Name'].iloc[0],
                                            'Start Price': f"₹{first_price:.2f}",
                                            'Current Price': f"₹{last_price:.2f}",
                                            'Highest': f"₹{max_price:.2f}",
                                            'Lowest': f"₹{min_price:.2f}",
                                            'Average': f"₹{avg_price:.2f}",
                                            'Change': f"₹{price_change:+.2f}",
                                            'Change %': f"{price_change_pct:+.2f}%",
                                            'Sort': price_change_pct
                                        })
                                
                                if comparison_data:
                                    comp_df = pd.DataFrame(comparison_data)
                                    comp_df = comp_df.sort_values('Sort', ascending=False)
                                    comp_df = comp_df.drop('Sort', axis=1)
                                    
                                    st.dataframe(
                                        comp_df,
                                        use_container_width=True,
                                        hide_index=True
                                    )
                                    
                                    # Best and worst performers
                                    col1, col2 = st.columns(2)
                                    
                                    with col1:
                                        if len(comp_df) > 0:
                                            st.success(f"🏆 Best Performer: {comp_df.iloc[0]['Stock Name']} ({comp_df.iloc[0]['Change %']})")
                                    
                                    with col2:
                                        if len(comp_df) > 0:
                                            st.error(f"📉 Worst Performer: {comp_df.iloc[-1]['Stock Name']} ({comp_df.iloc[-1]['Change %']})")
                                else:
                                    st.info("No comparison data available")
                            
                            with tab3:
                                st.subheader("Individual Stock Weekly Analysis")
                                
                                selected_ticker = st.selectbox(
                                    "Select a stock/MF to analyze",
                                    all_tickers,
                                    format_func=lambda x: f"{df[df['ticker']==x]['stock_name'].iloc[0]} ({x})" if len(df[df['ticker']==x]) > 0 else x,
                                    key="weekly_ticker_select"
                                )
                                
                                if selected_ticker and weekly_data:
                                    ticker_weekly = weekly_df[weekly_df['Ticker'] == selected_ticker].sort_values('Date')
                                    
                                    if not ticker_weekly.empty:
                                        # Individual stock chart
                                        fig_individual = go.Figure()
                                        
                                        fig_individual.add_trace(go.Scatter(
                                            x=ticker_weekly['Date'],
                                            y=ticker_weekly['Price'],
                                            mode='lines+markers',
                                            name=ticker_weekly['Stock Name'].iloc[0],
                                            line=dict(color='green', width=3),
                                            marker=dict(size=8),
                                            fill='tonexty',
                                            hovertemplate="Week: %{x}<br>Price: ₹%{y:.2f}<extra></extra>"
                                        ))
                                        
                                        fig_individual.update_layout(
                                            title=f"{ticker_weekly['Stock Name'].iloc[0]} - Weekly Performance",
                                            xaxis_title="Week",
                                            yaxis_title="Price (₹)",
                                            hovermode='x unified',
                                            height=500
                                        )
                                        
                                        st.plotly_chart(fig_individual, config={'displayModeBar': True, 'responsive': True})
                                        
                                        # Statistics
                                        col1, col2, col3, col4, col5 = st.columns(5)
                                        
                                        with col1:
                                            st.metric("Start Price", f"₹{ticker_weekly['Price'].iloc[0]:.2f}")
                                        
                                        with col2:
                                            st.metric("Current Price", f"₹{ticker_weekly['Price'].iloc[-1]:.2f}")
                                        
                                        with col3:
                                            st.metric("Highest", f"₹{ticker_weekly['Price'].max():.2f}")
                                        
                                        with col4:
                                            st.metric("Lowest", f"₹{ticker_weekly['Price'].min():.2f}")
                                        
                                        with col5:
                                            st.metric("Average", f"₹{ticker_weekly['Price'].mean():.2f}")
                                        
                                        # Detailed data table
                                        st.subheader("Weekly Price Data")
                                        st.dataframe(
                                            ticker_weekly[['Date', 'Price']].sort_values('Date', ascending=False),
                                            use_container_width=True,
                                            hide_index=True
                                        )
                                    else:
                                        st.warning(f"No weekly data available for {selected_ticker}")
                        else:
                            st.warning("No weekly data available")
                    else:
                        st.info("No holdings found in portfolio")
                        
                except Exception as e:
                    st.error(f"Error in weekly analysis: {e}")
                    import traceback
                    st.error(traceback.format_exc())
                

    
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
    
    def get_available_functions(self):
        """Define functions that AI can call"""
        return {
            "fetch_all_prices": {
                "function": lambda: self.bulk_fetch_and_cache_all_prices(self.session_state.user_id, show_ui=True),
                "description": "Fetch ALL prices (historical, weekly, live) for all holdings using AI in one batch. Use when user asks to update prices, refresh data, or get latest prices.",
                "parameters": {}
            },
            "process_csv_file": {
                "function": lambda file: self.process_csv_file(file, self.session_state.user_id),
                "description": "Process uploaded CSV transaction file and add to portfolio. Use when user uploads CSV file or asks to import transactions.",
                "parameters": {"file": "uploaded_file_object"}
            },
            "refresh_portfolio": {
                "function": lambda: self.load_portfolio_data(self.session_state.user_id, force_refresh=True),
                "description": "Refresh portfolio data from database. Use when user asks to refresh, reload, or update portfolio.",
                "parameters": {}
            },
            "get_price_for_ticker": {
                "function": lambda ticker, name: self.get_single_ticker_price_ai(ticker, name),
                "description": "Get current price for a specific ticker/stock/mutual fund using AI. Use when user asks about price of specific stock/fund.",
                "parameters": {"ticker": "ticker_code", "name": "stock_name"}
            }
        }
    
    def get_single_ticker_price_ai(self, ticker, name):
        """Helper to get single ticker price using AI (returns {'date', 'price', 'sector'})"""
        from ai_price_fetcher import AIPriceFetcher
        ai_fetcher = AIPriceFetcher()
        if ai_fetcher.is_available():
            # Detect type
            if str(ticker).isdigit():
                result = ai_fetcher.get_mutual_fund_nav(ticker, name)
                if result and isinstance(result, dict):
                    return {
                        "ticker": ticker,
                        "price": result.get('price'),
                        "date": result.get('date'),
                        "sector": result.get('sector'),
                        "type": "Mutual Fund"
                    }
            else:
                result = ai_fetcher.get_stock_price(ticker, name)
                if result and isinstance(result, dict):
                    return {
                        "ticker": ticker,
                        "price": result.get('price'),
                        "date": result.get('date'),
                        "sector": result.get('sector'),
                        "type": "Stock"
                    }
        return {"error": "AI not available"}
    
    def process_ai_query_with_db_access(self, user_query, uploaded_files=None):
        """Process AI query with full database access + FUNCTION CALLING capability"""
        try:
            # Add user message to chat history
            st.session_state.chat_history.append({"role": "user", "content": user_query})
            
            # Get complete portfolio data from database
            from database_config_supabase import get_transactions_supabase
            
            user_id = self.session_state.user_id
            transactions = get_transactions_supabase(user_id=user_id)
            
            # Prepare rich context with database data
            context_data = {
                "total_transactions": len(transactions) if transactions else 0,
                "portfolio_summary": {},
                "conversation_history": st.session_state.chat_history[:-1]  # All messages except current
            }
            
            if self.session_state.portfolio_data is not None:
                df = self.session_state.portfolio_data
                context_data["portfolio_summary"] = {
                    "total_invested": float(df['invested_amount'].sum()),
                    "current_value": float(df['current_value'].sum()),
                    "total_pnl": float(df['unrealized_pnl'].sum()),
                    "pnl_percentage": float((df['unrealized_pnl'].sum() / df['invested_amount'].sum()) * 100) if df['invested_amount'].sum() > 0 else 0,
                    "total_stocks": len(df['ticker'].unique()),
                    "holdings": df[['ticker', 'stock_name', 'quantity', 'invested_amount', 'current_value', 'unrealized_pnl', 'pnl_percentage']].to_dict('records'),
                    "top_performers": df.nlargest(5, 'unrealized_pnl')[['ticker', 'stock_name', 'unrealized_pnl', 'pnl_percentage']].to_dict('records'),
                    "worst_performers": df.nsmallest(5, 'unrealized_pnl')[['ticker', 'stock_name', 'unrealized_pnl', 'pnl_percentage']].to_dict('records'),
                    "sector_allocation": df.groupby('sector')['invested_amount'].sum().to_dict() if 'sector' in df.columns else {},
                    "channel_allocation": df.groupby('channel')['invested_amount'].sum().to_dict() if 'channel' in df.columns else {}
                }
            
            # Process and save uploaded files (PDFs, CSVs, TXT)
            file_content = ""
            csv_files_to_process = []
            
            if uploaded_files:
                with st.spinner("📄 Processing documents..."):
                    import base64
                    for file in uploaded_files:
                        # 🆕 Handle CSV files
                        if file.name.endswith('.csv'):
                            csv_files_to_process.append(file)
                            file_content += f"\n\n--- CSV File: {file.name} (will be processed) ---\n"
                            st.info(f"📊 CSV file detected: {file.name} - Will process transactions")
                            continue
                        
                        # Extract text from file
                        if file.type == "application/pdf":
                            pdf_bytes = file.read()
                            extracted_text = self.extract_text_from_pdf(pdf_bytes)
                            
                            # Save to database if PDF storage is available
                            if PDF_STORAGE_AVAILABLE:
                                try:
                                    file_content_b64 = base64.b64encode(pdf_bytes).decode('utf-8')
                                    save_pdf_document_supabase(
                                        user_id=user_id,
                                        filename=file.name,
                                        file_content=file_content_b64,
                                        extracted_text=extracted_text,
                                        is_global=False
                                    )
                                    st.success(f"✅ Saved {file.name} to library")
                                except Exception as e:
                                    st.warning(f"⚠️ Could not save {file.name}: {str(e)[:50]}")
                            
                            file_content += f"\n\n--- {file.name} ---\n{extracted_text}"
                            
                            # Show extraction stats
                            if extracted_text and extracted_text != "[No text could be extracted from PDF]":
                                st.success(f"✅ Extracted {len(extracted_text)} characters from {file.name}")
                            else:
                                st.warning(f"⚠️ Could not extract text from {file.name} - PDF might be image-based")
                        else:
                            # For text files
                            text = str(file.read(), "utf-8")
                            file_content += f"\n\n--- {file.name} ---\n{text}"
                    
                    if file_content:
                        st.success(f"✅ Processed {len(uploaded_files)} document(s) - Total {len(file_content)} characters")
            
            # Load previously uploaded PDFs for this user (if available)
            if PDF_STORAGE_AVAILABLE:
                try:
                    stored_pdfs = get_pdf_documents_supabase(user_id, include_global=True)
                    if stored_pdfs:
                        st.info(f"📚 Using {len(stored_pdfs)} stored document(s) from your library")
                        for pdf in stored_pdfs:
                            if pdf.get('extracted_text'):
                                file_content += f"\n\n--- Stored: {pdf['filename']} ---\n{pdf['extracted_text'][:2000]}"  # Limit to 2000 chars per doc
                except Exception as e:
                    print(f"⚠️ Could not load stored PDFs: {e}")
            
            # Build conversation context for ChatGPT-style interaction
            conversation_messages = []
            
            # Compact portfolio context (only top 20 holdings to save tokens)
            holdings_compact = ""
            if context_data['portfolio_summary'].get('holdings'):
                top_holdings = context_data['portfolio_summary']['holdings'][:20]  # Limit to 20
                for h in top_holdings:
                    holdings_compact += f"{h.get('ticker')}({h.get('stock_name','')}): ₹{h.get('unrealized_pnl',0):,.0f}({h.get('pnl_percentage',0):.1f}%)|"
            
            # Ultra-compact system prompt
            system_prompt = f"""Portfolio Analyst. Data:
Invested: ₹{context_data['portfolio_summary'].get('total_invested', 0):,.0f}
Current: ₹{context_data['portfolio_summary'].get('current_value', 0):,.0f}  
P&L: ₹{context_data['portfolio_summary'].get('total_pnl', 0):,.0f} ({context_data['portfolio_summary'].get('pnl_percentage', 0):.1f}%)
Holdings: {context_data['portfolio_summary'].get('total_stocks', 0)}

Top: {holdings_compact[:500]}

Functions: fetch_all_prices(), refresh_portfolio(), process_csv_file(0), get_price_for_ticker(ticker,name)
Call: FUNCTION_CALL: function_name(params)"""

            conversation_messages.append({"role": "system", "content": system_prompt})
            
            # Add conversation history (last 5 messages to save tokens)
            for msg in st.session_state.chat_history[-6:-1]:  # Reduced from 11 to 6
                conversation_messages.append(msg)
            
            # Add current user message with compact file content
            current_message = user_query
            if file_content:
                # Ultra-compact file content (first 3000 chars only)
                current_message += f"\n\nDocs: {file_content[:3000]}{'...' if len(file_content) > 3000 else ''}"
            
            conversation_messages.append({"role": "user", "content": current_message})
            
            # Generate AI response using Gemini with conversation context
            with st.spinner("🤔 Analyzing your portfolio..."):
                ai_response = self.generate_conversational_response(conversation_messages, "Google Gemini 2.5 Flash (Fast)")
            
            # 🆕 PARSE FUNCTION CALLS from AI response
            function_results = []
            if "FUNCTION_CALL:" in ai_response:
                import re
                function_calls = re.findall(r'FUNCTION_CALL:\s*(\w+)\((.*?)\)', ai_response)
                
                for func_name, params_str in function_calls:
                    st.info(f"🤖 AI is calling function: {func_name}({params_str})")
                    
                    try:
                        # Execute function based on name
                        if func_name == "fetch_all_prices":
                            with st.spinner("⏳ Fetching all prices..."):
                                self.bulk_fetch_and_cache_all_prices(self.session_state.user_id, show_ui=True)
                            function_results.append(f"✅ Successfully fetched all prices")
                        
                        elif func_name == "refresh_portfolio":
                            with st.spinner("⏳ Refreshing portfolio..."):
                                self.load_portfolio_data(self.session_state.user_id, force_refresh=True)
                            function_results.append(f"✅ Portfolio refreshed successfully")
                            st.rerun()  # Reload page to show updated data
                        
                        elif func_name == "process_csv_file":
                            # Extract file index
                            file_idx = int(params_str.strip())
                            if csv_files_to_process and file_idx < len(csv_files_to_process):
                                csv_file = csv_files_to_process[file_idx]
                                with st.spinner(f"⏳ Processing {csv_file.name}..."):
                                    success = self.process_csv_file(csv_file, self.session_state.user_id)
                                    if success:
                                        function_results.append(f"✅ Successfully processed {csv_file.name}")
                                        # Auto-fetch prices after CSV processing
                                        st.info("🤖 Auto-fetching prices for new transactions...")
                                        self.bulk_fetch_and_cache_all_prices(self.session_state.user_id, show_ui=False)
                                        st.success("✅ Prices cached!")
                                    else:
                                        function_results.append(f"❌ Failed to process {csv_file.name}")
                            else:
                                function_results.append(f"❌ CSV file index {file_idx} not found")
                        
                        elif func_name == "get_price_for_ticker":
                            # Extract ticker and name
                            params = [p.strip().strip("'\"") for p in params_str.split(',')]
                            if len(params) >= 2:
                                ticker, name = params[0], params[1]
                                with st.spinner(f"⏳ Fetching price for {ticker}..."):
                                    result = self.get_single_ticker_price_ai(ticker, name)
                                    if 'error' in result:
                                        function_results.append(f"❌ {result['error']}")
                                    else:
                                        function_results.append(f"✅ {result['type']} {ticker}: ₹{result['price']}")
                            else:
                                function_results.append(f"❌ Invalid parameters for get_price_for_ticker")
                        
                        else:
                            function_results.append(f"❌ Unknown function: {func_name}")
                    
                    except Exception as func_error:
                        function_results.append(f"❌ Error executing {func_name}: {str(func_error)}")
                
                # Show function results
                if function_results:
                    st.markdown("### 🔧 Function Execution Results:")
                    for result in function_results:
                        if result.startswith("✅"):
                            st.success(result)
                        else:
                            st.error(result)
                
                # Remove FUNCTION_CALL tags from display
                ai_response = re.sub(r'FUNCTION_CALL:\s*\w+\(.*?\)', '', ai_response).strip()
            
            # Add AI response to chat history
            st.session_state.chat_history.append({"role": "assistant", "content": ai_response})
            
            # Show response in main area
            st.success("✅ AI Response:")
            st.markdown(ai_response)
            
        except Exception as e:
            error_msg = f"Error processing AI query: {e}"
            st.error(error_msg)
            import traceback
            st.error(traceback.format_exc())
            st.session_state.chat_history.append({"role": "assistant", "content": f"❌ {error_msg}"})
    
    def generate_conversational_response(self, conversation_messages, ai_model="Google Gemini 2.5 Flash (Fast)"):
        """Generate conversational AI response like ChatGPT with full context"""
        try:
            if ai_model in ["Google Gemini 2.5 Flash (Fast)", "Google Gemini 2.5 Pro (Advanced)"]:
                # Use Gemini
                api_key = st.session_state.gemini_api_key
                if not api_key:
                    return "❌ Gemini API key not configured"
                
                genai.configure(api_key=api_key)
                
                # Try different Gemini models
                model_names = ['gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-2.0-flash', 'gemini-flash-latest']
                model = None
                
                for model_name in model_names:
                    try:
                        model = genai.GenerativeModel(model_name)
                        break
                    except:
                        continue
                
                if not model:
                    return "❌ No working Gemini model found"
                
                # Convert conversation to Gemini format
                # Gemini uses a simpler format - combine system + history into context
                full_context = ""
                user_message = ""
                
                for msg in conversation_messages:
                    if msg["role"] == "system":
                        full_context += f"SYSTEM CONTEXT:\n{msg['content']}\n\n"
                    elif msg["role"] == "user":
                        user_message = msg['content']
                        if len(conversation_messages) > 2:  # If there's history
                            full_context += f"Previous User: {msg['content']}\n"
                    elif msg["role"] == "assistant":
                        full_context += f"Previous Assistant: {msg['content']}\n"
                
                # Final prompt with full context
                final_prompt = f"{full_context}\n\nCurrent User Question: {user_message}\n\nProvide a detailed, helpful response:"
                
                # Generate response
                response = model.generate_content(final_prompt)
                return response.text
                
            else:
                # Use OpenAI ChatGPT
                from openai import OpenAI
                api_key = st.session_state.openai_api_key
                if not api_key:
                    return "❌ OpenAI API key not configured"
                
                client = OpenAI(api_key=api_key)
                
                # ChatGPT natively supports conversation format
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=conversation_messages,
                    temperature=0.7,
                    max_tokens=500  # Reduced from 2000 to save costs
                )
                
                return response.choices[0].message.content
                
        except Exception as e:
            return f"❌ Error generating response: {str(e)}"
    
    def render_ai_assistant_page(self):
        """Render AI Assistant page as a clean chatbot with database access"""
        st.header("🤖 AI Portfolio Assistant")
        st.markdown("*Ask me anything about your portfolio - I have access to your complete investment data*")
        
        # Initialize session state for chat
        if 'chat_history' not in st.session_state:
            st.session_state.chat_history = []
        
        # Check API key status
        if not st.session_state.gemini_api_key:
            st.warning("⚠️ AI Assistant needs API key configuration")
            if st.button("🔑 Configure Gemini API Key"):
                st.session_state.show_gemini_config = True
            return
        
        # File Upload Section (collapsible)
        with st.expander("📁 Upload Stock Analysis PDFs (Optional)", expanded=False):
            uploaded_files = st.file_uploader(
                "Upload stock analysis reports, research PDFs, or financial documents",
                type=['pdf', 'txt', 'csv'],
                accept_multiple_files=True,
                help="Upload documents for the AI to analyze along with your portfolio data"
            )
            
            if uploaded_files:
                st.success(f"✅ {len(uploaded_files)} file(s) uploaded")
                for file in uploaded_files:
                    st.write(f"📄 {file.name}")
        
        # Chat Interface
        st.markdown("---")
        
        # Display chat history
        chat_container = st.container()
        with chat_container:
            if not st.session_state.chat_history:
                st.info("👋 Hi! I'm your AI portfolio assistant. I have access to your complete investment data including stocks, mutual funds, PMS, and transactions. Ask me anything!")
            
            for message in st.session_state.chat_history:
                if message["role"] == "user":
                    with st.chat_message("user"):
                        st.markdown(message['content'])
                else:
                    with st.chat_message("assistant"):
                        st.markdown(message['content'])
        
        # Chat input
        user_input = st.chat_input(
            "Ask me anything about your portfolio...",
            key="chat_input"
        )
        
        if user_input:
            # Process the query
            self.process_ai_query_with_db_access(user_input, uploaded_files if 'uploaded_files' in locals() else None)
            st.rerun()
        
        # Quick action buttons
        st.markdown("---")
        st.markdown("**💡 Quick Actions:**")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("📊 Portfolio Summary", use_container_width=True):
                self.process_ai_query_with_db_access("Give me a comprehensive summary of my portfolio including total value, best performers, and allocation")
                st.rerun()
        
        with col2:
            if st.button("📈 Best Performers", use_container_width=True):
                self.process_ai_query_with_db_access("What are my top 5 best performing investments and why?")
                st.rerun()
        
        with col3:
            if st.button("⚠️ Risk Analysis", use_container_width=True):
                self.process_ai_query_with_db_access("Analyze the risk in my portfolio and suggest improvements")
                st.rerun()
        
        with col4:
            if st.button("🗑️ Clear Chat", use_container_width=True):
                st.session_state.chat_history = []
                st.rerun()
    
    def process_ai_query(self, user_input, uploaded_files=None, current_page=None, ai_model="Google Gemini 2.5 Flash (Fast)"):
        """Process user query with AI assistant"""
        try:
            # Check rate limit based on selected model
            import time
            current_time = time.time()
            
            if ai_model in ["Google Gemini 2.5 Flash (Fast)", "Google Gemini 2.5 Pro (Advanced)"]:
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

                    # Test OCR functionality first
                    ocr_working = self.test_ocr_functionality()
                    if not ocr_working:
                        status_text.text("⚠️ OCR may not be available - PDF text extraction might fail...")
                        st.warning("⚠️ OCR functionality not detected. PDF processing may not work for image-based documents.")

                    file_content = self.process_uploaded_files(uploaded_files)

                    progress_bar.progress(1.0)

                    # Show results
                    if "OCR extraction failed" in file_content or "[No text could be extracted" in file_content:
                        status_text.text("⚠️ PDF processing had issues - some content may be missing")
                        st.warning("⚠️ PDF processing encountered issues. If the PDF contains images with text, OCR may not be working properly.")
                    else:
                        status_text.text("✅ PDF processing complete!")
                        st.success("✅ PDF content extracted successfully")

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
            
            # Don't rerun - let Streamlit handle natural UI updates
            # This prevents unnecessary page reloads when asking AI questions
            
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

                        # Try to extract embedded images and perform OCR
                        try:
                            # Get page dimensions for cropping
                            page_width, page_height = page.width, page.height

                            # Try to find image objects in the page
                            if hasattr(page, 'objects'):
                                for obj in page.objects:
                                    if obj.get('type') == 'image':
                                        try:
                                            # Extract the image
                                            img_data = obj.get('data')
                                            if img_data:
                                                # Convert to PIL Image
                                                img = Image.open(io.BytesIO(img_data))
                                                # Perform OCR
                                                ocr_text = pytesseract.image_to_string(img, lang='eng')
                                                if ocr_text and ocr_text.strip():
                                                    extracted_text.append(f"Page {page_num} Embedded Image (OCR):\n{ocr_text.strip()}\n")
                                        except Exception as ocr_error:
                                            pass
                        except Exception as img_error:
                            pass
            except Exception as e:
                print(f"pdfplumber extraction failed: {str(e)}")

            # Method 2: Fallback to PyPDF2 if pdfplumber fails
            if not extracted_text:
                try:
                    pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
                    for page_num, page in enumerate(pdf_reader.pages, 1):
                        text = page.extract_text()
                        if text and text.strip():
                            extracted_text.append(f"Page {page_num} (PyPDF2):\n{text.strip()}\n")
                except Exception as e:
                    print(f"PyPDF2 extraction failed: {str(e)}")

            # Method 3: Convert entire PDF to images and perform OCR (most reliable for image-heavy PDFs)
            try:
                # Use higher DPI for better OCR accuracy
                pdf_images = convert_from_bytes(pdf_bytes, dpi=200)  # Reduced from 300 for speed

                for page_num, img in enumerate(pdf_images, 1):
                    try:
                        # Pre-process image for better OCR (convert to grayscale, enhance contrast)
                        img_gray = img.convert('L')
                        img_enhanced = img_gray.point(lambda x: 0 if x < 128 else 255, '1')  # Binarize

                        # Perform OCR with multiple configuration options
                        ocr_text = pytesseract.image_to_string(img_enhanced, lang='eng', config='--psm 6')

                        if ocr_text and ocr_text.strip() and len(ocr_text.strip()) > 20:  # Filter out very short results
                            extracted_text.append(f"Page {page_num} (Full Page OCR):\n{ocr_text.strip()}\n")
                            print(f"✅ OCR successful for page {page_num} - extracted {len(ocr_text.strip())} characters")
                        else:
                            # Try original image if enhanced version didn't work
                            ocr_text_orig = pytesseract.image_to_string(img, lang='eng', config='--psm 3')
                            if ocr_text_orig and ocr_text_orig.strip() and len(ocr_text_orig.strip()) > 20:
                                extracted_text.append(f"Page {page_num} (Full Page OCR - Original):\n{ocr_text_orig.strip()}\n")
                                print(f"✅ OCR successful for page {page_num} (original) - extracted {len(ocr_text_orig.strip())} characters")
                    except Exception as ocr_error:
                        print(f"OCR failed for page {page_num}: {str(ocr_error)}")

            except Exception as e:
                print(f"Full page OCR conversion failed: {str(e)}")

        except Exception as e:
            print(f"PDF processing error: {str(e)}")
            return f"[Error processing PDF: {str(e)}]"

        # Combine all extracted text
        result = "\n".join(extracted_text) if extracted_text else "[No text could be extracted from PDF]"

        # Log the result for debugging
        if result == "[No text could be extracted from PDF]":
            print("⚠️ No text extracted from PDF - may be image-based or corrupted")
        else:
            print(f"✅ PDF processing complete - extracted {len(result)} characters")

        return result

    def test_ocr_functionality(self):
        """Test if OCR functionality is working"""
        try:
            # Create a simple test image
            test_img = Image.new('RGB', (100, 30), color='white')
            # This should work if OCR dependencies are installed
            test_text = pytesseract.image_to_string(test_img, lang='eng')
            return True
        except Exception as e:
            print(f"OCR test failed: {e}")
            return False

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

                    if extracted_content and extracted_content != "[No text could be extracted from PDF]" and len(extracted_content) > 50:
                        file_content += f"PDF Content (with OCR):\n{extracted_content}"
                    else:
                        # Show warning if OCR failed
                        file_content += f"PDF Content: [OCR extraction failed or insufficient text extracted. PDF may be image-based or corrupted.]"
                else:
                    file_content += f"File type {file.type} - content extraction not supported yet"
            
            return file_content
            
        except Exception as e:
            st.error(f"❌ Error processing files: {e}")
            return ""
    
    def generate_ai_response(self, user_input, context_data, file_content="", ai_model="Google Gemini 2.5 Flash (Fast)"):
        """Generate AI response using selected AI model"""
        try:
            if ai_model in ["Google Gemini 2.5 Flash (Fast)", "Google Gemini 2.5 Pro (Advanced)"]:
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
                
                # Try the newer Gemini 2.5 models that are actually available
                model = None
                model_names_to_try = [
                    'gemini-2.5-flash',  # Fast and efficient
                    'gemini-2.5-pro',    # Advanced analysis
                    'gemini-2.0-flash',  # Alternative fast model
                    'gemini-2.0-pro-exp', # Experimental pro model
                    'gemini-flash-latest', # Latest flash
                    'gemini-pro-latest'   # Latest pro
                ]
                
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
                        # First fetch live prices and sectors (force refresh)
                        self.fetch_live_prices_and_sectors(user_id, force_refresh=True)
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
                    self.fetch_live_prices_and_sectors(user_id, force_refresh=True)
                    st.success("Live prices updated!")
        
        with col3:
            if st.button("🧹 Clear Cache"):
                if 'live_prices' in self.session_state:
                    del self.session_state['live_prices']

                # Also clear the fetch flags and timestamps so prices will be refetched
                fetch_keys_to_clear = [key for key in self.session_state.keys() if key.startswith('prices_fetched_') or key.startswith('prices_last_fetch_')]
                for key in fetch_keys_to_clear:
                    del self.session_state[key]

                st.success("Cache and fetch flags cleared!")
        
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
    
    def render_weekly_values(self, ticker, user_id, context="default"):
        """
        Render weekly price values chart for a specific ticker (single mode)
        """
        # Call multi-select version with single ticker
        self.render_weekly_values_multi([ticker], user_id, context=context)
    
    def render_weekly_values_multi(self, tickers, user_id, context="default"):
        """
        Render weekly price values chart for multiple tickers (comparative mode)
        
        Args:
            tickers: List of stock/MF ticker symbols
            user_id: User ID for fetching data
            context: Unique context identifier to prevent duplicate keys (e.g., "sector", "channel", "overall")
        """
        try:
            from database_config_supabase import get_stock_prices_range_supabase
            import plotly.graph_objects as go
            from datetime import datetime, timedelta
            from pms_aif_fetcher import is_pms_code, is_aif_code
            import hashlib
            
            if not tickers or len(tickers) == 0:
                st.warning("No tickers selected")
                return
            
            # Filter out PMS/AIF tickers - they don't have weekly price data
            pms_aif_tickers = []
            valid_tickers = []
            
            for ticker in tickers:
                ticker_str = str(ticker).strip()
                if is_pms_code(ticker_str) or is_aif_code(ticker_str) or 'PMS' in ticker_str.upper() or 'AIF' in ticker_str.upper():
                    pms_aif_tickers.append(ticker)
                else:
                    valid_tickers.append(ticker)
            
            # Handle PMS/AIF tickers separately
            if pms_aif_tickers:
                st.info(f"💡 **Note:** PMS/AIF investments don't have daily price tracking like stocks. " +
                       "They're valued based on fund manager performance reports.")
                
                # Show PMS/AIF performance summary instead of price chart
                self.render_pms_aif_summary(pms_aif_tickers, user_id)
            
            if not valid_tickers:
                # If ONLY PMS/AIF selected, we've already shown their summary above
                if pms_aif_tickers:
                    return
                else:
                    st.warning("⚠️ No holdings selected.")
                    return
            
            # Continue with only valid tickers for weekly chart
            tickers = valid_tickers
            
            # Calculate date range (last 1 year)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365)
            
            # Show status message
            with st.spinner(f"📊 Loading weekly price data for {len(tickers)} holding(s)..."):
                pass
            
            # Create the chart
            fig = go.Figure()
            
            # Colors for different lines
            colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
                     '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
            
            # Store statistics for each ticker
            all_stats = []
            tickers_with_data = []
            
            for idx, ticker in enumerate(tickers):
                # Get historical prices from database for date range
                prices_data = get_stock_prices_range_supabase(
                    ticker=ticker,
                    start_date=start_date.strftime('%Y-%m-%d'),
                    end_date=end_date.strftime('%Y-%m-%d')
                )
                
                if not prices_data or len(prices_data) == 0:
                    st.warning(f"⚠️ No historical price data available for **{ticker}**")
                    st.info(f"💡 Historical data for {ticker} may still be loading. Try refreshing the page or use the 'Refresh Cache' button in Settings.")
                    continue
                
                # Convert to DataFrame
                df_prices = pd.DataFrame(prices_data)
                
                # Ensure we have the required columns (handle both date and price_date naming)
                if 'price_date' in df_prices.columns:
                    df_prices['date'] = df_prices['price_date']
                
                if 'date' not in df_prices.columns or 'price' not in df_prices.columns:
                    continue
                
                # Sort by date
                df_prices['date'] = pd.to_datetime(df_prices['date'])
                df_prices = df_prices.sort_values('date')
                
                # Filter to last 52 weeks (1 year)
                one_year_ago = datetime.now() - timedelta(days=365)
                df_prices = df_prices[df_prices['date'] >= one_year_ago]
                
                if df_prices.empty:
                    continue
                
                # Add line to chart
                color = colors[idx % len(colors)]
                fig.add_trace(go.Scatter(
                    x=df_prices['date'],
                    y=df_prices['price'],
                    mode='lines+markers',
                    name=ticker,
                    line=dict(color=color, width=2),
                    marker=dict(size=4),
                    hovertemplate=f'<b>{ticker}</b><br>' +
                                 '<b>Date:</b> %{x|%Y-%m-%d}<br>' +
                                 '<b>Price:</b> ₹%{y:,.2f}<extra></extra>'
                ))
                
                # Calculate statistics
                min_price = df_prices['price'].min()
                max_price = df_prices['price'].max()
                avg_price = df_prices['price'].mean()
                latest_price = df_prices['price'].iloc[-1]
                first_price = df_prices['price'].iloc[0]
                price_change = ((latest_price - first_price) / first_price * 100) if first_price > 0 else 0
                
                all_stats.append({
                    'ticker': ticker,
                    'current': latest_price,
                    'min': min_price,
                    'max': max_price,
                    'avg': avg_price,
                    'change_pct': price_change,
                    'color': color
                })
                
                tickers_with_data.append(ticker)
            
            if len(tickers_with_data) == 0:
                st.error("❌ No weekly price data available for selected holdings")
                st.info("""
                💡 **To populate weekly price data for charts:**
                1. Go to **⚙️ Settings** in the sidebar
                2. Click **"🔄 Refresh Price Data"** button
                3. Wait for the cache to populate (~30 seconds)
                4. Return to this page to see the chart
                
                **Note:** Weekly price data is cached automatically after file upload, but may take a moment to populate.
                """)
                return
            
            # Update layout with better text visibility
            title = f"Price Comparison: {', '.join(tickers_with_data[:3])}"
            if len(tickers_with_data) > 3:
                title += f" and {len(tickers_with_data) - 3} more"
            
            fig.update_layout(
                title=dict(
                    text=title + " (Last 1 Year)",
                    font=dict(size=18, color='#262730')  # Dark text for visibility
                ),
                xaxis_title=dict(
                    text="Date",
                    font=dict(size=14, color='#262730')
                ),
                yaxis_title=dict(
                    text="Price (₹)",
                    font=dict(size=14, color='#262730')
                ),
                height=600,
                hovermode='x unified',
                showlegend=True,
                legend=dict(
                    yanchor="top",
                    y=0.99,
                    xanchor="left",
                    x=0.01,
                    bgcolor="rgba(255, 255, 255, 0.95)",  # More opaque white background
                    bordercolor="rgba(0, 0, 0, 0.2)",
                    borderwidth=1,
                    font=dict(size=12, color='#262730')  # Dark text in legend
                ),
                xaxis=dict(
                    rangeslider=dict(visible=False),  # Hidden to avoid looking like 2 graphs
                    type='date',
                    tickfont=dict(color='#262730')  # Dark tick labels
                ),
                yaxis=dict(
                    tickfont=dict(color='#262730')  # Dark tick labels
                ),
                plot_bgcolor='rgba(240, 242, 246, 0.5)',  # Light background
                paper_bgcolor='white',  # White paper background
                font=dict(color='#262730')  # Default font color
            )
            
            # Display chart with unique key including context, timestamp, and random component
            import time
            import random
            tickers_str = '_'.join(sorted(tickers_with_data[:5]))
            # Create a highly unique hash combining multiple factors
            timestamp = str(time.time())
            random_component = str(random.randint(1000, 9999))
            unique_string = f"{context}_{tickers_str}_{len(tickers_with_data)}_{timestamp}_{random_component}"
            unique_hash = hashlib.md5(unique_string.encode()).hexdigest()[:12]
            chart_key = f"weekly_chart_{context}_{unique_hash}"
            
            # Debug log
            print(f"🔑 Generated chart key: {chart_key}")
            
            st.plotly_chart(fig, use_container_width=True, key=chart_key)
            
            # Display statistics for each ticker
            if len(all_stats) > 0:
                st.markdown("### 📈 Price Statistics (Last 52 Weeks)")
                
                # Create expandable sections for each ticker
                for stat in all_stats:
                    with st.expander(f"📊 {stat['ticker']}", expanded=(len(all_stats) == 1)):
                        col1, col2, col3, col4, col5 = st.columns(5)
                        
                        with col1:
                            st.metric("Current", f"₹{stat['current']:,.2f}")
                        with col2:
                            st.metric("Min (52W)", f"₹{stat['min']:,.2f}")
                        with col3:
                            st.metric("Max (52W)", f"₹{stat['max']:,.2f}")
                        with col4:
                            st.metric("Average", f"₹{stat['avg']:,.2f}")
                        with col5:
                            delta_color = "normal" if stat['change_pct'] >= 0 else "inverse"
                            st.metric("1Y Change", f"{stat['change_pct']:.2f}%", 
                                    delta=f"{stat['change_pct']:.2f}%", delta_color=delta_color)
            
        except Exception as e:
            st.error(f"Error rendering weekly values: {e}")
            print(f"❌ Error in render_weekly_values_multi: {e}")
            import traceback
            traceback.print_exc()
    
    def render_pms_aif_summary(self, tickers, user_id):
        """
        Render performance summary for PMS/AIF investments
        
        Args:
            tickers: List of PMS/AIF ticker symbols
            user_id: User ID for fetching data
        """
        try:
            import plotly.graph_objects as go
            from datetime import datetime
            
            st.subheader("📊 PMS/AIF Performance Summary")
            
            # Get portfolio data for these tickers
            if self.session_state.portfolio_data is None:
                st.warning("Portfolio data not available")
                return
            
            df = self.session_state.portfolio_data
            pms_aif_data = df[df['ticker'].isin(tickers)].copy()
            
            if pms_aif_data.empty:
                st.warning("No data found for selected PMS/AIF investments")
                return
            
            # Check if values are showing 0% return (indicates SEBI data fetch failed)
            if 'unrealized_pnl' in pms_aif_data.columns:
                zero_pnl_count = (pms_aif_data['unrealized_pnl'] == 0).sum()
                if zero_pnl_count > 0:
                    st.info("""
                    💡 **Note:** Some PMS/AIF values may be estimated using conservative CAGR rates (10-12%) 
                    because real-time SEBI data is currently unavailable. Values shown are approximations.
                    
                    **Why?** SEBI website might be temporarily down, or the investment name doesn't match the SEBI database exactly.
                    """)
            
            
            # Aggregate by ticker
            summary = pms_aif_data.groupby('ticker').agg({
                'stock_name': 'first',
                'invested_amount': 'sum',
                'current_value': 'sum',
                'unrealized_pnl': 'sum',
                'date': 'min'  # First investment date
            }).reset_index()
            
            summary['pnl_percentage'] = (summary['unrealized_pnl'] / summary['invested_amount'] * 100)
            summary['holding_days'] = (datetime.now() - pd.to_datetime(summary['date'])).dt.days
            
            # Display as cards
            for idx, row in summary.iterrows():
                with st.expander(f"📈 {row['stock_name']}", expanded=True):
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Invested", f"₹{row['invested_amount']:,.0f}")
                    with col2:
                        st.metric("Current Value", f"₹{row['current_value']:,.0f}")
                    with col3:
                        pnl_delta = f"+₹{row['unrealized_pnl']:,.0f}" if row['unrealized_pnl'] >= 0 else f"-₹{abs(row['unrealized_pnl']):,.0f}"
                        st.metric("Profit/Loss", pnl_delta, 
                                delta=f"{row['pnl_percentage']:.2f}%",
                                delta_color="normal" if row['unrealized_pnl'] >= 0 else "inverse")
                    with col4:
                        st.metric("Holding Period", f"{row['holding_days']} days")
                    
                    # Calculate estimated CAGR
                    years = row['holding_days'] / 365.25
                    if years > 0 and row['invested_amount'] > 0:
                        cagr = ((row['current_value'] / row['invested_amount']) ** (1/years) - 1) * 100
                        
                        # Show CAGR visualization
                        st.markdown(f"**Estimated CAGR:** {cagr:.2f}% per annum")
                        
                        # Create a simple value progression chart
                        investment_date = pd.to_datetime(row['date'])
                        months_held = int(row['holding_days'] / 30)
                        
                        if months_held > 1:
                            # Generate monthly progression based on CAGR
                            dates = pd.date_range(start=investment_date, periods=min(months_held, 60), freq='M')
                            values = []
                            
                            for i, date in enumerate(dates):
                                days_elapsed = (date - investment_date).days
                                years_elapsed = days_elapsed / 365.25
                                estimated_value = row['invested_amount'] * ((1 + cagr/100) ** years_elapsed)
                                values.append(estimated_value)
                            
                            # Add current value as final point
                            dates = dates.tolist() + [datetime.now()]
                            values = values + [row['current_value']]
                            
                            # Create chart
                            fig = go.Figure()
                            
                            # Add value progression line
                            fig.add_trace(go.Scatter(
                                x=dates,
                                y=values,
                                mode='lines+markers',
                                name='Estimated Value',
                                line=dict(color='#2E86AB', width=3),
                                marker=dict(size=6),
                                fill='tonexty',
                                hovertemplate='<b>Date:</b> %{x|%b %Y}<br><b>Value:</b> ₹%{y:,.0f}<extra></extra>'
                            ))
                            
                            # Add initial investment line
                            fig.add_hline(
                                y=row['invested_amount'],
                                line_dash="dash",
                                line_color="gray",
                                annotation_text=f"Initial: ₹{row['invested_amount']:,.0f}",
                                annotation_position="left"
                            )
                            
                            fig.update_layout(
                                title=f"Value Progression (Estimated based on {cagr:.2f}% CAGR)",
                                xaxis_title="Date",
                                yaxis_title="Value (₹)",
                                height=400,
                                hovermode='x unified',
                                showlegend=False
                            )
                            
                            # Generate unique key with timestamp
                            import time
                            import random
                            unique_suffix = f"{time.time()}_{random.randint(1000,9999)}"
                            chart_key = f"pms_aif_progression_{row['ticker']}_{unique_suffix}"
                            st.plotly_chart(fig, use_container_width=True, key=chart_key)
                    
                    st.markdown("---")
                    st.caption("💡 Values are estimated based on fund manager reports and may not reflect exact real-time NAV")
            
            # If multiple PMS/AIF, show comparison chart
            if len(summary) > 1:
                st.markdown("---")
                st.subheader("📊 Performance Comparison")
                
                fig_compare = go.Figure()
                
                # Add bar chart for P&L percentage
                fig_compare.add_trace(go.Bar(
                    x=summary['stock_name'],
                    y=summary['pnl_percentage'],
                    marker_color=['green' if x >= 0 else 'red' for x in summary['pnl_percentage']],
                    text=summary['pnl_percentage'].round(2),
                    textposition='auto',
                    texttemplate='%{text}%',
                    hovertemplate='<b>%{x}</b><br>Return: %{y:.2f}%<extra></extra>'
                ))
                
                fig_compare.update_layout(
                    title="PMS/AIF Return Comparison",
                    xaxis_title="Investment",
                    yaxis_title="Return %",
                    height=400,
                    showlegend=False
                )
                
                # Generate unique key with timestamp
                import time
                import random
                unique_suffix = f"{time.time()}_{random.randint(1000,9999)}"
                chart_key = f"pms_aif_comparison_bar_{unique_suffix}"
                st.plotly_chart(fig_compare, use_container_width=True, key=chart_key)
        
        except Exception as e:
            st.error(f"Error rendering PMS/AIF summary: {e}")
            print(f"❌ Error in render_pms_aif_summary: {e}")
            import traceback
            traceback.print_exc()
    
    def run(self):
        """Main run method"""
        # Check authentication status
        if not self.session_state.get('user_authenticated', False):
            self.render_login_page()
        else:
            self.render_main_dashboard()

# Main execution
if __name__ == "__main__":
    # ============================================================================
    # AI & BULK INTEGRATION DIAGNOSTICS
    # ============================================================================
    st.write("---")
    st.subheader("🔍 System Diagnostics (Startup)")
    
    diag_col1, diag_col2 = st.columns(2)
    
    with diag_col1:
        st.caption("**1. API Keys Status**")
        try:
            gemini_key = st.secrets.get("gemini_api_key") or st.secrets.get("google_api_key")
            openai_key = st.secrets.get("open_ai")
            
            if gemini_key:
                st.success(f"✅ Gemini: {gemini_key[:15]}...")
            else:
                st.error("❌ Gemini: Not found")
            
            if openai_key:
                st.success(f"✅ OpenAI: {openai_key[:15]}...")
            else:
                st.error("❌ OpenAI: Not found")
        except Exception as e:
            st.error(f"❌ Secrets error: {e}")
    
    with diag_col2:
        st.caption("**2. AI & Bulk Status**")
        try:
            from ai_price_fetcher import AIPriceFetcher
            ai = AIPriceFetcher()
            
            if ai.is_available():
                if ai.gemini_client:
                    st.success("✅ AI: Gemini Active")
                elif ai.openai_client:
                    st.success("✅ AI: OpenAI Active")
            else:
                st.error("❌ AI: Not Available")
        except Exception as e:
            st.error(f"❌ AI Error: {e}")
        
        if BULK_FETCH_AVAILABLE:
            st.success("✅ Bulk: Enabled")
        else:
            st.error("❌ Bulk: Disabled")
    
    st.write("---")
    
    # ============================================================================
    # Initialize the portfolio analytics system
    app = PortfolioAnalytics()
    
    # Run the application
    app.run()
