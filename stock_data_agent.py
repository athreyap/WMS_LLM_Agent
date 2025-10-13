import os
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import yfinance as yf
import hashlib
import json

# Import the existing database configuration
from database_config_supabase import (
    update_stock_data_supabase,
    get_stock_data_supabase,
    get_transactions_supabase,
    update_transaction_sector_supabase,
    get_transactions_by_ticker_supabase,
    get_transactions_by_tickers_supabase,
    update_transactions_sector_bulk_supabase
)

# StockDataAgent class for managing stock data using Supabase
class StockDataAgent:
    """Agentic AI system for managing stock data"""
    
    def __init__(self):
        self.cache = {}
        self.cache_lock = threading.Lock()
        # Update interval - can be configured via environment variable
        self.update_interval = int(os.getenv('STOCK_UPDATE_INTERVAL', 3600))  # Default: 1 hour
        self.auto_update = os.getenv('STOCK_AUTO_UPDATE', 'false').lower() == 'true'  # Default: disabled (user-specific updates)
        self.max_retries = 3
        self.batch_size = 25
        
        # Start background update thread
        self._start_background_updates()
    
    def _start_background_updates(self):
        """Start background thread for periodic updates"""
        def update_worker():
            while True:
                try:
                    if self.auto_update:
                        self._update_all_stock_data()
                    time.sleep(self.update_interval)
                except Exception as e:
                    print(f"❌ Background update error: {e}")
                    time.sleep(60)  # Wait 1 minute on error
        
        update_thread = threading.Thread(target=update_worker, daemon=True)
        update_thread.start()
        if self.auto_update:
            print("🔄 Background stock data update thread started")
        else:
            print("⏸️ Background stock data updates disabled")
    
    def _get_data_hash(self, ticker: str, stock_name: str, sector: str, live_price: float) -> str:
        """Generate hash for data change detection"""
        data_string = f"{ticker}:{stock_name}:{sector}:{live_price}"
        return hashlib.md5(data_string.encode()).hexdigest()
    
    def _fetch_stock_data(self, ticker: str) -> Dict:
        """Fetch stock data using smart routing (mutual funds -> mftool, stocks -> yfinance/indstocks)"""
        try:
            # Check if it's a numerical ticker (mutual fund)
            clean_ticker = str(ticker).strip().upper()
            clean_ticker = clean_ticker.replace('.NS', '').replace('.BO', '').replace('.NSE', '').replace('.BSE', '')
            
            if clean_ticker.isdigit():
                # Mutual fund - use mftool directly
                print(f"🔍 Fetching mutual fund data for {ticker} using mftool...")
                try:
                    from mf_price_fetcher import fetch_mutual_fund_price
                    price = fetch_mutual_fund_price(ticker, None)  # None for current price
                    if price is not None:
                        return {
                            'live_price': float(price),
                            'sector': 'Mutual Funds',
                            'price_source': 'mftool',
                            'stock_name': f"MF-{ticker}"
                        }
                except Exception as e:
                    print(f"⚠️ MFTool failed for {ticker}: {e}")
                
                # Fallback to INDstocks for mutual funds
                try:
                    from indstocks_api import get_indstocks_client
                    api_client = get_indstocks_client()
                    if api_client and api_client.available:
                        price_data = api_client.get_stock_price(ticker)
                        if price_data and price_data.get('price'):
                            return {
                                'live_price': float(price_data['price']),
                                'sector': 'Mutual Funds',
                                'price_source': 'indstocks_mf',
                                'stock_name': f"MF-{ticker}"
                            }
                except Exception as e:
                    print(f"⚠️ INDstocks failed for mutual fund {ticker}: {e}")
                
                return None
            else:
                # Stock - try yfinance first, then INDstocks
                print(f"🔍 Fetching stock data for {ticker} using yfinance...")
                
                # Try yfinance first
                try:
                    # Add .NS suffix for Indian stocks if not present
                    if not ticker.endswith(('.NS', '.BO')):
                        ticker_with_suffix = f"{ticker}.NS"
                    else:
                        ticker_with_suffix = ticker
                    
                    stock = yf.Ticker(ticker_with_suffix)
                    info = stock.info
                    
                    live_price = info.get('regularMarketPrice', 0)
                    sector = info.get('sector', 'Unknown')
                    stock_name = info.get('longName', ticker)
                    
                    if live_price and live_price > 0:
                        return {
                            'live_price': float(live_price),
                            'sector': sector,
                            'price_source': 'yfinance',
                            'stock_name': stock_name
                        }
                    
                    # Try without .NS suffix
                    if ticker_with_suffix.endswith('.NS'):
                        stock = yf.Ticker(ticker)
                        info = stock.info
                        
                        live_price = info.get('regularMarketPrice', 0)
                        sector = info.get('sector', 'Unknown')
                        stock_name = info.get('longName', ticker)
                        
                        if live_price and live_price > 0:
                            return {
                                'live_price': float(live_price),
                                'sector': sector,
                                'price_source': 'yfinance',
                                'stock_name': stock_name
                            }
                            
                except Exception as e:
                    print(f"⚠️ YFinance failed for {ticker}: {e}")
                    
                    # Fallback to INDstocks for stocks
                    try:
                        from indstocks_api import get_indstocks_client
                        api_client = get_indstocks_client()
                        if api_client and api_client.available:
                            price_data = api_client.get_stock_price(ticker)
                            if price_data and price_data.get('price'):
                                sector_data = api_client.get_stock_sector(ticker)
                                return {
                                    'live_price': float(price_data['price']),
                                    'sector': sector_data if sector_data else 'Unknown',
                                    'price_source': 'indstocks',
                                    'stock_name': price_data.get('name', ticker)
                                }
                    except Exception as e:
                        print(f"⚠️ INDstocks failed for stock {ticker}: {e}")
                
                return None
            
        except Exception as e:
            print(f"❌ Error fetching data for {ticker}: {e}")
            return None
    
    def _update_stock_data(self, ticker: str) -> bool:
        """Update live price data for a single stock using Supabase"""
        try:
            # Fetch new live data
            new_data = self._fetch_stock_data(ticker)
            
            if new_data:
                # Update stock data using Supabase
                update_stock_data_supabase(
                        ticker=ticker,
                        stock_name=new_data['stock_name'],
                        sector=new_data['sector'],
                    current_price=new_data['live_price']
                )
                
                print(f"✅ Updated live price for {ticker}: ₹{new_data['live_price']:.2f} - {new_data['sector']}")
                
                # Also update sector information in transactions table
                try:
                    # Update all transactions with this ticker to have the correct sector
                    update_transaction_sector_supabase(ticker, new_data['sector'])
                except Exception as e:
                    print(f"⚠️ Could not update transaction sectors for {ticker}: {e}")
                
                    return True
            else:
                print(f"❌ Failed to fetch live data for {ticker}")
                return False
                
        except Exception as e:
            print(f"❌ Error updating live price for {ticker}: {e}")
            return False
    
    def _update_all_stock_data(self, user_id: int = None):
        """Update all stock data using bulk updates"""
        try:
            # Get all unique tickers from transactions table using Supabase
            transactions = get_transactions_supabase(user_id)
            tickers = list(set([t['ticker'] for t in transactions if t.get('ticker')]))
            
            if not tickers:
                print(f"ℹ️ No tickers found in transactions table{' for user ' + str(user_id) if user_id else ''}")
                return
            
            print(f"🔄 Bulk updating data for {len(tickers)} tickers{' for user ' + str(user_id) if user_id else ''}...")
            
            # Use bulk update for better performance
            result = self._bulk_update_stock_data(tickers)
            
            print(f"✅ Bulk update completed: {result['updated']} updated, {result['failed']} failed")
            
        except Exception as e:
            print(f"❌ Error in bulk update: {e}")
    
    def update_user_stock_data(self, user_id: int):
        """Update stock data for a specific user's stocks"""
        try:
            # Get distinct tickers for the specific user using Supabase
            transactions = get_transactions_supabase(user_id)
            tickers = list(set([t['ticker'] for t in transactions if t.get('ticker')]))
            
            if not tickers:
                print(f"ℹ️ No tickers found for user {user_id}")
                return {'updated': 0, 'failed': 0, 'total': 0}
            
            print(f"🔄 Updating stock data for user {user_id}: {len(tickers)} tickers...")
            
            # Use bulk update for better performance
            return self._bulk_update_stock_data(tickers)
            
        except Exception as e:
            print(f"❌ Error updating user stock data: {e}")
            return {'updated': 0, 'failed': 0, 'total': 0, 'error': str(e)}

    def _bulk_update_stock_data(self, tickers: List[str]):
        """Bulk update stock data for multiple tickers"""
        try:
            print(f"🔄 Bulk updating {len(tickers)} tickers...")
            
            # Separate mutual funds and stocks for efficient processing
            mutual_funds = []
            stocks = []
            
            for ticker in tickers:
                if ticker and ticker.strip():
                    # Check if it's a numerical ticker (mutual fund)
                    clean_ticker = str(ticker).strip().upper()
                    clean_ticker = clean_ticker.replace('.NS', '').replace('.BO', '').replace('.NSE', '').replace('.BSE', '')
                    
                    if clean_ticker.isdigit():
                        mutual_funds.append(ticker.strip())
                    else:
                        stocks.append(ticker.strip())
            
            updated_count = 0
            failed_count = 0
            sector_updates = {}  # Collect sector updates for batch processing
            
            # Bulk update mutual funds
            if mutual_funds:
                print(f"🔍 Bulk updating {len(mutual_funds)} mutual funds...")
                mf_results = self._bulk_update_mutual_funds(mutual_funds)
                updated_count += mf_results['updated']
                failed_count += mf_results['failed']
                # Collect sector updates from mutual funds
                if 'sector_updates' in mf_results:
                    sector_updates.update(mf_results['sector_updates'])
            
            # Bulk update stocks
            if stocks:
                print(f"🔍 Bulk updating {len(stocks)} stocks...")
                stock_results = self._bulk_update_stocks(stocks)
                updated_count += stock_results['updated']
                failed_count += stock_results['failed']
                # Collect sector updates from stocks
                if 'sector_updates' in stock_results:
                    sector_updates.update(stock_results['sector_updates'])
            
            # Perform batch sector updates
            if sector_updates:
                print(f"🔄 Performing batch sector updates for {len(sector_updates)} tickers...")
                self._batch_update_transaction_sectors(sector_updates)
            
            result = {
                'updated': updated_count,
                'failed': failed_count,
                'total': len(tickers)
            }
            
            print(f"✅ Bulk update completed: {updated_count} updated, {failed_count} failed")
            return result
            
        except Exception as e:
            print(f"❌ Error in bulk update: {e}")
            return {'updated': 0, 'failed': 0, 'total': len(tickers), 'error': str(e)}

    def _bulk_update_mutual_funds(self, mutual_funds: List[str]):
        """Bulk update mutual fund data"""
        try:
            updated_count = 0
            failed_count = 0
            sector_updates = {}
            
            # Try bulk fetching from mftool
            try:
                from mf_price_fetcher import fetch_mutual_funds_bulk
                # Create dummy dates for current prices
                mf_data = [(ticker, None) for ticker in mutual_funds]
                bulk_prices = fetch_mutual_funds_bulk(mf_data)
                
                # Update database with bulk results using Supabase
                for ticker, price in bulk_prices.items():
                    if price is not None:
                        success = update_stock_data_supabase(
                            ticker=ticker,
                            stock_name=f"MF-{ticker}",
                            sector='Mutual Funds',
                            current_price=price
                        )
                        if success:
                            updated_count += 1
                            sector_updates[ticker] = 'Mutual Funds'
                        else:
                            failed_count += 1
                    else:
                        failed_count += 1
                
            except Exception as e:
                print(f"⚠️ Bulk mutual fund update failed: {e}")
                # Fallback to individual updates
                for ticker in mutual_funds:
                    success = self._update_stock_data(ticker)
                    if success:
                        updated_count += 1
                        sector_updates[ticker] = 'Mutual Funds'
                    else:
                        failed_count += 1
                    time.sleep(0.1)
            
            return {'updated': updated_count, 'failed': failed_count, 'sector_updates': sector_updates}
            
        except Exception as e:
            print(f"❌ Error in bulk mutual fund update: {e}")
            return {'updated': 0, 'failed': len(mutual_funds), 'sector_updates': {}}

    def _bulk_update_stocks(self, stocks: List[str]):
        """Bulk update stock data"""
        try:
            updated_count = 0
            failed_count = 0
            sector_updates = {}
            
            # Try bulk fetching from yfinance
            try:
                import yfinance as yf
                
                # Create ticker objects for bulk fetching
                ticker_objects = [yf.Ticker(ticker) for ticker in stocks]
                
                # Fetch current prices in bulk using Supabase
                for ticker, ticker_obj in zip(stocks, ticker_objects):
                    try:
                        current_price = ticker_obj.info.get('regularMarketPrice')
                        if current_price:
                            # Try to get sector information
                            sector = ticker_obj.info.get('sector', 'Unknown')
                            stock_name = ticker_obj.info.get('longName', ticker)
                            
                            success = update_stock_data_supabase(
                                ticker=ticker,
                                stock_name=stock_name,
                                sector=sector,
                                current_price=float(current_price)
                            )
                            if success:
                                updated_count += 1
                                if sector != 'Unknown':
                                    sector_updates[ticker] = sector
                            else:
                                failed_count += 1
                        else:
                            failed_count += 1
                            
                    except Exception as e:
                        print(f"⚠️ Error updating {ticker}: {e}")
                        failed_count += 1
                
            except Exception as e:
                print(f"⚠️ Bulk stock update failed: {e}")
                # Fallback to individual updates
                for ticker in stocks:
                    success = self._update_stock_data(ticker)
                    if success:
                        updated_count += 1
                        # Get sector from stock data
                        stock_data = self.get_stock_data(ticker)
                        if stock_data and stock_data.get('sector') != 'Unknown':
                            sector_updates[ticker] = stock_data['sector']
                    else:
                        failed_count += 1
                    time.sleep(0.1)
            
            return {'updated': updated_count, 'failed': failed_count, 'sector_updates': sector_updates}
            
        except Exception as e:
            print(f"❌ Error in bulk stock update: {e}")
            return {'updated': 0, 'failed': len(stocks), 'sector_updates': {}}
    
    def get_stock_data(self, ticker: str) -> Optional[Dict]:
        """Get stock data from cache or database using Supabase"""
        # Check cache first
        with self.cache_lock:
            if ticker in self.cache:
                cached_data, timestamp = self.cache[ticker]
                if time.time() - timestamp < 60:  # 1 minute cache
                    return cached_data
        
        try:
            stock_data = get_stock_data_supabase(ticker)
            
            if stock_data:
                data = {
                    'ticker': stock_data[0]['ticker'],
                    'stock_name': stock_data[0].get('stock_name'),
                    'sector': stock_data[0].get('sector'),
                    'live_price': stock_data[0].get('current_price'),
                    'price_source': 'supabase',
                    'last_updated': stock_data[0].get('last_updated')
                }
                
                # Cache the result
                with self.cache_lock:
                    self.cache[ticker] = (data, time.time())
                
                return data
            else:
                return None
                
        except Exception as e:
            print(f"❌ Error getting stock data for {ticker}: {e}")
            return None
    
    def get_all_stock_data(self) -> Dict[str, Dict]:
        """Get all stock data as a dictionary using Supabase"""
        try:
            stock_data_list = get_stock_data_supabase()
            
            stock_data = {}
            for record in stock_data_list:
                stock_data[record['ticker']] = {
                    'ticker': record['ticker'],
                    'stock_name': record.get('stock_name'),
                    'sector': record.get('sector'),
                    'live_price': record.get('current_price'),
                    'price_source': 'supabase',
                    'last_updated': record.get('last_updated')
                }
            
            return stock_data
            
        except Exception as e:
            print(f"❌ Error getting all stock data: {e}")
            return {}
    
    def get_user_stock_data(self, user_id: int) -> Dict[str, Dict]:
        """Get stock data only for stocks that a specific user owns using Supabase"""
        try:
            # Get user's tickers using Supabase
            transactions = get_transactions_supabase(user_id)
            user_tickers = list(set([t['ticker'] for t in transactions if t.get('ticker')]))
            
            if not user_tickers:
                return {}
            
            # Get stock data for user's tickers only
            stock_data = {}
            for ticker in user_tickers:
                ticker_data = get_stock_data_supabase(ticker)
                if ticker_data:
                    record = ticker_data[0]
                    stock_data[record['ticker']] = {
                        'ticker': record['ticker'],
                        'stock_name': record.get('stock_name'),
                        'sector': record.get('sector'),
                        'live_price': record.get('live_price'),  # Use live_price instead of current_price
                        'price_source': 'supabase',
                        'last_updated': record.get('last_updated')
                }
            
            return stock_data
            
        except Exception as e:
            print(f"❌ Error getting user stock data: {e}")
            return {}
    
    def force_update_ticker(self, ticker: str) -> bool:
        """Force update a specific ticker"""
        return self._update_stock_data(ticker)
    
    def get_database_stats(self) -> Dict:
        """Get statistics about the stock data database using Supabase"""
        try:
            stock_data_list = get_stock_data_supabase()
            
            total_stocks = len(stock_data_list)
            active_stocks = total_stocks  # All stocks in Supabase are considered active
            error_stocks = 0  # Not tracked in Supabase
            recent_updates = 0  # Not tracked in Supabase
            
            return {
                'total_stocks': total_stocks,
                'active_stocks': active_stocks,
                'error_stocks': error_stocks,
                'recent_updates': recent_updates,
                'cache_size': len(self.cache)
            }
            
        except Exception as e:
            print(f"❌ Error getting database stats: {e}")
            return {}
    
    def cleanup_old_data(self, days: int = 30):
        """Clean up old inactive stock data (not implemented for Supabase)"""
        try:
            print("⚠️ Cleanup not implemented for Supabase - data is managed automatically")
        except Exception as e:
            print(f"❌ Error cleaning up old data: {e}")
    
    def update_all_stock_sectors(self, user_id: int = None):
        """Update sector information for all stocks in the database using Supabase"""
        try:
            print(f"🔄 Updating sectors for all stocks{' for user ' + str(user_id) if user_id else ''}...")
            
            # Get all unique tickers from transactions table using Supabase
            transactions = get_transactions_supabase(user_id)
            tickers = list(set([t['ticker'] for t in transactions if t.get('ticker') and t.get('sector') in ['Unknown', '']]))
            
            if not tickers:
                print(f"ℹ️ No tickers found that need sector updates{' for user ' + str(user_id) if user_id else ''}")
                return
            
            print(f"🔄 Updating sectors for {len(tickers)} tickers...")
            
            updated_count = 0
            for ticker in tickers:
                try:
                    # Fetch fresh data for this ticker
                    new_data = self._fetch_stock_data(ticker)
                    if new_data and new_data.get('sector') and new_data['sector'] != 'Unknown':
                        # Update the stock data table
                        success = self._update_stock_data(ticker)
                        if success:
                            updated_count += 1
                            print(f"✅ Updated sector for {ticker}: {new_data['sector']}")
                except Exception as e:
                    print(f"⚠️ Error updating sector for {ticker}: {e}")
                    continue
            
            print(f"✅ Sector update completed: {updated_count}/{len(tickers)} tickers updated")
            
        except Exception as e:
            print(f"❌ Error updating stock sectors: {e}")
    
    def _batch_update_transaction_sectors(self, sector_updates: Dict[str, str]):
        """Batch update sector information in transactions table using Supabase"""
        try:
            if not sector_updates:
                return
            
            # Use Supabase bulk update
            success = update_transactions_sector_bulk_supabase(sector_updates)
            
            if success:
                print(f"✅ Batch sector update completed for {len(sector_updates)} tickers")
            else:
                print(f"⚠️ Some sector updates failed")
            
        except Exception as e:
            print(f"❌ Error in batch sector update: {e}")

# Global instance
stock_agent = StockDataAgent()

# Helper functions for easy access
def get_live_price(ticker: str) -> Optional[float]:
    """Get live price for a ticker"""
    data = stock_agent.get_stock_data(ticker)
    return data['live_price'] if data else None

def get_sector(ticker: str) -> Optional[str]:
    """Get sector for a ticker"""
    data = stock_agent.get_stock_data(ticker)
    return data['sector'] if data else None

def get_stock_name(ticker: str) -> Optional[str]:
    """Get stock name for a ticker"""
    data = stock_agent.get_stock_data(ticker)
    return data['stock_name'] if data else None

def get_all_live_prices() -> Dict[str, float]:
    """Get all live prices as a dictionary"""
    all_data = stock_agent.get_all_stock_data()
    return {ticker: data['live_price'] for ticker, data in all_data.items()}

def get_user_live_prices(user_id: int) -> Dict[str, float]:
    """Get live prices only for stocks that a specific user owns"""
    user_data = stock_agent.get_user_stock_data(user_id)
    return {ticker: data['live_price'] for ticker, data in user_data.items()}

def force_update_stock(ticker: str) -> bool:
    """Force update a specific stock"""
    return stock_agent.force_update_ticker(ticker)

def get_stock_data_stats() -> Dict:
    """Get stock data statistics"""
    return stock_agent.get_database_stats()

def update_user_stock_prices(user_id: int) -> Dict:
    """Update live prices for a specific user's stocks"""
    return stock_agent.update_user_stock_data(user_id)

def update_all_stock_sectors(user_id: int = None):
    """Update sector information for all stocks"""
    return stock_agent.update_all_stock_sectors(user_id)
