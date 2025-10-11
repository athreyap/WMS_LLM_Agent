#!/usr/bin/env python3
"""
Download and parse PMS factsheets to extract CAGR data
Uses PyPDF2 for text extraction (lighter than camelot)
"""

import requests
import re
import PyPDF2
import io
from typing import Optional, Dict, List
import pandas as pd
from datetime import datetime

class PMSFactsheetParser:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Latest factsheet URLs (from our test)
        self.factsheet_urls = {
            'INP000005000': {
                'name': 'Buoyant Capital',
                'url': 'https://www.buoyantcap.com/wp-content/uploads/2025/09/PMS-flyer-Sep-25.pdf'
            },
            'INP000006387': {
                'name': 'Carnelian Capital - Shift Strategy',
                'urls': [  # Multiple strategies
                    'https://www.carneliancapital.co.in/_files/ugd/3ea37e_226f032b021f40c992d0511e2782f5ae.pdf',
                    'https://www.carneliancapital.co.in/_files/ugd/3ea37e_493d1a9b40204f899bd59fb9e33b20ff.pdf'
                ]
            },
            'INP000000613': {
                'name': 'Unifi Capital BCAD',
                'url': 'https://www.unificap.com/sites/default/files/track_record/pdf/Unifi-Capital-Presentation-September-2025.pdf'
            },
            'INP000005125': {
                'name': 'Valentis Advisors',
                'url': 'https://www.valentisadvisors.com/wp-content/uploads/2025/06/Valentis-PMS-Presentation-May-2025.pdf'
            },
            # AIF
            'AIF_IN_AIF3_20-21_0857': {
                'name': 'Nuvama Enhanced Dynamic Growth AIF',
                'url': 'https://www.nuvama.com/',  # Need to find actual factsheet URL
                'note': 'AIF - may need different source'
            }
        }
    
    def download_pdf(self, url: str) -> Optional[bytes]:
        """Download PDF from URL"""
        try:
            print(f"📥 Downloading: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            print(f"✅ Downloaded {len(response.content)} bytes")
            return response.content
        except Exception as e:
            print(f"❌ Error downloading: {e}")
            return None
    
    def extract_text_from_pdf(self, pdf_bytes: bytes) -> str:
        """Extract text from PDF bytes"""
        try:
            pdf_file = io.BytesIO(pdf_bytes)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            
            return text
        except Exception as e:
            print(f"❌ Error extracting text: {e}")
            return ""
    
    def extract_cagr_from_text(self, text: str) -> Dict[str, str]:
        """
        Extract CAGR values from factsheet text
        
        Looks for patterns like:
        - 1Y Return: 15.5%
        - 3Y CAGR: 18.2%
        - 5Y CAGR: 22.1%
        """
        cagr_data = {}
        
        # Common patterns
        patterns = [
            # Pattern 1: "1Y Return: 15.5%"
            (r'1\s*[Yy](?:ear)?\s*(?:Return|CAGR)?\s*:?\s*([+-]?\d+\.?\d*)\s*%', '1y_return'),
            (r'1\s*[Yy](?:ear)?\s*(?:Performance)?\s*:?\s*([+-]?\d+\.?\d*)\s*%', '1y_return'),
            
            # Pattern 2: "3Y CAGR: 18.2%"
            (r'3\s*[Yy](?:ear)?\s*(?:CAGR|Return)?\s*:?\s*([+-]?\d+\.?\d*)\s*%', '3y_cagr'),
            (r'3\s*[Yy](?:ear)?\s*(?:Performance)?\s*:?\s*([+-]?\d+\.?\d*)\s*%', '3y_cagr'),
            
            # Pattern 3: "5Y CAGR: 22.1%"
            (r'5\s*[Yy](?:ear)?\s*(?:CAGR|Return)?\s*:?\s*([+-]?\d+\.?\d*)\s*%', '5y_cagr'),
            (r'5\s*[Yy](?:ear)?\s*(?:Performance)?\s*:?\s*([+-]?\d+\.?\d*)\s*%', '5y_cagr'),
            
            # Shorter periods
            (r'1\s*[Mm](?:onth)?\s*(?:Return)?\s*:?\s*([+-]?\d+\.?\d*)\s*%', '1m_return'),
            (r'3\s*[Mm](?:onth)?\s*(?:Return)?\s*:?\s*([+-]?\d+\.?\d*)\s*%', '3m_return'),
            (r'6\s*[Mm](?:onth)?\s*(?:Return)?\s*:?\s*([+-]?\d+\.?\d*)\s*%', '6m_return'),
        ]
        
        for pattern, key in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches and key not in cagr_data:
                # Take the first match
                value = matches[0]
                cagr_data[key] = f"{value}%"
                print(f"   ✅ Found {key}: {value}%")
        
        return cagr_data
    
    def fetch_pms_data(self, ticker: str) -> Optional[Dict[str, str]]:
        """Fetch and parse factsheet for a specific PMS/AIF"""
        if ticker not in self.factsheet_urls:
            print(f"❌ No factsheet URL configured for {ticker}")
            return None
        
        info = self.factsheet_urls[ticker]
        print(f"\n{'='*80}")
        print(f"📊 {info['name']} ({ticker})")
        print(f"{'='*80}")
        
        # Handle multiple URLs (for Carnelian with multiple strategies)
        urls_to_try = info.get('urls', [info.get('url')]) if isinstance(info.get('urls'), list) else [info.get('url')]
        
        for url in urls_to_try:
            if not url or 'nuvama.com' in url:  # Skip if no URL or Nuvama (need specific factsheet)
                continue
            
            print(f"\n🔍 Trying: {url}")
            
            # Download PDF
            pdf_bytes = self.download_pdf(url)
            if not pdf_bytes:
                continue
            
            # Extract text
            print("📄 Extracting text from PDF...")
            text = self.extract_text_from_pdf(pdf_bytes)
            
            if not text:
                print("⚠️ No text extracted")
                continue
            
            print(f"✅ Extracted {len(text)} characters")
            
            # Show sample of text (for debugging)
            print(f"\n📝 Sample text:")
            print(text[:500])
            
            # Extract CAGR
            print(f"\n🔍 Searching for CAGR values...")
            cagr_data = self.extract_cagr_from_text(text)
            
            if cagr_data:
                return cagr_data
            else:
                print("⚠️ No CAGR data found in text")
        
        return None
    
    def fetch_all_pms(self) -> Dict[str, Dict[str, str]]:
        """Fetch data for all PMS/AIF"""
        results = {}
        
        print("="*80)
        print("📥 FETCHING PMS/AIF FACTSHEETS")
        print("="*80)
        
        for ticker in self.factsheet_urls.keys():
            cagr_data = self.fetch_pms_data(ticker)
            if cagr_data:
                results[ticker] = cagr_data
        
        return results
    
    def update_csv(self, cagr_data: Dict[str, Dict[str, str]], csv_path: str = 'pms_aif_performance.csv'):
        """Update CSV with fetched CAGR data"""
        try:
            df = pd.read_csv(csv_path)
            
            print(f"\n{'='*80}")
            print("📝 UPDATING CSV FILE")
            print(f"{'='*80}")
            
            for ticker, data in cagr_data.items():
                mask = df['ticker'] == ticker
                
                # Update CAGR columns
                for key, value in data.items():
                    if key in df.columns:
                        df.loc[mask, key] = value
                
                # Update metadata
                df.loc[mask, 'last_updated'] = datetime.now().strftime('%Y-%m-%d')
                df.loc[mask, 'notes'] = 'Extracted from official factsheet'
                
                print(f"✅ Updated {ticker}")
                for key, value in data.items():
                    print(f"   {key}: {value}")
            
            # Save
            df.to_csv(csv_path, index=False)
            print(f"\n✅ CSV saved: {csv_path}")
            
            # Show updated CSV
            print(f"\n📊 Updated CSV:")
            print(df.to_string(index=False))
            
        except Exception as e:
            print(f"❌ Error updating CSV: {e}")
            import traceback
            traceback.print_exc()


def main():
    print("="*80)
    print("🚀 PMS/AIF FACTSHEET DOWNLOADER & PARSER")
    print("="*80)
    
    parser = PMSFactsheetParser()
    
    # Fetch all data
    results = parser.fetch_all_pms()
    
    if results:
        print(f"\n{'='*80}")
        print(f"✅ Successfully extracted data from {len(results)} factsheet(s)")
        print(f"{'='*80}")
        
        # Update CSV
        parser.update_csv(results)
    else:
        print(f"\n⚠️ No data could be extracted")
    
    print(f"\n{'='*80}")
    print("✅ DONE!")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()

