import os
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import yfinance as yf
import hashlib
import json

# Import the existing database configuration
from database_config_supabase import (
    update_stock_data_supabase,
    get_stock_data_supabase,
    update_transaction_sector_supabase,
    get_transactions_by_ticker_supabase,
    get_transactions_by_tickers_supabase,
    update_transactions_sector_bulk_supabase
)

# Create a new base for stock data tables
StockDataBase = declarative_base()

class StockData(StockDataBase):
    """Table to store live prices and sector information for stocks"""
    __tablename__ = "stock_data"
    
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, unique=True, index=True, nullable=False)
    stock_name = Column(String)
    sector = Column(String)
    live_price = Column(Float)
    last_updated = Column(DateTime, default=datetime.utcnow)
    price_source = Column(String, default='unknown')  # 'yfinance', 'indstocks', etc.
    is_active = Column(Boolean, default=True)
    error_count = Column(Integer, default=0)
    last_error = Column(Text)
    data_hash = Column(String)  # Hash of the data for change detection

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
    
    def _create_stock_data_table(self):
        """Create the stock_data table if it doesn't exist"""
        try:
            StockDataBase.metadata.create_all(bind=self.engine)
            print("✅ Stock data table created/verified successfully!")
        except Exception as e:
            print(f"❌ Error creating stock data table: {e}")
    
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
    
    def _update_all_stock_data(self):
        """Update all stock data using bulk updates"""
        try:
            session = self.SessionLocal()
            
            # Get all unique tickers from transactions table
            result = session.execute(text("""
                SELECT DISTINCT ticker 
                FROM investment_transactions 
                WHERE ticker IS NOT NULL AND ticker != ''
            """))
            tickers = [row[0] for row in result.fetchall()]
            
            session.close()
            
            if not tickers:
                print("ℹ️ No tickers found in transactions table")
                return
            
            print(f"🔄 Bulk updating data for {len(tickers)} tickers...")
            
            # Use bulk update for better performance
            result = self._bulk_update_stock_data(tickers)
            
            print(f"✅ Bulk update completed: {result['updated']} updated, {result['failed']} failed")
            
        except Exception as e:
            print(f"❌ Error in bulk update: {e}")
    
    def update_user_stock_data(self, user_id: int):
        """Update stock data for a specific user's stocks"""
        try:
            session = self.SessionLocal()
            
            # Get distinct tickers for the specific user
            result = session.execute(text("""
                SELECT DISTINCT ticker 
                FROM investment_transactions 
                WHERE user_id = :user_id AND ticker IS NOT NULL AND ticker != ''
            """), {'user_id': user_id})
            
            tickers = [row[0] for row in result.fetchall()]
            session.close()
            
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
                
                # Update database with bulk results
                session = self.SessionLocal()
                for ticker, price in bulk_prices.items():
                    if price is not None:
                        success = self._update_stock_record_batch(session, ticker, {
                            'live_price': price,
                            'sector': 'Mutual Funds',
                            'price_source': 'mftool_bulk',
                            'stock_name': f"MF-{ticker}"
                        })
                        if success:
                            updated_count += 1
                            sector_updates[ticker] = 'Mutual Funds'
                        else:
                            failed_count += 1
                    else:
                        failed_count += 1
                
                session.close()
                
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
                
                # Fetch current prices in bulk
                session = self.SessionLocal()
                for ticker, ticker_obj in zip(stocks, ticker_objects):
                    try:
                        current_price = ticker_obj.info.get('regularMarketPrice')
                        if current_price:
                            # Try to get sector information
                            sector = ticker_obj.info.get('sector', 'Unknown')
                            stock_name = ticker_obj.info.get('longName', ticker)
                            
                            success = self._update_stock_record_batch(session, ticker, {
                                'live_price': float(current_price),
                                'sector': sector,
                                'price_source': 'yfinance_bulk',
                                'stock_name': stock_name
                            })
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
                
                session.close()
                
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

    def _update_stock_record(self, session, ticker: str, data: Dict) -> bool:
        """Update a single stock record in the database"""
        try:
            # Check if stock exists in database
            stock_record = session.query(StockData).filter_by(ticker=ticker).first()
            
            if stock_record:
                # Update existing record
                data_hash = self._get_data_hash(
                    ticker, 
                    data['stock_name'], 
                    data['sector'], 
                    data['live_price']
                )
                
                stock_record.stock_name = data['stock_name']
                stock_record.sector = data['sector']
                stock_record.live_price = data['live_price']
                stock_record.price_source = data['price_source']
                stock_record.last_updated = datetime.utcnow()
                stock_record.data_hash = data_hash
                stock_record.error_count = 0
                stock_record.last_error = None
                stock_record.is_active = True
                
                session.commit()
                
                # Also update sector information in transactions table
                try:
                    from database_config_supabase import SessionLocal as TransactionSessionLocal
                    transaction_session = TransactionSessionLocal()
                    # Update all transactions with this ticker to have the correct sector
                    from database_config_supabase import InvestmentTransaction
                    transactions_to_update = transaction_session.query(InvestmentTransaction).filter(
                        InvestmentTransaction.ticker == ticker,
                        InvestmentTransaction.sector.in_(['Unknown', ''])
                    ).all()
                    
                    for transaction in transactions_to_update:
                        transaction.sector = data['sector']
                    
                    if transactions_to_update:
                        transaction_session.commit()
                        print(f"✅ Updated {len(transactions_to_update)} transactions for {ticker} to {data['sector']} sector")
                    
                    transaction_session.close()
                except Exception as e:
                    print(f"⚠️ Could not update transaction sectors for {ticker}: {e}")
                
                return True
            else:
                # Create new record
                data_hash = self._get_data_hash(
                    ticker, 
                    data['stock_name'], 
                    data['sector'], 
                    data['live_price']
                )
                
                new_stock = StockData(
                    ticker=ticker,
                    stock_name=data['stock_name'],
                    sector=data['sector'],
                    live_price=data['live_price'],
                    price_source=data['price_source'],
                    data_hash=data_hash
                )
                
                session.add(new_stock)
                session.commit()
                
                # Also update sector information in transactions table
                try:
                    from database_config_supabase import SessionLocal as TransactionSessionLocal
                    transaction_session = TransactionSessionLocal()
                    # Update all transactions with this ticker to have the correct sector
                    from database_config_supabase import InvestmentTransaction
                    transactions_to_update = transaction_session.query(InvestmentTransaction).filter(
                        InvestmentTransaction.ticker == ticker,
                        InvestmentTransaction.sector.in_(['Unknown', ''])
                    ).all()
                    
                    for transaction in transactions_to_update:
                        transaction.sector = data['sector']
                    
                    if transactions_to_update:
                        transaction_session.commit()
                        print(f"✅ Updated {len(transactions_to_update)} transactions for {ticker} to {data['sector']} sector")
                    
                    transaction_session.close()
                except Exception as e:
                    print(f"⚠️ Could not update transaction sectors for {ticker}: {e}")
                
                return True
                
        except Exception as e:
            print(f"❌ Error updating stock record for {ticker}: {e}")
            return False
    
    def _update_stock_record_batch(self, session, ticker: str, data: Dict) -> bool:
        """Update a single stock record in the database (batch version - no individual sector updates)"""
        try:
            # Check if stock exists in database
            stock_record = session.query(StockData).filter_by(ticker=ticker).first()
            
            if stock_record:
                # Update existing record
                data_hash = self._get_data_hash(
                    ticker, 
                    data['stock_name'], 
                    data['sector'], 
                    data['live_price']
                )
                
                stock_record.stock_name = data['stock_name']
                stock_record.sector = data['sector']
                stock_record.live_price = data['live_price']
                stock_record.price_source = data['price_source']
                stock_record.last_updated = datetime.utcnow()
                stock_record.data_hash = data_hash
                stock_record.error_count = 0
                stock_record.last_error = None
                stock_record.is_active = True
                
                session.commit()
                return True
            else:
                # Create new record
                data_hash = self._get_data_hash(
                    ticker, 
                    data['stock_name'], 
                    data['sector'], 
                    data['live_price']
                )
                
                new_stock = StockData(
                    ticker=ticker,
                    stock_name=data['stock_name'],
                    sector=data['sector'],
                    live_price=data['live_price'],
                    price_source=data['price_source'],
                    data_hash=data_hash
                )
                
                session.add(new_stock)
                session.commit()
                return True
                
        except Exception as e:
            print(f"❌ Error updating stock record for {ticker}: {e}")
            return False
    
    def get_stock_data(self, ticker: str) -> Optional[Dict]:
        """Get stock data from cache or database"""
        # Check cache first
        with self.cache_lock:
            if ticker in self.cache:
                cached_data, timestamp = self.cache[ticker]
                if time.time() - timestamp < 60:  # 1 minute cache
                    return cached_data
        
        try:
            session = self.SessionLocal()
            stock_record = session.query(StockData).filter_by(ticker=ticker, is_active=True).first()
            session.close()
            
            if stock_record:
                data = {
                    'ticker': stock_record.ticker,
                    'stock_name': stock_record.stock_name,
                    'sector': stock_record.sector,
                    'live_price': stock_record.live_price,
                    'price_source': stock_record.price_source,
                    'last_updated': stock_record.last_updated
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
        """Get all stock data as a dictionary"""
        try:
            session = self.SessionLocal()
            stock_records = session.query(StockData).filter_by(is_active=True).all()
            session.close()
            
            stock_data = {}
            for record in stock_records:
                stock_data[record.ticker] = {
                    'ticker': record.ticker,
                    'stock_name': record.stock_name,
                    'sector': record.sector,
                    'live_price': record.live_price,
                    'price_source': record.price_source,
                    'last_updated': record.last_updated
                }
            
            return stock_data
            
        except Exception as e:
            print(f"❌ Error getting all stock data: {e}")
            return {}
    
    def get_user_stock_data(self, user_id: int) -> Dict[str, Dict]:
        """Get stock data only for stocks that a specific user owns"""
        try:
            session = self.SessionLocal()
            
            # Get user's tickers
            result = session.execute(text("""
                SELECT DISTINCT ticker 
                FROM investment_transactions 
                WHERE user_id = :user_id AND ticker IS NOT NULL AND ticker != ''
            """), {'user_id': user_id})
            
            user_tickers = [row[0] for row in result.fetchall()]
            
            if not user_tickers:
                session.close()
                return {}
            
            # Get stock data for user's tickers only
            stock_records = session.query(StockData).filter(
                StockData.ticker.in_(user_tickers),
                StockData.is_active == True
            ).all()
            
            session.close()
            
            stock_data = {}
            for record in stock_records:
                stock_data[record.ticker] = {
                    'ticker': record.ticker,
                    'stock_name': record.stock_name,
                    'sector': record.sector,
                    'live_price': record.live_price,
                    'price_source': record.price_source,
                    'last_updated': record.last_updated
                }
            
            return stock_data
            
        except Exception as e:
            print(f"❌ Error getting user stock data: {e}")
            return {}
    
    def force_update_ticker(self, ticker: str) -> bool:
        """Force update a specific ticker"""
        return self._update_stock_data(ticker)
    
    def get_database_stats(self) -> Dict:
        """Get statistics about the stock data database"""
        try:
            session = self.SessionLocal()
            
            total_stocks = session.query(StockData).count()
            active_stocks = session.query(StockData).filter_by(is_active=True).count()
            error_stocks = session.query(StockData).filter(StockData.error_count > 0).count()
            
            # Get recent updates
            recent_updates = session.query(StockData).filter(
                StockData.last_updated >= datetime.utcnow() - timedelta(hours=1)
            ).count()
            
            session.close()
            
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
        """Clean up old inactive stock data"""
        try:
            session = self.SessionLocal()
            
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            old_records = session.query(StockData).filter(
                StockData.last_updated < cutoff_date,
                StockData.is_active == False
            ).all()
            
            for record in old_records:
                session.delete(record)
            
            session.commit()
            session.close()
            
            print(f"✅ Cleaned up {len(old_records)} old stock records")
            
        except Exception as e:
            print(f"❌ Error cleaning up old data: {e}")
    
    def update_all_stock_sectors(self):
        """Update sector information for all stocks in the database"""
        try:
            print("🔄 Updating sectors for all stocks...")
            
            # Get all unique tickers from transactions table
            session = self.SessionLocal()
            result = session.execute(text("""
                SELECT DISTINCT ticker 
                FROM investment_transactions 
                WHERE ticker IS NOT NULL AND ticker != '' AND sector IN ('Unknown', '')
            """))
            tickers = [row[0] for row in result.fetchall()]
            session.close()
            
            if not tickers:
                print("ℹ️ No tickers found that need sector updates")
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
        """Batch update sector information in transactions table"""
        try:
            if not sector_updates:
                return
            
            from database_config_supabase import SessionLocal as TransactionSessionLocal
            transaction_session = TransactionSessionLocal()
            
            total_updated = 0
            
            # Group updates by sector for efficiency
            sector_groups = {}
            for ticker, sector in sector_updates.items():
                if sector not in sector_groups:
                    sector_groups[sector] = []
                sector_groups[sector].append(ticker)
            
            # Update transactions by sector groups
            for sector, tickers in sector_groups.items():
                try:
                    from database_config_supabase import InvestmentTransaction
                    
                    # Update all transactions for these tickers that have Unknown or empty sector
                    result = transaction_session.query(InvestmentTransaction).filter(
                        InvestmentTransaction.ticker.in_(tickers),
                        InvestmentTransaction.sector.in_(['Unknown', ''])
                    ).update(
                        {InvestmentTransaction.sector: sector},
                        synchronize_session=False
                    )
                    
                    transaction_session.commit()
                    total_updated += result
                    
                    if result > 0:
                        print(f"✅ Batch updated {result} transactions to {sector} sector for {len(tickers)} tickers")
                        
                except Exception as e:
                    print(f"⚠️ Error in batch sector update for {sector}: {e}")
                    transaction_session.rollback()
                    continue
            
            transaction_session.close()
            print(f"✅ Batch sector update completed: {total_updated} transactions updated")
            
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

def update_all_stock_sectors():
    """Update sector information for all stocks"""
    return stock_agent.update_all_stock_sectors()
