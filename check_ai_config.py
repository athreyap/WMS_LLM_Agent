#!/usr/bin/env python3
"""
Check if AI is properly configured for MF/PMS price fetching
"""

import os
import sys

print("="*80)
print("AI CONFIGURATION CHECK")
print("="*80)

# Check 1: Environment variables
print("\n1. ENVIRONMENT VARIABLES:")
gemini_key_env = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
openai_key_env = os.getenv('OPENAI_API_KEY')

print(f"   GOOGLE_API_KEY: {'✅ Set' if gemini_key_env else '❌ Not set'}")
print(f"   OPENAI_API_KEY: {'✅ Set' if openai_key_env else '❌ Not set'}")

# Check 2: Streamlit secrets
print("\n2. STREAMLIT SECRETS:")
try:
    import streamlit as st
    gemini_key_st = st.secrets.get("google_api_key") or st.secrets.get("gemini_api_key")
    openai_key_st = st.secrets.get("open_ai") or st.secrets.get("openai_api_key")
    print(f"   google_api_key: {'✅ Set' if gemini_key_st else '❌ Not set'}")
    print(f"   open_ai: {'✅ Set' if openai_key_st else '❌ Not set'}")
except:
    print("   ⚠️ Streamlit not running - secrets unavailable")

# Check 3: AI fetcher availability
print("\n3. AI PRICE FETCHER:")
try:
    from ai_price_fetcher import AIPriceFetcher
    
    ai = AIPriceFetcher()
    if ai.is_available():
        print("   ✅ AI fetcher is AVAILABLE")
        print(f"   Model: {ai.gemini_client if hasattr(ai, 'gemini_client') else 'OpenAI'}")
    else:
        print("   ❌ AI fetcher is NOT AVAILABLE")
        print("   💡 Check API keys in .streamlit/secrets.toml or environment")
except ImportError as e:
    print(f"   ❌ Cannot import ai_price_fetcher: {e}")
except Exception as e:
    print(f"   ❌ Error initializing AI: {e}")

# Check 4: Bulk integration
print("\n4. BULK INTEGRATION:")
try:
    from bulk_integration import fetch_live_prices_bulk
    print("   ✅ bulk_integration.py found")
except ImportError:
    print("   ❌ bulk_integration.py NOT FOUND")
    print("   💡 Upload bulk_integration.py to server")

# Check 5: Test MF NAV fetch
print("\n5. TEST MF NAV FETCH:")
try:
    from ai_price_fetcher import get_mf_nav_with_ai
    
    test_code = "102949"
    test_name = "HDFC Hybrid Equity Fund"
    
    print(f"   Testing: {test_code} ({test_name})")
    nav = get_mf_nav_with_ai(test_code, test_name)
    
    if nav and nav > 0:
        print(f"   ✅ SUCCESS: NAV = ₹{nav}")
    else:
        print(f"   ❌ FAILED: Returned {nav}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Summary
print("\n" + "="*80)
print("DIAGNOSIS & FIX")
print("="*80)

if not (gemini_key_env or openai_key_env):
    print("""
❌ PROBLEM: No AI API keys configured!

FIX: Add API keys to Streamlit secrets:

1. Create/edit .streamlit/secrets.toml:
   
   [default]
   google_api_key = "YOUR_GEMINI_KEY_HERE"
   # OR
   open_ai = "YOUR_OPENAI_KEY_HERE"

2. Restart Streamlit app

3. Verify in app settings that keys are loaded
""")
else:
    print("""
✅ API keys are configured!

If MF still showing 0%, check:
1. Run this from Streamlit app (not standalone)
2. Check logs for "AI not available" warnings
3. Verify bulk_integration.py is uploaded
4. Check if BULK_FETCH_AVAILABLE = True in web_agent.py logs
""")

print("="*80)

