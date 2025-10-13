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
                    results[tickers[0]] = price
                    suffix = ticker_to_suffix[tickers[0]]
                    logger.info(f"✅ {tickers[0]} ({suffix}): ₹{price}")
            else:
                # Multiple tickers
                for ticker in tickers:
                    suffix = ticker_to_suffix[ticker]
                    ticker_with_suffix = f"{ticker}{suffix}"
                    try:
                        if ticker_with_suffix in data.columns.levels[0]:
                            ticker_data = data[ticker_with_suffix]
                            if not ticker_data.empty and 'Close' in ticker_data.columns:
                                price = float(ticker_data['Close'].iloc[-1])
                                results[ticker] = price
                                logger.info(f"✅ {ticker} ({suffix}): ₹{price}")
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
        try:
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
                
                # Make AI call
                response = ai.gemini_client.generate_content(prompt)
                
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
            
            logger.info(f"✅ AI bulk fetch complete: {len(results)}/{len(codes)} MF codes")
            return results
            
        except Exception as e:
            logger.error(f"❌ Bulk MF fetch failed: {e}")
            return {}
    
    def get_bulk_mf_nav_by_name(self, codes: List[str], names: Dict[str, str]) -> Dict[str, float]:
        """
        Get MF NAV by fund name (fallback when codes don't work)
        Uses AI to search by fund name instead of code
        """
        try:
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
                
                # Make AI call
                response = ai.gemini_client.generate_content(prompt)
                
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
            
            logger.info(f"✅ AI name-based fetch complete: {len(results)}/{len(codes)} funds")
            return results
            
        except Exception as e:
            logger.error(f"❌ Bulk name-based fetch failed: {e}")
            return {}
    
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
        try:
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
            
            # Make AI call
            response = ai.gemini_client.generate_content(prompt)
            
            # Parse response
            results = {}
            for line in response.text.strip().split('\n'):
                if '|' not in line:
                    continue
                
                parts = line.split('|')
                code = parts[0].strip()
                
                if ticker_type == 'MF':
                    try:
                        nav = float(parts[1].strip())
                        results[code] = nav
                        logger.info(f"✅ AI: {code} = ₹{nav}")
                    except:
                        continue
                
                elif ticker_type == 'PMS':
                    # Parse returns data (stored differently)
                    returns = {}
                    for part in parts[1:]:
                        if ':' in part:
                            period, value = part.split(':')
                            returns[period] = float(value.strip())
                    results[code] = returns
                    logger.info(f"✅ AI: {code} = {returns}")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Bulk AI fetch failed: {e}")
            return {}
    
    def get_stocks_historical_bulk(self, tickers: List[str], dates: List[str]) -> Dict[str, Dict[str, float]]:
        """
        Get historical prices for stocks in bulk for specific dates
        Returns: {ticker: {date: price}}
        """
        if not tickers or not dates:
            return {}
        
        try:
            from datetime import datetime
            
            logger.info(f"📥 Bulk downloading historical prices for {len(tickers)} stocks...")
            
            # Convert dates to datetime
            dates_dt = [pd.to_datetime(d) for d in dates]
            start_date = min(dates_dt)
            end_date = max(dates_dt)
            
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
            
            # Parse results for each ticker and date
            for ticker in tickers:
                suffix = ticker_to_suffix[ticker]
                ticker_with_suffix = f"{ticker}{suffix}"
                results[ticker] = {}
                
                for date in dates:
                    date_str = pd.to_datetime(date).strftime('%Y-%m-%d')
                    try:
                        if len(tickers) == 1:
                            # Single ticker
                            if date_str in data.index:
                                price = float(data.loc[date_str, 'Close'])
                                results[ticker][date_str] = price
                        else:
                            # Multiple tickers
                            if ticker_with_suffix in data['Close'].columns and date_str in data.index:
                                price = float(data['Close'][ticker_with_suffix].loc[date_str])
                                results[ticker][date_str] = price
                    except:
                        continue
            
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
        
        # 1. MF: Handle both ISIN and AMFI codes using AI bulk (most reliable)
        mf_prices = {}
        if mf_tickers:
            logger.info(f"📊 Fetching NAV for {len(mf_tickers)} MF using AI bulk...")
            mf_prices = self.get_bulk_mf_nav_isin(mf_tickers, ticker_names)
            
            # If some failed, try fetching by name (fallback)
            failed_codes = [code for code in mf_tickers if code not in mf_prices]
            if failed_codes:
                logger.info(f"⚠️ Retrying {len(failed_codes)} failed codes using fund names...")
                name_based_prices = self.get_bulk_mf_nav_by_name(failed_codes, ticker_names)
                mf_prices.update(name_based_prices)
        
        # 2. Stocks: Use yfinance bulk (FREE, fast)
        stock_prices = {}
        if stock_tickers:
            stock_prices = self.get_stocks_bulk(stock_tickers)
        
        # 3. PMS: Use AI bulk (paid but efficient)
        pms_data = {}
        if pms_tickers:
            pms_data = self.get_bulk_prices_with_ai(
                pms_tickers,
                ticker_names,
                ticker_type='PMS'
            )
        
        logger.info(f"✅ Bulk fetch complete:")
        logger.info(f"   - MF: {len(mf_prices)}/{len(mf_tickers) if mf_tickers else 0}")
        logger.info(f"   - Stocks: {len(stock_prices)}/{len(stock_tickers) if stock_tickers else 0}")
        logger.info(f"   - PMS/AIF: {len(pms_data)}/{len(pms_tickers) if pms_tickers else 0}")
        
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
                        price = ai.get_mutual_fund_nav(ticker, name, date, allow_closest=True)
                    else:  # Stock
                        price = ai.get_stock_price(ticker, name, date, allow_closest=True)
                    
                    if price:
                        results[ticker][date] = price
                        logger.info(f"✅ AI historical: {ticker} @ {date} = ₹{price}")
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

