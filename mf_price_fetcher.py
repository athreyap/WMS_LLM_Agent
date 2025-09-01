#!/usr/bin/env python3
"""
Mutual Fund Price Fetcher for WMS-LLM
Handles fetching mutual fund NAVs using mftool library
"""

import pandas as pd
from datetime import datetime, timedelta
import time
import logging
from typing import Optional, Dict, Any, List
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MFToolClient:
    """Mutual Fund client for fetching NAV data using mftool library"""
    
    def __init__(self):
        """Initialize MFTool client"""
        try:
            from mftool import Mftool
            self.mf = Mftool()
            self.available = True
            logger.info("MFTool client initialized successfully")
        except ImportError:
            logger.error("mftool library not available. Please install with: pip install mftool")
            self.available = False
        except Exception as e:
            logger.error(f"Error initializing MFTool client: {str(e)}")
            self.available = False
    
    def get_scheme_code_from_name(self, fund_name: str) -> Optional[int]:
        """
        Get AMFI scheme code from mutual fund name
        
        Args:
            fund_name (str): Mutual fund name (e.g., 'HDFC Mid-Cap Opportunities Fund')
            
        Returns:
            int: AMFI scheme code or None if not found
        """
        if not self.available:
            return None
            
        try:
            # Search for the fund by name
            search_results = self.mf.search_schemes(fund_name)
            
            if search_results and len(search_results) > 0:
                # Return the first matching scheme code
                return search_results[0].get('schemeCode')
            
            return None
            
        except Exception as e:
            logger.error(f"Error searching for scheme code for {fund_name}: {str(e)}")
            return None
    
    def get_mutual_fund_nav(self, scheme_code: int, date: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Fetches current NAV and recent NAV history for a mutual fund scheme.
        
        Args:
            scheme_code (int): AMFI mutual fund scheme code (e.g., 120828 for a specific fund).
            date (str): Date in YYYY-MM-DD format (optional, defaults to latest)
            
        Returns:
            dict: {
                'scheme_code': int,
                'scheme_name': str,
                'nav': float,
                'date': str,
                'source': str
            }
        """
        if not self.available:
            return None
            
        try:
            # If specific date requested, try to get historical NAV first
            if date:
                logger.info(f"🔍 Fetching historical NAV for scheme {scheme_code} on {date}")
                try:
                    hist_df = self.mf.get_scheme_historical_nav(scheme_code, as_Dataframe=True)
                    if not hist_df.empty:
                        # Convert index (date) to column and parse dates
                        hist_df = hist_df.reset_index()
                        hist_df['date'] = pd.to_datetime(hist_df['date'], format='%d-%m-%Y', errors='coerce')
                        target_date = pd.to_datetime(date)
                        
                        # Remove rows with invalid dates
                        hist_df = hist_df.dropna(subset=['date'])
                        
                        if not hist_df.empty:
                            # Find exact match or closest date
                            exact_match = hist_df[hist_df['date'] == target_date]
                            if not exact_match.empty:
                                nav_data = {
                                    'scheme_code': scheme_code,
                                    'scheme_name': 'Unknown',  # Historical data doesn't include scheme name
                                    'nav': float(exact_match.iloc[0]['nav']),
                                    'date': exact_match.iloc[0]['date'].strftime('%Y-%m-%d'),
                                    'source': 'mftool_historical'
                                }
                                logger.info(f"✅ Historical NAV found for {scheme_code}: ₹{nav_data['nav']} on {nav_data['date']}")
                                return nav_data
                            else:
                                # Find closest date within 30 days (more flexible for mutual funds)
                                date_diff = abs(hist_df['date'] - target_date)
                                closest_idx = date_diff.idxmin()
                                if date_diff[closest_idx] <= pd.Timedelta(days=30):
                                    nav_data = {
                                        'scheme_code': scheme_code,
                                        'scheme_name': 'Unknown',  # Historical data doesn't include scheme name
                                        'nav': float(hist_df.iloc[closest_idx]['nav']),
                                        'date': hist_df.iloc[closest_idx]['date'].strftime('%Y-%m-%d'),
                                        'source': 'mftool_historical'
                                    }
                                    logger.info(f"✅ Closest historical NAV found for {scheme_code}: ₹{nav_data['nav']} on {nav_data['date']}")
                                    return nav_data
                                else:
                                    logger.warning(f"⚠️ No historical NAV found within 30 days for {scheme_code} on {date}")
                        else:
                            logger.warning(f"⚠️ No valid dates found in historical data for scheme {scheme_code}")
                    else:
                        logger.warning(f"⚠️ No historical data available for scheme {scheme_code}")
                except Exception as e:
                    logger.warning(f"Could not fetch historical NAV for {scheme_code} on {date}: {str(e)}")
            
            # If no date specified or historical fetch failed, get current NAV
            logger.info(f"🔍 Fetching current NAV for scheme {scheme_code}")
            quote = self.mf.get_scheme_quote(scheme_code)
            
            if not quote or 'nav' not in quote:
                logger.warning(f"No NAV data found for scheme code {scheme_code}")
                return None
            
            nav_data = {
                'scheme_code': scheme_code,
                'scheme_name': quote.get('scheme_name', 'Unknown'),
                'nav': float(quote.get('nav', 0)),
                'date': quote.get('date', datetime.now().strftime('%Y-%m-%d')),
                'source': 'mftool'
            }
            
            logger.info(f"✅ Current NAV found for {scheme_code}: ₹{nav_data['nav']} on {nav_data['date']}")
            return nav_data
            
        except Exception as e:
            logger.error(f"Error fetching NAV for scheme code {scheme_code}: {str(e)}")
            return None
    
    def get_mutual_fund_nav_by_name(self, fund_name: str, date: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Fetches NAV for a mutual fund by name
        
        Args:
            fund_name (str): Mutual fund name
            date (str): Date in YYYY-MM-DD format (optional)
            
        Returns:
            dict: NAV data or None if not found
        """
        scheme_code = self.get_scheme_code_from_name(fund_name)
        if scheme_code:
            return self.get_mutual_fund_nav(scheme_code, date)
        return None
    
    def get_bulk_navs(self, scheme_codes: List[int], date: Optional[str] = None) -> Dict[int, Any]:
        """
        Get NAVs for multiple scheme codes
        
        Args:
            scheme_codes (list): List of AMFI scheme codes
            date (str): Date in YYYY-MM-DD format (optional)
            
        Returns:
            dict: Dictionary mapping scheme codes to NAV data
        """
        results = {}
        
        for scheme_code in scheme_codes:
            if scheme_code:
                nav_data = self.get_mutual_fund_nav(scheme_code, date)
                if nav_data:
                    results[scheme_code] = nav_data
                
                # Rate limiting
                time.sleep(0.2)
        
        return results

def extract_scheme_code_from_ticker(ticker: str) -> Optional[int]:
    """
    Extract AMFI scheme code from ticker symbol
    
    Args:
        ticker (str): Ticker symbol (e.g., 'MF_120828', '120828', 'HDFC_MIDCAP')
        
    Returns:
        int: AMFI scheme code or None if not found
    """
    try:
        # Pattern 1: MF_ followed by numbers (e.g., MF_120828)
        match = re.search(r'MF_(\d+)', ticker, re.IGNORECASE)
        if match:
            return int(match.group(1))
        
        # Pattern 2: Just numbers (e.g., 120828)
        match = re.search(r'^(\d+)$', ticker)
        if match:
            return int(match.group(1))
        
        # Pattern 3: Extract numbers from anywhere in the ticker
        match = re.search(r'(\d{5,6})', ticker)
        if match:
            return int(match.group(1))
        
        return None
        
    except Exception as e:
        logger.error(f"Error extracting scheme code from ticker {ticker}: {str(e)}")
        return None

def is_mutual_fund_ticker(ticker: str) -> bool:
    """
    Check if a ticker represents a mutual fund
    
    Args:
        ticker (str): Ticker symbol
        
    Returns:
        bool: True if it's a mutual fund ticker
    """
    # Check for common mutual fund patterns
    patterns = [
        r'^MF_',  # MF_ prefix
        r'^\d{5,6}$',  # Just numbers (5-6 digits)
        r'_MF$',  # _MF suffix
        r'FUND$',  # FUND suffix
        r'GROWTH$',  # GROWTH suffix
        r'DIVIDEND$',  # DIVIDEND suffix
    ]
    
    for pattern in patterns:
        if re.search(pattern, ticker, re.IGNORECASE):
            return True
    
    return False

def get_mutual_fund_price_with_fallback(ticker: str, date: Optional[str] = None, client: Optional[MFToolClient] = None) -> Optional[Dict[str, Any]]:
    """
    Get mutual fund NAV with fallback to basic data
    
    Args:
        ticker (str): Mutual fund ticker or name
        date (str): Date in YYYY-MM-DD format
        client (MFToolClient): MFTool client instance
        
    Returns:
        dict: NAV data or None
    """
    if not client:
        client = MFToolClient()
    
    # Try to extract scheme code from ticker
    scheme_code = extract_scheme_code_from_ticker(ticker)
    
    if scheme_code:
        # Try to get NAV by scheme code
        nav_data = client.get_mutual_fund_nav(scheme_code, date)
        if nav_data:
            return nav_data
    
    # If no scheme code or NAV not found, try by name
    nav_data = client.get_mutual_fund_nav_by_name(ticker, date)
    if nav_data:
        return nav_data
    
    return None

def fetch_mutual_fund_price(ticker: str, transaction_date: Optional[datetime] = None) -> Optional[float]:
    """
    Fetch mutual fund price for a given ticker and date
    
    Args:
        ticker (str): Mutual fund ticker
        transaction_date (datetime): Transaction date
        
    Returns:
        float: NAV price or None if not found
    """
    try:
        client = get_mftool_client()
        if not client.available:
            return None
        
        # Convert date to string if provided
        date_str = None
        if transaction_date:
            date_str = transaction_date.strftime('%Y-%m-%d')
        
        # Get NAV data
        nav_data = get_mutual_fund_price_with_fallback(ticker, date_str, client)
        
        if nav_data and nav_data.get('nav'):
            return float(nav_data['nav'])
        
        return None
        
    except Exception as e:
        logger.error(f"Error fetching mutual fund price for {ticker}: {str(e)}")
        return None

def fetch_mutual_funds_bulk(mutual_funds: List[tuple]) -> Dict[str, Optional[float]]:
    """
    Bulk fetch mutual fund prices for multiple tickers
    
    Args:
        mutual_funds: List of tuples (ticker, transaction_date)
        
    Returns:
        Dict mapping ticker to price
    """
    results = {}
    
    try:
        client = get_mftool_client()
        if not client.available:
            logger.warning("MFTool not available for bulk fetching")
            return results
        
        # Group by date for efficient fetching
        date_groups = {}
        for ticker, date in mutual_funds:
            date_key = date.strftime('%Y-%m-%d') if date else 'current'
            if date_key not in date_groups:
                date_groups[date_key] = []
            date_groups[date_key].append(ticker)
        
        # Process each date group
        for date_key, tickers in date_groups.items():
            try:
                # Extract scheme codes for this group
                scheme_codes = []
                ticker_to_scheme = {}
                
                for ticker in tickers:
                    scheme_code = extract_scheme_code_from_ticker(ticker)
                    if scheme_code:
                        scheme_codes.append(scheme_code)
                        ticker_to_scheme[ticker] = scheme_code
                
                # Bulk fetch NAVs for this date group
                if scheme_codes:
                    date_str = date_key if date_key != 'current' else None
                    bulk_navs = client.get_bulk_navs(scheme_codes, date_str)
                    
                    # Map results back to tickers
                    for ticker, scheme_code in ticker_to_scheme.items():
                        nav_data = bulk_navs.get(scheme_code)
                        if nav_data and nav_data.get('nav'):
                            results[ticker] = float(nav_data['nav'])
                            logger.info(f"✅ MFTool bulk: {ticker} = ₹{nav_data['nav']}")
                        else:
                            results[ticker] = None
                            logger.warning(f"❌ No NAV found for {ticker}")
                
                # For any tickers without scheme codes, try individual fetching
                remaining_tickers = [ticker for ticker in tickers if ticker not in ticker_to_scheme]
                for ticker in remaining_tickers:
                    price = fetch_mutual_fund_price(ticker, pd.to_datetime(date_key) if date_key != 'current' else None)
                    results[ticker] = price
                    
            except Exception as e:
                logger.error(f"Error in bulk fetching for date {date_key}: {str(e)}")
                # Fallback to individual fetching for this group
                for ticker in tickers:
                    if ticker not in results:
                        price = fetch_mutual_fund_price(ticker, pd.to_datetime(date_key) if date_key != 'current' else None)
                        results[ticker] = price
        
        return results
        
    except Exception as e:
        logger.error(f"Error in bulk mutual fund fetching: {str(e)}")
        return results

# Global client instance
_mftool_client = None

def get_mftool_client() -> MFToolClient:
    """
    Get or create MFTool client instance
    
    Returns:
        MFToolClient: Client instance
    """
    global _mftool_client
    if _mftool_client is None:
        _mftool_client = MFToolClient()
    return _mftool_client
