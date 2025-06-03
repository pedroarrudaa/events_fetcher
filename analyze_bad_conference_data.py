#!/usr/bin/env python3
"""
Script to analyze and clean up bad conference data in the database.
"""
import os
import sys
from database_utils import get_db_session, get_db_stats, Conference
from sqlalchemy import text
import pandas as pd

def analyze_bad_data():
    """Analyze the bad data in the conferences table."""
    
    try:
        session = get_db_session()
        
        # Get all conferences data
        result = session.execute(text("""
            SELECT id, name, url, start_date, city, remote, description, 
                   short_description, source, created_at
            FROM conferences 
            ORDER BY created_at DESC
        """))
        
        rows = result.fetchall()
        
        print(f"📊 Total conferences in database: {len(rows)}")
        
        # Analyze the data
        blog_posts = []
        signup_pages = []
        company_pages = []
        user_profiles = []
        resource_pages = []
        legitimate_conferences = []
        tbd_dates = []
        
        for row in rows:
            id, name, url, start_date, city, remote, description, short_description, source, created_at = row
            
            name_lower = (name or '').lower()
            url_lower = (url or '').lower()
            desc_lower = (description or '').lower()
            short_desc_lower = (short_description or '').lower()
            
            all_text = f"{name_lower} {url_lower} {desc_lower} {short_desc_lower}"
            
            # Categorize the bad data
            if 'blog' in name_lower or '/blog/' in url_lower:
                blog_posts.append((id, name, url))
            elif 'sign up' in all_text or 'create account' in all_text or '/signup' in url_lower:
                signup_pages.append((id, name, url))
            elif '/user/' in url_lower or 'viewprofilepage' in url_lower or 'user profile' in all_text:
                user_profiles.append((id, name, url))
            elif any(x in all_text for x in ['pricing', 'platform', 'business solution', 'resource center', 'support', 'documentation']):
                company_pages.append((id, name, url))
            elif any(x in all_text for x in ['collection of', 'explore', 'resources to help', 'learning platform']):
                resource_pages.append((id, name, url))
            elif start_date == 'TBD':
                tbd_dates.append((id, name, url))
            # Additional bad data patterns
            elif 'status.' in url_lower or '/status' in url_lower:
                company_pages.append((id, name, url))  # Status pages
            elif 'ticketing' in name_lower or 'event industry' in all_text:
                company_pages.append((id, name, url))  # Service pages
            elif name.startswith('Event at https://') and not any(x in name_lower for x in ['conference', 'summit', 'symposium', 'workshop', 'expo']):
                company_pages.append((id, name, url))  # Generic "Event at" entries without conference indicators
            elif any(x in url_lower for x in ['/organizer/', '/industry/', '/service']):
                company_pages.append((id, name, url))  # Service/organizer pages
            elif any(x in name_lower for x in ['conference', 'summit', 'symposium', 'workshop', 'event', 'expo', 'convention']):
                legitimate_conferences.append((id, name, url))
        
        print("\n📋 Data Analysis Results:")
        print(f"🔍 Blog posts: {len(blog_posts)}")
        print(f"📝 Sign-up pages: {len(signup_pages)}")
        print(f"👤 User profiles: {len(user_profiles)}")
        print(f"🏢 Company/resource pages: {len(company_pages)}")
        print(f"📚 Resource collections: {len(resource_pages)}")
        print(f"📅 TBD dates: {len(tbd_dates)}")
        print(f"✅ Legitimate conferences: {len(legitimate_conferences)}")
        
        # Show some examples of bad data
        if blog_posts:
            print("\n🔍 Example blog posts:")
            for i, (id, name, url) in enumerate(blog_posts[:5]):
                print(f"  {id}: {name[:60]}... → {url}")
        
        if signup_pages:
            print("\n📝 Example sign-up pages:")
            for i, (id, name, url) in enumerate(signup_pages[:5]):
                print(f"  {id}: {name[:60]}... → {url}")
        
        if user_profiles:
            print("\n👤 Example user profiles:")
            for i, (id, name, url) in enumerate(user_profiles[:5]):
                print(f"  {id}: {name[:60]}... → {url}")
        
        # Calculate total bad data
        total_bad = len(blog_posts) + len(signup_pages) + len(user_profiles) + len(company_pages) + len(resource_pages) + len(tbd_dates)
        print(f"\n🗑️ Total bad data entries: {total_bad} out of {len(rows)} ({total_bad/len(rows)*100:.1f}%)")
        
        session.close()
        
        return {
            'blog_posts': [x[0] for x in blog_posts],
            'signup_pages': [x[0] for x in signup_pages],
            'user_profiles': [x[0] for x in user_profiles],
            'company_pages': [x[0] for x in company_pages],
            'resource_pages': [x[0] for x in resource_pages],
            'tbd_dates': [x[0] for x in tbd_dates]
        }
        
    except Exception as e:
        print(f"❌ Error analyzing data: {e}")
        return None

def delete_bad_data(bad_data_ids):
    """Delete bad data from the database."""
    
    if not bad_data_ids:
        print("✅ No bad data to delete")
        return
    
    try:
        session = get_db_session()
        
        # Flatten all bad data IDs
        all_bad_ids = []
        for category, ids in bad_data_ids.items():
            all_bad_ids.extend(ids)
        
        if not all_bad_ids:
            print("✅ No bad data IDs found")
            return
        
        print(f"🗑️ Deleting {len(all_bad_ids)} bad data entries...")
        
        # Delete in batches to avoid SQL limits
        batch_size = 100
        deleted_count = 0
        
        for i in range(0, len(all_bad_ids), batch_size):
            batch = all_bad_ids[i:i + batch_size]
            
            # Use SQLAlchemy to delete records
            deleted = session.query(Conference).filter(Conference.id.in_(batch)).delete(synchronize_session=False)
            deleted_count += deleted
            
        session.commit()
        session.close()
        
        print(f"✅ Successfully deleted {deleted_count} bad data entries")
        
    except Exception as e:
        print(f"❌ Error deleting bad data: {e}")

def main():
    """Main function."""
    print("🔍 Analyzing conference database for bad data...")
    
    # Analyze the data
    bad_data_ids = analyze_bad_data()
    
    if not bad_data_ids:
        print("❌ Failed to analyze data")
        return
    
    # Ask user if they want to delete the bad data
    total_bad = sum(len(ids) for ids in bad_data_ids.values())
    
    if total_bad == 0:
        print("✅ No bad data found!")
        return
    
    print(f"\n🗑️ Found {total_bad} bad data entries")
    response = input("Do you want to delete this bad data? (y/N): ").strip().lower()
    
    if response in ['y', 'yes']:
        delete_bad_data(bad_data_ids)
        
        # Show updated stats
        print("\n📊 Updated database statistics:")
        try:
            stats = get_db_stats()
            print(f"   📊 Total conferences: {stats['conferences']['total']}")
            print(f"   🌐 Remote conferences: {stats['conferences']['remote']}")
            print(f"   🏢 In-person conferences: {stats['conferences']['in_person']}")
        except Exception as e:
            print(f"   ⚠️ Could not get updated stats: {e}")
    else:
        print("🚫 Data deletion cancelled")

if __name__ == "__main__":
    main() 