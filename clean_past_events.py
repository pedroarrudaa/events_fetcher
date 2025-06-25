#!/usr/bin/env python3
"""
Script to remove past events from the database
"""

import sys
import os
from datetime import datetime, date

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database_utils import get_db_manager, Hackathon, Conference
from shared_utils import DateParser

def parse_date_string(date_str):
    """Parse date string to date object using unified DateParser"""
    return DateParser.parse_to_date(date_str)

def clean_past_events():
    """Remove events that have already started"""
    today = date.today()
    print(f"Today: {today}")
    print("Removing events that have already started...")
    
    db_manager = get_db_manager()
    
    with db_manager.get_session() as session:
        # Check hackathons
        hackathons = session.query(Hackathon).all()
        removed_hackathons = 0
        
        for hackathon in hackathons:
            start_date = parse_date_string(hackathon.start_date)
            if start_date and start_date <= today:  # Started or starting today
                print(f"❌ Removing hackathon: {hackathon.start_date} - {hackathon.name}")
                session.delete(hackathon)
                removed_hackathons += 1
        
        # Check conferences
        conferences = session.query(Conference).all()
        removed_conferences = 0
        
        for conference in conferences:
            start_date = parse_date_string(conference.start_date)
            if start_date and start_date <= today:  # Started or starting today
                print(f"❌ Removing conference: {conference.start_date} - {conference.name}")
                session.delete(conference)
                removed_conferences += 1
        
        # Commit the changes
        session.commit()
        
        print(f"\n✅ Cleanup complete:")
        print(f"   - Removed {removed_hackathons} past hackathons")
        print(f"   - Removed {removed_conferences} past conferences")
        print(f"   - Total removed: {removed_hackathons + removed_conferences}")
        
        # Count remaining events
        remaining_hackathons = session.query(Hackathon).count()
        remaining_conferences = session.query(Conference).count()
        
        print(f"\n📊 Remaining events:")
        print(f"   - Hackathons: {remaining_hackathons}")
        print(f"   - Conferences: {remaining_conferences}")
        print(f"   - Total: {remaining_hackathons + remaining_conferences}")

if __name__ == "__main__":
    clean_past_events() 