#!/usr/bin/env python3
"""
Debug script to check P&L calculation issues
"""

from database_config_supabase import get_transactions_supabase, supabase
import pandas as pd

def debug_pnl_calculation(user_id):
    """Debug P&L calculation issues"""
    print(f"🔍 Debugging P&L calculation for user {user_id}")

    # Get transactions
    transactions = get_transactions_supabase(user_id=user_id)
    if not transactions:
        print("❌ No transactions found")
        return

    print(f"✅ Found {len(transactions)} transactions")

    # Convert to DataFrame
    df = pd.DataFrame(transactions)
    print(f"📊 DataFrame shape: {df.shape}")
    print(f"📋 Columns: {df.columns.tolist()}")

    # Check for required columns
    required_columns = ['ticker', 'quantity', 'price', 'transaction_type']
    for col in required_columns:
        if col not in df.columns:
            print(f"❌ Missing required column: {col}")
            return
        else:
            print(f"✅ Column {col}: {df[col].dtype}, sample: {df[col].head(3).tolist()}")

    # Filter to only buy transactions for portfolio calculation
    buy_df = df[df['transaction_type'] == 'buy'].copy()
    print(f"🛒 Buy transactions: {len(buy_df)}")

    if len(buy_df) == 0:
        print("❌ No buy transactions found")
        return

    # Check for unique tickers
    unique_tickers = buy_df['ticker'].unique()
    print(f"🎯 Unique tickers: {len(unique_tickers)}")
    print(f"📈 Tickers: {unique_tickers[:10].tolist()}")  # Show first 10

    # Try to fetch live prices manually to see if that's working
    print("\n🔄 Testing live price fetching...")
    live_prices = {}

    for ticker in unique_tickers[:5]:  # Test first 5 tickers
        try:
            print(f"🔍 Testing ticker: {ticker}")
            # Try different price sources
            price = None

            # Try yfinance for stocks
            if not price:
                try:
                    import yfinance as yf
                    ticker_yf = ticker
                    if not ticker.endswith('.NS') and not ticker.endswith('.BO'):
                        ticker_yf = ticker + '.NS'  # Default to NSE

                    stock = yf.Ticker(ticker_yf)
                    info = stock.history(period='1d')
                    if not info.empty:
                        price = float(info['Close'].iloc[-1])
                        print(f"✅ yfinance {ticker_yf}: ₹{price}")
                except Exception as e:
                    print(f"⚠️ yfinance failed for {ticker}: {e}")

            # Try unified price fetcher
            if not price:
                try:
                    from unified_price_fetcher import get_stock_price_and_sector
                    price, sector, market_cap = get_stock_price_and_sector(ticker, ticker, None)
                    if price and price > 0:
                        print(f"✅ unified_price_fetcher {ticker}: ₹{price}")
                except Exception as e:
                    print(f"⚠️ unified_price_fetcher failed for {ticker}: {e}")

            if price and price > 0:
                live_prices[ticker] = price
            else:
                print(f"❌ No price found for {ticker}")

        except Exception as e:
            print(f"❌ Error testing {ticker}: {e}")

    print(f"\n📊 Successfully fetched live prices for {len(live_prices)}/{len(unique_tickers[:5])} tickers")

    # Simulate portfolio calculation
    if live_prices:
        print("\n🧮 Simulating portfolio calculation...")

        # Group by ticker to get total quantity and weighted average price
        portfolio = buy_df.groupby('ticker').agg({
            'quantity': 'sum',
            'price': lambda x: (x * buy_df.loc[x.index, 'quantity']).sum() / x.sum() if x.sum() > 0 else 0
        }).reset_index()

        print(f"📊 Portfolio positions: {len(portfolio)}")

        # Add live prices
        portfolio['live_price'] = portfolio['ticker'].map(live_prices)
        portfolio['invested_amount'] = portfolio['quantity'] * portfolio['price']
        portfolio['current_value'] = portfolio['quantity'] * portfolio['live_price'].fillna(portfolio['price'])
        portfolio['unrealized_pnl'] = portfolio['current_value'] - portfolio['invested_amount']

        # Calculate totals
        total_invested = portfolio['invested_amount'].sum()
        total_current = portfolio['current_value'].sum()
        total_pnl = portfolio['unrealized_pnl'].sum()

        print("\n💰 Portfolio Summary:")
        print(f"   Total Invested: ₹{total_invested:,.2f}")
        print(f"   Current Value: ₹{total_current:,.2f}")
        print(f"   Total P&L: ₹{total_pnl:,.2f}")
        print(f"   P&L %: {(total_pnl/total_invested*100):.2f}%" if total_invested > 0 else "   P&L %: N/A")

        if total_pnl == 0:
            print("\n⚠️ P&L is 0, which suggests live prices are not being fetched correctly")
            print(f"   Live prices available: {len(live_prices)}")
            print(f"   Tickers with live prices: {list(live_prices.keys())}")
            print(f"   Sample live price values: {list(live_prices.values())[:3]}")

if __name__ == "__main__":
    # Find the user ID automatically
    try:
        result = supabase.table('users').select('id, username').execute()
        if result.data:
            # Use the first user found (or you can modify this logic)
            user_id = result.data[0]['id']
            username = result.data[0]['username']
            print(f"🔍 Using user: {username} (ID: {user_id})")
        else:
            print("❌ No users found in database")
            exit(1)
    except Exception as e:
        print(f"❌ Error finding users: {e}")
        # Fallback to user ID 1 if we can't query users
        user_id = 1
        print(f"🔍 Using fallback user ID: {user_id}")

    debug_pnl_calculation(user_id)
