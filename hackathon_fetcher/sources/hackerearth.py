"""
HackerEarth source for fetching hackathon opportunities.
"""
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any

def get_hackathon_urls(limit: int = 2) -> List[Dict[str, Any]]:
    """
    Fetch hackathon URLs from HackerEarth.
    
    Args:
        limit: Maximum number of hackathons to fetch
        
    Returns:
        List of dictionaries with hackathon information
    """
    print(f"🔍 Fetching {limit} hackathons from HackerEarth...")
    
    try:
        url = "https://www.hackerearth.com/challenges/hackathon/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        hackathons = []
        
        # Look for challenge/hackathon containers
        challenge_elements = soup.find_all(['div', 'article'], class_=lambda x: x and ('challenge' in x.lower() or 'hackathon' in x.lower() or 'card' in x.lower()))
        
        # Also look for direct links that might be hackathons
        if not challenge_elements:
            challenge_elements = soup.find_all('a', href=True)
        
        count = 0
        for element in challenge_elements:
            if count >= limit:
                break
                
            # Extract name and URL
            name = None
            challenge_url = None
            
            if element.name == 'a':
                name = element.get_text(strip=True)
                challenge_url = element.get('href')
            else:
                # Look for link within the container
                link = element.find('a', href=True)
                if link:
                    name = link.get_text(strip=True) or element.get_text(strip=True)[:100]
                    challenge_url = link.get('href')
            
            if name and challenge_url and len(name.strip()) > 3:
                # Ensure URL is absolute
                if challenge_url.startswith('/'):
                    challenge_url = f"https://www.hackerearth.com{challenge_url}"
                elif not challenge_url.startswith('http'):
                    continue
                
                # Filter for hackathon-related URLs
                if 'hackathon' in challenge_url.lower() or 'challenge' in challenge_url.lower():
                    hackathons.append({
                        "name": name.strip(),
                        "url": challenge_url,
                        "source": "hackerearth"
                    })
                    count += 1
        
        print(f"✅ Found {len(hackathons)} hackathons from HackerEarth")
        return hackathons[:limit]
        
    except Exception as e:
        print(f"❌ Error fetching from HackerEarth: {str(e)}")
        # Return empty list instead of mock data
        return [] 