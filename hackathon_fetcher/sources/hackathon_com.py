"""
Hackathon.com source for fetching hackathon opportunities.
"""
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any

def get_hackathon_urls(limit: int = 2) -> List[Dict[str, Any]]:
    """
    Fetch hackathon URLs from hackathon.com.
    
    Args:
        limit: Maximum number of hackathons to fetch
        
    Returns:
        List of dictionaries with hackathon information
    """
    print(f"🔍 Fetching {limit} hackathons from hackathon.com...")
    
    try:
        url = "https://www.hackathon.com/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        hackathons = []
        
        # Look for hackathon containers - different possible structures
        hackathon_elements = soup.find_all(['div', 'article', 'section'], class_=lambda x: x and ('hackathon' in x.lower() or 'event' in x.lower() or 'card' in x.lower()))
        
        # Also look for direct links that might be hackathons
        if not hackathon_elements:
            hackathon_elements = soup.find_all('a', href=True)
        
        count = 0
        for element in hackathon_elements:
            if count >= limit:
                break
                
            # Extract name and URL
            name = None
            hackathon_url = None
            
            if element.name == 'a':
                name = element.get_text(strip=True)
                hackathon_url = element.get('href')
            else:
                # Look for link within the container
                link = element.find('a', href=True)
                if link:
                    name = link.get_text(strip=True) or element.get_text(strip=True)[:100]
                    hackathon_url = link.get('href')
            
            if name and hackathon_url and len(name.strip()) > 3:
                # Ensure URL is absolute
                if hackathon_url.startswith('/'):
                    hackathon_url = f"https://www.hackathon.com{hackathon_url}"
                elif not hackathon_url.startswith('http'):
                    continue
                
                # Skip common non-hackathon URLs
                skip_patterns = ['/about', '/contact', '/login', '/signup', '/terms', '/privacy']
                if any(pattern in hackathon_url.lower() for pattern in skip_patterns):
                    continue
                
                # Additional quality checks for hackathon.com
                # Skip generic or placeholder names
                name_lower = name.lower().strip()
                if name_lower in ['online', 'virtual', 'remote', 'hackathon', 'event', 'challenge']:
                    continue
                
                # Skip URLs that look like generic pages
                if hackathon_url.lower() in ['https://www.hackathon.com/', 'https://www.hackathon.com/online']:
                    continue
                
                hackathons.append({
                    "name": name.strip(),
                    "url": hackathon_url,
                    "source": "hackathon_com"
                })
                count += 1
        
        print(f"✅ Found {len(hackathons)} hackathons from hackathon.com")
        return hackathons[:limit]
        
    except Exception as e:
        print(f"❌ Error fetching from hackathon.com: {str(e)}")
        # Return empty list instead of mock data
        return [] 