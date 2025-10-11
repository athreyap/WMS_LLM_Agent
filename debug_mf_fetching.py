#!/usr/bin/env python3
"""
Debug script to check why mutual fund price fetching is failing
"""

from mf_price_fetcher import extract_scheme_code_from_ticker, is_mutual_fund_ticker, get_mftool_client
from datetime import datetime

def debug_mf_price_fetching():
    """Debug mutual fund price fetching issues"""

    # Test tickers that should be stocks but might be misclassified as MF
    test_tickers = [
        'INFY',      # Infosys - should be stock, not MF
        'RELIANCE',  # Reliance - should be stock
        'TCS',       # TCS - should be stock
        '120828',    # Valid MF scheme code
        'MF_120828', # MF with prefix
        'HDFC_TOP_100', # MF with name-like ticker
    ]

    print("🔍 Testing mutual fund detection and price fetching...")

    for ticker in test_tickers:
        print(f"\n📊 Testing ticker: {ticker}")

        # Test detection
        is_mf_ticker = is_mutual_fund_ticker(ticker)
        scheme_code = extract_scheme_code_from_ticker(ticker)

        print(f"   🔍 is_mutual_fund_ticker: {is_mf_ticker}")
        print(f"   🔍 scheme_code: {scheme_code}")

        # Test if it matches the detection rules used in web_agent.py
        ticker_str = str(ticker).strip()
        detection_rules_match = (
            ticker_str.isdigit() or
            ticker_str.startswith('MF_') or
            ticker_str.startswith('INF') or  # ISIN codes start with INF
            len(ticker_str) == 12  # ISIN codes are 12 characters
        )

        # Test if it matches the stricter price fetching rules
        clean_ticker = str(ticker).strip().upper()
        clean_ticker = clean_ticker.replace('.NS', '').replace('.BO', '').replace('.NSE', '').replace('.BSE', '')
        price_fetching_rules_match = (
            (clean_ticker.isdigit() and len(clean_ticker) >= 5 and len(clean_ticker) <= 6 and clean_ticker.startswith(('1', '2'))) or
            clean_ticker.startswith('MF_')
        )

        print(f"   🔍 web_agent detection rules: {detection_rules_match}")
        print(f"   🔍 price_fetching rules: {price_fetching_rules_match}")

        # Test actual price fetching
        try:
            client = get_mftool_client()
            if client.available:
                nav_data = client.get_mutual_fund_nav_by_name(ticker, None)
                if nav_data:
                    print(f"   ✅ MF price fetch: ₹{nav_data['nav']} ({nav_data['source']})")
                else:
                    print("   ❌ MF price fetch: Failed")

                    # Try scheme code if available
                    if scheme_code:
                        nav_data = client.get_mutual_fund_nav(scheme_code, None)
                        if nav_data:
                            print(f"   ✅ MF price fetch (scheme code): ₹{nav_data['nav']} ({nav_data['source']})")
                        else:
                            print("   ❌ MF price fetch (scheme code): Failed")
            else:
                print("   ⚠️ MF client not available")

        except Exception as e:
            print(f"   ❌ Error in MF price fetch: {e}")

    # Test with actual problematic ticker from database
    print("\n🔥 Testing problematic tickers from database...")
    problematic_tickers = ['INFY']  # From the database results

    for ticker in problematic_tickers:
        print(f"\n🚨 Testing problematic ticker: {ticker}")

        # Check if it should be treated as stock or MF
        try:
            import yfinance as yf
            stock = yf.Ticker(f"{ticker}.NS")
            info = stock.history(period='1d')
            if not info.empty:
                current_price = float(info['Close'].iloc[-1])
                print(f"   ✅ Stock price fetch: ₹{current_price} (should be treated as stock)")
            else:
                print("   ❌ Stock price fetch failed")
        except Exception as e:
            print(f"   ❌ Stock price fetch error: {e}")

        # Check MF detection
        is_mf = is_mutual_fund_ticker(ticker)
        print(f"   🔍 MF detection result: {is_mf}")

if __name__ == "__main__":
    debug_mf_price_fetching()
