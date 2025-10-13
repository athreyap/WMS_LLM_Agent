#!/usr/bin/env python3
"""
AI-Powered Price Fetching for Mutual Funds and PMS/AIF
Uses Google Gemini (free tier) and OpenAI GPT as fallback
"""

import os
import re
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        
        # Try Gemini first (free tier)
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
                    logger.info("✅ Gemini AI initialized")
            except Exception as e:
                logger.warning(f"Gemini initialization failed: {e}")
        
        # Try OpenAI as fallback
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
                    logger.info("✅ OpenAI initialized")
            except Exception as e:
                logger.warning(f"OpenAI initialization failed: {e}")
    
    def is_available(self) -> bool:
        """Check if any AI service is available"""
        return self.gemini_client is not None or self.openai_client is not None
    
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
        
        # Build prompt with date handling
        if date:
            date_instruction = f"""Target Date: {date}
If the exact date is not available, find the CLOSEST date within 7 days (before or after).
Return format: NAV_VALUE|DATE
Example: 45.67|2024-11-10"""
        else:
            date_instruction = "Get the LATEST available NAV."
        
        prompt = f"""Get the NAV (Net Asset Value) for this Indian mutual fund using BOTH identifiers for 100% accuracy:

Fund Name: {fund_name}
Scheme Code: {ticker}
{date_instruction}

CRITICAL VERIFICATION (to avoid wrong plan/option):
1. Search AMFI India NAV list for scheme code {ticker}
2. VERIFY the fund name matches "{fund_name}"
3. Check if it's Direct/Regular plan and Growth/Dividend option
4. If code and name don't match, search by fund name to get correct NAV

Common mistakes to avoid:
- Code 148097 (Dividend) vs 148098 (Growth) = Different NAVs!
- Regular Plan vs Direct Plan = Different NAVs!

Search these official sources:
- AMFI India: https://www.amfiindia.com/spages/NAVAll.txt
- Value Research: https://www.valueresearchonline.com
- Morningstar India
- Fund house official website

IMPORTANT: If exact date not available, find CLOSEST available date within ±7 days.

Return ONLY the numeric NAV (e.g., "45.67").
If using closest date, return: NAV|DATE (e.g., "45.67|2024-11-10")
If code and name don't match or not found, return "NOT_FOUND".
No currency symbols, no extra text."""
        
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
        
        # Build prompt with date handling
        if date:
            date_instruction = f"""Target Date: {date}
If exact date not available, find CLOSEST trading day within 7 days.
Return format: PRICE|DATE
Example: 1523.45|2024-11-10"""
        else:
            date_instruction = "Get the LATEST market price (today's closing or current price)."
        
        prompt = f"""Get the stock price for this Indian company using BOTH identifiers for 100% accuracy:

Company Name: {stock_name}
Stock Ticker/Code: {ticker}
{date_instruction}

CRITICAL VERIFICATION (to avoid wrong company):
1. Search NSE/BSE using ticker "{ticker}"
2. VERIFY the company name matches "{stock_name}"
3. If mismatch (delisted, renamed, wrong code), search by company name
4. Check for .NS (NSE) or .BO (BSE) suffix

Common issues to watch:
- TANFACIND may be delisted or renamed to TNPL
- BSE code vs NSE ticker differences
- Company mergers/name changes

Search these official sources in order:
1. MoneyControl.com (most reliable)
2. NSE India: https://www.nseindia.com
3. BSE India: https://www.bseindia.com
4. Screener.in
5. Economic Times

IMPORTANT: If exact date not available, find CLOSEST trading day within ±7 days.

Return ONLY the numeric price in INR (e.g., "1523.45").
If using closest date, return: PRICE|DATE (e.g., "1523.45|2024-11-10")
If ticker and name don't match or not found, return "NOT_FOUND".
No currency symbols, no extra text."""
        
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
        
        # Build enhanced prompt with monthly CAGR request
        prompt = f"""Get the latest performance data for this Indian PMS/AIF investment:

Fund Name: {fund_name}
SEBI Registration Code: {ticker}

Search these official sources:
1. SEBI website: https://www.sebi.gov.in
2. PMS Bazaar: https://www.pmsbazaar.com
3. AIF Data: https://www.aifdata.in
4. Fund's official website/factsheet
5. Fund manager website

Extract and return performance data in this EXACT format:

MONTHLY (if available):
1M: [number]
3M: [number]
6M: [number]

ANNUAL (required):
1Y: [number]
3Y: [number]
5Y: [number]

SINCE INCEPTION (if available):
SI: [number]

Example output:
1M: 2.5
3M: 5.8
6M: 12.3
1Y: 15.5
3Y: 18.2
5Y: 22.1
SI: 24.0

Rules:
- All values are CAGR percentages (annualized returns)
- For monthly periods, annualize the return
- If a period is not available, write "N/A"
- Return ONLY numbers in the format shown above
- No extra text, explanations, or commentary
- Verify both fund name and SEBI code match"""
        
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
        Call AI service (Gemini first, then OpenAI)
        
        Args:
            prompt: The prompt to send
        
        Returns:
            AI response text or None
        """
        # Try Gemini first
        if self.gemini_client:
            try:
                response = self.gemini_client.generate_content(prompt)
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                logger.warning(f"Gemini call failed: {e}")
        
        # Try OpenAI as fallback
        if self.openai_client:
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",  # Cheaper than GPT-4
                    messages=[
                        {"role": "system", "content": "You are a financial data expert. Provide only the requested data in the exact format specified."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0,  # For consistent results
                    max_tokens=200
                )
                if response.choices and response.choices[0].message:
                    return response.choices[0].message.content.strip()
            except Exception as e:
                logger.warning(f"OpenAI call failed: {e}")
        
        return None
    
    def _extract_number(self, text: str) -> Optional[float]:
        """
        Extract a numeric value from text
        
        Args:
            text: Text containing a number
        
        Returns:
            Float value or None
        """
        try:
            # Remove common currency symbols and units
            cleaned = text.replace('₹', '').replace('Rs', '').replace(',', '').strip()
            
            # Find first number in text
            match = re.search(r'([+-]?\d+\.?\d*)', cleaned)
            if match:
                return float(match.group(1))
            
            return None
        except Exception:
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

