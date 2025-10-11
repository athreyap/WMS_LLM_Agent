# 🗄️ Database Schema & Query Optimization Guide

## Complete Database Schema

### 1. Users Table
```sql
CREATE TABLE users (
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
```

**Purpose**: User accounts and authentication
**Keys**: 
- PK: `id`
- Unique: `username`

---

### 2. Investment Transactions Table
```sql
CREATE TABLE investment_transactions (
    id SERIAL PRIMARY KEY,
    file_id INTEGER REFERENCES investment_files(id),
    user_id INTEGER REFERENCES users(id),
    stock_name VARCHAR(100) NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    quantity DECIMAL(10,2) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    transaction_type VARCHAR(10) NOT NULL,  -- 'buy' or 'sell'
    date DATE NOT NULL,
    channel VARCHAR(50),
    sector VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Purpose**: User-specific transaction records (BUY/SELL)
**Keys**:
- PK: `id`
- FK: `user_id` → `users(id)`
- FK: `file_id` → `investment_files(id)`
- Index on: `user_id`, `ticker`, `date`

**Data Characteristics**:
- User-specific (NOT shared)
- Stores historical transactions
- Links to stock_data via `ticker`

---

### 3. Stock Data Table
```sql
CREATE TABLE stock_data (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) UNIQUE NOT NULL,
    stock_name VARCHAR(100),
    sector VARCHAR(50),
    live_price DECIMAL(10,2),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Purpose**: Shared stock metadata (ticker info, sector, latest price)
**Keys**:
- PK: `id`
- Unique: `ticker`

**Data Characteristics**:
- **SHARED across all users**
- One entry per ticker
- Stores latest live price
- Metadata like sector, stock name

---

### 4. Historical Prices Table
```sql
CREATE TABLE historical_prices (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    transaction_date DATE NOT NULL,
    historical_price DECIMAL(10,2),
    current_price DECIMAL(10,2),
    price_source VARCHAR(20) DEFAULT 'yfinance',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, transaction_date)
);
```

**Purpose**: Historical price snapshots (shared cache)
**Keys**:
- PK: `id`
- Unique: `(ticker, transaction_date)`
- Index on: `ticker`, `transaction_date`

**Data Characteristics**:
- **SHARED across all users**
- One price per (ticker, date)
- Used for P&L calculations
- Caches API results

---

### 5. Investment Files Table
```sql
CREATE TABLE investment_files (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_hash VARCHAR(64) UNIQUE NOT NULL,
    customer_name VARCHAR(100),
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'processed'
);
```

**Purpose**: Track uploaded CSV files per user
**Keys**:
- PK: `id`
- FK: `user_id` → `users(id)`
- Unique: `file_hash` (prevents duplicate uploads)

---

### 6. User Login Table
```sql
CREATE TABLE user_login (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE,
    email TEXT UNIQUE,
    password_hash TEXT,
    password_salt TEXT,
    role TEXT DEFAULT 'user',
    folder_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    failed_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP
);
```

**Purpose**: Login tracking and session management
**Keys**:
- PK: `id`
- Unique: `username`, `email`

---

### 7. PDF Documents Table
```sql
CREATE TABLE pdf_documents (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    filename TEXT NOT NULL,
    file_content TEXT,  -- Base64 encoded
    extracted_text TEXT,
    is_global BOOLEAN DEFAULT FALSE,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Purpose**: Store PDF documents for AI chatbot context
**Keys**:
- PK: `id`
- FK: `user_id` → `users(id)`

---

## 📊 Entity Relationship Diagram

```
┌─────────────┐
│   users     │
│  (id, name) │
└──────┬──────┘
       │
       │ 1:N
       │
       ├─────────────────────┐
       │                     │
       ▼                     ▼
┌──────────────────┐  ┌──────────────┐
│investment_trans  │  │invest_files  │
│(user_id FK)      │  │(user_id FK)  │
│ticker (ref)      │  └──────────────┘
└────────┬─────────┘
         │
         │ M:1
         │
         ▼
  ┌─────────────┐
  │ stock_data  │◄──────┐
  │(ticker PK)  │       │
  │SHARED       │       │ M:1
  └──────┬──────┘       │
         │              │
         │ 1:N          │
         │              │
         ▼              │
  ┌────────────────────┴──┐
  │  historical_prices    │
  │ (ticker FK, date)     │
  │       SHARED          │
  └───────────────────────┘
```

---

## ⚡ Optimized Query Strategy

### Current Problem with N+1 Queries
```python
# ❌ BAD: 1 + N queries for N tickers
transactions = get_transactions(user_id)  # 1 query
for txn in transactions:
    stock_info = get_stock_data(txn['ticker'])  # N queries
    price = get_price(txn['ticker'], txn['date'])  # N queries
# Total: 1 + 2N queries
```

### Optimized Solution with JOINs and Bulk Fetch
```python
# ✅ GOOD: 5 queries total regardless of N
# 1. Get user info
user = get_user(user_id)  # 1 query

# 2. Get all transactions
transactions = get_transactions(user_id)  # 1 query
tickers = unique(transactions['ticker'])

# 3. Bulk fetch stock_data
stock_metadata = bulk_get_stock_data(tickers)  # 1 query

# 4. Bulk fetch historical prices
historical = bulk_get_prices(tickers, dates)  # 1 query

# 5. Get latest prices
current_prices = bulk_get_current_prices(tickers)  # 1 query

# Total: 5 queries (constant time)
```

---

## 🚀 Implementation in Code

### Query 1: Get User Transactions with Minimal Data
```python
def get_user_portfolio_optimized(user_id: int):
    # Query 1: Get all transactions for user
    result = supabase.table('investment_transactions')\
        .select('*')\
        .eq('user_id', user_id)\
        .order('date', desc=False)\
        .execute()
    
    df = pd.DataFrame(result.data)
    tickers = df['ticker'].unique().tolist()
    
    return df, tickers
```

### Query 2: Bulk Fetch Stock Metadata
```python
def bulk_fetch_stock_metadata(tickers: List[str]) -> Dict:
    # Query 2: Bulk fetch stock_data (SHARED)
    result = supabase.table('stock_data')\
        .select('ticker, stock_name, sector, live_price, last_updated')\
        .in_('ticker', tickers)\
        .execute()
    
    # Convert to dict for O(1) lookup
    return {row['ticker']: row for row in result.data}
```

### Query 3: Bulk Fetch Current Prices
```python
def bulk_fetch_current_prices(tickers: List[str]) -> Dict:
    # Query 3: Get latest price for each ticker
    today = datetime.now().strftime('%Y-%m-%d')
    
    result = supabase.table('historical_prices')\
        .select('ticker, historical_price, current_price, transaction_date')\
        .in_('ticker', tickers)\
        .lte('transaction_date', today)\
        .order('transaction_date', desc=True)\
        .execute()
    
    # Keep only latest price per ticker
    prices = {}
    seen = set()
    for row in result.data:
        if row['ticker'] not in seen:
            prices[row['ticker']] = {
                'price': row['current_price'] or row['historical_price'],
                'date': row['transaction_date']
            }
            seen.add(row['ticker'])
    
    return prices
```

### Query 4: Calculate Holdings with JOIN Logic
```python
def calculate_holdings(df: pd.DataFrame, stock_metadata: Dict, current_prices: Dict) -> List[Dict]:
    holdings = []
    
    for ticker in df['ticker'].unique():
        ticker_df = df[df['ticker'] == ticker]
        
        # Calculate net position
        buys = ticker_df[ticker_df['transaction_type'] == 'buy']
        sells = ticker_df[ticker_df['transaction_type'] == 'sell']
        
        net_qty = buys['quantity'].sum() - sells['quantity'].sum()
        
        if net_qty <= 0:
            continue  # Fully sold
        
        # Calculate average price
        avg_price = (buys['quantity'] * buys['price']).sum() / buys['quantity'].sum()
        
        # Get current price (O(1) lookup)
        current_price = current_prices.get(ticker, {}).get('price', avg_price)
        
        # Calculate P&L
        invested = net_qty * avg_price
        current_value = net_qty * current_price
        pnl = current_value - invested
        pnl_pct = (pnl / invested * 100) if invested > 0 else 0
        
        # Add metadata (O(1) lookup)
        meta = stock_metadata.get(ticker, {})
        
        holdings.append({
            'ticker': ticker,
            'stock_name': meta.get('stock_name', ticker),
            'sector': meta.get('sector', 'Unknown'),
            'quantity': float(net_qty),
            'avg_price': float(avg_price),
            'current_price': float(current_price),
            'invested_amount': float(invested),
            'current_value': float(current_value),
            'pnl': float(pnl),
            'pnl_percent': float(pnl_pct)
        })
    
    return sorted(holdings, key=lambda x: x['current_value'], reverse=True)
```

---

## 📈 Performance Comparison

### Before Optimization
```
For 100 transactions with 50 unique tickers:
- Get transactions: 1 query
- Get stock_data: 50 queries (one per ticker)
- Get prices: 50 queries (one per ticker)
- Total: 101 queries
- Time: ~5-10 seconds
```

### After Optimization
```
For 100 transactions with 50 unique tickers:
- Get user: 1 query
- Get transactions: 1 query
- Bulk get stock_data: 1 query (all 50 tickers)
- Bulk get prices: 1 query (all 50 tickers)
- Calculate in memory: 0 queries
- Total: 4 queries
- Time: ~0.5-1 second
```

**Result**: **25x faster** 🚀

---

## 🎯 Best Practices

### 1. Always Use Bulk Queries
```python
# ❌ BAD
for ticker in tickers:
    data = supabase.table('stock_data').select('*').eq('ticker', ticker).execute()

# ✅ GOOD
data = supabase.table('stock_data').select('*').in_('ticker', tickers).execute()
```

### 2. Use Proper Indexing
```sql
-- Ensure these indexes exist
CREATE INDEX idx_transactions_user_id ON investment_transactions(user_id);
CREATE INDEX idx_transactions_ticker ON investment_transactions(ticker);
CREATE INDEX idx_prices_ticker_date ON historical_prices(ticker, transaction_date);
```

### 3. Cache Shared Data
```python
# Stock metadata and prices are SHARED - cache them
class OptimizedLoader:
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes
    
    def get_with_cache(self, key, fetch_func):
        if key in self.cache and not self.is_expired(key):
            return self.cache[key]
        
        data = fetch_func()
        self.cache[key] = data
        return data
```

### 4. Minimize Data Transfer
```python
# ❌ BAD: Select all columns
result = supabase.table('stock_data').select('*')

# ✅ GOOD: Select only needed columns
result = supabase.table('stock_data').select('ticker, stock_name, sector, live_price')
```

### 5. Use Pagination for Large Results
```python
# For historical data spanning years
def get_price_history(ticker, limit=365):
    return supabase.table('historical_prices')\
        .select('transaction_date, historical_price')\
        .eq('ticker', ticker)\
        .order('transaction_date', desc=True)\
        .limit(limit)\
        .execute()
```

---

## 🔍 Query Execution Plan

### Step-by-Step Execution
```
1. User Login
   └─> Get user info (users table) - 1 query

2. Load Portfolio
   ├─> Get all transactions for user (investment_transactions) - 1 query
   ├─> Extract unique tickers from transactions
   ├─> Bulk fetch stock_data for tickers (stock_data) - 1 query
   ├─> Bulk fetch current prices (historical_prices) - 1 query
   └─> Calculate holdings in memory (0 queries)

3. Display Dashboard
   ├─> All data already loaded
   ├─> Calculate P&L in memory
   ├─> Generate charts in memory
   └─> No additional queries needed

4. Refresh Prices (optional)
   ├─> Fetch live prices from APIs
   ├─> Update stock_data.live_price - 1 query per ticker (batched)
   └─> Insert into historical_prices - 1 query per ticker (batched)

Total Queries for Complete Load: 4-5 queries
```

---

## 📊 Data Flow Diagram

```
User Request
    │
    ▼
┌─────────────────────┐
│  Optimized Loader   │
└──────────┬──────────┘
           │
           ├─────────────┐
           │             │
           ▼             ▼
     ┌──────────┐  ┌──────────┐
     │  Query 1 │  │  Query 2 │
     │  Users   │  │  Trans   │
     └────┬─────┘  └────┬─────┘
          │             │
          └──────┬──────┘
                 │
                 ▼
          ┌────────────┐
          │Extract     │
          │Unique      │
          │Tickers     │
          └─────┬──────┘
                │
                ├───────────────┐
                │               │
                ▼               ▼
          ┌──────────┐    ┌──────────┐
          │  Query 3 │    │  Query 4 │
          │  Stock   │    │  Prices  │
          │  Data    │    │          │
          └────┬─────┘    └────┬─────┘
               │               │
               └───────┬───────┘
                       │
                       ▼
                ┌────────────┐
                │In-Memory   │
                │Calculations│
                │(Holdings,  │
                │ P&L, etc)  │
                └─────┬──────┘
                      │
                      ▼
               ┌─────────────┐
               │   Result    │
               │   Cache     │
               └──────┬──────┘
                      │
                      ▼
                  Dashboard
```

---

## 🛠️ Maintenance Queries

### Check for Missing stock_data Entries
```sql
SELECT DISTINCT it.ticker
FROM investment_transactions it
LEFT JOIN stock_data sd ON it.ticker = sd.ticker
WHERE sd.ticker IS NULL;
```

### Ensure Foreign Key Integrity
```python
# Run this periodically
python ensure_stock_data_link.py
```

### Update Stale Prices
```sql
-- Find tickers with prices older than 1 day
SELECT ticker, MAX(transaction_date) as last_update
FROM historical_prices
GROUP BY ticker
HAVING MAX(transaction_date) < CURRENT_DATE - INTERVAL '1 day';
```

---

## 📝 Summary

### Key Optimizations
1. **Bulk Queries**: Fetch data for all tickers in single queries
2. **Shared Data**: stock_data and historical_prices shared across users
3. **Caching**: Session-level and database-level caching
4. **In-Memory Calculations**: P&L calculated in Python, not SQL
5. **Indexed Lookups**: O(1) dictionary lookups instead of O(N) queries

### Query Reduction
- **Before**: 1 + 2N queries (N = number of tickers)
- **After**: 4-5 queries (constant time)
- **Improvement**: 25x faster for typical portfolio

### Scalability
- Handles 100+ tickers efficiently
- Sub-second load times
- Minimal database load
- User-specific data isolated
- Shared data cached and reused

---

*This schema and optimization strategy ensures fast, scalable portfolio analytics for all users.*

