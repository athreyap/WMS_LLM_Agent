#!/usr/bin/env python3
"""
Database Schema Fix Script
Adds missing 'sector' column to investment_transactions table
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

def fix_database_schema():
    """Fix the database schema by adding missing columns"""
    
    # Database connection - use the same URL as database_config_supabase.py
    DATABASE_URL = "postgresql://postgres:wmssupabase123@db.rolcoegikoeblxzqgkix.supabase.co:5432/postgres"
    
    try:
        # Create engine
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            # Check if sector column exists
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'investment_transactions' 
                AND column_name = 'sector'
            """))
            
            if result.fetchone():
                print("✅ Sector column already exists")
                return True
            
            # Add sector column
            print("🔄 Adding sector column to investment_transactions table...")
            conn.execute(text("""
                ALTER TABLE investment_transactions 
                ADD COLUMN sector VARCHAR(255)
            """))
            conn.commit()
            print("✅ Sector column added successfully!")
            
            # Update existing records with default sector value
            print("🔄 Updating existing records with default sector value...")
            conn.execute(text("""
                UPDATE investment_transactions 
                SET sector = 'Unknown' 
                WHERE sector IS NULL
            """))
            conn.commit()
            print("✅ Existing records updated!")
            
            return True
            
    except Exception as e:
        print(f"❌ Error fixing database schema: {e}")
        return False

def verify_fix():
    """Verify that the fix was successful"""
    DATABASE_URL = "postgresql://postgres:wmssupabase123@db.rolcoegikoeblxzqgkix.supabase.co:5432/postgres"
    
    try:
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            # Check column exists
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'investment_transactions' 
                AND column_name = 'sector'
            """))
            
            if result.fetchone():
                print("✅ Verification successful: sector column exists")
                
                # Check transaction count
                result = conn.execute(text("SELECT COUNT(*) FROM investment_transactions"))
                count = result.fetchone()[0]
                print(f"✅ Found {count} transactions in database")
                
                return True
            else:
                print("❌ Verification failed: sector column still missing")
                return False
                
    except Exception as e:
        print(f"❌ Verification error: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Database Schema Fix Tool")
    print("=" * 40)
    
    if fix_database_schema():
        print("\n🔍 Verifying fix...")
        if verify_fix():
            print("\n✅ Database schema fixed successfully!")
            print("You can now run the web agent without errors.")
        else:
            print("\n❌ Verification failed!")
    else:
        print("\n❌ Failed to fix database schema!")
