"""
Ensure stock_data is linked with historical_prices
This script ensures that:
1. Every ticker in historical_prices has a corresponding entry in stock_data
2. Creates stock_data entries for tickers that don't have metadata yet
3. Validates the relationship between the two tables
"""

from database_config_supabase import supabase, update_stock_data_supabase
from unified_price_fetcher import get_stock_price_and_sector
from typing import Set, List, Dict
import time


def get_all_tickers_from_historical_prices() -> Set[str]:
    """Get all unique tickers from historical_prices table"""
    try:
        print("📊 Fetching all tickers from historical_prices...")
        
        # Get distinct tickers
        result = supabase.table('historical_prices')\
            .select('ticker')\
            .execute()
        
        if result.data:
            tickers = set(row['ticker'] for row in result.data if row.get('ticker'))
            print(f"✅ Found {len(tickers)} unique tickers in historical_prices")
            return tickers
        
        return set()
    except Exception as e:
        print(f"❌ Error fetching tickers from historical_prices: {e}")
        return set()


def get_all_tickers_from_stock_data() -> Set[str]:
    """Get all tickers from stock_data table"""
    try:
        print("📊 Fetching all tickers from stock_data...")
        
        result = supabase.table('stock_data')\
            .select('ticker')\
            .execute()
        
        if result.data:
            tickers = set(row['ticker'] for row in result.data if row.get('ticker'))
            print(f"✅ Found {len(tickers)} tickers in stock_data")
            return tickers
        
        return set()
    except Exception as e:
        print(f"❌ Error fetching tickers from stock_data: {e}")
        return set()


def get_all_tickers_from_transactions() -> Set[str]:
    """Get all unique tickers from investment_transactions table"""
    try:
        print("📊 Fetching all tickers from investment_transactions...")
        
        result = supabase.table('investment_transactions')\
            .select('ticker')\
            .execute()
        
        if result.data:
            tickers = set(row['ticker'] for row in result.data if row.get('ticker'))
            print(f"✅ Found {len(tickers)} unique tickers in transactions")
            return tickers
        
        return set()
    except Exception as e:
        print(f"❌ Error fetching tickers from transactions: {e}")
        return set()


def create_stock_data_entry(ticker: str) -> bool:
    """Create a stock_data entry for a ticker"""
    try:
        print(f"🔄 Creating stock_data entry for {ticker}...")
        
        # Try to fetch metadata from yfinance
        live_price, sector, market_cap = get_stock_price_and_sector(ticker, ticker, None)
        
        # Create stock_data entry
        success = update_stock_data_supabase(
            ticker=ticker,
            sector=sector or "Unknown",
            market_cap=market_cap,
            last_price=live_price
        )
        
        if success:
            print(f"✅ Created stock_data for {ticker}")
            return True
        else:
            print(f"⚠️ Failed to create stock_data for {ticker}")
            return False
            
    except Exception as e:
        print(f"❌ Error creating stock_data for {ticker}: {e}")
        return False


def ensure_stock_data_for_all_tickers():
    """
    Ensure all tickers in historical_prices and transactions have stock_data entries.
    This establishes the proper FK relationship.
    """
    print("\n" + "="*70)
    print("🔗 ENSURING STOCK_DATA LINK FOR ALL TICKERS")
    print("="*70 + "\n")
    
    # Get all tickers from different tables
    hist_tickers = get_all_tickers_from_historical_prices()
    txn_tickers = get_all_tickers_from_transactions()
    stock_data_tickers = get_all_tickers_from_stock_data()
    
    # Combine all tickers that should have stock_data
    all_tickers = hist_tickers.union(txn_tickers)
    
    print(f"\n📊 Summary:")
    print(f"   Tickers in historical_prices: {len(hist_tickers)}")
    print(f"   Tickers in transactions: {len(txn_tickers)}")
    print(f"   Tickers in stock_data: {len(stock_data_tickers)}")
    print(f"   Total unique tickers: {len(all_tickers)}")
    
    # Find tickers missing from stock_data
    missing_tickers = all_tickers - stock_data_tickers
    
    if not missing_tickers:
        print(f"\n✅ All tickers already have stock_data entries!")
        print(f"   ✅ historical_prices ← FK → stock_data relationship is complete")
        return
    
    print(f"\n⚠️ Found {len(missing_tickers)} tickers missing from stock_data:")
    for ticker in sorted(missing_tickers):
        print(f"   - {ticker}")
    
    # Ask for confirmation
    print(f"\n{'='*70}")
    confirm = input(f"Create stock_data entries for {len(missing_tickers)} tickers? (yes/no): ")
    
    if confirm.lower() != 'yes':
        print("❌ Operation cancelled")
        return
    
    # Create stock_data entries
    print(f"\n🔄 Creating stock_data entries...")
    success_count = 0
    fail_count = 0
    
    for i, ticker in enumerate(sorted(missing_tickers), 1):
        print(f"\n[{i}/{len(missing_tickers)}] Processing {ticker}...")
        
        if create_stock_data_entry(ticker):
            success_count += 1
        else:
            fail_count += 1
        
        # Rate limiting
        if i < len(missing_tickers):
            time.sleep(0.5)  # Small delay between requests
    
    # Summary
    print(f"\n{'='*70}")
    print(f"📊 OPERATION COMPLETE")
    print(f"{'='*70}")
    print(f"   ✅ Success: {success_count}")
    print(f"   ❌ Failed: {fail_count}")
    print(f"   📈 Total: {len(missing_tickers)}")
    
    if success_count > 0:
        print(f"\n✅ historical_prices ← FK → stock_data relationship established!")
        print(f"   All {success_count} tickers now have stock_data entries")


def validate_stock_data_link():
    """Validate that all historical_prices entries have corresponding stock_data"""
    print("\n" + "="*70)
    print("🔍 VALIDATING STOCK_DATA LINK")
    print("="*70 + "\n")
    
    hist_tickers = get_all_tickers_from_historical_prices()
    stock_data_tickers = get_all_tickers_from_stock_data()
    
    orphan_tickers = hist_tickers - stock_data_tickers
    
    if not orphan_tickers:
        print("✅ VALIDATION PASSED!")
        print(f"   All {len(hist_tickers)} tickers in historical_prices have stock_data entries")
        print(f"   ✅ FK relationship is intact")
        return True
    else:
        print(f"❌ VALIDATION FAILED!")
        print(f"   Found {len(orphan_tickers)} orphan tickers in historical_prices:")
        for ticker in sorted(orphan_tickers):
            print(f"   - {ticker}")
        return False


def show_relationship_stats():
    """Show statistics about the relationship between tables"""
    print("\n" + "="*70)
    print("📊 RELATIONSHIP STATISTICS")
    print("="*70 + "\n")
    
    hist_tickers = get_all_tickers_from_historical_prices()
    txn_tickers = get_all_tickers_from_transactions()
    stock_data_tickers = get_all_tickers_from_stock_data()
    
    # Count historical_prices entries
    try:
        hist_count = supabase.table('historical_prices').select('id', count='exact').execute()
        total_hist_records = hist_count.count if hasattr(hist_count, 'count') else len(hist_count.data)
    except:
        total_hist_records = "?"
    
    # Count transactions
    try:
        txn_count = supabase.table('investment_transactions').select('id', count='exact').execute()
        total_txn_records = txn_count.count if hasattr(txn_count, 'count') else len(txn_count.data)
    except:
        total_txn_records = "?"
    
    print(f"📊 stock_data (Master Table - SHARED):")
    print(f"   Tickers: {len(stock_data_tickers)}")
    print(f"   Purpose: Metadata for all tickers (sector, market_cap, etc.)")
    
    print(f"\n📊 historical_prices (Linked to stock_data):")
    print(f"   Tickers: {len(hist_tickers)}")
    print(f"   Total Records: {total_hist_records}")
    print(f"   Purpose: Price history for tickers")
    print(f"   Link: ticker → stock_data.ticker (FK)")
    
    print(f"\n📊 investment_transactions (User-specific):")
    print(f"   Tickers: {len(txn_tickers)}")
    print(f"   Total Records: {total_txn_records}")
    print(f"   Purpose: User transactions")
    print(f"   Links: ticker → stock_data.ticker (implicit)")
    
    # Check coverage
    hist_coverage = len(hist_tickers.intersection(stock_data_tickers))
    hist_coverage_pct = (hist_coverage / len(hist_tickers) * 100) if hist_tickers else 0
    
    txn_coverage = len(txn_tickers.intersection(stock_data_tickers))
    txn_coverage_pct = (txn_coverage / len(txn_tickers) * 100) if txn_tickers else 0
    
    print(f"\n📈 Coverage Analysis:")
    print(f"   historical_prices → stock_data: {hist_coverage}/{len(hist_tickers)} ({hist_coverage_pct:.1f}%)")
    print(f"   transactions → stock_data: {txn_coverage}/{len(txn_tickers)} ({txn_coverage_pct:.1f}%)")
    
    if hist_coverage_pct == 100 and txn_coverage_pct == 100:
        print(f"\n✅ Perfect coverage! All tickers are properly linked.")
    else:
        print(f"\n⚠️ Some tickers are not linked to stock_data")


if __name__ == "__main__":
    import sys
    
    print("\n🔗 STOCK_DATA LINK MANAGEMENT TOOL")
    print("="*70)
    print("This tool ensures all tickers have stock_data entries")
    print("="*70 + "\n")
    
    print("Options:")
    print("1. Show relationship statistics")
    print("2. Validate stock_data link")
    print("3. Ensure stock_data for all tickers (create missing entries)")
    print("4. All of the above")
    print("5. Exit")
    
    choice = input("\nSelect option (1-5): ")
    
    if choice == "1":
        show_relationship_stats()
    elif choice == "2":
        validate_stock_data_link()
    elif choice == "3":
        ensure_stock_data_for_all_tickers()
    elif choice == "4":
        show_relationship_stats()
        validate_stock_data_link()
        ensure_stock_data_for_all_tickers()
        print("\n" + "="*70)
        validate_stock_data_link()  # Validate again after creation
    else:
        print("Exiting...")

