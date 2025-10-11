"""
Optimized Data Loader with JOINs for Fast Portfolio Analytics
Schema:
- users: User accounts
- investment_transactions: User-specific transactions (user_id FK)
- historical_prices: Historical prices for tickers (ticker, transaction_date)
- stock_data: Ticker metadata - SHARED across users (ticker, sector, market_cap, company_name)
- investment_files: File records per user
- pdf_documents: PDF documents for AI chatbot
- user_login: Login tracking
"""

from database_config_supabase import supabase, update_stock_data_supabase
from typing import Dict, List, Optional
import pandas as pd
from datetime import datetime
import time


class OptimizedPortfolioLoader:
    """
    Fast portfolio data loader using optimized JOINs and bulk queries.
    Minimizes database round trips and provides data for both dashboard and chatbot.
    """
    
    def __init__(self):
        self.cache = {}
        self.cache_timestamp = {}
        self.cache_ttl = 300  # 5 minutes cache TTL
    
    def _is_cache_valid(self, key: str) -> bool:
        """Check if cache is still valid"""
        if key not in self.cache:
            return False
        
        if key not in self.cache_timestamp:
            return False
        
        age = time.time() - self.cache_timestamp[key]
        return age < self.cache_ttl
    
    def _set_cache(self, key: str, data: any):
        """Set cache with timestamp"""
        self.cache[key] = data
        self.cache_timestamp[key] = time.time()
    
    def get_user_portfolio_fast(self, user_id: int, force_refresh: bool = False) -> Dict:
        """
        Get complete portfolio data with all JOINs in optimized queries.
        Uses caching to avoid repeated database calls.
        
        Returns:
        {
            'user_info': {...},
            'transactions': [...],
            'holdings': [...],
            'summary': {...},
            'stock_metadata': {...},  # For chatbot
            'price_history': {...}   # For chatbot and graphs
        }
        """
        cache_key = f"portfolio_{user_id}"
        
        if not force_refresh and self._is_cache_valid(cache_key):
            print(f"✅ Using cached portfolio data for user {user_id}")
            return self.cache[cache_key]
        
        print(f"🔄 Loading fresh portfolio data for user {user_id}...")
        start_time = time.time()
        
        try:
            # Step 1: Get user info (1 query)
            user_info = supabase.table('users')\
                .select('id, username, email, role, created_at')\
                .eq('id', user_id)\
                .execute()
            
            if not user_info.data or len(user_info.data) == 0:
                return {'error': 'User not found'}
            
            user_data = user_info.data[0]
            print(f"✅ User: {user_data.get('username')}")
            
            # Step 2: Get all transactions for user (1 query)
            transactions = supabase.table('investment_transactions')\
                .select('*')\
                .eq('user_id', user_id)\
                .order('date', desc=False)\
                .execute()
            
            if not transactions.data:
                print("⚠️ No transactions found")
                result = {
                    'user_info': user_data,
                    'transactions': [],
                    'holdings': [],
                    'summary': {},
                    'stock_metadata': {},
                    'price_history': {}
                }
                self._set_cache(cache_key, result)
                return result
            
            print(f"✅ Found {len(transactions.data)} transactions")
            
            # Convert to DataFrame
            df = pd.DataFrame(transactions.data)
            df['date'] = pd.to_datetime(df['date'])
            
            # Get unique tickers
            unique_tickers = df['ticker'].unique().tolist()
            print(f"✅ Found {len(unique_tickers)} unique tickers")
            
            # Step 3: Bulk fetch stock_data for all tickers (1 query - SHARED DATA)
            # Ensures stock_data exists for all tickers (FK relationship)
            stock_metadata = {}
            if unique_tickers:
                stock_data_result = supabase.table('stock_data')\
                    .select('ticker, sector, market_cap, company_name, exchange, industry, last_updated')\
                    .in_('ticker', unique_tickers)\
                    .execute()
                
                if stock_data_result.data:
                    stock_metadata = {s['ticker']: s for s in stock_data_result.data}
                    print(f"✅ Fetched metadata for {len(stock_metadata)} tickers")
                
                # Check for tickers missing from stock_data and create entries
                missing_tickers = set(unique_tickers) - set(stock_metadata.keys())
                if missing_tickers:
                    print(f"⚠️ Creating stock_data entries for {len(missing_tickers)} missing tickers...")
                    for ticker in missing_tickers:
                        try:
                            # Create basic stock_data entry to maintain FK integrity
                            update_stock_data_supabase(
                                ticker=ticker,
                                sector="Unknown",
                                market_cap=None,
                                last_price=None
                            )
                            stock_metadata[ticker] = {
                                'ticker': ticker,
                                'sector': 'Unknown',
                                'market_cap': None,
                                'company_name': ticker
                            }
                        except Exception as e:
                            print(f"⚠️ Could not create stock_data for {ticker}: {e}")
            
            # Step 4: Bulk fetch current prices (1 query - SHARED DATA)
            current_prices = {}
            if unique_tickers:
                today = datetime.now().strftime('%Y-%m-%d')
                
                # Get latest price for each ticker
                prices_result = supabase.table('historical_prices')\
                    .select('ticker, historical_price, current_price, transaction_date')\
                    .in_('ticker', unique_tickers)\
                    .lte('transaction_date', today)\
                    .order('transaction_date', desc=True)\
                    .execute()
                
                if prices_result.data:
                    # Keep only latest price per ticker
                    seen_tickers = set()
                    for price_data in prices_result.data:
                        ticker = price_data['ticker']
                        if ticker not in seen_tickers:
                            current_prices[ticker] = {
                                'price': price_data.get('current_price') or price_data.get('historical_price'),
                                'date': price_data['transaction_date']
                            }
                            seen_tickers.add(ticker)
                    
                    print(f"✅ Fetched current prices for {len(current_prices)} tickers")
            
            # Step 5: Enrich transactions with JOINed data
            for idx, row in df.iterrows():
                ticker = row['ticker']
                
                # Add metadata from stock_data
                if ticker in stock_metadata:
                    for key, value in stock_metadata[ticker].items():
                        if key != 'ticker':
                            df.at[idx, f'stock_{key}'] = value
                
                # Add current price
                if ticker in current_prices:
                    df.at[idx, 'current_price'] = current_prices[ticker]['price']
                    df.at[idx, 'current_price_date'] = current_prices[ticker]['date']
            
            # Step 6: Calculate holdings and P&L
            holdings = []
            
            for ticker in unique_tickers:
                ticker_df = df[df['ticker'] == ticker].copy()
                
                # Calculate net quantity
                buys = ticker_df[ticker_df['transaction_type'] == 'buy']
                sells = ticker_df[ticker_df['transaction_type'] == 'sell']
                
                total_buy_qty = buys['quantity'].sum()
                total_sell_qty = sells['quantity'].sum()
                net_quantity = total_buy_qty - total_sell_qty
                
                if net_quantity <= 0:
                    continue  # Fully sold
                
                # Calculate weighted average price
                total_invested = (buys['quantity'] * buys['price']).sum()
                avg_price = total_invested / total_buy_qty if total_buy_qty > 0 else 0
                
                # Get current price (fallback to avg if not available)
                current_price = current_prices.get(ticker, {}).get('price', avg_price)
                
                # Calculate P&L
                invested_amount = net_quantity * avg_price
                current_value = net_quantity * current_price
                pnl = current_value - invested_amount
                pnl_percent = (pnl / invested_amount * 100) if invested_amount > 0 else 0
                
                # Get metadata
                metadata = stock_metadata.get(ticker, {})
                
                holding = {
                    'ticker': ticker,
                    'stock_name': metadata.get('company_name', ticker),
                    'quantity': float(net_quantity),
                    'avg_price': float(avg_price),
                    'current_price': float(current_price),
                    'invested_amount': float(invested_amount),
                    'current_value': float(current_value),
                    'pnl': float(pnl),
                    'pnl_percent': float(pnl_percent),
                    'sector': metadata.get('sector'),
                    'market_cap': metadata.get('market_cap'),
                    'industry': metadata.get('industry'),
                    'first_buy_date': str(buys['date'].min()),
                    'last_transaction_date': str(ticker_df['date'].max()),
                    'total_buys': int(len(buys)),
                    'total_sells': int(len(sells))
                }
                
                holdings.append(holding)
            
            # Sort holdings by current value (descending)
            holdings.sort(key=lambda x: x['current_value'], reverse=True)
            
            # Step 7: Calculate portfolio summary
            total_invested = sum(h['invested_amount'] for h in holdings)
            total_current_value = sum(h['current_value'] for h in holdings)
            total_pnl = total_current_value - total_invested
            total_pnl_percent = (total_pnl / total_invested * 100) if total_invested > 0 else 0
            
            # Top gainers and losers
            gainers = sorted([h for h in holdings if h['pnl'] > 0], key=lambda x: x['pnl_percent'], reverse=True)[:5]
            losers = sorted([h for h in holdings if h['pnl'] < 0], key=lambda x: x['pnl_percent'])[:5]
            
            # Sector allocation
            sector_allocation = {}
            for h in holdings:
                sector = h.get('sector') or 'Unknown'
                if sector not in sector_allocation:
                    sector_allocation[sector] = {'value': 0, 'count': 0}
                sector_allocation[sector]['value'] += h['current_value']
                sector_allocation[sector]['count'] += 1
            
            summary = {
                'total_invested': float(total_invested),
                'total_current_value': float(total_current_value),
                'total_pnl': float(total_pnl),
                'total_pnl_percent': float(total_pnl_percent),
                'total_holdings': len(holdings),
                'active_holdings': len([h for h in holdings if h['quantity'] > 0]),
                'total_transactions': len(df),
                'total_buys': len(df[df['transaction_type'] == 'buy']),
                'total_sells': len(df[df['transaction_type'] == 'sell']),
                'first_transaction_date': str(df['date'].min()),
                'last_transaction_date': str(df['date'].max()),
                'top_gainers': gainers,
                'top_losers': losers,
                'sector_allocation': sector_allocation
            }
            
            # Step 8: Prepare price history for graphs
            price_history = {}
            for ticker in unique_tickers:
                ticker_prices = supabase.table('historical_prices')\
                    .select('transaction_date, historical_price, current_price')\
                    .eq('ticker', ticker)\
                    .order('transaction_date', desc=False)\
                    .limit(365)\
                    .execute()
                
                if ticker_prices.data:
                    price_history[ticker] = ticker_prices.data
            
            # Final result
            result = {
                'user_info': user_data,
                'transactions': df.to_dict('records'),
                'holdings': holdings,
                'summary': summary,
                'stock_metadata': stock_metadata,  # For chatbot
                'price_history': price_history,    # For graphs
                'current_prices': current_prices   # For chatbot
            }
            
            # Cache the result
            self._set_cache(cache_key, result)
            
            elapsed = time.time() - start_time
            print(f"✅ Portfolio loaded in {elapsed:.2f}s")
            print(f"   📊 {len(holdings)} holdings | ₹{total_invested:,.2f} invested | ₹{total_pnl:,.2f} P&L ({total_pnl_percent:.2f}%)")
            
            return result
            
        except Exception as e:
            print(f"❌ Error loading portfolio: {e}")
            import traceback
            traceback.print_exc()
            return {'error': str(e)}
    
    def get_chatbot_context(self, user_id: int) -> str:
        """
        Get formatted context for chatbot with all portfolio data.
        This allows the chatbot to answer questions about the portfolio.
        """
        portfolio = self.get_user_portfolio_fast(user_id)
        
        if 'error' in portfolio:
            return f"Error loading portfolio: {portfolio['error']}"
        
        # Format context for chatbot
        context = []
        context.append(f"=== Portfolio Summary ===")
        context.append(f"User: {portfolio['user_info']['username']}")
        
        summary = portfolio['summary']
        context.append(f"\nTotal Invested: ₹{summary['total_invested']:,.2f}")
        context.append(f"Current Value: ₹{summary['total_current_value']:,.2f}")
        context.append(f"Total P&L: ₹{summary['total_pnl']:,.2f} ({summary['total_pnl_percent']:.2f}%)")
        context.append(f"Active Holdings: {summary['active_holdings']}")
        context.append(f"Total Transactions: {summary['total_transactions']}")
        
        context.append(f"\n=== Top Holdings ===")
        for i, holding in enumerate(portfolio['holdings'][:10], 1):
            context.append(
                f"{i}. {holding['stock_name']} ({holding['ticker']}): "
                f"₹{holding['current_value']:,.2f} | "
                f"P&L: ₹{holding['pnl']:,.2f} ({holding['pnl_percent']:.2f}%)"
            )
        
        context.append(f"\n=== Sector Allocation ===")
        for sector, data in summary['sector_allocation'].items():
            pct = (data['value'] / summary['total_current_value'] * 100)
            context.append(f"{sector}: ₹{data['value']:,.2f} ({pct:.1f}%) - {data['count']} holdings")
        
        return "\n".join(context)
    
    def clear_cache(self, user_id: Optional[int] = None):
        """Clear cache for specific user or all users"""
        if user_id:
            cache_key = f"portfolio_{user_id}"
            if cache_key in self.cache:
                del self.cache[cache_key]
                del self.cache_timestamp[cache_key]
                print(f"✅ Cleared cache for user {user_id}")
        else:
            self.cache.clear()
            self.cache_timestamp.clear()
            print("✅ Cleared all cache")


# Global instance
portfolio_loader = OptimizedPortfolioLoader()


# Convenience functions
def get_portfolio_fast(user_id: int, force_refresh: bool = False) -> Dict:
    """Get complete portfolio with all JOINs - fast and optimized"""
    return portfolio_loader.get_user_portfolio_fast(user_id, force_refresh)


def get_chatbot_context(user_id: int) -> str:
    """Get portfolio context for chatbot"""
    return portfolio_loader.get_chatbot_context(user_id)


def clear_portfolio_cache(user_id: Optional[int] = None):
    """Clear portfolio cache"""
    portfolio_loader.clear_cache(user_id)


if __name__ == "__main__":
    # Test the optimized loader
    print("Testing Optimized Portfolio Loader...")
    print("=" * 60)
    
    # You can test with a specific user_id
    # result = get_portfolio_fast(23)
    # print(json.dumps(result['summary'], indent=2))

