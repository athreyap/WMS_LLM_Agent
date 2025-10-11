#!/usr/bin/env python3
"""
Download PMS/AIF factsheets and store CAGR data directly in database
"""

import requests
import re
import PyPDF2
import io
from typing import Optional, Dict, List
import pandas as pd
from datetime import datetime
from database_config_supabase import update_stock_data_supabase, save_stock_price_supabase

class FactsheetToDatabaseLoader:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # PMS/AIF factsheet URLs with metadata
        self.investments = {
            'INP000005000': {
                'name': 'Buoyant Opportunities (PMS)',
                'type': 'PMS',
                'sector': 'PMS Equity',
                'url': 'https://www.buoyantcap.com/wp-content/uploads/2025/09/PMS-flyer-Sep-25.pdf'
            },
            'INP000006387': {
                'name': 'Carnelian Capital - The Shift Strategy (PMS)',
                'type': 'PMS',
                'sector': 'PMS Equity',
                'urls': [
                    'https://www.carneliancapital.co.in/_files/ugd/3ea37e_226f032b021f40c992d0511e2782f5ae.pdf',
                    'https://www.carneliancapital.co.in/_files/ugd/3ea37e_493d1a9b40204f899bd59fb9e33b20ff.pdf'
                ]
            },
            'INP000000613': {
                'name': 'Unifi Capital Business Consolidation After Disruption (BCAD) Fund (PMS)',
                'type': 'PMS',
                'sector': 'PMS Equity',
                'url': 'https://www.unificap.com/sites/default/files/track_record/pdf/Unifi-Capital-Presentation-September-2025.pdf'
            },
            'INP000005125': {
                'name': 'Valentis Rising Stars Opportunity Fund (PMS)',
                'type': 'PMS',
                'sector': 'PMS Equity',
                'url': 'https://www.valentisadvisors.com/wp-content/uploads/2025/06/Valentis-PMS-Presentation-May-2025.pdf'
            },
            'INP000007012': {
                'name': 'Julius Baer India Premier Opportunities Portfolio (PMS)',
                'type': 'PMS',
                'sector': 'PMS Equity',
                'url': None,  # Need to find factsheet
                'note': 'Manual entry needed'
            },
            # AIF
            'AIF_IN_AIF3_20-21_0857': {
                'name': 'Nuvama Enhanced Dynamic Growth Equity Fund (Monthly) - AIF Cat III',
                'type': 'AIF',
                'sector': 'Alternative Investments',
                'url': None,  # Need to find factsheet
                'note': 'Manual entry needed - check Nuvama investor portal'
            }
        }
    
    def download_pdf(self, url: str) -> Optional[bytes]:
        """Download PDF from URL"""
        try:
            print(f"   📥 Downloading PDF...")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            print(f"   ✅ Downloaded {len(response.content):,} bytes")
            return response.content
        except Exception as e:
            print(f"   ❌ Download error: {e}")
            return None
    
    def extract_text_from_pdf(self, pdf_bytes: bytes) -> str:
        """Extract text from PDF"""
        try:
            pdf_file = io.BytesIO(pdf_bytes)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            text = ""
            for page_num, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                text += page_text + "\n"
                
                # Show preview of first page
                if page_num == 0:
                    print(f"\n   📄 First page preview:")
                    print(f"   {page_text[:300]}...")
            
            print(f"   ✅ Extracted {len(text):,} characters from {len(pdf_reader.pages)} pages")
            return text
        except Exception as e:
            print(f"   ❌ Text extraction error: {e}")
            return ""
    
    def extract_returns_from_text(self, text: str) -> Dict[str, float]:
        """
        Extract return/CAGR values from factsheet text
        
        Returns:
            Dict with keys like '1m_return', '3y_cagr', etc. mapped to float values
        """
        returns_data = {}
        
        # Comprehensive patterns for different formats
        patterns = {
            '1m_return': [
                r'1\s*M(?:onth)?.*?(?:Return|Performance).*?([+-]?\d+\.?\d*)\s*%',
                r'1\s*Month.*?([+-]?\d+\.?\d*)\s*%',
            ],
            '3m_return': [
                r'3\s*M(?:onth)?.*?(?:Return|Performance).*?([+-]?\d+\.?\d*)\s*%',
                r'3\s*Month.*?([+-]?\d+\.?\d*)\s*%',
            ],
            '6m_return': [
                r'6\s*M(?:onth)?.*?(?:Return|Performance).*?([+-]?\d+\.?\d*)\s*%',
                r'6\s*Month.*?([+-]?\d+\.?\d*)\s*%',
            ],
            '1y_return': [
                r'1\s*Y(?:ear)?.*?(?:Return|CAGR|Performance).*?([+-]?\d+\.?\d*)\s*%',
                r'1\s*Year.*?([+-]?\d+\.?\d*)\s*%',
                r'(?:^|\s)1Y\s*(?:Return|CAGR)?\s*[:\-]?\s*([+-]?\d+\.?\d*)\s*%',
            ],
            '3y_cagr': [
                r'3\s*Y(?:ear)?.*?(?:CAGR|Return|Performance).*?([+-]?\d+\.?\d*)\s*%',
                r'3\s*Year.*?CAGR.*?([+-]?\d+\.?\d*)\s*%',
                r'(?:^|\s)3Y\s*(?:CAGR|Return)?\s*[:\-]?\s*([+-]?\d+\.?\d*)\s*%',
            ],
            '5y_cagr': [
                r'5\s*Y(?:ear)?.*?(?:CAGR|Return|Performance).*?([+-]?\d+\.?\d*)\s*%',
                r'5\s*Year.*?CAGR.*?([+-]?\d+\.?\d*)\s*%',
                r'(?:^|\s)5Y\s*(?:CAGR|Return)?\s*[:\-]?\s*([+-]?\d+\.?\d*)\s*%',
            ],
            'since_inception': [
                r'Since\s*Inception.*?CAGR.*?([+-]?\d+\.?\d*)\s*%',
                r'SI.*?CAGR.*?([+-]?\d+\.?\d*)\s*%',
            ]
        }
        
        for key, pattern_list in patterns.items():
            for pattern in pattern_list:
                matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
                if matches:
                    try:
                        value = float(matches[0])
                        returns_data[key] = value
                        print(f"   ✅ {key}: {value}%")
                        break  # Found a match for this key
                    except ValueError:
                        continue
        
        return returns_data
    
    def calculate_live_price_from_cagr(self, investment_amount: float, investment_date: str, returns_data: Dict[str, float]) -> Optional[float]:
        """
        Calculate current value using CAGR
        Similar to logic in pms_aif_fetcher.py
        """
        try:
            from datetime import datetime
            from dateutil import relativedelta
            
            inv_date = datetime.strptime(investment_date, '%Y-%m-%d')
            current_date = datetime.now()
            
            years_elapsed = (current_date - inv_date).days / 365.25
            months_elapsed = (current_date - inv_date).days / 30.44
            
            current_value = investment_amount
            cagr_used = None
            
            # Use best available CAGR based on holding period
            if years_elapsed >= 5 and '5y_cagr' in returns_data:
                cagr = returns_data['5y_cagr'] / 100
                current_value = investment_amount * ((1 + cagr) ** years_elapsed)
                cagr_used = f"5Y CAGR: {returns_data['5y_cagr']}%"
                
            elif years_elapsed >= 3 and '3y_cagr' in returns_data:
                cagr = returns_data['3y_cagr'] / 100
                current_value = investment_amount * ((1 + cagr) ** years_elapsed)
                cagr_used = f"3Y CAGR: {returns_data['3y_cagr']}%"
                
            elif years_elapsed >= 1 and '1y_return' in returns_data:
                annual_return = returns_data['1y_return'] / 100
                current_value = investment_amount * ((1 + annual_return) ** years_elapsed)
                cagr_used = f"1Y Return: {returns_data['1y_return']}%"
            
            # Calculate "live price" as value per unit (assuming 1 unit = initial investment)
            live_price = current_value
            
            print(f"   💰 Calculated value: ₹{investment_amount:,.0f} → ₹{current_value:,.0f} ({cagr_used})")
            
            return live_price
            
        except Exception as e:
            print(f"   ⚠️ Price calculation error: {e}")
            return None
    
    def save_to_database(self, ticker: str, info: Dict, returns_data: Dict[str, float], investment_date: str, investment_amount: float):
        """
        Save PMS/AIF data to database
        
        Saves to:
        1. stock_data table (ticker, stock_name, sector, live_price)
        2. historical_prices table (live price with today's date)
        """
        try:
            print(f"\n   💾 Saving to database...")
            
            # Calculate live price
            live_price = self.calculate_live_price_from_cagr(investment_amount, investment_date, returns_data)
            
            if not live_price:
                print(f"   ⚠️ Could not calculate live price, skipping database save")
                return False
            
            # Save to stock_data table
            stock_data = {
                'ticker': ticker,
                'stock_name': info['name'],
                'sector': info['sector'],
                'live_price': live_price,
                'market_cap': None  # Not applicable for PMS/AIF
            }
            
            success = update_stock_data_supabase(**stock_data)
            
            if success:
                print(f"   ✅ Saved to stock_data table")
                
                # Also save as historical price for today
                today = datetime.now().strftime('%Y-%m-%d')
                save_stock_price_supabase(ticker, live_price, today)
                print(f"   ✅ Saved live price to historical_prices")
                
                return True
            else:
                print(f"   ❌ Failed to save to stock_data")
                return False
                
        except Exception as e:
            print(f"   ❌ Database save error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def process_investment(self, ticker: str) -> bool:
        """Process a single PMS/AIF investment"""
        if ticker not in self.investments:
            print(f"❌ {ticker} not in configuration")
            return False
        
        info = self.investments[ticker]
        
        print(f"\n{'='*80}")
        print(f"📊 {info['name']}")
        print(f"   Ticker: {ticker}")
        print(f"   Type: {info['type']}")
        print(f"{'='*80}")
        
        # Check if URL is available
        if not info.get('url') and not info.get('urls'):
            print(f"   ⚠️ No factsheet URL configured")
            if info.get('note'):
                print(f"   💡 {info['note']}")
            return False
        
        # Get URLs to try
        urls = info.get('urls', [info.get('url')]) if isinstance(info.get('urls'), list) else [info.get('url')]
        
        for url in urls:
            if not url:
                continue
            
            print(f"\n   🔍 Processing: {url}")
            
            # Download PDF
            pdf_bytes = self.download_pdf(url)
            if not pdf_bytes:
                continue
            
            # Extract text
            text = self.extract_text_from_pdf(pdf_bytes)
            if not text:
                continue
            
            # Extract returns
            print(f"\n   🔍 Extracting performance data...")
            returns_data = self.extract_returns_from_text(text)
            
            if not returns_data:
                print(f"   ⚠️ No performance data found")
                continue
            
            # Get investment details from CSV
            try:
                csv_df = pd.read_csv('pms_aif_performance.csv')
                inv_row = csv_df[csv_df['ticker'] == ticker]
                
                if not inv_row.empty:
                    investment_date = inv_row.iloc[0]['investment_date']
                    investment_amount = inv_row.iloc[0]['investment_amount']
                    
                    # Save to database
                    success = self.save_to_database(ticker, info, returns_data, investment_date, investment_amount)
                    
                    if success:
                        # Also update CSV
                        for key, value in returns_data.items():
                            if key in csv_df.columns:
                                csv_df.loc[csv_df['ticker'] == ticker, key] = f"{value}%"
                        
                        csv_df.loc[csv_df['ticker'] == ticker, 'last_updated'] = datetime.now().strftime('%Y-%m-%d')
                        csv_df.loc[csv_df['ticker'] == ticker, 'notes'] = 'From factsheet + DB'
                        csv_df.to_csv('pms_aif_performance.csv', index=False)
                        print(f"   ✅ Updated CSV file")
                        
                        return True
                else:
                    print(f"   ⚠️ Investment details not found in CSV")
                    
            except Exception as e:
                print(f"   ⚠️ Error reading CSV: {e}")
            
            # If we got returns data, that's partial success
            if returns_data:
                return True
        
        return False
    
    def process_all(self):
        """Process all PMS/AIF investments"""
        print("="*80)
        print("🚀 PMS/AIF FACTSHEET TO DATABASE LOADER")
        print("="*80)
        
        results = {'success': 0, 'failed': 0, 'skipped': 0}
        
        for ticker in self.investments.keys():
            try:
                success = self.process_investment(ticker)
                if success:
                    results['success'] += 1
                else:
                    results['failed'] += 1
            except Exception as e:
                print(f"\n❌ Error processing {ticker}: {e}")
                results['failed'] += 1
        
        # Summary
        print(f"\n{'='*80}")
        print("📊 SUMMARY")
        print(f"{'='*80}")
        print(f"✅ Success: {results['success']}")
        print(f"❌ Failed: {results['failed']}")
        print(f"\n{'='*80}")
        print("✅ DONE!")
        print(f"{'='*80}")


def main():
    loader = FactsheetToDatabaseLoader()
    loader.process_all()


if __name__ == "__main__":
    main()

