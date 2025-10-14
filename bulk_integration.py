#!/usr/bin/env python3
"""
Bulk Price Integration Module
Provides optimized bulk price fetching for web_agent.py
"""

import pandas as pd
import logging
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
from bulk_price_fetcher import BulkPriceFetcher
from pms_aif_fetcher import is_pms_code, is_aif_code
from database_config_supabase import (
    bulk_save_historical_prices,
    bulk_update_stock_data,
    save_stock_price_supabase
)

# Weekly prices use the same storage as regular prices
def save_weekly_stock_prices_supabase(ticker: str, week_start: str, price: float):
    """Save weekly price (uses same storage as historical prices)"""
    return save_stock_price_supabase(ticker, week_start, price, price_source='weekly')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def categorize_tickers(df: pd.DataFrame) -> Tuple[List[str], List[str], List[str], Dict[str, str]]:
    """
    Categorize tickers into MF (ISIN), Stocks, and PMS/AIF
    
    Returns:
        (mf_isins, stock_tickers, pms_tickers, ticker_names)
    """
    mf_isins = []
    stock_tickers = []
    pms_tickers = []
    ticker_names = {}
    
    logger.info(f"📋 Categorizing {len(df)} tickers from DataFrame...")
    logger.info(f"📋 DataFrame columns: {list(df.columns)}")
    logger.info(f"📋 Sample tickers: {df['ticker'].head(10).tolist() if 'ticker' in df.columns else 'No ticker column!'}")
    
    for _, row in df.iterrows():
        ticker = str(row['ticker']).strip()
        name = row.get('stock_name', ticker)
        ticker_names[ticker] = name
        
        # Check PMS/AIF FIRST (before ISIN, as PMS codes also start with 'IN')
        if is_pms_code(ticker) or is_aif_code(ticker):
            pms_tickers.append(ticker)
        # Check if ISIN (starts with IN and has correct format, typically 12 chars)
        elif ticker.startswith('IN') and len(ticker) == 12:
            mf_isins.append(ticker)
        # Check if MF AMFI code (5-6 digit number, exclude BSE codes starting with 5)
        elif ticker.isdigit() and len(ticker) in [5, 6]:
            # BSE codes start with 5 and are 6 digits
            if len(ticker) == 6 and ticker.startswith('5'):
                stock_tickers.append(ticker)
            else:
                # AMFI codes are 5-6 digits but don't start with 5 (or if 5 digits, it's MF)
                mf_isins.append(ticker)
        # Everything else is stock
        else:
            stock_tickers.append(ticker)
    
    # Remove duplicates
    mf_isins = list(set(mf_isins))
    stock_tickers = list(set(stock_tickers))
    pms_tickers = list(set(pms_tickers))
    
    logger.info(f"📊 Categorized tickers:")
    logger.info(f"   - MF (ISIN): {len(mf_isins)}")
    logger.info(f"   - Stocks: {len(stock_tickers)}")
    logger.info(f"   - PMS/AIF: {len(pms_tickers)}")
    
    return mf_isins, stock_tickers, pms_tickers, ticker_names


def fetch_historical_prices_bulk(
    df: pd.DataFrame,
    user_id: int,
    progress_callback=None
) -> Dict[str, Dict[str, float]]:
    """
    Fetch historical prices for all tickers in bulk (for transaction dates)
    
    Args:
        df: DataFrame with transactions
        user_id: User ID
        progress_callback: Optional callback for progress updates
    
    Returns:
        Dict of {ticker: {date: price}}
    """
    logger.info("🚀 Starting bulk historical price fetch...")
    
    # Categorize tickers
    mf_isins, stock_tickers, pms_tickers, ticker_names = categorize_tickers(df)
    
    fetcher = BulkPriceFetcher()
    all_prices = {}
    
    # Get unique transaction dates
    unique_dates = df['date'].unique().tolist()
    
    # 1. Stocks: Bulk download from yfinance (with AI fallback for failures)
    if stock_tickers:
        if progress_callback:
            progress_callback(f"📥 Fetching historical prices for {len(stock_tickers)} stocks...")
        
        stock_hist = fetcher.get_stocks_historical_bulk(stock_tickers, unique_dates)
        all_prices.update(stock_hist)
        logger.info(f"✅ Stocks: {len(stock_hist)}/{len(stock_tickers)} fetched via yfinance")
        
        # Check for failed tickers (no data or partial data with NaN)
        failed_ticker_dates = {}  # {ticker: [missing_dates]}
        
        for ticker in stock_tickers:
            # Get expected dates for this ticker
            ticker_trans = df[df['ticker'] == ticker]
            expected_dates = [pd.to_datetime(d).strftime('%Y-%m-%d') for d in ticker_trans['date'].unique()]
            
            # Check what's missing
            if ticker not in stock_hist or not stock_hist[ticker]:
                # Completely failed - all dates missing
                failed_ticker_dates[ticker] = expected_dates
                logger.debug(f"   ❌ {ticker}: ALL dates failed (0/{len(expected_dates)})")
            else:
                # Partial data - check for missing dates (NaN values)
                missing_dates = [d for d in expected_dates if d not in stock_hist[ticker]]
                if missing_dates:
                    failed_ticker_dates[ticker] = missing_dates
                    logger.debug(f"   ⚠️ {ticker}: {len(missing_dates)}/{len(expected_dates)} dates have NaN")
                else:
                    logger.debug(f"   ✅ {ticker}: All {len(expected_dates)} dates have valid prices")
        
        # Use AI for failed/partial tickers
        if failed_ticker_dates:
            total_missing = sum(len(dates) for dates in failed_ticker_dates.values())
            logger.info(f"⚠️ {len(failed_ticker_dates)} stocks have {total_missing} missing prices (NaN), trying AI fallback...")
            if progress_callback:
                progress_callback(f"🤖 Using AI fallback for {total_missing} missing prices...")
            
            try:
                from bulk_price_fetcher import get_historical_prices_with_ai
                
                # Build ticker types dict and dates
                ticker_types = {t: 'Stock' for t in failed_ticker_dates.keys()}
                all_missing_dates = sorted(set([d for dates in failed_ticker_dates.values() for d in dates]))
                
                ai_results = get_historical_prices_with_ai(
                    list(failed_ticker_dates.keys()),
                    all_missing_dates,
                    ticker_names,
                    ticker_types
                )
                
                # Merge AI results (only for missing dates)
                for ticker, dates_dict in ai_results.items():
                    if ticker not in all_prices:
                        all_prices[ticker] = {}
                    all_prices[ticker].update(dates_dict)
                
                logger.info(f"✅ AI fallback: Recovered {sum(len(d) for d in ai_results.values())} prices")
            except Exception as e:
                logger.warning(f"⚠️ AI fallback failed: {e}")
    
    # 2. MF (ISIN): Use transaction price (fastest, most accurate)
    if mf_isins:
        if progress_callback:
            progress_callback(f"📊 Using transaction prices for {len(mf_isins)} MF...")
        
        for isin in mf_isins:
            isin_trans = df[df['ticker'] == isin]
            all_prices[isin] = {}
            
            for _, row in isin_trans.iterrows():
                date_str = pd.to_datetime(row['date']).strftime('%Y-%m-%d')
                all_prices[isin][date_str] = float(row['price'])
        
        logger.info(f"✅ MF (ISIN): {len(mf_isins)} using transaction prices")
    
    # 3. PMS/AIF: Use transaction price (no historical prices exist)
    if pms_tickers:
        if progress_callback:
            progress_callback(f"💼 Using transaction prices for {len(pms_tickers)} PMS/AIF...")
        
        for ticker in pms_tickers:
            ticker_trans = df[df['ticker'] == ticker]
            all_prices[ticker] = {}
            
            for _, row in ticker_trans.iterrows():
                date_str = pd.to_datetime(row['date']).strftime('%Y-%m-%d')
                all_prices[ticker][date_str] = float(row['price'])
        
        logger.info(f"✅ PMS/AIF: {len(pms_tickers)} using transaction prices")
    
    # Save to database in bulk
    if progress_callback:
        progress_callback(f"💾 Saving {len(all_prices)} historical prices to database...")
    
    save_count = 0
    skip_count = 0
    price_data_list = []
    
    import math
    
    for ticker, dates_dict in all_prices.items():
        for date_str, price in dates_dict.items():
            # ✅ VALIDATE: Skip NaN, inf, and invalid prices
            if not isinstance(price, (int, float)) or math.isnan(price) or math.isinf(price) or price <= 0:
                logger.debug(f"⚠️ Skipping invalid price for {ticker} on {date_str}: {price}")
                skip_count += 1
                continue
            
            price_data_list.append({
                'ticker': ticker,
                'date': date_str,
                'price': float(price),  # Ensure it's a standard float
                'source': 'bulk_historical'  # Add source field for database storage
            })
            save_count += 1
    
    if price_data_list:
        bulk_save_historical_prices(price_data_list)
    
    if skip_count > 0:
        logger.warning(f"⚠️ Skipped {skip_count} invalid prices (NaN/inf)")
    logger.info(f"✅ Historical prices saved: {save_count} records")
    
    return all_prices


def fetch_weekly_prices_bulk(
    df: pd.DataFrame,
    user_id: int,
    weeks: int = 26,
    progress_callback=None
) -> Dict[str, pd.DataFrame]:
    """
    Fetch weekly prices for all tickers in bulk (for charts)
    
    Args:
        df: DataFrame with transactions
        user_id: User ID
        weeks: Number of weeks to fetch (default: 26 = 6 months)
        progress_callback: Optional callback for progress updates
    
    Returns:
        Dict of {ticker: DataFrame with weekly prices}
    """
    logger.info(f"🚀 Starting bulk weekly price fetch ({weeks} weeks)...")
    
    # Categorize tickers
    mf_isins, stock_tickers, pms_tickers, ticker_names = categorize_tickers(df)
    
    fetcher = BulkPriceFetcher()
    all_weekly = {}
    
    # 1. Stocks: Bulk download weekly data
    if stock_tickers:
        if progress_callback:
            progress_callback(f"📈 Fetching weekly data for {len(stock_tickers)} stocks...")
        
        stock_weekly = fetcher.get_stocks_weekly_bulk(stock_tickers, weeks)
        all_weekly.update(stock_weekly)
        logger.info(f"✅ Stocks weekly: {len(stock_weekly)} fetched")
    
    # 2. MF (ISIN): Use AI bulk to get current NAV, then extrapolate backwards
    if mf_isins:
        if progress_callback:
            progress_callback(f"🤖 Fetching NAV for {len(mf_isins)} MF using AI...")
        
        # Get current NAV using AI bulk (with name-based fallback)
        current_navs = fetcher.get_bulk_mf_nav_isin(mf_isins, ticker_names)
        
        # If some failed, try fetching by name
        failed_codes = [code for code in mf_isins if code not in current_navs]
        if failed_codes:
            logger.info(f"⚠️ Retrying {len(failed_codes)} failed codes using fund names...")
            name_based_navs = fetcher.get_bulk_mf_nav_by_name(failed_codes, ticker_names)
            current_navs.update(name_based_navs)
        
        # For each MF, create weekly data
        for isin in mf_isins:
            if isin in current_navs:
                # Create weekly data (simplified: use transaction price as baseline)
                isin_trans = df[df['ticker'] == isin].iloc[0]
                trans_price = float(isin_trans['price'])
                current_nav = current_navs[isin]
                
                # Calculate weekly progression
                weeks_list = []
                end_date = datetime.now()
                
                for i in range(weeks):
                    week_date = end_date - timedelta(weeks=i)
                    # Linear interpolation between transaction price and current NAV
                    progress = i / weeks
                    weekly_price = trans_price + (current_nav - trans_price) * progress
                    weeks_list.append({
                        'date': week_date,
                        'price': weekly_price
                    })
                
                all_weekly[isin] = pd.DataFrame(weeks_list).set_index('date')
        
        logger.info(f"✅ MF weekly: {len(current_navs)} calculated")
    
    # 3. PMS/AIF: Get CAGR using AI bulk, then calculate weekly values
    if pms_tickers:
        if progress_callback:
            progress_callback(f"💼 Fetching CAGR for {len(pms_tickers)} PMS/AIF using AI...")
        
        # Get CAGR data using AI bulk
        pms_data = fetcher.get_bulk_prices_with_ai(pms_tickers, ticker_names, ticker_type='PMS')
        
        # Calculate weekly values from CAGR
        for ticker in pms_tickers:
            if ticker in pms_data:
                cagr_data = pms_data[ticker]
                
                # Get investment details
                ticker_trans = df[df['ticker'] == ticker]
                first_trans = ticker_trans.iloc[0]
                investment_date = pd.to_datetime(first_trans['date'])
                investment_amount = float(ticker_trans['quantity'].sum() * first_trans['price'])
                
                # Use appropriate CAGR
                years_elapsed = (datetime.now() - investment_date).days / 365.25
                
                if years_elapsed >= 5 and '5Y' in cagr_data:
                    cagr = cagr_data['5Y'] / 100
                elif years_elapsed >= 3 and '3Y' in cagr_data:
                    cagr = cagr_data['3Y'] / 100
                elif '1Y' in cagr_data:
                    cagr = cagr_data['1Y'] / 100
                else:
                    continue
                
                # Calculate weekly values
                weeks_list = []
                end_date = datetime.now()
                
                for i in range(weeks):
                    week_date = end_date - timedelta(weeks=i)
                    weeks_from_investment = (week_date - investment_date).days / 7
                    years_at_week = weeks_from_investment / 52
                    
                    weekly_value = investment_amount * ((1 + cagr) ** years_at_week)
                    weeks_list.append({
                        'date': week_date,
                        'price': weekly_value
                    })
                
                all_weekly[ticker] = pd.DataFrame(weeks_list).set_index('date')
        
        logger.info(f"✅ PMS/AIF weekly: {len(pms_data)} calculated")
    
    # Save to database in bulk
    if progress_callback:
        progress_callback(f"💾 Saving weekly prices to database...")
    
    save_count = 0
    for ticker, weekly_df in all_weekly.items():
        for date, row in weekly_df.iterrows():
            try:
                save_weekly_stock_prices_supabase(
                    ticker=ticker,
                    week_start=date.strftime('%Y-%m-%d'),
                    price=float(row['price'])
                )
                save_count += 1
            except Exception as e:
                logger.warning(f"Failed to save weekly price for {ticker}: {e}")
                continue
    
    logger.info(f"✅ Weekly prices saved: {save_count} records")
    
    return all_weekly


def fetch_live_prices_bulk(
    df: pd.DataFrame,
    user_id: int,
    progress_callback=None
) -> Dict[str, Tuple[float, str]]:
    """
    Fetch live prices for all tickers in bulk
    
    Args:
        df: DataFrame with transactions (or tickers list)
        user_id: User ID
        progress_callback: Optional callback for progress updates
    
    Returns:
        Dict of {ticker: (price, sector)}
    """
    logger.info("🚀 Starting bulk live price fetch...")
    print("\n" + "=" * 80)
    print("🚀 BULK INTEGRATION - fetch_live_prices_bulk()")
    print("=" * 80)
    
    # Categorize tickers
    mf_isins, stock_tickers, pms_tickers, ticker_names = categorize_tickers(df)
    
    print(f"📊 Categorization Results:")
    print(f"   MF/ISIN codes: {len(mf_isins)} → {mf_isins[:5]}{'...' if len(mf_isins) > 5 else ''}")
    print(f"   Stock tickers: {len(stock_tickers)} → {stock_tickers[:5]}{'...' if len(stock_tickers) > 5 else ''}")
    print(f"   PMS/AIF codes: {len(pms_tickers)} → {pms_tickers[:5]}{'...' if len(pms_tickers) > 5 else ''}")
    
    fetcher = BulkPriceFetcher()
    
    # Check AI availability
    print(f"\n🤖 AI Availability Check:")
    try:
        from ai_price_fetcher import AIPriceFetcher
        ai = AIPriceFetcher()
        if ai.is_available():
            if ai.gemini_client:
                print("   ✅ Gemini AI is active")
            elif ai.openai_client:
                print("   ✅ OpenAI is active")
        else:
            print("   ❌ AI is NOT available!")
    except Exception as e:
        print(f"   ❌ AI check failed: {e}")
    
    # Fetch all prices using optimized bulk methods
    if progress_callback:
        progress_callback(f"💰 Fetching live prices for {len(mf_isins) + len(stock_tickers) + len(pms_tickers)} tickers...")
    
    print(f"\n🔄 Calling BulkPriceFetcher.get_all_prices_optimized()...")
    mf_prices, stock_prices, pms_data = fetcher.get_all_prices_optimized(
        mf_isins,
        stock_tickers,
        pms_tickers,
        ticker_names
    )
    
    print(f"\n✅ Fetching complete:")
    print(f"   MF prices: {len(mf_prices)}/{len(mf_isins)}")
    print(f"   Stock prices: {len(stock_prices)}/{len(stock_tickers)}")
    print(f"   PMS/AIF data: {len(pms_data)}/{len(pms_tickers)}")
    
    # Combine results with sectors
    all_prices = {}
    
    # Stocks
    for ticker, price in stock_prices.items():
        all_prices[ticker] = (price, "Equity")  # Sector will be updated later
    
    # MF
    for ticker, price in mf_prices.items():
        all_prices[ticker] = (price, "Mutual Fund")
    
    # PMS/AIF - calculate current value from CAGR
    # Check if we have transaction data (date, price, quantity columns)
    has_trans_data = all(col in df.columns for col in ['date', 'price', 'quantity'])
    
    for ticker, cagr_data in pms_data.items():
        if has_trans_data:
            # Get investment details from transaction data
            ticker_trans = df[df['ticker'] == ticker]
            if ticker_trans.empty:
                continue
            
            first_trans = ticker_trans.iloc[0]
            investment_date = pd.to_datetime(first_trans['date'])
            investment_amount = float(ticker_trans['quantity'].sum() * first_trans['price'])
            
            # Calculate current value
            years_elapsed = (datetime.now() - investment_date).days / 365.25
            
            current_value = investment_amount
            if years_elapsed >= 5 and '5Y' in cagr_data:
                cagr = cagr_data['5Y'] / 100
                current_value = investment_amount * ((1 + cagr) ** years_elapsed)
            elif years_elapsed >= 3 and '3Y' in cagr_data:
                cagr = cagr_data['3Y'] / 100
                current_value = investment_amount * ((1 + cagr) ** years_elapsed)
            elif '1Y' in cagr_data:
                annual_return = cagr_data['1Y'] / 100
                current_value = investment_amount * ((1 + annual_return) ** years_elapsed)
            
            sector = "Alternative Investments" if is_aif_code(ticker) else "PMS Equity"
            all_prices[ticker] = (current_value, sector)
        else:
            # No transaction data available - use CAGR info as a placeholder
            # This happens during login when only tickers are passed
            # The actual value will be calculated when displaying portfolio
            sector = "Alternative Investments" if is_aif_code(ticker) else "PMS Equity"
            # Store CAGR data as the "price" temporarily (will be handled by portfolio display)
            cagr_value = cagr_data.get('3Y', cagr_data.get('1Y', 0))
            all_prices[ticker] = (cagr_value, sector)
    
    # Bulk update database
    if progress_callback:
        progress_callback(f"💾 Saving {len(all_prices)} live prices to database...")
    
    update_list = []
    for ticker, (price, sector) in all_prices.items():
        name = ticker_names.get(ticker, ticker)
        update_list.append({
            'ticker': ticker,
            'stock_name': name,
            'sector': sector,
            'live_price': price
        })
    
    if update_list:
        bulk_update_stock_data(update_list)
    
    logger.info(f"✅ Live prices updated: {len(all_prices)} tickers")
    
    return all_prices


# Export functions
__all__ = [
    'categorize_tickers',
    'fetch_historical_prices_bulk',
    'fetch_weekly_prices_bulk',
    'fetch_live_prices_bulk'
]

