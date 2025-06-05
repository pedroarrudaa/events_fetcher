"""
Eventbrite source for fetching hackathon opportunities.
"""
import requests
import time
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from urllib.parse import urljoin, urlparse
import re

class EventbriteScraper:
    """Scraper for Eventbrite hackathon listings using DevpostScraper interface pattern."""
    
    def __init__(self):
        """Initialize the scraper."""
        self.base_url = "https://www.eventbrite.com"
        self.search_url = f"{self.base_url}/d/online/hackathon"
        self.page_metadata = []
    
    def _extract_page_title_from_html(self, html: str) -> str:
        """Extract page title from HTML content for logging."""
        if not html:
            return "No HTML content"
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            title_elem = soup.find('title')
            if title_elem:
                title = title_elem.get_text().strip()
                return title[:100] if title else "Unknown page title"
            return "Unknown page title"
        except Exception as e:
            return f"Title extraction error: {str(e)[:50]}"
    
    def _scrape_with_retry(self, url: str, max_retries: int = 3) -> Dict[str, Any]:
        """Scrape URL with retry logic for rate limits."""
        retries = 0
        backoff_time = 2
        
        while retries < max_retries:
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                
                response = requests.get(url, headers=headers, timeout=15)
                response.raise_for_status()
                
                html_content = response.text
                html_size = len(html_content)
                page_title = self._extract_page_title_from_html(html_content)
                
                return {
                    'success': True,
                    'html': html_content,
                    'markdown': BeautifulSoup(html_content, 'html.parser').get_text(),
                    'html_size': html_size,
                    'page_title': page_title
                }
                
            except requests.exceptions.RequestException as e:
                if "429" in str(e) or "rate limit" in str(e).lower():
                    print(f"Rate limit hit for {url}. Waiting {backoff_time}s...")
                    time.sleep(backoff_time)
                    retries += 1
                    backoff_time *= 2
                else:
                    return {
                        'success': False,
                        'error': f"Request failed: {str(e)}",
                        'html': '',
                        'markdown': ''
                    }
        
        return {
            'success': False,
            'error': f"Max retries reached after {max_retries} attempts",
            'html': '',
            'markdown': ''
        }
    
    def get_hackathon_list_urls(self, max_pages: int = 5) -> List[str]:
        """Get URLs for hackathon listing pages."""
        hackathon_urls = []
        
        search_queries = [
            "hackathon",
            "coding competition",
            "programming contest",
            "tech challenge"
        ]
        
        for query in search_queries:
            search_url = f"{self.base_url}/d/online/{query.replace(' ', '-')}"
            
            print(f"🔍 Searching Eventbrite for: {query}")
            
            for page in range(1, max_pages + 1):
                if page > 1:
                    time.sleep(3)  # Rate limiting
                
                page_url = f"{search_url}/?page={page}" if page > 1 else search_url
                
                result = self._scrape_with_retry(page_url)
                
                if result['success']:
                    page_metadata = {
                        'page_number': page,
                        'url': page_url,
                        'query': query,
                        'title': result.get('page_title', 'Unknown'),
                        'html_size': result.get('html_size', 0),
                        'timestamp': time.time()
                    }
                    self.page_metadata.append(page_metadata)
                    
                    urls = self._extract_hackathon_urls_from_html(result['html'])
                    hackathon_urls.extend(urls)
                    
                    print(f"   Found {len(urls)} events on page {page} for '{query}'")
                    
                    # If no events found on this page, skip remaining pages for this query
                    if len(urls) == 0:
                        break
                else:
                    print(f"   Failed to fetch page {page}: {result.get('error')}")
                    break
        
        # Remove duplicates
        unique_urls = list(set(hackathon_urls))
        print(f"✅ Found {len(unique_urls)} unique hackathon URLs from Eventbrite")
        return unique_urls
    
    def _extract_hackathon_urls_from_html(self, html: str) -> List[str]:
        """Extract hackathon URLs from Eventbrite HTML."""
        if not html:
            return []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            urls = []
            
            # Eventbrite event links are typically in event cards
            event_selectors = [
                'a[href*="/e/"]',  # Eventbrite event URLs contain /e/
                '.event-card a',
                '.search-event-card a',
                '[data-event-id] a'
            ]
            
            for selector in event_selectors:
                links = soup.select(selector)
                for link in links:
                    href = link.get('href')
                    if href and self._is_hackathon_url(href):
                        if href.startswith('/'):
                            href = urljoin(self.base_url, href)
                        elif not href.startswith('http'):
                            continue
                        
                        # Check if event text suggests it's a hackathon
                        event_text = link.get_text().strip().lower()
                        hackathon_keywords = [
                            'hackathon', 'hack', 'coding', 'programming', 
                            'developer', 'tech challenge', 'code', 'dev'
                        ]
                        
                        if any(keyword in event_text for keyword in hackathon_keywords):
                            urls.append(href)
            
            return list(set(urls))  # Remove duplicates
            
        except Exception as e:
            print(f"Error extracting URLs from Eventbrite HTML: {e}")
            return []
    
    def _is_hackathon_url(self, url: str) -> bool:
        """Check if URL is likely a hackathon event."""
        if not url:
            return False
        
        # Eventbrite event URLs contain /e/ followed by event ID
        return '/e/' in url and 'eventbrite.com' in url
    
    def get_hackathon_details(self, url: str) -> Dict[str, Any]:
        """Get detailed information for a specific hackathon."""
        result = self._scrape_with_retry(url)
        
        if not result['success']:
            return {
                'url': url,
                'name': 'Failed to load',
                'source': 'eventbrite',
                'error': result.get('error'),
                'discovery_method': 'eventbrite_search',
                'source_reliability': 0.6,  # Medium reliability
                'data_completeness': 0.1
            }
        
        try:
            soup = BeautifulSoup(result['html'], 'html.parser')
            
            # Extract title
            title = self._extract_title(soup)
            
            # Extract basic details
            details = self._extract_basic_details(soup)
            
            # Calculate quality metrics
            quality_score = self._calculate_content_quality_score(
                result.get('html_size', 0), 
                result['html']
            )
            
            return {
                'url': url,
                'name': title,
                'source': 'eventbrite',
                'discovery_method': 'eventbrite_search',
                'quality_score': quality_score,
                'source_reliability': 0.7,  # Good reliability for Eventbrite
                'data_completeness': min(1.0, len([v for v in details.values() if v]) / 8),
                **details
            }
            
        except Exception as e:
            return {
                'url': url,
                'name': 'Parsing failed',
                'source': 'eventbrite',
                'error': str(e),
                'discovery_method': 'eventbrite_search',
                'source_reliability': 0.6,
                'data_completeness': 0.1
            }
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract event title from Eventbrite page."""
        title_selectors = [
            'h1.event-title',
            'h1[data-automation="event-title"]',
            '.event-title h1',
            'h1',
            'title'
        ]
        
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                title = element.get_text().strip()
                if len(title) > 5:
                    return title
        
        return "Unknown Event"
    
    def _extract_basic_details(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract basic event details from Eventbrite page."""
        details = {
            'short_description': None,
            'start_date': None,
            'end_date': None,
            'location': None,
            'organizer': None
        }
        
        # Extract description
        desc_selectors = [
            '.event-description',
            '.structured-content-rich-text',
            '[data-automation="event-description"]'
        ]
        
        for selector in desc_selectors:
            desc_elem = soup.select_one(selector)
            if desc_elem:
                desc_text = desc_elem.get_text().strip()
                if len(desc_text) > 20:
                    details['short_description'] = desc_text[:200] + "..." if len(desc_text) > 200 else desc_text
                    break
        
        # Extract dates from datetime elements
        datetime_elem = soup.select_one('[datetime]')
        if datetime_elem:
            datetime_str = datetime_elem.get('datetime')
            if datetime_str:
                try:
                    from datetime import datetime
                    date_obj = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
                    details['start_date'] = date_obj.strftime('%Y-%m-%d')
                    details['end_date'] = details['start_date']  # Default to same day
                except:
                    pass
        
        # Extract location
        location_selectors = [
            '.location-info__address',
            '.event-details__data',
            '[data-automation="event-location"]'
        ]
        
        for selector in location_selectors:
            location_elem = soup.select_one(selector)
            if location_elem:
                location_text = location_elem.get_text().strip()
                if location_text and location_text.lower() != 'online event':
                    details['location'] = location_text
                    break
        
        # Extract organizer
        organizer_selectors = [
            '.organizer-name',
            '.event-organizer a',
            '[data-automation="organizer-name"]'
        ]
        
        for selector in organizer_selectors:
            org_elem = soup.select_one(selector)
            if org_elem:
                org_text = org_elem.get_text().strip()
                if org_text:
                    details['organizer'] = org_text
                    break
        
        return details
    
    def _calculate_content_quality_score(self, html_size: int, html_content: str) -> float:
        """Calculate quality score based on content richness."""
        score = 0.0
        
        # Size-based scoring
        if html_size > 10000:
            score += 0.3
        elif html_size > 5000:
            score += 0.2
        elif html_size > 2000:
            score += 0.1
        
        # Content-based scoring
        if html_content:
            soup = BeautifulSoup(html_content, 'html.parser')
            text = soup.get_text().lower()
            
            # Check for hackathon-specific terms
            hackathon_terms = ['hackathon', 'coding', 'programming', 'developer', 'tech']
            score += min(0.3, sum(0.1 for term in hackathon_terms if term in text))
            
            # Check for date information
            if any(date_word in text for date_word in ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december', '2024', '2025']):
                score += 0.2
            
            # Check for location information
            if any(loc_word in text for loc_word in ['location', 'venue', 'address', 'online', 'virtual']):
                score += 0.1
        
        return min(1.0, score)

def get_hackathon_urls(limit: int = 5) -> List[Dict[str, Any]]:
    """
    Fetch hackathon URLs from Eventbrite.
    
    Args:
        limit: Maximum number of hackathons to fetch
        
    Returns:
        List of dictionaries with hackathon information
    """
    print(f"🔍 Fetching {limit} hackathons from Eventbrite...")
    
    scraper = EventbriteScraper()
    urls = scraper.get_hackathon_list_urls(max_pages=3)
    
    hackathons = []
    for i, url in enumerate(urls[:limit]):
        print(f"📄 Processing hackathon {i+1}/{min(limit, len(urls))}: {url[:80]}...")
        
        details = scraper.get_hackathon_details(url)
        hackathons.append(details)
        
        # Add small delay between requests
        if i < len(urls) - 1:
            time.sleep(2)
    
    print(f"✅ Successfully processed {len(hackathons)} hackathons from Eventbrite")
    return hackathons 