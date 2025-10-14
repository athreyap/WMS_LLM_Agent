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
        
        # 🆕 HYBRID STRATEGY: Gemini PRIMARY (FREE) + OpenAI BACKUP (PAID)
        # This maximizes free usage while maintaining speed and reliability
        
        # Initialize Gemini FIRST (FREE - 10 requests/minute)
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
                    logger.info("✅ Gemini AI initialized (PRIMARY - FREE, 10 req/min)")
            except Exception as e:
                logger.warning(f"Gemini initialization failed: {e}")
        
        # Initialize OpenAI as BACKUP (PAID - ₹300 available)
        if OPENAI_AVAILABLE:
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
                    # Create client (use key's default project)
                    self.openai_client = OpenAI(api_key=api_key)
                    logger.info("✅ OpenAI initialized (BACKUP - ₹300 available)")
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
    
    def _retry_with_alternate_provider(self, prompt: str, max_tokens: int, ticker: str) -> Optional[str]:
        """
        Retry AI call with alternate provider if first one fails
        
        Args:
            prompt: The prompt to retry
            max_tokens: Max tokens for response
            ticker: Ticker being fetched (for logging)
            
        Returns:
            Response from alternate provider, or None if retry fails
        """
        logger.warning(f"🔄 Retrying {ticker} with alternate AI provider...")
        
        # Save original clients
        original_gemini = self.gemini_client
        original_openai = self.openai_client
        
        try:
            # If we used Gemini, try OpenAI (or vice versa)
            if self._call_count > 0:  # Was using Gemini
                logger.info(f"🔄 Switching from Gemini to OpenAI for retry...")
                self.gemini_client = None  # Temporarily disable Gemini
            else:  # Was using OpenAI
                logger.info(f"🔄 Switching from OpenAI to Gemini for retry...")
                self.openai_client = None  # Temporarily disable OpenAI
            
            # Retry the call
            retry_response = self._call_ai(prompt, max_tokens=max_tokens)
            
            # Restore original clients
            self.gemini_client = original_gemini
            self.openai_client = original_openai
            
            if retry_response:
                logger.info(f"✅ Retry successful for {ticker}")
                return retry_response
            else:
                logger.warning(f"⚠️ Retry returned empty response for {ticker}")
                return None
                
        except Exception as retry_error:
            logger.error(f"❌ Retry failed for {ticker}: {retry_error}")
            # Restore original clients
            self.gemini_client = original_gemini
            self.openai_client = original_openai
            return None
    
    def get_mutual_fund_nav(
        self, 
        ticker: str, 
        fund_name: str, 
        date: Optional[str] = None,
        allow_closest: bool = True,
        verify_both: bool = True
    ) -> Optional[Dict[str, any]]:
        """
        Get mutual fund NAV with date and category using AI
        
        Args:
            ticker: AMFI scheme code or ISIN
            fund_name: Full fund name
            date: Target date (YYYY-MM-DD) or None for latest
            allow_closest: If True, return closest available date if exact not found
        
        Returns:
            Dict with {'date': 'YYYY-MM-DD', 'price': float, 'sector': str} or None
        """
        if not self.is_available():
            return None
        
        # CRITICAL: Be explicit to prevent code generation
        if date:
            prompt = f"""Get the ACTUAL NAV for this mutual fund:

Fund Name: {fund_name}
Fund Code: {ticker}
Target Date: {date} (or nearest available date)

Provide the REAL NAV data in this exact format:
{{'date': 'YYYY-MM-DD', 'price': <actual_nav>, 'sector': '<fund_category>'}}

Replace:
- YYYY-MM-DD with the actual date
- <actual_nav> with the real NAV value
- <fund_category> with the fund type (e.g., 'Equity: Large Cap', 'Debt: Short Duration')

Return ONLY the dictionary with REAL data:"""
        else:
            prompt = f"""Get the LATEST NAV for this mutual fund:

Fund Name: {fund_name}
Fund Code: {ticker}
Date: Latest available (yesterday or most recent)

Provide the REAL NAV data in this exact format:
{{'date': 'YYYY-MM-DD', 'price': <actual_nav>, 'sector': '<fund_category>'}}

Replace:
- YYYY-MM-DD with the actual date
- <actual_nav> with the real NAV value
- <fund_category> with the fund type (e.g., 'Equity: Large Cap', 'Debt: Short Duration')

Return ONLY the dictionary with REAL data:"""
        
        # LOG PROMPT FOR DEBUGGING (use print to bypass log filters)
        print(f"\n{'='*60}")
        print(f"📤 MF PROMPT for {ticker}:")
        print(prompt)
        print(f"{'='*60}\n")
        
        try:
            response = self._call_ai(prompt)
            print(f"📥 MF RESPONSE for {ticker}: {response}\n")
            if response and response != "NOT_FOUND":
                clean_response = response.strip()
                
                # 🚨 DETECT IF AI RETURNED CODE OR EXPLANATION INSTEAD OF DATA
                code_indicators = ['import ', 'def ', 'class ', 'for ', 'while ', 'if __name__', 'requests.', 'yfinance', 'pandas', 'datetime.']
                explanation_indicators = ['I am sorry', 'I do not have', 'I cannot', 'As an AI', 'I must adhere', 'I apologize']
                
                is_code = any(indicator in clean_response for indicator in code_indicators)
                is_explanation = any(indicator in clean_response for indicator in explanation_indicators)
                
                if is_code or is_explanation:
                    error_type = "CODE" if is_code else "EXPLANATION"
                    logger.error(f"❌ AI returned {error_type} instead of DATA for MF {ticker}!")
                    logger.error(f"Response preview: {clean_response[:200]}...")
                    
                    # 🔄 RETRY WITH ALTERNATE AI PROVIDER
                    retry_response = self._retry_with_alternate_provider(prompt, max_tokens=300, ticker=ticker)
                    if retry_response and retry_response != response:
                        logger.info(f"✅ Retry successful for MF {ticker}, re-parsing...")
                        clean_response = retry_response.strip()
                        # Continue to parsing below
                    else:
                        logger.warning(f"⚠️ Retry failed for MF {ticker}, skipping")
                        return None
                
                # Try parsing as Python dictionary first (safest and cleanest)
                try:
                    import ast
                    from datetime import datetime as dt
                    today_dt = dt.now()
                    
                    # Extract dictionary from response (handle markdown code blocks)
                    if '```' in clean_response:
                        clean_response = clean_response.split('```')[1]
                        if clean_response.startswith('python'):
                            clean_response = clean_response[6:]
                    
                    # Find dictionary in response
                    dict_start = clean_response.find('{')
                    dict_end = clean_response.rfind('}') + 1
                    if dict_start >= 0 and dict_end > dict_start:
                        dict_str = clean_response[dict_start:dict_end]
                        result = ast.literal_eval(dict_str)
                        
                        if isinstance(result, dict) and 'price' in result:
                            nav = float(result.get('price', 0))
                            result_date = result.get('date', date or 'LATEST')
                            
                            # 🚨 VALIDATE: Reject future dates
                            if result_date != 'LATEST':
                                try:
                                    date_dt = dt.strptime(result_date, '%Y-%m-%d')
                                    if date_dt > today_dt:
                                        logger.warning(f"⚠️ AI returned FUTURE date {result_date} for MF {ticker} - rejecting")
                                        return None
                                except ValueError:
                                    logger.warning(f"⚠️ Invalid date format: {result_date}")
                                    return None
                            
                            if nav > 0:
                                logger.info(f"✅ AI found NAV for {ticker}: ₹{nav} on {result_date}, category: {result.get('sector')}")
                                return {
                                    'date': result_date,
                                    'price': nav,
                                    'sector': result.get('sector', 'Mutual Fund')
                                }
                except Exception as e:
                    logger.debug(f"Failed to parse as dict: {e}, trying CSV fallback")
                
                # Fallback: CSV format (comma or pipe separated)
                from datetime import datetime as dt
                today_dt = dt.now()
                
                if ',' in clean_response:
                    parts = [p.strip() for p in clean_response.split(',')]
                elif '|' in clean_response:
                    parts = [p.strip() for p in clean_response.split('|')]
                else:
                    parts = []
                
                if len(parts) >= 3:
                    nav = self._extract_number(parts[1])
                    result_date = parts[0]
                    
                    # 🚨 VALIDATE: Reject future dates
                    if result_date != 'LATEST':
                        try:
                            date_dt = dt.strptime(result_date, '%Y-%m-%d')
                            if date_dt > today_dt:
                                logger.warning(f"⚠️ AI returned FUTURE date {result_date} for MF {ticker} - rejecting")
                                return None
                        except ValueError:
                            pass  # Allow processing to continue
                    
                    if nav and nav > 0:
                        return {'date': result_date, 'price': nav, 'sector': parts[2]}
                elif len(parts) >= 2:
                    nav = self._extract_number(parts[1])
                    result_date = parts[0]
                    
                    # 🚨 VALIDATE: Reject future dates
                    if result_date != 'LATEST':
                        try:
                            date_dt = dt.strptime(result_date, '%Y-%m-%d')
                            if date_dt > today_dt:
                                logger.warning(f"⚠️ AI returned FUTURE date {result_date} for MF {ticker} - rejecting")
                                return None
                        except ValueError:
                            pass  # Allow processing to continue
                    
                    if nav and nav > 0:
                        return {'date': result_date, 'price': nav, 'sector': 'Mutual Fund'}
                else:
                    # Last resort: just extract number
                    nav = self._extract_number(clean_response)
                if nav and nav > 0:
                        return {'date': date or 'LATEST', 'price': nav, 'sector': 'Mutual Fund'}
            
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
    ) -> Optional[Dict[str, any]]:
        """
        Get stock price with date and sector using AI
        
        Args:
            ticker: Stock ticker (e.g., INFY, RELIANCE, 500325)
            stock_name: Stock name
            date: Target date (YYYY-MM-DD) or None for latest
            allow_closest: If True, return closest available date if exact not found
        
        Returns:
            Dict with {'date': 'YYYY-MM-DD', 'price': float, 'sector': str} or None
        """
        if not self.is_available():
            return None
        
        # CRITICAL: Be explicit to prevent code generation
        if date:
            prompt = f"""Get the ACTUAL stock price for this Indian stock:

Stock Name: {stock_name}
Ticker: {ticker}
Target Date: {date} (or nearest trading day)

Provide the REAL price data in this exact format:
{{'date': 'YYYY-MM-DD', 'price': <actual_price>, 'sector': '<company_sector>'}}

Replace:
- YYYY-MM-DD with the actual trading date
- <actual_price> with the real closing price
- <company_sector> with the company's sector (e.g., 'Banking', 'IT Services', 'Automobiles')

Return ONLY the dictionary with REAL data:"""
        else:
            prompt = f"""Get the LATEST stock price for this Indian stock:

Stock Name: {stock_name}
Ticker: {ticker}
Date: Latest closing price (yesterday or most recent trading day)

Provide the REAL price data in this exact format:
{{'date': 'YYYY-MM-DD', 'price': <actual_price>, 'sector': '<company_sector>'}}

Replace:
- YYYY-MM-DD with the actual trading date
- <actual_price> with the real closing price
- <company_sector> with the company's sector (e.g., 'Banking', 'IT Services', 'Automobiles')

Return ONLY the dictionary with REAL data:"""
        
        # LOG PROMPT FOR DEBUGGING (use print to bypass log filters)
        print(f"\n{'='*60}")
        print(f"📤 STOCK PROMPT for {ticker}:")
        print(prompt)
        print(f"{'='*60}\n")
        
        try:
            response = self._call_ai(prompt)
            print(f"📥 STOCK RESPONSE for {ticker}: {response}\n")
            if response and response != "NOT_FOUND":
                clean_response = response.strip()
                
                # 🚨 DETECT IF AI RETURNED CODE OR EXPLANATION INSTEAD OF DATA
                code_indicators = ['import ', 'def ', 'class ', 'for ', 'while ', 'if __name__', 'requests.', 'yfinance', 'pandas', 'datetime.']
                explanation_indicators = ['I am sorry', 'I do not have', 'I cannot', 'As an AI', 'I must adhere', 'I apologize']
                
                is_code = any(indicator in clean_response for indicator in code_indicators)
                is_explanation = any(indicator in clean_response for indicator in explanation_indicators)
                
                if is_code or is_explanation:
                    error_type = "CODE" if is_code else "EXPLANATION"
                    logger.error(f"❌ AI returned {error_type} instead of DATA for Stock {ticker}!")
                    logger.error(f"Response preview: {clean_response[:200]}...")
                    
                    # 🔄 RETRY WITH ALTERNATE AI PROVIDER
                    retry_response = self._retry_with_alternate_provider(prompt, max_tokens=300, ticker=ticker)
                    if retry_response and retry_response != response:
                        logger.info(f"✅ Retry successful for Stock {ticker}, re-parsing...")
                        clean_response = retry_response.strip()
                        # Continue to parsing below
                    else:
                        logger.warning(f"⚠️ Retry failed for Stock {ticker}, skipping")
                        return None
                
                # Try parsing as Python dictionary first (safest and cleanest)
                try:
                    import ast
                    from datetime import datetime as dt
                    today_dt = dt.now()
                    
                    # Extract dictionary from response (handle markdown code blocks)
                    if '```' in clean_response:
                        # Extract content between code blocks
                        clean_response = clean_response.split('```')[1]
                        if clean_response.startswith('python'):
                            clean_response = clean_response[6:]
                    
                    # Find dictionary in response
                    dict_start = clean_response.find('{')
                    dict_end = clean_response.rfind('}') + 1
                    if dict_start >= 0 and dict_end > dict_start:
                        dict_str = clean_response[dict_start:dict_end]
                        result = ast.literal_eval(dict_str)
                        
                        if isinstance(result, dict) and 'price' in result:
                            price = float(result.get('price', 0))
                            result_date = result.get('date', date or 'LATEST')
                            
                            # 🚨 VALIDATE: Reject future dates
                            if result_date != 'LATEST':
                                try:
                                    date_dt = dt.strptime(result_date, '%Y-%m-%d')
                                    if date_dt > today_dt:
                                        logger.warning(f"⚠️ AI returned FUTURE date {result_date} for {ticker} - rejecting")
                                        return None
                                except ValueError:
                                    logger.warning(f"⚠️ Invalid date format: {result_date}")
                                    return None
                            
                            if price > 0:
                                logger.info(f"✅ AI found price for {ticker}: ₹{price} on {result_date}, sector: {result.get('sector')}")
                                return {
                                    'date': result_date,
                                    'price': price,
                                    'sector': result.get('sector', 'Other Stocks')
                                }
                except Exception as e:
                    logger.debug(f"Failed to parse as dict: {e}, trying CSV fallback")
                
                # Fallback: CSV format (comma or pipe separated)
                from datetime import datetime as dt
                today_dt = dt.now()
                
                if ',' in clean_response:
                    parts = [p.strip() for p in clean_response.split(',')]
                elif '|' in clean_response:
                    parts = [p.strip() for p in clean_response.split('|')]
                else:
                    parts = []
                
                if len(parts) >= 3:
                    price = self._extract_number(parts[1])
                    result_date = parts[0]
                    
                    # 🚨 VALIDATE: Reject future dates
                    if result_date != 'LATEST':
                        try:
                            date_dt = dt.strptime(result_date, '%Y-%m-%d')
                            if date_dt > today_dt:
                                logger.warning(f"⚠️ AI returned FUTURE date {result_date} for {ticker} - rejecting")
                                return None
                        except ValueError:
                            pass  # Allow processing to continue
                    
                    if price and price > 0:
                        return {'date': result_date, 'price': price, 'sector': parts[2]}
                elif len(parts) >= 2:
                    price = self._extract_number(parts[1])
                    result_date = parts[0]
                    
                    # 🚨 VALIDATE: Reject future dates
                    if result_date != 'LATEST':
                        try:
                            date_dt = dt.strptime(result_date, '%Y-%m-%d')
                            if date_dt > today_dt:
                                logger.warning(f"⚠️ AI returned FUTURE date {result_date} for {ticker} - rejecting")
                                return None
                        except ValueError:
                            pass  # Allow processing to continue
                    
                    if price and price > 0:
                        return {'date': result_date, 'price': price, 'sector': 'Other Stocks'}
                else:
                    # Last resort: just extract number
                    price = self._extract_number(clean_response)
                if price and price > 0:
                        return {'date': date or 'LATEST', 'price': price, 'sector': 'Other Stocks'}
            
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
        end_date: str = 'TODAY',
        asset_type: str = 'Stock'
    ) -> Dict[str, Dict[str, any]]:
        """
        Get weekly prices with dates and sector for a ticker between two dates using AI
        
        Args:
            ticker: Ticker code
            name: Asset name
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD) or 'TODAY'
            asset_type: Type of asset (Stock, Mutual Fund, PMS, AIF)
        
        Returns:
            Dict of {date: {'price': float, 'sector': str}} with weekly prices
            Example: {'2024-01-01': {'price': 2500.50, 'sector': 'Banking'}, ...}
        """
        if not self.is_available():
            return {}
        
        # CRITICAL: Be explicit to prevent code generation AND future data
        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')
        
        prompt = f"""IMPORTANT: Respond ONLY with the data list below. NO explanations, NO text, NO code.

Asset: {name} ({ticker})
Period: {start_date} to {end_date} (weekly prices)
Today: {today}

RULES:
- Return weekly historical prices ONLY (no dates after {today})
- Format: Python list of dictionaries
- NO code, NO explanations, NO extra text
- Start your response with [ and end with ]

Required format (replace with ACTUAL data):
[
  {{'date': '2024-01-08', 'price': 2500.50, 'sector': 'Banking'}},
  {{'date': '2024-01-15', 'price': 2550.00, 'sector': 'Banking'}},
  ... (ALL weeks from {start_date} to {end_date}, stopping at {today} if needed)
]

RESPOND WITH ONLY THE DATA LIST (start with [, end with ]):"""
        
        # LOG PROMPT FOR DEBUGGING (use print to bypass log filters)
        print(f"\n{'='*60}")
        print(f"📤 WEEKLY RANGE PROMPT for {ticker}:")
        print(f"{'='*60}")
        print(prompt)
        print(f"{'='*60}\n")
        
        try:
            # Use higher max_tokens for weekly data (52 weeks × ~30 tokens = 1560 tokens needed)
            response = self._call_ai(prompt, max_tokens=1500)
            print(f"\n{'='*60}")
            print(f"📥 WEEKLY RANGE RESPONSE for {ticker}:")
            print(f"{'='*60}")
            print(response)
            print(f"{'='*60}\n")
            
            if not response:
                return {}
            
            # Parse response into dict (Python list format first, then CSV fallback)
            results = {}
            clean_response = response.strip()
            
            # 🚨 DETECT IF AI RETURNED CODE OR EXPLANATION INSTEAD OF DATA
            code_indicators = ['import ', 'def ', 'class ', 'for ', 'while ', 'if __name__', 'requests.', 'yfinance', 'pandas', 'datetime.']
            explanation_indicators = ['I am sorry', 'I do not have', 'I cannot', 'As an AI', 'I must adhere', 'I apologize']
            
            is_code = any(indicator in clean_response for indicator in code_indicators)
            is_explanation = any(indicator in clean_response for indicator in explanation_indicators)
            
            if is_code or is_explanation:
                error_type = "CODE" if is_code else "EXPLANATION"
                logger.error(f"❌ AI returned {error_type} instead of DATA for weekly range {ticker}!")
                logger.error(f"Response preview: {clean_response[:200]}...")
                
                # 🔄 RETRY WITH ALTERNATE AI PROVIDER
                retry_response = self._retry_with_alternate_provider(prompt, max_tokens=1500, ticker=ticker)
                if retry_response and retry_response != response:
                    logger.info(f"✅ Retry successful for weekly range {ticker}, re-parsing...")
                    clean_response = retry_response.strip()
                    # Continue to parsing below
                else:
                    logger.warning(f"⚠️ Retry failed for weekly range {ticker}, skipping")
                    return {}
            
            # Try parsing as Python list of dictionaries first (cleanest)
            try:
                import ast
                from datetime import datetime as dt
                today_dt = dt.now()
                
                # Extract list from response (handle markdown code blocks)
                if '```' in clean_response:
                    clean_response = clean_response.split('```')[1]
                    if clean_response.startswith('python'):
                        clean_response = clean_response[6:]
                
                # Find list in response
                list_start = clean_response.find('[')
                list_end = clean_response.rfind(']') + 1
                if list_start >= 0 and list_end > list_start:
                    list_str = clean_response[list_start:list_end]
                    price_list = ast.literal_eval(list_str)
                    
                    future_dates_skipped = 0
                    if isinstance(price_list, list):
                        for item in price_list:
                            if isinstance(item, dict) and 'date' in item and 'price' in item:
                                date = item.get('date')
                                price = float(item.get('price', 0))
                                sector = item.get('sector', 'Other')
                                
                                # 🚨 VALIDATE: Reject future dates
                                try:
                                    date_dt = dt.strptime(date, '%Y-%m-%d')
                                    if date_dt > today_dt:
                                        future_dates_skipped += 1
                                        logger.warning(f"⚠️ Skipping FUTURE date {date} for {ticker} (today: {today})")
                                        continue
                                except ValueError:
                                    logger.warning(f"⚠️ Invalid date format: {date}")
                                    continue
                                
                                if price > 0 and price < 1000000000:
                                    results[date] = {
                                        'price': price,
                                        'sector': sector
                                    }
                        
                        if future_dates_skipped > 0:
                            logger.warning(f"⚠️ Rejected {future_dates_skipped} FUTURE dates from AI response for {ticker}")
                        
                        if results:
                            logger.info(f"✅ AI weekly range (Python list): {ticker} - {len(results)} weekly prices")
                            return results
            except Exception as e:
                logger.debug(f"Failed to parse as Python list: {e}, trying CSV fallback")
            
            # Fallback: CSV format (comma or pipe separated, line by line)
            from datetime import datetime as dt
            today_dt = dt.now()
            future_dates_skipped_csv = 0
            
            for line in response.strip().split('\n'):
                line = line.strip()
                
                # Skip empty lines or headers
                if not line or line.lower().startswith(('date', 'ticker', 'week', 'note', 'source', 'example', 'your output', '[', ']')):
                    continue
                
                # Handle different separators: comma (CSV) first, then pipe, colon, tab
                if ',' in line:
                    parts = [p.strip() for p in line.split(',')]
                elif '|' in line:
                    parts = [p.strip() for p in line.split('|')]
                elif ':' in line and line.count(':') == 1:
                    parts = [p.strip() for p in line.split(':')]
                elif '\t' in line:
                    parts = [p.strip() for p in line.split('\t')]
                else:
                    continue
                
                if len(parts) >= 2:
                    try:
                        date = parts[0]
                        price = self._extract_number(parts[1])
                        sector = parts[2] if len(parts) >= 3 else 'Other'
                        
                        # 🚨 VALIDATE: Reject future dates
                        try:
                            date_dt = dt.strptime(date, '%Y-%m-%d')
                            if date_dt > today_dt:
                                future_dates_skipped_csv += 1
                                logger.warning(f"⚠️ Skipping FUTURE date {date} for {ticker} (today: {today})")
                                continue
                        except ValueError:
                            # Date format issue, skip
                            continue
                        
                        if price and price > 0 and price < 1000000000:
                            results[date] = {
                                'price': price,
                                'sector': sector
                            }
                    except (ValueError, IndexError) as e:
                        logger.debug(f"Failed to parse line '{line}': {e}")
                        continue
            
            if future_dates_skipped_csv > 0:
                logger.warning(f"⚠️ Rejected {future_dates_skipped_csv} FUTURE dates from CSV fallback for {ticker}")
            
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
        
        # LOG PROMPT FOR DEBUGGING
        logger.info(f"📤 BULK PROMPT ({len(tickers_with_names)} tickers, {len(dates)} dates):\n{prompt}\n{'='*50}")
        
        try:
            # Use higher max_tokens for bulk data (5 tickers × 10 dates = 50 entries × 30 tokens = 1500)
            response = self._call_ai(prompt, max_tokens=1500)
            logger.info(f"📥 BULK RESPONSE:\n{response}\n{'='*50}")
            
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
    ) -> Optional[Dict[str, any]]:
        """
        Get PMS/AIF NAV with date and category using AI
        
        Args:
            ticker: SEBI registration code
            fund_name: Fund name
            date: Target date or None for latest
        
        Returns:
            Dict with {'date': 'YYYY-MM-DD', 'price': float, 'sector': str} or None
        """
        if not self.is_available():
            return None
        
        # CRITICAL: Be explicit to prevent code generation
        if date:
            prompt = f"""You are a financial data API. Provide ACTUAL PMS/AIF NAV data.

🚫 DO NOT write Python code
🚫 DO NOT use any libraries
🚫 DO NOT write functions or import statements
✅ ONLY return the actual NAV data in the format below

Fund: {fund_name}
SEBI Code: {ticker}
Date: {date} (or nearest available date)

Return ONLY this exact text format (replace with actual values):
{{'date': 'YYYY-MM-DD', 'price': 1250.50, 'sector': 'PMS Equity'}}

Example response:
{{'date': '2024-10-14', 'price': 1250.50, 'sector': 'PMS Equity'}}

Your response (actual data only, no code):"""
        else:
            prompt = f"""You are a financial data API. Provide ACTUAL PMS/AIF NAV data.

🚫 DO NOT write Python code
🚫 DO NOT use any libraries
🚫 DO NOT write functions or import statements
✅ ONLY return the actual NAV data in the format below

Fund: {fund_name}
SEBI Code: {ticker}
Date: LATEST (most recent NAV available)

Return ONLY this exact text format (replace with actual values):
{{'date': 'YYYY-MM-DD', 'price': 1250.50, 'sector': 'PMS Equity'}}

Example response:
{{'date': '2024-10-13', 'price': 1250.50, 'sector': 'PMS Equity'}}

Your response (actual data only, no code):"""
        
        # LOG PROMPT FOR DEBUGGING
        logger.info(f"📤 PMS/AIF PROMPT for {ticker}:\n{prompt}\n{'='*50}")
        
        try:
            response = self._call_ai(prompt)
            logger.info(f"📥 PMS/AIF RESPONSE for {ticker}: {response}")
            if response and response != "NOT_FOUND":
                clean_response = response.strip()
                
                # 🚨 DETECT IF AI RETURNED CODE OR EXPLANATION INSTEAD OF DATA
                code_indicators = ['import ', 'def ', 'class ', 'for ', 'while ', 'if __name__', 'requests.', 'yfinance', 'pandas', 'datetime.']
                explanation_indicators = ['I am sorry', 'I do not have', 'I cannot', 'As an AI', 'I must adhere', 'I apologize']
                
                is_code = any(indicator in clean_response for indicator in code_indicators)
                is_explanation = any(indicator in clean_response for indicator in explanation_indicators)
                
                if is_code or is_explanation:
                    error_type = "CODE" if is_code else "EXPLANATION"
                    logger.error(f"❌ AI returned {error_type} instead of DATA for PMS/AIF {ticker}!")
                    logger.error(f"Response preview: {clean_response[:200]}...")
                    
                    # 🔄 RETRY WITH ALTERNATE AI PROVIDER
                    retry_response = self._retry_with_alternate_provider(prompt, max_tokens=300, ticker=ticker)
                    if retry_response and retry_response != response:
                        logger.info(f"✅ Retry successful for PMS/AIF {ticker}, re-parsing...")
                        clean_response = retry_response.strip()
                        # Continue to parsing below
                    else:
                        logger.warning(f"⚠️ Retry failed for PMS/AIF {ticker}, skipping")
                        return None
                
                # Try parsing as Python dictionary first (safest and cleanest)
                try:
                    import ast
                    # Extract dictionary from response (handle markdown code blocks)
                    if '```' in clean_response:
                        clean_response = clean_response.split('```')[1]
                        if clean_response.startswith('python'):
                            clean_response = clean_response[6:]
                    
                    # Find dictionary in response
                    dict_start = clean_response.find('{')
                    dict_end = clean_response.rfind('}') + 1
                    if dict_start >= 0 and dict_end > dict_start:
                        dict_str = clean_response[dict_start:dict_end]
                        result = ast.literal_eval(dict_str)
                        
                        if isinstance(result, dict) and 'price' in result:
                            nav = float(result.get('price', 0))
                            if nav > 0:
                                logger.info(f"✅ AI found PMS/AIF NAV for {ticker}: ₹{nav} on {result.get('date')}, category: {result.get('sector')}")
                                return {
                                    'date': result.get('date', date or 'LATEST'),
                                    'price': nav,
                                    'sector': result.get('sector', 'PMS/AIF')
                                }
                except Exception as e:
                    logger.debug(f"Failed to parse as dict: {e}, trying CSV fallback")
                
                # Fallback: CSV format (comma or pipe separated)
                if ',' in clean_response:
                    parts = [p.strip() for p in clean_response.split(',')]
                elif '|' in clean_response:
                    parts = [p.strip() for p in clean_response.split('|')]
                else:
                    parts = []
                
                if len(parts) >= 3:
                    nav = self._extract_number(parts[1])
                    if nav and nav > 0:
                        return {'date': parts[0], 'price': nav, 'sector': parts[2]}
                elif len(parts) >= 2:
                    nav = self._extract_number(parts[1])
                    if nav and nav > 0:
                        return {'date': parts[0], 'price': nav, 'sector': 'PMS/AIF'}
                else:
                    # Last resort: just extract number
                    nav = self._extract_number(clean_response)
                    if nav and nav > 0:
                        return {'date': date or 'LATEST', 'price': nav, 'sector': 'PMS/AIF'}
            
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
    
    def _call_ai(self, prompt: str, max_tokens: int = 100) -> Optional[str]:
        """
        Call AI service (OpenAI FIRST for paid tier, Gemini fallback)
        
        Args:
            prompt: The prompt to send
            max_tokens: Maximum tokens for AI response (default: 100)
                       - Single price: 50-100
                       - Weekly range (52 weeks): 1500
                       - Performance data: 300
        
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
        
        # 🔄 HYBRID STRATEGY: Gemini FIRST (FREE), then OpenAI BACKUP (PAID)
        
        # Try Gemini FIRST (FREE - maximize free usage!)
        if self.gemini_client:
            # Rate limiting for Gemini (10/min free tier)
            if self._call_count >= 9:
                wait_time = max(0, 60 - elapsed)
                if wait_time > 0:
                    print(f"⏳ Gemini quota: 9/10 used. Switching to OpenAI...")
                    # Don't wait, immediately switch to OpenAI
                    self._call_count = 0
                    self._call_start_time = time.time()
            else:
                # Use Gemini if we haven't hit the limit
                try:
                    if self._call_count > 0:
                        time.sleep(0.3)  # 300ms between calls
                    
                    print(f"🤖 Calling Gemini FREE (call {self._call_count + 1}/9)...")
                    response = self.gemini_client.generate_content(prompt)
                                
                    if response and response.text:
                        self._call_count += 1
                        print(f"✅ Gemini successful ({self._call_count}/9 used)")
                        return response.text.strip()
                except Exception as e:
                            logger.error(f"❌ Gemini call failed: {e}")
                            # If rate limit, switch to OpenAI
                            if "429" in str(e) or "quota" in str(e).lower():
                                print(f"⚠️ Gemini rate limit hit! Switching to OpenAI...")
                                self._call_count = 9  # Mark as exhausted
                        # Fall through to OpenAI
        
        # Try OpenAI as BACKUP (PAID - when Gemini fails or hits limit)
        if self.openai_client:
            try:
                print(f"🤖 Calling OpenAI BACKUP (max_tokens={max_tokens})...")
                response = self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a financial data expert. Provide only numeric answers."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0,
                    max_tokens=max_tokens  # Dynamic based on request type
                )
                if response.choices and response.choices[0].message:
                    print(f"✅ OpenAI call successful")
                    return response.choices[0].message.content.strip()
            except Exception as e:
                logger.error(f"❌ OpenAI call failed: {e}")
        
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

