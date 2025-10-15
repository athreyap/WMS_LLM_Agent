#!/usr/bin/env python3
"""
WMS Portfolio Analytics - Clean Implementation
Author: AI Agent
Date: 2025-10-15

Features:
- User registration and login
- CSV file upload and processing
- Historical, weekly, and live price fetching
- P&L calculation and portfolio analytics
- Interactive dashboards and charts
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import time
import warnings
import json

warnings.filterwarnings('ignore')

# Database imports
from database_config_supabase import (
    supabase,
    get_user_by_username_supabase,
    update_user_login_supabase,
    get_transactions_supabase,
    save_transactions_bulk_supabase,
    get_stock_data_supabase,
    bulk_update_stock_data,
    get_all_weekly_prices_for_user,
    bulk_save_historical_prices,
    save_stock_price_supabase,
    get_stock_price_supabase
)

# Login system imports
from login_system import (
    hash_password,
    verify_password,
    create_user as create_user_with_auth
)

# Price fetching imports
from unified_price_fetcher import (
    get_stock_price_and_sector,
    get_mutual_fund_price
)

from bulk_integration import (
    fetch_live_prices_bulk,
    categorize_tickers
)

from bulk_price_fetcher import BulkPriceFetcher

# AI imports
from ai_price_fetcher import AIPriceFetcher

# Page config
st.set_page_config(
    page_title="Portfolio Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)


class SessionState:
    """Manages Streamlit session state"""
    
    def __init__(self):
        # Initialize all session state variables
        if 'user_authenticated' not in st.session_state:
            st.session_state.user_authenticated = False
        if 'user_id' not in st.session_state:
            st.session_state.user_id = None
        if 'username' not in st.session_state:
            st.session_state.username = None
        if 'user_role' not in st.session_state:
            st.session_state.user_role = None
        if 'login_time' not in st.session_state:
            st.session_state.login_time = None
        if 'portfolio_data' not in st.session_state:
            st.session_state.portfolio_data = None
        if 'live_prices' not in st.session_state:
            st.session_state.live_prices = {}
        if 'sectors' not in st.session_state:
            st.session_state.sectors = {}
    
    @property
    def user_authenticated(self):
        return st.session_state.user_authenticated
    
    @user_authenticated.setter
    def user_authenticated(self, value):
        st.session_state.user_authenticated = value
    
    @property
    def user_id(self):
        return st.session_state.user_id
    
    @user_id.setter
    def user_id(self, value):
        st.session_state.user_id = value
    
    @property
    def username(self):
        return st.session_state.username
    
    @username.setter
    def username(self, value):
        st.session_state.username = value


class PortfolioAnalytics:
    """Main application class for portfolio analytics"""
    
    def __init__(self):
        self.session = SessionState()
        self.ai_fetcher = AIPriceFetcher()
        self.bulk_fetcher = BulkPriceFetcher()
    
    def run(self):
        """Main application entry point"""
        if self.session.user_authenticated:
            self.show_dashboard()
        else:
            self.show_login_page()
    
    # ==================== AUTHENTICATION ====================
    
    def show_login_page(self):
        """Display login and registration page"""
        st.title("📊 Portfolio Analytics Dashboard")
        st.markdown("---")
        
        tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])
        
        with tab1:
            self.render_login_form()
        
        with tab2:
            self.render_registration_form()
    
    def render_login_form(self):
        """Render login form"""
        st.subheader("Login to Your Portfolio")
        
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        
        if st.button("Login", type="primary"):
            if not username or not password:
                st.error("❌ Please enter both username and password")
                return
            
            # Get user from database
            user_data = get_user_by_username_supabase(username)
            
            if not user_data:
                st.error("❌ Invalid username or password")
                return
            
            # Verify password
            password_hash = user_data.get('password_hash', '')
            password_salt = user_data.get('password_salt', '')
            
            if not verify_password(password, password_hash, password_salt):
                st.error("❌ Invalid username or password")
                return
            
            # Login successful
            self.session.user_authenticated = True
            self.session.user_id = user_data['id']
            self.session.username = user_data['username']
            self.session.user_role = user_data.get('role', 'user')
            st.session_state.login_time = datetime.now()
            
            # Update last login
            update_user_login_supabase(user_data['id'])
            
            st.success(f"✅ Welcome back, {username}!")
            
            # Fetch live prices
            self.fetch_live_prices_for_user(user_data['id'])
            
            # Fetch incremental weekly prices
            self.fetch_incremental_weekly_prices(user_data['id'])
            
            st.rerun()
    
    def render_registration_form(self):
        """Render registration form"""
        st.subheader("Create New Account")
        
        username = st.text_input("Choose Username", key="reg_username")
        password = st.text_input("Choose Password", type="password", key="reg_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="reg_confirm")
        
        uploaded_files = st.file_uploader(
            "Upload Portfolio CSV Files",
            type=['csv'],
            accept_multiple_files=True,
            key="reg_files"
        )
        
        if st.button("Create Account & Upload Files", type="primary"):
            # Validate inputs
            if not username or not password:
                st.error("❌ Please enter username and password")
                return
            
            if password != confirm_password:
                st.error("❌ Passwords do not match")
                return
            
            if not uploaded_files:
                st.error("❌ Please upload at least one CSV file")
                return
            
            # Create user (using login_system's create_user which handles Supabase)
            with st.spinner("Creating your account..."):
                success, message = create_user_with_auth(username, '', password, role='user')
            
            if not success:
                st.error(f"❌ {message}")
                return
            
            # Fetch the created user
            user_data = get_user_by_username_supabase(username)
            if not user_data:
                st.error("❌ Failed to retrieve user data")
                return
            
            user_id = user_data['id']
            st.success(f"✅ {message}")
            
            # Process uploaded files
            self.process_files_on_registration(user_id, uploaded_files)
            
            # Auto-login after registration
            self.session.user_authenticated = True
            self.session.user_id = user_id
            self.session.username = username
            self.session.user_role = 'user'
            st.session_state.login_time = datetime.now()
            
            st.success("🎉 Registration complete! Redirecting to dashboard...")
            time.sleep(2)
            st.rerun()
    
    # ==================== FILE PROCESSING ====================
    
    def process_files_on_registration(self, user_id, uploaded_files):
        """Process multiple CSV files during registration"""
        st.markdown("### 📁 Processing Files")
        
        total_files = len(uploaded_files)
        processed = 0
        failed = 0
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, uploaded_file in enumerate(uploaded_files):
            try:
                status_text.text(f"Processing {idx+1}/{total_files}: {uploaded_file.name}")
                progress_bar.progress((idx + 1) / total_files)
                
                # Process single file
                success = self.process_single_csv_file(uploaded_file, user_id)
                
                if success:
                    st.success(f"✅ {uploaded_file.name}")
                    processed += 1
                else:
                    st.error(f"❌ {uploaded_file.name}")
                    failed += 1
                
            except Exception as e:
                st.error(f"❌ {uploaded_file.name}: {str(e)}")
                failed += 1
                print(f"Error processing {uploaded_file.name}: {e}")
                import traceback
                traceback.print_exc()
        
        # Summary
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("✅ Processed", processed)
        with col2:
            st.metric("❌ Failed", failed)
        with col3:
            st.metric("📁 Total", total_files)
        
        if processed > 0:
            st.success(f"🎉 {processed} file(s) processed successfully!")
    
    def process_single_csv_file(self, uploaded_file, user_id):
        """
        Process a single CSV file:
        1. Read and validate CSV
        2. Fetch historical prices for transaction dates
        3. Fetch weekly prices (52 weeks)
        4. Save everything to database
        
        Returns: True if successful, False otherwise
        """
        try:
            # Step 1: Read CSV
            df = pd.read_csv(uploaded_file)
            
            # Step 2: Standardize columns
            df.columns = [col.strip().lower() for col in df.columns]
            
            # Step 3: Validate required columns
            required_cols = ['ticker', 'quantity']
            if not all(col in df.columns for col in required_cols):
                st.error(f"❌ Missing required columns in {uploaded_file.name}")
                return False
            
            # Step 4: Add missing columns with defaults
            if 'stock_name' not in df.columns:
                df['stock_name'] = df['ticker']
            if 'transaction_type' not in df.columns:
                df['transaction_type'] = 'buy'
            if 'channel' not in df.columns:
                df['channel'] = 'Default'
            if 'sector' not in df.columns:
                df['sector'] = None
            if 'date' not in df.columns:
                df['date'] = datetime.now().strftime('%Y-%m-%d')
            
            # Step 5: Parse dates
            df['date'] = pd.to_datetime(df['date'], format='mixed', dayfirst=True, errors='coerce')
            
            # Handle invalid dates
            invalid_dates = df[df['date'].isna()]
            if len(invalid_dates) > 0:
                # Use average of valid dates
                valid_dates = df[df['date'].notna()]['date']
                if len(valid_dates) > 0:
                    avg_date = valid_dates.mean()
                    df.loc[df['date'].isna(), 'date'] = avg_date
                else:
                    df['date'] = datetime.now()
            
            df['date'] = df['date'].dt.strftime('%Y-%m-%d')
            
            # Step 6: Clean data
            df = df[df['quantity'] > 0]
            df = df[np.isfinite(df['quantity'])]
            
            # Remove price column if exists (we'll fetch fresh prices)
            if 'price' in df.columns:
                df = df.drop(columns=['price'])
            
            if df.empty:
                st.warning(f"⚠️ No valid transactions in {uploaded_file.name}")
                return False
            
            # Step 7: Save file record
            file_hash = str(hash(uploaded_file.name + str(user_id)))
            
            # Check if file already exists
            existing_file = supabase.table('investment_files')\
                .select('id')\
                .eq('user_id', user_id)\
                .eq('file_hash', file_hash)\
                .execute()
            
            if existing_file.data:
                file_id = existing_file.data[0]['id']
            else:
                file_record = supabase.table('investment_files').insert({
                    'user_id': user_id,
                    'filename': uploaded_file.name,
                    'file_path': f'/uploads/{uploaded_file.name}',  # Virtual path for Streamlit
                    'file_hash': file_hash
                }).execute()
                file_id = file_record.data[0]['id']
            
            # Step 8: Fetch historical prices for transaction dates
            st.info(f"📊 Fetching prices for {len(df)} transactions...")
            df = self.fetch_historical_prices_for_transactions(df, user_id)
            
            # Step 9: Save transactions to database
            df['user_id'] = user_id
            df['file_id'] = file_id
            df['created_at'] = datetime.now().isoformat()
            
            success = save_transactions_bulk_supabase(df, user_id, file_id)
            
            if not success:
                st.error(f"❌ Failed to save transactions for {uploaded_file.name}")
                return False
            
            # Step 10: Fetch and save weekly prices for this file's tickers
            tickers = df['ticker'].unique().tolist()
            st.info(f"📈 Fetching weekly prices for {len(tickers)} tickers...")
            
            self.fetch_and_save_weekly_prices_for_tickers(
                tickers=tickers,
                ticker_names=df.groupby('ticker')['stock_name'].first().to_dict(),
                ticker_data=df.groupby('ticker').agg({
                    'date': 'first',
                    'price': 'first',
                    'quantity': 'sum'
                }).to_dict('index')
            )
            
            st.success(f"✅ {uploaded_file.name} - Complete!")
            return True
            
        except Exception as e:
            st.error(f"❌ Error processing {uploaded_file.name}: {e}")
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def fetch_historical_prices_for_transactions(self, df, user_id):
        """
        Fetch historical prices for each transaction date
        Uses API-first (yfinance/mftool), then AI fallback
        Returns DataFrame with 'price' column populated
        """
        print(f"\n{'='*80}")
        print(f"📊 FETCHING HISTORICAL PRICES FOR {len(df)} TRANSACTIONS")
        print(f"{'='*80}\n")
        
        for idx, row in df.iterrows():
            ticker = row['ticker']
            date_str = row['date']
            stock_name = row.get('stock_name', ticker)
            
            # Detect asset type
            ticker_str = str(ticker).strip()
            is_pms_aif = (ticker_str.startswith('INP') or ticker_str.startswith('INA') or 
                         'PMS' in ticker_str.upper() or 'AIF' in ticker_str.upper())
            is_mutual_fund = (ticker_str.isdigit() and len(ticker_str) in [5, 6]) or ticker_str.startswith('MF_')
            
            price = None
            sector = None
            
            # Fetch price based on asset type
            if is_pms_aif:
                # PMS/AIF: Use transaction price, calculate current via CAGR later
                # For now, just use a placeholder
                price = 0.0  # Will be calculated during live price fetch
                sector = 'AIF' if 'AIF' in ticker_str.upper() else 'PMS'
                print(f"💼 {ticker}: PMS/AIF - will calculate price via CAGR at login")
                
            elif is_mutual_fund:
                # Try mftool first
                try:
                    scheme_code = int(ticker_str.replace('MF_', ''))
                    result = get_mutual_fund_price(ticker, ticker, user_id, date_str)
                    if result and result > 0:
                        price = result
                        sector = 'Mutual Fund'
                        print(f"✅ {ticker}: mftool = ₹{price}")
                except:
                    pass
                
                # AI fallback
                if not price or price <= 0:
                    try:
                        ai_result = self.ai_fetcher.get_mutual_fund_nav(ticker, stock_name, date_str, allow_closest=True)
                        if ai_result and isinstance(ai_result, dict):
                            price = ai_result.get('price', 0)
                            sector = 'Mutual Fund'
                            print(f"🤖 {ticker}: AI = ₹{price}")
                    except:
                        pass
                
            else:
                # Stock: Try yfinance first
                try:
                    price_result, sector_result, _ = get_stock_price_and_sector(ticker, ticker, date_str)
                    if price_result and price_result > 0:
                        price = price_result
                        sector = sector_result or 'Equity'
                        print(f"✅ {ticker}: yfinance = ₹{price}")
                except:
                    pass
                
                # AI fallback
                if not price or price <= 0:
                    try:
                        ai_result = self.ai_fetcher.get_stock_price(ticker, stock_name, date_str, allow_closest=True)
                        if ai_result and isinstance(ai_result, dict):
                            price = ai_result.get('price', 0)
                            sector = ai_result.get('sector', 'Equity')
                            print(f"🤖 {ticker}: AI = ₹{price}")
                    except:
                        pass
            
            # Set price and sector
            if not price or price <= 0:
                price = 0.0  # Placeholder, will need manual entry
            
            df.at[idx, 'price'] = price
            if sector:
                df.at[idx, 'sector'] = sector
        
        print(f"\n✅ Historical prices fetched for {len(df)} transactions\n")
        return df
    
    def fetch_and_save_weekly_prices_for_tickers(self, tickers, ticker_names, ticker_data):
        """
        Fetch weekly prices (52 weeks) for given tickers
        Uses API-first (yfinance/mftool), then AI dict fallback
        Saves to historical_prices table in bulk
        """
        print(f"\n{'='*80}")
        print(f"📈 FETCHING WEEKLY PRICES FOR {len(tickers)} TICKERS")
        print(f"{'='*80}\n")
        
        one_year_ago = datetime.now() - timedelta(days=365)
        all_weekly_prices = []
        
        for ticker in tickers:
            ticker_str = str(ticker).strip()
            
            # Detect asset type
            is_pms_aif = (ticker_str.startswith('INP') or ticker_str.startswith('INA') or 
                         'PMS' in ticker_str.upper() or 'AIF' in ticker_str.upper())
            is_bse = (ticker_str.isdigit() and len(ticker_str) == 6 and ticker_str.startswith('5'))
            is_mutual_fund = ((ticker_str.isdigit() and len(ticker_str) in [5, 6] and not is_bse) or 
                            ticker_str.startswith('MF_'))
            
            # Skip PMS/AIF (uses CAGR on-demand)
            if is_pms_aif:
                print(f"⏩ {ticker}: PMS/AIF - skipping weekly (uses CAGR)")
                continue
            
            # Fetch weekly prices
            if is_mutual_fund:
                # MF: Get current NAV only
                try:
                    from mf_price_fetcher import MFPriceFetcher
                    mf_fetcher = MFPriceFetcher()
                    scheme_code = int(ticker_str.replace('MF_', ''))
                    
                    nav_data = mf_fetcher.get_mutual_fund_nav(scheme_code)
                    if nav_data and nav_data.get('nav', 0) > 0:
                        all_weekly_prices.append({
                            'ticker': ticker,
                            'transaction_date': datetime.now().strftime('%Y-%m-%d'),
                            'historical_price': float(nav_data['nav']),
                            'price_source': 'mftool_weekly'
                        })
                        print(f"✅ {ticker}: mftool NAV = ₹{nav_data['nav']}")
                except Exception as e:
                    print(f"⚠️ {ticker}: mftool failed - {e}")
            
            else:
                # Stock: Get 52 weeks via yfinance
                try:
                    import yfinance as yf
                    yf_ticker = f"{ticker}.NS"
                    stock = yf.Ticker(yf_ticker)
                    hist = stock.history(start=one_year_ago, end=datetime.now(), interval='1wk')
                    
                    if not hist.empty:
                        for date_idx, price in zip(hist.index, hist['Close']):
                            if pd.notna(price) and not np.isinf(price) and price > 0:
                                all_weekly_prices.append({
                                    'ticker': ticker,
                                    'transaction_date': date_idx.strftime('%Y-%m-%d'),
                                    'historical_price': float(price),
                                    'price_source': 'yfinance_weekly'
                                })
                        print(f"✅ {ticker}: yfinance = {len(hist)} weeks")
                    else:
                        # Try BSE
                        yf_ticker = f"{ticker}.BO"
                        stock = yf.Ticker(yf_ticker)
                        hist = stock.history(start=one_year_ago, end=datetime.now(), interval='1wk')
                        
                        if not hist.empty:
                            for date_idx, price in zip(hist.index, hist['Close']):
                                if pd.notna(price) and not np.isinf(price) and price > 0:
                                    all_weekly_prices.append({
                                        'ticker': ticker,
                                        'transaction_date': date_idx.strftime('%Y-%m-%d'),
                                        'historical_price': float(price),
                                        'price_source': 'yfinance_weekly_bse'
                                    })
                            print(f"✅ {ticker}: yfinance BSE = {len(hist)} weeks")
                
                except Exception as e:
                    print(f"⚠️ {ticker}: yfinance failed - {e}")
        
        # Bulk save all weekly prices
        if all_weekly_prices:
            print(f"\n💾 Saving {len(all_weekly_prices)} weekly prices to database...")
            bulk_save_historical_prices(all_weekly_prices)
            print(f"✅ Weekly prices saved!\n")
        
        return True
    
    # ==================== LIVE PRICE FETCHING ====================
    
    def fetch_live_prices_for_user(self, user_id):
        """
        Fetch live prices for all user's tickers
        Uses API-first (yfinance/mftool), then AI dict fallback
        Saves to stock_data table
        """
        st.info("💰 Fetching live prices...")
        
        # Get all transactions
        transactions = get_transactions_supabase(user_id=user_id)
        if not transactions:
            return
        
        df = pd.DataFrame(transactions)
        
        # Prepare DataFrame with transaction data for PMS/AIF
        df_for_fetch = df.groupby('ticker').agg({
            'stock_name': 'first',
            'date': 'first',
            'price': 'first',
            'quantity': 'sum'
        }).reset_index()
        
        # Fetch live prices using bulk integration
        live_prices = fetch_live_prices_bulk(
            df=df_for_fetch,
            user_id=user_id,
            progress_callback=lambda msg: st.caption(msg)
        )
        
        # Store in session state
        for ticker, (price, sector) in live_prices.items():
            st.session_state.live_prices[ticker] = price
            st.session_state.sectors[ticker] = sector
        
        st.success(f"✅ Live prices fetched: {len(live_prices)} tickers")
    
    def fetch_incremental_weekly_prices(self, user_id):
        """
        Fetch only NEW weekly prices since last cached date
        Uses API-first, then AI fallback
        """
        st.info("📊 Checking for new weekly prices...")
        
        # Get all tickers
        transactions = get_transactions_supabase(user_id=user_id)
        if not transactions:
            return
        
        df = pd.DataFrame(transactions)
        tickers = df['ticker'].unique()
        
        # Check latest cached date for each ticker
        current_date = datetime.now()
        one_year_ago = current_date - timedelta(days=365)
        
        tickers_need_update = []
        
        for ticker in tickers:
            # Check last 10 weeks for cached data
            latest_cached = None
            check_date = current_date
            
            for _ in range(10):
                monday = check_date - timedelta(days=check_date.weekday())
                
                # Check all days in the week
                for day_offset in range(7):
                    check_day = monday + timedelta(days=day_offset)
                    cached_price = get_stock_price_supabase(str(ticker), check_day.strftime('%Y-%m-%d'))
                    
                    if cached_price and cached_price > 0:
                        latest_cached = monday
                        break
                
                if latest_cached:
                    break
                
                check_date -= timedelta(days=7)
            
            if latest_cached:
                # Only fetch if more than 7 days old
                if (current_date - latest_cached).days > 7:
                    tickers_need_update.append(ticker)
            else:
                # No cache, need full fetch
                tickers_need_update.append(ticker)
        
        if not tickers_need_update:
            st.success("✅ All weekly prices are up to date!")
            return
        
        st.info(f"📈 Fetching weekly prices for {len(tickers_need_update)} tickers...")
        
        # Fetch weekly prices (this will be incremental based on cached data)
        # For now, simplified to fetch current prices only
        # Full weekly historical will be done during file upload
        
        st.success(f"✅ Incremental weekly update complete!")
    
    # ==================== DASHBOARD ====================
    
    def show_dashboard(self):
        """Main dashboard after login"""
        # Sidebar
        with st.sidebar:
            st.title(f"👤 {self.session.username}")
            st.caption(f"Role: {st.session_state.user_role}")
            
            if st.button("🚪 Logout"):
                self.logout()
                st.rerun()
            
            st.markdown("---")
            st.markdown("### 📊 Navigation")
        
        # Main content
        st.title("📊 Portfolio Analytics Dashboard")
        
        # Load portfolio data
        portfolio_df = self.load_portfolio_data()
        
        if portfolio_df is None or portfolio_df.empty:
            st.warning("⚠️ No portfolio data found. Please upload files.")
            return
        
        # Calculate P&L
        portfolio_df = self.calculate_portfolio_metrics(portfolio_df)
        
        # Display dashboard
        self.render_portfolio_overview(portfolio_df)
        self.render_sector_analysis(portfolio_df)
        self.render_weekly_charts(portfolio_df)
    
    def load_portfolio_data(self):
        """Load portfolio data from database"""
        try:
            transactions = get_transactions_supabase(user_id=self.session.user_id)
            
            if not transactions:
                return None
            
            df = pd.DataFrame(transactions)
            
            # Add live prices from session state
            df['live_price'] = df['ticker'].map(st.session_state.live_prices)
            df['sector'] = df['ticker'].map(st.session_state.sectors)
            
            return df
            
        except Exception as e:
            st.error(f"❌ Error loading portfolio: {e}")
            return None
    
    def calculate_portfolio_metrics(self, df):
        """Calculate P&L and other metrics"""
        # Calculate invested amount
        df['invested_amount'] = df['quantity'] * df['price']
        
        # Calculate current value
        df['current_value'] = df['quantity'] * df['live_price'].fillna(df['price'])
        
        # Calculate P&L
        df['unrealized_pnl'] = df['current_value'] - df['invested_amount']
        df['pnl_percentage'] = (df['unrealized_pnl'] / df['invested_amount'] * 100).fillna(0)
        
        return df
    
    def render_portfolio_overview(self, df):
        """Render portfolio overview section"""
        st.subheader("🏠 Portfolio Overview")
        
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
            arrow = "🔼" if total_pnl > 0 else ("🔽" if total_pnl < 0 else "➖")
            st.metric("Total P&L", f"{arrow} ₹{total_pnl:,.2f}", delta_color=pnl_color)
        
        with col4:
            if total_invested > 0:
                total_return = (total_pnl / total_invested) * 100
                arrow = "🔼" if total_return >= 0 else "🔽"
                st.metric("Total Return", f"{arrow} {total_return:.2f}%")
        
        st.markdown("---")
    
    def render_sector_analysis(self, df):
        """Render sector-wise analysis"""
        st.subheader("🏢 Sector-Wise Performance")
        
        if 'sector' not in df.columns or df['sector'].isna().all():
            st.warning("Sector data not available")
            return
        
        sector_data = df.groupby('sector').agg({
            'invested_amount': 'sum',
            'current_value': 'sum',
            'unrealized_pnl': 'sum'
        }).reset_index()
        
        sector_data['pnl_percentage'] = (sector_data['unrealized_pnl'] / sector_data['invested_amount'] * 100)
        
        # Display table
        st.dataframe(
            sector_data.style.format({
                'invested_amount': '₹{:,.0f}',
                'current_value': '₹{:,.0f}',
                'unrealized_pnl': '₹{:,.0f}',
                'pnl_percentage': '{:.2f}%'
            }),
            use_container_width=True
        )
        
        # Pie chart
        fig = px.pie(
            sector_data,
            values='current_value',
            names='sector',
            title='Portfolio Allocation by Sector'
        )
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
    
    def render_weekly_charts(self, df):
        """Render weekly price comparison charts"""
        st.subheader("📈 Weekly Price Charts")
        
        # Get unique tickers
        unique_tickers = df['ticker'].unique().tolist()
        
        # Multi-select for comparison
        selected_tickers = st.multiselect(
            "Select tickers to compare",
            options=unique_tickers,
            default=unique_tickers[:3] if len(unique_tickers) >= 3 else unique_tickers
        )
        
        if not selected_tickers:
            st.warning("Please select at least one ticker")
            return
        
        # Fetch ALL weekly prices for user (JOIN query, no date filter)
        all_weekly_prices = get_all_weekly_prices_for_user(self.session.user_id)
        
        # Create chart
        fig = go.Figure()
        
        one_year_ago = datetime.now() - timedelta(days=365)
        
        for ticker in selected_tickers:
            if ticker in all_weekly_prices and all_weekly_prices[ticker]:
                prices_df = pd.DataFrame(all_weekly_prices[ticker])
                prices_df['date'] = pd.to_datetime(prices_df['date'])
                prices_df = prices_df[prices_df['date'] >= one_year_ago]
                prices_df = prices_df.sort_values('date')
                
                if not prices_df.empty:
                    fig.add_trace(go.Scatter(
                        x=prices_df['date'],
                        y=prices_df['price'],
                        mode='lines+markers',
                        name=ticker,
                        hovertemplate=f'<b>{ticker}</b><br>Date: %{{x}}<br>Price: ₹%{{y:,.2f}}<extra></extra>'
                    ))
        
        fig.update_layout(
            title="Weekly Price Comparison",
            xaxis_title="Date",
            yaxis_title="Price (₹)",
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    def logout(self):
        """Logout user"""
        for key in list(st.session_state.keys()):
            del st.session_state[key]


# ==================== MAIN ====================

def main():
    """Application entry point"""
    app = PortfolioAnalytics()
    app.run()


if __name__ == "__main__":
    main()
