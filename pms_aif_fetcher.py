#!/usr/bin/env python3
"""
PMS and AIF Price Fetcher for WMS-LLM
Handles fetching NAV/performance data for PMS and AIF from SEBI website
"""

import pandas as pd
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_pms_aif_from_csv(ticker: str, csv_path: str = 'pms_aif_performance.csv') -> Optional[Dict[str, Any]]:
    """
    Load PMS/AIF performance data from a local CSV file
    
    This is a fallback method when SEBI data is unavailable.
    Update the CSV file quarterly with data from fund manager reports.
    
    Args:
        ticker: PMS/AIF registration code
        csv_path: Path to CSV file with performance data
    
    Returns:
        Dict with performance data or None
    """
    try:
        import os
        
        if not os.path.exists(csv_path):
            logger.debug(f"CSV file not found: {csv_path}")
            return None
        
        df = pd.read_csv(csv_path)
        
        # Find matching ticker
        match = df[df['ticker'] == ticker]
        
        if match.empty:
            logger.debug(f"Ticker {ticker} not found in CSV")
            return None
        
        row = match.iloc[0]
        
        # Check if performance data is available
        has_data = False
        result = {
            'ticker': ticker,
            'name': row.get('name', ticker),
            'source': 'local_csv',
            'last_updated': row.get('last_updated', 'N/A')
        }
        
        # Add performance metrics if available
        for key in ['1y_return', '3y_cagr', '5y_cagr', '1m_return', '3m_return', '6m_return']:
            value = row.get(key)
            if pd.notna(value) and str(value).strip() != '':
                result[key] = str(value).strip()
                has_data = True
        
        if not has_data:
            logger.warning(f"CSV entry for {ticker} exists but has no performance data")
            return None
        
        logger.info(f"✅ Loaded {ticker} performance data from CSV (updated: {result['last_updated']})")
        return result
    
    except Exception as e:
        logger.error(f"Error reading CSV for {ticker}: {e}")
        return None

def is_pms_code(ticker: str) -> bool:
    """Check if ticker is a PMS registration code"""
    ticker_str = str(ticker).strip().upper()
    # Match the detection logic from web_agent.py
    pms_keywords = ['PMS', 'INP', 'BUOYANT', 'CARNELIAN', 'JULIUS', 'VALENTIS', 'UNIFI']
    return (any(keyword in ticker_str for keyword in pms_keywords) or
            ticker_str.endswith('_PMS') or
            ticker_str.startswith('INP'))

def is_aif_code(ticker: str) -> bool:
    """Check if ticker is an AIF registration code"""
    ticker_str = str(ticker).strip().upper()
    return ticker_str.startswith('AIF') or 'AIF' in ticker_str

def get_pms_nav_from_sebi(pms_name: str = None, registration_code: str = None) -> Optional[pd.DataFrame]:
    """
    Fetch PMS NAV/performance data from SEBI website
    
    Args:
        pms_name (str): Name of PMS (e.g., 'Buoyant', 'Carnelian', 'Julius Baer')
        registration_code (str): PMS registration code (e.g., 'INP000006387')
    
    Returns:
        DataFrame with PMS data or None if not found
    """
    try:
        logger.info(f"🔍 Fetching PMS data from SEBI for: {pms_name or registration_code}")
        
        # SEBI PMS disclosure URL
        url = "https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doPmr=yes"
        
        # Read all tables from the page with headers to avoid being blocked
        import requests
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        try:
            # Fetch HTML with custom headers first
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            tables = pd.read_html(response.text)
        except ValueError as ve:
            # "No tables found" error
            logger.warning(f"⚠️ SEBI website returned no tables (website may be down or structure changed): {ve}")
            return None
        
        if not tables:
            logger.warning("No tables found on SEBI PMS page")
            return None
        
        # Concatenate all tables
        df = pd.concat(tables, ignore_index=True)
        
        # Check if we have the expected columns
        if 'Portfolio Manager' not in df.columns:
            logger.warning("No 'Portfolio Manager' column found. SEBI site structure may have changed.")
            logger.info(f"Available columns: {df.columns.tolist()}")
            return None
        
        # Search by name or registration code
        if pms_name:
            # Clean the PMS name for searching
            search_term = pms_name.replace("_", " ").replace("-", " ")
            match = df[df['Portfolio Manager'].str.contains(search_term, case=False, na=False)]
        elif registration_code:
            # Try to find by registration code
            # First check if there's a Registration column
            if 'Registration No.' in df.columns or 'Registration Number' in df.columns:
                reg_col = 'Registration No.' if 'Registration No.' in df.columns else 'Registration Number'
                match = df[df[reg_col].str.contains(registration_code, case=False, na=False)]
            else:
                # Fallback: Registration codes sometimes appear in the Portfolio Manager name
                # Search for the code in Portfolio Manager column
                logger.info(f"Registration column not found, searching for code in Portfolio Manager name")
                match = df[df['Portfolio Manager'].str.contains(registration_code, case=False, na=False)]
                
            # If still not found by code, caller will retry with name
        else:
            logger.warning("Either pms_name or registration_code must be provided")
            return None
        
        if match.empty:
            logger.warning(f"No PMS data found for: {pms_name or registration_code}")
            return None
        
        logger.info(f"✅ Found {len(match)} PMS records")
        return match
        
    except Exception as e:
        logger.error(f"Error fetching PMS data from SEBI: {e}")
        return None

def calculate_current_value(initial_investment: float, investment_date: str, returns_data: Dict[str, str]) -> Dict[str, Any]:
    """
    Calculate current value based on investment date and SEBI returns data
    
    Args:
        initial_investment (float): Initial investment amount
        investment_date (str): Investment date in YYYY-MM-DD format
        returns_data (dict): Dictionary with return keys like '1m_return', '1y_return', '3y_cagr', '5y_cagr'
    
    Returns:
        dict with calculated values
    """
    from dateutil.relativedelta import relativedelta
    
    try:
        inv_date = datetime.strptime(investment_date, '%Y-%m-%d')
        current_date = datetime.now()
        
        # Calculate time elapsed
        months_elapsed = (current_date.year - inv_date.year) * 12 + (current_date.month - inv_date.month)
        years_elapsed = months_elapsed / 12.0
        
        logger.info(f"📅 Investment period: {years_elapsed:.2f} years ({months_elapsed} months)")
        
        # Determine which return to use based on investment period
        current_value = initial_investment
        return_used = None
        return_period = None
        
        if years_elapsed >= 5 and '5y_cagr' in returns_data:
            # Use 5Y CAGR
            cagr_str = returns_data['5y_cagr']
            if cagr_str and cagr_str != 'N/A':
                cagr = float(cagr_str.replace('%', '').strip()) / 100
                current_value = initial_investment * ((1 + cagr) ** years_elapsed)
                return_used = cagr
                return_period = '5Y CAGR'
        
        elif years_elapsed >= 3 and '3y_cagr' in returns_data:
            # Use 3Y CAGR
            cagr_str = returns_data['3y_cagr']
            if cagr_str and cagr_str != 'N/A':
                cagr = float(cagr_str.replace('%', '').strip()) / 100
                current_value = initial_investment * ((1 + cagr) ** years_elapsed)
                return_used = cagr
                return_period = '3Y CAGR'
        
        elif years_elapsed >= 1 and '1y_return' in returns_data:
            # Use 1Y Return (annualized for the period)
            return_str = returns_data['1y_return']
            if return_str and return_str != 'N/A':
                annual_return = float(return_str.replace('%', '').strip()) / 100
                current_value = initial_investment * ((1 + annual_return) ** years_elapsed)
                return_used = annual_return
                return_period = '1Y Return'
        
        elif months_elapsed >= 6 and '6m_return' in returns_data:
            # Use 6M Return (annualized)
            return_str = returns_data['6m_return']
            if return_str and return_str != 'N/A':
                six_month_return = float(return_str.replace('%', '').strip()) / 100
                annual_return = ((1 + six_month_return) ** 2) - 1  # Annualize 6M return
                current_value = initial_investment * ((1 + annual_return) ** years_elapsed)
                return_used = annual_return
                return_period = '6M Return (annualized)'
        
        elif months_elapsed >= 3 and '3m_return' in returns_data:
            # Use 3M Return (annualized)
            return_str = returns_data['3m_return']
            if return_str and return_str != 'N/A':
                three_month_return = float(return_str.replace('%', '').strip()) / 100
                annual_return = ((1 + three_month_return) ** 4) - 1  # Annualize 3M return
                current_value = initial_investment * ((1 + annual_return) ** years_elapsed)
                return_used = annual_return
                return_period = '3M Return (annualized)'
        
        elif months_elapsed >= 1 and '1m_return' in returns_data:
            # Use 1M Return (annualized)
            return_str = returns_data['1m_return']
            if return_str and return_str != 'N/A':
                one_month_return = float(return_str.replace('%', '').strip()) / 100
                annual_return = ((1 + one_month_return) ** 12) - 1  # Annualize 1M return
                current_value = initial_investment * ((1 + annual_return) ** years_elapsed)
                return_used = annual_return
                return_period = '1M Return (annualized)'
        
        # Calculate gains
        absolute_gain = current_value - initial_investment
        percentage_gain = (absolute_gain / initial_investment) * 100 if initial_investment > 0 else 0
        
        result = {
            'initial_investment': initial_investment,
            'current_value': current_value,
            'absolute_gain': absolute_gain,
            'percentage_gain': percentage_gain,
            'years_elapsed': years_elapsed,
            'months_elapsed': months_elapsed,
            'return_used': return_used,
            'return_period': return_period,
            'calculation_method': 'SEBI returns-based calculation'
        }
        
        logger.info(f"💰 Calculated: ₹{initial_investment:,.2f} → ₹{current_value:,.2f} (using {return_period})")
        
        return result
        
    except Exception as e:
        logger.error(f"Error calculating current value: {e}")
        return {
            'initial_investment': initial_investment,
            'current_value': initial_investment,
            'absolute_gain': 0,
            'percentage_gain': 0,
            'error': str(e)
        }

def get_pms_nav(ticker: str, pms_name: str = None, investment_date: str = None, investment_amount: float = None) -> Optional[Dict[str, Any]]:
    """
    Get PMS NAV/performance data and calculate current value
    
    Args:
        ticker (str): PMS registration code (e.g., 'INP000006387')
        pms_name (str): Optional PMS name for better matching
        investment_date (str): Investment date in YYYY-MM-DD format (for value calculation)
        investment_amount (float): Initial investment amount (for value calculation)
    
    Returns:
        dict with PMS data and calculated current value or None
    """
    try:
        # PRIORITY 1: Check local CSV file first (most reliable)
        csv_data = get_pms_aif_from_csv(ticker)
        if csv_data:
            logger.info(f"📁 Using CSV data for {ticker}")
            
            # If investment details provided, calculate current value
            if investment_date and investment_amount:
                returns_data = {}
                for key in ['1m_return', '3m_return', '6m_return', '1y_return', '3y_cagr', '5y_cagr']:
                    if key in csv_data:
                        returns_data[key] = csv_data[key]
                
                calculation = calculate_current_value(investment_amount, investment_date, returns_data)
                csv_data['calculated_value'] = calculation
                csv_data['price'] = calculation['current_value']
            
            return csv_data
        
        # PRIORITY 2: Extract PMS name from ticker if not provided
        if not pms_name and not is_pms_code(ticker):
            # Try to extract name from ticker
            pms_name = ticker
        
        # PRIORITY 3: Try to fetch from SEBI
        if is_pms_code(ticker):
            # Try with registration code first
            sebi_data = get_pms_nav_from_sebi(registration_code=ticker)
            
            # If not found by code, try with name
            if sebi_data is None and pms_name:
                sebi_data = get_pms_nav_from_sebi(pms_name=pms_name)
        else:
            # Try with name
            sebi_data = get_pms_nav_from_sebi(pms_name=ticker)
        
        if sebi_data is not None and not sebi_data.empty:
            # Extract relevant information
            first_record = sebi_data.iloc[0]
            
            result = {
                'ticker': ticker,
                'pms_name': first_record.get('Portfolio Manager', pms_name),
                'strategy': first_record.get('Strategy', 'N/A'),
                'source': 'sebi_pms',
                'date': datetime.now().strftime('%Y-%m-%d'),
            }
            
            # Extract performance metrics
            returns_data = {}
            performance_cols = {
                '1M Return': '1m_return',
                '3M Return': '3m_return',
                '6M Return': '6m_return',
                '1Y Return': '1y_return',
                '3Y CAGR': '3y_cagr',
                '5Y CAGR': '5y_cagr'
            }
            
            for col, key in performance_cols.items():
                if col in first_record:
                    value = first_record[col]
                    result[key] = value
                    returns_data[key] = value
            
            # Add AUM if available
            if 'AUM (Cr.)' in first_record:
                result['aum_cr'] = first_record['AUM (Cr.)']
            
            # Calculate current value if investment details provided
            if investment_date and investment_amount:
                calculation = calculate_current_value(investment_amount, investment_date, returns_data)
                result['calculated_value'] = calculation
                result['price'] = calculation['current_value']  # For compatibility with other price fetchers
            
            logger.info(f"✅ Successfully fetched PMS data for {ticker}")
            return result
        
        # FALLBACK: If SEBI data not available, return None (no fake estimates)
        logger.warning(f"⚠️ No PMS data found for {ticker} from SEBI")
        logger.info(f"💡 Real-time SEBI data unavailable - will show 0% return (honest)")
        
        # DO NOT generate fake estimated values
        # Better to show 0% return than misleading estimates
        return None
        
    except Exception as e:
        logger.error(f"Error getting PMS NAV for {ticker}: {e}")
        return None

def get_aif_nav_from_sebi(aif_name: str = None, registration_code: str = None) -> Optional[pd.DataFrame]:
    """
    Fetch AIF NAV/performance data from SEBI website
    
    Args:
        aif_name (str): Name of AIF
        registration_code (str): AIF registration code
    
    Returns:
        DataFrame with AIF data or None if not found
    """
    try:
        logger.info(f"🔍 Fetching AIF data from SEBI for: {aif_name or registration_code}")
        
        # SEBI AIF disclosure URL (may need to be updated based on SEBI's current structure)
        # Note: SEBI AIF data might be on a different page
        url = "https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRecognisedFpi=yes&type=aif"
        
        # Add headers to avoid being blocked
        import requests
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        try:
            # Fetch HTML with custom headers first
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            tables = pd.read_html(response.text)
        except ValueError as ve:
            logger.warning(f"⚠️ SEBI AIF website returned no tables (website may be down or structure changed): {ve}")
            return None
            
        if not tables:
            logger.warning("No AIF tables found on SEBI page")
            return None
        
        df = pd.concat(tables, ignore_index=True)
        
        # Search by name or registration code
        if aif_name:
            search_term = aif_name.replace("_", " ").replace("-", " ")
            match = df[df.apply(lambda row: row.astype(str).str.contains(search_term, case=False, na=False).any(), axis=1)]
        elif registration_code:
            match = df[df.apply(lambda row: row.astype(str).str.contains(registration_code, case=False, na=False).any(), axis=1)]
        else:
            return None
        
        if match.empty:
            logger.warning(f"No AIF data found for: {aif_name or registration_code}")
            return None
        
        logger.info(f"✅ Found {len(match)} AIF records")
        return match
        
    except Exception as e:
        logger.error(f"Error fetching AIF data from SEBI: {e}")
        return None

def get_aif_nav(ticker: str, aif_name: str = None, investment_date: str = None, investment_amount: float = None) -> Optional[Dict[str, Any]]:
    """
    Get AIF NAV/performance data
    
    Args:
        ticker (str): AIF registration code or name
        aif_name (str): Optional AIF name for better matching
        investment_date (str): Investment date in YYYY-MM-DD format (for value calculation)
        investment_amount (float): Initial investment amount (for value calculation)
    
    Returns:
        dict with AIF data or None
    """
    try:
        # PRIORITY 1: Check local CSV file first (most reliable)
        csv_data = get_pms_aif_from_csv(ticker)
        if csv_data:
            logger.info(f"📁 Using CSV data for {ticker}")
            
            # If investment details provided, calculate current value
            if investment_date and investment_amount:
                returns_data = {}
                for key in ['1m_return', '3m_return', '6m_return', '1y_return', '3y_cagr', '5y_cagr']:
                    if key in csv_data:
                        returns_data[key] = csv_data[key]
                
                calculation = calculate_current_value(investment_amount, investment_date, returns_data)
                csv_data['calculated_value'] = calculation
                csv_data['price'] = calculation['current_value']
            
            return csv_data
        
        # PRIORITY 2: Try to fetch from SEBI
        sebi_data = None
        
        if is_aif_code(ticker):
            sebi_data = get_aif_nav_from_sebi(registration_code=ticker)
            if sebi_data is None and aif_name:
                sebi_data = get_aif_nav_from_sebi(aif_name=aif_name)
        else:
            sebi_data = get_aif_nav_from_sebi(aif_name=ticker)
        
        if sebi_data is not None and not sebi_data.empty:
            first_record = sebi_data.iloc[0]
            
            result = {
                'ticker': ticker,
                'aif_name': aif_name or ticker,
                'source': 'sebi_aif',
                'date': datetime.now().strftime('%Y-%m-%d'),
                'data': first_record.to_dict()
            }
            
            # Calculate current value if investment details provided
            if investment_date and investment_amount:
                # Extract returns data (AIF might have different column names)
                returns_data = {}
                performance_cols = {
                    '1Y Return': '1y_return',
                    '3Y CAGR': '3y_cagr',
                    '5Y CAGR': '5y_cagr'
                }
                
                for col, key in performance_cols.items():
                    if col in first_record:
                        returns_data[key] = first_record[col]
                
                calculation = calculate_current_value(investment_amount, investment_date, returns_data)
                result['calculated_value'] = calculation
                result['price'] = calculation['current_value']
            
            logger.info(f"✅ Successfully fetched AIF data for {ticker}")
            return result
        
        # FALLBACK: If SEBI data not available, return None (no fake estimates)
        logger.warning(f"⚠️ No AIF data found for {ticker} from SEBI")
        logger.info(f"💡 Real-time SEBI data unavailable - will show 0% return (honest)")
        
        # DO NOT generate fake estimated values
        # Better to show 0% return than misleading estimates
        return None
        
    except Exception as e:
        logger.error(f"Error getting AIF NAV for {ticker}: {e}")
        return None

def get_alternative_investment_nav(ticker: str, investment_name: str = None) -> Optional[Dict[str, Any]]:
    """
    Smart fetcher for alternative investments (PMS/AIF)
    
    Args:
        ticker (str): Investment code or name
        investment_name (str): Optional investment name
    
    Returns:
        dict with NAV/performance data or None
    """
    # Determine investment type
    if is_pms_code(ticker) or (investment_name and 'pms' in investment_name.lower()):
        logger.info(f"🔍 Detected PMS: {ticker}")
        return get_pms_nav(ticker, investment_name)
    
    elif is_aif_code(ticker) or (investment_name and 'aif' in investment_name.lower()):
        logger.info(f"🔍 Detected AIF: {ticker}")
        return get_aif_nav(ticker, investment_name)
    
    else:
        # Try both
        logger.info(f"🔍 Unknown type, trying both PMS and AIF for: {ticker}")
        
        pms_data = get_pms_nav(ticker, investment_name)
        if pms_data:
            return pms_data
        
        aif_data = get_aif_nav(ticker, investment_name)
        if aif_data:
            return aif_data
        
        logger.warning(f"⚠️ No data found for {ticker} in PMS or AIF")
        return None

# Test function
def test_pms_fetcher():
    """Test PMS fetcher with known PMS names"""
    print("=" * 80)
    print("🧪 TESTING PMS/AIF FETCHER")
    print("=" * 80)
    
    test_cases = [
        ('INP000006387', 'Carnelian Capital'),
        ('INP000007012', 'Julius Baer'),
        ('Buoyant', None),
        ('Marcellus', None),
    ]
    
    for ticker, name in test_cases:
        print(f"\n{'='*80}")
        print(f"Testing: {ticker} ({name})")
        print(f"{'='*80}")
        
        result = get_alternative_investment_nav(ticker, name)
        
        if result:
            print(f"✅ SUCCESS:")
            for key, value in result.items():
                print(f"  {key}: {value}")
        else:
            print(f"❌ FAILED: No data found")
        print()

if __name__ == "__main__":
    test_pms_fetcher()

