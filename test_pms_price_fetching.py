#!/usr/bin/env python3
"""
Test PMS price fetching logic step by step
"""

from database_config_supabase import get_transactions_supabase, save_stock_price_supabase, get_stock_price_supabase, supabase
import pandas as pd
from datetime import datetime

def test_pms_price_fetching():
    """Test PMS price fetching step by step"""

    print("🔍 Testing PMS price fetching logic...")

    # Find the user with PMS transactions
    try:
        users_result = supabase.table('users').select('id, username').execute()
        pms_user_id = None

        for user in users_result.data:
            user_id = user['id']
            transactions = get_transactions_supabase(user_id=user_id)
            if transactions:
                df = pd.DataFrame(transactions)
                pms_count = df['ticker'].str.upper().str.contains('PMS|AIF|BUOYANT|CARNELIAN').sum()
                if pms_count > 0:
                    pms_user_id = user_id
                    print(f"🔍 Found PMS transactions for user: {user['username']} (ID: {user_id})")
                    break

        if not pms_user_id:
            print("❌ No users with PMS transactions found")
            return

        # Get transactions for this user
        transactions = get_transactions_supabase(user_id=pms_user_id)
        df = pd.DataFrame(transactions)
        df['date'] = pd.to_datetime(df['date'])

        # Find PMS transactions
        pms_ticker = 'BUOYANT_OPPORTUNITIES_PMS'
        target_date = datetime(2024, 1, 6)

        print(f"\n📊 Testing PMS price fetching for {pms_ticker}...")

        # Step 1: Simulate PMS detection
        ticker_upper = pms_ticker.upper()
        is_pms_aif = any(keyword in ticker_upper for keyword in [
            'PMS', 'AIF', 'INP', 'BUOYANT', 'CARNELIAN', 'JULIUS',
            'VALENTIS', 'UNIFI', 'PORTFOLIO', 'FUND'
        ]) or ticker_upper.endswith('_PMS') or ticker_upper.startswith('INP')

        print(f"   🔍 Step 1 - PMS detection: {is_pms_aif}")

        if is_pms_aif:
            print("   ✅ PMS detected, proceeding with transaction price logic")

            # Step 2: Simulate transaction lookup (from web_agent.py logic)
            ticker_txns = df[
                (df['ticker'] == pms_ticker) &
                (df['date'] <= target_date) &
                (df['transaction_type'] == 'buy')
            ]

            print(f"   🔍 Step 2 - Transaction lookup: Found {len(ticker_txns)} transactions")

            if not ticker_txns.empty:
                latest_txn = ticker_txns.sort_values('date', ascending=False).iloc[0]
                price = float(latest_txn['price'])
                price_source = 'pms_transaction_price'
                target_date_str = target_date.strftime('%Y-%m-%d')

                print(f"   ✅ Step 3 - Found transaction price: ₹{price}")
                print(f"   📋 Transaction: ₹{latest_txn['price']} on {latest_txn['date'].strftime('%Y-%m-%d')}")

                # Step 4: Test saving the price
                try:
                    save_result = save_stock_price_supabase(pms_ticker, target_date_str, price, price_source)
                    print(f"   💾 Step 4 - Save result: {save_result}")
                except Exception as e:
                    print(f"   ❌ Step 4 - Save error: {e}")

                # Step 5: Test retrieving the price
                try:
                    retrieved_price = get_stock_price_supabase(pms_ticker, target_date_str)
                    print(f"   🔍 Step 5 - Retrieved price: {retrieved_price}")

                    if retrieved_price and abs(float(retrieved_price) - price) < 0.01:
                        print(f"   ✅ Step 6 - Save/Retrieve test PASSED")
                    else:
                        print(f"   ❌ Step 6 - Save/Retrieve test FAILED")
                except Exception as e:
                    print(f"   ❌ Step 5 - Retrieve error: {e}")
            else:
                print("   ❌ No matching transactions found")
        else:
            print("   ❌ PMS not detected")

    except Exception as e:
        print(f"❌ Error in PMS price fetching test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_pms_price_fetching()
