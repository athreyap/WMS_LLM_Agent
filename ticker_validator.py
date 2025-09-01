import yfinance as yf
from difflib import get_close_matches
import pandas as pd
from datetime import datetime, timedelta
import logging
from typing import Optional, Tuple, List, Dict, Any
import sqlite3
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TickerValidator:
    def __init__(self, db_path: str = "wms_database.db"):
        self.db_path = db_path
        self.valid_tickers_cache = {}
        
    def is_valid_ticker(self, symbol: str) -> bool:
        """
        Returns True if ticker returns any history, otherwise False.
        """
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="7d", interval="1d")
            return df.shape[0] > 0
        except Exception as e:
            logger.warning(f"Error validating ticker {symbol}: {e}")
            return False
    
    def get_ticker_data(self, symbol: str, days: int = 30) -> Optional[pd.DataFrame]:
        """
        Get historical data for a ticker.
        """
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=f"{days}d", interval="1d")
            if df.shape[0] > 0:
                return df
            return None
        except Exception as e:
            logger.warning(f"Error getting data for ticker {symbol}: {e}")
            return None
    
    def suggest_ticker(self, symbol: str, valid_list: List[str], n: int = 3) -> List[str]:
        """
        Suggest closest matching symbol(s) from valid_list.
        """
        return get_close_matches(symbol.upper(), valid_list, n=n, cutoff=0.6)
    
    def try_nse_bse_tickers(self, base_symbol: str) -> Tuple[Optional[str], Optional[pd.DataFrame]]:
        """
        Try both NSE (.NS) and BSE (.BO) versions of a ticker.
        Returns (valid_ticker, data) or (None, None) if neither works.
        """
        # Remove any existing suffix
        clean_symbol = base_symbol.replace('.NS', '').replace('.BO', '').strip()
        
        # Try NSE first
        nse_ticker = f"{clean_symbol}.NS"
        logger.info(f"Trying NSE ticker: {nse_ticker}")
        
        if self.is_valid_ticker(nse_ticker):
            data = self.get_ticker_data(nse_ticker)
            if data is not None:
                logger.info(f"✅ NSE ticker {nse_ticker} is valid")
                return nse_ticker, data
        
        # Try BSE
        bse_ticker = f"{clean_symbol}.BO"
        logger.info(f"Trying BSE ticker: {bse_ticker}")
        
        if self.is_valid_ticker(bse_ticker):
            data = self.get_ticker_data(bse_ticker)
            if data is not None:
                logger.info(f"✅ BSE ticker {bse_ticker} is valid")
                return bse_ticker, data
        
        logger.warning(f"❌ Neither NSE nor BSE ticker found for {base_symbol}")
        return None, None
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Get current price for a ticker.
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            if 'regularMarketPrice' in info and info['regularMarketPrice']:
                return info['regularMarketPrice']
            elif 'currentPrice' in info and info['currentPrice']:
                return info['currentPrice']
            else:
                # Try to get from recent history
                df = ticker.history(period="1d")
                if not df.empty:
                    return df['Close'].iloc[-1]
            return None
        except Exception as e:
            logger.warning(f"Error getting current price for {symbol}: {e}")
            return None
    
    def update_database_ticker(self, old_ticker: str, new_ticker: str) -> bool:
        """
        Update ticker in the database.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Update in portfolio table
            cursor.execute("""
                UPDATE portfolio 
                SET ticker = ? 
                WHERE ticker = ?
            """, (new_ticker, old_ticker))
            
            # Update in prices table
            cursor.execute("""
                UPDATE prices 
                SET ticker = ? 
                WHERE ticker = ?
            """, (new_ticker, old_ticker))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Updated ticker from {old_ticker} to {new_ticker} in database")
            return True
            
        except Exception as e:
            logger.error(f"Error updating ticker in database: {e}")
            return False
    
    def validate_and_update_ticker(self, symbol: str, update_db: bool = True) -> Dict[str, Any]:
        """
        Main function to validate ticker, try NSE/BSE alternatives, and update database.
        """
        result = {
            'original_symbol': symbol,
            'valid_ticker': None,
            'ticker_type': None,  # 'NSE' or 'BSE'
            'current_price': None,
            'historical_data': None,
            'suggestions': [],
            'database_updated': False,
            'success': False
        }
        
        # First, try the symbol as-is
        if self.is_valid_ticker(symbol):
            result['valid_ticker'] = symbol
            result['ticker_type'] = 'NSE' if symbol.endswith('.NS') else 'BSE' if symbol.endswith('.BO') else 'Unknown'
            result['current_price'] = self.get_current_price(symbol)
            result['historical_data'] = self.get_ticker_data(symbol)
            result['success'] = True
            logger.info(f"✅ Original ticker {symbol} is valid")
            return result
        
        # Try NSE and BSE versions
        valid_ticker, data = self.try_nse_bse_tickers(symbol)
        
        if valid_ticker:
            result['valid_ticker'] = valid_ticker
            result['ticker_type'] = 'NSE' if valid_ticker.endswith('.NS') else 'BSE'
            result['current_price'] = self.get_current_price(valid_ticker)
            result['historical_data'] = data
            result['success'] = True
            
            # Update database if requested and ticker changed
            if update_db and valid_ticker != symbol:
                result['database_updated'] = self.update_database_ticker(symbol, valid_ticker)
            
            return result
        
        # If still no success, provide suggestions
        # Common NSE tickers for suggestions
        common_tickers = [
            "RELIANCE.NS", "TCS.NS", "INFY.NS", "SBIN.NS", "HDFCBANK.NS",
            "ICICIBANK.NS", "HINDUNILVR.NS", "ITC.NS", "BHARTIARTL.NS", "AXISBANK.NS",
            "KOTAKBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "HCLTECH.NS", "SUNPHARMA.NS",
            "WIPRO.NS", "ULTRACEMCO.NS", "TITAN.NS", "BAJFINANCE.NS", "NESTLEIND.NS"
        ]
        
        result['suggestions'] = self.suggest_ticker(symbol, common_tickers)
        
        return result
    
    def batch_validate_tickers(self, symbols: List[str], update_db: bool = True) -> Dict[str, Dict[str, Any]]:
        """
        Validate multiple tickers in batch.
        """
        results = {}
        
        for symbol in symbols:
            logger.info(f"Processing ticker: {symbol}")
            results[symbol] = self.validate_and_update_ticker(symbol, update_db)
        
        return results
    
    def get_portfolio_tickers(self) -> List[str]:
        """
        Get all unique tickers from the portfolio table.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT DISTINCT ticker FROM portfolio")
            tickers = [row[0] for row in cursor.fetchall()]
            
            conn.close()
            return tickers
            
        except Exception as e:
            logger.error(f"Error getting portfolio tickers: {e}")
            return []
    
    def validate_all_portfolio_tickers(self, update_db: bool = True) -> Dict[str, Dict[str, Any]]:
        """
        Validate all tickers in the portfolio and update database.
        """
        tickers = self.get_portfolio_tickers()
        logger.info(f"Found {len(tickers)} tickers in portfolio to validate")
        
        return self.batch_validate_tickers(tickers, update_db)


def main():
    """
    Example usage and testing.
    """
    validator = TickerValidator()
    
    # Test individual ticker
    test_symbols = ["SBIN", "RELIANCE", "TCS", "INVALIDTICKER"]
    
    for symbol in test_symbols:
        print(f"\n{'='*50}")
        print(f"Testing symbol: {symbol}")
        print(f"{'='*50}")
        
        result = validator.validate_and_update_ticker(symbol, update_db=False)
        
        print(f"Original Symbol: {result['original_symbol']}")
        print(f"Valid Ticker: {result['valid_ticker']}")
        print(f"Ticker Type: {result['ticker_type']}")
        print(f"Current Price: {result['current_price']}")
        print(f"Success: {result['success']}")
        
        if result['suggestions']:
            print(f"Suggestions: {', '.join(result['suggestions'])}")
        
        if result['historical_data'] is not None:
            print(f"Historical Data Shape: {result['historical_data'].shape}")
            print("Recent prices:")
            print(result['historical_data'][['Close', 'Volume']].tail(3))


if __name__ == "__main__":
    main()
