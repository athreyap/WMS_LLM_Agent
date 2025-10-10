"""
Test PMS NAV calculation with real example
"""

from pms_aif_fetcher import get_pms_nav, calculate_current_value
from datetime import datetime

def test_pms_calculation_example():
    """
    Test with example from Poornima_PMS_AIF.csv:
    - INP000006387 (Carnelian Capital)
    - Investment: ₹50,00,000
    - Date: 23/06/2022
    """
    
    print("=" * 80)
    print("🧪 TESTING PMS NAV CALCULATION")
    print("=" * 80)
    
    # Example 1: Carnelian Capital
    print("\n📋 Example 1: Carnelian Capital - The Shift Strategy")
    print("-" * 80)
    
    ticker = "INP000006387"
    pms_name = "Carnelian Capital"
    investment_date = "2022-06-23"
    investment_amount = 5000000  # ₹50 lakhs
    
    print(f"Ticker: {ticker}")
    print(f"PMS Name: {pms_name}")
    print(f"Investment Date: {investment_date}")
    print(f"Investment Amount: ₹{investment_amount:,.2f}")
    print()
    
    result = get_pms_nav(
        ticker=ticker,
        pms_name=pms_name,
        investment_date=investment_date,
        investment_amount=investment_amount
    )
    
    if result:
        print("✅ PMS Data Retrieved:")
        print(f"  Portfolio Manager: {result.get('pms_name')}")
        print(f"  Strategy: {result.get('strategy')}")
        print(f"  1M Return: {result.get('1m_return', 'N/A')}")
        print(f"  1Y Return: {result.get('1y_return', 'N/A')}")
        print(f"  3Y CAGR: {result.get('3y_cagr', 'N/A')}")
        print(f"  5Y CAGR: {result.get('5y_cagr', 'N/A')}")
        
        if 'calculated_value' in result:
            calc = result['calculated_value']
            print(f"\n💰 Calculated Values:")
            print(f"  Initial Investment: ₹{calc['initial_investment']:,.2f}")
            print(f"  Current Value: ₹{calc['current_value']:,.2f}")
            print(f"  Absolute Gain: ₹{calc['absolute_gain']:,.2f}")
            print(f"  Percentage Gain: {calc['percentage_gain']:.2f}%")
            print(f"  Investment Period: {calc['years_elapsed']:.2f} years ({calc['months_elapsed']} months)")
            print(f"  Return Used: {calc['return_period']}")
            print(f"  Calculation Method: {calc['calculation_method']}")
    else:
        print("❌ Failed to retrieve PMS data")
    
    # Example 2: Manual calculation test
    print("\n\n📋 Example 2: Manual Calculation Test (Buoyant Opportunities)")
    print("-" * 80)
    
    # Simulating Buoyant data from your example
    returns_data = {
        '1m_return': '1.8%',
        '1y_return': '24.6%',
        '3y_cagr': '17.2%',
        '5y_cagr': '18.5%'
    }
    
    investment_amount_2 = 10000000  # ₹1 crore
    investment_date_2 = "2020-06-01"  # ~5.4 years ago
    
    print(f"Investment Amount: ₹{investment_amount_2:,.2f}")
    print(f"Investment Date: {investment_date_2}")
    print(f"Returns Data: {returns_data}")
    print()
    
    calc_result = calculate_current_value(investment_amount_2, investment_date_2, returns_data)
    
    print("💰 Calculated Values:")
    print(f"  Initial Investment: ₹{calc_result['initial_investment']:,.2f}")
    print(f"  Current Value: ₹{calc_result['current_value']:,.2f}")
    print(f"  Absolute Gain: ₹{calc_result['absolute_gain']:,.2f}")
    print(f"  Percentage Gain: {calc_result['percentage_gain']:.2f}%")
    print(f"  Investment Period: {calc_result['years_elapsed']:.2f} years")
    print(f"  Return Used: {calc_result['return_period']}")
    
    # Show the calculation formula
    if calc_result['return_used']:
        print(f"\n📐 Formula Used:")
        print(f"  Current Value = Initial Investment × (1 + CAGR)^Years")
        print(f"  Current Value = ₹{investment_amount_2:,.2f} × (1 + {calc_result['return_used']:.4f})^{calc_result['years_elapsed']:.2f}")
        print(f"  Current Value = ₹{calc_result['current_value']:,.2f}")

if __name__ == "__main__":
    test_pms_calculation_example()

