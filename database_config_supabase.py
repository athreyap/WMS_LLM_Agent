"""
Database configuration and utilities for Supabase integration.
Handles user management, transactions, file records, stock price caching, and PDF documents.
Version: 2.0.1 - Added PDF document storage and enhanced mutual fund/PMS support
Last Updated: 2025-10-10
"""

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

__version__ = "2.0.1"
# Module updated: 2025-10-10 - PDF storage + MF/PMS fixes

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://rolcoegikoeblxzqgkix.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJvbGNvZWdpa29lYmx4enFna2l4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTY1NDM2MjUsImV4cCI6MjA3MjExOTYyNX0.Vwg2hgdKNQGizJiulgTlxXkTLfy-J3vFNkX8gA_6ul4')

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# PDF Documents Storage Functions (defined after supabase client initialization)
def save_pdf_document_supabase(user_id: int, filename: str, file_content: str, extracted_text: str, is_global: bool = False) -> Optional[Dict]:
    """
    Save PDF document to database for AI assistant access
    
    Args:
        user_id: User ID who uploaded the document
        filename: Name of the PDF file
        file_content: Base64 encoded PDF content
        extracted_text: Extracted text from PDF
        is_global: If True, document is available to all users
    
    Returns:
        dict with document record or None
    """
    try:
        document_data = {
            "user_id": user_id if not is_global else None,
            "filename": filename,
            "file_content": file_content,
            "extracted_text": extracted_text,
            "is_global": is_global,
            "uploaded_at": datetime.utcnow().isoformat()
        }
        
        result = supabase.table("pdf_documents").insert(document_data).execute()
        
        if result.data:
            print(f"✅ Saved PDF document: {filename}")
            return result.data[0]
        
        return None
        
    except Exception as e:
        print(f"❌ Error saving PDF document: {e}")
        return None

def get_pdf_documents_supabase(user_id: int, include_global: bool = True) -> List[Dict]:
    """
    Get all PDF documents for a user
    
    Args:
        user_id: User ID
        include_global: If True, also include global documents
    
    Returns:
        List of PDF document records
    """
    try:
        if include_global:
            # Get user's documents + global documents
            result = supabase.table("pdf_documents").select("*").or_(f"user_id.eq.{user_id},is_global.eq.true").execute()
        else:
            # Get only user's documents
            result = supabase.table("pdf_documents").select("*").eq("user_id", user_id).execute()
        
        return result.data if result.data else []
        
    except Exception as e:
        print(f"❌ Error getting PDF documents: {e}")
        return []

def delete_pdf_document_supabase(document_id: int) -> bool:
    """Delete a PDF document"""
    try:
        result = supabase.table("pdf_documents").delete().eq("id", document_id).execute()
        return True if result.data else False
    except Exception as e:
        print(f"❌ Error deleting PDF document: {e}")
        return False

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
        # Convert username to lowercase for case-insensitive storage
        username_lower = username.lower()
        
        # Convert folder path to GitHub path for Streamlit Cloud
        github_folder_path = get_user_folder_path(username_lower, folder_path)
        
        data = {
            "username": username_lower,
            "password_hash": password_hash,
            "password_salt": password_salt,
            "email": email,
            "role": role,
            "folder_path": github_folder_path,
            "created_at": datetime.utcnow().isoformat()
        }
        
        result = supabase.table("users").insert(data).execute()
        
        if result.data:
            print(f"✅ User {username_lower} created successfully")
            return result.data[0]
        else:
            print(f"❌ Failed to create user {username_lower}")
            return None
            
    except Exception as e:
        print(f"❌ Error creating user {username}: {e}")
        return None

def get_user_by_username_supabase(username: str) -> Optional[Dict]:
    """Get user by username using Supabase client (case-insensitive)"""
    try:
        # Convert username to lowercase for case-insensitive lookup
        username_lower = username.lower()
        
        result = supabase.table("users").select("*").eq("username", username_lower).execute()
        
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
        import math
        bulk_data = []
        for _, row in df.iterrows():
            # Safely convert quantity to float, handling inf/nan
            quantity = row.get('quantity', 0)
            if pd.notna(quantity):
                try:
                    quantity_float = float(quantity)
                    # Check for inf/-inf/nan using math.isfinite
                    if not math.isfinite(quantity_float):
                        print(f"⚠️ Invalid quantity value {quantity_float} for {row.get('ticker', 'unknown')}, using 0")
                        quantity_float = 0
                except (ValueError, OverflowError) as e:
                    print(f"⚠️ Could not convert quantity {quantity} for {row.get('ticker', 'unknown')}: {e}, using 0")
                    quantity_float = 0
            else:
                quantity_float = 0
            
            # Safely convert price to float, handling inf/nan
            price = row.get('price')
            if pd.notna(price):
                try:
                    price_float = float(price)
                    # Check for inf/-inf/nan using math.isfinite
                    if not math.isfinite(price_float):
                        print(f"⚠️ Invalid price value {price_float} for {row.get('ticker', 'unknown')}, using None")
                        price_float = None
                except (ValueError, OverflowError) as e:
                    print(f"⚠️ Could not convert price {price} for {row.get('ticker', 'unknown')}: {e}, using None")
                    price_float = None
            else:
                price_float = None
            
            # Safely convert date to string
            date_value = row.get('date', '')
            if pd.notna(date_value):
                try:
                    if isinstance(date_value, pd.Timestamp):
                        date_str = date_value.strftime('%Y-%m-%d')
                    else:
                        date_str = str(date_value)
                except Exception as e:
                    print(f"⚠️ Could not convert date {date_value} for {row.get('ticker', 'unknown')}: {e}, using empty string")
                    date_str = ''
            else:
                date_str = ''
            
            # Safely convert string fields, handling NaN
            def safe_str(value, default=''):
                if pd.notna(value):
                    return str(value)
                return default
            
            transaction_data = {
                "user_id": user_id,
                "file_id": file_id,
                "stock_name": safe_str(row.get('stock_name', '')),
                "ticker": safe_str(row.get('ticker', '')),
                "quantity": quantity_float,
                "price": price_float,
                "transaction_type": safe_str(row.get('transaction_type', '')),
                "date": date_str,
                "channel": safe_str(row.get('channel', '')),
                "created_at": datetime.utcnow().isoformat()
            }
            bulk_data.append(transaction_data)
        
        # Validate all data before insert
        print(f"🔍 Validating {len(bulk_data)} transactions before insert...")
        import json
        for idx, transaction in enumerate(bulk_data):
            try:
                # Try to serialize to JSON to catch any issues
                json.dumps(transaction)
            except (TypeError, ValueError, OverflowError) as json_error:
                print(f"❌ Transaction {idx} failed JSON validation: {json_error}")
                print(f"❌ Problematic transaction: {transaction}")
                
                # Check each field individually to identify the problem
                for field_name, field_value in transaction.items():
                    try:
                        json.dumps({field_name: field_value})
                    except Exception as field_error:
                        print(f"❌ Problem field: {field_name} = {field_value} (type: {type(field_value).__name__})")
                        print(f"❌ Field error: {field_error}")
                
                raise ValueError(f"Invalid data in transaction {idx}: {json_error}")
        
        print(f"✅ All transactions passed validation")
        
        # Insert all transactions in bulk
        print(f"🔄 Inserting {len(bulk_data)} transactions into database...")
        
        # Debug: Print first transaction to verify data structure
        if bulk_data:
            print(f"📊 Sample transaction data: {bulk_data[0]}")
        
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
        print(f"❌ Error type: {type(e).__name__}")
        print(f"❌ Full error details: {repr(e)}")
        
        # Print the problematic data for debugging
        if bulk_data:
            print(f"📊 Number of transactions attempted: {len(bulk_data)}")
            print(f"📊 First transaction: {bulk_data[0]}")
            if len(bulk_data) > 1:
                print(f"📊 Last transaction: {bulk_data[-1]}")
        
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
        elif "json" in error_str or "float" in error_str:
            print(f"💡 Data Type Error: Invalid float/JSON values detected")
            print(f"💡 Check for infinity, NaN, or extremely large numbers in the data")
        
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
        
        CREATE TABLE IF NOT EXISTS stock_prices (
            id SERIAL PRIMARY KEY,
            ticker VARCHAR(20) NOT NULL,
            price_date DATE NOT NULL,
            price DECIMAL(10,2) NOT NULL,
            price_source VARCHAR(20) DEFAULT 'yfinance',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ticker, price_date)
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

# Stock Prices Functions (unified for both weekly and monthly data)
def save_stock_price_supabase(ticker: str, price_date: str, price: float, price_source: str = 'yfinance') -> bool:
    """Save stock price to database using Supabase"""
    try:
        print(f"💾 Attempting to save {ticker} price for {price_date} (₹{price}) to stock_prices table...")

        # Try the new unified stock_prices table first
        result = supabase.table('stock_prices').upsert({
            'ticker': ticker,
            'price_date': price_date,
            'price': price,
            'price_source': price_source
        }).execute()

        # Verify the save was successful
        if result.data and len(result.data) > 0:
            print(f"✅ Successfully saved {ticker} price for {price_date} to stock_prices table")
            print(f"   Saved data: {result.data[0]}")
            return True
        else:
            print(f"⚠️ Save returned no data for {ticker} on {price_date}")
            print(f"   Result object: {result}")
            print(f"   Result.data: {result.data}")
            print(f"   Result.data type: {type(result.data)}")
            print(f"   Result.data length: {len(result.data) if result.data else 'None'}")
            return False

    except Exception as e:
        error_msg = str(e)
        print(f"❌ Exception in stock_prices save for {ticker} on {price_date}: {error_msg}")

        # If stock_prices table doesn't exist, try using historical_prices table as fallback
        # Check for PGRST205 error code (table not found) or any error mentioning stock_prices
        if ("pgrst205" in error_msg.lower() or "stock_pric" in error_msg.lower()):
            print(f"⚠️ stock_prices table not found, trying historical_prices as fallback...")
            try:
                # Map to historical_prices table structure
                result = supabase.table('historical_prices').insert({
                    'ticker': ticker,
                    'transaction_date': price_date,
                    'historical_price': price,
                    'current_price': price,
                    'price_source': price_source,
                    'transaction_id': None,  # Not applicable for cached prices
                    'file_id': None  # Not applicable for cached prices
                }).execute()

                if result.data and len(result.data) > 0:
                    print(f"✅ Saved to historical_prices table as fallback")
                    print(f"   Fallback data: {result.data[0]}")
                    return True
                else:
                    print(f"❌ Fallback save returned no data for {ticker}")
                    return False

            except Exception as fallback_error:
                print(f"❌ Error saving to historical_prices fallback for {ticker}: {fallback_error}")
                return False
        else:
            print(f"❌ Error saving stock price for {ticker} on {price_date}: {e}")
            print(f"   Error type: {type(e).__name__}")
            return False

def get_stock_price_supabase(ticker: str, price_date: str) -> Optional[float]:
    """Get stock price from database using Supabase"""
    try:
        # Try the new unified stock_prices table first
        result = supabase.table('stock_prices').select('price').eq('ticker', ticker).eq('price_date', price_date).execute()
        
        if result.data:
            return float(result.data[0]['price'])
        return None
        
    except Exception as e:
        error_msg = str(e)
        
        # If stock_prices table doesn't exist, try using historical_prices table as fallback
        # Check for PGRST205 error code (table not found) or any error mentioning stock_prices
        if ("pgrst205" in error_msg.lower() or "stock_pric" in error_msg.lower()):
            try:
                # Map to historical_prices table structure
                result = supabase.table('historical_prices').select('historical_price').eq('ticker', ticker).eq('transaction_date', price_date).execute()
                
                if result.data:
                    return float(result.data[0]['historical_price'])
                return None
                
            except Exception as fallback_error:
                print(f"❌ Error getting from historical_prices fallback: {fallback_error}")
                return None
        else:
            print(f"❌ Error getting stock price for {ticker} on {price_date}: {e}")
            return None

def get_stock_prices_bulk_supabase(tickers: List[str], price_date: str) -> Dict[str, float]:
    """
    Get stock prices for multiple tickers on a specific date using Supabase (BULK QUERY)
    
    Args:
        tickers: List of ticker symbols
        price_date: Date in YYYY-MM-DD format
    
    Returns:
        Dictionary mapping ticker to price {ticker: price}
    """
    try:
        if not tickers:
            return {}
        
        # Try the new unified stock_prices table first
        result = supabase.table('stock_prices').select('ticker,price').in_('ticker', tickers).eq('price_date', price_date).execute()
        
        if result.data:
            # Convert to dictionary for O(1) lookup
            return {row['ticker']: float(row['price']) for row in result.data}
        return {}
        
    except Exception as e:
        error_msg = str(e)
        
        # If stock_prices table doesn't exist, try using historical_prices table as fallback
        if ("pgrst205" in error_msg.lower() or "stock_pric" in error_msg.lower()):
            try:
                result = supabase.table('historical_prices').select('ticker,historical_price').in_('ticker', tickers).eq('transaction_date', price_date).execute()
                
                if result.data:
                    return {row['ticker']: float(row['historical_price']) for row in result.data}
                return {}
                
            except Exception as fallback_error:
                print(f"❌ Error getting bulk prices from historical_prices fallback: {fallback_error}")
                return {}
        else:
            print(f"❌ Error getting bulk stock prices for {price_date}: {e}")
            return {}

def get_stock_prices_range_supabase(ticker: str, start_date: str, end_date: str) -> List[Dict]:
    """Get stock prices for a date range using Supabase"""
    try:
        # Try the new unified stock_prices table first
        result = supabase.table('stock_prices').select('*').eq('ticker', ticker).gte('price_date', start_date).lte('price_date', end_date).order('price_date').execute()
        
        return result.data if result.data else []
        
    except Exception as e:
        error_msg = str(e)
        
        # If stock_prices table doesn't exist, try using historical_prices table as fallback
        # Check for PGRST205 error code (table not found) or any error mentioning stock_prices
        if ("pgrst205" in error_msg.lower() or "stock_pric" in error_msg.lower()):
            try:
                # Map to historical_prices table structure
                result = supabase.table('historical_prices').select('ticker,transaction_date,historical_price,price_source').eq('ticker', ticker).gte('transaction_date', start_date).lte('transaction_date', end_date).order('transaction_date').execute()
                
                # Map the results to match the expected structure
                if result.data:
                    mapped_data = []
                    for row in result.data:
                        mapped_data.append({
                            'ticker': row['ticker'],
                            'price_date': row['transaction_date'],
                            'price': row['historical_price'],
                            'price_source': row['price_source']
                        })
                    return mapped_data
                
                return []
                
            except Exception as fallback_error:
                print(f"❌ Error getting range from historical_prices fallback: {fallback_error}")
                return []
        else:
            print(f"❌ Error getting stock prices range for {ticker}: {e}")
            return []

def get_all_stock_prices_supabase() -> List[Dict]:
    """Get all stock prices using Supabase"""
    try:
        # Try the new unified stock_prices table first
        result = supabase.table('stock_prices').select('*').order('ticker', 'price_date').execute()
        
        return result.data if result.data else []
        
    except Exception as e:
        error_msg = str(e)
        
        # If stock_prices table doesn't exist, try using historical_prices table as fallback
        # Check for PGRST205 error code (table not found) or any error mentioning stock_prices
        if ("pgrst205" in error_msg.lower() or "stock_pric" in error_msg.lower()):
            try:
                # Map to historical_prices table structure
                result = supabase.table('historical_prices').select('ticker,transaction_date,historical_price,price_source').order('ticker', 'transaction_date').execute()
                
                # Map the results to match the expected structure
                if result.data:
                    mapped_data = []
                    for row in result.data:
                        mapped_data.append({
                            'ticker': row['ticker'],
                            'price_date': row['transaction_date'],
                            'price': row['historical_price'],
                            'price_source': row['price_source']
                        })
                    return mapped_data
                
                return []
                
            except Exception as fallback_error:
                print(f"❌ Error getting all from historical_prices fallback: {fallback_error}")
                return []
        else:
            print(f"❌ Error getting all stock prices: {e}")
            return []

def delete_old_stock_prices_supabase(days_old: int = 730) -> bool:
    """Delete stock prices older than specified days using Supabase (default: 2 years)"""
    try:
        from datetime import datetime, timedelta
        cutoff_date = (datetime.now() - timedelta(days=days_old)).strftime('%Y-%m-%d')
        
        result = supabase.table('stock_prices').delete().lt('price_date', cutoff_date).execute()
        
        return True
        
    except Exception as e:
        print(f"❌ Error deleting old stock prices: {e}")
        return False

# Backward compatibility aliases
save_monthly_stock_price_supabase = save_stock_price_supabase
get_monthly_stock_price_supabase = get_stock_price_supabase
get_monthly_stock_prices_range_supabase = get_stock_prices_range_supabase
get_all_monthly_stock_prices_supabase = get_all_stock_prices_supabase
save_weekly_stock_price_supabase = save_stock_price_supabase
get_weekly_stock_price_supabase = get_stock_price_supabase
get_weekly_stock_prices_range_supabase = get_stock_prices_range_supabase


# Optimized JOIN functions for better performance
def get_portfolio_data_with_prices(user_id: int) -> List[Dict]:
    """
    Get complete portfolio data with JOINs to fetch all related data in one query.
    This joins:
    - investment_transactions (user's transactions)
    - stock_data (ticker metadata: sector, market cap)
    - stock_prices (current/latest prices)
    
    Returns transactions with enriched data from related tables.
    """
    try:
        # Use Supabase to fetch transactions with related data
        # Note: Supabase doesn't support complex JOINs in the traditional SQL sense,
        # but we can use select with foreign key relationships or do multiple queries
        # and join in Python for better performance than N+1 queries
        
        # Step 1: Get all transactions for user
        transactions = supabase.table('investment_transactions')\
            .select('*')\
            .eq('user_id', user_id)\
            .execute()
        
        if not transactions.data:
            return []
        
        # Step 2: Get unique tickers from transactions
        unique_tickers = list(set(t['ticker'] for t in transactions.data if t.get('ticker')))
        
        if not unique_tickers:
            return transactions.data
        
        # Step 3: Bulk fetch stock_data for all tickers (metadata like sector, market_cap)
        stock_data_map = {}
        try:
            stock_data = supabase.table('stock_data')\
                .select('ticker, sector, market_cap, company_name')\
                .in_('ticker', unique_tickers)\
                .execute()
            
            if stock_data.data:
                stock_data_map = {s['ticker']: s for s in stock_data.data}
                print(f"✅ Fetched metadata for {len(stock_data_map)} tickers via JOIN")
        except Exception as e:
            print(f"⚠️ Could not fetch stock_data: {e}")
        
        # Step 4: Bulk fetch latest stock prices for all tickers
        stock_prices_map = {}
        try:
            from datetime import datetime
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Get latest prices (you might want to get the most recent available)
            stock_prices = supabase.table('stock_prices')\
                .select('ticker, price, price_date')\
                .in_('ticker', unique_tickers)\
                .lte('price_date', today)\
                .order('price_date', desc=True)\
                .execute()
            
            if stock_prices.data:
                # Keep only the latest price for each ticker
                for price_data in stock_prices.data:
                    ticker = price_data['ticker']
                    if ticker not in stock_prices_map:
                        stock_prices_map[ticker] = price_data
                print(f"✅ Fetched prices for {len(stock_prices_map)} tickers via JOIN")
        except Exception as e:
            print(f"⚠️ Could not fetch stock_prices: {e}")
        
        # Step 5: Enrich transactions with joined data
        enriched_transactions = []
        for txn in transactions.data:
            ticker = txn.get('ticker')
            
            # Add stock metadata
            if ticker in stock_data_map:
                txn['stock_sector'] = stock_data_map[ticker].get('sector')
                txn['stock_market_cap'] = stock_data_map[ticker].get('market_cap')
                txn['stock_company_name'] = stock_data_map[ticker].get('company_name')
            
            # Add current price
            if ticker in stock_prices_map:
                txn['current_price'] = stock_prices_map[ticker].get('price')
                txn['current_price_date'] = stock_prices_map[ticker].get('price_date')
            
            enriched_transactions.append(txn)
        
        print(f"✅ Enriched {len(enriched_transactions)} transactions with JOIN data")
        return enriched_transactions
        
    except Exception as e:
        print(f"❌ Error in get_portfolio_data_with_prices: {e}")
        # Fallback to basic transactions
        try:
            return supabase.table('investment_transactions')\
                .select('*')\
                .eq('user_id', user_id)\
                .execute().data or []
        except:
            return []


def get_transactions_with_all_data(user_id: int = None) -> List[Dict]:
    """
    Get transactions with all related data using optimized queries.
    Uses bulk fetching instead of N+1 queries for better performance.
    
    If user_id is None, fetches for all users (admin view).
    """
    try:
        # Fetch transactions
        query = supabase.table('investment_transactions').select('*')
        if user_id is not None:
            query = query.eq('user_id', user_id)
        
        transactions = query.execute()
        
        if not transactions.data:
            return []
        
        # Get unique tickers
        unique_tickers = list(set(t['ticker'] for t in transactions.data if t.get('ticker')))
        
        if not unique_tickers:
            return transactions.data
        
        # Bulk fetch related data
        stock_data_map = {}
        stock_prices_map = {}
        
        # Fetch stock metadata
        try:
            stock_data = supabase.table('stock_data')\
                .select('*')\
                .in_('ticker', unique_tickers)\
                .execute()
            
            if stock_data.data:
                stock_data_map = {s['ticker']: s for s in stock_data.data}
        except Exception as e:
            print(f"⚠️ Could not bulk fetch stock_data: {e}")
        
        # Fetch latest prices
        try:
            from datetime import datetime
            today = datetime.now().strftime('%Y-%m-%d')
            
            stock_prices = supabase.table('stock_prices')\
                .select('ticker, price, price_date')\
                .in_('ticker', unique_tickers)\
                .lte('price_date', today)\
                .order('price_date', desc=True)\
                .limit(len(unique_tickers))\
                .execute()
            
            if stock_prices.data:
                for price_data in stock_prices.data:
                    ticker = price_data['ticker']
                    if ticker not in stock_prices_map:
                        stock_prices_map[ticker] = price_data
        except Exception as e:
            print(f"⚠️ Could not bulk fetch stock_prices: {e}")
        
        # Enrich transactions
        for txn in transactions.data:
            ticker = txn.get('ticker')
            
            if ticker in stock_data_map:
                txn.update({
                    'sector': stock_data_map[ticker].get('sector') or txn.get('sector'),
                    'market_cap': stock_data_map[ticker].get('market_cap'),
                    'company_name': stock_data_map[ticker].get('company_name')
                })
            
            if ticker in stock_prices_map:
                txn.update({
                    'latest_price': stock_prices_map[ticker].get('price'),
                    'latest_price_date': stock_prices_map[ticker].get('price_date')
                })
        
        return transactions.data
        
    except Exception as e:
        print(f"❌ Error in get_transactions_with_all_data: {e}")
        return []


def get_complete_portfolio_with_calculations(user_id: int) -> Dict:
    """
    Get complete portfolio data with all JOINs and calculations done in one function.
    This is the optimized version that:
    1. Gets user transactions
    2. JOINs with historical_prices based on ticker AND transaction date
    3. JOINs with stock_data for metadata
    4. JOINs with stock_prices for current/live prices
    5. Performs all P&L calculations
    
    Returns a complete portfolio summary with all calculations done.
    """
    import pandas as pd
    from datetime import datetime
    
    try:
        print(f"📊 Fetching complete portfolio for user {user_id}...")
        
        # Step 1: Get all transactions for user
        transactions = supabase.table('investment_transactions')\
            .select('*')\
            .eq('user_id', user_id)\
            .order('date', desc=False)\
            .execute()
        
        if not transactions.data:
            print("❌ No transactions found")
            return {'transactions': [], 'summary': {}, 'holdings': []}
        
        print(f"✅ Found {len(transactions.data)} transactions")
        
        # Convert to DataFrame for easier processing
        df = pd.DataFrame(transactions.data)
        df['date'] = pd.to_datetime(df['date'])
        
        # Get unique tickers
        unique_tickers = df['ticker'].unique().tolist()
        print(f"✅ Found {len(unique_tickers)} unique tickers")
        
        # Step 2: Bulk fetch historical prices for all transaction dates and tickers
        historical_prices_map = {}  # Key: (ticker, date)
        try:
            # Get all unique (ticker, date) combinations
            ticker_dates = df[['ticker', 'date']].drop_duplicates()
            
            for _, row in ticker_dates.iterrows():
                ticker = row['ticker']
                date_str = row['date'].strftime('%Y-%m-%d')
                
                # Try stock_prices first
                try:
                    price_result = supabase.table('stock_prices')\
                        .select('price')\
                        .eq('ticker', ticker)\
                        .eq('price_date', date_str)\
                        .execute()
                    
                    if price_result.data and len(price_result.data) > 0:
                        historical_prices_map[(ticker, date_str)] = price_result.data[0]['price']
                except:
                    pass
                
                # Fallback to historical_prices if not found
                if (ticker, date_str) not in historical_prices_map:
                    try:
                        hist_result = supabase.table('historical_prices')\
                            .select('historical_price')\
                            .eq('ticker', ticker)\
                            .eq('transaction_date', date_str)\
                            .execute()
                        
                        if hist_result.data and len(hist_result.data) > 0:
                            historical_prices_map[(ticker, date_str)] = hist_result.data[0]['historical_price']
                    except:
                        pass
            
            print(f"✅ Fetched historical prices for {len(historical_prices_map)} transaction dates")
        except Exception as e:
            print(f"⚠️ Error fetching historical prices: {e}")
        
        # Step 3: Bulk fetch current/live prices for all tickers
        current_prices_map = {}
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            
            current_prices = supabase.table('stock_prices')\
                .select('ticker, price, price_date')\
                .in_('ticker', unique_tickers)\
                .lte('price_date', today)\
                .order('price_date', desc=True)\
                .execute()
            
            if current_prices.data:
                for price_data in current_prices.data:
                    ticker = price_data['ticker']
                    if ticker not in current_prices_map:
                        current_prices_map[ticker] = {
                            'price': price_data['price'],
                            'date': price_data['price_date']
                        }
            
            print(f"✅ Fetched current prices for {len(current_prices_map)} tickers")
        except Exception as e:
            print(f"⚠️ Error fetching current prices: {e}")
        
        # Step 4: Bulk fetch stock metadata
        stock_metadata_map = {}
        try:
            stock_data = supabase.table('stock_data')\
                .select('ticker, sector, market_cap, company_name')\
                .in_('ticker', unique_tickers)\
                .execute()
            
            if stock_data.data:
                stock_metadata_map = {s['ticker']: s for s in stock_data.data}
            
            print(f"✅ Fetched metadata for {len(stock_metadata_map)} tickers")
        except Exception as e:
            print(f"⚠️ Error fetching stock metadata: {e}")
        
        # Step 5: Enrich transactions with JOINed data
        for idx, row in df.iterrows():
            ticker = row['ticker']
            date_str = row['date'].strftime('%Y-%m-%d')
            
            # Add historical price from JOIN
            hist_key = (ticker, date_str)
            if hist_key in historical_prices_map:
                df.at[idx, 'historical_price'] = historical_prices_map[hist_key]
            
            # Add current price from JOIN
            if ticker in current_prices_map:
                df.at[idx, 'current_price'] = current_prices_map[ticker]['price']
                df.at[idx, 'current_price_date'] = current_prices_map[ticker]['date']
            
            # Add metadata from JOIN
            if ticker in stock_metadata_map:
                df.at[idx, 'sector'] = stock_metadata_map[ticker].get('sector') or row.get('sector')
                df.at[idx, 'market_cap'] = stock_metadata_map[ticker].get('market_cap')
                df.at[idx, 'company_name'] = stock_metadata_map[ticker].get('company_name')
        
        # Step 6: Calculate holdings (aggregate by ticker)
        holdings = []
        
        for ticker in unique_tickers:
            ticker_df = df[df['ticker'] == ticker].copy()
            
            # Calculate net quantity (buys - sells)
            buys = ticker_df[ticker_df['transaction_type'] == 'buy']
            sells = ticker_df[ticker_df['transaction_type'] == 'sell']
            
            total_quantity = buys['quantity'].sum() - sells['quantity'].sum()
            
            if total_quantity <= 0:
                continue  # Skip fully sold positions
            
            # Calculate average purchase price (weighted)
            total_invested = (buys['quantity'] * buys['price']).sum()
            total_buy_quantity = buys['quantity'].sum()
            avg_price = total_invested / total_buy_quantity if total_buy_quantity > 0 else 0
            
            # Get current price
            current_price = current_prices_map.get(ticker, {}).get('price', avg_price)
            
            # Calculate P&L
            invested_amount = total_quantity * avg_price
            current_value = total_quantity * current_price
            pnl = current_value - invested_amount
            pnl_percent = (pnl / invested_amount * 100) if invested_amount > 0 else 0
            
            # Get metadata
            metadata = stock_metadata_map.get(ticker, {})
            
            holdings.append({
                'ticker': ticker,
                'stock_name': metadata.get('company_name', ticker),
                'quantity': total_quantity,
                'avg_price': avg_price,
                'current_price': current_price,
                'invested_amount': invested_amount,
                'current_value': current_value,
                'pnl': pnl,
                'pnl_percent': pnl_percent,
                'sector': metadata.get('sector'),
                'market_cap': metadata.get('market_cap'),
                'first_buy_date': buys['date'].min(),
                'last_transaction_date': ticker_df['date'].max()
            })
        
        # Step 7: Calculate portfolio summary
        total_invested = sum(h['invested_amount'] for h in holdings)
        total_current_value = sum(h['current_value'] for h in holdings)
        total_pnl = total_current_value - total_invested
        total_pnl_percent = (total_pnl / total_invested * 100) if total_invested > 0 else 0
        
        summary = {
            'total_invested': total_invested,
            'total_current_value': total_current_value,
            'total_pnl': total_pnl,
            'total_pnl_percent': total_pnl_percent,
            'total_holdings': len(holdings),
            'total_transactions': len(df),
            'first_transaction_date': df['date'].min(),
            'last_transaction_date': df['date'].max()
        }
        
        print(f"✅ Portfolio calculations complete!")
        print(f"   Total Invested: ₹{total_invested:,.2f}")
        print(f"   Current Value: ₹{total_current_value:,.2f}")
        print(f"   P&L: ₹{total_pnl:,.2f} ({total_pnl_percent:.2f}%)")
        
        return {
            'transactions': df.to_dict('records'),
            'holdings': holdings,
            'summary': summary
        }
        
    except Exception as e:
        print(f"❌ Error in get_complete_portfolio_with_calculations: {e}")
        import traceback
        traceback.print_exc()
        return {'transactions': [], 'holdings': [], 'summary': {}}


