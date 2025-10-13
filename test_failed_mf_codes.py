#!/usr/bin/env python3
"""
Test the 9 MF codes that are showing 0% returns
"""

import os

# Set API key for testing
os.environ['GOOGLE_API_KEY'] = "AIzaSyAnmI0sWrLlV5_UXVBBoyHkU2DvBdLlTjs"

from ai_price_fetcher import AIPriceFetcher
import google.generativeai as genai

print("="*80)
print("TESTING FAILED MF CODES")
print("="*80)

failed_mf = [
    ('128470', 'PGIM India Midcap Fund - Direct Plan - Growth'),
    ('104781', 'SBI Healthcare Opportunities Fund - Regular Plan - Growth'),
    ('120140', 'Axis Mid Cap Fund - Growth (Regular)'),
    ('102949', 'HDFC Hybrid Equity Fund - Reg Plan - Growth'),
    ('120122', 'Axis Large Cap Fund - Regular Plan - Growth'),
    ('133560', 'Invesco India Infrastructure Fund - Regular Plan - Growth'),
    ('25872', 'DSP Dynamic Asset Allocation Fund - Regular Plan - Growth'),
    ('133561', 'Invesco India Infrastructure Fund - Direct Plan - Growth'),
    ('134812', 'Mirae Asset Aggressive Hybrid Fund - Regular Plan - Growth'),
]

print(f"\nTesting {len(failed_mf)} MF codes that showed 0% returns...\n")

# Test with AI bulk (same as production)
genai.configure(api_key=os.environ['GOOGLE_API_KEY'])
model = genai.GenerativeModel('models/gemini-2.5-flash')

# Build bulk prompt (exactly as in production)
fund_list = []
for idx, (code, name) in enumerate(failed_mf):
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

print("Sending bulk request to AI...")
print("-"*80)

try:
    response = model.generate_content(prompt)
    print("\nAI Response:")
    print(response.text)
    
    print("\n" + "="*80)
    print("PARSED RESULTS:")
    print("="*80)
    
    found_codes = {}
    for line in response.text.strip().split('\n'):
        if '|' in line:
            parts = line.split('|')
            if len(parts) >= 2:
                code = parts[0].strip()
                try:
                    nav = float(parts[1].strip())
                    found_codes[code] = nav
                    print(f"✅ {code}: ₹{nav}")
                except:
                    print(f"⚠️ {code}: Invalid NAV format")
    
    print("\n" + "="*80)
    print("SUMMARY:")
    print("="*80)
    print(f"Requested: {len(failed_mf)} codes")
    print(f"Found: {len(found_codes)} codes")
    print(f"Missing: {len(failed_mf) - len(found_codes)} codes")
    
    if len(found_codes) < len(failed_mf):
        missing = [code for code, _ in failed_mf if code not in found_codes]
        print(f"\n❌ Missing codes: {missing}")
        print("\n💡 REASON: These codes might be:")
        print("   1. Delisted/closed funds")
        print("   2. Incorrect AMFI codes")
        print("   3. New funds not in AI training data")
        
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "="*80)
print("RECOMMENDATION:")
print("="*80)
print("""
If AI cannot find these codes:
1. Verify AMFI codes are correct (check AMFI website)
2. Use mftool as fallback for these specific codes
3. Or update CSV with correct ISIN codes instead of AMFI codes
""")

