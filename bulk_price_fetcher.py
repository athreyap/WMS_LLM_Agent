#!/usr/bin/env python3
"""
Bulk Price Fetcher - Optimized for Speed & Cost
Uses official free sources first, AI as fallback
"""

import requests
import pandas as pd
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import yfinance as yf

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BulkPriceFetcher:
    """Fetch prices in bulk from official sources + AI fallback"""
    
    def __init__(self):
        self.amfi_cache = None
        self.amfi_cache_time = None
        
    def get_all_mf_navs_bulk(self) -> pd.DataFrame:
        """
        Get ALL MF NAVs from AMFI India (FREE, ~10,000 funds)
        Updates daily, cached for 1 hour
        """
        # Use cache if available (1 hour)
        if self.amfi_cache is not None:
            cache_age = (datetime.now() - self.amfi_cache_time).seconds
            if cache_age < 3600:  # 1 hour
                logger.info(f"✅ Using AMFI cache (age: {cache_age}s)")
                return self.amfi_cache
        
        try:
            logger.info("📥 Downloading AMFI bulk data (~10,000 MF NAVs)...")
            url = "https://www.amfiindia.com/spages/NAVAll.txt"
            response = requests.get(url, timeout=10)
            
            data = []
            current_scheme_type = None
            
            for line in response.text.split('\n'):
                line = line.strip()
                
                # Skip empty lines
                if not line:
                    continue
                
                # Check if it's a scheme type header
                if line.endswith('Mutual Fund'):
                    current_scheme_type = line
                    continue
                
                # Parse NAV data
                if ';' in line:
                    parts = line.split(';')
                    if len(parts) >= 5:
                        try:
                            code = parts[0].strip()
                            isin_dividend = parts[1].strip()
                            isin_reinvest = parts[2].strip()
                            name = parts[3].strip()
                            nav = parts[4].strip()
                            
                            # Skip invalid entries
                            if not code or code == 'N.A.':
                                continue
                            
                            data.append({
                                'code': code,
                                'name': name,
                                'nav': float(nav) if nav and nav != 'N.A.' else None,
                                'scheme_type': current_scheme_type,
                                'isin_dividend': isin_dividend,
                                'isin_reinvest': isin_reinvest
                            })
                        except (ValueError, IndexError) as e:
                            continue
            
            df = pd.DataFrame(data)
            
            # Cache the result
            self.amfi_cache = df
            self.amfi_cache_time = datetime.now()
            
            logger.info(f"✅ Downloaded {len(df)} MF NAVs from AMFI")
            return df
            
        except Exception as e:
            logger.error(f"❌ AMFI bulk download failed: {e}")
            return pd.DataFrame()
    
    def get_mf_navs_for_tickers(self, tickers: List[str]) -> Dict[str, float]:
        """Get NAVs for specific MF tickers from AMFI bulk data"""
        all_navs = self.get_all_mf_navs_bulk()
        
        if all_navs.empty:
            return {}
        
        # Debug: show sample of AMFI data
        logger.info(f"📊 AMFI data sample: {all_navs.head(3)[['code', 'name', 'nav']].to_dict('records')}")
        
        results = {}
        for ticker in tickers:
            # Clean ticker - remove MF_ prefix and convert to string
            clean_ticker = str(ticker).strip().replace('MF_', '')
            
            # Try exact match first
            nav_data = all_navs[all_navs['code'].astype(str) == clean_ticker]
            
            if not nav_data.empty and pd.notna(nav_data.iloc[0]['nav']):
                nav = float(nav_data.iloc[0]['nav'])
                results[ticker] = nav
                logger.info(f"✅ {ticker}: NAV ₹{nav} from AMFI")
            else:
                logger.warning(f"⚠️ {ticker} (clean: {clean_ticker}) not found in AMFI data")
                # Debug: show similar codes
                similar = all_navs[all_navs['code'].astype(str).str.contains(clean_ticker[:3], na=False)]
                if not similar.empty:
                    logger.info(f"   Similar codes: {similar.head(3)['code'].tolist()}")
        
        return results
    
    def get_stocks_bulk(self, tickers: List[str]) -> Dict[str, float]:
        """
        Get stock prices in bulk using yfinance
        Much faster than individual calls
        Handles both NSE (.NS) and BSE (.BO) stocks
        """
        if not tickers:
            return {}
        
        try:
            logger.info(f"📥 Bulk downloading {len(tickers)} stock prices...")
            
            # Add correct suffix (.NS for NSE, .BO for BSE)
            ticker_list = []
            ticker_to_suffix = {}
            for t in tickers:
                # BSE codes: 6 digits starting with 5
                if t.isdigit() and len(t) == 6 and t.startswith('5'):
                    ticker_with_suffix = f"{t}.BO"
                    ticker_to_suffix[t] = '.BO'
                    logger.info(f"   📍 BSE stock: {t} → {ticker_with_suffix}")
                else:
                    ticker_with_suffix = f"{t}.NS"
                    ticker_to_suffix[t] = '.NS'
                ticker_list.append(ticker_with_suffix)
            
            # Bulk download (1 API call for all stocks!)
            data = yf.download(
                ticker_list,
                period="1d",
                group_by='ticker',
                progress=False,
                threads=True
            )
            
            results = {}
            
            # Parse results
            if len(tickers) == 1:
                # Single ticker
                if not data.empty and 'Close' in data.columns:
                    price = float(data['Close'].iloc[-1])
                    # Filter out NaN/inf values
                    import math
                    if not math.isnan(price) and not math.isinf(price) and price > 0:
                        results[tickers[0]] = price
                        suffix = ticker_to_suffix[tickers[0]]
                        logger.info(f"✅ {tickers[0]} ({suffix}): ₹{price}")
                    else:
                        logger.warning(f"⚠️ {tickers[0]}: Invalid price (NaN/inf), skipping")
            else:
                # Multiple tickers
                import math
                for ticker in tickers:
                    suffix = ticker_to_suffix[ticker]
                    ticker_with_suffix = f"{ticker}{suffix}"
                    try:
                        if ticker_with_suffix in data.columns.levels[0]:
                            ticker_data = data[ticker_with_suffix]
                            if not ticker_data.empty and 'Close' in ticker_data.columns:
                                price = float(ticker_data['Close'].iloc[-1])
                                # Filter out NaN/inf values
                                if not math.isnan(price) and not math.isinf(price) and price > 0:
                                    results[ticker] = price
                                    logger.info(f"✅ {ticker} ({suffix}): ₹{price}")
                                else:
                                    logger.warning(f"⚠️ {ticker} ({suffix}): Invalid price (NaN/inf), will try AI fallback")
                    except:
                        continue
            
            logger.info(f"✅ Downloaded {len(results)}/{len(tickers)} stock prices")
            return results
            
        except Exception as e:
            logger.error(f"❌ Bulk stock download failed: {e}")
            return {}
    
    def get_bulk_mf_nav_isin(self, codes: List[str], names: Dict[str, str]) -> Dict[str, float]:
        """
        Get MF NAV for ISIN/AMFI codes using AI bulk
        Batches 20 codes per AI call
        Handles both ISIN (12 chars) and AMFI (5-6 digit) codes
        """
        from ai_price_fetcher import AIPriceFetcher
        
        ai = AIPriceFetcher()
        if not ai.is_available():
            logger.warning("AI not available for MF NAV lookup")
            return {}
        
        results = {}
        
        # Process in batches of 20
        for i in range(0, len(codes), 20):
            batch = codes[i:i+20]
            logger.info(f"🤖 AI bulk fetch: Processing batch {i//20 + 1} ({len(batch)} MF codes)...")
            
            try:
                # Build prompt - adapt based on code type
                fund_list = []
                for idx, code in enumerate(batch):
                    name = names.get(code, code)
                    # Detect code type
                    if code.startswith('IN') and len(code) == 12:
                        fund_list.append(f"{idx+1}. ISIN: {code}, Fund: {name}")
                    else:
                        fund_list.append(f"{idx+1}. AMFI Code: {code}, Fund: {name}")
                
                prompt = f"""Get the LATEST NAV for these Indian mutual funds:

{chr(10).join(fund_list)}

Return ONLY in this exact format (one per line):
CODE|NAV

Examples:
INF740K01NY4|49.52
119019|146.58
102949|296.80

Rules:
- One fund per line
- Format: CODE|NAV (numeric only, no currency symbols)
- CODE can be ISIN (12 chars) or AMFI scheme code (5-6 digits)
- Skip if not found
- Code must match exactly"""
                
                # Make AI call with automatic OpenAI fallback
                response = None
                try:
                    response = ai.gemini_client.generate_content(prompt)
                except Exception as gemini_error:
                    logger.warning(f"⚠️ Gemini failed (batch {i//20 + 1}): {str(gemini_error)[:100]}, trying OpenAI...")
                    if ai.openai_client:
                        try:
                            response_obj = ai.openai_client.chat.completions.create(
                                model="gpt-4o-mini",
                                messages=[{"role": "user", "content": prompt}],
                                max_tokens=500
                            )
                            # Create a mock response object with .text attribute
                            class MockResponse:
                                def __init__(self, text):
                                    self.text = text
                            response = MockResponse(response_obj.choices[0].message.content)
                            logger.info(f"✅ OpenAI succeeded for batch {i//20 + 1}")
                        except Exception as openai_error:
                            logger.error(f"❌ OpenAI also failed: {str(openai_error)[:100]}")
                            continue
                    else:
                        logger.error("❌ No AI backup available")
                        continue
                
                if response is None:
                    logger.warning(f"⚠️ Skipping batch {i//20 + 1} - no response from any AI")
                    continue
                
                # Parse response
                for line in response.text.strip().split('\n'):
                    if '|' not in line:
                        continue
                    
                    parts = line.split('|')
                    if len(parts) >= 2:
                        code = parts[0].strip()
                        try:
                            nav = float(parts[1].strip())
                            results[code] = nav
                            logger.info(f"✅ AI: {code} = ₹{nav}")
                        except ValueError:
                            continue
            
            except Exception as batch_error:
                logger.error(f"❌ Batch {i//20 + 1} processing error: {batch_error}")
                continue
        
        logger.info(f"✅ AI bulk fetch complete: {len(results)}/{len(codes)} MF codes")
        return results
    
    def get_bulk_mf_nav_by_name(self, codes: List[str], names: Dict[str, str]) -> Dict[str, float]:
        """
        Get MF NAV by fund name (fallback when codes don't work)
        Uses AI to search by fund name instead of code
        """
        from ai_price_fetcher import AIPriceFetcher
        
        ai = AIPriceFetcher()
        if not ai.is_available():
            logger.warning("AI not available for name-based MF lookup")
            return {}
        
        results = {}
        
        # Process in batches of 15 (names are longer, so smaller batches)
        for i in range(0, len(codes), 15):
            batch = codes[i:i+15]
            logger.info(f"🤖 AI name-based fetch: Processing batch {i//15 + 1} ({len(batch)} funds)...")
            
            try:
                # Build prompt using fund names
                fund_list = []
                for idx, code in enumerate(batch):
                    name = names.get(code, code)
                    fund_list.append(f"{idx+1}. Fund Name: {name}")
                
                prompt = f"""Get the LATEST NAV for these Indian mutual funds BY NAME:

{chr(10).join(fund_list)}

Return ONLY in this exact format (one per line):
FUND_NAME_PARTIAL|NAV

Example:
HDFC Hybrid Equity|296.80
Axis Mid Cap Fund|80.37
DSP Dynamic Asset|49.52

Rules:
- One fund per line
- Use partial fund name (first 3-4 words)
- Format: FUND_NAME|NAV (numeric only, no currency symbols)
- Skip if not found"""
                
                # Make AI call with automatic OpenAI fallback
                response = None
                try:
                    response = ai.gemini_client.generate_content(prompt)
                except Exception as gemini_error:
                    logger.warning(f"⚠️ Gemini failed (batch {i//15 + 1}): {str(gemini_error)[:100]}, trying OpenAI...")
                    if ai.openai_client:
                        try:
                            response_obj = ai.openai_client.chat.completions.create(
                                model="gpt-4o-mini",
                                messages=[{"role": "user", "content": prompt}],
                                max_tokens=500
                            )
                            class MockResponse:
                                def __init__(self, text):
                                    self.text = text
                            response = MockResponse(response_obj.choices[0].message.content)
                            logger.info(f"✅ OpenAI succeeded for batch {i//15 + 1}")
                        except Exception as openai_error:
                            logger.error(f"❌ OpenAI also failed: {str(openai_error)[:100]}")
                            continue
                    else:
                        logger.error("❌ No AI backup available")
                        continue
                
                if response is None:
                    logger.warning(f"⚠️ Skipping batch {i//15 + 1} - no response from any AI")
                    continue
                
                # Parse response - match by fund name similarity
                for line in response.text.strip().split('\n'):
                    if '|' not in line:
                        continue
                    
                    parts = line.split('|')
                    if len(parts) >= 2:
                        response_name = parts[0].strip().lower()
                        try:
                            nav = float(parts[1].strip())
                            
                            # Try to match with original codes by name similarity
                            for code in batch:
                                fund_name = names.get(code, '').lower()
                                # Check if response name is in the full fund name
                                if response_name in fund_name or fund_name[:30] in response_name:
                                    results[code] = nav
                                    logger.info(f"✅ AI (by name): {code} ({names[code][:40]}) = ₹{nav}")
                                    break
                        except ValueError:
                            continue
            
            except Exception as batch_error:
                logger.error(f"❌ Batch {i//15 + 1} processing error: {batch_error}")
                continue
        
        logger.info(f"✅ AI name-based fetch complete: {len(results)}/{len(codes)} funds")
        return results
    
    def get_bulk_prices_with_ai(
        self, 
        tickers: List[str], 
        ticker_names: Dict[str, str],
        ticker_type: str = 'MF'
    ) -> Dict[str, float]:
        """
        Get prices for multiple tickers using AI (bulk call)
        
        Args:
            tickers: List of ticker codes
            ticker_names: Dict mapping ticker to full name
            ticker_type: 'MF', 'PMS', or 'STOCK'
        """
        from ai_price_fetcher import AIPriceFetcher
        import google.generativeai as genai
        
        ai = AIPriceFetcher()
        if not ai.is_available():
            logger.warning("AI not available")
            return {}
        
        # Build bulk request
        ticker_list = []
        for ticker in tickers:
            name = ticker_names.get(ticker, ticker)
            ticker_list.append(f"{ticker}|{name}")
        
        if ticker_type == 'MF':
            prompt = f"""Get the LATEST NAV for these Indian mutual funds:

{chr(10).join([f"{i+1}. Code: {t.split('|')[0]}, Fund: {t.split('|')[1]}" for i, t in enumerate(ticker_list)])}

Return ONLY in this format (one per line):
CODE|NAV_VALUE

Example:
102949|296.88
119551|125.50

Rules:
- One fund per line
- Format: CODE|NAV (numeric only)
- No currency symbols
- Skip if not found"""
        
        elif ticker_type == 'PMS':
            prompt = f"""Get the LATEST performance for these PMS/AIF funds:

{chr(10).join([f"{i+1}. Code: {t.split('|')[0]}, Fund: {t.split('|')[1]}" for i, t in enumerate(ticker_list)])}

Return ONLY in this format (one per line):
CODE|1Y:XX.XX|3Y:XX.XX|5Y:XX.XX

Example:
INP000005000|1Y:30.65|3Y:17.51|5Y:20.35
INP000000613|1Y:23.50|3Y:21.00|5Y:26.50

Rules:
- One fund per line
- Values in percentage
- Skip periods if not available"""
        
        else:  # STOCK
            return {}  # Use yfinance for stocks
        
        # Make AI call with automatic OpenAI fallback
        response = None
        try:
            response = ai.gemini_client.generate_content(prompt)
            logger.info(f"✅ Gemini succeeded for {ticker_type}")
        except Exception as gemini_error:
            logger.warning(f"⚠️ Gemini failed for {ticker_type}: {str(gemini_error)[:100]}, trying OpenAI...")
            if ai.openai_client:
                try:
                    response_obj = ai.openai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=500
                    )
                    class MockResponse:
                        def __init__(self, text):
                            self.text = text
                    response = MockResponse(response_obj.choices[0].message.content)
                    logger.info(f"✅ OpenAI succeeded for {ticker_type}")
                except Exception as openai_error:
                    logger.error(f"❌ OpenAI also failed for {ticker_type}: {str(openai_error)[:100]}")
                    return {}
            else:
                logger.error("❌ No AI backup available")
                return {}
        
        if response is None:
            logger.warning(f"⚠️ No response from any AI for {ticker_type}")
            return {}
        
        # Parse response
        results = {}
        try:
            # Debug: Print full response
            print(f"\n🔍 DEBUG: AI Response for {ticker_type}:")
            print(f"{'=' * 80}")
            print(response.text[:500])  # First 500 chars to avoid spam
            print(f"{'=' * 80}\n")
            
            # Clean response text (remove markdown code blocks, explanations, etc.)
            response_text = response.text.strip()
            
            # Remove markdown code blocks if present
            if '```' in response_text:
                # Extract content between code blocks
                parts = response_text.split('```')
                for part in parts:
                    if '|' in part and not part.startswith('python'):
                        response_text = part.strip()
                        break
            
            for line in response_text.split('\n'):
                line = line.strip()
                
                # Skip empty lines, explanations, headers
                if not line or '|' not in line:
                    continue
                
                # Skip lines that look like headers or explanations
                if any(word in line.lower() for word in ['code', 'fund', 'name', 'nav', 'example', 'format', 'rule']):
                    if line.count('|') <= 1 or not any(char.isdigit() for char in line):
                        continue
                
                parts = line.split('|')
                if len(parts) < 2:
                    continue
                
                code = parts[0].strip()
                
                # Validate code format
                if not code or len(code) < 3:
                    continue
                
                if ticker_type == 'MF':
                    try:
                        # Extract numeric value (remove currency symbols, commas)
                        nav_str = parts[1].strip().replace('₹', '').replace(',', '').replace('Rs', '').replace('.', '', parts[1].count('.') - 1)
                        nav = float(nav_str)
                        if nav > 0:
                            results[code] = nav
                            logger.info(f"✅ AI: {code} = ₹{nav}")
                    except Exception as e:
                        logger.debug(f"   Failed to parse MF line: {line} - {e}")
                        continue
                
                elif ticker_type == 'PMS':
                    # Parse returns data (stored differently)
                    returns = {}
                    for part in parts[1:]:
                        if ':' in part:
                            try:
                                period, value = part.split(':')
                                period = period.strip()
                                value = value.strip().replace('%', '').replace(',', '')
                                returns[period] = float(value)
                            except:
                                continue
                    
                    if returns:
                        results[code] = returns
                        logger.info(f"✅ AI: {code} = {returns}")
        except Exception as parse_error:
            logger.error(f"❌ Error parsing AI response for {ticker_type}: {parse_error}")
            import traceback
            traceback.print_exc()
        
        logger.info(f"📊 Parsed {len(results)} valid results from AI response")
        return results
    
    def _find_nearest_trading_day_price(self, data, ticker_with_suffix, target_date, is_single_ticker=False, max_days=7):
        """
        Find the nearest trading day price for holidays/weekends
        
        Args:
            data: yfinance DataFrame
            ticker_with_suffix: Ticker symbol with exchange suffix (e.g., RELIANCE.NS)
            target_date: Target date string (YYYY-MM-DD)
            is_single_ticker: True if only one ticker in data
            max_days: Maximum days to look before/after (default: 7 for holiday weeks)
        
        Returns:
            (price, actual_date, days_diff) or (None, None, None) if not found
        """
        from datetime import datetime, timedelta
        import math
        
        target_dt = pd.to_datetime(target_date)
        
        # Try exact date first
        if target_date in data.index:
            if is_single_ticker:
                price = float(data.loc[target_date, 'Close'])
            else:
                price = float(data['Close'][ticker_with_suffix].loc[target_date])
            
            if pd.notna(price) and not math.isinf(price) and price > 0:
                return price, target_date, 0
        
        # Search nearby dates (prefer previous days for historical accuracy)
        for days_back in range(1, max_days + 1):
            # Try previous day first (more accurate for historical transactions)
            prev_date = (target_dt - timedelta(days=days_back)).strftime('%Y-%m-%d')
            if prev_date in data.index:
                try:
                    if is_single_ticker:
                        price = float(data.loc[prev_date, 'Close'])
                    else:
                        price = float(data['Close'][ticker_with_suffix].loc[prev_date])
                    
                    if pd.notna(price) and not math.isinf(price) and price > 0:
                        return price, prev_date, -days_back
                except:
                    pass
            
            # Try next day (in case transaction was pre-dated)
            next_date = (target_dt + timedelta(days=days_back)).strftime('%Y-%m-%d')
            if next_date in data.index:
                try:
                    if is_single_ticker:
                        price = float(data.loc[next_date, 'Close'])
                    else:
                        price = float(data['Close'][ticker_with_suffix].loc[next_date])
                    
                    if pd.notna(price) and not math.isinf(price) and price > 0:
                        return price, next_date, days_back
                except:
                    pass
        
        return None, None, None
    
    def get_stocks_historical_bulk(self, tickers: List[str], dates: List[str]) -> Dict[str, Dict[str, float]]:
        """
        Get historical prices for stocks in bulk for specific dates
        Returns: {ticker: {date: price}}
        
        Features:
        - Finds nearest trading day for holidays/weekends (±7 days)
        - Skips NaN/inf values
        - Only returns valid prices
        """
        if not tickers or not dates:
            return {}
        
        try:
            from datetime import datetime
            
            logger.info(f"📥 Bulk downloading historical prices for {len(tickers)} stocks...")
            
            # Convert dates to datetime
            dates_dt = [pd.to_datetime(d) for d in dates]
            start_date = min(dates_dt) - pd.Timedelta(days=7)  # Extra buffer for holidays
            end_date = max(dates_dt) + pd.Timedelta(days=7)
            
            # Add correct suffix (.NS for NSE, .BO for BSE)
            ticker_list = []
            ticker_to_suffix = {}
            for t in tickers:
                # BSE codes: 6 digits starting with 5
                if t.isdigit() and len(t) == 6 and t.startswith('5'):
                    ticker_with_suffix = f"{t}.BO"
                    ticker_to_suffix[t] = '.BO'
                else:
                    ticker_with_suffix = f"{t}.NS"
                    ticker_to_suffix[t] = '.NS'
                ticker_list.append(ticker_with_suffix)
            
            # Bulk download
            data = yf.download(
                ticker_list,
                start=start_date,
                end=end_date,
                progress=False,
                threads=True
            )
            
            results = {}
            nearest_count = 0
            nan_count = 0
            
            is_single = len(tickers) == 1
            
            # Parse results for each ticker and date
            for ticker in tickers:
                suffix = ticker_to_suffix[ticker]
                ticker_with_suffix = f"{ticker}{suffix}"
                results[ticker] = {}
                
                for date in dates:
                    date_str = pd.to_datetime(date).strftime('%Y-%m-%d')
                    
                    # Try to find nearest trading day price
                    price, actual_date, days_diff = self._find_nearest_trading_day_price(
                        data, ticker_with_suffix, date_str, is_single_ticker=is_single
                    )
                    
                    if price is not None:
                        results[ticker][date_str] = price
                        if days_diff != 0:
                            nearest_count += 1
                            logger.debug(f"   📅 {ticker} @ {date_str}: Used {actual_date} ({abs(days_diff)} days {'before' if days_diff < 0 else 'after'})")
                    else:
                        nan_count += 1
                        logger.debug(f"   ⚠️ {ticker} @ {date_str}: No nearby data (will use AI)")
            
            if nearest_count > 0:
                logger.info(f"📅 Found {nearest_count} prices from nearby trading days (holidays/weekends)")
            if nan_count > 0:
                logger.info(f"⚠️ {nan_count} prices unavailable (AI fallback will handle)")
            logger.info(f"✅ Historical bulk download complete")
            return results
            
        except Exception as e:
            logger.error(f"❌ Historical bulk download failed: {e}")
            return {}
    
    def get_stocks_weekly_bulk(self, tickers: List[str], weeks: int = 26) -> Dict[str, pd.DataFrame]:
        """
        Get weekly prices for stocks in bulk (default: 26 weeks = 6 months)
        Returns: {ticker: DataFrame with weekly prices}
        """
        if not tickers:
            return {}
        
        try:
            from datetime import datetime, timedelta
            
            logger.info(f"📥 Bulk downloading {weeks} weeks of data for {len(tickers)} stocks...")
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(weeks=weeks)
            
            # Add correct suffix (.NS for NSE, .BO for BSE)
            ticker_list = []
            ticker_to_suffix = {}
            for t in tickers:
                # BSE codes: 6 digits starting with 5
                if t.isdigit() and len(t) == 6 and t.startswith('5'):
                    ticker_with_suffix = f"{t}.BO"
                    ticker_to_suffix[t] = '.BO'
                else:
                    ticker_with_suffix = f"{t}.NS"
                    ticker_to_suffix[t] = '.NS'
                ticker_list.append(ticker_with_suffix)
            
            # Bulk download with weekly interval
            data = yf.download(
                ticker_list,
                start=start_date,
                end=end_date,
                interval='1wk',
                progress=False,
                threads=True
            )
            
            results = {}
            
            # Parse results
            if len(tickers) == 1:
                # Single ticker
                if not data.empty:
                    results[tickers[0]] = data[['Close']].copy()
                    results[tickers[0]].columns = ['price']
            else:
                # Multiple tickers
                for ticker in tickers:
                    suffix = ticker_to_suffix[ticker]
                    ticker_with_suffix = f"{ticker}{suffix}"
                    try:
                        if ticker_with_suffix in data['Close'].columns:
                            ticker_data = data['Close'][ticker_with_suffix].dropna()
                            results[ticker] = pd.DataFrame({'price': ticker_data})
                    except:
                        continue
            
            logger.info(f"✅ Weekly bulk download complete: {len(results)} tickers")
            return results
            
        except Exception as e:
            logger.error(f"❌ Weekly bulk download failed: {e}")
            return {}
    
    def get_all_prices_optimized(
        self,
        mf_tickers: List[str],
        stock_tickers: List[str],
        pms_tickers: List[str],
        ticker_names: Dict[str, str]
    ) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, any]]:
        """
        Optimized fetch: Official sources first, AI as fallback
        
        Returns:
            (mf_prices, stock_prices, pms_data)
        """
        logger.info("🚀 Starting optimized bulk price fetch...")
        
        # 1. MF: Try mftool (FREE) first, then AI fallback
        mf_prices = {}
        if mf_tickers:
            logger.info(f"📊 Fetching NAV for {len(mf_tickers)} MF using mftool (FREE)...")
            
            # Try mftool for all MF tickers
            try:
                from mf_price_fetcher import MFPriceFetcher
                mf_fetcher = MFPriceFetcher()
                
                for code in mf_tickers:
                    try:
                        # Remove 'MF_' prefix if exists
                        clean_code = code.replace('MF_', '')
                        
                        # Convert to integer (mftool expects int, not string)
                        try:
                            scheme_code_int = int(clean_code)
                        except ValueError:
                            logger.warning(f"   ⚠️ {code} is not a valid scheme code (not a number)")
                            continue
                        
                        logger.debug(f"   🔍 Trying mftool for {code} (scheme_code: {scheme_code_int})...")
                        
                        # Try getting current NAV
                        nav_result = mf_fetcher.get_mutual_fund_nav(scheme_code_int)
                        
                        logger.debug(f"   📥 mftool response for {code}: {nav_result}")
                        
                        nav = nav_result.get('nav') if nav_result and isinstance(nav_result, dict) else None
                        
                        if nav and nav > 0:
                            mf_prices[code] = nav
                            logger.info(f"✅ mftool (FREE): {code} = ₹{nav}")
                        else:
                            logger.warning(f"   ⚠️ mftool returned invalid NAV for {code}: {nav}")
                    except Exception as e:
                        logger.warning(f"   ⚠️ mftool exception for {code}: {e}")
                        continue
                
                logger.info(f"✅ mftool (FREE): {len(mf_prices)}/{len(mf_tickers)} MF prices fetched")
            except Exception as e:
                logger.warning(f"⚠️ mftool import/init failed: {e}")
            
            # Use AI for failed tickers
            failed_codes = [code for code in mf_tickers if code not in mf_prices]
            if failed_codes:
                logger.info(f"🤖 Using AI fallback for {len(failed_codes)} MF codes...")
                ai_prices = self.get_bulk_mf_nav_isin(failed_codes, ticker_names)
                mf_prices.update(ai_prices)
                
                # If still failed, try by name
                still_failed = [code for code in failed_codes if code not in mf_prices]
                if still_failed:
                    logger.info(f"🤖 Retrying {len(still_failed)} codes using fund names...")
                    name_based_prices = self.get_bulk_mf_nav_by_name(still_failed, ticker_names)
                    mf_prices.update(name_based_prices)
        
        # 2. Stocks: Use yfinance bulk (FREE, fast) → AI fallback
        stock_prices = {}
        if stock_tickers:
            stock_prices = self.get_stocks_bulk(stock_tickers)
            
            # AI fallback for stocks that failed yfinance
            failed_stocks = [ticker for ticker in stock_tickers if ticker not in stock_prices]
            if failed_stocks:
                logger.info(f"🤖 Using AI fallback for {len(failed_stocks)} stocks (yfinance failed)...")
                try:
                    ai_stock_prices = self.get_bulk_prices_with_ai(
                        failed_stocks,
                        ticker_names,
                        ticker_type='Stock'
                    )
                    # Extract just prices from AI response (it returns CAGR data for PMS, but prices for stocks)
                    for ticker, data in ai_stock_prices.items():
                        if isinstance(data, dict) and 'price' in data:
                            stock_prices[ticker] = data['price']
                        elif isinstance(data, (int, float)):
                            stock_prices[ticker] = float(data)
                    logger.info(f"✅ AI recovered {len(ai_stock_prices)}/{len(failed_stocks)} stock prices")
                except Exception as e:
                    logger.warning(f"⚠️ AI fallback for stocks failed: {e}")
        
        # 3. PMS: Use AI bulk (paid but efficient)
        pms_data = {}
        if pms_tickers:
            pms_data = self.get_bulk_prices_with_ai(
                pms_tickers,
                ticker_names,
                ticker_type='PMS'
            )
        
        logger.info(f"✅ Bulk fetch complete:")
        logger.info(f"   - MF: {len(mf_prices)}/{len(mf_tickers) if mf_tickers else 0} (mftool→AI)")
        logger.info(f"   - Stocks: {len(stock_prices)}/{len(stock_tickers) if stock_tickers else 0} (yfinance→AI)")
        logger.info(f"   - PMS/AIF: {len(pms_data)}/{len(pms_tickers) if pms_tickers else 0} (AI)")
        
        return mf_prices, stock_prices, pms_data


# Convenience functions
def get_bulk_prices(tickers: List[str], ticker_info: Dict[str, dict]) -> Dict[str, float]:
    """
    Main entry point for bulk price fetching
    
    Args:
        tickers: List of all tickers
        ticker_info: Dict with ticker details (name, type)
    
    Returns:
        Dict of ticker -> price
    """
    fetcher = BulkPriceFetcher()
    
    # Categorize tickers
    mf_tickers = []
    stock_tickers = []
    pms_tickers = []
    ticker_names = {}
    
    for ticker in tickers:
        info = ticker_info.get(ticker, {})
        name = info.get('name', ticker)
        ticker_type = info.get('type', 'STOCK')
        
        ticker_names[ticker] = name
        
        if ticker_type == 'MF':
            mf_tickers.append(ticker)
        elif ticker_type in ['PMS', 'AIF']:
            pms_tickers.append(ticker)
        else:
            stock_tickers.append(ticker)
    
    # Fetch all prices
    mf_prices, stock_prices, pms_data = fetcher.get_all_prices_optimized(
        mf_tickers,
        stock_tickers,
        pms_tickers,
        ticker_names
    )
    
    # Combine results
    all_prices = {}
    all_prices.update(mf_prices)
    all_prices.update(stock_prices)
    # PMS data needs special handling (has CAGR, not direct price)
    
    return all_prices


def get_historical_prices_with_ai(
    tickers: List[str],
    dates: List[str],
    ticker_names: Dict[str, str],
    ticker_types: Dict[str, str]
) -> Dict[str, Dict[str, float]]:
    """
    Fetch historical prices using AI for MF/Stocks when other sources fail
    
    Args:
        tickers: List of tickers
        dates: List of dates (YYYY-MM-DD format)
        ticker_names: Dict of {ticker: name}
        ticker_types: Dict of {ticker: type} where type is 'MF', 'Stock', 'PMS', 'AIF'
    
    Returns:
        Dict of {ticker: {date: price}}
    """
    try:
        from ai_price_fetcher import AIPriceFetcher
        
        ai = AIPriceFetcher()
        if not ai.is_available():
            logger.warning("AI not available for historical price fetch")
            return {}
        
        results = {}
        
        # Group by asset type for better prompts
        for ticker in tickers:
            ticker_type = ticker_types.get(ticker, 'Stock')
            name = ticker_names.get(ticker, ticker)
            results[ticker] = {}
            
            for date in dates:
                try:
                    if ticker_type == 'MF':
                        result = ai.get_mutual_fund_nav(ticker, name, date, allow_closest=True)
                    else:  # Stock
                        result = ai.get_stock_price(ticker, name, date, allow_closest=True)
                    
                    # Handle new dict format: {'date': 'YYYY-MM-DD', 'price': float, 'sector': str}
                    if result:
                        if isinstance(result, dict):
                            price = result.get('price')
                            actual_date = result.get('date', date)
                            sector = result.get('sector', 'Unknown')
                        else:
                            # Fallback for old format (just float)
                            price = result
                            actual_date = date
                            sector = 'Unknown'
                        
                        if price and price > 0:
                            results[ticker][date] = price
                            logger.info(f"✅ AI historical: {ticker} @ {actual_date} = ₹{price} ({sector})")
                except Exception as e:
                    logger.error(f"❌ AI historical failed for {ticker} @ {date}: {e}")
        
        return results
        
    except Exception as e:
        logger.error(f"❌ AI historical fetch error: {e}")
        return {}


if __name__ == "__main__":
    # Test the bulk fetcher
    print("Testing Bulk Price Fetcher...\n")
    
    fetcher = BulkPriceFetcher()
    
    # Test 1: MF bulk
    print("1. Testing MF Bulk Fetch (AMFI):")
    mf_tickers = ['102949', '25872', '120140', '104781']
    mf_navs = fetcher.get_mf_navs_for_tickers(mf_tickers)
    print(f"Result: {mf_navs}\n")
    
    # Test 2: Stock bulk
    print("2. Testing Stock Bulk Fetch (yfinance):")
    stock_tickers = ['TCS', 'INFY', 'HDFCBANK']
    stock_prices = fetcher.get_stocks_bulk(stock_tickers)
    print(f"Result: {stock_prices}\n")
    
    print("✅ Bulk fetcher working!")

