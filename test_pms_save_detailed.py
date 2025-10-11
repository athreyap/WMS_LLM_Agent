#!/usr/bin/env python3
"""
Detailed test of PMS price saving
"""

from database_config_supabase import save_stock_price_supabase, get_stock_price_supabase, supabase
from datetime import datetime
import time

def test_pms_save_detailed():
    """Detailed test of PMS price saving"""

    test_cases = [
        {
            'ticker': 'BUOYANT_OPPORTUNITIES_PMS',
            'date': '2024-01-06',
            'price': 7000000.0,
            'source': 'pms_transaction_price'
        }
    ]

    print("🔍 Detailed PMS price saving test...")

    for case in test_cases:
        ticker = case['ticker']
        date = case['date']
        price = case['price']
        source = case['source']

        print(f"\n📊 Testing {ticker}...")

        # Step 1: Save the price
        print("   💾 Step 1: Saving price...")
        try:
            save_result = save_stock_price_supabase(ticker, date, price, source)
            print(f"   💾 Save result: {save_result}")
        except Exception as e:
            print(f"   ❌ Save error: {e}")
            continue

        # Step 2: Wait a moment for commit
        print("   ⏳ Step 2: Waiting for database commit...")
        time.sleep(1)

        # Step 3: Check if record exists in historical_prices table
        print("   🔍 Step 3: Checking historical_prices table...")
        try:
            result = supabase.table('historical_prices').select('*').eq('ticker', ticker).eq('transaction_date', date).execute()

            if result.data:
                print(f"   ✅ Found {len(result.data)} records in historical_prices")
                for record in result.data:
                    print(f"      Record: {record}")
            else:
                print("   ❌ No records found in historical_prices")

        except Exception as e:
            print(f"   ❌ Error checking historical_prices: {e}")

        # Step 4: Try to retrieve using get_stock_price_supabase
        print("   🔍 Step 4: Testing get_stock_price_supabase...")
        try:
            retrieved_price = get_stock_price_supabase(ticker, date)
            print(f"   🔍 Retrieved price: {retrieved_price}")

            if retrieved_price:
                print("   ✅ Price retrieval successful")
            else:
                print("   ❌ Price retrieval failed")
        except Exception as e:
            print(f"   ❌ Error retrieving price: {e}")

        # Step 5: Check if the issue is with the detection logic in check_investment_types.py
        print("   🔍 Step 5: Testing detection logic...")
        ticker_upper = ticker.upper()
        is_pms = any(keyword in ticker_upper for keyword in ['PMS', 'AIF', 'BUOYANT', 'CARNELIAN'])

        if is_pms:
            print("   ✅ PMS detection working correctly")
        else:
            print("   ❌ PMS detection failed")

if __name__ == "__main__":
    test_pms_save_detailed()
