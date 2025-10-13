#!/usr/bin/env python3
"""
AI-Powered Price Fetching for Mutual Funds and PMS/AIF
Uses Google Gemini (free tier) and OpenAI GPT as fallback
"""

import os
import re
import logging
import time
from typing import Dict, Optional, Tuple, List
from datetime import datetime
from threading import Lock

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Rate limiting for API calls
_api_call_times = []
_api_lock = Lock()
_RATE_LIMIT_CALLS = 8  # Conservative: 8 calls per minute (Gemini free = 10/min)
_RATE_LIMIT_WINDOW = 60  # seconds

# Try to import AI libraries
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("Google Gemini not available. Install: pip install google-generativeai")

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI not available. Install: pip install openai")


class AIPriceFetcher:
    """AI-powered price fetcher using Gemini/GPT"""
    
    def __init__(self, gemini_key=None, openai_key=None):
        """
        Initialize AI clients
        
        Args:
            gemini_key: Google Gemini API key (optional, uses env vars if not provided)
            openai_key: OpenAI API key (optional, uses env vars if not provided)
        """
        self.gemini_client = None
        self.openai_client = None
        
        # 🆕 Try Gemini FIRST (FREE tier - user preference)
        if GEMINI_AVAILABLE:
            try:
                # Priority: 1) Provided key, 2) Streamlit secrets, 3) Environment variables
                api_key = gemini_key
                if not api_key:
                    try:
                        import streamlit as st
                        api_key = st.secrets.get("google_api_key") or st.secrets.get("gemini_api_key")
                    except:
                        pass
                if not api_key:
                    api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
                
                if api_key:
                    genai.configure(api_key=api_key)
                    # Use gemini-2.5-flash (latest stable fast model)
                    self.gemini_client = genai.GenerativeModel('models/gemini-2.5-flash')
                    logger.info("✅ Gemini AI initialized (PRIMARY - FREE)")
            except Exception as e:
                logger.warning(f"Gemini initialization failed: {e}")
        
        # Try OpenAI as FALLBACK (when Gemini quota exceeded)
        if OPENAI_AVAILABLE and not self.gemini_client:
            try:
                # Priority: 1) Provided key, 2) Streamlit secrets, 3) Environment variables
                api_key = openai_key
                if not api_key:
                    try:
                        import streamlit as st
                        api_key = st.secrets.get("open_ai") or st.session_state.get('openai_api_key')
                    except:
                        pass
                if not api_key:
                    api_key = os.getenv('OPENAI_API_KEY')
                
                if api_key:
                    self.openai_client = OpenAI(api_key=api_key)
                    logger.info("✅ OpenAI initialized (FALLBACK)")
            except Exception as e:
                logger.warning(f"OpenAI initialization failed: {e}")
    
    def is_available(self) -> bool:
        """Check if any AI service is available AND has quota"""
        # Check if we have any clients
        has_clients = self.gemini_client is not None or self.openai_client is not None
        
        # Check if quota is exhausted for all available clients
        if has_clients:
            # If OpenAI is primary but has quota issues, check Gemini
            if self.openai_client and hasattr(self, '_openai_quota_exhausted'):
                if self._openai_quota_exhausted and not self.gemini_client:
                    logger.warning("⚠️ OpenAI quota exhausted and no Gemini fallback")
                    return False
            
            # If both have quota issues, disable AI
            if hasattr(self, '_both_quotas_exhausted') and self._both_quotas_exhausted:
                logger.warning("⚠️ Both OpenAI and Gemini quotas exhausted - using traditional APIs")
                return False
        
        return has_clients
    
    def get_mutual_fund_nav(
        self, 
        ticker: str, 
        fund_name: str, 
        date: Optional[str] = None,
        allow_closest: bool = True,
        verify_both: bool = True
    ) -> Optional[float]:
        """
        Get mutual fund NAV using AI
        
        Args:
            ticker: AMFI scheme code or ISIN
            fund_name: Full fund name
            date: Target date (YYYY-MM-DD) or None for latest
            allow_closest: If True, return closest available date if exact not found
        
        Returns:
            NAV value or None if not found
        """
        if not self.is_available():
            return None
        
        # Clear prompt to avoid AI confusion (specify "NAV on date")
        if date:
            prompt = f"What was the NAV (Net Asset Value) of mutual fund {fund_name} (scheme code: {ticker}) on {date}? Reply with just the NAV number in INR."
        else:
            prompt = f"What is today's NAV or the most recent NAV of mutual fund {fund_name} (scheme code: {ticker})? Reply with just the NAV number in INR."
        
        try:
            response = self._call_ai(prompt)
            if response and response != "NOT_FOUND":
                # Extract numeric value
                nav = self._extract_number(response)
                if nav and nav > 0:
                    logger.info(f"✅ AI found NAV for {ticker}: ₹{nav}")
                    return nav
            
            logger.warning(f"⚠️ AI could not find NAV for {ticker}")
            return None
            
        except Exception as e:
            logger.error(f"❌ AI NAV fetch failed for {ticker}: {e}")
            return None
    
    def get_stock_price(
        self,
        ticker: str,
        stock_name: str,
        date: Optional[str] = None,
        allow_closest: bool = True,
        verify_both: bool = True
    ) -> Optional[float]:
        """
        Get stock price using AI (fallback when yfinance fails)
        
        Args:
            ticker: Stock ticker (e.g., INFY, RELIANCE, 500325)
            stock_name: Stock name
            date: Target date (YYYY-MM-DD) or None for latest
            allow_closest: If True, return closest available date if exact not found
        
        Returns:
            Stock price or None if not found
        """
        if not self.is_available():
            return None
        
        # Clear prompt to avoid AI confusion (specify "close price" explicitly)
        if date:
            prompt = f"What was the closing price of {stock_name} (NSE ticker: {ticker}) on {date}? Reply with just the closing price number in INR."
        else:
            prompt = f"What is today's closing price or the most recent closing price of {stock_name} (NSE ticker: {ticker})? Reply with just the price number in INR."
        
        try:
            response = self._call_ai(prompt)
            if response and response != "NOT_FOUND":
                # Extract numeric value (handle DATE suffix if present)
                price_str = response.split('|')[0] if '|' in response else response
                price = self._extract_number(price_str)
                if price and price > 0:
                    logger.info(f"✅ AI found price for {ticker}: ₹{price}")
                    return price
            
            logger.warning(f"⚠️ AI could not find price for {ticker}")
            return None
            
        except Exception as e:
            logger.error(f"❌ AI price fetch failed for {ticker}: {e}")
            return None
    
    def get_weekly_prices_in_range(
        self,
        ticker: str,
        name: str,
        start_date: str,
        end_date: str = 'TODAY'
    ) -> Dict[str, float]:
        """
        Get weekly prices for a ticker between two dates using AI
        
        Args:
            ticker: Ticker code
            name: Asset name
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD) or 'TODAY'
        
        Returns:
            Dict of {date: price} with weekly prices
            Example: {'2024-01-01': 2500.50, '2024-01-08': 2550.00, ...}
        """
        if not self.is_available():
            return {}
        
        # Clear prompt for weekly closing prices in date range
        prompt = f"Provide weekly closing prices for {name} (NSE ticker: {ticker}) from {start_date} to {end_date}. Give one price per week (Monday or first trading day of each week). Format each line as: YYYY-MM-DD|closing_price_in_INR (example: 2024-01-15|2500.50)"
        
        try:
            response = self._call_ai(prompt)
            if not response:
                return {}
            
            # Parse response into dict (robust parsing for various AI formats)
            results = {}
            for line in response.strip().split('\n'):
                line = line.strip()
                
                # Skip empty lines or headers
                if not line or line.lower().startswith(('date', 'ticker', 'week', 'note', 'source')):
                    continue
                
                # Handle different separators: | or : or tab or multiple spaces
                if '|' in line:
                    parts = line.split('|')
                elif ':' in line and line.count(':') == 1:
                    parts = line.split(':')
                elif '\t' in line:
                    parts = line.split('\t')
                elif '  ' in line:  # Multiple spaces
                    parts = line.split()
                else:
                    continue
                
                if len(parts) >= 2:
                    try:
                        # Extract date (first part)
                        date = parts[0].strip()
                        
                        # Extract price (second part, remove currency symbols and commas)
                        price_str = parts[1].strip()
                        # Remove common prefixes/symbols
                        for symbol in ['₹', '$', 'Rs', 'INR', 'Rs.', '₹.']:
                            price_str = price_str.replace(symbol, '')
                        price_str = price_str.replace(',', '').strip()
                        
                        price = float(price_str)
                        
                        # Validate: price should be positive and reasonable
                        if price > 0 and price < 1000000000:  # Less than 1 billion (sanity check)
                            results[date] = price
                        else:
                            logger.warning(f"Skipping invalid price for {date}: {price}")
                    except (ValueError, IndexError) as e:
                        logger.debug(f"Failed to parse line '{line}': {e}")
                        continue
            
            if results:
                logger.info(f"✅ AI weekly range: {ticker} - {len(results)} weekly prices")
                return results
            else:
                logger.warning(f"⚠️ AI weekly range: No data for {ticker}")
                return {}
                
        except Exception as e:
            logger.error(f"❌ AI weekly range fetch failed for {ticker}: {e}")
            return {}
    
    def get_bulk_prices_with_dates(
        self,
        tickers_with_names: Dict[str, str],
        dates: List[str] = None,
        asset_type: str = 'AUTO'
    ) -> Dict[str, Dict[str, float]]:
        """
        Get prices for multiple tickers with multiple dates in ONE AI call
        
        Args:
            tickers_with_names: Dict of {ticker: name} pairs
            dates: List of dates ['2024-01-15', '2024-02-20', 'LATEST'] or None for latest only
            asset_type: 'STOCK', 'MF', or 'AUTO' (auto-detect)
        
        Returns:
            Dict of {ticker: {date: price}} 
            Example: {'RELIANCE': {'2024-01-15': 2500.50, 'LATEST': 2650.00}}
        """
        if not self.is_available() or not tickers_with_names:
            return {}
        
        # Default to latest if no dates provided
        if not dates:
            dates = ['LATEST']
        
        # Clear bulk prompt to avoid confusion (specify closing prices)
        ticker_list = [f"{name} (ticker: {ticker})" for ticker, name in tickers_with_names.items()]
        date_list = ', '.join(dates[:5]) + ('...' if len(dates) > 5 else '')
        
        prompt = f"Provide closing prices for: {'; '.join(ticker_list[:5])}{'...' if len(ticker_list) > 5 else ''} on dates: {date_list}. For 'LATEST', give today's or most recent closing price. Format each line as: TICKER|YYYY-MM-DD|closing_price_in_INR (example: RELIANCE|2024-01-15|2500.50)"
        
        try:
            response = self._call_ai(prompt)
            if not response:
                return {}
            
            # Parse response into nested dict
            results = {}
            for line in response.strip().split('\n'):
                line = line.strip()
                if '|' in line:
                    parts = line.split('|')
                    if len(parts) >= 3:
                        ticker = parts[0].strip()
                        date = parts[1].strip()
                        try:
                            price = float(parts[2].strip())
                            if ticker not in results:
                                results[ticker] = {}
                            results[ticker][date] = price
                        except ValueError:
                            continue
            
            if results:
                total_prices = sum(len(dates) for dates in results.values())
                logger.info(f"✅ AI bulk fetch: {len(results)} tickers, {total_prices} prices")
                return results
            else:
                logger.warning("⚠️ AI bulk fetch returned no parseable data")
                return {}
                
        except Exception as e:
            logger.error(f"❌ AI bulk price fetch failed: {e}")
            return {}
    
    def get_pms_aif_nav(
        self,
        ticker: str,
        fund_name: str,
        date: Optional[str] = None
    ) -> Optional[float]:
        """
        Get PMS/AIF NAV using AI (for current value calculation)
        
        Args:
            ticker: SEBI registration code
            fund_name: Fund name
            date: Target date or None for latest
        
        Returns:
            NAV/Unit value or None
        """
        if not self.is_available():
            return None
        
        # Clear prompt to avoid AI confusion (specify NAV on date)
        if date:
            prompt = f"What was the NAV (Net Asset Value) or unit value of PMS/AIF fund {fund_name} (SEBI code: {ticker}) on {date}? Reply with just the NAV number in INR."
        else:
            prompt = f"What is today's NAV or the most recent NAV/unit value of PMS/AIF fund {fund_name} (SEBI code: {ticker})? Reply with just the NAV number in INR."
        
        try:
            response = self._call_ai(prompt)
            if response and response != "NOT_FOUND":
                nav = self._extract_number(response)
                if nav and nav > 0:
                    logger.info(f"✅ AI found PMS/AIF NAV for {ticker}: ₹{nav}")
                    return nav
            
            logger.warning(f"⚠️ AI could not find PMS/AIF NAV for {ticker}")
            return None
        except Exception as e:
            logger.error(f"❌ AI PMS/AIF NAV fetch failed for {ticker}: {e}")
            return None
    
    def get_pms_aif_performance(
        self, 
        ticker: str, 
        fund_name: str
    ) -> Dict[str, float]:
        """
        Get PMS/AIF performance data using AI
        
        Args:
            ticker: SEBI registration code (e.g., INP000005000)
            fund_name: Full PMS/AIF name
        
        Returns:
            Dict with '1Y', '3Y', '5Y' CAGR percentages or empty dict
        """
        if not self.is_available():
            return {}
        
        # Ultra-minimal prompt
        prompt = f"{fund_name} ({ticker}) returns: 1Y=? 3Y=? 5Y=?"
        
        try:
            response = self._call_ai(prompt)
            if not response:
                return {}
            
            # Parse response
            returns_data = {}
            
            # Extract 1Y, 3Y, 5Y values
            one_year = re.search(r'1Y:\s*([+-]?\d+\.?\d*)', response, re.IGNORECASE)
            three_year = re.search(r'3Y:\s*([+-]?\d+\.?\d*)', response, re.IGNORECASE)
            five_year = re.search(r'5Y:\s*([+-]?\d+\.?\d*)', response, re.IGNORECASE)
            
            if one_year:
                returns_data['1Y'] = float(one_year.group(1))
            if three_year:
                returns_data['3Y'] = float(three_year.group(1))
            if five_year:
                returns_data['5Y'] = float(five_year.group(1))
            
            if returns_data:
                logger.info(f"✅ AI found performance for {ticker}: {returns_data}")
            else:
                logger.warning(f"⚠️ AI could not extract performance data for {ticker}")
            
            return returns_data
            
        except Exception as e:
            logger.error(f"❌ AI performance fetch failed for {ticker}: {e}")
            return {}
    
    def _call_ai(self, prompt: str) -> Optional[str]:
        """
        Call AI service (OpenAI FIRST for paid tier, Gemini fallback)
        
        Args:
            prompt: The prompt to send
        
        Returns:
            AI response text or None
        """
        # Track call count for rate limiting
        if not hasattr(self, '_call_count'):
            self._call_count = 0
            self._call_start_time = time.time()
            self._use_openai = False  # Start with Gemini
        
        # Reset counter every minute
        elapsed = time.time() - self._call_start_time
        if elapsed > 60:
            self._call_count = 0
            self._call_start_time = time.time()
            self._use_openai = False  # Reset to Gemini after 1 minute
            logger.info("🔄 Rate limit counter reset, switching back to Gemini")
        
        # 🔄 SMART ALTERNATING STRATEGY: Gemini (9 calls) → OpenAI (while Gemini resets)
        if self._call_count >= 9 and not self._use_openai:
            # Switch to OpenAI after 9 Gemini calls
            logger.info("🔄 Gemini batch complete (9/9), switching to OpenAI...")
            self._use_openai = True
        
        # Try Gemini FIRST (for first 9 calls)
        if self.gemini_client and not self._use_openai:
            try:
                time.sleep(0.3)  # 300ms delay for safety
                
                response = self.gemini_client.generate_content(prompt)
                if response and response.text:
                    self._call_count += 1
                    logger.info(f"✅ Gemini call {self._call_count}/9 successful")
                    return response.text.strip()
            except Exception as e:
                error_str = str(e)
                logger.warning(f"Gemini call failed: {e}")
                
                # If it's a rate limit error, switch to OpenAI immediately
                if "429" in error_str or "quota" in error_str.lower() or "rate" in error_str.lower():
                    logger.warning("⚠️ Gemini rate limit hit, switching to OpenAI...")
                    self._use_openai = True
        
        # Use OpenAI (after 9 Gemini calls or when Gemini fails)
        if self.openai_client and self._use_openai:
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",  # Fast and cost-effective
                    messages=[
                        {"role": "system", "content": "Financial data expert."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0,  # For consistent results
                    max_tokens=50  # Reduced - only need number responses
                )
                if response.choices and response.choices[0].message:
                    logger.info(f"✅ OpenAI call successful (Gemini: {self._call_count}/9)")
                    return response.choices[0].message.content.strip()
            except Exception as e:
                logger.error(f"OpenAI call failed: {e}")
                # If OpenAI fails, try Gemini as last resort
                if self.gemini_client and self._call_count < 9:
                    logger.warning("⚠️ OpenAI failed, trying Gemini again...")
                    self._use_openai = False
                    return self._call_ai(prompt)  # Recursive retry with Gemini
        
        logger.error("❌ All AI providers failed")
        return None
    
    def _extract_number(self, text: str) -> Optional[float]:
        """
        Extract a numeric value from text (robust parsing)
        
        Args:
            text: Text containing a number
        
        Returns:
            Float value or None
        """
        try:
            # Remove common currency symbols, units, and text
            cleaned = text
            
            # Remove currency symbols and prefixes
            for symbol in ['₹', '$', 'Rs', 'INR', 'Rs.', '₹.', 'NAV:', 'NAV=', 'Price:', 'Price=', '=']:
                cleaned = cleaned.replace(symbol, '')
            
            # Remove commas (Indian/international number format)
            cleaned = cleaned.replace(',', '')
            
            # Remove extra whitespace
            cleaned = cleaned.strip()
            
            # Try direct conversion first
            try:
                return float(cleaned)
            except ValueError:
                pass
            
            # Find first number in text (handles formats like "2500.50 as of 2024-10-13")
            match = re.search(r'([+-]?\d+\.?\d*)', cleaned)
            if match:
                value = float(match.group(1))
                # Sanity check: price should be positive and reasonable
                if value > 0 and value < 1000000000:
                    return value
            
            return None
        except Exception as e:
            logger.debug(f"Failed to extract number from '{text}': {e}")
            return None


# Global instance
_ai_fetcher = None

def get_ai_fetcher() -> AIPriceFetcher:
    """Get or create global AI fetcher instance"""
    global _ai_fetcher
    if _ai_fetcher is None:
        _ai_fetcher = AIPriceFetcher()
    return _ai_fetcher


# Convenience functions
def get_mf_nav_with_ai(ticker: str, fund_name: str, date: Optional[str] = None) -> Optional[float]:
    """Get mutual fund NAV using AI"""
    fetcher = get_ai_fetcher()
    if not fetcher.is_available():
        logger.warning("AI services not available - check API keys")
        return None
    return fetcher.get_mutual_fund_nav(ticker, fund_name, date)


def get_pms_aif_performance_with_ai(ticker: str, fund_name: str) -> Dict[str, float]:
    """Get PMS/AIF performance using AI"""
    fetcher = get_ai_fetcher()
    if not fetcher.is_available():
        logger.warning("AI services not available - check API keys")
        return {}
    return fetcher.get_pms_aif_performance(ticker, fund_name)


if __name__ == "__main__":
    # Test the AI fetcher
    print("Testing AI Price Fetcher...")
    
    fetcher = AIPriceFetcher()
    
    if not fetcher.is_available():
        print("❌ No AI service available. Set GOOGLE_API_KEY or OPENAI_API_KEY")
    else:
        print(f"✅ AI service available")
        
        # Test MF NAV
        print("\n1. Testing Mutual Fund NAV...")
        nav = fetcher.get_mutual_fund_nav(
            ticker="119551",
            fund_name="HDFC Balanced Advantage Fund - Regular Plan - Growth"
        )
        print(f"Result: {nav}")
        
        # Test PMS performance
        print("\n2. Testing PMS Performance...")
        perf = fetcher.get_pms_aif_performance(
            ticker="INP000005000",
            fund_name="Buoyant Opportunities (PMS)"
        )
        print(f"Result: {perf}")

