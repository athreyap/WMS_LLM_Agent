# 🚀 WMS-LLM System Architecture & Optimizations

## Overview
This document describes the architecture, optimizations, and key design decisions in the WMS-LLM (Wealth Management System with LLM) platform.

---

## 🏗️ System Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit Frontend                        │
│                     (web_agent.py)                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
           ┌───────────┴──────────┐
           │                      │
┌──────────▼──────────┐  ┌───────▼────────────┐
│  Data Loader        │  │  Price Fetcher     │
│  (optimized_data    │  │  (unified_price    │
│   _loader.py)       │  │   _fetcher.py)     │
└──────────┬──────────┘  └───────┬────────────┘
           │                     │
           └──────────┬──────────┘
                      │
           ┌──────────▼──────────┐
           │   Database Layer    │
           │  (database_config   │
           │   _supabase.py)     │
           └──────────┬──────────┘
                      │
           ┌──────────▼──────────┐
           │   Supabase DB       │
           │  (PostgreSQL)       │
           └─────────────────────┘
```

---

## 🗄️ Database Schema

### Table Relationships

```
users (id, username, password_hash, role)
  │
  ├──> user_login (user_id FK, last_login)
  │
  └──> investment_transactions (user_id FK, ticker, date, type, quantity, price)
              │
              └──> stock_data (ticker PK, stock_name, sector, live_price)
                      │
                      └──> historical_prices (ticker FK, transaction_date, historical_price)
```

### Key Design Principles

1. **User-Specific Data**: `investment_transactions` contains user-specific portfolio data
2. **Shared Data**: `stock_data` and `historical_prices` are shared across all users
3. **Foreign Keys**: Enforce data integrity with FK relationships
4. **No Duplication**: Stock metadata and historical prices stored once for all users

---

## ⚡ Performance Optimizations

### 1. Optimized Data Loading

**Problem**: Multiple database queries for each ticker (N+1 problem)

**Solution**: Bulk JOINs in `optimized_data_loader.py`

```python
# OLD: 100 queries for 100 tickers
for ticker in tickers:
    transaction = get_transaction(user_id, ticker)
    stock = get_stock_data(ticker)
    price = get_price(ticker)

# NEW: 3 queries total
transactions = get_all_transactions_with_joins(user_id)  # 1 query
stock_metadata = bulk_fetch_stock_data(tickers)          # 1 query  
current_prices = bulk_fetch_prices(tickers)              # 1 query
```

**Result**: 
- Reduced DB calls from ~300 to ~5 per page load
- 10x faster portfolio loading

### 2. Intelligent Caching Strategy

#### Session-Level Cache
- Live prices cached in `st.session_state`
- Cache TTL: 5 minutes
- Avoids redundant API calls during same session

#### Database-Level Cache
- Historical prices stored in `historical_prices` table
- Weekly and monthly price snapshots
- Fallback hierarchy:
  1. Check database cache
  2. Fetch from API
  3. Save to database
  4. Return to user

### 3. First-Time Setup Optimization

**Challenge**: New users need complete historical data

**Solution**: Smart detection + bulk processing

```python
# Check if any cached data exists
has_cache = check_existing_cache(tickers)

if not has_cache:
    # First time: Process ALL tickers
    process_all_tickers_no_limit(tickers)
else:
    # Incremental: Limit to 20 tickers per update
    process_top_20_stale_tickers(tickers)
```

**Result**:
- First login: Complete data population (one-time)
- Subsequent logins: Fast incremental updates

### 4. Price Fetching Optimization

#### Multi-Source Fallback
```python
def get_price(ticker, investment_type):
    # Step 1: Check database cache
    price = get_from_db(ticker, date)
    if price:
        return price
    
    # Step 2: Try primary API
    if investment_type == "Stock":
        price = yfinance.get(ticker)
    elif investment_type == "MF":
        price = mftool.get_nav(ticker)
    elif investment_type == "PMS":
        price = sebi.get_pms_data(ticker)
    
    # Step 3: Save to cache
    save_to_db(ticker, date, price)
    
    return price
```

#### Rate Limiting & Timeout
- Max 20 concurrent API calls
- 10-second timeout per request (Windows-compatible)
- Graceful fallback on API failures

---

## 🔄 Data Flow

### Portfolio Loading Flow

```
1. User Login
   ↓
2. optimized_data_loader.get_portfolio_fast()
   ↓
3. Bulk fetch transactions (user-specific)
   ↓
4. Extract unique tickers
   ↓
5. Bulk fetch stock_data (shared)
   ↓
6. Bulk fetch historical_prices (shared)
   ↓
7. Check for missing live prices
   ↓
8. Fetch live prices from APIs (batch)
   ↓
9. Save live prices to database
   ↓
10. Calculate P&L and metrics
   ↓
11. Return portfolio data to UI
```

### Price Update Flow

```
1. Identify stale prices (>1 day old)
   ↓
2. Prioritize by portfolio weight
   ↓
3. Batch fetch from APIs (max 20)
   ↓
4. Update stock_data.live_price
   ↓
5. Insert into historical_prices
   ↓
6. Update session cache
   ↓
7. Trigger UI refresh
```

---

## 🎯 Key Features

### 1. Multi-Asset Support

| Asset Type | Price Source | Identifier | Storage |
|------------|-------------|------------|---------|
| Stocks | yfinance, indstocks | Symbol (e.g., INFY) | stock_data |
| Mutual Funds | mftool | AMFI Code (6-digit) | stock_data |
| PMS/AIF | SEBI, transactions | Custom ID | stock_data |

### 2. Automatic Ticker Classification

```python
def classify_ticker(ticker):
    if ticker.endswith('_PMS') or ticker.endswith('_AIF'):
        return 'PMS'
    elif ticker.isdigit() and len(ticker) == 6:
        return 'MF'
    else:
        return 'Stock'
```

### 3. Intelligent P&L Calculation

#### For Stocks & MF
```python
invested_amount = sum(buy_qty * buy_price) - sum(sell_qty * sell_price)
current_quantity = sum(buy_qty) - sum(sell_qty)
current_value = current_quantity * live_price
pnl = current_value - invested_amount
pnl_percent = (pnl / invested_amount) * 100
```

#### For PMS
```python
# Uses percentage-based calculation from transaction history
nav_at_start = first_transaction_price
nav_current = latest_transaction_price
pnl_percent = ((nav_current - nav_at_start) / nav_at_start) * 100
```

---

## 🔐 Security & Scalability

### Security
- Row-Level Security (RLS) in Supabase
- User data isolation via `user_id` FK
- Password hashing
- Environment-based secrets

### Scalability
- Shared stock data: 1 entry per ticker (not per user)
- Efficient indexing on tickers and dates
- Pagination support for large portfolios
- Lazy loading for historical data

---

## 🛠️ Maintenance Operations

### Database Maintenance

```bash
# Ensure FK relationships
python ensure_stock_data_link.py

# Create admin user
python create_admin_user.py

# Setup database
python setup_database.py
python create_tables.py
```

### Cache Management

```python
# Clear user cache
from optimized_data_loader import clear_portfolio_cache
clear_portfolio_cache(user_id)

# Rebuild cache
from web_agent import populate_weekly_and_monthly_cache
populate_weekly_and_monthly_cache(user_id, force_refresh=True)
```

---

## 📊 Monitoring & Debugging

### Key Metrics to Monitor
1. Database query count per page load
2. API call success rate
3. Cache hit rate
4. Average portfolio load time
5. Failed price fetches

### Logging
- All price fetching logged to console
- Failed API calls tracked
- Database errors captured
- User actions logged for debugging

---

## 🚀 Future Enhancements

### Planned Optimizations
1. **Redis Cache Layer**: Add Redis for even faster caching
2. **Background Jobs**: Scheduled price updates via cron
3. **GraphQL API**: Replace REST with GraphQL for efficient queries
4. **Real-time Updates**: WebSocket support for live price streaming
5. **Advanced Analytics**: Machine learning for portfolio recommendations

### Feature Roadmap
1. Mobile app (React Native)
2. Email alerts for price movements
3. Tax calculation and reporting
4. Portfolio comparison and benchmarking
5. Social features (share portfolios, compare with friends)

---

## 📝 Code Quality

### Testing
- Unit tests for price fetchers
- Integration tests for database operations
- End-to-end tests for user flows

### Documentation
- Inline code comments
- Function docstrings
- README for setup
- This architecture doc

---

## 🤝 Contributing

When contributing, please:
1. Follow existing code style
2. Add tests for new features
3. Update documentation
4. Test with multiple users
5. Check database performance impact

---

## 📚 References

- [Streamlit Documentation](https://docs.streamlit.io)
- [Supabase Documentation](https://supabase.com/docs)
- [yfinance Documentation](https://pypi.org/project/yfinance/)
- [PostgreSQL Best Practices](https://wiki.postgresql.org/wiki/Don't_Do_This)

---

*Last Updated: October 2025*
