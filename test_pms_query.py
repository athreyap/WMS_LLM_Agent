#!/usr/bin/env python3
"""
Test PMS query specifically
"""

from database_config_supabase import supabase

def test_pms_query():
    """Test PMS query specifically"""

    print("🔍 Testing PMS query...")

    try:
        # Query specifically for PMS tickers
        pms_tickers = ['BUOYANT_OPPORTUNITIES_PMS', 'CARNELIAN_PMS']

        for ticker in pms_tickers:
            print(f"\n📊 Querying for ticker: {ticker}")

            result = supabase.table('historical_prices').select('*').eq('ticker', ticker).execute()

            if result.data:
                print(f"   ✅ Found {len(result.data)} records")
                for record in result.data:
                    print(f"      {record}")
            else:
                print("   ❌ No records found")

        # Also try a broader query for PMS-like tickers
        print("\n🔍 Broad query for PMS-like tickers...")
        result = supabase.table('historical_prices').select('*').ilike('ticker', '%PMS%').execute()

        if result.data:
            print(f"   ✅ Found {len(result.data)} PMS-like records")
            for record in result.data:
                print(f"      Ticker: {record.get('ticker')}, Price: {record.get('historical_price')}, Source: {record.get('price_source')}")
        else:
            print("   ❌ No PMS-like records found")

    except Exception as e:
        print(f"❌ Error in PMS query: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_pms_query()
