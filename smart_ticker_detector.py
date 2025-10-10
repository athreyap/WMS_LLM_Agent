"""
Smart Ticker Detection System
Tries NSE, BSE, Mutual Fund, and PMS for all numeric codes
"""

import yfinance as yf
from mftool import Mftool
from indstocks_api import get_indstocks_client
import pandas as pd

def detect_and_fetch_price(ticker: str, date: str = None):
    """
    Smart detection: Try NSE → BSE → Mutual Fund → PMS for numeric tickers
    
    Args:
        ticker: Ticker code (can be numeric or text)
        date: Date in YYYY-MM-DD format (None for current price)
    
    Returns:
        dict with price, source, and type
    """
    ticker_str = str(ticker).strip()
    
    print(f"\n{'='*80}")
    print(f"🔍 Detecting ticker type for: {ticker_str}")
    print(f"{'='*80}")
    
    # For numeric tickers, try all possibilities
    if ticker_str.isdigit():
        print(f"📊 Numeric ticker detected - trying NSE, BSE, MF, PMS...")
        
        # 1. Try NSE (with .NS suffix)
        try:
            print(f"  1️⃣ Trying NSE: {ticker_str}.NS")
            stock = yf.Ticker(f"{ticker_str}.NS")
            if date:
                hist = stock.history(start=date, end=pd.to_datetime(date) + pd.Timedelta(days=1))
            else:
                hist = stock.history(period='1d')
            
            if not hist.empty:
                price = float(hist['Close'].iloc[0])
                print(f"  ✅ SUCCESS: NSE stock - Price: ₹{price}")
                return {'ticker': ticker_str, 'price': price, 'source': 'yfinance_nse', 'type': 'stock', 'exchange': 'NSE'}
            else:
                print(f"  ❌ No data from NSE")
        except Exception as e:
            print(f"  ❌ NSE failed: {str(e)[:50]}")
        
        # 2. Try BSE (with .BO suffix)
        try:
            print(f"  2️⃣ Trying BSE: {ticker_str}.BO")
            stock = yf.Ticker(f"{ticker_str}.BO")
            if date:
                hist = stock.history(start=date, end=pd.to_datetime(date) + pd.Timedelta(days=1))
            else:
                hist = stock.history(period='1d')
            
            if not hist.empty:
                price = float(hist['Close'].iloc[0])
                print(f"  ✅ SUCCESS: BSE stock - Price: ₹{price}")
                return {'ticker': ticker_str, 'price': price, 'source': 'yfinance_bse', 'type': 'stock', 'exchange': 'BSE'}
            else:
                print(f"  ❌ No data from BSE")
        except Exception as e:
            print(f"  ❌ BSE failed: {str(e)[:50]}")
        
        # 3. Try Mutual Fund (mftool)
        try:
            print(f"  3️⃣ Trying Mutual Fund: AMFI code {ticker_str}")
            mf = Mftool()
            quote = mf.get_scheme_quote(ticker_str)
            
            if quote and 'nav' in quote:
                price = float(quote['nav'])
                scheme_name = quote.get('scheme_name', 'Unknown Fund')
                print(f"  ✅ SUCCESS: Mutual Fund - NAV: ₹{price}")
                print(f"     Fund: {scheme_name}")
                return {'ticker': ticker_str, 'price': price, 'source': 'mftool', 'type': 'mutual_fund', 'scheme_name': scheme_name}
            else:
                print(f"  ❌ No data from mftool")
        except Exception as e:
            print(f"  ❌ Mutual Fund failed: {str(e)[:50]}")
        
        # 4. Try PMS (check if it's a known PMS)
        print(f"  4️⃣ Checking if PMS...")
        print(f"  ℹ️  PMS codes usually have text (INP...) or end with _PMS")
        print(f"  ❌ {ticker_str} is numeric - unlikely to be PMS")
        
        # 5. All failed
        print(f"\n❌ Could not identify {ticker_str} as NSE/BSE/MF/PMS")
        return {'ticker': ticker_str, 'price': None, 'source': 'unknown', 'type': 'unknown'}
    
    # For text tickers
    else:
        print(f"📊 Text ticker detected")
        
        # Check for PMS
        if (ticker_str.startswith('INP') or ticker_str.endswith('_PMS') or 
            ticker_str.endswith('PMS') or 'BUOYANT' in ticker_str or 
            'CARNELIAN' in ticker_str):
            print(f"  ✅ Detected as PMS")
            return {'ticker': ticker_str, 'price': None, 'source': 'pms', 'type': 'pms', 'note': 'Use SEBI calculation'}
        
        # Check for MF ISIN
        if ticker_str.startswith('INF') and len(ticker_str) == 12:
            print(f"  ✅ Detected as Mutual Fund ISIN")
            try:
                client = get_indstocks_client()
                result = client.get_stock_price(ticker_str, date)
                if result and result.get('price'):
                    return {'ticker': ticker_str, 'price': result['price'], 'source': 'indstocks', 'type': 'mutual_fund_isin'}
            except Exception as e:
                print(f"  ❌ indstocks failed: {e}")
            return {'ticker': ticker_str, 'price': None, 'source': 'indstocks', 'type': 'mutual_fund_isin'}
        
        # Regular stock - try NSE then BSE
        print(f"  Detected as stock ticker")
        
        # Try NSE
        try:
            ticker_ns = f"{ticker_str}.NS" if not ticker_str.endswith(('.NS', '.BO')) else ticker_str
            stock = yf.Ticker(ticker_ns)
            if date:
                hist = stock.history(start=date, end=pd.to_datetime(date) + pd.Timedelta(days=1))
            else:
                hist = stock.history(period='1d')
            
            if not hist.empty:
                price = float(hist['Close'].iloc[0])
                print(f"  ✅ SUCCESS: NSE stock - Price: ₹{price}")
                return {'ticker': ticker_str, 'price': price, 'source': 'yfinance_nse', 'type': 'stock', 'exchange': 'NSE'}
        except Exception as e:
            print(f"  ❌ NSE failed: {e}")
        
        # Try BSE
        try:
            ticker_bo = f"{ticker_str}.BO"
            stock = yf.Ticker(ticker_bo)
            if date:
                hist = stock.history(start=date, end=pd.to_datetime(date) + pd.Timedelta(days=1))
            else:
                hist = stock.history(period='1d')
            
            if not hist.empty:
                price = float(hist['Close'].iloc[0])
                print(f"  ✅ SUCCESS: BSE stock - Price: ₹{price}")
                return {'ticker': ticker_str, 'price': price, 'source': 'yfinance_bse', 'type': 'stock', 'exchange': 'BSE'}
        except Exception as e:
            print(f"  ❌ BSE failed: {e}")
        
        return {'ticker': ticker_str, 'price': None, 'source': 'unknown', 'type': 'unknown'}

def test_ticker_detection():
    """Test ticker detection with various types"""
    test_cases = [
        ('500414', 'BSE stock code'),
        ('100120', 'Mutual fund AMFI'),
        ('119019', 'Mutual fund AMFI'),
        ('INFY', 'NSE stock'),
        ('INF174K01KT2', 'Mutual fund ISIN'),
        ('INP000006387', 'PMS code'),
        ('BUOYANT_OPPORTUNITIES_PMS', 'PMS name'),
    ]
    
    print("\n" + "="*80)
    print("🧪 TESTING SMART TICKER DETECTION")
    print("="*80)
    
    for ticker, description in test_cases:
        print(f"\nTest: {ticker} ({description})")
        result = detect_and_fetch_price(ticker)
        print(f"\nResult:")
        for key, value in result.items():
            print(f"  {key}: {value}")
        print()

if __name__ == "__main__":
    test_ticker_detection()

