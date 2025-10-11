#!/usr/bin/env python3
"""
Check if different investment types (stocks, MF, PMS) are stored in the database
"""

from database_config_supabase import supabase

def check_investment_types():
    """Check what types of investments are stored in the database"""
    print("🔍 Checking investment types in database...")

    try:
        # Get all stock prices - try stock_prices first, fallback to historical_prices
        try:
            result = supabase.table('stock_prices').select('*').execute()
        except:
            print("🔄 Using historical_prices table as fallback...")
            result = supabase.table('historical_prices').select('*').execute()  # Increase limit

        if not result.data:
            print("❌ No stock prices found in database")
            return

        all_prices = result.data
        print(f"✅ Found {len(all_prices)} total price records")
        print(f"🔍 DEBUG: Sample record keys: {all_prices[0].keys() if all_prices else 'No records'}")

        # Analyze by price source
        price_sources = {}
        mf_indicators = []
        pms_indicators = []
        stock_indicators = []

        for price in all_prices:
            # Handle different column names between stock_prices and historical_prices tables
            ticker = price.get('ticker', '')
            source = price.get('price_source', 'unknown')
            price_date = price.get('price_date') or price.get('transaction_date', '')
            price_val = price.get('price') or price.get('historical_price', 0)

            # Count by source
            if source not in price_sources:
                price_sources[source] = 0
            price_sources[source] += 1

            # Identify investment types based on ticker patterns and sources
            ticker_upper = ticker.upper()

            # PMS/AIF indicators
            pms_keywords = ['PMS', 'AIF', 'INP', 'BUOYANT', 'CARNELIAN', 'JULIUS', 'VALENTIS', 'UNIFI']
            is_pms = any(keyword in ticker_upper for keyword in pms_keywords) or ticker_upper.endswith('_PMS')

            if is_pms:
                pms_indicators.append({
                    'ticker': ticker,
                    'source': source,
                    'date': price_date,
                    'price': price_val
                })
                print(f"🔍 DEBUG: Classified {ticker} as PMS (source: {source})")
            # Mutual Fund indicators
            elif (source == 'mftool' or
                  ticker.isdigit() or
                  ticker.startswith('MF_') or
                  ticker.startswith('INF') or
                  len(ticker) == 12):  # ISIN codes
                mf_indicators.append({
                    'ticker': ticker,
                    'source': source,
                    'date': price_date,
                    'price': price_val
                })
            # Stock indicators
            else:
                stock_indicators.append({
                    'ticker': ticker,
                    'source': source,
                    'date': price_date,
                    'price': price_val
                })

        # Print summary
        print(f"\n📊 Price Sources Summary:")
        for source, count in sorted(price_sources.items(), key=lambda x: x[1], reverse=True):
            print(f"   {source}: {count} records")

        print("\n🏦 Investment Types Found:")
        print(f"   📈 Stocks: {len(stock_indicators)}")
        print(f"   📊 Mutual Funds: {len(mf_indicators)}")
        print(f"   💼 PMS/AIF: {len(pms_indicators)}")

        # Show samples of each type
        if stock_indicators:
            print("\n📈 Stock Samples:")
            for stock in stock_indicators[:5]:
                print(f"   {stock['ticker']} ({stock['source']}): ₹{stock['price']} on {stock['date']}")

        if mf_indicators:
            print("\n📊 Mutual Fund Samples:")
            for mf in mf_indicators[:5]:
                print(f"   {mf['ticker']} ({mf['source']}): ₹{mf['price']} on {mf['date']}")

        if pms_indicators:
            print("\n💼 PMS/AIF Samples:")
            for pms in pms_indicators[:5]:
                print(f"   {pms['ticker']} ({pms['source']}): ₹{pms['price']} on {pms['date']}")

        # Check for recent data (last 30 days)
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=30)

        recent_stocks = [s for s in stock_indicators if s['date'] > cutoff_date.strftime('%Y-%m-%d')]
        recent_mf = [m for m in mf_indicators if m['date'] > cutoff_date.strftime('%Y-%m-%d')]
        recent_pms = [p for p in pms_indicators if p['date'] > cutoff_date.strftime('%Y-%m-%d')]

        print("\n🕐 Recent Activity (Last 30 Days):")
        print(f"   📈 Recent Stocks: {len(recent_stocks)}")
        print(f"   📊 Recent Mutual Funds: {len(recent_mf)}")
        print(f"   💼 Recent PMS/AIF: {len(recent_pms)}")

        if recent_stocks or recent_mf or recent_pms:
            print("\n🔥 Most Recent Records:")
            recent_all = recent_stocks + recent_mf + recent_pms
            recent_all.sort(key=lambda x: x['date'], reverse=True)

            for record in recent_all[:10]:
                type_label = "📈 Stock" if record in recent_stocks else ("📊 MF" if record in recent_mf else "💼 PMS")
                print(f"   {type_label}: {record['ticker']} - ₹{record['price']} on {record['date']}")

    except Exception as e:
        print(f"❌ Error checking investment types: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_investment_types()
