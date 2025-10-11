#!/usr/bin/env python3
"""
Debug script to check mftool scheme codes functionality
"""

try:
    from mftool import Mftool
    mf = Mftool()

    print("🔍 Testing mftool scheme codes...")

    # Test get_scheme_codes
    print("📋 Testing get_scheme_codes()...")
    try:
        scheme_codes = mf.get_scheme_codes()
        print(f"✅ get_scheme_codes() returned {len(scheme_codes)} codes")
        print("Sample codes:", list(scheme_codes.keys())[:10])
    except Exception as e:
        print(f"❌ Error with get_scheme_codes(): {e}")

    # Test get_scheme_details for a known scheme code
    print("\n📋 Testing get_scheme_details() for scheme code 120828...")
    try:
        details = mf.get_scheme_details(120828)
        if details:
            print("✅ Scheme details found:")
            print(f"   Scheme Name: {details.get('scheme_name', 'N/A')}")
            print(f"   Scheme Code: {details.get('scheme_code', 'N/A')}")
            print(f"   Fund House: {details.get('fund_house', 'N/A')}")
        else:
            print("❌ No scheme details found")
    except Exception as e:
        print(f"❌ Error getting scheme details: {e}")

    # Test get_scheme_quote
    print("\n📋 Testing get_scheme_quote() for scheme code 120828...")
    try:
        quote = mf.get_scheme_quote(120828)
        if quote:
            print("✅ Scheme quote found:")
            print(f"   NAV: {quote.get('nav', 'N/A')}")
            print(f"   Date: {quote.get('date', 'N/A')}")
            print(f"   Scheme Name: {quote.get('scheme_name', 'N/A')}")
        else:
            print("❌ No scheme quote found")
    except Exception as e:
        print(f"❌ Error getting scheme quote: {e}")

except ImportError as e:
    print(f"❌ mftool not available: {e}")
except Exception as e:
    print(f"❌ Error testing mftool: {e}")
