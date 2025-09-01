import os
import socket
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

def build_ipv4_dsn():
    """
    Returns a DSN string that:
    - Forces IPv4 (`hostaddr=...`)
    - Uses TLS (`sslmode=require`)
    - Keeps the original user/password/port/database
    """
    raw = os.getenv('DATABASE_URL')  # Use DATABASE_URL instead of SUPABASE_DB_URL
    
    if not raw:
        raise RuntimeError("DATABASE_URL environment variable not found")
    
    parsed = urlparse(raw)
    
    # Resolve the hostname to a single IPv4 address
    try:
        ipv4 = socket.getaddrinfo(parsed.hostname, None, socket.AF_INET)[0][4][0]
        print(f"✅ Resolved {parsed.hostname} to IPv4: {ipv4}")
    except Exception as exc:
        raise RuntimeError(
            f"Could not resolve IPv4 for {parsed.hostname}: {exc}"
        ) from exc
    
    # Preserve any existing query params, then add sslmode and hostaddr
    qs = dict(parse_qsl(parsed.query))
    qs.update({"sslmode": "require", "hostaddr": ipv4})
    new_query = urlencode(qs, doseq=True)
    dsn = urlunparse(parsed._replace(query=new_query))
    
    return dsn

def get_database_url_with_fallbacks():
    """
    Get database URL with multiple fallback options for Streamlit Cloud
    """
    # Method 1: Try to resolve hostname to IPv4
    try:
        return build_ipv4_dsn()
    except Exception as e:
        print(f"⚠️ Method 1 (DNS resolution) failed: {e}")
    
    # Method 2: Use Supabase Connection Pooler (recommended for Streamlit Cloud)
    try:
        # Connection pooler uses port 6543 instead of 5432
        raw = os.getenv('DATABASE_URL', "postgresql://postgres:wmssupabase123@db.rolcoegikoeblxzqgkix.supabase.co:5432/postgres")
        parsed = urlparse(raw)
        
        # Replace port with connection pooler port
        pooler_url = urlunparse(parsed._replace(
            netloc=parsed.netloc.replace(':5432', ':6543'),
            query="sslmode=require"
        ))
        print("✅ Using Method 2: Supabase Connection Pooler (port 6543)")
        return pooler_url
    except Exception as e:
        print(f"⚠️ Method 2 (connection pooler) failed: {e}")
    
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

if __name__ == "__main__":
    # Test the functions
    try:
        print("Testing database URL resolution...")
        url = get_database_url_with_fallbacks()
        print(f"Final URL: {url}")
    except Exception as e:
        print(f"Error: {e}")
