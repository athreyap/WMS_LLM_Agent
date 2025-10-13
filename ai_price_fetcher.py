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
        date: Optional[str] = None
    ) -> Optional[float]:
        """
        Get mutual fund NAV using AI
        
        Args:
            ticker: AMFI scheme code
            fund_name: Full fund name
            date: Target date (YYYY-MM-DD) or None for latest
        
        Returns:
            NAV value or None if not found
        """
        if not self.is_available():
            return None
        
        # Build prompt
        date_str = f"as of {date}" if date else "latest available"
        prompt = f"""You are a financial data expert. Get the current NAV (Net Asset Value) for this Indian mutual fund:

Fund Name: {fund_name}
AMFI Code: {ticker}
Date: {date_str}

Search the web and return ONLY the NAV value as a number (e.g., "45.67" or "123.45").
If you cannot find the exact NAV, return "NOT_FOUND".
Do not include currency symbols, units, or any other text - ONLY the numeric NAV value.
"""
        
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
            Dict with '1y_return', '3y_cagr', '5y_cagr' or empty dict
        """
        if not self.is_available():
            return {}
        
        # Build prompt
        prompt = f"""You are a financial data expert. Get the latest performance data for this Indian PMS/AIF:

Fund Name: {fund_name}
SEBI Registration: {ticker}

Search the web for the LATEST factsheet or performance report and extract:
1. 1-Year Return (or CAGR): X%
2. 3-Year CAGR: X%
3. 5-Year CAGR: X%

Return the data in this EXACT format (one per line):
1Y: [number]
3Y: [number]
5Y: [number]

Example:
1Y: 15.5
3Y: 18.2
5Y: 22.1

If any value is not available, write "N/A" for that line.
Return ONLY the numbers in the format shown - no additional text.
"""
        
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
                returns_data['1y_return'] = float(one_year.group(1))
            if three_year:
                returns_data['3y_cagr'] = float(three_year.group(1))
            if five_year:
                returns_data['5y_cagr'] = float(five_year.group(1))
            
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

