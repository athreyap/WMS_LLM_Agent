"""
Script to delete users and all their associated data from Supabase
"""

from database_config_supabase import supabase
import sys

def delete_user_and_data(username):
    """Delete a user and all their associated data"""
    try:
        print(f"\n🔍 Looking for user: {username}")
        
        # Get user by username (case-insensitive)
        username_lower = username.lower()
        user_result = supabase.table("users").select("*").eq("username", username_lower).execute()
        
        if not user_result.data or len(user_result.data) == 0:
            print(f"❌ User '{username}' not found in database")
            return False
        
        user = user_result.data[0]
        user_id = user['id']
        print(f"✅ Found user: {user['username']} (ID: {user_id})")
        
        # Delete investment_transactions
        print(f"🗑️ Deleting transactions for user {user_id}...")
        trans_result = supabase.table("investment_transactions").delete().eq("user_id", user_id).execute()
        print(f"✅ Deleted {len(trans_result.data) if trans_result.data else 0} transactions")
        
        # Delete investment_files
        print(f"🗑️ Deleting files for user {user_id}...")
        files_result = supabase.table("investment_files").delete().eq("user_id", user_id).execute()
        print(f"✅ Deleted {len(files_result.data) if files_result.data else 0} files")
        
        # Delete user
        print(f"🗑️ Deleting user {username}...")
        user_delete_result = supabase.table("users").delete().eq("id", user_id).execute()
        print(f"✅ Deleted user {username}")
        
        print(f"\n✅ Successfully deleted user '{username}' and all associated data")
        return True
        
    except Exception as e:
        print(f"❌ Error deleting user '{username}': {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main function"""
    print("=" * 60)
    print("🗑️  USER DELETION SCRIPT")
    print("=" * 60)
    
    usernames_to_delete = ["kalyan", "kalyan_rao"]
    
    print(f"\n⚠️  WARNING: This will permanently delete the following users and ALL their data:")
    for username in usernames_to_delete:
        print(f"   • {username}")
    
    # Confirm deletion
    confirm = input("\n❓ Type 'DELETE' to confirm (or anything else to cancel): ")
    
    if confirm != "DELETE":
        print("\n❌ Deletion cancelled")
        return
    
    print("\n🚀 Starting deletion process...\n")
    
    success_count = 0
    for username in usernames_to_delete:
        if delete_user_and_data(username):
            success_count += 1
    
    print("\n" + "=" * 60)
    print(f"✅ Deletion complete: {success_count}/{len(usernames_to_delete)} users deleted")
    print("=" * 60)

if __name__ == "__main__":
    main()

