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
from database_config_supabase import save_transaction_supabase, save_file_record_supabase, fetch_historical_prices_background
from stock_data_agent import stock_agent, force_update_stock

# Import price fetching functions
try:
    from file_manager import get_indstocks_client, get_mftool_client, fetch_price_with_yfinance
    MF_TOOL_AVAILABLE = True
except ImportError:
    MF_TOOL_AVAILABLE = False
    print("⚠️ MF_TOOL not available, using fallback price fetching")

class FileReadingAgent:
    """Agentic AI system for reading and processing investment files"""
    
    def __init__(self, folder_path: str = "investments"):
        self.folder_path = Path(folder_path)
        self.processed_files = set()
        self.file_hashes = {}
        self.monitoring = False
        self.monitor_thread = None
        self.check_interval = 30  # Check every 30 seconds
        self.max_retries = 3
        
        # Create folder if it doesn't exist
        self.folder_path.mkdir(exist_ok=True)
        
        # Load processed files from cache
        self._load_processed_files()
        
        print(f"📁 File Reading Agent initialized for folder: {self.folder_path}")
    
    def _load_processed_files(self):
        """Load list of processed files from cache"""
        try:
            cache_file = self.folder_path / ".processed_files.json"
            if cache_file.exists():
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    self.processed_files = set(data.get('processed_files', []))
                    self.file_hashes = data.get('file_hashes', {})
                print(f"✅ Loaded {len(self.processed_files)} processed files from cache")
        except Exception as e:
            print(f"⚠️ Could not load processed files cache: {e}")
    
    def _save_processed_files(self):
        """Save list of processed files to cache"""
        try:
            cache_file = self.folder_path / ".processed_files.json"
            data = {
                'processed_files': list(self.processed_files),
                'file_hashes': self.file_hashes,
                'last_updated': datetime.now().isoformat()
            }
            with open(cache_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"⚠️ Could not save processed files cache: {e}")
    
    def _get_file_hash(self, file_path: Path) -> str:
        """Generate hash for file content"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            print(f"❌ Error generating hash for {file_path}: {e}")
            return ""
    
    def _is_file_modified(self, file_path: Path) -> bool:
        """Check if file has been modified since last processing"""
        file_hash = self._get_file_hash(file_path)
        last_hash = self.file_hashes.get(str(file_path), "")
        return file_hash != last_hash
    
    def _extract_channel_from_filename(self, filename: str) -> str:
        """Extract channel name from filename"""
        # Remove timestamp and extension
        name_parts = filename.replace('.csv', '').split('_')
        if len(name_parts) >= 2:
            # Remove timestamp (last part)
            channel_parts = name_parts[:-1]
            return '_'.join(channel_parts)
        return "default"
    
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
            required_columns = ['stock_name', 'ticker', 'quantity', 'transaction_type', 'date']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                print(f"❌ Missing required columns in {file_path.name}: {missing_columns}")
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
    
    def _process_file(self, file_path: Path, user_id: int = 1) -> bool:
        """Process a single CSV file"""
        try:
            print(f"🔄 Processing file: {file_path.name}")
            
            # Read CSV file
            df = self._read_csv_file(file_path)
            if df is None:
                return False
            
                            # Save file to database using Supabase
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
                
                # Save transactions to database using Supabase
                success = True
                for _, row in df.iterrows():
                    transaction_success = save_transaction_supabase(
                        user_id=user_id,
                        stock_name=row['stock_name'],
                        ticker=row['ticker'],
                        quantity=row['quantity'],
                        price=row['price'],
                        transaction_type=row['transaction_type'],
                        date=row['date'],
                        channel=row.get('channel'),
                        sector=row.get('sector')
                    )
                    if not transaction_success:
                        success = False
                        break
                
                if success:
                    # Update file hash
                    file_hash = self._get_file_hash(file_path)
                    self.file_hashes[str(file_path)] = file_hash
                    self.processed_files.add(str(file_path))
                    
                    # Trigger stock data updates for new tickers
                    new_tickers = df['ticker'].unique().tolist()
                    self._update_stock_data_for_tickers(new_tickers)
                    
                    print(f"✅ Successfully processed {file_path.name}")
                    return True
                else:
                    print(f"❌ Failed to save transactions for {file_path.name}")
                    return False
                    
            except Exception as e:
                print(f"❌ Error saving to database: {e}")
                return False
                
        except Exception as e:
            print(f"❌ Error processing {file_path.name}: {e}")
            return False
    
    def _fetch_historical_prices(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fetch historical prices for missing price values"""
        try:
            print(f"🔍 Fetching historical prices for {len(df)} transactions...")
            api_client = get_indstocks_client()
            mf_client = get_mftool_client() if MF_TOOL_AVAILABLE else None
            historical_prices = []
            
            for idx, row in df.iterrows():
                ticker = row['ticker']
                transaction_date = row['date']
                current_price = row['price']
                
                # If price is already available, keep it
                if pd.notna(current_price) and current_price > 0:
                    historical_prices.append(current_price)
                    continue
                
                if pd.isna(transaction_date):
                    print(f"⚠️ No valid date for {ticker} at row {idx}, using current price")
                    transaction_date = None
                
                try:
                    # Convert date to string format if it's a datetime
                    date_str = None
                    if transaction_date:
                        date_str = transaction_date.strftime('%Y-%m-%d')
                    
                    # Try yfinance first for historical data (more reliable for historical prices)
                    price = fetch_price_with_yfinance(ticker, transaction_date)
                    if price is not None:
                        historical_prices.append(price)
                        print(f"✅ yfinance: {ticker} on {date_str or 'current'} = ₹{price}")
                    else:
                        # Fallback to INDstocks if yfinance fails
                        if api_client and api_client.available:
                            price_data = api_client.get_stock_price(ticker, date_str)
                            if price_data and price_data.get('price'):
                                historical_prices.append(float(price_data['price']))
                                source = price_data.get('source', 'unknown')
                                note = price_data.get('note', '')
                                if note:
                                    print(f"✅ {source}: {ticker} on {date_str or 'current'} = ₹{price_data['price']} ({note})")
                                else:
                                    print(f"✅ {source}: {ticker} on {date_str or 'current'} = ₹{price_data['price']}")
                            else:
                                historical_prices.append(None)
                                print(f"❌ No price found for {ticker}")
                        else:
                            historical_prices.append(None)
                            print(f"❌ No price found for {ticker}")
                except Exception as e:
                    print(f"❌ Error fetching price for {ticker}: {e}")
                    historical_prices.append(None)
            
            # Update prices in DataFrame
            df['price'] = historical_prices
            
            # Show summary
            prices_found = sum(1 for price in historical_prices if price is not None)
            print(f"🔍 Price summary: {prices_found}/{len(historical_prices)} transactions got historical prices")
            
            return df
            
        except Exception as e:
            print(f"❌ Error fetching historical prices: {e}")
            return df

    def _update_stock_data_for_tickers(self, tickers: List[str]):
        """Update stock data for new tickers"""
        try:
            print(f"🔄 Updating stock data for {len(tickers)} tickers...")
            
            for ticker in tickers:
                if ticker and ticker.strip():
                    # Force update stock data
                    success = force_update_stock(ticker.strip())
                    if success:
                        print(f"✅ Updated stock data for {ticker}")
                    else:
                        print(f"⚠️ Failed to update stock data for {ticker}")
                    
                    time.sleep(0.1)  # Small delay to avoid rate limiting
            
            print("✅ Stock data update completed")
            
        except Exception as e:
            print(f"❌ Error updating stock data: {e}")
    
    def _scan_for_new_files(self) -> List[Path]:
        """Scan folder for new or modified CSV files"""
        try:
            csv_files = list(self.folder_path.glob("*.csv"))
            new_files = []
            
            for file_path in csv_files:
                # Check if file is new or modified
                if (str(file_path) not in self.processed_files or 
                    self._is_file_modified(file_path)):
                    new_files.append(file_path)
            
            return new_files
            
        except Exception as e:
            print(f"❌ Error scanning for new files: {e}")
            return []
    
    def _monitor_folder(self):
        """Background thread for monitoring folder"""
        print("🔄 Starting folder monitoring...")
        
        while self.monitoring:
            try:
                # Scan for new files
                new_files = self._scan_for_new_files()
                
                if new_files:
                    print(f"📁 Found {len(new_files)} new/modified files")
                    
                    for file_path in new_files:
                        self._process_file(file_path)
                    
                    # Save processed files cache
                    self._save_processed_files()
                
                # Wait before next scan
                time.sleep(self.check_interval)
                
            except Exception as e:
                print(f"❌ Error in folder monitoring: {e}")
                time.sleep(60)  # Wait 1 minute on error
    
    def start_monitoring(self):
        """Start monitoring the folder for new files"""
        if not self.monitoring:
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self._monitor_folder, daemon=True)
            self.monitor_thread.start()
            print("✅ Folder monitoring started")
    
    def stop_monitoring(self):
        """Stop monitoring the folder"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        print("⏹️ Folder monitoring stopped")
    
    def process_all_files(self, user_id: int = 1) -> Dict:
        """Process all CSV files in the folder"""
        try:
            csv_files = list(self.folder_path.glob("*.csv"))
            
            if not csv_files:
                print("ℹ️ No CSV files found in the folder")
                return {'processed': 0, 'failed': 0, 'total': 0}
            
            print(f"🔄 Processing {len(csv_files)} CSV files...")
            
            processed_count = 0
            failed_count = 0
            
            for file_path in csv_files:
                if self._process_file(file_path, user_id):
                    processed_count += 1
                else:
                    failed_count += 1
            
            # Save processed files cache
            self._save_processed_files()
            
            result = {
                'processed': processed_count,
                'failed': failed_count,
                'total': len(csv_files)
            }
            
            print(f"✅ Processing completed: {processed_count} successful, {failed_count} failed")
            return result
            
        except Exception as e:
            print(f"❌ Error processing all files: {e}")
            return {'processed': 0, 'failed': 0, 'total': 0, 'error': str(e)}
    
    def reprocess_file(self, filename: str, user_id: int = 1) -> bool:
        """Reprocess a specific file"""
        try:
            file_path = self.folder_path / filename
            
            if not file_path.exists():
                print(f"❌ File not found: {filename}")
                return False
            
            # Remove from processed files to force reprocessing
            self.processed_files.discard(str(file_path))
            
            # Process the file
            success = self._process_file(file_path, user_id)
            
            if success:
                self._save_processed_files()
            
            return success
            
        except Exception as e:
            print(f"❌ Error reprocessing {filename}: {e}")
            return False
    
    def get_processing_status(self) -> Dict:
        """Get status of file processing"""
        try:
            csv_files = list(self.folder_path.glob("*.csv"))
            
            processed_files = []
            unprocessed_files = []
            
            for file_path in csv_files:
                if str(file_path) in self.processed_files:
                    processed_files.append(file_path.name)
                else:
                    unprocessed_files.append(file_path.name)
            
            return {
                'total_files': len(csv_files),
                'processed_files': processed_files,
                'unprocessed_files': unprocessed_files,
                'monitoring_active': self.monitoring,
                'folder_path': str(self.folder_path)
            }
            
        except Exception as e:
            print(f"❌ Error getting processing status: {e}")
            return {}
    
    def cleanup_old_files(self, days: int = 30):
        """Clean up old processed files"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            cleaned_count = 0
            
            for file_path in self.folder_path.glob("*.csv"):
                if file_path.stat().st_mtime < cutoff_date.timestamp():
                    # Move to archive folder
                    archive_folder = self.folder_path / "archive"
                    archive_folder.mkdir(exist_ok=True)
                    
                    archive_path = archive_folder / file_path.name
                    shutil.move(str(file_path), str(archive_path))
                    
                    # Remove from processed files
                    self.processed_files.discard(str(file_path))
                    self.file_hashes.pop(str(file_path), None)
                    
                    cleaned_count += 1
            
            if cleaned_count > 0:
                self._save_processed_files()
                print(f"✅ Cleaned up {cleaned_count} old files")
            
        except Exception as e:
            print(f"❌ Error cleaning up old files: {e}")

# Global instance
file_agent = FileReadingAgent()

# Helper functions for easy access
def start_file_monitoring():
    """Start monitoring the investments folder"""
    file_agent.start_monitoring()

def stop_file_monitoring():
    """Stop monitoring the investments folder"""
    file_agent.stop_monitoring()

def process_all_investment_files(user_id: int = 1) -> Dict:
    """Process all CSV files in the investments folder"""
    return file_agent.process_all_files(user_id)

def reprocess_investment_file(filename: str, user_id: int = 1) -> bool:
    """Reprocess a specific investment file"""
    return file_agent.reprocess_file(filename, user_id)

def get_file_processing_status() -> Dict:
    """Get status of file processing"""
    return file_agent.get_processing_status()

def cleanup_old_investment_files(days: int = 30):
    """Clean up old investment files"""
    file_agent.cleanup_old_files(days)

# Auto-start monitoring when module is imported
if __name__ != "__main__":
    # Start monitoring in background
    start_file_monitoring()
