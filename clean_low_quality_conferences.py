#!/usr/bin/env python3
"""
Clean low-quality conference data from the database.

This script identifies and removes conference entries that don't meet quality standards:
- Generic names like "Artificial Intelligence", "Conference", "Event at https://..."
- Invalid URLs (root pages, sign-up pages, blog pages)
- Insufficient data after enrichment
- Duplicate entries

Usage:
    python clean_low_quality_conferences.py          # Dry run (shows what would be deleted)
    python clean_low_quality_conferences.py --execute # Actually delete the entries
"""

import argparse
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

# Add the current directory to Python path to import modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from database_utils import get_db_engine
from event_filters import EventFilter

def get_all_conferences():
    """Get all conferences from the database."""
    try:
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Query all conferences - simplified to work with any table structure
        result = session.execute(text("""
            SELECT *
            FROM conferences
            ORDER BY created_at DESC
        """))
        
        conferences = []
        for row in result:
            # Convert row to dictionary dynamically
            conference_dict = dict(row._mapping)
            conferences.append(conference_dict)
        
        session.close()
        return conferences
        
    except Exception as e:
        print(f"❌ Error fetching conferences: {e}")
        return []

def delete_conferences(conference_ids):
    """Delete conferences by ID."""
    if not conference_ids:
        return 0
        
    try:
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Delete conferences
        result = session.execute(text("""
            DELETE FROM conferences 
            WHERE id = ANY(:ids)
        """), {'ids': conference_ids})
        
        session.commit()
        deleted_count = result.rowcount
        session.close()
        
        return deleted_count
        
    except Exception as e:
        print(f"❌ Error deleting conferences: {e}")
        return 0

def main():
    parser = argparse.ArgumentParser(description='Clean low-quality conference data from database')
    parser.add_argument('--execute', action='store_true', help='Actually delete the entries (default is dry run)')
    args = parser.parse_args()
    
    print("🔍 Scanning database for low-quality conferences...")
    
    # Get all conferences
    conferences = get_all_conferences()
    if not conferences:
        print("No conferences found in database.")
        return
    
    print(f"📊 Found {len(conferences)} conferences in database")
    
    # Initialize quality filter
    event_filter = EventFilter()
    
    # Find low-quality conferences
    low_quality_conferences = []
    high_quality_count = 0
    
    for conference in conferences:
        if not event_filter.is_high_quality_conference(conference):
            low_quality_conferences.append(conference)
        else:
            high_quality_count += 1
    
    print(f"\n📈 Quality Analysis:")
    print(f"   • High-quality conferences: {high_quality_count}")
    print(f"   • Low-quality conferences: {len(low_quality_conferences)}")
    
    if not low_quality_conferences:
        print("✅ No low-quality conferences found! Database is clean.")
        return
    
    print(f"\n🗑️ Low-quality conferences to be removed:")
    for i, conference in enumerate(low_quality_conferences, 1):
        name = conference['name'][:60] + ('...' if len(conference['name']) > 60 else '')
        url = conference['url'][:80] + ('...' if len(conference['url']) > 80 else '')
        source = conference.get('source', 'unknown')
        created = conference.get('created_at', 'unknown')
        
        print(f"   {i:2d}. {name}")
        print(f"       URL: {url}")
        print(f"       Source: {source} | Created: {created}")
        print()
    
    if args.execute:
        print("🚨 Executing deletion...")
        conference_ids = [conf['id'] for conf in low_quality_conferences]
        deleted_count = delete_conferences(conference_ids)
        
        if deleted_count > 0:
            print(f"✅ Successfully deleted {deleted_count} low-quality conferences")
        else:
            print("❌ Failed to delete conferences")
    else:
        print("🔒 DRY RUN - No conferences were deleted")
        print("    Run with --execute flag to actually delete these entries")

if __name__ == "__main__":
    main() 