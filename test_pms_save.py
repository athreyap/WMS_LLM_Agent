#!/usr/bin/env python3
"""
Test PMS price saving functionality
"""

from database_config_supabase import save_stock_price_supabase, get_stock_price_supabase
from datetime import datetime

def test_pms_save():
    """Test PMS price saving"""

    test_cases = [
        {
            'ticker': 'BUOYANT_OPPORTUNITIES_PMS',
            'date': '2024-01-06',
            'price': 7000000.0,
            'source': 'pms_transaction_price'
        },
        {
            'ticker': 'CARNELIAN_PMS',
            'date': '2024-01-01',
            'price': 5000000.0,
            'source': 'pms_transaction_price'
        }
    ]

    print("🔍 Testing PMS price saving...")

    for case in test_cases:
        ticker = case['ticker']
        date = case['date']
        price = case['price']
        source = case['source']

        print(f"\n📊 Testing {ticker}...")

        # Test saving
        try:
            save_result = save_stock_price_supabase(ticker, date, price, source)
            print(f"   💾 Save result: {save_result}")
        except Exception as e:
            print(f"   ❌ Save error: {e}")

        # Test retrieval
        try:
            retrieved_price = get_stock_price_supabase(ticker, date)
            print(f"   🔍 Retrieved price: {retrieved_price}")

            if retrieved_price and abs(float(retrieved_price) - price) < 0.01:
                print(f"   ✅ Save/Retrieve test PASSED for {ticker}")
            else:
                print(f"   ❌ Save/Retrieve test FAILED for {ticker}")
        except Exception as e:
            print(f"   ❌ Retrieve error: {e}")

if __name__ == "__main__":
    test_pms_save()
