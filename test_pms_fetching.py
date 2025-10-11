#!/usr/bin/env python3
"""
Test PMS price fetching functionality
"""

from pms_aif_fetcher import get_pms_nav, is_pms_code, is_aif_code
from datetime import datetime

def test_pms_fetching():
    """Test PMS price fetching"""

    test_cases = [
        'BUOYANT_OPPORTUNITIES_PMS',
        'CARNELIAN_PMS',
        'INP123',
    ]

    print("🔍 Testing PMS price fetching...")

    for ticker in test_cases:
        print(f"\n📊 Testing PMS ticker: {ticker}")

        # Test PMS detection
        is_pms = is_pms_code(ticker)
        is_aif = is_aif_code(ticker)

        print(f"   🔍 is_pms_code: {is_pms}")
        print(f"   🔍 is_aif_code: {is_aif}")

        # Test PMS NAV fetching
        try:
            # Extract PMS name from ticker (remove _PMS suffix)
            pms_name = ticker.replace('_PMS', '').replace('_', ' ').title()
            print(f"   🔍 Extracted PMS name: {pms_name}")

            # Test PMS NAV fetching
            nav_data = get_pms_nav(ticker, pms_name, '2024-01-01', 1000000)

            if nav_data and nav_data.get('price'):
                print(f"   ✅ PMS NAV fetch successful: ₹{nav_data['price']}")
            else:
                print("   ❌ PMS NAV fetch failed or returned no price")
        except Exception as e:
            print(f"   ❌ PMS NAV fetch error: {e}")

if __name__ == "__main__":
    test_pms_fetching()
