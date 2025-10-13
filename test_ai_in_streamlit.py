"""
Test AI configuration inside Streamlit context
Run with: streamlit run test_ai_in_streamlit.py
"""

import streamlit as st

st.title("🤖 AI Configuration Test")

# Check secrets
st.subheader("1. Streamlit Secrets")
try:
    gemini_key = st.secrets.get("gemini_api_key") or st.secrets.get("google_api_key")
    openai_key = st.secrets.get("open_ai")
    
    if gemini_key:
        st.success(f"✅ Gemini API Key found: {gemini_key[:20]}...")
    else:
        st.error("❌ Gemini API Key not found")
    
    if openai_key:
        st.success(f"✅ OpenAI API Key found: {openai_key[:20]}...")
    else:
        st.error("❌ OpenAI API Key not found")
except Exception as e:
    st.error(f"Error accessing secrets: {e}")

# Test AI Price Fetcher
st.subheader("2. AI Price Fetcher")
try:
    from ai_price_fetcher import AIPriceFetcher
    
    ai = AIPriceFetcher()
    
    if ai.is_available():
        st.success("✅ AI Price Fetcher is AVAILABLE!")
        
        # Test MF fetch
        st.subheader("3. Test MF NAV Fetch")
        test_code = "102949"
        test_name = "HDFC Hybrid Equity Fund - Reg Plan - Growth"
        
        with st.spinner(f"Testing NAV fetch for {test_code}..."):
            nav = ai.get_mf_nav(test_code, test_name)
            
            if nav and nav > 0:
                st.success(f"✅ SUCCESS! NAV = ₹{nav}")
            else:
                st.error(f"❌ FAILED! Returned: {nav}")
    else:
        st.error("❌ AI Price Fetcher is NOT AVAILABLE")
        st.info("Check API keys in .streamlit/secrets.toml")
        
except Exception as e:
    st.error(f"Error: {e}")
    import traceback
    st.code(traceback.format_exc())

# Test Bulk Integration
st.subheader("4. Bulk Integration")
try:
    from bulk_integration import BULK_FETCH_AVAILABLE
    
    if BULK_FETCH_AVAILABLE:
        st.success("✅ Bulk Integration is AVAILABLE")
    else:
        st.error("❌ Bulk Integration is NOT AVAILABLE")
except Exception as e:
    st.error(f"Error: {e}")

st.divider()
st.info("💡 If all checks pass, restart your main app to use AI-powered bulk fetching!")

