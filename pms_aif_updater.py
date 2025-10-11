#!/usr/bin/env python3
"""
PMS/AIF Value Updater
Fetches CAGR from official factsheets and updates database
Can be called independently for file uploads or scheduled updates
"""

import pandas as pd
import requests
import PyPDF2
import io
import re
from datetime import datetime
from typing import List, Dict, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Factsheet URLs for known PMS/AIF
FACTSHEET_URLS = {
    'INP000005000': 'https://www.buoyantcap.com/wp-content/uploads/2025/09/PMS-flyer-Sep-25.pdf',
    'INP000006387': 'https://www.carneliancapital.co.in/_files/ugd/3ea37e_226f032b021f40c992d0511e2782f5ae.pdf',
    'INP000000613': 'https://www.unificap.com/sites/default/files/track_record/pdf/Unifi-Capital-Presentation-September-2025.pdf',
    'INP000005125': 'https://www.valentisadvisors.com/wp-content/uploads/2025/06/Valentis-PMS-Presentation-May-2025.pdf',
}

def extract_cagr_from_pdf(pdf_url: str) -> Dict[str, float]:
    """
    Download PDF and extract CAGR/return percentages using regex
    
    Args:
        pdf_url: URL to PMS/AIF factsheet PDF
        
    Returns:
        Dict with extracted returns (1y_return, 3y_cagr, 5y_cagr, etc.)
    """
    try:
        # Download PDF
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        response = session.get(pdf_url, timeout=30)
        if response.status_code != 200:
            logger.warning(f"Failed to download PDF from {pdf_url}: HTTP {response.status_code}")
            return {}
        
        # Extract text from PDF
        pdf_file = io.BytesIO(response.content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        
        logger.info(f"📄 Extracted {len(text)} characters from PDF")
        
        # Extract CAGR/returns using regex patterns
        returns_data = {}
        patterns = {
            '1m_return': r'1\s*[Mm](?:onth)?\s*(?:Return|CAGR)?\s*:?\s*([+-]?\d+\.?\d*)\s*%',
            '3m_return': r'3\s*[Mm](?:onth)?\s*(?:Return|CAGR)?\s*:?\s*([+-]?\d+\.?\d*)\s*%',
            '6m_return': r'6\s*[Mm](?:onth)?\s*(?:Return|CAGR)?\s*:?\s*([+-]?\d+\.?\d*)\s*%',
            '1y_return': r'1\s*[Yy](?:ear)?\s*(?:Return|CAGR)?\s*:?\s*([+-]?\d+\.?\d*)\s*%',
            '3y_cagr': r'3\s*[Yy](?:ear)?\s*(?:CAGR|Return)?\s*:?\s*([+-]?\d+\.?\d*)\s*%',
            '5y_cagr': r'5\s*[Yy](?:ear)?\s*(?:CAGR|Return)?\s*:?\s*([+-]?\d+\.?\d*)\s*%',
            'since_inception': r'(?:Since\s*Inception|SI)\s*(?:CAGR|Return)?\s*:?\s*([+-]?\d+\.?\d*)\s*%'
        }
        
        for key, pattern in patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                returns_data[key] = float(matches[0])
                logger.info(f"✅ Extracted {key}: {matches[0]}%")
        
        return returns_data
        
    except Exception as e:
        logger.error(f"Error extracting CAGR from PDF: {e}")
        return {}

def calculate_current_value(investment_amount: float, investment_date: str, returns_data: Dict) -> float:
    """
    Calculate current value based on investment date and CAGR
    
    Args:
        investment_amount: Initial investment amount
        investment_date: Investment date (YYYY-MM-DD)
        returns_data: Dict with CAGR/return data
        
    Returns:
        Current value calculated using appropriate CAGR
    """
    try:
        inv_date = pd.to_datetime(investment_date)
        years_elapsed = (datetime.now() - inv_date).days / 365.25
        
        current_value = investment_amount
        
        # Use most appropriate return based on holding period
        if years_elapsed >= 5 and '5y_cagr' in returns_data:
            cagr = returns_data['5y_cagr'] / 100
            current_value = investment_amount * ((1 + cagr) ** years_elapsed)
            logger.info(f"💰 Using 5Y CAGR: {returns_data['5y_cagr']}%")
        elif years_elapsed >= 3 and '3y_cagr' in returns_data:
            cagr = returns_data['3y_cagr'] / 100
            current_value = investment_amount * ((1 + cagr) ** years_elapsed)
            logger.info(f"💰 Using 3Y CAGR: {returns_data['3y_cagr']}%")
        elif years_elapsed >= 1 and '1y_return' in returns_data:
            annual_return = returns_data['1y_return'] / 100
            current_value = investment_amount * ((1 + annual_return) ** years_elapsed)
            logger.info(f"💰 Using 1Y Return: {returns_data['1y_return']}%")
        
        return current_value
        
    except Exception as e:
        logger.error(f"Error calculating current value: {e}")
        return investment_amount

def update_pms_aif_for_file(user_id: int, file_id: Optional[int] = None):
    """
    Update PMS/AIF values for a specific user's file upload
    Fetches factsheets and updates database
    
    Args:
        user_id: User ID
        file_id: Optional file ID (if None, updates all user's PMS/AIF)
    """
    try:
        from database_config_supabase import (
            get_transactions_supabase,
            update_stock_data_supabase,
            save_stock_price_supabase
        )
        from pms_aif_fetcher import is_pms_code, is_aif_code
        
        # Get user's transactions
        if file_id:
            transactions = get_transactions_supabase(user_id=user_id, file_id=file_id)
            logger.info(f"📊 Processing file_id {file_id} for user {user_id}")
        else:
            transactions = get_transactions_supabase(user_id=user_id)
            logger.info(f"📊 Processing all transactions for user {user_id}")
        
        if not transactions:
            logger.warning("No transactions found")
            return
        
        df = pd.DataFrame(transactions)
        
        # Identify PMS/AIF holdings
        pms_aif_tickers = []
        for ticker in df['ticker'].unique():
            ticker_str = str(ticker).strip()
            if is_pms_code(ticker_str) or is_aif_code(ticker_str):
                pms_aif_tickers.append(ticker_str)
        
        if not pms_aif_tickers:
            logger.info("No PMS/AIF holdings found in this file")
            return
        
        logger.info(f"🔄 Found {len(pms_aif_tickers)} PMS/AIF holding(s): {pms_aif_tickers}")
        
        # Process each PMS/AIF
        updated_count = 0
        for ticker in pms_aif_tickers:
            try:
                if ticker not in FACTSHEET_URLS:
                    logger.warning(f"⚠️ No factsheet URL configured for {ticker}")
                    continue
                
                url = FACTSHEET_URLS[ticker]
                logger.info(f"🔄 Processing {ticker}")
                
                # Extract CAGR from factsheet
                returns_data = extract_cagr_from_pdf(url)
                
                if not returns_data:
                    logger.warning(f"⚠️ No returns data extracted for {ticker}")
                    continue
                
                # Get investment details
                ticker_trans = df[df['ticker'] == ticker]
                if ticker_trans.empty:
                    continue
                
                first_trans = ticker_trans.iloc[0]
                investment_date = pd.to_datetime(first_trans['date'])
                total_quantity = float(ticker_trans['quantity'].sum())
                avg_price = float(ticker_trans['price'].mean())
                investment_amount = total_quantity * avg_price
                
                # Calculate current value
                current_value = calculate_current_value(
                    investment_amount,
                    investment_date.strftime('%Y-%m-%d'),
                    returns_data
                )
                
                # Determine sector
                if is_aif_code(ticker):
                    sector = "Alternative Investments"
                else:
                    sector = "PMS Equity"
                
                # Update database
                stock_name = first_trans.get('stock_name', ticker)
                update_stock_data_supabase(
                    ticker=ticker,
                    stock_name=stock_name,
                    sector=sector,
                    current_price=current_value,  # Updated parameter name
                    market_cap=None
                )
                
                # Save as historical price
                today = datetime.now().strftime('%Y-%m-%d')
                save_stock_price_supabase(ticker, current_value, today)
                
                logger.info(f"✅ Updated {ticker}: ₹{investment_amount:,.0f} → ₹{current_value:,.0f}")
                updated_count += 1
                
            except Exception as e:
                logger.error(f"⚠️ Error updating {ticker}: {e}")
                continue
        
        logger.info(f"✅ Updated {updated_count}/{len(pms_aif_tickers)} PMS/AIF value(s)")
        return updated_count
        
    except Exception as e:
        logger.error(f"❌ Error in update_pms_aif_for_file: {e}")
        raise

if __name__ == "__main__":
    # Test the updater
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python pms_aif_updater.py <user_id> [file_id]")
        sys.exit(1)
    
    user_id = int(sys.argv[1])
    file_id = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    print(f"🔄 Updating PMS/AIF values for user {user_id}" + (f", file {file_id}" if file_id else ""))
    count = update_pms_aif_for_file(user_id, file_id)
    print(f"✅ Updated {count} PMS/AIF holding(s)")

