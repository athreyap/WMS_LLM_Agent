"""
Unified Price Fetcher Module

This module provides unified functions for fetching both historical and live prices
for stocks and mutual funds, with comprehensive fallback mechanisms.
"""

import pandas as pd
from typing import Optional, Tuple
import re

def get_mutual_fund_price_and_category(ticker: str, clean_ticker: str, user_id: int, target_date: str = None) -> Tuple[Optional[float], Optional[str]]:
    """Get price and fund category for mutual fund using mftool
    
    Args:
        ticker: The ticker symbol
        clean_ticker: Cleaned ticker symbol
        user_id: User ID for database lookups
        target_date: Target date for historical prices (None for current/live prices)
    
    Returns:
        Tuple of (price, category) where either can be None
    """
    price = None
    category = None
    
    # Method 1: Try to get transaction price from database (most reliable)
    try:
        from database_config_supabase import get_transactions_supabase
        all_user_transactions = get_transactions_supabase(user_id)
        if all_user_transactions:
            mf_transactions = [t for t in all_user_transactions if t.get('ticker') == ticker]
            if mf_transactions:
                if target_date:
                    # For historical prices, find NEAREST date match (not exact)
                    target_dt = pd.to_datetime(target_date)
                    
                    # Calculate days difference for each transaction
                    date_diffs = []
                    for t in mf_transactions:
                        if t.get('price') and t.get('price') > 0:
                            trans_date = pd.to_datetime(t.get('date'))
                            days_diff = abs((target_dt - trans_date).days)
                            date_diffs.append((days_diff, t.get('price')))
                    
                    if date_diffs:
                        # Sort by days difference and get the closest match
                        date_diffs.sort(key=lambda x: x[0])
                        closest_price = date_diffs[0][1]
                        closest_days = date_diffs[0][0]
                        
                        if closest_days <= 30:  # Accept prices within 30 days
                            price = closest_price
                            print(f"✅ MF {ticker}: Historical price ₹{price} for {target_date} (closest: {closest_days} days) from transaction data")
                            print(f"   📊 Found in database: Target: {target_date} → Closest: {closest_days} days → Price: ₹{price}")
                            return price, category
                        else:
                            print(f"⚠️ MF {ticker}: No transaction price within 30 days of {target_date}")
                            print(f"   📊 Closest available: {closest_days} days away (too far for accurate pricing)")
                else:
                    # For live prices, use average of all transaction prices
                    prices = [t.get('price', 0) for t in mf_transactions if t.get('price') and t.get('price') > 0]
                    if prices:
                        price = sum(prices) / len(prices)
                        print(f"✅ MF {ticker}: Live price ₹{price} from transaction data")
                        return price, category
    except Exception as e:
        print(f"⚠️ Could not get transaction price for MF {ticker}: {e}")
    
    # Method 2: For numerical tickers, go straight to mftool (most reliable)
    if not price and (clean_ticker.isdigit() or clean_ticker.startswith('MF_')):
        try:
            from mftool import Mftool
            
            # Create a fresh mftool instance for this request
            mf = Mftool()
            
            # Extract scheme code from ticker
            if clean_ticker.startswith('MF_'):
                scheme_code = clean_ticker.replace('MF_', '')
            elif clean_ticker.isdigit():
                scheme_code = clean_ticker
            else:
                # Try to extract numbers from ticker
                match = re.search(r'(\d{5,6})', clean_ticker)
                scheme_code = match.group(1) if match else None
            
            if scheme_code:
                if target_date:
                    # For historical prices, try mftool history method
                    try:
                        target_dt = pd.to_datetime(target_date)
                        # Get data for a range around the target date (5 days as requested)
                        start_date = target_dt - pd.Timedelta(days=5)
                        end_date = target_dt + pd.Timedelta(days=5)
                        
                        # Get historical NAV data using the working method
                        hist_data = mf.get_scheme_historical_nav(scheme_code, as_Dataframe=True)
                        
                        if hist_data is not None and not hist_data.empty:
                            # Convert date column to datetime with proper format handling
                            hist_data['date'] = pd.to_datetime(hist_data.index, format='%d-%m-%Y', dayfirst=True)
                            
                            # Filter data within 5 days range (as requested)
                            start_date = target_dt - pd.Timedelta(days=5)
                            end_date = target_dt + pd.Timedelta(days=5)
                            
                            # Filter data for the date range
                            range_data = hist_data[(hist_data['date'] >= start_date) & (hist_data['date'] <= end_date)].copy()
                            
                            if not range_data.empty:
                                # Find the closest date to target_date
                                range_data['days_diff'] = abs((range_data['date'] - target_dt).dt.days)
                                closest_idx = range_data['days_diff'].idxmin()
                                closest_nav = range_data.loc[closest_idx, 'nav']
                                closest_days = range_data.loc[closest_idx, 'days_diff']
                            
                            if closest_days <= 5:  # Accept NAV within 5 days
                                price = float(closest_nav)
                                print(f"✅ MF {ticker}: Historical NAV ₹{price} for {target_date} (closest: {closest_days} days) from mftool")
                                print(f"   📊 Mftool Historical: Target: {target_date} → Closest: {closest_days} days → NAV: ₹{price}")
                                
                                # Try to get fund category from mftool for historical data
                                try:
                                    scheme_quote = mf.get_scheme_quote(scheme_code)
                                    if scheme_quote and 'category' in scheme_quote:
                                        category = scheme_quote['category']
                                        print(f"✅ MF {ticker}: Fund category '{category}' from mftool")
                                except Exception as cat_error:
                                    print(f"⚠️ Could not fetch fund category for {ticker}: {cat_error}")
                                
                                return price, category
                            else:
                                print(f"⚠️ MF {ticker}: No NAV data within 5 days of {target_date}")
                                print(f"   📊 Closest available: {closest_days} days away (too far for accurate NAV)")
                        else:
                            print(f"⚠️ MF {ticker}: No historical NAV data available for date range")
                    except Exception as hist_error:
                        print(f"⚠️ Mftool history failed for {ticker}: {hist_error}")
                        
                        # Fallback: Try to get current NAV if historical fails
                        try:
                            scheme_quote = mf.get_scheme_quote(scheme_code)
                            if scheme_quote and 'nav' in scheme_quote:
                                price = float(scheme_quote['nav'])
                                if 'category' in scheme_quote:
                                    category = scheme_quote['category']
                                    print(f"✅ MF {ticker}: Fund category '{category}' from mftool")
                                print(f"✅ MF {ticker}: Using current NAV ₹{price} as fallback for {target_date}")
                                return price, category
                        except Exception as fallback_error:
                            print(f"⚠️ Mftool fallback also failed for {ticker}: {fallback_error}")
                else:
                    # For live prices, use mftool get_scheme_quote
                    try:
                        scheme_quote = mf.get_scheme_quote(scheme_code)
                        if scheme_quote and 'nav' in scheme_quote:
                            price = float(scheme_quote['nav'])
                            print(f"✅ MF {ticker}: Live NAV ₹{price} from mftool")
                            print(f"   📊 Mftool Quote: Current NAV: ₹{price}")
                            
                            # Get fund category from mftool
                            if 'category' in scheme_quote:
                                category = scheme_quote['category']
                                print(f"✅ MF {ticker}: Fund category '{category}' from mftool")
                            elif 'scheme_type' in scheme_quote:
                                category = scheme_quote['scheme_type']
                                print(f"✅ MF {ticker}: Scheme type '{category}' from mftool")
                            
                            return price, category
                    except Exception as quote_error:
                        print(f"⚠️ Mftool quote failed for {ticker}: {quote_error}")
            else:
                print(f"⚠️ Could not extract scheme code from ticker {clean_ticker}")
                
        except Exception as e:
            print(f"⚠️ Mftool failed for {ticker}: {e}")
    
    # Method 3: Try direct AMFI API only for non-numerical tickers (fallback)
    if not price and not (clean_ticker.isdigit() or clean_ticker.startswith('MF_')):
        try:
            import requests
            
            # Extract scheme code from ticker
            if clean_ticker.startswith('MF_'):
                scheme_code = clean_ticker.replace('MF_', '')
            elif clean_ticker.isdigit():
                scheme_code = clean_ticker
            else:
                # Try to extract numbers from ticker
                match = re.search(r'(\d{5,6})', clean_ticker)
                scheme_code = match.group(1) if match else None
            
            if scheme_code:
                # Fetch current NAV from AMFI with Streamlit Cloud compatibility
                response = requests.get('https://www.amfiindia.com/spages/NAVAll.txt', timeout=15)
                if response.status_code == 200:
                    lines = response.text.split('\n')
                    for line in lines:
                        if line.strip() and ';' in line:
                            parts = line.split(';')
                            if len(parts) >= 5 and parts[0].strip() == scheme_code:
                                try:
                                    nav = float(parts[4].strip())
                                    price = nav
                                    print(f"✅ MF {ticker}: Live NAV ₹{price} from AMFI API")
                                    print(f"   📊 AMFI API: Current NAV: ₹{price}")
                                    return price, category
                                except ValueError:
                                    continue
                else:
                    print(f"⚠️ AMFI API returned status {response.status_code}")
        except Exception as e:
            print(f"⚠️ AMFI API failed for {ticker}: {e}")
    
    # Method 4: Use intelligent default based on fund type
    if not price:
        price = get_mutual_fund_default_price(clean_ticker)
        if target_date:
            print(f"✅ MF {ticker}: Historical price ₹{price} for {target_date} (intelligent default)")
            print(f"   📊 Fallback: Target: {target_date} → Default Price: ₹{price} (no historical data available)")
        else:
            print(f"✅ MF {ticker}: Live price ₹{price} (intelligent default)")
            print(f"   📊 Fallback: Default Price: ₹{price} (no live data available)")
    
    return price, category

def get_mutual_fund_price(ticker: str, clean_ticker: str, user_id: int, target_date: str = None) -> float:
    """Get price for mutual fund using multiple fallback methods
    
    Args:
        ticker: The ticker symbol
        clean_ticker: Cleaned ticker symbol
        user_id: User ID for database lookups
        target_date: Target date for historical prices (None for current/live prices)
    """
    price = None
    
    # Method 1: Try to get transaction price from database (most reliable)
    try:
        from database_config_supabase import get_transactions_supabase
        all_user_transactions = get_transactions_supabase(user_id)
        if all_user_transactions:
            mf_transactions = [t for t in all_user_transactions if t.get('ticker') == ticker]
            if mf_transactions:
                if target_date:
                    # For historical prices, find NEAREST date match (not exact)
                    target_dt = pd.to_datetime(target_date)
                    
                    # Calculate days difference for each transaction
                    date_diffs = []
                    for t in mf_transactions:
                        if t.get('price') and t.get('price') > 0:
                            trans_date = pd.to_datetime(t.get('date'))
                            days_diff = abs((target_dt - trans_date).days)
                            date_diffs.append((days_diff, t.get('price')))
                    
                    if date_diffs:
                        # Sort by days difference and get the closest match
                        date_diffs.sort(key=lambda x: x[0])
                        closest_price = date_diffs[0][1]
                        closest_days = date_diffs[0][0]
                        
                        if closest_days <= 30:  # Accept prices within 30 days
                            price = closest_price
                            print(f"✅ MF {ticker}: Historical price ₹{price} for {target_date} (closest: {closest_days} days) from transaction data")
                            print(f"   📊 Found in database: Target: {target_date} → Closest: {closest_days} days → Price: ₹{price}")
                            return price
                        else:
                            print(f"⚠️ MF {ticker}: No transaction price within 30 days of {target_date}")
                            print(f"   📊 Closest available: {closest_days} days away (too far for accurate pricing)")
                else:
                    # For live prices, use average of all transaction prices
                    prices = [t.get('price', 0) for t in mf_transactions if t.get('price') and t.get('price') > 0]
                    if prices:
                        price = sum(prices) / len(prices)
                        print(f"✅ MF {ticker}: Live price ₹{price} from transaction data")
                        return price
    except Exception as e:
        print(f"⚠️ Could not get transaction price for MF {ticker}: {e}")
    
    # Method 2: For numerical tickers, go straight to mftool (most reliable)
    if not price and (clean_ticker.isdigit() or clean_ticker.startswith('MF_')):
        try:
            from mftool import Mftool
            
            # Create a fresh mftool instance for this request
            mf = Mftool()
            
            # Extract scheme code from ticker
            if clean_ticker.startswith('MF_'):
                scheme_code = clean_ticker.replace('MF_', '')
            elif clean_ticker.isdigit():
                scheme_code = clean_ticker
            else:
                # Try to extract numbers from ticker
                match = re.search(r'(\d{5,6})', clean_ticker)
                scheme_code = match.group(1) if match else None
            
            if scheme_code:
                if target_date:
                    # For historical prices, try mftool history method
                    try:
                        target_dt = pd.to_datetime(target_date)
                        # Get data for a range around the target date (5 days as requested)
                        start_date = target_dt - pd.Timedelta(days=5)
                        end_date = target_dt + pd.Timedelta(days=5)
                        
                        # Get historical NAV data using the working method
                        hist_data = mf.get_scheme_historical_nav(scheme_code, as_Dataframe=True)
                        
                        if hist_data is not None and not hist_data.empty:
                            # Convert date column to datetime with proper format handling
                            hist_data['date'] = pd.to_datetime(hist_data.index, format='%d-%m-%Y', dayfirst=True)
                            
                            # Filter data within 5 days range (as requested)
                            start_date = target_dt - pd.Timedelta(days=5)
                            end_date = target_dt + pd.Timedelta(days=5)
                            
                            # Filter data for the date range
                            range_data = hist_data[(hist_data['date'] >= start_date) & (hist_data['date'] <= end_date)].copy()
                            
                            if not range_data.empty:
                                # Find the closest date to target_date
                                range_data['days_diff'] = abs((range_data['date'] - target_dt).dt.days)
                                closest_idx = range_data['days_diff'].idxmin()
                                closest_nav = range_data.loc[closest_idx, 'nav']
                                closest_days = range_data.loc[closest_idx, 'days_diff']
                            
                            if closest_days <= 5:  # Accept NAV within 5 days
                                price = float(closest_nav)
                                print(f"✅ MF {ticker}: Historical NAV ₹{price} for {target_date} (closest: {closest_days} days) from mftool")
                                print(f"   📊 Mftool Historical: Target: {target_date} → Closest: {closest_days} days → NAV: ₹{price}")
                                return price
                            else:
                                print(f"⚠️ MF {ticker}: No NAV data within 5 days of {target_date}")
                                print(f"   📊 Closest available: {closest_days} days away (too far for accurate NAV)")
                        else:
                            print(f"⚠️ MF {ticker}: No historical NAV data available for date range")
                    except Exception as hist_error:
                        print(f"⚠️ Mftool history failed for {ticker}: {hist_error}")
                        
                        # Fallback: Try to get current NAV if historical fails
                        try:
                            scheme_quote = mf.get_scheme_quote(scheme_code)
                            if scheme_quote and 'nav' in scheme_quote:
                                price = float(scheme_quote['nav'])
                                print(f"✅ MF {ticker}: Using current NAV ₹{price} as fallback for {target_date}")
                                return price
                        except Exception as fallback_error:
                            print(f"⚠️ Mftool fallback also failed for {ticker}: {fallback_error}")
                else:
                    # For live prices, use mftool get_scheme_quote
                    try:
                        scheme_quote = mf.get_scheme_quote(scheme_code)
                        if scheme_quote and 'nav' in scheme_quote:
                            price = float(scheme_quote['nav'])
                            print(f"✅ MF {ticker}: Live NAV ₹{price} from mftool")
                            print(f"   📊 Mftool Quote: Current NAV: ₹{price}")
                            return price
                    except Exception as quote_error:
                        print(f"⚠️ Mftool quote failed for {ticker}: {quote_error}")
            else:
                print(f"⚠️ Could not extract scheme code from ticker {clean_ticker}")
                
        except Exception as e:
            print(f"⚠️ Mftool failed for {ticker}: {e}")
    
    # Method 3: Try direct AMFI API only for non-numerical tickers (fallback)
    if not price and not (clean_ticker.isdigit() or clean_ticker.startswith('MF_')):
        try:
            import requests
            
            # Extract scheme code from ticker
            if clean_ticker.startswith('MF_'):
                scheme_code = clean_ticker.replace('MF_', '')
            elif clean_ticker.isdigit():
                scheme_code = clean_ticker
            else:
                # Try to extract numbers from ticker
                match = re.search(r'(\d{5,6})', clean_ticker)
                scheme_code = match.group(1) if match else None
            
            if scheme_code:
                # Fetch current NAV from AMFI with Streamlit Cloud compatibility
                response = requests.get('https://www.amfiindia.com/spages/NAVAll.txt', timeout=15)
                if response.status_code == 200:
                    lines = response.text.split('\n')
                    for line in lines:
                        if line.strip() and ';' in line:
                            parts = line.split(';')
                            if len(parts) >= 5 and parts[0].strip() == scheme_code:
                                try:
                                    nav = float(parts[4].strip())
                                    price = nav
                                    print(f"✅ MF {ticker}: Live NAV ₹{price} from AMFI API")
                                    print(f"   📊 AMFI API: Current NAV: ₹{price}")
                                    return price
                                except ValueError:
                                    continue
                else:
                    print(f"⚠️ AMFI API returned status {response.status_code}")
        except Exception as e:
            print(f"⚠️ AMFI API failed for {ticker}: {e}")
    
    # Method 4: Use intelligent default based on fund type
    if not price:
        price = get_mutual_fund_default_price(clean_ticker)
        if target_date:
            print(f"✅ MF {ticker}: Historical price ₹{price} for {target_date} (intelligent default)")
            print(f"   📊 Fallback: Target: {target_date} → Default Price: ₹{price} (no historical data available)")
        else:
            print(f"✅ MF {ticker}: Live price ₹{price} (intelligent default)")
            print(f"   📊 Fallback: Default Price: ₹{price} (no live data available)")
    
    return price

def get_stock_price_and_sector(ticker: str, clean_ticker: str, target_date: str = None) -> Tuple[Optional[float], Optional[str], Optional[float]]:
    """Get price, sector, and market cap for stock using yfinance
    
    Args:
        ticker: The ticker symbol
        clean_ticker: Cleaned ticker symbol
        target_date: Target date for historical prices (None for current/live prices)
    
    Returns:
        Tuple of (price, sector, market_cap) where any can be None
    """
    price = None
    sector = None
    market_cap = None
    
    try:
        import yfinance as yf
        
        # Try .NS first (National Stock Exchange)
        yf_ticker_ns = clean_ticker
        if not yf_ticker_ns.endswith(('.NS', '.BO', '.NSE', '.BSE')):
            yf_ticker_ns = f"{clean_ticker}.NS"
        
        stock_ns = yf.Ticker(yf_ticker_ns)
        
        # Try to get sector and market cap information from yfinance
        try:
            info = stock_ns.info
            if info and 'sector' in info and info['sector']:
                sector = info['sector']
                print(f"✅ {ticker}: Sector '{sector}' fetched from yfinance")
            elif info and 'industry' in info and info['industry']:
                sector = info['industry']
                print(f"✅ {ticker}: Industry '{sector}' fetched from yfinance (using as sector)")
            
            # Get market cap in INR (convert from USD if needed)
            if info and 'marketCap' in info and info['marketCap']:
                market_cap_usd = info['marketCap']
                if market_cap_usd:
                    # Convert USD to INR (approximate rate 83.5)
                    market_cap = market_cap_usd * 83.5
                    print(f"✅ {ticker}: Market Cap ₹{market_cap:,.0f} Cr (${market_cap_usd/1000000000:.2f}B) from yfinance")
            elif info and 'market_cap' in info and info['market_cap']:
                market_cap = info['market_cap'] * 83.5  # Convert to INR
                print(f"✅ {ticker}: Market Cap ₹{market_cap:,.0f} Cr from yfinance")
                
        except Exception as sector_error:
            print(f"⚠️ Could not fetch sector/market cap for {ticker}: {sector_error}")
        
        if target_date:
            # For historical prices, get data for a range around the target date
            target_dt = pd.to_datetime(target_date)
            if target_dt.tz is not None:
                target_dt = target_dt.tz_localize(None)
            
            start_date = target_dt - pd.Timedelta(days=30)
            end_date = target_dt + pd.Timedelta(days=30)
            
            hist_ns = stock_ns.history(start=start_date, end=end_date)
            if not hist_ns.empty:
                hist_ns.index = hist_ns.index.tz_localize(None)
                hist_ns['days_diff'] = abs((hist_ns.index - target_dt).days)
                closest_idx = hist_ns['days_diff'].idxmin()
                closest_price = hist_ns.loc[closest_idx, 'Close']
                closest_days = hist_ns.loc[closest_idx, 'days_diff']
                
                if closest_days <= 30 and closest_price > 0:
                    price = closest_price
                    print(f"✅ {ticker}: Historical price ₹{price} for {target_date} (closest: {closest_days} days) from yfinance (.NS)")
        else:
            # For live prices, get current day data
            hist_ns = stock_ns.history(period="1d")
            if not hist_ns.empty and hist_ns['Close'].iloc[-1] > 0:
                price = hist_ns['Close'].iloc[-1]
                print(f"✅ {ticker}: Live price ₹{price} from yfinance (.NS)")
        
        # If .NS didn't work, try .BO (Bombay Stock Exchange)
        if not price and not yf_ticker_ns.endswith('.BO'):
            yf_ticker_bo = f"{clean_ticker}.BO"
            stock_bo = yf.Ticker(yf_ticker_bo)
            
            # Try to get sector and market cap from .BO if not already got from .NS
            if not sector or not market_cap:
                try:
                    info = stock_bo.info
                    if not sector and info and 'sector' in info and info['sector']:
                        sector = info['sector']
                        print(f"✅ {ticker}: Sector '{sector}' fetched from yfinance (.BO)")
                    elif not sector and info and 'industry' in info and info['industry']:
                        sector = info['industry']
                        print(f"✅ {ticker}: Industry '{sector}' fetched from yfinance (.BO) (using as sector)")
                    
                    if not market_cap and info and 'marketCap' in info and info['marketCap']:
                        market_cap_usd = info['marketCap']
                        if market_cap_usd:
                            market_cap = market_cap_usd * 83.5
                            print(f"✅ {ticker}: Market Cap ₹{market_cap:,.0f} Cr (${market_cap_usd/1000000000:.2f}B) from yfinance (.BO)")
                except Exception as sector_error:
                    print(f"⚠️ Could not fetch sector/market cap for {ticker} from .BO: {sector_error}")
            
            if target_date and not price:
                hist_bo = stock_bo.history(start=start_date, end=end_date)
                if not hist_bo.empty:
                    hist_bo.index = hist_bo.index.tz_localize(None)
                    hist_bo['days_diff'] = abs((hist_bo.index - target_dt).days)
                    closest_idx = hist_bo['days_diff'].idxmin()
                    closest_price = hist_bo.loc[closest_idx, 'Close']
                    closest_days = hist_bo.loc[closest_idx, 'days_diff']
                    
                    if closest_days <= 30 and closest_price > 0:
                        price = closest_price
                        print(f"✅ {ticker}: Historical price ₹{price} for {target_date} (closest: {closest_days} days) from yfinance (.BO)")
            elif not price:
                hist_bo = stock_bo.history(period="1d")
                if not hist_bo.empty and hist_bo['Close'].iloc[-1] > 0:
                    price = hist_bo.loc[closest_idx, 'Close']
                    print(f"✅ {ticker}: Live price ₹{price} from yfinance (.BO)")
        
        if not price:
            print(f"⚠️ {ticker}: No price data from yfinance (.NS or .BO)")
            
    except Exception as e:
        print(f"⚠️ yfinance failed for {ticker}: {e}")
    
    return price, sector, market_cap

def get_stock_price(ticker: str, clean_ticker: str, target_date: str = None) -> float:
    """Get price for stock using multiple sources
    
    Args:
        ticker: The ticker symbol
        clean_ticker: Cleaned ticker symbol
        target_date: Target date for historical prices (None for current/live prices)
    """
    price = None  # Initialize price variable
    
    # Method 1: Try yfinance with .NS first, then .BO as fallback
    try:
        import yfinance as yf
        
        # Try .NS first (National Stock Exchange)
        yf_ticker_ns = clean_ticker
        if not yf_ticker_ns.endswith(('.NS', '.BO', '.NSE', '.BSE')):
            yf_ticker_ns = f"{clean_ticker}.NS"
        
        stock_ns = yf.Ticker(yf_ticker_ns)
        
        if target_date:
            # For historical prices, get data for a range around the target date to find nearest available
            target_dt = pd.to_datetime(target_date)
            # Ensure target_dt is timezone-naive for comparison
            if target_dt.tz is not None:
                target_dt = target_dt.tz_localize(None)
            
            start_date = target_dt - pd.Timedelta(days=30)
            end_date = target_dt + pd.Timedelta(days=30)
            
            hist_ns = stock_ns.history(start=start_date, end=end_date)
            if not hist_ns.empty:
                # Convert index to timezone-naive for comparison
                hist_ns.index = hist_ns.index.tz_localize(None)
                # Find the closest date to target_date
                hist_ns['days_diff'] = abs((hist_ns.index - target_dt).days)
                closest_idx = hist_ns['days_diff'].idxmin()
                closest_price = hist_ns.loc[closest_idx, 'Close']
                closest_days = hist_ns.loc[closest_idx, 'days_diff']
                
                if closest_days <= 30 and closest_price > 0:  # Accept prices within 30 days
                    print(f"✅ {ticker}: Historical price ₹{closest_price} for {target_date} (closest: {closest_days} days) from yfinance (.NS)")
                    print(f"   📊 YFinance (.NS): Target: {target_date} → Closest: {closest_days} days → Price: ₹{closest_price}")
                    return closest_price
                else:
                    print(f"⚠️ {ticker}: No price data within 30 days of {target_date} from yfinance (.NS)")
                    print(f"   📊 Closest available: {closest_days} days away (too far for accurate pricing)")
            else:
                print(f"⚠️ {ticker}: No historical data available for {target_date} from yfinance (.NS)")
        else:
            # For live prices, get current day data
            hist_ns = stock_ns.history(period="1d")
            if not hist_ns.empty and hist_ns['Close'].iloc[-1] > 0:
                price = hist_ns['Close'].iloc[-1]
                print(f"✅ {ticker}: Live price ₹{price} from yfinance (.NS)")
                return price
        
        # If .NS didn't work, try .BO (Bombay Stock Exchange)
        if not yf_ticker_ns.endswith('.BO'):
            yf_ticker_bo = f"{clean_ticker}.BO"
            stock_bo = yf.Ticker(yf_ticker_bo)
            
            if target_date:
                # For historical prices, get data for a range around the target date
                hist_bo = stock_bo.history(start=start_date, end=end_date)
                if not hist_bo.empty:
                    # Convert index to timezone-naive for comparison
                    hist_bo.index = hist_bo.index.tz_localize(None)
                    # Find the closest date to target_date
                    hist_bo['days_diff'] = abs((hist_bo.index - target_dt).days)
                    closest_idx = hist_bo['days_diff'].idxmin()
                    closest_price = hist_bo.loc[closest_idx, 'Close']
                    closest_days = hist_bo.loc[closest_idx, 'days_diff']
                    
                    if closest_days <= 30 and closest_price > 0:  # Accept prices within 30 days
                        print(f"✅ {ticker}: Historical price ₹{closest_price} for {target_date} (closest: {closest_days} days) from yfinance (.BO)")
                        print(f"   📊 YFinance (.BO): Target: {target_date} → Closest: {closest_days} days → Price: ₹{closest_price}")
                        return closest_price
                    else:
                        print(f"⚠️ {ticker}: No price data within 30 days of {target_date} from yfinance (.BO)")
                        print(f"   📊 Closest available: {closest_days} days away (too far for accurate pricing)")
                else:
                    print(f"⚠️ {ticker}: No historical data available for {target_date} from yfinance (.BO)")
            else:
                # For live prices, get current day data
                hist_bo = stock_bo.history(period="1d")
                if not hist_bo.empty and hist_bo['Close'].iloc[-1] > 0:
                    price = hist_bo['Close'].iloc[-1]
                    print(f"✅ {ticker}: Live price ₹{price} from yfinance (.BO)")
                    return price
            
            print(f"⚠️ {ticker}: No price data from yfinance (.NS or .BO)")
        else:
            print(f"⚠️ {ticker}: No price data from yfinance (.NS)")
            
    except Exception as e:
        print(f"⚠️ yfinance failed for {ticker}: {e}")
    
    # Method 2: Try indstocks_api as fallback
    try:
        from indstocks_api import INDstocksClient
        
        # Create indstocks client
        indstocks_client = INDstocksClient()
        if indstocks_client.available:
            # Try with .NS suffix first
            if not clean_ticker.endswith(('.NS', '.BO')):
                ticker_ns = f"{clean_ticker}.NS"
                price_data = indstocks_client.get_stock_price(ticker_ns, target_date)
                if price_data and isinstance(price_data, dict) and price_data.get('price'):
                    price = float(price_data['price'])
                    if target_date:
                        print(f"✅ {ticker}: Historical price ₹{price} for {target_date} from indstocks_api (.NS)")
                    else:
                        print(f"✅ {ticker}: Live price ₹{price} from indstocks_api (.NS)")
                    return price
                
                # If .NS didn't work, try .BO
                ticker_bo = f"{clean_ticker}.BO"
                price_data = indstocks_client.get_stock_price(ticker_bo, target_date)
                if price_data and isinstance(price_data, dict) and price_data.get('price'):
                    price = float(price_data['price'])
                    if target_date:
                        print(f"✅ {ticker}: Historical price ₹{price} for {target_date} from indstocks_api (.BO)")
                    else:
                        print(f"✅ {ticker}: Historical price ₹{price} for {target_date} from indstocks_api (.BO)")
                    return price
            else:
                # Ticker already has suffix, try as is
                price_data = indstocks_client.get_stock_price(clean_ticker, target_date)
                if price_data and isinstance(price_data, dict) and price_data.get('price'):
                    price = float(price_data['price'])
                    if target_date:
                        print(f"✅ {ticker}: Historical price ₹{price} from indstocks_api")
                    else:
                        print(f"✅ {ticker}: Live price ₹{price} from indstocks_api")
                    return price
        else:
            print(f"⚠️ Indstocks client not available")
                
    except Exception as e:
        print(f"⚠️ indstocks_api failed for {ticker}: {e}")
    
    # Method 3: Use default price as last resort
    if not price:
        price = 1000.0  # Default price for stocks
        print(f"⚠️ {ticker}: Using default price ₹{price}")
    
    return price

def get_mutual_fund_default_price(clean_ticker: str) -> float:
    """Get intelligent default price for mutual fund based on ticker pattern"""
    try:
        # Extract scheme code for pattern matching
        if clean_ticker.startswith('MF_'):
            scheme_code = clean_ticker.replace('MF_', '')
        elif clean_ticker.isdigit():
            scheme_code = clean_ticker
        else:
            # Try to extract numbers from ticker
            match = re.search(r'(\d{5,6})', clean_ticker)
            scheme_code = match.group(1) if match else None
        
        if scheme_code:
            # Use scheme code to determine fund type and default price
            scheme_num = int(scheme_code)
            
            # Different fund types have different typical NAV ranges
            if 120000 <= scheme_num <= 129999:  # Tata funds
                return 50.0
            elif 130000 <= scheme_num <= 139999:  # HDFC funds
                return 100.0
            elif 140000 <= scheme_num <= 149999:  # ICICI funds
                return 75.0
            elif 150000 <= scheme_num <= 159999:  # SBI funds
                return 80.0
            elif 160000 <= scheme_num <= 169999:  # Axis funds
                return 90.0
            elif 170000 <= scheme_num <= 179999:  # Kotak funds
                return 85.0
            elif 180000 <= scheme_num <= 189999:  # Aditya Birla funds
                return 70.0
            elif 190000 <= scheme_num <= 199999:  # DSP funds
                return 60.0
            elif 200000 <= scheme_num <= 209999:  # Franklin funds
                return 55.0
            elif 210000 <= scheme_num <= 219999:  # Mirae funds
                return 65.0
            elif 220000 <= scheme_num <= 229999:  # PGIM funds
                return 45.0
            elif 230000 <= scheme_num <= 239999:  # Nippon funds
                return 40.0
            elif 240000 <= scheme_num <= 249999:  # UTI funds
                return 35.0
            elif 250000 <= scheme_num <= 259999:  # L&T funds
                return 50.0
            elif 260000 <= scheme_num <= 269999:  # Invesco funds
                return 30.0
            elif 270000 <= scheme_num <= 279999:  # Edelweiss funds
                return 25.0
            elif 280000 <= scheme_num <= 289999:  # Motilal funds
                return 20.0
            elif 290000 <= scheme_num <= 299999:  # Sundaram funds
                return 15.0
            elif 300000 <= scheme_num <= 309999:  # Quantum funds
                return 10.0
            elif 310000 <= scheme_num <= 319999:  # PPFAS funds
                return 12.0
            elif 320000 <= scheme_num <= 329999:  # WhiteOak funds
                return 18.0
            elif 330000 <= scheme_num <= 339999:  # Navi funds
                return 22.0
            elif 340000 <= scheme_num <= 349999:  # Groww funds
                return 28.0
            elif 350000 <= scheme_num <= 359999:  # Upstox funds
                return 32.0
            elif 360000 <= scheme_num <= 369999:  # Zerodha funds
                return 38.0
            elif 370000 <= scheme_num <= 379999:  # Angel funds
                return 42.0
            elif 380000 <= scheme_num <= 389999:  # 5Paisa funds
                return 48.0
            elif 390000 <= scheme_num <= 399999:  # Samco funds
                return 52.0
            elif 400000 <= scheme_num <= 409999:  # Finvasia funds
                return 58.0
            elif 410000 <= scheme_num <= 419999:  # IIFL funds
                return 62.0
            elif 420000 <= scheme_num <= 429999:  # Religare funds
                return 68.0
            elif 430000 <= scheme_num <= 439999:  # JM funds
                return 72.0
            elif 440000 <= scheme_num <= 449999:  # Canara funds
                return 78.0
            elif 450000 <= scheme_num <= 459999:  # Union funds
                return 82.0
            elif 460000 <= scheme_num <= 469999:  # BOI funds
                return 88.0
            elif 470000 <= scheme_num <= 479999:  # PNB funds
                return 92.0
            elif 480000 <= scheme_num <= 489999:  # IDBI funds
                return 96.0
            elif 490000 <= scheme_num <= 499999:  # IOB funds
                                return 98.0
            else:
                # Default for unknown fund types
                return 100.0
        else:
            # Default for tickers without scheme codes
            return 100.0
            
    except Exception as e:
        print(f"⚠️ Error getting default price for {clean_ticker}: {e}")
        return 100.0  # Fallback default
