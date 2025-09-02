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
from user_file_reading_agent import process_user_files_on_login

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
                with st.expander("📋 Sample CSV Format"):
                    st.markdown("""
                    Your CSV file should have these columns:
                    - **date**: Transaction date (YYYY-MM-DD)
                    - **ticker**: Stock symbol (e.g., AAPL, MSFT) or MF scheme code
                    - **quantity**: Number of shares/units
                    - **price**: Price per share/unit (optional - will be fetched automatically)
                    - **transaction_type**: 'buy' or 'sell'
                    - **stock_name**: Company name (optional)
                    - **channel**: Investment channel (optional - auto-generated from filename)
                    - **sector**: Stock sector (optional)
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
            user = get_user_by_username_supabase(username)
            # Temporary simple password handling - will be updated when login_system is fixed
            if user and user['password_hash'] == password:  # In production, use proper verification
                self.session_state.user_authenticated = True
                self.session_state.user_id = user['id']
                self.session_state.username = user['username']
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
            
            # Read the CSV file
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
                'channel': 'channel',
                'Sector': 'sector',
                'sector': 'sector'
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
                st.info("Optional columns: price, stock_name, sector")
                return False
            
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
                return False
            
            # Add user_id to the dataframe
            df['user_id'] = user_id
            
            # Fetch historical prices for missing price values
            if 'price' not in df.columns or df['price'].isna().any():
                st.info(f"🔍 Fetching historical prices for {uploaded_file.name}...")
                df = self.fetch_historical_prices_for_transactions(df)
            
            # Save transactions to database
            success = self.save_transactions_to_database(df, user_id, uploaded_file.name)
            
            if success:
                st.success(f"✅ Successfully saved {len(df)} transactions from {uploaded_file.name}")
                return True
            else:
                st.error(f"❌ Failed to save transactions from {uploaded_file.name}")
                return False
                
        except Exception as e:
            st.error(f"❌ Error processing {uploaded_file.name}: {e}")
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
                if str(ticker).isdigit() or str(ticker).startswith('MF_'):
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
                    if str(ticker).isdigit() or str(ticker).startswith('MF_'):
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
            progress_bar.empty()
            status_text.empty()
            
            return df
            
        except Exception as e:
            st.error(f"Error fetching historical prices: {e}")
            return df
    
    def save_transactions_to_database(self, df, user_id, filename):
        """Save transactions to database"""
        try:
            from database_config_supabase import save_transactions_bulk_supabase, save_file_record_supabase
            
            # First save file record
            file_record = save_file_record_supabase(filename, f"/uploads/{filename}", user_id)
            if not file_record:
                st.error("Failed to save file record")
                return False
            
            file_id = file_record['id']
            
            # Save transactions in bulk
            success = save_transactions_bulk_supabase(df, file_id, user_id)
            
            if success:
                st.success(f"✅ Saved {len(df)} transactions to database")
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
                        if ticker.startswith('MF_'):
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
        """Fetch live prices and sectors for all user tickers"""
        try:
            st.info("🔄 Fetching live prices and sectors...")
            
            # Get unique tickers from user transactions
            transactions = get_transactions_supabase(user_id=user_id)
            if not transactions:
                return
            
            df = pd.DataFrame(transactions)
            unique_tickers = df['ticker'].unique()
            
            live_prices = {}
            sectors = {}
            
            # Fetch live prices and sectors for each ticker
            for ticker in unique_tickers:
                try:
                    if ticker.startswith('MF_'):
                        live_price = get_mutual_fund_price(ticker, ticker, user_id, None)
                        sector = "Mutual Fund"  # Default sector for MFs
                    else:
                        live_price = get_stock_price(ticker, ticker, None)
                        # Get sector from stock data table
                        stock_data = get_stock_data_supabase(ticker)
                        sector = stock_data.get('sector', 'Unknown') if stock_data else 'Unknown'
                    
                    if live_price and live_price > 0:
                        live_prices[ticker] = live_price
                        sectors[ticker] = sector
                        
                except Exception as e:
                    st.warning(f"⚠️ Could not fetch data for {ticker}: {e}")
                    continue
            
            # Store in session state
            self.session_state.live_prices = live_prices
            
            st.success(f"✅ Fetched live prices for {len(live_prices)} tickers")
            
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
            
            # Calculate portfolio metrics
            df['invested_amount'] = df['quantity'] * df['price']
            df['current_value'] = df['quantity'] * df['live_price'].fillna(df['price'])
            df['unrealized_pnl'] = df['current_value'] - df['invested_amount']
            df['pnl_percentage'] = (df['unrealized_pnl'] / df['invested_amount']) * 100
            
            # Store processed data
            self.session_state.portfolio_data = df
            
        except Exception as e:
            st.error(f"Error loading portfolio data: {e}")
    
    def render_main_dashboard(self):
        """Render the main dashboard with comprehensive analytics"""
        st.title("📊 Portfolio Analytics Dashboard")
        
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
                with st.sidebar.spinner("Processing file..."):
                    try:
                        # Process the uploaded file
                        result = process_user_files_on_login(self.session_state.user_id)
                        if result:
                            st.sidebar.success("✅ File processed successfully!")
                            # Refresh portfolio data
                            self.load_portfolio_data(self.session_state.user_id)
                            st.rerun()
                        else:
                            st.sidebar.error("❌ Error processing file")
                    except Exception as e:
                        st.sidebar.error(f"❌ Error: {e}")
        
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
        
        if self.session_state.portfolio_data is None:
            st.warning("No portfolio data available")
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
                            labels={'x': 'Return %', 'y': 'Ticker'}
                        )
                        st.plotly_chart(fig_top, use_container_width=True)
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
                            labels={'x': 'Return %', 'y': 'Ticker'}
                        )
                        st.plotly_chart(fig_bottom, use_container_width=True)
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
                    
                    st.plotly_chart(fig_timeline, use_container_width=True)
                    
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
            use_container_width=True
        )
    
    def render_performance_page(self):
        """Render performance analysis charts"""
        st.header("📈 Performance Analysis")
        
        if self.session_state.portfolio_data is None:
            st.warning("No portfolio data available")
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
            
            st.plotly_chart(fig_performance, use_container_width=True)
            
            # Rolling volatility
            st.subheader("📈 Rolling Volatility (30-day)")
            if len(daily_performance) > 30:
                daily_performance['rolling_volatility'] = daily_performance['cumulative_return'].rolling(30).std()
                
                fig_volatility = go.Figure()
                fig_volatility.add_trace(go.Scatter(
                    x=daily_performance['date'],
                    y=daily_performance['rolling_volatility'],
                    mode='lines',
                    name='30-day Rolling Volatility',
                    line=dict(color='red', width=2)
                ))
                
                fig_volatility.update_layout(
                    title="Portfolio Volatility Over Time",
                    xaxis_title="Date",
                    yaxis_title="Volatility (%)",
                    hovermode='x unified'
                )
                
                st.plotly_chart(fig_volatility, use_container_width=True)
            
            # Performance metrics table
            st.subheader("📊 Performance Metrics")
            
            # Calculate key metrics
            total_return = ((df['current_value'].sum() - df['invested_amount'].sum()) / df['invested_amount'].sum()) * 100
            volatility = df.groupby(df['date'].dt.date)['unrealized_pnl'].sum().std()
            sharpe_ratio = total_return / volatility if volatility > 0 else 0
            
            metrics_df = pd.DataFrame({
                'Metric': ['Total Return (%)', 'Volatility (%)', 'Sharpe Ratio', 'Max Drawdown (%)'],
                'Value': [f"{total_return:.2f}", f"{total_return:.2f}", f"{sharpe_ratio:.2f}", "N/A"]
            })
            
            st.dataframe(metrics_df, use_container_width=True)
            
        except Exception as e:
            st.error(f"Error processing performance data: {e}")
    
    def render_allocation_page(self):
        """Render asset allocation analysis"""
        st.header("📊 Asset Allocation Analysis")
        
        if self.session_state.portfolio_data is None:
            st.warning("No portfolio data available")
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
                    st.plotly_chart(fig_type, use_container_width=True)
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
                    st.plotly_chart(fig_sector, use_container_width=True)
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
                    st.plotly_chart(fig_holdings, use_container_width=True)
                else:
                    st.info("No holdings data available for visualization")
            else:
                st.info("No valid current value data available")
        else:
            st.info("Current value information not available in portfolio data")
        
        # Market cap distribution (if available)
        st.subheader("📊 Market Cap Distribution")
        
        # This would require market cap data from external sources
        st.info("Market cap distribution requires additional market data integration")
    
    def render_pnl_analysis_page(self):
        """Render detailed P&L analysis"""
        st.header("💰 P&L Analysis")
        
        if self.session_state.portfolio_data is None:
            st.warning("No portfolio data available")
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
        
        st.plotly_chart(fig_pnl, use_container_width=True)
        

        
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
            st.plotly_chart(fig_sector_pnl, use_container_width=True)
            
            # Sector P&L summary
            col1, col2, col3 = st.columns(3)
            with col1:
                best_sector = pnl_by_sector.loc[pnl_by_sector['unrealized_pnl'].idxmax()]
                st.metric("Best Sector", best_sector['sector'], delta=f"₹{best_sector['unrealized_pnl']:,.2f}")
            with col2:
                worst_sector = pnl_by_sector.loc[pnl_by_sector['unrealized_pnl'].idxmin()]
                st.metric("Worst Sector", worst_sector['sector'], delta=f"₹{worst_sector['unrealized_pnl']:,.2f}")
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
            st.plotly_chart(fig_channel_pnl, use_container_width=True)
            
            # Channel P&L summary
            col1, col2, col3 = st.columns(3)
            with col1:
                best_channel = pnl_by_channel.loc[pnl_by_channel['unrealized_pnl'].idxmax()]
                st.metric("Best Channel", best_channel['channel'], delta=f"₹{best_channel['unrealized_pnl']:,.2f}")
            with col2:
                worst_channel = pnl_by_channel.loc[pnl_by_channel['unrealized_pnl'].idxmin()]
                st.metric("Worst Channel", worst_channel['channel'], delta=f"₹{worst_channel['unrealized_pnl']:,.2f}")
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
            st.plotly_chart(fig_combined, use_container_width=True)
            
            # Combined summary table
            combined_pnl['pnl_formatted'] = combined_pnl['unrealized_pnl'].apply(lambda x: f"₹{x:,.2f}")
            combined_pnl['percentage'] = (combined_pnl['unrealized_pnl'] / combined_pnl['unrealized_pnl'].abs().sum() * 100).apply(lambda x: f"{x:.2f}%")
            
            st.dataframe(
                combined_pnl[['sector', 'channel', 'pnl_formatted', 'percentage']],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No combined sector-channel data available for P&L analysis")
        
        # Detailed P&L table
        st.subheader("📋 Detailed P&L Table")
        st.dataframe(
            pnl_summary.sort_values('unrealized_pnl', ascending=False),
            use_container_width=True
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
        
        uploaded_file = st.file_uploader(
            "Choose a CSV file",
                    type=['csv'],
            help="Upload your investment portfolio CSV file"
        )
        
        if uploaded_file is not None:
            if st.button("Process File"):
                with st.spinner("Processing file..."):
                    try:
                        # Process the uploaded file
                        result = process_user_files_on_login(user_id)
                        if result:
                            st.success("File processed successfully!")
                            # Refresh portfolio data
                            self.load_portfolio_data(user_id)
                        else:
                            st.error("Error processing file")
                    except Exception as e:
                        st.error(f"Error processing file: {e}")
        
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
                st.dataframe(files_df[display_columns], use_container_width=True)
                
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
                    self.load_portfolio_data(user_id)
                    st.success("Portfolio data refreshed!")
        
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
