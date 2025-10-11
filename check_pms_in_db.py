#!/usr/bin/env python3
"""
Check if PMS prices are actually in the database
"""

from database_config_supabase import supabase

def check_pms_in_db():
    """Check if PMS prices are in the database"""

    print("🔍 Checking for PMS prices in database...")

    try:
        # Check historical_prices table directly
        result = supabase.table('historical_prices').select('*').execute()

        if not result.data:
            print("❌ No records in historical_prices table")
            return

        all_records = result.data
        print(f"✅ Found {len(all_records)} total records in historical_prices")

        # Find PMS records
        pms_records = []
        for record in all_records:
            ticker = record.get('ticker', '')
            ticker_upper = ticker.upper()

            if any(keyword in ticker_upper for keyword in ['PMS', 'AIF', 'BUOYANT', 'CARNELIAN']):
                pms_records.append(record)

        print(f"\n💼 PMS/AIF records found: {len(pms_records)}")

        if pms_records:
            print("📋 PMS records:")
            for record in pms_records:
                ticker = record.get('ticker', 'N/A')
                price = record.get('historical_price', 0)
                date = record.get('transaction_date', 'N/A')
                source = record.get('price_source', 'unknown')
                print(f"   {ticker}: ₹{price} on {date} ({source})")
        else:
            print("❌ No PMS records found in database")

        # Also check if our manually saved record is there
        manual_record = None
        for record in all_records:
            if (record.get('ticker') == 'BUOYANT_OPPORTUNITIES_PMS' and
                record.get('transaction_date') == '2024-01-06' and
                record.get('historical_price') == 7000000.0):
                manual_record = record
                break

        if manual_record:
            print("\n✅ Manual PMS record found:")
            print(f"   Ticker: {manual_record.get('ticker')}")
            print(f"   Price: ₹{manual_record.get('historical_price')}")
            print(f"   Date: {manual_record.get('transaction_date')}")
            print(f"   Source: {manual_record.get('price_source')}")
        else:
            print("\n❌ Manual PMS record NOT found in database")
    except Exception as e:
        print(f"❌ Error checking PMS in database: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_pms_in_db()
