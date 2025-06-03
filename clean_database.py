"""
Script to completely clean all data from the database tables.
This will delete ALL hackathons and conferences data.
"""
import sys
from database_utils import get_db_engine, create_tables
from sqlalchemy import text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def clean_all_database_data():
    """
    Delete all data from hackathons and conferences tables.
    """
    try:
        print("🗑️  Starting database cleanup...")
        engine = get_db_engine()
        
        with engine.connect() as conn:
            # Start a transaction
            trans = conn.begin()
            
            try:
                # Delete all data from hackathons table
                result_hackathons = conn.execute(text("DELETE FROM hackathons"))
                hackathons_deleted = result_hackathons.rowcount
                
                # Delete all data from conferences table  
                result_conferences = conn.execute(text("DELETE FROM conferences"))
                conferences_deleted = result_conferences.rowcount
                
                # Commit the transaction
                trans.commit()
                
                print(f"✅ Database cleanup completed!")
                print(f"   - Deleted {hackathons_deleted} hackathons")
                print(f"   - Deleted {conferences_deleted} conferences")
                print(f"   - Total records deleted: {hackathons_deleted + conferences_deleted}")
                
                return True
                
            except Exception as e:
                # Rollback transaction on error
                trans.rollback()
                print(f"❌ Error during database cleanup: {str(e)}")
                return False
                
    except Exception as e:
        print(f"❌ Error connecting to database: {str(e)}")
        return False

def main():
    """Main function."""
    print("🧹 Database Cleanup Script")
    print("=" * 50)
    
    # Check if user wants to proceed
    if "--force" not in sys.argv:
        print("⚠️  WARNING: This will DELETE ALL data from hackathons and conferences tables!")
        print("   This action cannot be undone.")
        print()
        response = input("Are you sure you want to proceed? (y/N): ").strip().lower()
        
        if response != 'y':
            print("❌ Database cleanup cancelled.")
            return
    
    # Perform cleanup
    success = clean_all_database_data()
    
    if success:
        print()
        print("🎉 Database is now clean and ready for fresh data!")
        print("   You can now run the fetching scripts:")
        print("   - python hackathon_fetcher/main.py")
        print("   - python conference_fetcher/conference_fetcher.py")
    else:
        print()
        print("❌ Database cleanup failed. Please check the error messages above.")

if __name__ == "__main__":
    main() 