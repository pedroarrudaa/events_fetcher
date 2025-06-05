"""
Logic module for Hackathon Mini - Contains all core functionality.
Simplified and self-contained implementations of scraping, enrichment, and filtering.
"""

import os
import re
import json
import time
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class HackathonMiniScraper:
    """Simplified hackathon URL scraper."""
    
    def __init__(self):
        """Initialize the scraper."""
        self.sources = {
            "devpost": self._scrape_devpost,
            "hackathon_com": self._scrape_hackathon_com,
            "eventbrite": self._scrape_eventbrite_simple
        }
        
        # Request headers
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def fetch_hackathon_urls(self, limit: int = 10) -> List[str]:
        """
        Fetch hackathon URLs from multiple sources.
        
        Args:
            limit: Maximum URLs to fetch
            
        Returns:
            List of hackathon URLs
        """
        all_urls = []
        urls_per_source = max(1, limit // len(self.sources))
        
        for source_name, source_func in self.sources.items():
            try:
                print(f"📡 Fetching from {source_name}...")
                urls = source_func(limit=urls_per_source)
                all_urls.extend(urls)
                print(f"✅ Got {len(urls)} URLs from {source_name}")
                
                # Add delay between sources
                time.sleep(2)
                
            except Exception as e:
                print(f"❌ Error with {source_name}: {e}")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in all_urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        
        return unique_urls[:limit]
    
    def _scrape_devpost(self, limit: int = 5) -> List[str]:
        """Scrape Devpost for hackathon URLs."""
        urls = []
        base_url = "https://devpost.com/hackathons"
        
        try:
            response = requests.get(base_url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find hackathon links
            hackathon_links = soup.find_all('a', href=True)
            
            for link in hackathon_links:
                href = link.get('href', '')
                if '/challenges/' in href or '/hackathons/' in href:
                    if href.startswith('/'):
                        full_url = f"https://devpost.com{href}"
                    else:
                        full_url = href
                    
                    if self._is_valid_hackathon_url(full_url):
                        urls.append(full_url)
                        if len(urls) >= limit:
                            break
            
        except Exception as e:
            print(f"Devpost scraping error: {e}")
        
        return urls
    
    def _scrape_hackathon_com(self, limit: int = 5) -> List[str]:
        """Scrape Hackathon.com for hackathon URLs."""
        urls = []
        base_url = "https://www.hackathon.com/city/null/25000/75000/online"
        
        try:
            response = requests.get(base_url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find event links (adjust selector as needed)
            event_links = soup.find_all('a', href=True)
            
            for link in event_links:
                href = link.get('href', '')
                if '/event/' in href:
                    if href.startswith('/'):
                        full_url = f"https://www.hackathon.com{href}"
                    else:
                        full_url = href
                    
                    if self._is_valid_hackathon_url(full_url):
                        urls.append(full_url)
                        if len(urls) >= limit:
                            break
            
        except Exception as e:
            print(f"Hackathon.com scraping error: {e}")
        
        return urls
    
    def _scrape_eventbrite_simple(self, limit: int = 5) -> List[str]:
        """Simple Eventbrite scraping for hackathon events."""
        urls = []
        
        # Eventbrite search for hackathons
        search_url = "https://www.eventbrite.com/d/online/hackathon/"
        
        try:
            response = requests.get(search_url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find event links
            event_links = soup.find_all('a', href=True)
            
            for link in event_links:
                href = link.get('href', '')
                if '/e/' in href and 'eventbrite.com' in href:
                    if self._is_valid_hackathon_url(href):
                        urls.append(href)
                        if len(urls) >= limit:
                            break
            
        except Exception as e:
            print(f"Eventbrite scraping error: {e}")
        
        return urls
    
    def _is_valid_hackathon_url(self, url: str) -> bool:
        """Check if URL looks like a valid hackathon."""
        if not url or len(url) < 10:
            return False
        
        # Basic URL validation
        hackathon_keywords = ['hackathon', 'hack', 'challenge', 'competition']
        url_lower = url.lower()
        
        return any(keyword in url_lower for keyword in hackathon_keywords)


class HackathonMiniEnricher:
    """Simplified GPT-based hackathon data enricher."""
    
    def __init__(self):
        """Initialize the enricher."""
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        if not self.openai_api_key:
            print("⚠️ No OpenAI API key found. Enrichment will be limited.")
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def enrich_hackathons(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Enrich hackathon URLs with structured data.
        
        Args:
            urls: List of hackathon URLs
            
        Returns:
            List of enriched hackathon data
        """
        enriched_data = []
        
        for i, url in enumerate(urls):
            try:
                print(f"🧠 Enriching {i+1}/{len(urls)}: {url[:50]}...")
                
                # Get page content
                content = self._fetch_page_content(url)
                
                if content:
                    # Extract basic data
                    basic_data = self._extract_basic_data(content, url)
                    
                    # Try GPT enrichment if API key available
                    if self.openai_api_key:
                        gpt_data = self._gpt_enrich(content, url)
                        basic_data.update(gpt_data)
                    
                    enriched_data.append(basic_data)
                    
                    # Add delay between requests
                    time.sleep(1)
                
            except Exception as e:
                print(f"❌ Error enriching {url}: {e}")
                # Add basic fallback data
                enriched_data.append({
                    "url": url,
                    "name": f"Hackathon at {url.split('/')[-1]}",
                    "source": "mini",
                    "extraction_success": False
                })
        
        return enriched_data
    
    def _fetch_page_content(self, url: str) -> Optional[str]:
        """Fetch and clean page content."""
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text content
            text_content = soup.get_text()
            
            # Clean up whitespace
            lines = (line.strip() for line in text_content.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            clean_content = '\n'.join(chunk for chunk in chunks if chunk)
            
            return clean_content[:8000]  # Limit content length
            
        except Exception as e:
            print(f"Failed to fetch content from {url}: {e}")
            return None
    
    def _extract_basic_data(self, content: str, url: str) -> Dict[str, Any]:
        """Extract basic data using regex patterns."""
        data = {
            "url": url,
            "source": "mini",
            "extraction_success": True
        }
        
        # Extract title
        title_patterns = [
            r'^([^\n]{10,100})',  # First substantial line
            r'(.*hackathon.*)',   # Line containing "hackathon"
            r'(.*challenge.*)',   # Line containing "challenge"
        ]
        
        for pattern in title_patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
            if match:
                data["name"] = match.group(1).strip()[:100]
                break
        
        if "name" not in data:
            data["name"] = f"Hackathon at {url.split('/')[-1]}"
        
        # Extract dates
        date_data = self._extract_dates(content)
        data.update(date_data)
        
        # Extract location
        location = self._extract_location(content)
        if location:
            data["location"] = location
            data["remote"] = "remote" in location.lower() or "online" in location.lower()
        
        # Extract description (first few sentences)
        sentences = content.split('.')[:3]
        data["description"] = '. '.join(sentences)[:300]
        
        return data
    
    def _extract_dates(self, content: str) -> Dict[str, Optional[str]]:
        """Extract dates from content."""
        dates = {"start_date": None, "end_date": None}
        
        # Simple date patterns
        date_patterns = [
            r'(\d{4}-\d{2}-\d{2})',  # ISO format
            r'(\w+ \d{1,2}, \d{4})', # Month Day, Year
            r'(\d{1,2}/\d{1,2}/\d{4})'  # MM/DD/YYYY
        ]
        
        found_dates = []
        for pattern in date_patterns:
            matches = re.findall(pattern, content)
            found_dates.extend(matches)
        
        if found_dates:
            dates["start_date"] = found_dates[0]
            if len(found_dates) > 1:
                dates["end_date"] = found_dates[1]
        
        return dates
    
    def _extract_location(self, content: str) -> Optional[str]:
        """Extract location from content."""
        # Look for common location patterns
        location_patterns = [
            r'(?:location|venue|address):\s*([^\n]{5,50})',
            r'(?:in|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:,\s*[A-Z]{2})?)',
            r'(San Francisco|New York|NYC|Remote|Online|Virtual)',
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _gpt_enrich(self, content: str, url: str) -> Dict[str, Any]:
        """Use GPT to extract structured data."""
        try:
            import openai
            openai.api_key = self.openai_api_key
            
            prompt = f"""
            Extract structured information from this hackathon page content:
            
            URL: {url}
            Content: {content[:2000]}...
            
            Return JSON with these fields:
            - name: Event name
            - start_date: Start date (YYYY-MM-DD format)
            - end_date: End date (YYYY-MM-DD format)
            - location: Location (city, state or "Remote")
            - description: Brief description
            - themes: List of themes/topics
            - remote: true if virtual/online
            
            Return only valid JSON, no additional text.
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.1
            )
            
            result = response.choices[0].message.content.strip()
            return json.loads(result)
            
        except Exception as e:
            print(f"GPT enrichment failed: {e}")
            return {}


class HackathonMiniFilter:
    """Simplified filtering for hackathon data."""
    
    def __init__(self):
        """Initialize the filter."""
        self.target_locations = [
            "san francisco", "sf", "bay area", "silicon valley",
            "new york", "nyc", "new york city", "manhattan",
            "remote", "online", "virtual"
        ]
    
    def filter_hackathons(self, hackathons: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter hackathons based on location and date criteria.
        
        Args:
            hackathons: List of hackathon data
            
        Returns:
            Filtered list of hackathons
        """
        filtered = []
        
        for hackathon in hackathons:
            if self._passes_filters(hackathon):
                filtered.append(hackathon)
        
        return filtered
    
    def _passes_filters(self, hackathon: Dict[str, Any]) -> bool:
        """Check if hackathon passes all filters."""
        
        # Location filter
        if not self._passes_location_filter(hackathon):
            return False
        
        # Date filter
        if not self._passes_date_filter(hackathon):
            return False
        
        # Quality filter
        if not self._passes_quality_filter(hackathon):
            return False
        
        return True
    
    def _passes_location_filter(self, hackathon: Dict[str, Any]) -> bool:
        """Check if hackathon location matches target locations."""
        location = hackathon.get('location', '').lower()
        
        if not location:
            return True  # Allow if no location specified
        
        return any(target in location for target in self.target_locations)
    
    def _passes_date_filter(self, hackathon: Dict[str, Any]) -> bool:
        """Check if hackathon date is in the future."""
        start_date = hackathon.get('start_date')
        
        if not start_date:
            return True  # Allow if no date specified
        
        try:
            # Try to parse different date formats
            for fmt in ['%Y-%m-%d', '%B %d, %Y', '%m/%d/%Y']:
                try:
                    event_date = datetime.strptime(start_date, fmt)
                    return event_date.date() >= datetime.now().date()
                except ValueError:
                    continue
            
            # If no format matches, allow the event
            return True
            
        except Exception:
            return True
    
    def _passes_quality_filter(self, hackathon: Dict[str, Any]) -> bool:
        """Basic quality checks."""
        name = hackathon.get('name', '')
        url = hackathon.get('url', '')
        
        # Must have name and URL
        if not name or not url:
            return False
        
        # Name should be substantial
        if len(name) < 5:
            return False
        
        # URL should be valid
        if not url.startswith(('http://', 'https://')):
            return False
        
        return True 