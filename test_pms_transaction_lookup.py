#!/usr/bin/env python3
"""
Test PMS transaction lookup functionality
"""

from database_config_supabase import get_transactions_supabase, supabase
import pandas as pd
from datetime import datetime

def test_pms_transaction_lookup():
    """Test PMS transaction lookup"""

    print("🔍 Testing PMS transaction lookup...")

    # Get all transactions - try to find the user with PMS transactions
    try:
        # First, find users with PMS transactions
        users_result = supabase.table('users').select('id, username').execute()
        pms_user_id = None

        for user in users_result.data:
            user_id = user['id']
            transactions = get_transactions_supabase(user_id=user_id)
            if transactions:
                df = pd.DataFrame(transactions)
                pms_count = df['ticker'].str.upper().str.contains('PMS|AIF|BUOYANT|CARNELIAN').sum()
                if pms_count > 0:
                    pms_user_id = user_id
                    print(f"🔍 Found PMS transactions for user: {user['username']} (ID: {user_id})")
                    break

        if not pms_user_id:
            print("❌ No users with PMS transactions found")
            return

        transactions = get_transactions_supabase(user_id=pms_user_id)
        if not transactions:
            print("❌ No transactions found")
            return

        print(f"✅ Found {len(transactions)} total transactions")

        # Convert to DataFrame
        df = pd.DataFrame(transactions)
        df['date'] = pd.to_datetime(df['date'])

        # Test PMS ticker lookup
        pms_ticker = 'BUOYANT_OPPORTUNITIES_PMS'
        target_date = datetime(2024, 1, 6)

        print(f"\n📊 Testing lookup for {pms_ticker} on {target_date.strftime('%Y-%m-%d')}")

        # Simulate the lookup logic from web_agent.py
        ticker_txns = df[
            (df['ticker'] == pms_ticker) &
            (df['date'] <= target_date) &
            (df['transaction_type'] == 'buy')
        ]

        print(f"   🔍 Found {len(ticker_txns)} matching transactions")

        if not ticker_txns.empty:
            latest_txn = ticker_txns.sort_values('date', ascending=False).iloc[0]
            print(f"   ✅ Latest transaction: ₹{latest_txn['price']} on {latest_txn['date'].strftime('%Y-%m-%d')}")
            print(f"   📋 Transaction details: {latest_txn.to_dict()}")
        else:
            print("   ❌ No matching transactions found")

        # Show all PMS transactions
        pms_transactions = df[df['ticker'].str.upper().str.contains('PMS|AIF|BUOYANT|CARNELIAN')]
        print(f"\n💼 All PMS/AIF transactions found: {len(pms_transactions)}")

        for _, txn in pms_transactions.iterrows():
            print(f"   {txn['ticker']}: ₹{txn['price']} on {txn['date'].strftime('%Y-%m-%d')}")

    except Exception as e:
        print(f"❌ Error in PMS transaction lookup: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_pms_transaction_lookup()
