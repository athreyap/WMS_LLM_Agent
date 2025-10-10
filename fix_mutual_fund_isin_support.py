"""
Fix for Mutual Fund ISIN Support
This script demonstrates how to properly fetch mutual fund prices using ISINs with indstocks
"""

from indstocks_api import get_indstocks_client, get_price_with_fallback
from mf_price_fetcher import get_mftool_client, is_mutual_fund_ticker
import pandas as pd

def is_isin_code(ticker: str) -> bool:
    """Check if ticker is an ISIN code"""
    ticker_str = str(ticker).strip().upper()
    # ISIN codes start with INF and are 12 characters long
    return ticker_str.startswith('INF') and len(ticker_str) == 12

def is_amfi_code(ticker: str) -> bool:
    """Check if ticker is an AMFI scheme code (numeric)"""
    ticker_str = str(ticker).strip()
    return ticker_str.isdigit() and len(ticker_str) >= 5 and len(ticker_str) <= 7

def is_pms_or_aif_code(ticker: str) -> bool:
    """Check if ticker is a PMS or AIF code"""
    ticker_str = str(ticker).strip().upper()
    return (
        ticker_str.startswith('INP') or  # PMS codes
        ticker_str.startswith('AIF:') or  # AIF codes
        'LEI:' in ticker_str  # LEI codes
    )

def is_invalid_ticker(ticker: str) -> bool:
    """Check if ticker has invalid format"""
    ticker_str = str(ticker).strip()
    return (
        '/' in ticker_str or  # Fractions
        'E+' in ticker_str.upper() or  # Scientific notation
        'E-' in ticker_str.upper() or
        len(ticker_str) > 20  # Extremely long codes
    )

def get_mutual_fund_price_smart(ticker: str, date: str = None) -> dict:
    """
    Smart mutual fund price fetcher that uses the right API based on ticker type
    
    Args:
        ticker: Can be ISIN code (INF...), AMFI code (numeric), or fund name
        date: Date in YYYY-MM-DD format (optional)
    
    Returns:
        dict with price data or None
    """
    ticker_str = str(ticker).strip()
    
    # Check for invalid tickers
    if is_invalid_ticker(ticker_str):
        print(f"❌ Invalid ticker format: {ticker_str}")
        return None
    
    # Check for PMS/AIF codes (can't fetch prices)
    if is_pms_or_aif_code(ticker_str):
        print(f"⚠️ PMS/AIF code detected: {ticker_str} - prices must be manually entered")
        return {'ticker': ticker_str, 'price': None, 'note': 'PMS/AIF - manual price entry required'}
    
    # ISIN codes -> use indstocks
    if is_isin_code(ticker_str):
        print(f"🔍 ISIN code detected: {ticker_str} - using indstocks")
        indstocks_client = get_indstocks_client()
        result = indstocks_client.get_stock_price(ticker_str, date)
        if result and result.get('price'):
            print(f"✅ Got price from indstocks: ₹{result['price']}")
            return result
        else:
            print(f"❌ indstocks failed for ISIN {ticker_str}")
            return None
    
    # AMFI codes -> use mftool
    elif is_amfi_code(ticker_str):
        print(f"🔍 AMFI code detected: {ticker_str} - using mftool")
        mftool_client = get_mftool_client()
        result = mftool_client.get_mutual_fund_nav(int(ticker_str), date)
        if result and result.get('nav'):
            print(f"✅ Got NAV from mftool: ₹{result['nav']}")
            return {'ticker': ticker_str, 'price': result['nav'], 'source': 'mftool', 'scheme_name': result.get('scheme_name')}
        else:
            print(f"❌ mftool failed for AMFI code {ticker_str}")
            return None
    
    # Stock ticker -> use indstocks with yfinance fallback
    else:
        print(f"🔍 Stock ticker detected: {ticker_str} - using indstocks/yfinance")
        indstocks_client = get_indstocks_client()
        result = get_price_with_fallback(ticker_str, date, indstocks_client)
        if result and result.get('price'):
            print(f"✅ Got price: ₹{result['price']} from {result.get('source')}")
            return result
        else:
            print(f"❌ Failed to get price for {ticker_str}")
            return None

def test_mutual_fund_isins():
    """Test mutual fund ISIN fetching"""
    print("=" * 80)
    print("🧪 TESTING MUTUAL FUND ISIN SUPPORT")
    print("=" * 80)
    
    # Test cases from Poornima.csv
    test_cases = [
        ('INF740K01NY4', 'DSP Aggressive Hybrid Fund'),
        ('INF179K01AS4', 'HDFC Hybrid Equity Fund'),
        ('INF109K01480', 'ICICI Prudential Equity & Debt Fund'),
        ('INF769K01DE6', 'Mirae Asset Aggressive Hybrid Fund'),
        ('INF174K01KT2', 'Kotak Small Cap Fund - Direct'),
        ('119019', 'DSP Aggressive Hybrid Fund - AMFI Code'),
        ('INFY', 'Infosys - Stock'),
        ('INP000006387', 'PMS Code'),
        ('32613719/27', 'Invalid ticker with slash'),
    ]
    
    print("\n")
    for ticker, name in test_cases:
        print(f"\n{'='*80}")
        print(f"Testing: {ticker} ({name})")
        print(f"{'='*80}")
        result = get_mutual_fund_price_smart(ticker)
        if result:
            print(f"✅ SUCCESS: {result}")
        else:
            print(f"❌ FAILED: No price data")
        print()

if __name__ == "__main__":
    test_mutual_fund_isins()

