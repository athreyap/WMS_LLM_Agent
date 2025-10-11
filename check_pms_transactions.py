#!/usr/bin/env python3
"""
Check for PMS/AIF transactions in the database
"""

from database_config_supabase import supabase

def check_pms_transactions():
    """Check if there are any PMS/AIF transactions in the database"""
    print("🔍 Checking for PMS/AIF transactions...")

    try:
        # Get all transactions
        result = supabase.table('investment_transactions').select('*').execute()

        if not result.data:
            print("❌ No transactions found in database")
            return

        all_transactions = result.data
        print(f"✅ Found {len(all_transactions)} total transactions")

        # Find PMS/AIF transactions
        pms_transactions = []
        mf_transactions = []
        stock_transactions = []

        for txn in all_transactions:
            ticker = txn.get('ticker', '')
            ticker_upper = ticker.upper()

            # PMS/AIF indicators
            pms_keywords = ['PMS', 'AIF', 'INP', 'BUOYANT', 'CARNELIAN', 'JULIUS', 'VALENTIS', 'UNIFI']
            if any(keyword in ticker_upper for keyword in pms_keywords) or ticker_upper.endswith('_PMS'):
                pms_transactions.append(txn)
            # Mutual Fund indicators
            elif (ticker.isdigit() or
                  ticker.startswith('MF_') or
                  ticker.startswith('INF') or
                  len(ticker) == 12):  # ISIN codes
                mf_transactions.append(txn)
            else:
                stock_transactions.append(txn)

        print("\n🏦 Transaction Types:")
        print(f"   📈 Stock Transactions: {len(stock_transactions)}")
        print(f"   📊 Mutual Fund Transactions: {len(mf_transactions)}")
        print(f"   💼 PMS/AIF Transactions: {len(pms_transactions)}")

        if pms_transactions:
            print("\n💼 PMS/AIF Transactions:")
            for pms in pms_transactions[:5]:
                ticker = pms.get('ticker', 'N/A')
                quantity = pms.get('quantity', 0)
                price = pms.get('price', 0)
                date = pms.get('date', 'N/A')
                print(f"   {ticker}: {quantity} units @ ₹{price} on {date}")

        if mf_transactions:
            print("\n📊 Mutual Fund Transactions:")
            for mf in mf_transactions[:5]:
                ticker = mf.get('ticker', 'N/A')
                quantity = mf.get('quantity', 0)
                price = mf.get('price', 0)
                date = mf.get('date', 'N/A')
                print(f"   {ticker}: {quantity} units @ ₹{price} on {date}")

        # Check if PMS/AIF transactions have corresponding price records
        if pms_transactions:
            print(f"\n🔍 Checking if PMS/AIF transactions have price records...")
            pms_tickers = [p.get('ticker') for p in pms_transactions]

            # Check historical_prices table for PMS data
            for ticker in pms_tickers[:3]:  # Check first 3 PMS tickers
                try:
                    result = supabase.table('historical_prices').select('*').eq('ticker', ticker).execute()
                    if result.data:
                        print(f"   ✅ {ticker}: Found {len(result.data)} price records")
                        for record in result.data[:3]:
                            price_date = record.get('transaction_date', 'N/A')
                            price_val = record.get('historical_price', 0)
                            source = record.get('price_source', 'unknown')
                            print(f"      {price_date}: ₹{price_val} ({source})")
                    else:
                        print(f"   ❌ {ticker}: No price records found")
                except Exception as e:
                    print(f"   ❌ Error checking {ticker}: {e}")

    except Exception as e:
        print(f"❌ Error checking PMS transactions: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_pms_transactions()
