#!/usr/bin/env python3
"""
INDstocks Library Integration for WMS-LLM
Handles fetching stock and mutual fund prices using indstocks library
"""

import pandas as pd
from datetime import datetime, timedelta
import time
import logging
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import mutual fund price fetcher
try:
    from mf_price_fetcher import get_mftool_client, is_mutual_fund_ticker, get_mutual_fund_price_with_fallback
    MF_TOOL_AVAILABLE = True
except ImportError:
    MF_TOOL_AVAILABLE = False
    logger.warning("mf_price_fetcher not available. Mutual fund price fetching will be limited.")

class INDstocksClient:
    """INDstocks client for fetching stock and mutual fund data using indstocks library"""
    
    def __init__(self):
        """Initialize INDstocks client"""
        try:
            import indstocks as stocks
            self.stocks = stocks
            self.available = True
        except ImportError:
            logger.error("indstocks library not available. Please install with: pip install indstocks")
            self.available = False
    
    def get_stock_price(self, symbol: str, date: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get stock price or mutual fund NAV for a given symbol and date
        
        Args:
            symbol (str): Stock symbol or mutual fund ticker (e.g., 'RELIANCE', 'INFY', 'MF_120828')
            date (str): Date in YYYY-MM-DD format (optional, defaults to latest)
            
        Returns:
            dict: Stock price or NAV data or None if not found
        """
        if not self.available:
            return None
        
        # Try INDstocks first for ALL tickers (including mutual funds)
        try:
            # Clean symbol (remove .NS or .BO if present)
            clean_symbol = symbol.replace('.NS', '').replace('.BO', '')
            
            quote = self.stocks.Quote(clean_symbol)
            
            if date:
                # Try to get historical price using INDstocks' built-in historical data
                try:
                    # Check if the requested date is in the future
                    requested_date_obj = datetime.strptime(date, '%Y-%m-%d')
                    current_date = datetime.now()
                    
                    if requested_date_obj > current_date:
                        # Future date - get current price and indicate it's not historical
                        current_price = quote.get_current_price()
                        if isinstance(current_price, str):
                            current_price = float(current_price.replace(',', ''))
                        
                        return {
                            'symbol': symbol,
                            'price': current_price,
                            'date': date,
                            'source': 'indstocks_current_future_date',
                            'note': f'Future date {date} - using current price'
                        }
                    
                    # Get historical data from INDstocks
                    hist_data = quote.get_stock_historical_data()
                    
                    if hist_data:
                        # Convert to DataFrame for easier processing
                        df = pd.DataFrame(hist_data)
                        
                        if 'date' in df.columns:
                            df['date'] = pd.to_datetime(df['date'])
                            df.set_index('date', inplace=True)
                            
                            # Look for exact date match
                            if date in df.index.strftime('%Y-%m-%d'):
                                # Get the close price for that date
                                close_price = df.loc[date, 'close'] if 'close' in df.columns else df.loc[date, 'Close']
                                return {
                                    'symbol': symbol,
                                    'price': float(close_price),
                                    'date': date,
                                    'source': 'indstocks_historical'
                                }
                            else:
                                # No exact match, fall back to current price
                                current_price = quote.get_current_price()
                                if isinstance(current_price, str):
                                    current_price = float(current_price.replace(',', ''))
                                
                                return {
                                    'symbol': symbol,
                                    'price': current_price,
                                    'date': date,
                                    'source': 'indstocks_current_no_historical',
                                    'note': f'No historical data for {date} - using current price'
                                }
                        else:
                            # No date column in historical data, fall back to current price
                            current_price = quote.get_current_price()
                            if isinstance(current_price, str):
                                current_price = float(current_price.replace(',', ''))
                            
                            return {
                                'symbol': symbol,
                                'price': current_price,
                                'date': date,
                                'source': 'indstocks_current_no_historical',
                                'note': f'Historical data has no date column - using current price'
                            }
                    else:
                        # No historical data available, fall back to current price
                        current_price = quote.get_current_price()
                        if isinstance(current_price, str):
                            current_price = float(current_price.replace(',', ''))
                        
                        return {
                            'symbol': symbol,
                            'price': current_price,
                            'date': date,
                            'source': 'indstocks_current_no_historical',
                            'note': f'No historical data for {date} - using current price'
                        }
                        
                except Exception as hist_error:
                    # Only log as warning if it's not a common HTML parsing issue
                    error_msg = str(hist_error)
                    if "'NoneType' object has no attribute 'find_all'" in error_msg:
                        logger.debug(f"INDstocks historical data not available for {symbol} on {date} (common for old dates)")
                    else:
                        logger.warning(f"INDstocks historical price fetch failed for {symbol} on {date}: {hist_error}")
                    
                    # Fall back to current price
                    try:
                        current_price = quote.get_current_price()
                        if isinstance(current_price, str):
                            current_price = float(current_price.replace(',', ''))
                        
                        return {
                            'symbol': symbol,
                            'price': current_price,
                            'date': date,
                            'source': 'indstocks_current_fallback',
                            'note': f'Historical data unavailable - using current price'
                        }
                    except Exception as current_error:
                        logger.error(f"Failed to get current price for {symbol}: {current_error}")
                        return None
            else:
                # Get current price
                current_price = quote.get_current_price()
                price_change = quote.get_stock_price_change()
                
                # Convert price to float if it's a string
                if isinstance(current_price, str):
                    # Remove commas and convert to float
                    current_price = float(current_price.replace(',', ''))
                
                return {
                    'symbol': symbol,
                    'price': current_price,
                    'price_change': price_change,
                    'date': datetime.now().strftime('%Y-%m-%d'),
                    'source': 'indstocks'
                }
                
        except Exception as e:
            logger.warning(f"INDstocks failed for {symbol}: {str(e)}")
            
            # If INDstocks failed and this might be a mutual fund, try mutual fund tools
            if MF_TOOL_AVAILABLE and is_mutual_fund_ticker(symbol):
                try:
                    logger.info(f"Trying mutual fund tools for {symbol}")
                    mf_client = get_mftool_client()
                    nav_data = get_mutual_fund_price_with_fallback(symbol, date, mf_client)
                    if nav_data:
                        # Convert NAV data to match stock price format
                        return {
                            'symbol': symbol,
                            'price': nav_data.get('nav', 0),
                            'date': nav_data.get('date', datetime.now().strftime('%Y-%m-%d')),
                            'source': nav_data.get('source', 'mftool_fallback'),
                            'scheme_code': nav_data.get('scheme_code'),
                            'scheme_name': nav_data.get('scheme_name'),
                            'note': f'INDstocks failed - using mutual fund tools'
                        }
                except Exception as mf_error:
                    logger.error(f"Mutual fund fallback also failed for {symbol}: {str(mf_error)}")
            
            return None
    
    def get_stock_insights(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive stock insights
        
        Args:
            symbol (str): Stock symbol
            
        Returns:
            dict: Stock insights or None if not found
        """
        if not self.available:
            return None
            
        try:
            # Clean symbol (remove .NS or .BO if present)
            clean_symbol = symbol.replace('.NS', '').replace('.BO', '')
            
            quote = self.stocks.Quote(clean_symbol)
            
            current_price = quote.get_current_price()
            # Convert price to float if it's a string
            if isinstance(current_price, str):
                # Remove commas and convert to float
                current_price = float(current_price.replace(',', ''))
            
            return {
                'ticker': symbol,
                'current_price': current_price,
                'price_change': quote.get_stock_price_change(),
                'basic_info': quote.get_basic_info(),
                'company_profile': quote.get_stock_info(),
                'pros_and_cons': quote.get_pros_and_cons(),
                'source': 'indstocks'
            }
            
        except Exception as e:
            logger.error(f"Error fetching stock insights for {symbol}: {str(e)}")
            return None
    
    def get_stock_sector(self, symbol: str) -> Optional[str]:
        """
        Get sector information for a stock
        
        Args:
            symbol (str): Stock symbol
            
        Returns:
            str: Sector name or None if not found
        """
        if not self.available:
            return None
            
        try:
            # Clean symbol (remove .NS or .BO if present)
            clean_symbol = symbol.replace('.NS', '').replace('.BO', '')
            
            quote = self.stocks.Quote(clean_symbol)
            
            # Try to get sector from basic info
            try:
                basic_info = quote.get_basic_info()
                if isinstance(basic_info, dict):
                    sector = basic_info.get('sector') or basic_info.get('Sector')
                    if sector:
                        return sector
            except:
                pass
            
            # Try to get sector from company profile
            try:
                company_profile = quote.get_stock_info()
                if isinstance(company_profile, dict):
                    sector = company_profile.get('sector') or company_profile.get('Sector')
                    if sector:
                        return sector
            except:
                pass
            
            # Default sector mapping for major stocks
            sector_mapping = {
                'RELIANCE': 'Oil & Gas',
                'TCS': 'Technology',
                'INFY': 'Technology',
                'HDFCBANK': 'Banking',
                'HDFC': 'Banking',
                'ICICIBANK': 'Banking',
                'SBIN': 'Banking',
                'BHARTIARTL': 'Telecom',
                'ITC': 'FMCG',
                'HINDUNILVR': 'FMCG',
                'LT': 'Engineering',
                'ASIANPAINT': 'Paints',
                'MARUTI': 'Automobile',
                'BAJFINANCE': 'Finance',
                'HCLTECH': 'Technology',
                'WIPRO': 'Technology',
                'TECHM': 'Technology',
            }
            
            return sector_mapping.get(clean_symbol.upper(), 'Unknown')
                
        except Exception as e:
            logger.error(f"Error fetching sector for {symbol}: {str(e)}")
            return None
    
    def get_bulk_prices(self, symbols: list, date: Optional[str] = None) -> Dict[str, Any]:
        """
        Get prices for multiple symbols
        
        Args:
            symbols (list): List of stock symbols
            date (str): Date in YYYY-MM-DD format (optional)
            
        Returns:
            dict: Dictionary mapping symbols to price data
        """
        results = {}
        
        for symbol in symbols:
            if symbol:
                price_data = self.get_stock_price(symbol, date)
                if price_data:
                    results[symbol] = price_data
                
                # Rate limiting
                time.sleep(0.1)
        
        return results
    
    def get_historical_prices(self, symbol: str, start_date: str, end_date: str) -> list:
        """
        Get historical prices for a symbol within a date range
        
        Args:
            symbol (str): Stock symbol
            start_date (str): Start date in YYYY-MM-DD format
            end_date (str): End date in YYYY-MM-DD format
            
        Returns:
            list: List of price data points
        """
        if not self.available:
            return []
            
        try:
            # Clean symbol (remove .NS or .BO if present)
            clean_symbol = symbol.replace('.NS', '').replace('.BO', '')
            
            # Note: indstocks library might not support historical data directly
            # For now, return current price as a single data point
            current_price = self.get_stock_price(symbol)
            if current_price:
                return [current_price]
            return []
                
        except Exception as e:
            logger.error(f"Error fetching history for {symbol}: {str(e)}")
            return []

# Fallback to yfinance if indstocks fails
def get_price_with_fallback(symbol: str, date: Optional[str] = None, client: Optional[INDstocksClient] = None) -> Optional[Dict[str, Any]]:
    """
    Get price with fallback to yfinance if indstocks fails
    
    Args:
        symbol (str): Stock symbol or mutual fund ticker
        date (str): Date in YYYY-MM-DD format
        client (INDstocksClient): INDstocks client instance
        
    Returns:
        dict: Price data or None
    """
    # Try indstocks first for ALL tickers (including mutual funds)
    if client and client.available:
        price_data = client.get_stock_price(symbol, date)
        if price_data and price_data.get('price'):
            return price_data
    
    # Fallback to yfinance for stocks
    try:
        import yfinance as yf
        
        if date:
            data = yf.download(symbol, start=date, end=date, progress=False, auto_adjust=True)
        else:
            data = yf.download(symbol, period="1d", progress=False, auto_adjust=True)
        
        if not data.empty:
            return {
                'symbol': symbol,
                'price': data['Close'].iloc[-1].item(),  # Use .item() to avoid deprecation warning
                'date': date or data.index[-1].strftime('%Y-%m-%d'),
                'source': 'yfinance_fallback'
            }
    except Exception as e:
        logger.error(f"Fallback to yfinance failed for {symbol}: {str(e)}")
    
    return None

def get_stock_insights_with_fallback(symbol: str, client: Optional[INDstocksClient] = None) -> Optional[Dict[str, Any]]:
    """
    Get stock insights with fallback to basic price data
    
    Args:
        symbol (str): Stock symbol
        client (INDstocksClient): INDstocks client instance
        
    Returns:
        dict: Stock insights or None
    """
    # Try indstocks first
    if client and client.available:
        insights = client.get_stock_insights(symbol)
        if insights:
            return insights
    
    # Fallback to basic price data
    price_data = get_price_with_fallback(symbol, None, client)
    if price_data:
        return {
            'ticker': symbol,
            'current_price': price_data.get('price'),
            'source': price_data.get('source', 'fallback')
        }
    
    return None

# Global client instance
_indstocks_client = None

def get_indstocks_client() -> INDstocksClient:
    """
    Get or create INDstocks client instance
    
    Returns:
        INDstocksClient: Client instance
    """
    global _indstocks_client
    if _indstocks_client is None:
        _indstocks_client = INDstocksClient()
    return _indstocks_client
