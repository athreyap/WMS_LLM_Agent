#!/usr/bin/env python3
"""
Check database directly for PMS records
"""

from database_config_supabase import supabase

def check_db_directly():
    """Check database directly for PMS records"""

    print("🔍 Checking database directly for PMS records...")

    try:
        # Query historical_prices table for PMS tickers
        pms_tickers = ['BUOYANT_OPPORTUNITIES_PMS', 'CARNELIAN_PMS']

        for ticker in pms_tickers:
            print(f"\n📊 Checking for ticker: {ticker}")

            # Query for this specific ticker
            result = supabase.table('historical_prices').select('*').eq('ticker', ticker).execute()

            if result.data:
                print(f"   ✅ Found {len(result.data)} records for {ticker}")
                for record in result.data:
                    print(f"      ID: {record.get('id')}")
                    print(f"      Ticker: {record.get('ticker')}")
                    print(f"      Date: {record.get('transaction_date')}")
                    print(f"      Price: {record.get('historical_price')}")
                    print(f"      Source: {record.get('price_source')}")
                    print(f"      Created: {record.get('created_at')}")
            else:
                print(f"   ❌ No records found for {ticker}")

        # Also check if the table has any records at all
        result = supabase.table('historical_prices').select('count').execute()
        print(f"\n📊 Total records in historical_prices table: {result}")

    except Exception as e:
        print(f"❌ Error checking database directly: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_db_directly()
