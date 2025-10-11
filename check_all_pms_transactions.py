#!/usr/bin/env python3
"""
Check for PMS transactions across all users
"""

from database_config_supabase import get_transactions_supabase, supabase
import pandas as pd

def check_all_pms_transactions():
    """Check for PMS transactions across all users"""

    print("🔍 Checking for PMS transactions across all users...")

    try:
        # Get all users first
        users_result = supabase.table('users').select('id, username').execute()
        if not users_result.data:
            print("❌ No users found")
            return

        users = users_result.data
        print(f"✅ Found {len(users)} users")

        all_pms_transactions = []

        for user in users:
            user_id = user['id']
            username = user['username']

            try:
                transactions = get_transactions_supabase(user_id=user_id)
                if transactions:
                    df = pd.DataFrame(transactions)

                    # Find PMS transactions for this user
                    pms_txns = []
                    for _, txn in df.iterrows():
                        ticker = str(txn.get('ticker', '')).upper()
                        if any(keyword in ticker for keyword in ['PMS', 'AIF', 'BUOYANT', 'CARNELIAN']):
                            pms_txns.append({
                                'user_id': user_id,
                                'username': username,
                                'ticker': txn.get('ticker'),
                                'price': txn.get('price'),
                                'date': txn.get('date'),
                                'quantity': txn.get('quantity'),
                                'transaction_type': txn.get('transaction_type')
                            })

                    if pms_txns:
                        all_pms_transactions.extend(pms_txns)
                        print(f"   👤 {username}: Found {len(pms_txns)} PMS transactions")

            except Exception as e:
                print(f"   ❌ Error checking user {username}: {e}")

        print(f"\n💼 Total PMS/AIF transactions found: {len(all_pms_transactions)}")

        for txn in all_pms_transactions:
            print(f"   {txn['username']}: {txn['ticker']} - ₹{txn['price']} on {txn['date']} ({txn['quantity']} units)")

        return all_pms_transactions

    except Exception as e:
        print(f"❌ Error checking PMS transactions: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_all_pms_transactions()
