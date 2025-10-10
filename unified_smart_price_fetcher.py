#!/usr/bin/env python3
"""
Unified Smart Price Fetcher
Automatically detects investment type and uses the appropriate API
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def is_isin_code(ticker: str) -> bool:
    """Check if ticker is an ISIN code"""
    ticker_str = str(ticker).strip().upper()
    return ticker_str.startswith('INF') and len(ticker_str) == 12

def is_amfi_code(ticker: str) -> bool:
    """Check if ticker is an AMFI scheme code"""
    ticker_str = str(ticker).strip()
    return ticker_str.isdigit() and 5 <= len(ticker_str) <= 7

def is_pms_code(ticker: str) -> bool:
    """Check if ticker is a PMS code"""
    ticker_str = str(ticker).strip().upper()
    return ticker_str.startswith('INP')

def is_aif_code(ticker: str) -> bool:
    """Check if ticker is an AIF code"""
    ticker_str = str(ticker).strip().upper()
    return ticker_str.startswith('AIF') or 'AIF' in ticker_str or 'LEI:' in ticker_str

def is_invalid_ticker(ticker: str) -> bool:
    """Check if ticker has invalid format"""
    ticker_str = str(ticker).strip()
    return (
        '/' in ticker_str or
        'E+' in ticker_str.upper() or
        'E-' in ticker_str.upper() or
        len(ticker_str) > 25
    )

def get_price_smart(ticker: str, date: str = None, stock_name: str = None) -> Optional[Dict[str, Any]]:
    """
    Smart price fetcher that automatically detects investment type
    and uses the appropriate API
    
    Priority:
    1. Check for invalid tickers
    2. Check for PMS/AIF (use SEBI)
    3. Check for Mutual Fund ISIN (use indstocks)
    4. Check for Mutual Fund AMFI code (use mftool)
    5. Check for stock ticker (use yfinance with .NS/.BO, fallback to indstocks)
    
    Args:
        ticker (str): Investment ticker/code
        date (str): Date in YYYY-MM-DD format (optional)
        stock_name (str): Investment name for better matching (optional)
    
    Returns:
        dict with price data or None
    """
    ticker_str = str(ticker).strip()
    
    # 1. Check for invalid tickers
    if is_invalid_ticker(ticker_str):
        logger.warning(f"❌ Invalid ticker format: {ticker_str}")
        return {
            'ticker': ticker_str,
            'price': None,
            'error': 'Invalid ticker format',
            'note': 'Ticker contains invalid characters or format'
        }
    
    # 2. Check for PMS/AIF
    if is_pms_code(ticker_str) or is_aif_code(ticker_str):
        logger.info(f"🔍 PMS/AIF detected: {ticker_str}")
        try:
            from pms_aif_fetcher import get_alternative_investment_nav
            result = get_alternative_investment_nav(ticker_str, stock_name)
            if result:
                return {
                    'ticker': ticker_str,
                    'price': None,  # PMS/AIF don't have daily prices
                    'source': result.get('source'),
                    'pms_name': result.get('pms_name') or result.get('aif_name'),
                    'performance': result,
                    'note': 'PMS/AIF - use manual price entry or performance metrics'
                }
        except Exception as e:
            logger.warning(f"⚠️ PMS/AIF fetch failed: {e}")
        
        return {
            'ticker': ticker_str,
            'price': None,
            'note': 'PMS/AIF - manual price entry required'
        }
    
    # 3. Check for Mutual Fund ISIN
    if is_isin_code(ticker_str):
        logger.info(f"🔍 Mutual Fund ISIN detected: {ticker_str}")
        try:
            from indstocks_api import get_indstocks_client
            client = get_indstocks_client()
            result = client.get_stock_price(ticker_str, date)
            if result and result.get('price'):
                logger.info(f"✅ Got NAV from indstocks: ₹{result['price']}")
                return result
        except Exception as e:
            logger.warning(f"⚠️ indstocks failed for ISIN {ticker_str}: {e}")
        
        return {
            'ticker': ticker_str,
            'price': None,
            'error': 'Could not fetch NAV for ISIN',
            'note': 'Try using AMFI code instead'
        }
    
    # 4. Check for Mutual Fund AMFI code
    if is_amfi_code(ticker_str):
        logger.info(f"🔍 Mutual Fund AMFI code detected: {ticker_str}")
        try:
            from mf_price_fetcher import get_mftool_client
            client = get_mftool_client()
            result = client.get_mutual_fund_nav(int(ticker_str), date)
            if result and result.get('nav'):
                logger.info(f"✅ Got NAV from mftool: ₹{result['nav']}")
                return {
                    'ticker': ticker_str,
                    'price': result['nav'],
                    'source': 'mftool',
                    'scheme_name': result.get('scheme_name'),
                    'date': result.get('date')
                }
        except Exception as e:
            logger.warning(f"⚠️ mftool failed for AMFI code {ticker_str}: {e}")
        
        return {
            'ticker': ticker_str,
            'price': None,
            'error': 'Could not fetch NAV for AMFI code'
        }
    
    # 5. Stock ticker - try yfinance first, then indstocks
    logger.info(f"🔍 Stock ticker detected: {ticker_str}")
    
    # Try yfinance with .NS suffix
    try:
        import yfinance as yf
        from datetime import timedelta
        
        # Add .NS suffix if not present
        if not ticker_str.endswith(('.NS', '.BO')):
            ticker_with_suffix = f"{ticker_str}.NS"
        else:
            ticker_with_suffix = ticker_str
        
        if date:
            # For historical price
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            end_date = (date_obj + timedelta(days=1)).strftime('%Y-%m-%d')
            data = yf.download(ticker_with_suffix, start=date, end=end_date, progress=False)
            
            if data.empty and ticker_with_suffix.endswith('.NS'):
                # Try .BO if .NS failed
                ticker_with_suffix = ticker_str + '.BO'
                data = yf.download(ticker_with_suffix, start=date, end=end_date, progress=False)
        else:
            # For current price
            data = yf.download(ticker_with_suffix, period='1d', progress=False)
            
            if data.empty and ticker_with_suffix.endswith('.NS'):
                # Try .BO if .NS failed
                ticker_with_suffix = ticker_str + '.BO'
                data = yf.download(ticker_with_suffix, period='1d', progress=False)
        
        if not data.empty:
            price = data['Close'].iloc[-1]
            logger.info(f"✅ Got price from yfinance: ₹{price}")
            return {
                'ticker': ticker_str,
                'price': float(price),
                'source': 'yfinance',
                'date': date or data.index[-1].strftime('%Y-%m-%d')
            }
    except Exception as e:
        logger.warning(f"⚠️ yfinance failed for {ticker_str}: {e}")
    
    # Fallback to indstocks
    try:
        from indstocks_api import get_indstocks_client
        client = get_indstocks_client()
        result = client.get_stock_price(ticker_str, date)
        if result and result.get('price'):
            logger.info(f"✅ Got price from indstocks: ₹{result['price']}")
            return result
    except Exception as e:
        logger.warning(f"⚠️ indstocks failed for {ticker_str}: {e}")
    
    # All methods failed
    logger.error(f"❌ All price fetching methods failed for {ticker_str}")
    return {
        'ticker': ticker_str,
        'price': None,
        'error': 'Could not fetch price from any source',
        'note': 'Check if ticker is correct or use manual price entry'
    }

def test_smart_fetcher():
    """Test the smart price fetcher"""
    print("=" * 80)
    print("🧪 TESTING UNIFIED SMART PRICE FETCHER")
    print("=" * 80)
    
    test_cases = [
        ('INFY', 'Stock - NSE'),
        ('INF174K01KT2', 'Mutual Fund ISIN - Kotak Small Cap'),
        ('119019', 'Mutual Fund AMFI - DSP Aggressive Hybrid'),
        ('INP000006387', 'PMS - Carnelian Capital'),
        ('AIF:IN/AIF3/20-21/0857', 'AIF - Nuvama'),
        ('32613719/27', 'Invalid - Contains slash'),
        ('TANFACIND', 'Stock - May be delisted'),
    ]
    
    for ticker, description in test_cases:
        print(f"\n{'='*80}")
        print(f"Testing: {ticker}")
        print(f"Description: {description}")
        print(f"{'='*80}")
        
        result = get_price_smart(ticker)
        
        if result:
            print(f"Result:")
            for key, value in result.items():
                if key != 'performance':  # Skip verbose performance data
                    print(f"  {key}: {value}")
        else:
            print(f"❌ No result")
        print()

if __name__ == "__main__":
    test_smart_fetcher()

