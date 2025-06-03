"""
MLH source for fetching hackathon opportunities.
"""
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any
import re
from datetime import datetime

def parse_date_string(date_str: str) -> tuple:
    """
    Parse various date string formats and return start_date, end_date.
    
    Args:
        date_str: String containing date information
        
    Returns:
        Tuple of (start_date, end_date) as strings in YYYY-MM-DD format or None
    """
    if not date_str:
        return None, None
    
    try:
        # Clean the date string
        date_str = date_str.strip()
        
        # Pattern 1: "Friday July 14, 2025 11:00AM to Jul 16, 12:00PM EDT"
        pattern1 = r'(\w+)\s+(\w+)\s+(\d+),?\s+(\d{4}).*?to\s+(\w+)\s+(\d+),?\s+(\d{4})?'
        match1 = re.search(pattern1, date_str, re.IGNORECASE)
        if match1:
            start_month, start_day, start_year = match1.group(2), match1.group(3), match1.group(4)
            end_month, end_day = match1.group(5), match1.group(6)
            end_year = match1.group(7) if match1.group(7) else start_year
            
            try:
                start_date = datetime.strptime(f"{start_month} {start_day} {start_year}", "%B %d %Y")
                end_date = datetime.strptime(f"{end_month} {end_day} {end_year}", "%B %d %Y")
                return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")
            except ValueError:
                pass
        
        # Pattern 2: "July 14th - 16th, 2025"
        pattern2 = r'(\w+)\s+(\d+)(?:st|nd|rd|th)?\s*-\s*(\d+)(?:st|nd|rd|th)?,?\s*(\d{4})'
        match2 = re.search(pattern2, date_str, re.IGNORECASE)
        if match2:
            month, start_day, end_day, year = match2.groups()
            try:
                start_date = datetime.strptime(f"{month} {start_day} {year}", "%B %d %Y")
                end_date = datetime.strptime(f"{month} {end_day} {year}", "%B %d %Y")
                return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")
            except ValueError:
                pass
        
        # Pattern 3: "Jul 14-16, 2025"
        pattern3 = r'(\w+)\s+(\d+)-(\d+),?\s*(\d{4})'
        match3 = re.search(pattern3, date_str, re.IGNORECASE)
        if match3:
            month, start_day, end_day, year = match3.groups()
            try:
                start_date = datetime.strptime(f"{month} {start_day} {year}", "%b %d %Y")
                end_date = datetime.strptime(f"{month} {end_day} {year}", "%b %d %Y")
                return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")
            except ValueError:
                pass
        
        # Pattern 4: Single date "Friday, July 14, 2025"
        pattern4 = r'(\w+),?\s+(\w+)\s+(\d+),?\s+(\d{4})'
        match4 = re.search(pattern4, date_str, re.IGNORECASE)
        if match4:
            month, day, year = match4.group(2), match4.group(3), match4.group(4)
            try:
                single_date = datetime.strptime(f"{month} {day} {year}", "%B %d %Y")
                return single_date.strftime("%Y-%m-%d"), single_date.strftime("%Y-%m-%d")
            except ValueError:
                pass
        
        # Pattern 5: ISO format "2025-07-14"
        pattern5 = r'(\d{4})-(\d{1,2})-(\d{1,2})'
        match5 = re.search(pattern5, date_str)
        if match5:
            return match5.group(0), match5.group(0)
        
    except Exception as e:
        print(f"Date parsing error: {e}")
    
    return None, None

def extract_event_dates(element) -> tuple:
    """
    Extract start and end dates from an MLH event element.
    
    Args:
        element: BeautifulSoup element containing event information
        
    Returns:
        Tuple of (start_date, end_date) as strings or (None, None)
    """
    # Look for date-related text in various places
    date_texts = []
    
    # Look for date in element text
    date_texts.append(element.get_text())
    
    # Look for date in specific classes
    date_selectors = [
        '.date', '.event-date', '.hackathon-date', '.time', '.when',
        '[class*="date"]', '[class*="time"]', '.event-info'
    ]
    
    for selector in date_selectors:
        date_elements = element.select(selector)
        for date_elem in date_elements:
            date_texts.append(date_elem.get_text())
    
    # Try to parse dates from collected text
    for text in date_texts:
        start_date, end_date = parse_date_string(text)
        if start_date and end_date:
            return start_date, end_date
    
    return None, None

def get_hackathon_urls(limit: int = 2) -> List[Dict[str, Any]]:
    """
    Fetch hackathon URLs from MLH.
    
    Args:
        limit: Maximum number of hackathons to fetch
        
    Returns:
        List of dictionaries with hackathon information
    """
    print(f"🔍 Fetching {limit} hackathons from MLH...")
    
    try:
        url = "https://mlh.io/seasons/2024/events"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        hackathons = []
        
        # Look for event containers - MLH typically uses event cards
        event_elements = soup.find_all(['div', 'article'], class_=lambda x: x and ('event' in x.lower() or 'hackathon' in x.lower()))
        
        # If no specific event containers found, look for links that seem like events
        if not event_elements:
            event_elements = soup.find_all('a', href=True)
        
        count = 0
        for element in event_elements:
            if count >= limit:
                break
                
            # Extract name and URL
            name = None
            event_url = None
            
            if element.name == 'a':
                name = element.get_text(strip=True)
                event_url = element.get('href')
            else:
                # Look for link within the container
                link = element.find('a', href=True)
                if link:
                    name = link.get_text(strip=True) or element.get_text(strip=True)[:100]
                    event_url = link.get('href')
            
            if name and event_url and len(name.strip()) > 3:
                # Ensure URL is absolute
                if event_url.startswith('/'):
                    event_url = f"https://mlh.io{event_url}"
                elif not event_url.startswith('http'):
                    continue
                
                # Extract dates from the element
                start_date, end_date = extract_event_dates(element)
                
                hackathon_data = {
                    "name": name.strip(),
                    "url": event_url,
                    "source": "mlh"
                }
                
                # Add dates if found
                if start_date:
                    hackathon_data["start_date"] = start_date
                if end_date:
                    hackathon_data["end_date"] = end_date
                
                hackathons.append(hackathon_data)
                count += 1
        
        print(f"✅ Found {len(hackathons)} hackathons from MLH")
        return hackathons[:limit]
        
    except Exception as e:
        print(f"❌ Error fetching from MLH: {str(e)}")
        # Return empty list instead of mock data
        return [] 