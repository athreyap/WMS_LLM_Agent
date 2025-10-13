import os
import time
import threading
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
import hashlib
import json
from pathlib import Path
import glob
import shutil

# Import existing modules
from database_config_supabase import (
    save_transaction_supabase,
    save_file_record_supabase,
    get_user_by_id_supabase
)
from stock_data_agent import stock_agent, force_update_stock

# Import price fetching functions
try:
    from file_manager import get_indstocks_client, get_mftool_client, fetch_price_with_yfinance
    MF_TOOL_AVAILABLE = True
except ImportError:
    MF_TOOL_AVAILABLE = False
    print("⚠️ MF_TOOL not available, using fallback price fetching")

class UserFileReadingAgent:
    """User-specific agentic AI system for reading and processing investment files"""
    
    def __init__(self):
        self.user_agents = {}  # Dictionary to store agents for each user
        self.monitoring = False
        self.monitor_thread = None
        self.check_interval = 30  # Check every 30 seconds
        self.max_retries = 3
        
        print("📁 User File Reading Agent initialized")
    
    def _get_user_folder_path(self, user_id: int) -> Optional[str]:
        """Get user's folder path from database"""
        try:
            user = get_user_by_id_supabase(user_id)
            if user and user.get('folder_path'):
                folder_path = user['folder_path']
                
                # Ensure the folder exists (create if needed)
                folder = Path(folder_path)
                folder.mkdir(parents=True, exist_ok=True)
                
                # Create archive folder
                archive_folder = folder / "archive"
                archive_folder.mkdir(exist_ok=True)
                
                return folder_path
            return None
        except Exception as e:
            print(f"❌ Error getting folder path for user {user_id}: {e}")
            return None
    
    def _create_user_agent(self, user_id: int, folder_path: str):
        """Create a file reading agent for a specific user"""
        try:
            folder = Path(folder_path)
            
            # Create folder if it doesn't exist
            folder.mkdir(parents=True, exist_ok=True)
            
            # Create archive folder
            archive_folder = folder / "archive"
            archive_folder.mkdir(exist_ok=True)
            
            # Initialize user agent data
            user_agent_data = {
                'folder_path': folder,
                'processed_files': set(),
                'file_hashes': {},
                'last_check': datetime.now()
            }
            
            # Load processed files from cache
            self._load_user_processed_files(user_id, user_agent_data)
            
            self.user_agents[user_id] = user_agent_data
            print(f"✅ Created agent for user {user_id} with folder: {folder_path}")
            
        except Exception as e:
            print(f"❌ Error creating agent for user {user_id}: {e}")
    
    def _load_user_processed_files(self, user_id: int, user_agent_data: Dict):
        """Load list of processed files from cache for a specific user"""
        try:
            cache_file = user_agent_data['folder_path'] / f".processed_files_user_{user_id}.json"
            if cache_file.exists():
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    user_agent_data['processed_files'] = set(data.get('processed_files', []))
                    user_agent_data['file_hashes'] = data.get('file_hashes', {})
                print(f"✅ Loaded {len(user_agent_data['processed_files'])} processed files for user {user_id}")
        except Exception as e:
            print(f"⚠️ Could not load processed files cache for user {user_id}: {e}")
    
    def _save_user_processed_files(self, user_id: int, user_agent_data: Dict):
        """Save list of processed files to cache for a specific user"""
        try:
            cache_file = user_agent_data['folder_path'] / f".processed_files_user_{user_id}.json"
            data = {
                'processed_files': list(user_agent_data['processed_files']),
                'file_hashes': user_agent_data['file_hashes'],
                'last_updated': datetime.now().isoformat(),
                'user_id': user_id
            }
            with open(cache_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"⚠️ Could not save processed files cache for user {user_id}: {e}")
    
    def _get_file_hash(self, file_path: Path) -> str:
        """Generate hash for file content"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            print(f"❌ Error generating hash for {file_path}: {e}")
            return ""
    
    def _is_file_modified(self, file_path: Path, user_agent_data: Dict) -> bool:
        """Check if file has been modified since last processing"""
        file_hash = self._get_file_hash(file_path)
        last_hash = user_agent_data['file_hashes'].get(str(file_path), "")
        is_modified = file_hash != last_hash
        
        if is_modified:
            print(f"🔍 File {file_path.name} hash changed: {last_hash[:8]}... -> {file_hash[:8]}...")
        else:
            print(f"🔍 File {file_path.name} hash unchanged: {file_hash[:8]}...")
        
        return is_modified
    
    def _extract_channel_from_filename(self, filename: str) -> str:
        """Extract channel name from filename"""
        # Remove extension and replace underscores with spaces
        channel_name = filename.replace('.csv', '').replace('_', ' ')
        return channel_name
    
    def _read_csv_file(self, file_path: Path) -> Optional[pd.DataFrame]:
        """Read and parse CSV file"""
        try:
            # Try different CSV formats
            df = pd.read_csv(file_path)
            
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
                channel_name = self._extract_channel_from_filename(file_path.name)
                df['channel'] = channel_name
            
            # Ensure required columns exist (price is optional as it will be fetched automatically)
            required_columns = ['ticker', 'quantity', 'transaction_type', 'date']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                print(f"❌ Missing required columns in {file_path.name}: {missing_columns}")
                print(f"ℹ️ Required columns: {required_columns}")
                print(f"ℹ️ Optional columns: price, stock_name, sector")
                print(f"ℹ️ Note: If 'channel' column is missing, it will be auto-generated from the filename")
                print(f"ℹ️ Available columns: {list(df.columns)}")
                print(f"ℹ️ File will be skipped to avoid repeated processing attempts")
                return None
            
            # Ensure price column exists, if not create it with None values
            if 'price' not in df.columns:
                df['price'] = None
                print(f"📝 Price column not found in {file_path.name}, will fetch historical prices")
            
            # Clean and validate data
            df = df.dropna(subset=['ticker', 'quantity'])
            df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce')
            
            # Convert price to numeric if it exists, otherwise keep as None
            if 'price' in df.columns and not df['price'].isna().all():
                df['price'] = pd.to_numeric(df['price'], errors='coerce')
            
            # Remove rows with invalid data
            df = df[df['quantity'] > 0]
            # Only filter by price if price column has valid values
            if 'price' in df.columns and not df['price'].isna().all():
                df = df[df['price'] > 0]
            
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
                print(f"⚠️ No valid transactions found in {file_path.name}")
                return None
            
            # Fetch historical prices for missing price values
            if 'price' in df.columns and df['price'].isna().any():
                print(f"🔍 Fetching historical prices for missing values in {file_path.name}...")
                df = self._fetch_historical_prices(df)
            
            print(f"✅ Successfully read {len(df)} transactions from {file_path.name}")
            return df
            
        except Exception as e:
            print(f"❌ Error reading {file_path.name}: {e}")
            return None
    
    def _process_file(self, file_path: Path, user_id: int, user_agent_data: Dict) -> bool:
        """Process a single CSV file for a specific user"""
        try:
            print(f"🔄 Processing file: {file_path.name} for user {user_id}")
            
            # Read CSV file
            df = self._read_csv_file(file_path)
            if df is None:
                # Mark file as processed (even though it failed) to avoid repeated attempts
                file_hash = self._get_file_hash(file_path)
                user_agent_data['file_hashes'][str(file_path)] = file_hash
                user_agent_data['processed_files'].add(str(file_path))
                print(f"⚠️ Skipping {file_path.name} due to missing required columns - marked as processed to avoid repeated attempts")
                return False
            
            # Save file to database using Supabase client
            try:
                # Get username from user context or use a placeholder
                username = f"user_{user_id}"  # Placeholder - ideally should be passed from calling context
                file_record = save_file_record_supabase(
                    filename=file_path.name,
                    file_path=str(file_path),
                    user_id=user_id,
                    username=username
                )
                
                if file_record is None:
                    print(f"❌ Failed to save file record for {file_path.name}")
                    return False
                
                # Save transactions to database using Supabase client
                from database_config_supabase import save_transactions_bulk_supabase
                success = save_transactions_bulk_supabase(
                    df=df,
                    file_id=file_record['id'],
                    user_id=user_id
                )
                
                if success:
                    # Update file hash
                    file_hash = self._get_file_hash(file_path)
                    user_agent_data['file_hashes'][str(file_path)] = file_hash
                    user_agent_data['processed_files'].add(str(file_path))
                    
                    # Trigger stock data updates for new tickers
                    new_tickers = df['ticker'].unique().tolist()
                    self._update_stock_data_for_tickers(new_tickers)
                    
                    print(f"✅ Successfully processed {file_path.name} for user {user_id}")
                    return True
                else:
                    print(f"❌ Failed to save transactions for {file_path.name}")
                    return False
                    
            except Exception as e:
                print(f"❌ Error saving to database: {e}")
                return False
                
        except Exception as e:
            print(f"❌ Error processing {file_path.name} for user {user_id}: {e}")
            return False
    
    def _fetch_historical_prices(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fetch historical prices for missing price values using bulk fetching"""
        try:
            print(f"🔍 Bulk fetching historical prices for {len(df)} transactions...")
            
            # Prepare tickers and dates for bulk fetching
            tickers_with_dates = []
            price_indices = []  # Track which rows need price fetching
            
            for idx, row in df.iterrows():
                ticker = row['ticker']
                transaction_date = row['date']
                current_price = row['price']
                
                # If price is already available, keep it
                if pd.notna(current_price) and current_price > 0:
                    continue
                
                if pd.isna(transaction_date):
                    print(f"⚠️ No valid date for {ticker} at row {idx}, using current price")
                    transaction_date = None
                
                tickers_with_dates.append((ticker, transaction_date))
                price_indices.append(idx)
            
            if not tickers_with_dates:
                print("ℹ️ No prices need to be fetched")
                return df
            
            # Bulk fetch prices
            from file_manager import fetch_prices_bulk
            bulk_prices = fetch_prices_bulk(tickers_with_dates)
            
            # Update prices in DataFrame
            for i, (ticker, transaction_date) in enumerate(tickers_with_dates):
                idx = price_indices[i]
                price = bulk_prices.get(ticker)
                df.at[idx, 'price'] = price
            
            # Show summary
            prices_found = sum(1 for price in bulk_prices.values() if price is not None)
            print(f"🔍 Price summary: {prices_found}/{len(tickers_with_dates)} transactions got historical prices")
            
            return df
            
        except Exception as e:
            print(f"❌ Error fetching historical prices: {e}")
            return df

    def _update_stock_data_for_tickers(self, tickers: List[str]):
        """Update stock data for new tickers using bulk updates"""
        try:
            print(f"🔄 Bulk updating stock data for {len(tickers)} tickers...")
            
            # Use bulk update from stock_data_agent
            from stock_data_agent import stock_agent
            result = stock_agent._bulk_update_stock_data(tickers)
            
            print(f"✅ Bulk stock data update completed: {result['updated']} updated, {result['failed']} failed")
                
        except Exception as e:
            print(f"❌ Error updating stock data: {e}")
    
    def _scan_for_new_files(self, user_id: int, user_agent_data: Dict) -> List[Path]:
        """Scan user's folder for new or modified CSV files"""
        try:
            csv_files = list(user_agent_data['folder_path'].glob("*.csv"))
            new_files = []
            
            for file_path in csv_files:
                file_path_str = str(file_path)
                
                # Check if file is new (not in processed files)
                if file_path_str not in user_agent_data['processed_files']:
                    new_files.append(file_path)
                    continue
                
                # Check if file has been modified (hash changed)
                if self._is_file_modified(file_path, user_agent_data):
                    print(f"🔄 File {file_path.name} has been modified, will reprocess")
                    new_files.append(file_path)
                    continue
                
                # File is already processed and not modified, skip it
                print(f"ℹ️ File {file_path.name} already processed and unchanged, skipping")
            
            return new_files
            
        except Exception as e:
            print(f"❌ Error scanning for new files for user {user_id}: {e}")
            return []
    
    def _monitor_user_folders(self):
        """Background thread for monitoring all user folders"""
        print("🔄 Starting user folder monitoring...")
        
        while self.monitoring:
            try:
                # Check each user's folder
                for user_id, user_agent_data in list(self.user_agents.items()):
                    try:
                        # Scan for new files
                        new_files = self._scan_for_new_files(user_id, user_agent_data)
                
                        if new_files:
                            print(f"📁 Found {len(new_files)} new/modified files for user {user_id}")
                            
                            for file_path in new_files:
                                self._process_file(file_path, user_id, user_agent_data)
                            
                            # Save processed files cache
                            self._save_user_processed_files(user_id, user_agent_data)
                            
                            # Update last check time
                            user_agent_data['last_check'] = datetime.now()
                            
                    except Exception as e:
                        print(f"❌ Error monitoring folder for user {user_id}: {e}")
                
                # Wait before next scan
                time.sleep(self.check_interval)
                
            except Exception as e:
                print(f"❌ Error in user folder monitoring: {e}")
                time.sleep(60)  # Wait 1 minute on error
    
    def start_monitoring(self):
        """Start monitoring all user folders"""
        if not self.monitoring:
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self._monitor_user_folders, daemon=True)
            self.monitor_thread.start()
            print("✅ User folder monitoring started")
    
    def stop_monitoring(self):
        """Stop monitoring all user folders"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        print("⏹️ User folder monitoring stopped")
    
    def process_user_files(self, user_id: int, folder_path: str = None) -> Dict:
        """Process all CSV files for a specific user"""
        try:
            # Get user's folder path if not provided
            if not folder_path:
                folder_path = self._get_user_folder_path(user_id)
                if not folder_path:
                    return {'processed': 0, 'failed': 0, 'total': 0, 'error': 'User folder path not found'}
            
            # Create user agent if not exists
            if user_id not in self.user_agents:
                self._create_user_agent(user_id, folder_path)
            
            user_agent_data = self.user_agents[user_id]
            csv_files = list(user_agent_data['folder_path'].glob("*.csv"))
            
            if not csv_files:
                print(f"ℹ️ No CSV files found in user {user_id}'s folder")
                return {'processed': 0, 'failed': 0, 'total': 0}
            
            print(f"🔄 Processing {len(csv_files)} CSV files for user {user_id}...")
            
            processed_count = 0
            failed_count = 0
            
            for file_path in csv_files:
                if self._process_file(file_path, user_id, user_agent_data):
                    processed_count += 1
                else:
                    failed_count += 1
            
            # Save processed files cache
            self._save_user_processed_files(user_id, user_agent_data)
            
            result = {
                'processed': processed_count,
                'failed': failed_count,
                'total': len(csv_files)
            }
            
            print(f"✅ Processing completed for user {user_id}: {processed_count} successful, {failed_count} failed")
            return result
            
        except Exception as e:
            print(f"❌ Error processing files for user {user_id}: {e}")
            return {'processed': 0, 'failed': 0, 'total': 0, 'error': str(e)}
    
    def reprocess_user_file(self, user_id: int, filename: str) -> bool:
        """Reprocess a specific file for a user"""
        try:
            if user_id not in self.user_agents:
                folder_path = self._get_user_folder_path(user_id)
                if not folder_path:
                    return False
                self._create_user_agent(user_id, folder_path)
            
            user_agent_data = self.user_agents[user_id]
            file_path = user_agent_data['folder_path'] / filename
            
            if not file_path.exists():
                print(f"❌ File not found: {filename} for user {user_id}")
                return False
            
            # Remove from processed files to force reprocessing
            user_agent_data['processed_files'].discard(str(file_path))
            
            # Process the file
            success = self._process_file(file_path, user_id, user_agent_data)
            
            if success:
                self._save_user_processed_files(user_id, user_agent_data)
            
            return success
            
        except Exception as e:
            print(f"❌ Error reprocessing {filename} for user {user_id}: {e}")
            return False
    
    def get_user_processing_status(self, user_id: int) -> Dict:
        #"""Get status of file processing for a specific user"""
        try:
            if user_id not in self.user_agents:
                folder_path = self._get_user_folder_path(user_id)
                if not folder_path:
                    return {'error': 'User folder path not found'}
                self._create_user_agent(user_id, folder_path)
            
            user_agent_data = self.user_agents[user_id]
            csv_files = list(user_agent_data['folder_path'].glob("*.csv"))
        
            processed_files = []
            unprocessed_files = []
        
            for file_path in csv_files:
                if str(file_path) in user_agent_data['processed_files']:
                    processed_files.append(file_path.name)
                else:
                    unprocessed_files.append(file_path.name)
        
            return {
                'user_id': user_id,
                'total_files': len(csv_files),
                'processed_files': processed_files,
                'unprocessed_files': unprocessed_files,
                'monitoring_active': self.monitoring,
                'folder_path': str(user_agent_data['folder_path'])
            }
        
        except Exception as e:
            print(f"❌ Error getting processing status for user {user_id}: {e}")
            return {'error': str(e)}
    
    def cleanup_user_old_files(self, user_id: int, days: int = 30):
        """Clean up old processed files for a specific user"""
        try:
            if user_id not in self.user_agents:
                folder_path = self._get_user_folder_path(user_id)
                if not folder_path:
                    return
                self._create_user_agent(user_id, folder_path)
            
            user_agent_data = self.user_agents[user_id]
            cutoff_date = datetime.now() - timedelta(days=days)
            cleaned_count = 0
            
            for file_path in user_agent_data['folder_path'].glob("*.csv"):
                if file_path.stat().st_mtime < cutoff_date.timestamp():
                    # Move to archive folder
                    archive_folder = user_agent_data['folder_path'] / "archive"
                    archive_folder.mkdir(exist_ok=True)
                    
                    archive_path = archive_folder / file_path.name
                    shutil.move(str(file_path), str(archive_path))
                    
                    # Remove from processed files
                    user_agent_data['processed_files'].discard(str(file_path))
                    user_agent_data['file_hashes'].pop(str(file_path), None)
                    
                    cleaned_count += 1
            
            if cleaned_count > 0:
                self._save_user_processed_files(user_id, user_agent_data)
                print(f"✅ Cleaned up {cleaned_count} old files for user {user_id}")
            
        except Exception as e:
            print(f"❌ Error cleaning up old files for user {user_id}: {e}")
    
    def _fetch_historical_prices_for_upload(self, df):
        """Fetch historical prices for uploaded file data - BATCH PROCESSING"""
        try:
            import streamlit as st
            print("🔄 **Batch Historical Price Fetching** - Processing uploaded file...")
            
            # Ensure price column exists
            if 'price' not in df.columns:
                df['price'] = None
                print("📝 Price column not found, creating it with None values")
            
            # Validate required columns exist - CRITICAL SECURITY CHECK
            required_columns = ['ticker', 'date']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                error_msg = f"❌ SECURITY ERROR: Missing required columns: {missing_columns}. File processing stopped."
                print(error_msg)
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
                    
                    # Only fetch if price is missing
                    if pd.isna(row['price']) or row['price'] == 0:
                        ticker_date_pairs.append((ticker, transaction_date))
                        price_indices.append(idx)
                except KeyError as e:
                    error_msg = f"❌ SECURITY ERROR: Missing column in row {idx}: {e}. File processing stopped."
                    print(error_msg)
                    raise ValueError(error_msg)
                except Exception as e:
                    error_msg = f"❌ SECURITY ERROR: Error processing row {idx}: {e}. File processing stopped."
                    print(error_msg)
                    raise ValueError(error_msg)
            
            if not ticker_date_pairs:
                print("ℹ️ All transactions already have historical prices")
                return df
            
            print(f"📊 Fetching historical prices for {len(ticker_date_pairs)} transactions...")
            
            # Batch fetch prices
            prices_found = 0
            
            for i, (ticker, transaction_date) in enumerate(ticker_date_pairs):
                try:
                    # Check if it's a mutual fund (numeric ticker or MF_ prefixed)
                    clean_ticker = str(ticker).strip().upper()
                    clean_ticker = clean_ticker.replace('.NS', '').replace('.BO', '').replace('.NSE', '').replace('.BSE', '')
                    
                    if clean_ticker.isdigit() or clean_ticker.startswith('MF_'):
                        # Mutual fund - use unified approach with target date
                        print(f"🔍 Fetching historical price for MF {ticker} - Target Date: {transaction_date}")
                        try:
                            # Convert transaction_date to string format if it's a datetime object
                            if hasattr(transaction_date, 'strftime'):
                                target_date = transaction_date.strftime('%Y-%m-%d')
                            else:
                                target_date = str(transaction_date)
                            
                            # Use the unified mutual fund price fetching from unified_price_fetcher
                            from unified_price_fetcher import get_mutual_fund_price
                            price = get_mutual_fund_price(ticker, clean_ticker, user_id, target_date=target_date)
                            
                            if price and price > 0:
                                idx = price_indices[i]
                                df.at[idx, 'price'] = price
                                # Set sector to Mutual Funds for mutual fund tickers
                                if 'sector' not in df.columns:
                                    df['sector'] = None
                                if 'stock_name' not in df.columns:
                                    df['stock_name'] = None
                                df.at[idx, 'sector'] = 'Mutual Funds'
                                df.at[idx, 'stock_name'] = f"MF-{ticker}"
                                prices_found += 1
                                print(f"✅ MF {ticker}: Historical price ₹{price} fetched for transaction date {target_date} - Mutual Funds")
                                print(f"   📊 Transaction: {target_date} → Price: ₹{price} → Sector: Mutual Funds")
                            else:
                                print(f"❌ MF {ticker}: No historical price available for {target_date}")
                        except Exception as e:
                            print(f"⚠️ Error fetching MF price for {ticker}: {e}")
                    else:
                        # Regular stock - use unified approach with target date
                        print(f"🔍 Fetching historical price for stock {ticker} - Target Date: {transaction_date}")
                        try:
                            # Convert transaction_date to string format if it's a datetime object
                            if hasattr(transaction_date, 'strftime'):
                                target_date = transaction_date.strftime('%Y-%m-%d')
                            else:
                                target_date = str(transaction_date)
                            
                            # Use the unified stock price fetching from unified_price_fetcher
                            from unified_price_fetcher import get_stock_price
                            price = get_stock_price(ticker, clean_ticker, target_date=target_date)
                            
                            if price and price > 0:
                                idx = price_indices[i]
                                df.at[idx, 'price'] = price
                                prices_found += 1
                                print(f"✅ {ticker}: Historical price ₹{price} fetched for transaction date {target_date}")
                                print(f"   📊 Transaction: {target_date} → Price: ₹{price}")
                            else:
                                print(f"❌ {ticker}: No historical price available for {target_date}")
                        except Exception as e:
                            print(f"⚠️ Error fetching stock price for {ticker}: {e}")
                    
                except Exception as e:
                    print(f"⚠️ Error fetching historical price for {ticker}: {e}")
            
            # Final status
            print(f"✅ **Historical Price Fetch Complete**: {prices_found}/{len(ticker_date_pairs)} transactions got prices")
            
            # Detailed summary logging
            print(f"\n📊 HISTORICAL PRICE FETCHING SUMMARY:")
            print(f"   🎯 Target transactions: {len(ticker_date_pairs)}")
            print(f"   ✅ Prices found: {prices_found}")
            print(f"   ❌ Prices missing: {len(ticker_date_pairs) - prices_found}")
            print(f"   📈 Success rate: {(prices_found/len(ticker_date_pairs)*100):.1f}%")
            
            if prices_found > 0:
                print(f"   💰 Sample prices fetched:")
                # Show first few successful prices
                for i, (ticker, transaction_date) in enumerate(ticker_date_pairs[:5]):
                    if i < len(price_indices):
                        idx = price_indices[i]
                        fetched_price = df.at[idx, 'price']
                        if pd.notna(fetched_price) and fetched_price > 0:
                            print(f"      • {ticker}: {transaction_date} → ₹{fetched_price}")
            
            return df
            
        except Exception as e:
            print(f"❌ Error in batch historical price fetching: {e}")
            return df
    
    def _process_uploaded_file_direct(self, df: pd.DataFrame, user_id: int, filename: str) -> bool:
        """Process uploaded file data directly without saving to disk"""
        try:
            print(f"🔄 Processing uploaded file directly: {filename} for user {user_id}")
            
            # Create user agent if not exists
            if user_id not in self.user_agents:
                folder_path = self._get_user_folder_path(user_id)
                if not folder_path:
                    print(f"❌ No folder path found for user {user_id}")
                    return False
                self._create_user_agent(user_id, folder_path)
            
            user_agent_data = self.user_agents[user_id]
            
            # Step 1: Fetch historical prices for missing price values
            if 'price' not in df.columns or df['price'].isna().any():
                print(f"🔍 Fetching historical prices for {filename}...")
                try:
                    df = self._fetch_historical_prices_for_upload(df)
                except ValueError as e:
                    print(f"❌ SECURITY ERROR: {e}")
                    return False
            
            # Step 2: Save file record and transactions to database
            try:
                # Get username from user context or use a placeholder
                username = f"user_{user_id}"  # Placeholder - ideally should be passed from calling context
                file_record = save_file_record_supabase(
                    filename=filename,
                    file_path=f"uploaded_{filename}",  # Virtual path for uploaded files
                    user_id=user_id,
                    username=username
                )
                
                if file_record is None:
                    print(f"❌ Failed to save file record for {filename}")
                    return False
                
                # Save transactions to database using Supabase client
                from database_config_supabase import save_transactions_bulk_supabase
                success = save_transactions_bulk_supabase(
                    df=df,
                    file_id=file_record['id'],
                    user_id=user_id
                )
                
                if success:
                    # Step 3: Fetch live prices and sector data for new tickers
                    new_tickers = df['ticker'].unique().tolist()
                    print(f"🔄 Fetching live prices and sector data for {len(new_tickers)} tickers...")
                    
                    # Use stock_agent to fetch fresh live prices and sector data
                    from stock_data_agent import stock_agent
                    for ticker in new_tickers:
                        try:
                            # Check if it's a mutual fund (numeric ticker or MF_ prefixed)
                            is_mf = ticker.isdigit() or ticker.startswith('MF_')
                            
                            if is_mf:
                                # Use mftool for mutual funds
                                from mf_price_fetcher import fetch_mutual_fund_price
                                live_price = fetch_mutual_fund_price(ticker)
                                sector = 'Mutual Funds'
                                stock_name = f"MF-{ticker}"
                            else:
                                # Use stock_agent for regular stocks
                                stock_data = stock_agent._fetch_stock_data(ticker)
                                live_price = stock_data.get('live_price') if stock_data else None
                                sector = stock_data.get('sector') if stock_data else None
                                stock_name = stock_data.get('stock_name') if stock_data else None
                            
                            # Update stock_data table
                            if live_price:
                                from database_config_supabase import update_stock_data_supabase
                                update_stock_data_supabase(
                                    ticker=ticker,
                                    current_price=live_price,
                                    sector=sector,
                                    stock_name=stock_name
                                )
                                print(f"✅ {ticker}: Live=₹{live_price}, Sector={sector}")
                            else:
                                print(f"❌ {ticker}: No live price available")
                                
                        except Exception as e:
                            print(f"❌ Error updating stock data for {ticker}: {e}")
                    
                    # Mark as processed (no file hash needed for direct uploads)
                    user_agent_data['processed_files'].add(f"uploaded_{filename}")
                    
                    # Save processed files cache
                    self._save_user_processed_files(user_id, user_agent_data)
                    
                    print(f"✅ Successfully processed uploaded file {filename} for user {user_id}")
                    return True
                else:
                    print(f"❌ Failed to save transactions for {filename}")
                    return False
                    
            except Exception as e:
                print(f"❌ Error saving to database: {e}")
                return False
                
        except Exception as e:
            print(f"❌ Error processing uploaded file {filename} for user {user_id}: {e}")
            return False
    
    def _process_uploaded_file(self, file_path: str, user_id: int, df: pd.DataFrame) -> bool:
        """Process an uploaded file that has already been processed with historical prices"""
        try:
            print(f"🔄 Processing uploaded file: {file_path} for user {user_id}")
            
            # Create user agent if not exists
            if user_id not in self.user_agents:
                folder_path = self._get_user_folder_path(user_id)
                if not folder_path:
                    print(f"❌ No folder path found for user {user_id}")
                    return False
                self._create_user_agent(user_id, folder_path)
            
            user_agent_data = self.user_agents[user_id]
            file_path_obj = Path(file_path)
            
            # Save file to database using Supabase client
            try:
                # Get username from user context or use a placeholder
                username = f"user_{user_id}"  # Placeholder - ideally should be passed from calling context
                file_record = save_file_record_supabase(
                    filename=file_path_obj.name,
                    file_path=str(file_path_obj),
                    user_id=user_id,
                    username=username
                )
                
                if file_record is None:
                    print(f"❌ Failed to save file record for {file_path_obj.name}")
                    return False
                
                # Save transactions to database using Supabase client
                from database_config_supabase import save_transactions_bulk_supabase
                success = save_transactions_bulk_supabase(
                    df=df,
                    file_id=file_record['id'],
                    user_id=user_id
                )
                
                if success:
                    # Update file hash and mark as processed
                    file_hash = self._get_file_hash(file_path_obj)
                    user_agent_data['file_hashes'][str(file_path_obj)] = file_hash
                    user_agent_data['processed_files'].add(str(file_path_obj))
                    
                    # Trigger stock data updates for new tickers
                    new_tickers = df['ticker'].unique().tolist()
                    self._update_stock_data_for_tickers(new_tickers)
                    
                    # Save processed files cache
                    self._save_user_processed_files(user_id, user_agent_data)
                    
                    print(f"✅ Successfully processed uploaded file {file_path_obj.name} for user {user_id}")
                    return True
                else:
                    print(f"❌ Failed to save transactions for {file_path_obj.name}")
                    return False
                    
            except Exception as e:
                print(f"❌ Error saving to database: {e}")
                return False
                
        except Exception as e:
            print(f"❌ Error processing uploaded file {file_path} for user {user_id}: {e}")
            return False

# Global instance
user_file_agent = UserFileReadingAgent()

# Helper functions for easy access
def start_user_file_monitoring():
    """Start monitoring all user folders"""
    user_file_agent.start_monitoring()

def stop_user_file_monitoring():
    """Stop monitoring all user folders"""
    user_file_agent.stop_monitoring()

def process_user_files_on_login(user_id: int) -> Dict:
    """Process all CSV files for a user when they log in"""
    return user_file_agent.process_user_files(user_id)

def get_user_transactions_data(user_id: int) -> Dict:
    """Get user's transaction data and processing status"""
    return user_file_agent.get_user_processing_status(user_id)

def reprocess_user_investment_file(user_id: int, filename: str) -> bool:
    """Reprocess a specific investment file for a user"""
    return user_file_agent.reprocess_user_file(user_id, filename)

def cleanup_user_old_investment_files(user_id: int, days: int = 30):
    """Clean up old investment files for a user"""
    user_file_agent.cleanup_user_old_files(user_id, days)

# Auto-start monitoring when module is imported
if __name__ != "__main__":
    # Start monitoring in background
    start_user_file_monitoring()
