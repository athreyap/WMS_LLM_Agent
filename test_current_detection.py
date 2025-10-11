#!/usr/bin/env python3
"""
Test current detection logic for different investment types
"""

def test_detection_logic():
    """Test the current detection logic"""

    test_cases = [
        # Stocks (should NOT be detected as MF)
        ('INFY', False, 'Stock'),
        ('RELIANCE', False, 'Stock'),
        ('TCS', False, 'Stock'),
        ('HDFCBANK', False, 'Stock'),

        # Valid Mutual Funds (should be detected as MF)
        ('120828', True, 'MF'),
        ('145231', True, 'MF'),
        ('MF_120828', True, 'MF'),

        # PMS/AIF (should NOT be detected as MF)
        ('BUOYANT_OPPORTUNITIES_PMS', False, 'PMS'),
        ('CARNELIAN_PMS', False, 'PMS'),
        ('INP123', False, 'PMS'),

        # Edge cases
        ('123', False, 'Too short for MF'),
        ('1234567', False, 'Too long for MF'),
        ('INF123456', False, 'ISIN-like but not numeric'),
    ]

    print("🔍 Testing current detection logic...")

    for ticker, expected_mf, expected_type in test_cases:
        # Test MF detection (current logic)
        ticker_str = str(ticker).strip()
        is_mutual_fund = (
            (ticker_str.isdigit() and len(ticker_str) >= 5 and len(ticker_str) <= 6) or
            ticker_str.startswith('MF_')
        )

        # Test PMS detection
        ticker_upper = ticker.upper()
        pms_keywords = ['PMS', 'AIF', 'INP', 'BUOYANT', 'CARNELIAN', 'JULIUS', 'VALENTIS', 'UNIFI']
        is_pms = any(keyword in ticker_upper for keyword in pms_keywords) or ticker_upper.endswith('_PMS')

        print(f"\n📊 Ticker: {ticker}")
        print(f"   Expected MF: {expected_mf}, Detected MF: {is_mutual_fund}")
        print(f"   Expected PMS: {expected_type == 'PMS'}, Detected PMS: {is_pms}")

        if is_mutual_fund != expected_mf:
            print(f"   ❌ MF DETECTION MISMATCH!")
        else:
            print(f"   ✅ MF detection correct")

        if is_pms and expected_type != 'PMS':
            print(f"   ❌ PMS DETECTION MISMATCH!")
        elif not is_pms and expected_type == 'PMS':
            print(f"   ❌ PMS DETECTION MISMATCH!")
        else:
            print(f"   ✅ PMS detection correct")

if __name__ == "__main__":
    test_detection_logic()
