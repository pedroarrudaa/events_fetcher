#!/usr/bin/env python3
"""
Script to check the remaining conference data after cleanup.
"""
from database_utils import get_db_session
from sqlalchemy import text

def check_remaining_data():
    """Check the quality of remaining conference data."""
    
    session = get_db_session()
    result = session.execute(text('''
        SELECT name, url, source, description, start_date
        FROM conferences 
        ORDER BY created_at DESC 
        LIMIT 20
    '''))
    
    print('📋 Recent conferences after cleanup:')
    print('=' * 80)
    
    for i, (name, url, source, desc, start_date) in enumerate(result.fetchall(), 1):
        print(f'{i:2d}. {name[:60]}...')
        print(f'    🔗 URL: {url}')
        print(f'    📁 Source: {source}')
        print(f'    📅 Date: {start_date}')
        print(f'    📝 Desc: {(desc or "")[:80]}...')
        print()
    
    # Check for potential remaining bad data patterns
    result = session.execute(text('''
        SELECT COUNT(*) as count, 
               SUM(CASE WHEN name ILIKE '%blog%' OR url ILIKE '%/blog/%' THEN 1 ELSE 0 END) as blogs,
               SUM(CASE WHEN url ILIKE '%/user/%' OR url ILIKE '%profile%' THEN 1 ELSE 0 END) as profiles,
               SUM(CASE WHEN name ILIKE '%pricing%' OR name ILIKE '%platform%' THEN 1 ELSE 0 END) as company_pages,
               SUM(CASE WHEN start_date = 'TBD' THEN 1 ELSE 0 END) as tbd_dates
        FROM conferences
    '''))
    
    count, blogs, profiles, company_pages, tbd_dates = result.fetchone()
    
    print('📊 Remaining data quality check:')
    print(f'   Total conferences: {count}')
    print(f'   Potential blogs: {blogs}')
    print(f'   Potential profiles: {profiles}')
    print(f'   Potential company pages: {company_pages}')
    print(f'   TBD dates: {tbd_dates}')
    
    # Check sources
    result = session.execute(text('''
        SELECT source, COUNT(*) as count
        FROM conferences
        GROUP BY source
        ORDER BY count DESC
    '''))
    
    print('\n📁 Sources breakdown:')
    for source, count in result.fetchall():
        print(f'   {source}: {count}')
    
    session.close()

if __name__ == "__main__":
    check_remaining_data() 