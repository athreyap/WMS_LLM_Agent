"""
Optimized Data Loader - Batch Query Approach
Fetches ALL user data in 1-3 queries instead of 60+ individual requests
"""

import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
from database_config_supabase import (
    supabase,
    get_transactions_supabase,
    retry_on_disconnect
)

# In-memory cache for portfolio data
_portfolio_cache = {}
_cache_timestamp = {}

def clear_portfolio_cache(user_id: int):
    """Clear cached portfolio data for a user"""
    if user_id in _portfolio_cache:
        del _portfolio_cache[user_id]
    if user_id in _cache_timestamp:
        del _cache_timestamp[user_id]
    print(f"✅ Cleared portfolio cache for user {user_id}")


@retry_on_disconnect(max_retries=3, delay=2)
def get_portfolio_fast(user_id: int, force_refresh: bool = False) -> Dict:
    """
    Optimized portfolio loader - fetches ALL data in 1-3 batch queries
    
    Instead of:
        - 60+ queries for historical prices (one per ticker)
        - Individual stock data queries
    
    Does:
        - 1 query for ALL transactions
        - 1 query for ALL stock data (batched by ticker list)
        - 1 query for ALL historical prices (batched by ticker list)
    
    Returns portfolio data with all JOINs completed
    """
    
    # Check cache first (unless force_refresh)
    cache_key = user_id
    if not force_refresh and cache_key in _portfolio_cache:
        cache_age = (datetime.now() - _cache_timestamp.get(cache_key, datetime.min)).seconds
        if cache_age < 300:  # 5 minutes
            print(f"✅ Using cached portfolio data (age: {cache_age}s)")
            return _portfolio_cache[cache_key]
    
    try:
        print(f"🚀 Fetching portfolio data for user {user_id} (batch mode)")
        
        # ===== STEP 1: Get ALL transactions in 1 query =====
        print(f"   📊 Step 1/3: Fetching all transactions...")
        transactions = get_transactions_supabase(user_id=user_id)
        
        if not transactions:
            print(f"⚠️ No transactions found for user {user_id}")
            return {
                'transactions': [],
                'stock_data': {},
                'historical_prices': {},
                'error': 'No transactions found. Please upload a CSV file first.'
            }
        
        df_transactions = pd.DataFrame(transactions)
        unique_tickers = df_transactions['ticker'].unique().tolist()
        print(f"   ✅ Loaded {len(transactions)} transactions for {len(unique_tickers)} unique tickers")
        
        # ===== STEP 2: Get ALL stock data in 1 batch query =====
        print(f"   📊 Step 2/3: Fetching all stock data (batch)...")
        stock_data_result = supabase.table("stock_data")\
            .select("ticker,stock_name,sector,live_price,last_updated")\
            .in_("ticker", unique_tickers)\
            .execute()
        
        stock_data_list = stock_data_result.data if stock_data_result.data else []
        stock_data_dict = {item['ticker']: item for item in stock_data_list}
        print(f"   ✅ Loaded stock data for {len(stock_data_dict)} tickers")
        
        # ===== STEP 3: Get ALL historical prices in 1 batch query =====
        print(f"   📊 Step 3/3: Fetching all historical prices (batch)...")
        today = datetime.now().strftime('%Y-%m-%d')
        
        historical_prices_result = supabase.table("historical_prices")\
            .select("ticker,historical_price,current_price,transaction_date")\
            .in_("ticker", unique_tickers)\
            .lte("transaction_date", today)\
            .order("transaction_date", desc=True)\
            .execute()
        
        historical_prices_list = historical_prices_result.data if historical_prices_result.data else []
        
        # Group historical prices by ticker (most recent first due to order by desc)
        historical_prices_dict = {}
        for price_record in historical_prices_list:
            ticker = price_record['ticker']
            if ticker not in historical_prices_dict:
                historical_prices_dict[ticker] = []
            historical_prices_dict[ticker].append(price_record)
        
        print(f"   ✅ Loaded {len(historical_prices_list)} historical price records")
        
        # ===== STEP 4: Join everything in memory (fast!) =====
        print(f"   🔗 Step 4/4: Joining data in memory...")
        
        # Add stock data to transactions
        for idx, row in df_transactions.iterrows():
            ticker = row['ticker']
            stock_info = stock_data_dict.get(ticker, {})
            
            df_transactions.at[idx, 'live_price_db'] = stock_info.get('live_price')
            df_transactions.at[idx, 'sector_db'] = stock_info.get('sector')
            df_transactions.at[idx, 'stock_name_db'] = stock_info.get('stock_name', row.get('stock_name'))
            df_transactions.at[idx, 'last_updated'] = stock_info.get('last_updated')
        
        # Convert back to list of dicts for compatibility
        transactions_with_joins = df_transactions.to_dict('records')
        
        # ===== STEP 5: Cache and return =====
        result = {
            'transactions': transactions_with_joins,
            'stock_data': stock_data_dict,
            'historical_prices': historical_prices_dict,
            'error': None
        }
        
        # Cache the result
        _portfolio_cache[cache_key] = result
        _cache_timestamp[cache_key] = datetime.now()
        
        print(f"✅ Portfolio data loaded successfully (batch mode)")
        print(f"   - Transactions: {len(transactions)}")
        print(f"   - Unique tickers: {len(unique_tickers)}")
        print(f"   - Stock data: {len(stock_data_dict)}")
        print(f"   - Historical prices: {len(historical_prices_list)}")
        
        return result
        
    except Exception as e:
        print(f"❌ Error in batch portfolio loader: {e}")
        return {'error': str(e)}


def get_chatbot_context(user_id: int) -> str:
    """Get portfolio context for chatbot (uses cached data)"""
    try:
        portfolio_data = get_portfolio_fast(user_id, force_refresh=False)
        
        if 'error' in portfolio_data and portfolio_data['error']:
            return f"Error loading portfolio: {portfolio_data['error']}"
        
        transactions = portfolio_data.get('transactions', [])
        if not transactions:
            return "No portfolio data available"
        
        df = pd.DataFrame(transactions)
        
        # Build context summary
        context = f"""
Portfolio Summary for User {user_id}:

Total Holdings: {len(df)}
Unique Tickers: {df['ticker'].nunique()}

Holdings:
{df[['ticker', 'stock_name', 'quantity', 'price', 'date']].to_string(index=False)}

Sectors (if available):
{df.groupby('sector_db')['ticker'].count().to_string() if 'sector_db' in df.columns else 'N/A'}
"""
        return context
        
    except Exception as e:
        return f"Error getting chatbot context: {e}"


@retry_on_disconnect(max_retries=3, delay=2)
def get_user_portfolio_fast(user_id: int):
    """Alias for get_portfolio_fast for backwards compatibility"""
    return get_portfolio_fast(user_id, force_refresh=False)


# Export functions
__all__ = [
    'get_portfolio_fast',
    'get_user_portfolio_fast',
    'get_chatbot_context',
    'clear_portfolio_cache'
]

