#!/usr/bin/env python3
"""
Debug PMS detection in check_investment_types.py
"""

from database_config_supabase import supabase

def debug_pms_detection():
    """Debug why PMS records aren't being detected"""

    print("🔍 Debugging PMS detection...")

    try:
        # Get all records from historical_prices table
        result = supabase.table('historical_prices').select('*').execute()

        if not result.data:
            print("❌ No records in historical_prices table")
            return

        all_records = result.data
        print(f"✅ Found {len(all_records)} total records in historical_prices")

        # Find potential PMS records
        potential_pms = []
        for record in all_records:
            ticker = record.get('ticker', '')
            ticker_upper = ticker.upper()

            # Check if this looks like a PMS ticker
            pms_keywords = ['PMS', 'AIF', 'BUOYANT', 'CARNELIAN', 'JULIUS', 'VALENTIS', 'UNIFI']
            if any(keyword in ticker_upper for keyword in pms_keywords) or ticker_upper.endswith('_PMS'):
                potential_pms.append(record)

        print(f"\n💼 Potential PMS records found: {len(potential_pms)}")

        if potential_pms:
            print("📋 Potential PMS records:")
            for record in potential_pms:
                ticker = record.get('ticker', 'N/A')
                price = record.get('historical_price', 0)
                date = record.get('transaction_date', 'N/A')
                source = record.get('price_source', 'unknown')
                print(f"   {ticker}: ₹{price} on {date} ({source})")

                # Test the detection logic from check_investment_types.py
                ticker_upper = ticker.upper()
                pms_keywords = ['PMS', 'AIF', 'INP', 'BUOYANT', 'CARNELIAN', 'JULIUS', 'VALENTIS', 'UNIFI']
                is_pms = any(keyword in ticker_upper for keyword in pms_keywords) or ticker_upper.endswith('_PMS')

                print(f"   🔍 Detection test: {is_pms}")

                if is_pms:
                    print("   ✅ Should be detected as PMS")
                else:
                    print("   ❌ Should NOT be detected as PMS")
        else:
            print("❌ No potential PMS records found")

    except Exception as e:
        print(f"❌ Error debugging PMS detection: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_pms_detection()
