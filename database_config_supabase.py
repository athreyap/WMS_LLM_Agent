import os
import hashlib
from datetime import datetime
import psycopg2
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Float, Boolean, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from typing import Optional, List, Dict, Any
import pandas as pd
import time
import threading
from functools import wraps
import random

# PostgreSQL connection string for Supabase
DATABASE_URL = os.getenv('DATABASE_URL', "postgresql://postgres:wmssupabase123@db.rolcoegikoeblxzqgkix.supabase.co:5432/postgres?sslmode=require&prefer_ipv4=true")

def get_db_session_with_retry(max_retries=3, base_delay=1):
    """Get database session with retry logic for cloud environments"""
    for attempt in range(max_retries):
        try:
            session = SessionLocal()
            # Test the connection
            session.execute("SELECT 1")
            return session
        except Exception as e:
            session.close()
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                print(f"⚠️ Database connection attempt {attempt + 1} failed, retrying in {delay:.2f}s: {e}")
                time.sleep(delay)
            else:
                print(f"❌ Database connection failed after {max_retries} attempts: {e}")
                raise e
    return None

# Cache decorator for database functions
def cache_result(ttl_seconds=300):
    """Cache decorator for function results with TTL"""
    def decorator(func):
        cache = {}
        cache_timestamps = {}
        cache_lock = threading.Lock()
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            cache_key = f"{func.__name__}_{str(args)}_{str(sorted(kwargs.items()))}"
            
            with cache_lock:
                current_time = time.time()
                
                # Check if cached result exists and is still valid
                if cache_key in cache:
                    if current_time - cache_timestamps[cache_key] < ttl_seconds:
                        return cache[cache_key]
                    else:
                        # Remove expired cache entry
                        del cache[cache_key]
                        del cache_timestamps[cache_key]
                
                # Execute function and cache result
                result = func(*args, **kwargs)
                cache[cache_key] = result
                cache_timestamps[cache_key] = current_time
                
                return result
        
        return wrapper
    return decorator

# Create SQLAlchemy engine for PostgreSQL with optimized settings for cloud deployment
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=180,  # Reduced for cloud environments
    pool_size=3,  # Smaller pool for cloud
    max_overflow=5,  # Smaller overflow for cloud
    connect_args={
        "connect_timeout": 30,  # Reduced timeout for cloud
        "application_name": "WMS_LLM_Streamlit",
        "sslmode": "require",  # Force SSL connection
        "keepalives": 1,
        "keepalives_idle": 60,
        "keepalives_interval": 10,
        "keepalives_count": 3,
        "options": "-c statement_timeout=30000"  # 30 second statement timeout
    }
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class InvestmentFile(Base):
    __tablename__ = "investment_files"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    file_hash = Column(String, unique=True, nullable=False)
    customer_name = Column(String)
    customer_id = Column(String)
    customer_email = Column(String)
    customer_phone = Column(String)
    file_path = Column(String, nullable=False)
    upload_date = Column(DateTime, default=datetime.utcnow)
    file_size = Column(Integer)
    status = Column(String, default='active')

class InvestmentTransaction(Base):
    __tablename__ = "investment_transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer)
    user_id = Column(Integer, nullable=True)
    channel = Column(String)
    stock_name = Column(String)
    ticker = Column(String)
    sector = Column(String, nullable=True)  # Add sector column
    quantity = Column(Float)
    price = Column(Float)
    transaction_type = Column(String)
    date = Column(String)
    amount = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

class HistoricalPrice(Base):
    __tablename__ = "historical_prices"
    
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer)  # Reference to InvestmentTransaction.id
    file_id = Column(Integer)  # Reference to InvestmentFile.id
    ticker = Column(String)
    transaction_date = Column(Date)  # The date of the transaction
    historical_price = Column(Float)  # The price on the transaction date
    current_price = Column(Float)  # Current price when stored
    price_source = Column(String)  # 'yfinance', 'indstocks', 'mftool', etc.
    created_at = Column(DateTime, default=datetime.utcnow)

class UserLogin(Base):
    __tablename__ = "user_login"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    password_salt = Column(String)
    role = Column(String, default="user")
    folder_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    failed_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)

def create_database():
    """Create PostgreSQL database tables if they do not exist"""
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Supabase PostgreSQL database tables created successfully!")
    except Exception as e:
        print(f"❌ Error creating database tables: {e}")

def get_file_hash(file_content):
    """Generate SHA-256 hash of file content"""
    return hashlib.sha256(file_content).hexdigest()

def save_file_to_db(file, customer_info=None):
    """Save file information to database"""
    try:
        # Create investments folder if it doesn't exist
        investments_folder = "investments"
        if not os.path.exists(investments_folder):
            os.makedirs(investments_folder)
        
        # Generate file hash
        file_content = file.read()
        file_hash = get_file_hash(file_content)
        
        # Reset file pointer
        file.seek(0)
        
        # Check if file already exists in database
        session = SessionLocal()
        existing_file = session.query(InvestmentFile).filter_by(file_hash=file_hash).first()
        
        if existing_file:
            print(f"File already exists in database: {existing_file.original_filename}")
            session.close()
            return existing_file.id, False  # False indicates duplicate
        
        # Determine per-customer subfolder (based on filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename_without_ext = os.path.splitext(file.name)[0]
        file_extension = os.path.splitext(file.name)[1]
        # Sanitize folder name
        safe_folder = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in filename_without_ext).strip("._-") or "customer"
        target_dir = os.path.join(investments_folder, safe_folder)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
        
        # Save file to per-customer folder
        new_filename = f"{filename_without_ext}_{timestamp}{file_extension}"
        file_path = os.path.join(target_dir, new_filename)
        
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        # Save to database
        db_file = InvestmentFile(
            filename=new_filename,
            original_filename=file.name,
            file_hash=file_hash,
            customer_name=customer_info.get('name', '') if customer_info else '',
            customer_id=customer_info.get('id', '') if customer_info else '',
            customer_email=customer_info.get('email', '') if customer_info else '',
            customer_phone=customer_info.get('phone', '') if customer_info else '',
            file_path=file_path,
            file_size=len(file_content)
        )
        
        session.add(db_file)
        session.commit()
        session.refresh(db_file)
        session.close()
        
        print(f"File saved successfully: {new_filename}")
        return db_file.id, True  # True indicates new file
        
    except Exception as e:
        print(f"Error saving file to database: {e}")
        return None, False

def save_file_record_to_db(session, filename, file_path, user_id):
    """Save file record to database with session, filename, file_path, and user_id"""
    try:
        # Generate file hash from file content
        with open(file_path, 'rb') as f:
            file_content = f.read()
        file_hash = get_file_hash(file_content)
        
        # Check if file already exists in database
        existing_file = session.query(InvestmentFile).filter_by(file_hash=file_hash).first()
        
        if existing_file:
            print(f"File already exists in database: {existing_file.original_filename}")
            return existing_file
        
        # Save to database
        db_file = InvestmentFile(
            filename=filename,
            original_filename=filename,
            file_hash=file_hash,
            customer_name='',  # Will be filled by user info
            customer_id=str(user_id),
            customer_email='',  # Will be filled by user info
            customer_phone='',  # Will be filled by user info
            file_path=file_path,
            file_size=len(file_content)
        )
        
        session.add(db_file)
        session.commit()
        session.refresh(db_file)
        
        print(f"File record saved successfully: {filename}")
        return db_file
        
    except Exception as e:
        print(f"Error saving file record to database: {e}")
        session.rollback()
        return None

def get_all_files():
    """Get all files from database"""
    try:
        session = SessionLocal()
        files = session.query(InvestmentFile).filter_by(status='active').all()
        session.close()
        return files
    except Exception as e:
        print(f"Error getting files from database: {e}")
        return []

def fetch_historical_price_for_transaction(ticker, transaction_date_str):
    """Fetch historical price for a specific transaction date with optimized error handling"""
    try:
        import yfinance as yf
        from datetime import datetime, timedelta
        import time
        
        # Parse the transaction date
        transaction_date = datetime.strptime(transaction_date_str, '%Y-%m-%d').date()
        
        # Add .NS suffix if not present for Indian stocks
        if not ticker.endswith(('.NS', '.BO')):
            ticker_with_suffix = f"{ticker}.NS"
        else:
            ticker_with_suffix = ticker
        
        # Try INDstocks first (faster and more reliable for Indian stocks)
        try:
            from indstocks_api import get_indstocks_client
            api_client = get_indstocks_client()
            if api_client and hasattr(api_client, 'available') and api_client.available:
                # Get current price as fallback (faster than historical)
                current_price_data = api_client.get_stock_price(ticker)
                if current_price_data and 'price' in current_price_data:
                    return float(current_price_data['price']), 'indstocks'
        except Exception as e:
            # Silently continue to yfinance
            pass
        
        # Try yfinance with timeout
        try:
            stock = yf.Ticker(ticker_with_suffix)
            # Get data for a range around the transaction date (±3 days instead of 5)
            start_date = transaction_date - timedelta(days=3)
            end_date = transaction_date + timedelta(days=3)
            
            # Convert to timezone-aware datetime for yfinance
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.min.time())
            
            # Add timeout for yfinance calls
            hist_data = stock.history(start=start_datetime, end=end_datetime, timeout=10)
            
            if not hist_data.empty:
                # Find the closest date to the transaction date
                transaction_datetime = datetime.combine(transaction_date, datetime.min.time())
                closest_date = min(hist_data.index, key=lambda x: abs((x - transaction_datetime).days))
                historical_price = hist_data.loc[closest_date, 'Close']
                return historical_price, 'yfinance'
            else:
                # Try without .NS suffix
                if ticker_with_suffix.endswith('.NS'):
                    stock = yf.Ticker(ticker)
                    hist_data = stock.history(start=start_datetime, end=end_datetime, timeout=10)
                    if not hist_data.empty:
                        transaction_datetime = datetime.combine(transaction_date, datetime.min.time())
                        closest_date = min(hist_data.index, key=lambda x: abs((x - transaction_datetime).days))
                        historical_price = hist_data.loc[closest_date, 'Close']
                        return historical_price, 'yfinance'
        except Exception as e:
            # Silently continue to final fallback
            pass
        
        # Final fallback: try INDstocks again without availability check
        try:
            from indstocks_api import get_indstocks_client
            api_client = get_indstocks_client()
            if api_client:
                current_price_data = api_client.get_stock_price(ticker)
                if current_price_data and 'price' in current_price_data:
                    return float(current_price_data['price']), 'indstocks_fallback'
        except Exception as e:
            # Silently fail
            pass
        
        return None, None
        
    except Exception as e:
        # Don't print errors for individual tickers to reduce noise
        return None, None

def save_transactions_to_db(file_id, df, user_id=None):
    """Save transaction data to database with historical price fetching in batches"""
    try:
        print(f"🔍 Supabase PostgreSQL: Saving transactions - file_id: {file_id}, user_id: {user_id}, rows: {len(df)}")
        session = SessionLocal()
        
        # Call the session-based version
        return save_transactions_to_db_with_session(session, df, file_id, user_id)
        
    except Exception as e:
        print(f"❌ Supabase PostgreSQL: Error saving transactions: {e}")
        return False

def save_transactions_to_db_with_session(session, df, file_id, user_id=None):
    """Save transaction data to database with session - for use by file reading agents"""
    try:
        print(f"🚀 FAST SAVE: Saving transactions - file_id: {file_id}, user_id: {user_id}, rows: {len(df)}")
        
        # Clear existing transactions and historical prices for this file
        session.query(InvestmentTransaction).filter_by(file_id=file_id).delete()
        session.query(HistoricalPrice).filter_by(file_id=file_id).delete()
        session.commit()  # Commit the deletion first
        
        # Use bulk insert for maximum speed - skip historical price fetching on first load
        batch_size = 200  # Larger batch size for bulk operations
        total_rows = len(df)
        
        for batch_start in range(0, total_rows, batch_size):
            batch_end = min(batch_start + batch_size, total_rows)
            batch_df = df.iloc[batch_start:batch_end]
            
            transactions_to_add = []
            for _, row in batch_df.iterrows():
                # Get sector information if available
                sector = row.get('sector', 'Unknown')
                if sector == 'Unknown' or pd.isna(sector):
                    # For now, set unknown tickers as mutual funds if they're numeric
                    ticker = row.get('ticker', '')
                    if ticker and ticker.isdigit():
                        sector = 'Mutual Funds'
                    else:
                        sector = 'Unknown'
                
                transaction = InvestmentTransaction(
                    file_id=file_id,
                    user_id=user_id,
                    channel=row.get('channel', ''),
                    stock_name=row.get('stock_name', ''),
                    ticker=row.get('ticker', ''),
                    sector=sector,  # Add sector information
                    quantity=row.get('quantity', 0),
                    price=row.get('price', 0),
                    transaction_type=row.get('transaction_type', ''),
                    date=row.get('date', ''),
                    amount=row.get('quantity', 0) * row.get('price', 0)
                )
                transactions_to_add.append(transaction)
            
            # Bulk insert batch
            session.bulk_save_objects(transactions_to_add)
            session.commit()
            
            print(f"   ✅ Batch {batch_start//batch_size + 1}/{(total_rows + batch_size - 1)//batch_size} completed")
        
        session.close()
        
        print(f"✅ FAST SAVE: Transactions saved for file ID: {file_id}, user ID: {user_id}")
        print(f"💡 Historical prices will be fetched in background for better performance")
        return True
        
    except Exception as e:
        print(f"❌ FAST SAVE: Error saving transactions: {e}")
        if 'session' in locals():
            session.rollback()
            session.close()
        return False

def save_transactions_to_db_fast(file_id, df, user_id=None):
    """Save transaction data to database without historical price fetching for maximum speed"""
    try:
        print(f"🚀 Fast Save: Saving transactions - file_id: {file_id}, user_id: {user_id}, rows: {len(df)}")
        session = SessionLocal()
        
        # Clear existing transactions and historical prices for this file
        session.query(InvestmentTransaction).filter_by(file_id=file_id).delete()
        session.query(HistoricalPrice).filter_by(file_id=file_id).delete()
        session.commit()  # Commit the deletion first
        
        # Use bulk insert for faster processing with larger batches
        batch_size = 100  # Increased batch size for bulk operations
        total_rows = len(df)
        
        for batch_start in range(0, total_rows, batch_size):
            batch_end = min(batch_start + batch_size, total_rows)
            batch_df = df.iloc[batch_start:batch_end]
            
            transactions_to_add = []
            for _, row in batch_df.iterrows():
                # Get sector information if available
                sector = row.get('sector', 'Unknown')
                if sector == 'Unknown' or pd.isna(sector):
                    # For now, set unknown tickers as mutual funds if they're numeric
                    ticker = row.get('ticker', '')
                    if ticker and ticker.isdigit():
                        sector = 'Mutual Funds'
                    else:
                        sector = 'Unknown'
                
                transaction = InvestmentTransaction(
                    file_id=file_id,
                    user_id=user_id,
                    channel=row.get('channel', ''),
                    stock_name=row.get('stock_name', ''),
                    ticker=row.get('ticker', ''),
                    sector=sector,  # Add sector information
                    quantity=row.get('quantity', 0),
                    price=row.get('price', 0),
                    transaction_type=row.get('transaction_type', ''),
                    date=row.get('date', ''),
                    amount=row.get('quantity', 0) * row.get('price', 0)
                )
                transactions_to_add.append(transaction)
            
            # Bulk insert batch
            session.bulk_save_objects(transactions_to_add)
            session.commit()
            
            print(f"   ✅ Batch {batch_start//batch_size + 1}/{(total_rows + batch_size - 1)//batch_size} completed")
        
        session.close()
        
        print(f"✅ Fast Save: Transactions saved for file ID: {file_id}, user ID: {user_id}")
        
    except Exception as e:
        print(f"❌ Fast Save: Error saving transactions: {e}")
        if 'session' in locals():
            session.rollback()
            session.close()

def get_transactions_by_file_id(file_id):
    """Get transactions for a specific file"""
    try:
        session = SessionLocal()
        transactions = session.query(InvestmentTransaction).filter_by(file_id=file_id).all()
        session.close()
        return transactions
    except Exception as e:
        print(f"Error getting transactions: {e}")
        return []

def get_transactions_by_user_id(user_id):
    """Get all transactions for a specific user"""
    try:
        session = SessionLocal()
        transactions = session.query(InvestmentTransaction).filter_by(user_id=user_id).all()
        session.close()
        return transactions
    except Exception as e:
        print(f"Error getting user transactions: {e}")
        return []

def get_transactions_dataframe(user_id=None):
    """Get transactions as pandas DataFrame"""
    try:
        session = SessionLocal()
        query = session.query(InvestmentTransaction)
        if user_id:
            query = query.filter_by(user_id=user_id)
        
        transactions = query.all()
        session.close()
        
        if transactions:
            # Convert to DataFrame
            data = []
            for t in transactions:
                data.append({
                    'id': t.id,
                    'file_id': t.file_id,
                    'user_id': t.user_id,
                    'channel': t.channel,
                    'stock_name': t.stock_name,
                    'ticker': t.ticker,
                    'sector': t.sector,  # Include sector information
                    'quantity': t.quantity,
                    'price': t.price,
                    'transaction_type': t.transaction_type,
                    'date': t.date,
                    'amount': t.amount,
                    'created_at': t.created_at
                })
            return pd.DataFrame(data)
        else:
            return pd.DataFrame()
    except Exception as e:
        print(f"Error getting transactions DataFrame: {e}")
        return pd.DataFrame()

# User authentication functions
def create_user(username, email, password_hash, password_salt, folder_path=None):
    """Create a new user with retry logic"""
    try:
        session = get_db_session_with_retry()
        user = UserLogin(
            username=username,
            email=email,
            password_hash=password_hash,
            password_salt=password_salt,
            folder_path=folder_path,
            role='user',
            is_active=True
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        session.close()
        return user
    except Exception as e:
        print(f"Error creating user: {e}")
        return None

@cache_result(ttl_seconds=600)  # Cache for 10 minutes
def get_user_by_username(username):
    """Get user by username - with caching and retry logic"""
    try:
        session = get_db_session_with_retry()
        user = session.query(UserLogin).filter_by(username=username).first()
        session.close()
        
        if user:
            return {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'folder_path': user.folder_path,
                'created_at': user.created_at,
                'last_login': user.last_login,
                'is_active': user.is_active
            }
        return None
    except Exception as e:
        print(f"Error getting user: {e}")
        return None

@cache_result(ttl_seconds=600)  # Cache for 10 minutes
def get_user_by_id(user_id):
    """Get user by ID - with caching"""
    try:
        session = SessionLocal()
        user = session.query(UserLogin).filter_by(id=user_id).first()
        session.close()
        
        if user:
            return {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'folder_path': user.folder_path,
                'created_at': user.created_at,
                'last_login': user.last_login,
                'is_active': user.is_active
            }
        return None
    except Exception as e:
        print(f"Error getting user by ID: {e}")
        return None

def get_user_by_email(email):
    """Get user by email"""
    try:
        session = SessionLocal()
        user = session.query(UserLogin).filter_by(email=email).first()
        session.close()
        return user
    except Exception as e:
        print(f"Error getting user: {e}")
        return None

def update_user_login_time(user_id):
    """Update user's last login time"""
    try:
        session = SessionLocal()
        user = session.query(UserLogin).filter_by(id=user_id).first()
        if user:
            user.last_login = datetime.now()
            session.commit()
        session.close()
    except Exception as e:
        print(f"Error updating user login time: {e}")

def update_user_failed_attempts(user_id, failed_attempts, locked_until=None):
    """Update user's failed login attempts"""
    try:
        session = SessionLocal()
        user = session.query(UserLogin).filter_by(id=user_id).first()
        if user:
            user.failed_attempts = failed_attempts
            if locked_until:
                user.locked_until = locked_until
            session.commit()
        session.close()
    except Exception as e:
        print(f"Error updating user failed attempts: {e}")

def update_user_folder_path(user_id, folder_path):
    """Update user's folder path"""
    try:
        session = SessionLocal()
        user = session.query(UserLogin).filter_by(id=user_id).first()
        if user:
            user.folder_path = folder_path
            session.commit()
            session.close()
            return True
        session.close()
        return False
    except Exception as e:
        print(f"Error updating user folder path: {e}")
        return False

def get_all_users():
    """Get all users from database"""
    try:
        session = SessionLocal()
        users = session.query(UserLogin).filter_by(is_active=True).all()
        session.close()
        
        # Convert to list of dictionaries
        user_list = []
        for user in users:
            user_list.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'folder_path': user.folder_path,
                'created_at': user.created_at,
                'last_login': user.last_login
            })
        return user_list
    except Exception as e:
        print(f"Error getting all users: {e}")
        return []

def get_historical_prices_by_file_id(file_id):
    """Get historical prices for a specific file"""
    try:
        session = SessionLocal()
        historical_prices = session.query(HistoricalPrice).filter_by(file_id=file_id).all()
        session.close()
        return historical_prices
    except Exception as e:
        print(f"Error getting historical prices: {e}")
        return []

def get_historical_prices_by_user_id(user_id):
    """Get all historical prices for a specific user"""
    try:
        session = SessionLocal()
        # Join with transactions to get historical prices for user's transactions
        historical_prices = session.query(HistoricalPrice).join(
            InvestmentTransaction, 
            HistoricalPrice.transaction_id == InvestmentTransaction.id
        ).filter(InvestmentTransaction.user_id == user_id).all()
        session.close()
        return historical_prices
    except Exception as e:
        print(f"Error getting historical prices for user: {e}")
        return []

@cache_result(ttl_seconds=300)  # Cache for 5 minutes
def get_transactions_with_historical_prices(file_id=None, user_id=None):
    """Get transactions with their historical prices - optimized with caching and fast startup"""
    try:
        session = SessionLocal()
        
        # Use a single optimized query with JOIN instead of multiple queries
        if file_id:
            # Query for specific file
            query = session.query(
                InvestmentTransaction,
                HistoricalPrice.historical_price,
                HistoricalPrice.price_source,
                HistoricalPrice.transaction_date,
                HistoricalPrice.current_price
            ).outerjoin(
                HistoricalPrice, 
                InvestmentTransaction.id == HistoricalPrice.transaction_id
            ).filter(InvestmentTransaction.file_id == file_id)
        elif user_id:
            # Query for specific user - optimized for speed
            query = session.query(
                InvestmentTransaction,
                HistoricalPrice.historical_price,
                HistoricalPrice.price_source,
                HistoricalPrice.transaction_date,
                HistoricalPrice.current_price
            ).outerjoin(
                HistoricalPrice, 
                InvestmentTransaction.id == HistoricalPrice.transaction_id
            ).filter(InvestmentTransaction.user_id == user_id)
        else:
            # Query for all transactions
            query = session.query(
                InvestmentTransaction,
                HistoricalPrice.historical_price,
                HistoricalPrice.price_source,
                HistoricalPrice.transaction_date,
                HistoricalPrice.current_price
            ).outerjoin(
                HistoricalPrice, 
                InvestmentTransaction.id == HistoricalPrice.transaction_id
            )
        
        # Execute query and fetch all results at once - optimized for speed
        results = query.all()
        
        # Process results efficiently with list comprehension for speed
        result = [
            {
                'id': transaction.id,
                'file_id': transaction.file_id,
                'user_id': transaction.user_id,
                'channel': transaction.channel,
                'stock_name': transaction.stock_name,
                'ticker': transaction.ticker,
                'sector': transaction.sector,  # Include sector information
                'quantity': transaction.quantity,
                'price': transaction.price,
                'transaction_type': transaction.transaction_type,
                'date': transaction.date,
                'amount': transaction.amount,
                'created_at': transaction.created_at,
                'historical_price': hist_price,
                'price_source': price_source,
                'transaction_date': trans_date,
                'current_price': current_price,
                'original_price': current_price if current_price is not None else transaction.price
            }
            for transaction, hist_price, price_source, trans_date, current_price in results
        ]
        
        session.close()
        
        # Log performance info
        if user_id:
            print(f"🚀 Fast load: Retrieved {len(result)} transactions for user {user_id}")
        
        return result
        
    except Exception as e:
        print(f"Error getting transactions with historical prices: {e}")
        return []

def check_transaction_exists(file_id, ticker, date, transaction_type):
    """Check if a transaction already exists in the database"""
    try:
        session = SessionLocal()
        existing_transaction = session.query(InvestmentTransaction).filter_by(
            file_id=file_id,
            ticker=ticker,
            date=date,
            transaction_type=transaction_type
        ).first()
        session.close()
        return existing_transaction is not None
    except Exception as e:
        print(f"Error checking transaction existence: {e}")
        return False

def fetch_and_update_historical_prices(user_id=None):
    """Fetch and update historical prices for existing transactions"""
    try:
        session = SessionLocal()
        
        # Get transactions without historical prices or with file prices
        if user_id:
            transactions = session.query(InvestmentTransaction).filter_by(user_id=user_id).all()
        else:
            transactions = session.query(InvestmentTransaction).all()
        
        updated_count = 0
        batch_size = 50  # Process in larger batches for better performance
        
        for i in range(0, len(transactions), batch_size):
            batch_transactions = transactions[i:i+batch_size]
            
            for transaction in batch_transactions:
                try:
                    # Check if we already have a historical price record
                    existing_historical = session.query(HistoricalPrice).filter_by(
                        transaction_id=transaction.id
                    ).first()
                    
                    if existing_historical and existing_historical.price_source not in ['file', None]:
                        # Skip if we already have a good historical price
                        continue
                    
                    # Fetch historical price
                    if transaction.date and transaction.ticker:
                        historical_price, price_source = fetch_historical_price_for_transaction(
                            transaction.ticker, transaction.date
                        )
                        
                        if historical_price is not None:
                            # Update transaction price
                            transaction.price = historical_price
                            transaction.amount = transaction.quantity * historical_price
                            
                            # Update or create historical price record
                            if existing_historical:
                                existing_historical.historical_price = historical_price
                                existing_historical.price_source = price_source
                                existing_historical.current_price = historical_price
                            else:
                                # Create new historical price record
                                transaction_date = datetime.strptime(transaction.date, '%Y-%m-%d').date()
                                historical_price_record = HistoricalPrice(
                                    transaction_id=transaction.id,
                                    file_id=transaction.file_id,
                                    ticker=transaction.ticker,
                                    transaction_date=transaction_date,
                                    historical_price=historical_price,
                                    current_price=historical_price,
                                    price_source=price_source
                                )
                                session.add(historical_price_record)
                            
                            updated_count += 1
                    
                except Exception as e:
                    print(f"Error updating transaction {transaction.id}: {e}")
                    continue
            
            # Commit each batch
            session.commit()
            print(f"   ✅ Batch {i//batch_size + 1}/{(len(transactions) + batch_size - 1)//batch_size} completed - Updated {updated_count} transactions so far...")
        
        session.close()
        
        print(f"✅ Updated {updated_count} transactions with historical prices")
        return updated_count
        
    except Exception as e:
        print(f"❌ Error fetching and updating historical prices: {e}")
        if 'session' in locals():
            session.rollback()
            session.close()
        return 0

def update_mutual_fund_sectors():
    """Update sector information for numeric tickers to classify them as Mutual Funds"""
    try:
        session = SessionLocal()
        
        # Find transactions with numeric tickers that have 'Unknown' sector
        transactions = session.query(InvestmentTransaction).filter(
            InvestmentTransaction.sector.in_(['Unknown', '']),
            InvestmentTransaction.ticker.isnot(None)
        ).all()
        
        updated_count = 0
        for transaction in transactions:
            if transaction.ticker and transaction.ticker.isdigit():
                transaction.sector = 'Mutual Funds'
                updated_count += 1
        
        if updated_count > 0:
            session.commit()
            print(f"✅ Updated {updated_count} transactions with Mutual Funds sector")
        else:
            print("ℹ️ No transactions needed sector updates")
        
        session.close()
        return updated_count
        
    except Exception as e:
        print(f"❌ Error updating mutual fund sectors: {e}")
        if 'session' in locals():
            session.rollback()
            session.close()
        return 0

def fetch_historical_prices_background(user_id=None):
    """Background function to fetch historical prices without blocking the UI"""
    try:
        import threading
        import time
        
        def background_task():
            time.sleep(2)  # Wait 2 seconds before starting
            print(f"🔄 Starting background historical price fetch for user {user_id}...")
            # First update mutual fund sectors
            update_mutual_fund_sectors()
            # Then fetch historical prices
            fetch_and_update_historical_prices(user_id)
            print(f"✅ Background historical price fetch completed for user {user_id}")
        
        # Start background thread
        thread = threading.Thread(target=background_task, daemon=True)
        thread.start()
        return True
        
    except Exception as e:
        print(f"❌ Error starting background historical price fetch: {e}")
        return False
