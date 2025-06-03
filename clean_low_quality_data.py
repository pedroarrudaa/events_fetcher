#!/usr/bin/env python3
"""
One-time script to clean low-quality hackathon entries from the database.
This removes existing entries that match the low-quality patterns we've identified.
"""
import os
import re
from typing import List, Dict, Any
from dotenv import load_dotenv
from database_utils import get_db_session, Hackathon
from event_filters import EventFilter

# Load environment variables
load_dotenv()

def find_low_quality_hackathons() -> List[Dict[str, Any]]:
    """
    Find hackathons in the database that match low-quality patterns.
    
    Returns:
        List of low-quality hackathon records
    """
    session = get_db_session()
    
    try:
        # Get all hackathons from database
        hackathons = session.query(Hackathon).all()
        
        print(f"📊 Found {len(hackathons)} total hackathons in database")
        
        # Use the same EventFilter logic to identify low-quality entries
        event_filter = EventFilter()
        low_quality_hackathons = []
        
        for hackathon in hackathons:
            # Convert SQLAlchemy object to dictionary format expected by quality checker
            event = {
                'id': str(hackathon.id),
                'name': hackathon.name or '',
                'url': hackathon.url or '',
                'source': hackathon.source or '',
                'start_date': hackathon.start_date,
                'short_description': hackathon.short_description or '',
                'judges': hackathon.sponsors or [],  # Hackathon table doesn't have judges, use sponsors as proxy
                'prizes': [],  # Not stored in current schema
                'sponsors': hackathon.sponsors or [],
                'themes': hackathon.themes or [],
                'city': hackathon.city,
                'remote': hackathon.remote,
                'extraction_success': True  # Assume enriched data for quality check
            }
            
            # Check if it's low quality
            if not event_filter.is_high_quality_hackathon(event):
                # Convert back to dict with hackathon object for deletion
                low_quality_hackathons.append({
                    'id': str(hackathon.id),
                    'name': hackathon.name,
                    'url': hackathon.url,
                    'source': hackathon.source,
                    'hackathon_obj': hackathon
                })
                print(f"🗑️ Low quality found: '{hackathon.name}' from {hackathon.source}")
        
        return low_quality_hackathons
        
    except Exception as e:
        print(f"❌ Error finding low-quality hackathons: {e}")
        return []
    finally:
        session.close()

def remove_low_quality_hackathons(low_quality_hackathons: List[Dict[str, Any]], dry_run: bool = True) -> int:
    """
    Remove low-quality hackathons from the database.
    
    Args:
        low_quality_hackathons: List of hackathon records to remove
        dry_run: If True, only show what would be deleted without actually deleting
        
    Returns:
        Number of hackathons removed
    """
    if not low_quality_hackathons:
        print("✅ No low-quality hackathons found to remove")
        return 0
    
    session = get_db_session()
    
    try:
        removed_count = 0
        
        print(f"\n{'🧪 DRY RUN - ' if dry_run else '🔥 REMOVING '}Found {len(low_quality_hackathons)} low-quality hackathons:")
        
        for hackathon_data in low_quality_hackathons:
            hackathon_id = hackathon_data['id']
            name = hackathon_data['name'] or 'Unknown'
            source = hackathon_data['source'] or 'unknown'
            url = hackathon_data['url'] or 'No URL'
            
            print(f"   • ID: {hackathon_id}")
            print(f"     Name: '{name}'")
            print(f"     URL: {url}")
            print(f"     Source: {source}")
            print()
            
            if not dry_run:
                # Actually delete the record using SQLAlchemy
                hackathon_obj = hackathon_data['hackathon_obj']
                session.delete(hackathon_obj)
                removed_count += 1
        
        if not dry_run:
            session.commit()
            print(f"✅ Successfully removed {removed_count} low-quality hackathons")
        else:
            print(f"🧪 DRY RUN: Would remove {len(low_quality_hackathons)} low-quality hackathons")
            print("   Run with --execute to actually delete these records")
        
        return removed_count
        
    except Exception as e:
        print(f"❌ Error removing low-quality hackathons: {e}")
        session.rollback()
        return 0
    finally:
        session.close()

def main():
    """Main function to clean low-quality data."""
    import sys
    
    print("🧹 Low-Quality Hackathon Data Cleaner")
    print("=" * 50)
    
    # Check if this is a dry run or actual execution
    dry_run = "--execute" not in sys.argv
    
    if dry_run:
        print("🧪 Running in DRY RUN mode (no data will be deleted)")
        print("   Add --execute flag to actually remove low-quality entries")
    else:
        print("🔥 EXECUTION mode - low-quality entries will be permanently deleted!")
        confirm = input("   Are you sure you want to continue? (yes/no): ")
        if confirm.lower() != 'yes':
            print("❌ Operation cancelled")
            return
    
    print()
    
    # Find low-quality hackathons
    print("🔍 Scanning database for low-quality hackathon entries...")
    low_quality_hackathons = find_low_quality_hackathons()
    
    if not low_quality_hackathons:
        print("✅ No low-quality hackathons found! Database is clean.")
        return
    
    # Remove them (or show what would be removed)
    removed_count = remove_low_quality_hackathons(low_quality_hackathons, dry_run=dry_run)
    
    print("\n" + "=" * 50)
    if dry_run:
        print(f"🧪 DRY RUN COMPLETE: Found {len(low_quality_hackathons)} low-quality entries")
        print("   Run with --execute to remove them from the database")
    else:
        print(f"✅ CLEANUP COMPLETE: Removed {removed_count} low-quality hackathons")
        print("   Your database now contains only high-quality hackathon data!")

if __name__ == "__main__":
    main() 