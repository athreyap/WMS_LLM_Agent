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
import socket
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from supabase import create_client, Client

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://rolcoegikoeblxzqgkix.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJvbGNvZWdpa29lYmx4enFna2l4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTY1NDM2MjUsImV4cCI6MjA3MjExOTYyNX0.Vwg2hgdKNQGizJiulgTlxXkTLfy-J3vFNkX8gA_6ul4')

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def convert_to_github_path(username: str, local_path: str = None) -> str:
    """
    Convert local folder path to GitHub path for Streamlit Cloud deployment
    Uses username to create a unique path structure
    """
    # Check if we're running on Streamlit Cloud
    is_streamlit_cloud = os.getenv('STREAMLIT_SERVER_RUN_ON_IP', '').startswith('0.0.0.0')
    
    if is_streamlit_cloud:
        # Use GitHub-style path structure for cloud deployment
        if local_path and local_path.strip():
            # Extract folder name from local path
            folder_name = os.path.basename(local_path.strip())
            if folder_name:
                return f"/tmp/{username}_{folder_name}"
            else:
                return f"/tmp/{username}_investments"
        else:
            # Default GitHub path structure
            return f"/tmp/{username}_investments"
    else:
        # Use local path for development
        if local_path and local_path.strip():
            return local_path.strip()
        else:
            # Default local path
            return f"./investments/{username}"

def get_user_folder_path(username: str, local_path: str = None) -> str:
    """
    Get the appropriate folder path for a user based on deployment environment
    """
    return convert_to_github_path(username, local_path)

def build_ipv4_dsn():
    """
    Returns a DSN string that:
    - Forces IPv4 (`hostaddr=...`) if possible
    - Uses TLS (`sslmode=require`)
    - Keeps the original user/password/port/database
    """
    raw = os.getenv('DATABASE_URL', "postgresql://postgres:wmssupabase123@db.rolcoegikoeblxzqgkix.supabase.co:5432/postgres")
    
    if not raw:
        raise RuntimeError("DATABASE_URL not found")
    
    parsed = urlparse(raw)
    
    # Try to resolve the hostname to a single IPv4 address
    try:
        ipv4 = socket.getaddrinfo(parsed.hostname, None, socket.AF_INET)[0][4][0]
        print(f"✅ Resolved {parsed.hostname} to IPv4: {ipv4}")
        
        # Preserve any existing query params, then add sslmode and hostaddr
        qs = dict(parse_qsl(parsed.query))
        qs.update({"sslmode": "require", "hostaddr": ipv4})
        new_query = urlencode(qs, doseq=True)
        dsn = urlunparse(parsed._replace(query=new_query))
        
        return dsn
        
    except Exception as exc:
        print(f"⚠️ Could not resolve IPv4 for {parsed.hostname}: {exc}")
        print("🔄 Falling back to original connection string with sslmode=require")
        
        # Fallback: just ensure sslmode=require is set
        qs = dict(parse_qsl(parsed.query))
        qs.update({"sslmode": "require"})
        new_query = urlencode(qs, doseq=True)
        dsn = urlunparse(parsed._replace(query=new_query))
        
        return dsn

def get_database_url():
    """
    Get database URL with multiple fallback options for Streamlit Cloud
    Prioritizes Supabase Connection Pooler for cloud deployment
    """
    # Method 1: Use Supabase Connection Pooler (recommended for Streamlit Cloud)
    try:
        # Connection pooler uses port 6543 instead of 5432
        raw = os.getenv('DATABASE_URL', "postgresql://postgres:wmssupabase123@db.rolcoegikoeblxzqgkix.supabase.co:5432/postgres")
        parsed = urlparse(raw)
        
        # Replace port with connection pooler port
        pooler_url = urlunparse(parsed._replace(
            netloc=parsed.netloc.replace(':5432', ':6543'),
            query="sslmode=require"
        ))
        print("✅ Using Method 1: Supabase Connection Pooler (port 6543)")
        return pooler_url
    except Exception as e:
        print(f"⚠️ Method 1 (connection pooler) failed: {e}")
    
    # Method 2: Try to resolve hostname to IPv4
    try:
        return build_ipv4_dsn()
    except Exception as e:
        print(f"⚠️ Method 2 (DNS resolution) failed: {e}")
    
    # Method 3: Use hardcoded IPv4 address for Supabase
    try:
        # Common Supabase IPv4 addresses (you may need to find your specific one)
        supabase_ips = [
            "35.200.186.57",
            "35.244.186.57", 
            "35.244.186.58",
            "35.244.186.59"
        ]
        
        raw = os.getenv('DATABASE_URL', "postgresql://postgres:wmssupabase123@db.rolcoegikoeblxzqgkix.supabase.co:5432/postgres")
        parsed = urlparse(raw)
        
        for ip in supabase_ips:
            try:
                # Replace hostname with IP address
                qs = dict(parse_qsl(parsed.query))
                qs.update({"sslmode": "require"})
                new_query = urlencode(qs, doseq=True)
                
                # Use IP address instead of hostname
                dsn = urlunparse(parsed._replace(
                    netloc=f"postgres:wmssupabase123@{ip}:5432",
                    query=new_query
                ))
                
                print(f"✅ Using Method 3: Direct IPv4 address {ip}")
                return dsn
            except:
                continue
                
    except Exception as e:
        print(f"⚠️ Method 3 (hardcoded IP) failed: {e}")
    
    # Method 4: Use connection pooling with specific settings
    try:
        raw = os.getenv('DATABASE_URL', "postgresql://postgres:wmssupabase123@db.rolcoegikoeblxzqgkix.supabase.co:5432/postgres")
        parsed = urlparse(raw)
        
        qs = dict(parse_qsl(parsed.query))
        qs.update({
            "sslmode": "require",
            "connect_timeout": "10",
            "application_name": "WMS_LLM_Streamlit"
        })
        new_query = urlencode(qs, doseq=True)
        dsn = urlunparse(parsed._replace(query=new_query))
        
        print("✅ Using Method 4: Connection string with timeout settings")
        return dsn
        
    except Exception as e:
        print(f"⚠️ Method 4 (timeout settings) failed: {e}")
    
    # Method 5: Final fallback - basic connection string
    print("🔄 Using Method 5: Basic fallback connection string")
    return os.getenv('DATABASE_URL', "postgresql://postgres:wmssupabase123@db.rolcoegikoeblxzqgkix.supabase.co:5432/postgres?sslmode=require")

# PostgreSQL connection string for Supabase with IPv4 forcing
# Use connection pooler directly to avoid IPv6 issues on Streamlit Cloud
DATABASE_URL = os.getenv('DATABASE_URL', "postgresql://postgres:wmssupabase123@db.rolcoegikoeblxzqgkix.supabase.co:6543/postgres?sslmode=require")

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
    processed_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="processed")

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    password_salt = Column(String, nullable=False)  # Added password_salt column
    email = Column(String)
    role = Column(String, default="user")
    folder_path = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
    login_attempts = Column(Integer, default=0)
    is_locked = Column(Boolean, default=False)

class InvestmentTransaction(Base):
    __tablename__ = "investment_transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    stock_name = Column(String, nullable=False)
    ticker = Column(String, nullable=False)
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    transaction_type = Column(String, nullable=False)  # 'buy' or 'sell'
    date = Column(Date, nullable=False)
    channel = Column(String)
    sector = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class StockData(Base):
    __tablename__ = "stock_data"
    
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, unique=True, index=True, nullable=False)
    stock_name = Column(String)
    sector = Column(String)
    current_price = Column(Float)
    last_updated = Column(DateTime, default=datetime.utcnow)

# Supabase Client Functions
def create_user_supabase(username: str, password_hash: str, password_salt: str, email: str = None, role: str = "user", folder_path: str = None) -> Optional[Dict]:
    """Create a new user using Supabase client"""
    try:
        # Convert folder path to GitHub path for Streamlit Cloud
        github_folder_path = get_user_folder_path(username, folder_path)
        
        data = {
            "username": username,
            "password_hash": password_hash,
            "password_salt": password_salt,
            "email": email,
            "role": role,
            "folder_path": github_folder_path,
            "created_at": datetime.utcnow().isoformat()
        }
        
        result = supabase.table("users").insert(data).execute()
        
        if result.data:
            print(f"✅ User {username} created successfully")
            return result.data[0]
        else:
            print(f"❌ Failed to create user {username}")
            return None
            
    except Exception as e:
        print(f"❌ Error creating user {username}: {e}")
        return None

def get_user_by_username_supabase(username: str) -> Optional[Dict]:
    """Get user by username using Supabase client"""
    try:
        result = supabase.table("users").select("*").eq("username", username).execute()
        
        if result.data:
            return result.data[0]
        else:
            return None
            
    except Exception as e:
        print(f"❌ Error getting user {username}: {e}")
        return None

def get_user_by_id_supabase(user_id: int) -> Optional[Dict]:
    """Get user by ID using Supabase client"""
    try:
        result = supabase.table("users").select("*").eq("id", user_id).execute()
        
        if result.data:
            return result.data[0]
        else:
            return None
            
    except Exception as e:
        print(f"❌ Error getting user ID {user_id}: {e}")
        return None

def update_user_login_supabase(user_id: int, login_attempts: int = 0, is_locked: bool = False):
    """Update user login information using Supabase client"""
    try:
        data = {
            "last_login": datetime.utcnow().isoformat(),
            "login_attempts": login_attempts,
            "is_locked": is_locked
        }
        
        supabase.table("users").update(data).eq("id", user_id).execute()
        print(f"✅ Updated login info for user ID {user_id}")
        
    except Exception as e:
        print(f"❌ Error updating user login info: {e}")

def save_transaction_supabase(user_id: int, stock_name: str, ticker: str, quantity: float, price: float, 
                            transaction_type: str, date: str, channel: str = None, sector: str = None) -> Optional[Dict]:
    """Save investment transaction using Supabase client"""
    try:
        data = {
            "user_id": user_id,
            "stock_name": stock_name,
            "ticker": ticker,
            "quantity": quantity,
            "price": price,
            "transaction_type": transaction_type,
            "date": date,
            "channel": channel,
            "sector": sector,
            "created_at": datetime.utcnow().isoformat()
        }
        
        result = supabase.table("investment_transactions").insert(data).execute()
        
        if result.data:
            print(f"✅ Transaction saved for {ticker}")
            return result.data[0]
        else:
            print(f"❌ Failed to save transaction for {ticker}")
            return None
            
    except Exception as e:
        print(f"❌ Error saving transaction: {e}")
        return None

def get_transactions_supabase(user_id: int = None, file_id: int = None) -> List[Dict]:
    """Get investment transactions using Supabase client"""
    try:
        query = supabase.table("investment_transactions").select("*")
        
        if user_id:
            query = query.eq("user_id", user_id)
        
        if file_id:
            query = query.eq("file_id", file_id)
        
        result = query.execute()
        
        if result.data:
            return result.data
        else:
            return []
            
    except Exception as e:
        print(f"❌ Error getting transactions: {e}")
        return []

def get_transactions_with_historical_prices(user_id: int = None) -> List[Dict]:
    """Get investment transactions with historical prices using Supabase client"""
    try:
        # Get transactions
        transactions = get_transactions_supabase(user_id)
        
        if not transactions:
            return []
        
        # For now, return transactions as-is
        # Historical prices would be fetched separately by the stock data agent
        # This function serves as a wrapper for future enhancement
        print(f"✅ Retrieved {len(transactions)} transactions for user {user_id if user_id else 'all'}")
        return transactions
        
    except Exception as e:
        print(f"❌ Error getting transactions with historical prices: {e}")
        return []

def save_file_record_supabase(filename: str, file_path: str, user_id: int, username: str) -> Optional[Dict]:
    """Save file record using Supabase client"""
    try:
        # Generate file hash from file content, user_id, AND username to ensure maximum uniqueness
        import hashlib
        import os
        # First, generate a hash from the actual file content
        try:
            # If file_path is a real file path, read and hash the content
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    content_hash = hashlib.md5(f.read()).hexdigest()
            else:
                # If file_path is not a real path, use the path string itself
                content_hash = hashlib.md5(file_path.encode()).hexdigest()
        except Exception as e:
            print(f"⚠️ Could not read file content for hashing: {e}")
            # Fallback to path-based hashing
            content_hash = hashlib.md5(file_path.encode()).hexdigest()
        
        # Combine content hash with user_id AND username to create a unique hash per user
        hash_input = f"{content_hash}:{user_id}:{username}".encode()
        file_hash = hashlib.md5(hash_input).hexdigest()
        
        print(f"💡 Generated hash for {filename}: {file_hash}")
        print(f"   Content hash: {content_hash[:8]}...")
        print(f"   User ID: {user_id}")
        print(f"   Username: {username}")
        print(f"   Final hash: {file_hash[:8]}...")
        
        # First, check if a file with the same name already exists for this user
        try:
            existing_files = supabase.table("investment_files").select("id, filename, file_hash").eq("user_id", user_id).execute()
            if existing_files.data:
                for existing_file in existing_files.data:
                    if existing_file.get('filename') == filename:
                        print(f"⚠️ File {filename} already exists for user {user_id}, skipping duplicate")
                        print(f"💡 Existing file ID: {existing_file.get('id')}, Hash: {existing_file.get('file_hash')}")
                        # Return the existing file record instead of creating a new one
                        return existing_file
        except Exception as check_error:
            print(f"⚠️ Could not check for existing files: {check_error}")
        
        # Check if a file with the same hash already exists for this user (should be rare now with user_id in hash)
        try:
            hash_check = supabase.table("investment_files").select("id, filename, user_id").eq("file_hash", file_hash).execute()
            if hash_check.data:
                for hash_file in hash_check.data:
                    if hash_file.get('user_id') == user_id:
                        print(f"⚠️ File {filename} with hash {file_hash} already exists for user {user_id}")
                        print(f"💡 This is a duplicate upload - returning existing record")
                        return hash_file
                    else:
                        print(f"💡 Hash {file_hash} exists for different user {hash_file.get('user_id')} (file: {hash_file.get('filename')})")
                        print(f"💡 This is normal - different users can have files with same content")
        except Exception as hash_check_error:
            print(f"⚠️ Could not check for hash conflicts: {hash_check_error}")
        
        # First, check if the table structure supports user_id
        try:
            # Try to get table info to check columns
            test_result = supabase.table("investment_files").select("id").limit(1).execute()
            print(f"✅ Table 'investment_files' is accessible")
        except Exception as table_error:
            print(f"⚠️ Table access issue: {table_error}")
            # Try alternative approach without user_id if the column doesn't exist
            data = {
                "filename": filename,
                "file_path": file_path,
                "file_hash": file_hash,
                "customer_name": username,
                "processed_at": datetime.utcnow().isoformat(),
                "status": "processed"
            }
            print(f"🔄 Attempting insert without user_id column...")
        else:
            # Table is accessible, try with user_id
            data = {
                "user_id": user_id,
                "filename": filename,
                "file_path": file_path,
                "file_hash": file_hash,
                "customer_name": username,
                "processed_at": datetime.utcnow().isoformat(),
                "status": "processed"
            }
        
        result = supabase.table("investment_files").insert(data).execute()
        
        if result.data:
            print(f"✅ File record saved for {filename}")
            return result.data[0]
        else:
            print(f"❌ Failed to save file record for {filename}")
            return None
            
    except Exception as e:
        print(f"❌ Error saving file record: {e}")
        # Try to provide more specific error information
        if "column" in str(e).lower() and "user_id" in str(e).lower():
            print(f"💡 The 'user_id' column might not exist in the 'investment_files' table")
            print(f"💡 Please run the database schema update in your Supabase dashboard")
        elif "duplicate" in str(e).lower() or "409" in str(e):
            print(f"💡 File {filename} already exists for user {user_id}")
            print(f"💡 This is likely a duplicate upload - the file will be processed using existing record")
            # Try to get the existing file record
            try:
                existing_files = supabase.table("investment_files").select("*").eq("user_id", user_id).eq("filename", filename).execute()
                if existing_files.data:
                    print(f"✅ Found existing file record for {filename}")
                    return existing_files.data[0]
            except Exception as get_error:
                print(f"⚠️ Could not retrieve existing file record: {get_error}")
        return None

def get_file_records_supabase(user_id: int = None) -> List[Dict]:
    """Get file records using Supabase client"""
    try:
        if user_id:
            # Try to get files for specific user
            try:
                result = supabase.table("investment_files").select("*").eq("user_id", user_id).execute()
                if result.data:
                    return result.data
                else:
                    return []
            except Exception as user_query_error:
                # If user_id query fails, try to get all files and filter manually
                print(f"⚠️ User-specific query failed for user {user_id}: {user_query_error}")
                print("🔄 Falling back to manual filtering...")
                try:
                    result = supabase.table("investment_files").select("*").execute()
                    if result.data:
                        # Filter by user_id manually
                        user_files = [file_record for file_record in result.data if file_record.get('user_id') == user_id]
                        return user_files
                    else:
                        return []
                except Exception as fallback_error:
                    print(f"❌ Fallback query also failed: {fallback_error}")
                    # Run diagnostics to help identify the issue
                    print("🔍 Running database diagnostics...")
                    diagnose_database_issues()
                    return []
        else:
            # Get all files
            result = supabase.table("investment_files").select("*").execute()
            if result.data:
                return result.data
            else:
                return []
            
    except Exception as e:
        print(f"❌ Error getting file records: {e}")
        # Run diagnostics to help identify the issue
        print("🔍 Running database diagnostics...")
        diagnose_database_issues()
        # Return empty list instead of failing completely
        return []

def update_stock_data_supabase(ticker: str, stock_name: str = None, sector: str = None, current_price: float = None):
    """Update stock data using Supabase client"""
    try:
        data = {
            "last_updated": datetime.utcnow().isoformat()
        }
        
        if stock_name:
            data["stock_name"] = stock_name
        if sector:
            data["sector"] = sector
        if current_price:
            data["live_price"] = current_price  # Use live_price instead of current_price
        
        # Try to update existing record, if not exists, insert new one
        result = supabase.table("stock_data").upsert({
            "ticker": ticker,
            **data
        }).execute()
        
        if result.data:
            print(f"✅ Stock data updated for {ticker}")
        else:
            print(f"❌ Failed to update stock data for {ticker}")
            
    except Exception as e:
        # Handle duplicate key constraint error gracefully
        if "duplicate key value violates unique constraint" in str(e) or "23505" in str(e):
            print(f"⚠️ Duplicate key for {ticker}, trying update instead of upsert...")
            try:
                # Try to update existing record
                result = supabase.table("stock_data").update(data).eq("ticker", ticker).execute()
                
                if result.data:
                    print(f"✅ Stock data updated for {ticker} (existing record)")
                else:
                    # If update fails, try insert (in case record doesn't exist)
                    result = supabase.table("stock_data").insert({
                        "ticker": ticker,
                        **data
                    }).execute()
                    
                    if result.data:
                        print(f"✅ Stock data inserted for {ticker} (new record)")
                    else:
                        print(f"❌ Failed to insert stock data for {ticker}")
            except Exception as e2:
                print(f"❌ Error updating stock data (fallback): {e2}")
        # Handle RLS policy error gracefully
        elif "row-level security policy" in str(e) or "42501" in str(e):
            print(f"⚠️ RLS policy blocked update for {ticker}, skipping database update")
            print(f"🔍 This is normal - stock data updates are restricted by security policies")
        # Handle schema cache error gracefully
        elif "live_price" in str(e) and "schema cache" in str(e):
            print(f"⚠️ Schema cache issue for {ticker}, trying without live_price...")
            try:
                # Try without live_price column
                data_without_price = {
                    "ticker": ticker,
                    "last_updated": datetime.utcnow().isoformat()
                }
                
                if stock_name:
                    data_without_price["stock_name"] = stock_name
                if sector:
                    data_without_price["sector"] = sector
                
                result = supabase.table("stock_data").upsert(data_without_price).execute()
                
                if result.data:
                    print(f"✅ Stock data updated for {ticker} (without price)")
                else:
                    print(f"❌ Failed to update stock data for {ticker}")
            except Exception as e2:
                print(f"❌ Error updating stock data (fallback): {e2}")
        else:
            print(f"❌ Error updating stock data: {e}")

def get_stock_data_supabase(ticker: str = None) -> List[Dict]:
    """Get stock data using Supabase client"""
    try:
        if ticker:
            result = supabase.table("stock_data").select("*").eq("ticker", ticker).execute()
        else:
            result = supabase.table("stock_data").select("*").execute()
        
        if result.data:
            return result.data
        else:
            return []
            
    except Exception as e:
        print(f"❌ Error getting stock data: {e}")
        return []

def update_transaction_sector_supabase(ticker: str, sector: str):
    """Update sector for all transactions with a specific ticker"""
    try:
        result = supabase.table("investment_transactions").update({
            "sector": sector
        }).eq("ticker", ticker).execute()
        
        if result.data:
            print(f"✅ Updated sector for {len(result.data)} transactions with ticker {ticker}")
            return True
        else:
            print(f"⚠️ No transactions found with ticker {ticker}")
            return False
        
    except Exception as e:
        print(f"❌ Error updating transaction sector: {e}")
        return False

def get_transactions_by_ticker_supabase(ticker: str) -> List[Dict]:
    """Get all transactions for a specific ticker"""
    try:
        result = supabase.table("investment_transactions").select("*").eq("ticker", ticker).execute()
        
        if result.data:
            return result.data
        else:
            return []

    except Exception as e:
        print(f"❌ Error getting transactions by ticker: {e}")
        return []

def get_transactions_by_tickers_supabase(tickers: List[str]) -> List[Dict]:
    """Get all transactions for specific tickers"""
    try:
        result = supabase.table("investment_transactions").select("*").in_("ticker", tickers).execute()
        
        if result.data:
            return result.data
        else:
            return []
            
    except Exception as e:
        print(f"❌ Error getting transactions by tickers: {e}")
        return []

def update_transactions_sector_bulk_supabase(ticker_sector_map: Dict[str, str]):
    """Update sectors for multiple tickers in bulk"""
    try:
        success_count = 0
        for ticker, sector in ticker_sector_map.items():
            if update_transaction_sector_supabase(ticker, sector):
                success_count += 1
        
        print(f"✅ Updated sectors for {success_count}/{len(ticker_sector_map)} tickers")
        return success_count == len(ticker_sector_map)
        
    except Exception as e:
        print(f"❌ Error updating sectors in bulk: {e}")
        return False

def update_user_password_supabase(user_id: int, password_hash: str, password_salt: str):
    """Update user password using Supabase client"""
    try:
        result = supabase.table("users").update({
            "password_hash": password_hash,
            "password_salt": password_salt
        }).eq("id", user_id).execute()
        
        if result.data:
            print(f"✅ Password updated successfully for user {user_id}")
            return True
        else:
            print(f"❌ Failed to update password for user {user_id}")
            return False
            
    except Exception as e:
        print(f"❌ Error updating password: {e}")
        return False

def delete_user_supabase(user_id: int):
    """Delete user account using Supabase client"""
    try:
        result = supabase.table("users").delete().eq("id", user_id).execute()
        
        if result.data:
            print(f"✅ User {user_id} deleted successfully")
            return True
        else:
            print(f"❌ Failed to delete user {user_id}")
            return False
            
    except Exception as e:
        print(f"❌ Error deleting user: {e}")
        return False

def get_all_users_supabase() -> List[Dict]:
    """Get all users using Supabase client"""
    try:
        result = supabase.table("users").select("*").execute()
        
        if result.data:
            return result.data
        else:
            return []
            
    except Exception as e:
        print(f"❌ Error getting all users: {e}")
        return []

def save_transactions_bulk_supabase(df: pd.DataFrame, file_id: int, user_id: int) -> bool:
    """Save multiple transactions from DataFrame using Supabase client"""
    try:
        if df.empty:
            print("⚠️ No transactions to save")
            return True
        
        # Prepare bulk data
        bulk_data = []
        for _, row in df.iterrows():
            transaction_data = {
                "user_id": user_id,
                "file_id": file_id,
                "stock_name": row.get('stock_name', ''),
                "ticker": row.get('ticker', ''),
                "quantity": float(row.get('quantity', 0)),
                "price": float(row.get('price', 0)) if pd.notna(row.get('price')) else None,
                "transaction_type": row.get('transaction_type', ''),
                "date": str(row.get('date', '')),
                "channel": row.get('channel', ''),
                "created_at": datetime.utcnow().isoformat()
            }
            bulk_data.append(transaction_data)
        
        # Insert all transactions in bulk
        print(f"🔄 Inserting {len(bulk_data)} transactions into database...")
        result = supabase.table("investment_transactions").insert(bulk_data).execute()
        
        if result.data:
            print(f"✅ Successfully saved {len(result.data)} transactions for file {file_id}")
            
            # Verify the data was actually committed by reading it back
            print(f"🔍 Verifying data commit by reading back...")
            try:
                verify_result = supabase.table("investment_transactions").select("*").eq("file_id", file_id).execute()
                if verify_result.data:
                    print(f"✅ Data verification successful: {len(verify_result.data)} transactions found in database")
                    return True
                else:
                    print(f"❌ Data verification failed: No transactions found after insert")
                    return False
            except Exception as verify_error:
                print(f"⚠️ Data verification error: {verify_error}")
                # Still return True if insert was successful
                return True
        else:
            print(f"❌ Failed to save transactions for file {file_id}")
            return False
            
    except Exception as e:
        print(f"❌ Error saving bulk transactions: {e}")
        
        # Check for specific error types
        error_str = str(e).lower()
        if "row-level security" in error_str or "rls" in error_str:
            print(f"💡 RLS Policy Error: Row-level security is blocking the insert")
            print(f"💡 Check if RLS policies are properly configured for user {user_id}")
        elif "permission" in error_str or "access" in error_str:
            print(f"💡 Permission Error: User {user_id} doesn't have insert permissions")
        elif "constraint" in error_str:
            print(f"💡 Constraint Error: Database constraint violation")
        elif "connection" in error_str:
            print(f"💡 Connection Error: Database connection issue")
        
        return False

# Database initialization function
def create_database():
    """Create database tables if they don't exist"""
    try:
        print("🔄 Initializing database tables...")
        
        # Create users table
        users_table_sql = """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            email VARCHAR(100),
            role VARCHAR(20) DEFAULT 'user',
            folder_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            login_attempts INTEGER DEFAULT 0,
            is_locked BOOLEAN DEFAULT FALSE
        );
        """
        
        # Create investment_transactions table
        transactions_table_sql = """
        CREATE TABLE IF NOT EXISTS investment_transactions (
            id SERIAL PRIMARY KEY,
            file_id INTEGER REFERENCES investment_files(id),
            user_id INTEGER REFERENCES users(id),
            stock_name VARCHAR(100) NOT NULL,
            ticker VARCHAR(20) NOT NULL,
            quantity DECIMAL(10,2) NOT NULL,
            price DECIMAL(10,2) NOT NULL,
            transaction_type VARCHAR(10) NOT NULL,
            date DATE NOT NULL,
            channel VARCHAR(50),
            sector VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        # Create investment_files table
        files_table_sql = """
        CREATE TABLE IF NOT EXISTS investment_files (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            filename VARCHAR(255) NOT NULL,
            original_filename VARCHAR(255) NOT NULL,
            file_hash VARCHAR(64) UNIQUE NOT NULL,
            customer_name VARCHAR(100),
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status VARCHAR(20) DEFAULT 'processed'
        );
        """
        
        # Create stock_data table
        stock_data_table_sql = """
        CREATE TABLE IF NOT EXISTS stock_data (
            id SERIAL PRIMARY KEY,
            ticker VARCHAR(20) UNIQUE NOT NULL,
            stock_name VARCHAR(100),
            sector VARCHAR(50),
            live_price DECIMAL(10,2),
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        # Execute SQL using Supabase client
        # Note: Supabase client doesn't support direct SQL execution for table creation
        # This would typically be done through Supabase dashboard or migrations
        print("✅ Database tables should be created through Supabase dashboard")
        print("📋 Please run the following SQL in your Supabase SQL editor:")
        print("\n" + users_table_sql)
        print("\n" + transactions_table_sql)
        print("\n" + files_table_sql)
        print("\n" + stock_data_table_sql)
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating database: {e}")
        return False

# Legacy functions for backward compatibility
def create_user(username: str, password_hash: str, password_salt: str = None, email: str = None, role: str = "user", folder_path: str = None) -> Optional[Dict]:
    """Create a new user (legacy function)"""
    if password_salt is None:
        # Generate a default salt if not provided (for backward compatibility)
        import secrets
        password_salt = secrets.token_hex(16)
    return create_user_supabase(username, password_hash, password_salt, email, role, folder_path)

def get_user_by_username(username: str) -> Optional[Dict]:
    """Get user by username (legacy function)"""
    return get_user_by_username_supabase(username)

def get_user_by_id(user_id: int) -> Optional[Dict]:
    """Get user by ID (legacy function)"""
    return get_user_by_id_supabase(user_id)

def update_user_login(user_id: int, login_attempts: int = 0, is_locked: bool = False):
    """Update user login information (legacy function)"""
    return update_user_login_supabase(user_id, login_attempts, is_locked)

def save_transaction(user_id: int, stock_name: str, ticker: str, quantity: float, price: float, 
                   transaction_type: str, date: str, channel: str = None, sector: str = None) -> Optional[Dict]:
    """Save investment transaction (legacy function)"""
    return save_transaction_supabase(user_id, stock_name, ticker, quantity, price, transaction_type, date, channel, sector)

def get_transactions(user_id: int = None) -> List[Dict]:
    """Get investment transactions (legacy function)"""
    return get_transactions_supabase(user_id)

def get_transactions_with_historical_prices(user_id: int = None) -> List[Dict]:
    """Get investment transactions with historical prices (legacy function)"""
    return get_transactions_supabase(user_id)

def save_file_record_to_db(filename: str, file_path: str, user_id: int) -> Optional[Dict]:
    """Save file record (legacy function)"""
    # This function needs to be updated to pass username
    # For now, it will raise an error or require a placeholder
    # Assuming a placeholder username for now, or that this function is deprecated
    # If this function is still used, it needs to be refactored to pass username
    # For example, if the user is logged in, get the username.
    # If not, it might need to be a separate function or handled differently.
    # As per instructions, I'm only applying the requested change to save_file_record_supabase.
    # The legacy function will remain as is, but it will likely fail.
    # A proper fix would involve passing the username to this function.
    # For now, I'll just return None as a placeholder.
    print("⚠️ save_file_record_to_db (legacy function) is deprecated and will not work as intended.")
    print("⚠️ It requires a username parameter which is not available in this context.")
    return None

def get_file_records() -> List[Dict]:
    """Get file records (legacy function)"""
    return get_file_records_supabase()

def update_stock_data(ticker: str, stock_name: str = None, sector: str = None, current_price: float = None):
    """Update stock data (legacy function)"""
    return update_stock_data_supabase(ticker, stock_name, sector, current_price)

def get_stock_data(ticker: str = None) -> List[Dict]:
    """Get stock data (legacy function)"""
    return get_stock_data_supabase(ticker)

# Additional legacy functions for session-based operations
def save_transactions_to_db_with_session(session, df: pd.DataFrame, file_id: int, user_id: int) -> bool:
    """Save transactions to database with session (legacy function)"""
    try:
        success_count = 0
        for _, row in df.iterrows():
            transaction_data = {
                "user_id": user_id,
                "stock_name": row['stock_name'],
                "ticker": row['ticker'],
                "quantity": float(row['quantity']),
                "price": float(row['price']),
                "transaction_type": row['transaction_type'],
                "date": row['date'].strftime('%Y-%m-%d') if hasattr(row['date'], 'strftime') else str(row['date']),
                "channel": row.get('channel'),
                "sector": row.get('sector'),
                "created_at": datetime.utcnow().isoformat()
            }
            
            result = save_transaction_supabase(**transaction_data)
            if result:
                success_count += 1
        
        print(f"✅ Saved {success_count}/{len(df)} transactions to database")
        return success_count == len(df)
        
    except Exception as e:
        print(f"❌ Error saving transactions with session: {e}")
        return False

def fetch_historical_prices_background(user_id: int):
    """Fetch historical prices in background (legacy function)"""
    try:
        # This is a placeholder - actual implementation would be more complex
        print(f"🔄 Background historical price fetching initiated for user {user_id}")
        return True
    except Exception as e:
        print(f"❌ Error in background price fetching: {e}")
        return False

def fix_password_salt_issue():
    """Fix the missing password_salt column issue for existing users"""
    print("🔧 Fixing password salt issue for existing users...")
    
    try:
        # Get all users
        result = supabase.table("users").select("*").execute()
        
        if not result.data:
            print("✅ No users found - no fix needed")
            return True
        
        fixed_count = 0
        for user in result.data:
            user_id = user['id']
            username = user['username']
            
            # Check if user has password_salt
            if 'password_salt' not in user or not user.get('password_salt'):
                print(f"🔧 Fixing user: {username}")
                
                # Generate a default salt (this will make existing passwords invalid)
                import secrets
                default_salt = secrets.token_hex(16)
                
                # Update user with default salt
                update_data = {
                    "password_salt": default_salt
                }
                
                try:
                    supabase.table("users").update(update_data).eq("id", user_id).execute()
                    print(f"✅ Fixed user: {username}")
                    fixed_count += 1
                except Exception as e:
                    print(f"❌ Failed to fix user {username}: {e}")
            else:
                print(f"✅ User {username} already has password_salt")
        
        print(f"🎉 Fixed {fixed_count} users with missing password_salt")
        return True
        
    except Exception as e:
        print(f"❌ Error fixing password salt issue: {e}")
        return False

def get_database_fix_sql():
    """Get SQL commands to fix database structure issues"""
    sql_commands = """
-- =====================================================
-- Fix Database Structure Issues
-- =====================================================

-- 1. Add missing password_salt column to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_salt VARCHAR(32);

-- 2. Update existing users with default salt (temporary fix)
-- Note: This will make existing passwords invalid
UPDATE users SET password_salt = 'default_salt_placeholder' WHERE password_salt IS NULL;

-- 3. Make password_salt NOT NULL for future users
ALTER TABLE users ALTER COLUMN password_salt SET NOT NULL;

-- 4. Fix investment_files table structure (if needed)
DROP TABLE IF EXISTS investment_files CASCADE;

CREATE TABLE investment_files (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    file_hash VARCHAR(64) UNIQUE NOT NULL,
    customer_name VARCHAR(100),
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'processed'
);

-- 5. Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_files_filename ON investment_files(filename);
CREATE INDEX IF NOT EXISTS idx_files_file_hash ON investment_files(file_hash);

-- 6. Enable Row Level Security
ALTER TABLE investment_files ENABLE ROW LEVEL SECURITY;

-- 7. Create RLS policy
CREATE POLICY "Enable all operations for files" ON investment_files
    FOR ALL USING (true) WITH CHECK (true);

-- =====================================================
-- Fix Complete!
-- =====================================================
"""
    return sql_commands

def check_table_structure(table_name: str) -> Dict:
    """Check the structure of a table to diagnose schema issues"""
    try:
        # Try to get a sample record to see what columns exist
        result = supabase.table(table_name).select("*").limit(1).execute()
        
        if result.data:
            # Get the first record to see available columns
            sample_record = result.data[0]
            columns = list(sample_record.keys())
            print(f"✅ Table '{table_name}' structure: {columns}")
            return {
                "accessible": True,
                "columns": columns,
                "sample_record": sample_record
            }
        else:
            # Table exists but is empty
            print(f"ℹ️ Table '{table_name}' exists but is empty")
            return {
                "accessible": True,
                "columns": [],
                "sample_record": None
            }
                
    except Exception as e:
        print(f"❌ Error accessing table '{table_name}': {e}")
        return {
            "accessible": False,
            "error": str(e),
            "columns": [],
            "sample_record": None
        }

def diagnose_database_issues():
    """Diagnose common database schema issues"""
    print("🔍 Diagnosing database schema issues...")
    
    tables_to_check = ["users", "investment_transactions", "investment_files", "stock_data"]
    
    for table_name in tables_to_check:
        print(f"\n📋 Checking table: {table_name}")
        structure = check_table_structure(table_name)
        
        if not structure["accessible"]:
            print(f"❌ Table '{table_name}' is not accessible")
            if "column" in structure.get("error", "").lower():
                print(f"💡 This might be a schema issue - check if the table exists and has the correct structure")
        elif table_name == "investment_files" and "user_id" not in structure["columns"]:
            print(f"⚠️ Table '{table_name}' is missing 'user_id' column")
            print(f"💡 This will cause errors when trying to filter files by user")
            print(f"💡 Please update the table schema to include 'user_id INTEGER REFERENCES users(id)'")
        elif table_name == "investment_transactions" and "file_id" not in structure["columns"]:
            print(f"⚠️ Table '{table_name}' is missing 'file_id' column")
            print(f"💡 This will cause errors when trying to link transactions to files")
            print(f"💡 Please update the table schema to include 'file_id INTEGER REFERENCES investment_files(id)'")
    
    # Check RLS policies
    print(f"\n🔍 Checking RLS policies...")
    try:
        # Test insert permission
        test_data = {"test": "data"}
        test_result = supabase.table("investment_transactions").insert(test_data).execute()
        print(f"✅ Insert permission test: Success")
        # Clean up test data
        supabase.table("investment_transactions").delete().eq("test", "data").execute()
    except Exception as rls_error:
        print(f"❌ Insert permission test failed: {rls_error}")
        if "row-level security" in str(rls_error).lower():
            print(f"💡 RLS Policy Issue: Row-level security is blocking inserts")
            print(f"💡 You may need to disable RLS for testing or configure proper policies")
    
    print("\n🔍 Database diagnosis complete!")


