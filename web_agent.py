import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from collections import defaultdict
import os
import time
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
        self.session_state = st.session_state
        self.initialize_session_state()
        
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
            
            return True, "Login successful"
        else:
            return False, message
    
    def handle_user_registration(self, username, email, password, folder_path=None):
        """Handle user registration"""
        if not LOGIN_SYSTEM_AVAILABLE:
            return False, "Login system not available"
        
        success, message = create_user(username, email, password, folder_path=folder_path)
        return success, message
    
    def check_user_folder_access(self):
        """Check if current user has proper folder access"""
        if not LOGIN_SYSTEM_AVAILABLE:
            return True, "Login system not available"
        
        folder_path = self.session_state.get('folder_path', '')
        if not folder_path:
            return False, "No folder path configured for user"
        
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
                                st.write(f"- {file}")
                    except Exception as e:
                        st.error(f"Error accessing folder: {e}")
                else:
                    st.error(f"❌ {folder_message}")
            else:
                st.warning("⚠️ No folder path configured")
        
        # Admin-specific settings
        if user_role == 'admin':
            st.markdown("### 👑 Admin Settings")
            st.info("Admin features available in the Admin Panel")
    
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
    
    def load_data_from_agents(self, user_id: int = None) -> pd.DataFrame:
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
                except Exception as e:
                    pass  # Silently handle file processing errors
                
                # Get transactions from database
                transactions = get_transactions_with_historical_prices(user_id=user_id)
                
                if not transactions:
                    st.warning(f"⚠️ No transactions found for user ID {user_id}")
                    return pd.DataFrame()  # Return empty DataFrame instead of falling back to all transactions
            else:
                transactions = get_transactions_with_historical_prices()
            
            if not transactions:
                st.warning("⚠️ No transactions found in database")
                return pd.DataFrame()
            
            # Convert transactions to DataFrame
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
            
            if df.empty:
                st.warning("⚠️ No transactions found in database")
                return pd.DataFrame()
            
            return df
        
        try:
            # Use ThreadPoolExecutor for timeout protection (cross-platform)
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(load_data_with_timeout)
                df = future.result(timeout=300)  # 5 minutes timeout for data loading
            
            # Smart live price caching system
            cache_key = f'live_prices_user_{user_id}' if user_id else 'live_prices_global'
            cache_timestamp_key = f'live_prices_timestamp_user_{user_id}' if user_id else 'live_prices_timestamp_global'
            
            # Check if we have cached prices and if they're recent enough
            cache_age = time.time() - self.session_state.get(cache_timestamp_key, 0)
            cache_valid = cache_age < 300  # 5 minutes cache
            
            # In fast loading mode, extend cache validity to 10 minutes and skip live price fetching
            fast_loading = self.session_state.get('fast_loading', True)
            if fast_loading:
                cache_valid = cache_age < 600  # 10 minutes cache in fast mode
            else:
                cache_valid = cache_age < 300  # 5 minutes cache in normal mode
            
            if cache_valid and cache_key in self.session_state:
                # Use cached prices (fast)
                live_prices = self.session_state[cache_key]
                if fast_loading:
                    pass  # Silent cache usage
            else:
                # Need to fetch fresh prices (always fetch if not cached, regardless of fast loading mode)
                try:
                    print(f"🔄 Fetching fresh live prices for user {user_id}...")
                    # Set flag to indicate live prices are being updated
                    self.session_state['updating_live_prices'] = True
                    
                    if user_id and user_id != 1:  # Authenticated user
                        # Update only user's stocks (faster than all stocks)
                        print(f"🔄 Updating user-specific stock prices for user {user_id}...")
                        update_result = update_user_stock_prices(user_id)
                        print(f"🔍 Update result: {update_result}")
                        if update_result.get('updated', 0) > 0:
                            print(f"✅ Updated {update_result['updated']} stock prices")
                        else:
                            print(f"⚠️ No stock prices updated: {update_result}")
                    else:
                        # For non-authenticated users, update all stocks
                        print(f"🔄 Updating all stock prices...")
                        update_result = update_user_stock_prices(1)  # Update all stocks
                        print(f"🔍 Update result: {update_result}")
                        if update_result.get('updated', 0) > 0:
                            print(f"✅ Updated {update_result['updated']} stock prices")
                        else:
                            print(f"⚠️ No stock prices updated: {update_result}")
                    
                    # Get fresh live prices (user-specific when possible)
                    if user_id and user_id != 1:
                        print(f"🔄 Getting user-specific live prices for user {user_id}...")
                        live_prices = get_user_live_prices(user_id)
                    else:
                        print(f"🔄 Getting all live prices...")
                        live_prices = get_all_live_prices()
                    
                    print(f"🔍 Live prices fetched: {len(live_prices)} prices")
                    
                    # Cache the results
                    self.session_state[cache_key] = live_prices
                    self.session_state[cache_timestamp_key] = time.time()
                    
                    # Clear the updating flag
                    self.session_state['updating_live_prices'] = False
                    
                except Exception as e:
                    st.warning(f"⚠️ Could not fetch live prices: {e}")
                    # Fallback to cached prices if available
                    live_prices = self.session_state.get(cache_key, {})
                    # Clear the updating flag even on error
                    self.session_state['updating_live_prices'] = False
            
            # Add live prices to DataFrame
            df['live_price'] = df['ticker'].map(live_prices).fillna(df['price'])
            
            # Debug: Check live price fetching results
            if live_prices:
                prices_found = sum(1 for price in live_prices.values() if price and price > 0)
                total_prices = len(live_prices)
                print(f"🔍 Live price debug: {prices_found}/{total_prices} prices found, {len(df)} transactions")
                
                # Show sample of live prices
                sample_prices = list(live_prices.items())[:5]
                for ticker, price in sample_prices:
                    print(f"🔍 Sample live price: {ticker} = ₹{price}")
            else:
                print(f"⚠️ Live price debug: No live prices fetched, using historical prices")
            
            # Debug: Check final live prices in DataFrame
            zero_prices = (df['live_price'] == 0).sum()
            total_transactions = len(df)
            print(f"🔍 Final live prices: {zero_prices}/{total_transactions} transactions have zero prices")
            

            
            # Calculate current values and gains
            df['current_value'] = df['quantity'] * df['live_price']
            df['invested_amount'] = df['quantity'] * df['price']
            df['abs_gain'] = df['current_value'] - df['invested_amount']
            df['pct_gain'] = (df['abs_gain'] / df['invested_amount']) * 100
            
            # Add sector information if not present or if all sectors are Unknown
            if 'sector' not in df.columns or df['sector'].isna().all() or (df['sector'] == 'Unknown').all():
                
                
                # Try to load mutual fund functionality
                try:
                    from mf_price_fetcher import is_mutual_fund_ticker, get_mftool_client
                    mf_available = True
                except ImportError:
                    mf_available = False
                
                # Get sector information with mutual fund fallback
                def get_sector_with_mf_fallback(ticker):
                    if not ticker:
                        return 'Unknown'
                    
                    # First try stock data agent
                    sector = get_sector(ticker)
                    if sector and sector != 'Unknown':
                        return sector
                    
                    # If stock data agent fails and MF tool is available, try MF tool
                    if mf_available:
                        try:
                            if is_mutual_fund_ticker(ticker):
                                mf_client = get_mftool_client()
                                if mf_client:
                                    # For mutual funds, we can get category information
                                    try:
                                        mf_info = mf_client.get_scheme_details(ticker)
                                        if mf_info and 'category' in mf_info:
                                            return f"MF - {mf_info['category']}"
                                    except:
                                        pass
                                return "Mutual Fund"
                        except Exception as e:
                            st.warning(f"MF tool error for {ticker}: {e}")
                    
                    return 'Unknown'
                
                # Apply sector fetching with fallback
                df['sector'] = df['ticker'].apply(get_sector_with_mf_fallback)
                
                
            
            return df
            
        except concurrent.futures.TimeoutError:
            st.error("❌ Data loading timed out. Please try again or use fast loading mode.")
            return pd.DataFrame()
        except Exception as e:
            st.error(f"❌ Error loading data: {e}")
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
            
            # Add live prices for P&L calculation
            live_prices_cache_key = f'live_prices_user_{user_id}' if user_id else 'live_prices_global'
            live_prices = self.session_state.get(live_prices_cache_key, {})
            
            # Debug: Check if live prices are available
            print(f"🔍 Quarterly Analysis - Live prices debug:")
            print(f"🔍 Cache key: {live_prices_cache_key}")
            print(f"🔍 Live prices type: {type(live_prices)}")
            print(f"🔍 Live prices length: {len(live_prices) if isinstance(live_prices, dict) else 'N/A'}")
            
            if not live_prices:
                print(f"⚠️ No live prices found in cache key: {live_prices_cache_key}")
                print(f"🔍 Available cache keys: {[k for k in self.session_state.keys() if 'live_prices' in k]}")
                st.warning(f"⚠️ No live prices found in cache key: {live_prices_cache_key}")
                st.info(f"Available cache keys: {[k for k in self.session_state.keys() if 'live_prices' in k]}")
            else:
                print(f"🔍 Live prices found: {len(live_prices)} prices")
                sample_prices = list(live_prices.items())[:3]
                for ticker, price in sample_prices:
                    print(f"🔍 Sample live price: {ticker} = ₹{price}")
            
            buy_df['live_price'] = buy_df['ticker'].map(live_prices).fillna(buy_df['price'])
            
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
                st.plotly_chart(fig1, use_container_width=True, key="holdings_bar_main")
            
            with row1_col2:
                st.markdown('<h4 class="subsection-header">Top 10 P/L by Stock</h4>', unsafe_allow_html=True)
                top_pnl_stocks = selected_stocks
                
                if top_pnl_stocks['pnl'].sum() == 0:
                    st.warning("⚠️ All P&L values are zero. This might indicate missing live prices.")
                
                fig2 = px.bar(top_pnl_stocks, x='stock_name', y='pnl', 
                             title=f'{chart_title} (₹)', 
                             text='pnl',
                             color='pnl',
                             color_continuous_scale='RdYlGn')
                fig2.update_xaxes(tickangle=45)
                fig2.update_traces(texttemplate='₹%{text:,.2f}', textposition='outside')
                st.plotly_chart(fig2, use_container_width=True, key="pnl_bar_main")
    
    def render_sector_analysis(self, holdings: pd.DataFrame):
        """Render sector analysis charts"""
        if holdings.empty or 'sector' not in holdings.columns:
            return
        
        st.markdown('<h2 class="section-header">📈 Sector Analysis</h2>', unsafe_allow_html=True)
        
        # Add button to update sectors (only show when not loading live prices)
        loading_live_prices = False
        
        # Check if we're in the middle of a live price update
        cache_key = f'live_prices_user_{self.session_state.get("user_id", 1)}' if self.session_state.get("user_id") else 'live_prices_global'
        cache_timestamp_key = f'live_prices_timestamp_user_{self.session_state.get("user_id", 1)}' if self.session_state.get("user_id") else 'live_prices_timestamp_global'
        
        # If cache is too old or missing, we might be loading live prices
        cache_age = time.time() - self.session_state.get(cache_timestamp_key, 0)
        if cache_age > 300 or cache_key not in self.session_state:  # 5 minutes cache
            loading_live_prices = True
        
        # Also check if there's an ongoing live price update in session state
        if self.session_state.get('updating_live_prices', False):
            loading_live_prices = True
        
        # Only show the button if not loading live prices
        if not loading_live_prices:
            col1, col2, col3 = st.columns([2, 1, 1])
            with col2:
                if st.button("🔄 Update Sectors", help="Update sector information for all stocks"):
                    with st.spinner("Updating sectors..."):
                        from stock_data_agent import update_all_stock_sectors
                        update_all_stock_sectors()
                        st.success("✅ Sectors updated successfully!")
                        st.rerun()
        
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
            st.plotly_chart(fig1, use_container_width=True)
        
        with col2:
            st.markdown('<h4 class="subsection-header">Sector Performance</h4>', unsafe_allow_html=True)
            fig2 = px.bar(sector_performance, x='sector', y='pct_gain', 
                         title='Sector Performance (% Gain/Loss)',
                         color='pct_gain',
                         color_continuous_scale='RdYlGn')
            fig2.update_xaxes(tickangle=45)
            st.plotly_chart(fig2, use_container_width=True)
        
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
            st.plotly_chart(fig3, use_container_width=True)
        
        with col4:
            st.markdown('<h4 class="subsection-header">Number of Stocks per Sector</h4>', unsafe_allow_html=True)
            fig4 = px.bar(sector_performance, x='sector', y='num_stocks', 
                         title='Number of Stocks per Sector', 
                         text='num_stocks',
                         color='num_stocks',
                         color_continuous_scale='Greens')
            fig4.update_traces(texttemplate='%{text}', textposition='outside')
            fig4.update_layout(xaxis_title="Sector", yaxis_title="Number of Stocks")
            st.plotly_chart(fig4, use_container_width=True)
    
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
        
        st.dataframe(display_df, use_container_width=True)
    
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
        
        # Get live prices for current price display
        user_id = self.session_state.get('user_id', 1)
        cache_key = f'live_prices_user_{user_id}' if user_id else 'live_prices_global'
        live_prices_raw = self.session_state.get(cache_key, {})
        
        # Debug: Check live prices in Stock Performance Analysis
        print(f"🔍 Stock Performance Analysis - Live prices debug:")
        print(f"🔍 Cache key: {cache_key}")
        print(f"🔍 Live prices raw type: {type(live_prices_raw)}")
        print(f"🔍 Live prices raw length: {len(live_prices_raw) if isinstance(live_prices_raw, dict) else 'N/A'}")
        
        # Ensure live_prices is a dictionary
        if isinstance(live_prices_raw, dict):
            live_prices = live_prices_raw
            print(f"🔍 Live prices from cache: {len(live_prices)} prices")
            if live_prices:
                sample_prices = list(live_prices.items())[:3]
                for ticker, price in sample_prices:
                    print(f"🔍 Sample cache price: {ticker} = ₹{price}")
        else:
            live_prices = {}
            print(f"⚠️ Live prices raw is not a dict, using empty dict")
        
        # If live prices are empty, try to get them from the buy_df
        if len(live_prices) == 0:
            print(f"🔍 Live prices empty, trying to extract from buy_df...")
            # Extract live prices from the buy_df which should have them
            if not buy_df.empty and 'live_price' in buy_df.columns:
                live_prices = buy_df.set_index('ticker')['live_price'].to_dict()
                print(f"🔍 Extracted {len(live_prices)} prices from buy_df")
                if live_prices:
                    sample_prices = list(live_prices.items())[:3]
                    for ticker, price in sample_prices:
                        print(f"🔍 Sample buy_df price: {ticker} = ₹{price}")
            else:
                live_prices = {}
                print(f"⚠️ buy_df empty or missing live_price column")
        else:
            print(f"✅ Using live prices from cache")
        
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
            st.dataframe(rating_df, use_container_width=True)
    
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
            st.plotly_chart(fig1, use_container_width=True)
        
        with col2:
            st.markdown('<h4 class="subsection-header">Channel Performance</h4>', unsafe_allow_html=True)
            fig2 = px.bar(channel_allocation, x='channel', y='P&L_Percent', 
                         title='Channel Performance (% Gain/Loss)',
                         color='P&L_Percent',
                         color_continuous_scale='RdYlGn')
            fig2.update_xaxes(tickangle=45)
            fig2.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
            st.plotly_chart(fig2, use_container_width=True)
        
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
        st.dataframe(display_table, use_container_width=True)
    
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
            
            st.plotly_chart(fig, use_container_width=True)
                        
        except Exception as e:
            st.error(f"Error rendering portfolio value over time: {e}")
    
    def render_dashboard(self, df: pd.DataFrame):
        """Render the main dashboard"""
        if df.empty:
            st.warning("⚠️ No data available. Please upload files or check database.")
            return
        
        # Use cached holdings if available, otherwise calculate
        user_id = self.session_state.get('user_id', 1)
        holdings_cache_key = f'holdings_user_{user_id}'
        
        # Check if we need to recalculate holdings (only if data changed)
        if not df.empty and all(col in df.columns for col in ['ticker', 'quantity', 'price', 'live_price', 'transaction_type']):
            data_hash = hash(str(df[['ticker', 'quantity', 'price', 'live_price', 'transaction_type']].values.tobytes()))
            cached_data_hash = self.session_state.get(f'{holdings_cache_key}_hash', None)
        else:
            # If DataFrame is empty or missing columns, force recalculation
            data_hash = None
            cached_data_hash = None
        
        if cached_data_hash == data_hash and holdings_cache_key in self.session_state:
            # Use cached holdings
            all_holdings = self.session_state[holdings_cache_key]
        else:
            # Calculate holdings and cache them
            all_holdings = self.calculate_holdings(df)
            self.session_state[holdings_cache_key] = all_holdings
            self.session_state[f'{holdings_cache_key}_hash'] = data_hash
        
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
                    if st.button("← Back to Dashboard"):
                        st.session_state['show_settings'] = False
                        st.rerun()
                    st.stop()
        else:
            if 'user_authenticated' not in st.session_state:
                st.session_state['user_authenticated'] = True
                st.session_state['username'] = 'User'
                st.session_state['user_role'] = 'user'
        
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
        
        df = self.load_data_from_agents(user_id)
        
        if not df.empty:
            # Manual refresh button for live prices and sectors
            if st.sidebar.button("🔄 Refresh Live Prices & Sectors", help="Force update live prices and sector information for your stocks"):
                try:
                    if user_id and user_id != 1:
                        # Clear cache to force refresh
                        cache_key = f'live_prices_user_{user_id}'
                        cache_timestamp_key = f'live_prices_timestamp_user_{user_id}'
                        self.session_state.pop(cache_key, None)
                        self.session_state.pop(cache_timestamp_key, None)
                        
                        # Update live prices and sectors
                        update_result = update_user_stock_prices(user_id)
                        if update_result.get('updated', 0) > 0:
                            # Clear holdings and quarterly cache since prices changed
                            holdings_cache_key = f'holdings_user_{user_id}'
                            quarterly_cache_key = f'quarterly_analysis_user_{user_id}'
                            self.session_state.pop(holdings_cache_key, None)
                            self.session_state.pop(f'{holdings_cache_key}_hash', None)
                            self.session_state.pop(quarterly_cache_key, None)
                            self.session_state.pop(f'{quarterly_cache_key}_hash', None)
                            st.sidebar.success(f"✅ Updated {update_result['updated']} stock prices and sectors")
                        else:
                            st.sidebar.info("ℹ️ No updates needed")
                        
                        st.rerun()
                except Exception as e:
                    st.sidebar.error(f"❌ Error refreshing prices: {e}")
        else:
            st.sidebar.warning("**No transactions found for this user**")
        
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
        
        # Render filters at the top
        filtered_df, selected_channel, selected_sector, selected_stock = self.render_top_filters(df)
        
        # Render dashboard
        self.render_dashboard(filtered_df)

# Global web agent instance
web_agent = WebAgent()

# Main function for Streamlit
def main():
    web_agent.run()

if __name__ == "__main__":
    main()
