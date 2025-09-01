#!/usr/bin/env python3
"""
Simplified File Manager for WMS-LLM Portfolio Analyzer
Processes files from user's specific folder and moves them to archive
"""

import os
import glob
import shutil
import pandas as pd
from datetime import datetime
from pathlib import Path
import hashlib
from database_config_supabase import save_file_record_supabase, save_transaction_supabase
from indstocks_api import get_indstocks_client

# Import mutual fund functionality
try:
    from mf_price_fetcher import is_mutual_fund_ticker, get_mftool_client
    MF_TOOL_AVAILABLE = True
except ImportError:
    MF_TOOL_AVAILABLE = False
    print("Warning: mf_price_fetcher not available. Mutual fund price fetching will be limited.")
import streamlit as st

def get_file_hash(file_path):
    """Calculate SHA-256 hash of a file"""
    hash_sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()

def process_user_folder(user_folder_path, user_id):
    """
    Process all CSV files in user's folder and move them to archive
    Returns: (success_count, error_count, messages)
    """
    if not user_folder_path or not os.path.exists(user_folder_path):
        return 0, 0, ["❌ User folder path does not exist"]
    
    # Create archive folder if it doesn't exist
    archive_path = os.path.join(user_folder_path, "archive")
    if not os.path.exists(archive_path):
        try:
            os.makedirs(archive_path)
        except Exception as e:
            return 0, 0, [f"❌ Could not create archive folder: {str(e)}"]
    
    # Find all CSV files in the user's folder (not in archive)
    csv_files = glob.glob(os.path.join(user_folder_path, "*.csv"))
    
    if not csv_files:
        return 0, 0, ["ℹ️ No CSV files found in user folder"]
    
    success_count = 0
    error_count = 0
    messages = []
    
    for file_path in csv_files:
        try:
            print(f"🔍 Processing file: {os.path.basename(file_path)}")
            # Check if file was already processed (check hash in database)
            file_hash = get_file_hash(file_path)
            print(f"🔍 File hash: {file_hash[:10]}...")
            
            # Process the file
            success, message = process_single_file(file_path, user_id, file_hash)
            print(f"🔍 Processing result: success={success}, message={message}")
            
            if success:
                # Move file to archive
                filename = os.path.basename(file_path)
                archive_file_path = os.path.join(archive_path, filename)
                
                # If file already exists in archive, add timestamp
                if os.path.exists(archive_file_path):
                    name, ext = os.path.splitext(filename)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"{name}_{timestamp}{ext}"
                    archive_file_path = os.path.join(archive_path, filename)
                
                print(f"🔍 Moving file to archive: {file_path} -> {archive_file_path}")
                shutil.move(file_path, archive_file_path)
                print(f"✅ File moved to archive successfully")
                messages.append(f"✅ {filename}: {message} (moved to archive)")
                success_count += 1
            else:
                print(f"❌ File processing failed: {message}")
                messages.append(f"❌ {os.path.basename(file_path)}: {message}")
                error_count += 1
                
        except Exception as e:
            error_count += 1
            messages.append(f"❌ {os.path.basename(file_path)}: Error - {str(e)}")
    
    return success_count, error_count, messages

def process_single_file(file_path, user_id, file_hash=None):
    """
    Process a single CSV file and save to database
    Returns: (success, message)
    """
    try:
        print(f"🔍 Starting to process file: {os.path.basename(file_path)}")
        # Read CSV file
        df = pd.read_csv(file_path)
        print(f"🔍 CSV loaded with {len(df)} rows")
        
        if df.empty:
            return False, "File is empty"
        
        # Validate required columns (price is not required as it will be fetched automatically)
        required_columns = ['stock_name', 'ticker', 'quantity', 'transaction_type', 'date']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return False, f"Missing required columns: {missing_columns}"
        
        # Extract channel from filename if not present
        if 'channel' not in df.columns or df['channel'].isna().all():
            filename = os.path.basename(file_path)
            channel_name = filename.replace('.csv', '').replace('_', ' ')
            df['channel'] = channel_name
        
        # Ensure date column is datetime
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        
        # Ensure price column exists, if not create it with None values
        if 'price' not in df.columns:
            df['price'] = None
        
        # Fetch historical prices using bulk fetching for better performance
        print(f"🔍 Bulk fetching historical prices for {len(df)} transactions...")
        
        # Prepare tickers and dates for bulk fetching
        tickers_with_dates = []
        for idx, row in df.iterrows():
            ticker = row['ticker']
            transaction_date = row['date']
            
            if pd.isna(transaction_date):
                print(f"⚠️ No valid date for {ticker} at row {idx}, using current price")
                transaction_date = None
            
            tickers_with_dates.append((ticker, transaction_date))
        
        # Bulk fetch prices
        bulk_prices = fetch_prices_bulk(tickers_with_dates)
        
        # Map prices back to DataFrame
        historical_prices = []
        for ticker, transaction_date in tickers_with_dates:
            price = bulk_prices.get(ticker)
            historical_prices.append(price)
        
        # Update prices in DataFrame
        df['price'] = historical_prices
        
        # Show summary
        prices_found = sum(1 for price in historical_prices if price is not None)
        print(f"🔍 Price summary: {prices_found}/{len(historical_prices)} transactions got historical prices")
        
        # Create a file-like object for database saving
        class FileObject:
            def __init__(self, path):
                self.name = os.path.basename(path)
                self.path = path
                self._file = None
            
            def read(self):
                with open(self.path, 'rb') as f:
                    return f.read()
            
            def seek(self, offset, whence=0):
                """Implement seek method for file-like object compatibility"""
                if self._file is None:
                    self._file = open(self.path, 'rb')
                return self._file.seek(offset, whence)
            
            def close(self):
                """Close the file if it's open"""
                if self._file:
                    self._file.close()
                    self._file = None
        
        file_obj = FileObject(file_path)
        
        # Save file to database
        print(f"🔍 Saving file to database: {file_obj.name}")
        file_id, is_new = save_file_to_db(file_obj)
        print(f"🔍 Database save result: file_id={file_id}, is_new={is_new}")
        
        if not is_new:
            print(f"❌ File already exists in database")
            return False, "File already exists in database"
        
        if file_id is None:
            print(f"❌ Failed to save file to database")
            return False, "Failed to save file to database"
        
        # Save transactions to database
        print(f"🔍 Saving transactions to database: file_id={file_id}, user_id={user_id}")
        save_transactions_to_db(file_id, df, user_id)
        print(f"✅ Transactions saved successfully")
        
        return True, f"Processed {len(df)} transactions, {prices_found} prices fetched"
        
    except Exception as e:
        return False, f"Error processing file: {str(e)}"

def fetch_price_with_yfinance(ticker, transaction_date):
    """Fetch price using yfinance as fallback"""
    try:
        import yfinance as yf
        
        def clean_ticker_for_yfinance(ticker):
            """Clean ticker symbol for YFinance compatibility"""
            if not ticker:
                return None
            
            # Remove common prefixes and suffixes
            clean_ticker = str(ticker).strip().upper()
            clean_ticker = clean_ticker.replace('$', '')  # Remove $ prefix
            clean_ticker = clean_ticker.replace('.NS', '.NS')  # Keep .NS suffix
            clean_ticker = clean_ticker.replace('.BO', '.BO')  # Keep .BO suffix
            
            # For Indian stocks, add .NS suffix if not present
            if not clean_ticker.endswith(('.NS', '.BO', '.NSE', '.BSE')):
                clean_ticker = clean_ticker + '.NS'
            
            return clean_ticker
        
        clean_ticker = clean_ticker_for_yfinance(ticker)
        if not clean_ticker:
            print(f"❌ Invalid ticker symbol: {ticker}")
            return None
            
        ticker_obj = yf.Ticker(clean_ticker)
        
        if transaction_date:
            # Get historical data for specific date with wider range
            start_date = transaction_date - pd.Timedelta(days=5)  # 5 days before
            end_date = transaction_date + pd.Timedelta(days=5)    # 5 days after
            
            hist_data = ticker_obj.history(start=start_date, end=end_date)
            
            if not hist_data.empty:
                # Find the closest date to transaction date (handle timezone)
                hist_data_copy = hist_data.copy()
                hist_data_copy['date_diff'] = abs(hist_data_copy.index.tz_localize(None) - transaction_date)
                closest_idx = hist_data_copy['date_diff'].idxmin()
                closest_date = hist_data_copy.loc[closest_idx]
                price = closest_date['Close']
                actual_date = closest_idx.strftime('%Y-%m-%d')
                
                print(f"✅ YFinance Historical: {ticker} ({clean_ticker}) on {actual_date} (closest to {transaction_date.strftime('%Y-%m-%d')}) = ₹{price}")
                return float(price)
            else:
                # Try current price if historical not available
                current_price = ticker_obj.info.get('regularMarketPrice')
                if current_price:
                    print(f"⚠️ YFinance Current: {ticker} ({clean_ticker}) = ₹{current_price} (no historical data)")
                    return float(current_price)
                else:
                    print(f"❌ No price found for {ticker} ({clean_ticker})")
                    return None
        else:
            # Use current price if no date
            current_price = ticker_obj.info.get('regularMarketPrice')
            if current_price:
                print(f"⚠️ YFinance Current: {ticker} ({clean_ticker}) = ₹{current_price} (no date)")
                return float(current_price)
            else:
                print(f"❌ No price found for {ticker} ({clean_ticker})")
                return None
    except Exception as e:
        print(f"❌ YFinance fallback failed for {ticker}: {e}")
        return None

def is_numerical_ticker(ticker):
    """Check if ticker is numerical (likely a mutual fund)"""
    if not ticker:
        return False
    
    # Remove any common suffixes and prefixes
    clean_ticker = str(ticker).strip().upper()
    clean_ticker = clean_ticker.replace('.NS', '').replace('.BO', '').replace('.NSE', '').replace('.BSE', '')
    clean_ticker = clean_ticker.replace('MF_', '')  # Remove MF_ prefix
    
    # Check if it's purely numerical
    return clean_ticker.isdigit()

def fetch_price_smart(ticker, transaction_date):
    """
    Smart price fetching that routes to appropriate tool based on ticker type
    - Numerical tickers (mutual funds) -> mftool
    - Stock tickers -> yfinance -> INDstocks
    """
    try:
        # Convert date to string format if it's a datetime
        date_str = None
        if transaction_date:
            date_str = transaction_date.strftime('%Y-%m-%d')
        
        # Check if it's a numerical ticker (mutual fund)
        if is_numerical_ticker(ticker):
            print(f"🔍 Detected mutual fund ticker: {ticker}")
            
            # Try mftool first for mutual funds
            if MF_TOOL_AVAILABLE:
                try:
                    from mf_price_fetcher import fetch_mutual_fund_price
                    price = fetch_mutual_fund_price(ticker, transaction_date)
                    if price is not None:
                        print(f"✅ MFTool: {ticker} on {date_str or 'current'} = ₹{price}")
                        return price
                except Exception as e:
                    print(f"⚠️ MFTool failed for {ticker}: {e}")
            
            # Fallback to INDstocks for mutual funds
            try:
                api_client = get_indstocks_client()
                if api_client and api_client.available:
                    price_data = api_client.get_stock_price(ticker, date_str)
                    if price_data and price_data.get('price'):
                        price = float(price_data['price'])
                        source = price_data.get('source', 'INDstocks')
                        note = price_data.get('note', '')
                        if note:
                            print(f"✅ {source}: {ticker} on {date_str or 'current'} = ₹{price} ({note})")
                        else:
                            print(f"✅ {source}: {ticker} on {date_str or 'current'} = ₹{price}")
                        return price
            except Exception as e:
                print(f"⚠️ INDstocks failed for mutual fund {ticker}: {e}")
            
            print(f"❌ No price found for mutual fund {ticker}")
            return None
        
        else:
            # Stock ticker - try yfinance first
            print(f"🔍 Detected stock ticker: {ticker}")
            
            # Try yfinance first for stocks
            price = fetch_price_with_yfinance(ticker, transaction_date)
            if price is not None:
                return price
            
            # Fallback to INDstocks for stocks
            try:
                api_client = get_indstocks_client()
                if api_client and api_client.available:
                    price_data = api_client.get_stock_price(ticker, date_str)
                    if price_data and price_data.get('price'):
                        price = float(price_data['price'])
                        source = price_data.get('source', 'INDstocks')
                        note = price_data.get('note', '')
                        if note:
                            print(f"✅ {source}: {ticker} on {date_str or 'current'} = ₹{price} ({note})")
                        else:
                            print(f"✅ {source}: {ticker} on {date_str or 'current'} = ₹{price}")
                        return price
            except Exception as e:
                print(f"⚠️ INDstocks failed for stock {ticker}: {e}")
            
            print(f"❌ No price found for stock {ticker}")
            return None
            
    except Exception as e:
        print(f"❌ Smart price fetching failed for {ticker}: {e}")
        return None

def fetch_prices_bulk(tickers_with_dates):
    """
    Bulk price fetching for multiple tickers with proper batch processing
    Args:
        tickers_with_dates: List of tuples (ticker, transaction_date)
    Returns:
        Dict mapping ticker to price
    """
    import time
    import concurrent.futures
    
    print(f"🔍 Bulk fetching prices for {len(tickers_with_dates)} tickers...")
    
    def fetch_with_timeout():
        # Separate mutual funds and stocks
        mutual_funds = []
        stocks = []
        
        for ticker, date in tickers_with_dates:
            if is_numerical_ticker(ticker):
                mutual_funds.append((ticker, date))
            else:
                stocks.append((ticker, date))
        
        results = {}
        
        # Process mutual funds in batches
        if mutual_funds:
            print(f"🔍 Processing {len(mutual_funds)} mutual funds in batches...")
            mf_results = fetch_mutual_funds_bulk_batched(mutual_funds)
            results.update(mf_results)
        
        # Process stocks in batches
        if stocks:
            print(f"🔍 Processing {len(stocks)} stocks in batches...")
            stock_results = fetch_stocks_bulk_batched(stocks)
            results.update(stock_results)
        
        return results
    
    try:
        # Use ThreadPoolExecutor for timeout protection (cross-platform)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(fetch_with_timeout)
            results = future.result(timeout=90)  # 90 seconds timeout for bulk price fetching
        
        print(f"✅ Bulk fetch completed: {len([v for v in results.values() if v is not None])}/{len(tickers_with_dates)} prices found")
        return results
        
    except concurrent.futures.TimeoutError:
        print("❌ Bulk price fetching timed out")
        return {}
    except Exception as e:
        print(f"❌ Bulk price fetching failed: {e}")
        return {}

def fetch_mutual_funds_bulk_batched(mutual_funds):
    """Bulk fetch mutual fund prices with proper batch processing"""
    import time
    results = {}
    batch_size = 10  # Process 10 mutual funds at a time (reduced for faster processing)
    
    try:
        # Process mutual funds in batches
        for i in range(0, len(mutual_funds), batch_size):
            batch = mutual_funds[i:i + batch_size]
            print(f"🔍 Processing mutual fund batch {i//batch_size + 1}/{(len(mutual_funds) + batch_size - 1)//batch_size} ({len(batch)} items)")
            
            batch_results = fetch_mutual_funds_bulk(batch)
            results.update(batch_results)
            
            # Small delay between batches
            if i + batch_size < len(mutual_funds):
                time.sleep(0.5)
        
        return results
        
    except Exception as e:
        print(f"❌ Batched mutual fund fetching failed: {e}")
        return results

def fetch_mutual_funds_bulk(mutual_funds):
    """Bulk fetch mutual fund prices"""
    results = {}
    
    try:
        # Try mftool first for bulk mutual fund fetching
        if MF_TOOL_AVAILABLE:
            try:
                from mf_price_fetcher import fetch_mutual_funds_bulk as mf_bulk
                mf_prices = mf_bulk(mutual_funds)
                results.update(mf_prices)
                print(f"✅ MFTool bulk: {len([v for v in mf_prices.values() if v is not None])} prices found")
            except Exception as e:
                print(f"⚠️ MFTool bulk failed: {e}")
        
        # For any remaining unfetched mutual funds, try individual fetching
        remaining_mfs = [(ticker, date) for ticker, date in mutual_funds if ticker not in results or results[ticker] is None]
        
        if remaining_mfs:
            print(f"🔍 Individual fetching for {len(remaining_mfs)} remaining mutual funds...")
            for ticker, date in remaining_mfs:
                if ticker not in results or results[ticker] is None:
                    try:
                        price = fetch_price_smart(ticker, date)
                        results[ticker] = price
                        time.sleep(0.1)  # Rate limiting
                    except Exception as e:
                        print(f"⚠️ Failed to fetch {ticker}: {e}")
                        continue
        
        return results
        
    except Exception as e:
        print(f"❌ Bulk mutual fund fetching failed: {e}")
        return results

def fetch_stocks_bulk_batched(stocks):
    """Bulk fetch stock prices with proper batch processing"""
    import time
    results = {}
    batch_size = 15  # Process 15 stocks at a time (reduced for faster processing)
    
    try:
        # Process stocks in batches
        for i in range(0, len(stocks), batch_size):
            batch = stocks[i:i + batch_size]
            print(f"🔍 Processing stock batch {i//batch_size + 1}/{(len(stocks) + batch_size - 1)//batch_size} ({len(batch)} items)")
            
            batch_results = fetch_stocks_bulk(batch)
            results.update(batch_results)
            
            # Small delay between batches
            if i + batch_size < len(stocks):
                time.sleep(0.5)
        
        return results
        
    except Exception as e:
        print(f"❌ Batched stock fetching failed: {e}")
        return results

def fetch_stocks_bulk(stocks):
    """Bulk fetch stock prices"""
    results = {}
    
    try:
        # Try yfinance bulk first
        try:
            yf_prices = fetch_stocks_yfinance_bulk(stocks)
            results.update(yf_prices)
            print(f"✅ YFinance bulk: {len([v for v in yf_prices.values() if v is not None])} prices found")
        except Exception as e:
            print(f"⚠️ YFinance bulk failed: {e}")
        
        # For any remaining unfetched stocks, try INDstocks bulk
        remaining_stocks = [(ticker, date) for ticker, date in stocks if ticker not in results or results[ticker] is None]
        
        if remaining_stocks:
            try:
                ind_prices = fetch_stocks_indstocks_bulk(remaining_stocks)
                results.update(ind_prices)
                print(f"✅ INDstocks bulk: {len([v for v in ind_prices.values() if v is not None])} prices found")
            except Exception as e:
                print(f"⚠️ INDstocks bulk failed: {e}")
        
        # For any still remaining, try individual fetching
        final_remaining = [(ticker, date) for ticker, date in remaining_stocks if ticker not in results or results[ticker] is None]
        
        if final_remaining:
            print(f"🔍 Individual fetching for {len(final_remaining)} remaining stocks...")
            for ticker, date in final_remaining:
                if ticker not in results or results[ticker] is None:
                    try:
                        price = fetch_price_smart(ticker, date)
                        results[ticker] = price
                        time.sleep(0.2)  # Rate limiting
                    except Exception as e:
                        print(f"⚠️ Failed to fetch {ticker}: {e}")
                        continue
        
        return results
        
    except Exception as e:
        print(f"❌ Bulk stock fetching failed: {e}")
        return results

def fetch_stocks_yfinance_bulk(stocks):
    """Bulk fetch stock prices using yfinance"""
    results = {}
    
    try:
        import yfinance as yf
        import time
        
        def clean_ticker_for_yfinance(ticker):
            """Clean ticker symbol for YFinance compatibility"""
            if not ticker:
                return None
            
            # Remove common prefixes and suffixes
            clean_ticker = str(ticker).strip().upper()
            clean_ticker = clean_ticker.replace('$', '')  # Remove $ prefix
            clean_ticker = clean_ticker.replace('.NS', '.NS')  # Keep .NS suffix
            clean_ticker = clean_ticker.replace('.BO', '.BO')  # Keep .BO suffix
            
            # For Indian stocks, add .NS suffix if not present
            if not clean_ticker.endswith(('.NS', '.BO', '.NSE', '.BSE')):
                clean_ticker = clean_ticker + '.NS'
            
            return clean_ticker
        
        # Group stocks by date for efficient fetching
        date_groups = {}
        for ticker, date in stocks:
            date_key = date.strftime('%Y-%m-%d') if date else 'current'
            if date_key not in date_groups:
                date_groups[date_key] = []
            date_groups[date_key].append(ticker)
        
        # Fetch for each date group with limits
        for date_key, tickers in date_groups.items():
            try:
                # Limit tickers per date group to prevent timeout
                tickers = tickers[:10]  # Max 10 tickers per date group (reduced for faster processing)
                
                if date_key == 'current':
                    # Fetch current prices
                    for ticker in tickers:
                        try:
                            clean_ticker = clean_ticker_for_yfinance(ticker)
                            if not clean_ticker:
                                continue
                                
                            ticker_obj = yf.Ticker(clean_ticker)
                            current_price = ticker_obj.info.get('regularMarketPrice')
                            if current_price:
                                results[ticker] = float(current_price)
                                print(f"✅ YFinance Current: {ticker} ({clean_ticker}) = ₹{current_price}")
                            time.sleep(0.1)  # Rate limiting
                        except Exception as e:
                            print(f"⚠️ YFinance failed for {ticker}: {e}")
                else:
                    # Fetch historical prices
                    date_obj = pd.to_datetime(date_key)
                    start_date = date_obj - pd.Timedelta(days=5)
                    end_date = date_obj + pd.Timedelta(days=5)
                    
                    for ticker in tickers:
                        try:
                            clean_ticker = clean_ticker_for_yfinance(ticker)
                            if not clean_ticker:
                                continue
                                
                            ticker_obj = yf.Ticker(clean_ticker)
                            hist_data = ticker_obj.history(start=start_date, end=end_date)
                            
                            if not hist_data.empty:
                                # Find closest date
                                hist_data_copy = hist_data.copy()
                                hist_data_copy['date_diff'] = abs(hist_data_copy.index.tz_localize(None) - date_obj)
                                closest_idx = hist_data_copy['date_diff'].idxmin()
                                closest_date = hist_data_copy.loc[closest_idx]
                                price = closest_date['Close']
                                actual_date = closest_idx.strftime('%Y-%m-%d')
                                
                                results[ticker] = float(price)
                                print(f"✅ YFinance Historical: {ticker} ({clean_ticker}) on {actual_date} = ₹{price}")
                        except Exception as e:
                            print(f"⚠️ YFinance failed for {ticker}: {e}")
                            
            except Exception as e:
                print(f"⚠️ YFinance bulk failed for date {date_key}: {e}")
        
        return results
        
    except Exception as e:
        print(f"❌ YFinance bulk fetching failed: {e}")
        return results

def fetch_stocks_indstocks_bulk(stocks):
    """Bulk fetch stock prices using INDstocks"""
    results = {}
    
    try:
        api_client = get_indstocks_client()
        if not api_client or not api_client.available:
            print("⚠️ INDstocks not available for bulk fetching")
            return results
        
        # Group by date for efficient API calls
        date_groups = {}
        for ticker, date in stocks:
            date_key = date.strftime('%Y-%m-%d') if date else 'current'
            if date_key not in date_groups:
                date_groups[date_key] = []
            date_groups[date_key].append(ticker)
        
        # Fetch for each date group
        for date_key, tickers in date_groups.items():
            try:
                # INDstocks might support bulk fetching, but for now we'll do individual calls
                # with a small delay to avoid rate limiting
                for ticker in tickers:
                    try:
                        price_data = api_client.get_stock_price(ticker, date_key if date_key != 'current' else None)
                        if price_data and price_data.get('price'):
                            price = float(price_data['price'])
                            results[ticker] = price
                            source = price_data.get('source', 'INDstocks')
                            print(f"✅ {source}: {ticker} on {date_key} = ₹{price}")
                        
                        # Small delay to avoid rate limiting
                        import time
                        time.sleep(0.1)
                        
                    except Exception as e:
                        print(f"⚠️ INDstocks failed for {ticker}: {e}")
                        
            except Exception as e:
                print(f"⚠️ INDstocks bulk failed for date {date_key}: {e}")
        
        return results
        
    except Exception as e:
        print(f"❌ INDstocks bulk fetching failed: {e}")
        return results

def get_user_folder_info(user_folder_path):
    """Get information about files in user's folder"""
    if not user_folder_path or not os.path.exists(user_folder_path):
        return {"error": "Folder path does not exist"}
    
    archive_path = os.path.join(user_folder_path, "archive")
    
    # Count files in main folder
    csv_files = glob.glob(os.path.join(user_folder_path, "*.csv"))
    archive_files = glob.glob(os.path.join(archive_path, "*.csv")) if os.path.exists(archive_path) else []
    
    return {
        "main_folder": user_folder_path,
        "archive_folder": archive_path,
        "csv_files_count": len(csv_files),
        "archive_files_count": len(archive_files),
        "csv_files": [os.path.basename(f) for f in csv_files],
        "archive_files": [os.path.basename(f) for f in archive_files]
    }
