"""
Logic module for Conference Mini - Contains all core functionality.
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
from openai import OpenAI

# Load environment variables
load_dotenv()

class ConferenceMiniScraper:
    """Simplified conference URL scraper using multiple methods."""
    
    def __init__(self):
        """Initialize the scraper."""
        self.search_queries = [
            "AI conference San Francisco 2025",
            "Machine Learning conference New York 2025",
            "AI summit virtual 2025",
            "Deep Learning conference 2025",
            "Computer Vision conference 2025",
            "NLP conference 2025 remote",
            "Data Science conference San Francisco 2025",
            "MLOps conference New York 2025",
            "site:eventbrite.com AI conference 2025",
            "site:meetup.com machine learning conference 2025"
        ]
        
        # Request headers
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Initialize Tavily client if API key available
        self.tavily_client = None
        tavily_key = os.getenv('TAVILY_API_KEY')
        if tavily_key:
            try:
                from tavily import TavilyClient
                self.tavily_client = TavilyClient(api_key=tavily_key)
                print("✅ Tavily search enabled")
            except ImportError:
                print("⚠️ Tavily not available, using fallback methods")
    
    def fetch_conference_urls(self, limit: int = 10) -> List[str]:
        """
        Fetch conference URLs using available methods.
        
        Args:
            limit: Maximum URLs to fetch
            
        Returns:
            List of conference URLs
        """
        all_urls = []
        
        # Method 1: Tavily search (if available)
        if self.tavily_client:
            print("📡 Using Tavily search...")
            tavily_urls = self._search_with_tavily(limit=limit//2)
            all_urls.extend(tavily_urls)
        
        # Method 2: Manual conference site scraping
        print("📡 Scraping known conference sites...")
        manual_urls = self._scrape_known_sites(limit=limit//2)
        all_urls.extend(manual_urls)
        
        # Method 3: Simple Google search simulation (basic web scraping)
        if len(all_urls) < limit:
            print("📡 Using basic web search...")
            basic_urls = self._basic_web_search(limit=limit-len(all_urls))
            all_urls.extend(basic_urls)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in all_urls:
            if url not in seen and self._is_valid_conference_url(url):
                seen.add(url)
                unique_urls.append(url)
        
        return unique_urls[:limit]
    
    def _search_with_tavily(self, limit: int = 5) -> List[str]:
        """Search for conferences using Tavily API."""
        urls = []
        
        for query in self.search_queries[:3]:  # Limit queries to save credits
            try:
                print(f"🔍 Searching: {query}")
                response = self.tavily_client.search(
                    query=query,
                    search_depth="basic",
                    max_results=2
                )
                
                for result in response.get('results', []):
                    url = result.get('url', '')
                    if url and self._is_valid_conference_url(url):
                        urls.append(url)
                        if len(urls) >= limit:
                            break
                
                time.sleep(1)  # Rate limiting
                
                if len(urls) >= limit:
                    break
                    
            except Exception as e:
                print(f"❌ Tavily search error for '{query}': {e}")
                continue
        
        return urls
    
    def _scrape_known_sites(self, limit: int = 5) -> List[str]:
        """Scrape known conference listing sites."""
        urls = []
        
        # Known conference listing sites
        sites = [
            "https://www.eventbrite.com/d/online/ai-conference/",
            "https://www.conf-finder.com/",
            "https://www.allconferences.com/"
        ]
        
        for site in sites:
            try:
                print(f"🌐 Scraping: {site}")
                response = requests.get(site, headers=self.headers, timeout=30)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find links that look like conference pages
                links = soup.find_all('a', href=True)
                
                for link in links:
                    href = link.get('href', '')
                    if href.startswith('/'):
                        href = f"{site.rstrip('/')}{href}"
                    
                    if self._is_valid_conference_url(href):
                        urls.append(href)
                        if len(urls) >= limit:
                            break
                
                time.sleep(2)  # Be respectful
                
                if len(urls) >= limit:
                    break
                    
            except Exception as e:
                print(f"❌ Error scraping {site}: {e}")
                continue
        
        return urls
    
    def _basic_web_search(self, limit: int = 5) -> List[str]:
        """Basic web search simulation using direct site searches."""
        urls = []
        
        # Hardcoded high-quality conference URLs for fallback
        fallback_urls = [
            "https://www.nvidia.com/gtc/",
            "https://openai.com/events/",
            "https://events.google.com/io/",
            "https://developer.apple.com/wwdc/",
            "https://www.microsoft.com/en-us/build",
            "https://reinvent.awsevents.com/",
            "https://connect.facebook.com/",
            "https://www.icml.cc/",
            "https://nips.cc/",
            "https://iclr.cc/"
        ]
        
        # Return a subset of fallback URLs
        return fallback_urls[:limit]
    
    def _is_valid_conference_url(self, url: str) -> bool:
        """Check if URL looks like a valid conference."""
        if not url or len(url) < 10:
            return False
        
        # Basic URL validation
        conference_keywords = [
            'conference', 'summit', 'symposium', 'workshop', 'event',
            'ai', 'ml', 'machine-learning', 'artificial-intelligence',
            'tech', 'gtc', 'wwdc', 'build', 'reinvent', 'connect',
            'icml', 'nips', 'iclr', 'aaai'
        ]
        
        url_lower = url.lower()
        return any(keyword in url_lower for keyword in conference_keywords)


class ConferenceMiniEnricher:
    """Simplified GPT-based conference data enricher."""
    
    def __init__(self):
        """Initialize the enricher."""
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.openai_client = None
        if self.openai_api_key:
            self.openai_client = OpenAI(api_key=self.openai_api_key)
        else:
            print("⚠️ No OpenAI API key found. Enrichment will be limited.")
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def enrich_conferences(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Enrich conference URLs with structured data.
        
        Args:
            urls: List of conference URLs
            
        Returns:
            List of enriched conference data
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
                    "name": f"Conference at {url.split('/')[-1]}",
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
            r'(.*conference.*)',   # Line containing "conference"
            r'(.*summit.*)',       # Line containing "summit"
            r'(.*workshop.*)',     # Line containing "workshop"
        ]
        
        for pattern in title_patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
            if match:
                data["name"] = match.group(1).strip()[:100]
                break
        
        if "name" not in data:
            data["name"] = f"Conference at {url.split('/')[-1]}"
        
        # Extract dates
        date_data = self._extract_dates(content)
        data.update(date_data)
        
        # Extract location
        location = self._extract_location(content)
        if location:
            data["location"] = location
            data["remote"] = "remote" in location.lower() or "online" in location.lower() or "virtual" in location.lower()
        
        # Extract themes
        themes = self._extract_themes(content)
        if themes:
            data["themes"] = themes
        
        # Extract description (first few sentences)
        sentences = content.split('.')[:3]
        data["description"] = '. '.join(sentences)[:300]
        
        # Extract registration info
        reg_info = self._extract_registration_info(content, url)
        data.update(reg_info)
        
        return data
    
    def _extract_dates(self, content: str) -> Dict[str, Optional[str]]:
        """Extract dates from content."""
        dates = {"start_date": None, "end_date": None, "registration_deadline": None}
        
        # Date patterns
        date_patterns = [
            r'(\d{4}-\d{2}-\d{2})',  # ISO format
            r'(\w+ \d{1,2}, \d{4})', # Month Day, Year
            r'(\d{1,2}/\d{1,2}/\d{4})',  # MM/DD/YYYY
            r'(\w+ \d{1,2}-\d{1,2}, \d{4})'  # Month Day-Day, Year
        ]
        
        found_dates = []
        for pattern in date_patterns:
            matches = re.findall(pattern, content)
            found_dates.extend(matches)
        
        # Filter for future dates and reasonable years
        current_year = datetime.now().year
        valid_dates = []
        for date_str in found_dates:
            if any(str(year) in date_str for year in range(current_year, current_year + 3)):
                valid_dates.append(date_str)
        
        if valid_dates:
            dates["start_date"] = valid_dates[0]
            if len(valid_dates) > 1:
                dates["end_date"] = valid_dates[1]
        
        return dates
    
    def _extract_location(self, content: str) -> Optional[str]:
        """Extract location from content."""
        # Look for common location patterns
        location_patterns = [
            r'(?:location|venue|address):\s*([^\n]{5,50})',
            r'(?:in|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:,\s*[A-Z]{2})?)',
            r'(San Francisco|New York|NYC|Boston|Seattle|Austin|Denver|Remote|Online|Virtual)',
            r'(California|CA|New York|NY|Texas|TX|Washington|WA|Colorado|CO)',
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_themes(self, content: str) -> List[str]:
        """Extract conference themes/topics."""
        themes = []
        
        # AI/ML related themes
        theme_keywords = [
            "artificial intelligence", "machine learning", "deep learning",
            "computer vision", "natural language processing", "nlp",
            "robotics", "data science", "mlops", "ai ethics",
            "generative ai", "llm", "transformer", "neural networks"
        ]
        
        content_lower = content.lower()
        for keyword in theme_keywords:
            if keyword in content_lower:
                themes.append(keyword.title())
        
        return themes[:5]  # Limit to 5 themes
    
    def _extract_registration_info(self, content: str, url: str) -> Dict[str, Optional[str]]:
        """Extract registration information."""
        info = {"registration_url": None, "registration_deadline": None}
        
        # Look for registration URLs
        reg_patterns = [
            r'(https?://[^\s]+register[^\s]*)',
            r'(https?://[^\s]+registration[^\s]*)',
            r'(https?://[^\s]+signup[^\s]*)'
        ]
        
        for pattern in reg_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                info["registration_url"] = match.group(1).rstrip('.,;')
                break
        
        # If no specific registration URL, use the main URL
        if not info["registration_url"]:
            info["registration_url"] = url
        
        # Look for registration deadlines
        deadline_patterns = [
            r'(?:registration|submit|deadline|due).*?(?:by|until|before)\s+(\w+\s+\d+,?\s+\d{4})',
            r'(?:deadline|due)\s*:?\s*(\w+\s+\d+,?\s+\d{4})'
        ]
        
        for pattern in deadline_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                info["registration_deadline"] = match.group(1)
                break
        
        return info
    
    def _gpt_enrich(self, content: str, url: str) -> Dict[str, Any]:
        """Use GPT to extract structured data."""
        if not self.openai_client:
            print("❌ OpenAI client not available, skipping GPT enrichment.")
            return {}
            
        try:
            prompt = f"""
Extract structured information from this conference page content:

URL: {url}
Content: {content[:2000]}...

Return JSON with these fields:
- name: Conference name (max 100 chars)
- start_date: Start date (YYYY-MM-DD), or null
- end_date: End date (YYYY-MM-DD), or null
- location: City, State (e.g., "San Francisco, CA") or "Remote" (max 50 chars)
- description: Brief summary (max 300 chars)
- themes: List of relevant keywords (e.g., ["AI", "Machine Learning"]) (max 5 themes, 30 chars per theme)
- registration_url: URL for registration, or null
- registration_deadline: Deadline (YYYY-MM-DD), or null

Example:
{{
  "name": "Awesome AI Conference 2025",
  "start_date": "2025-03-15",
  "end_date": "2025-03-17",
  "location": "San Francisco, CA",
  "description": "Join us for the leading AI conference...",
  "themes": ["AI", "Machine Learning", "Deep Learning"],
  "registration_url": "https://example.com/register",
  "registration_deadline": "2025-02-28"
}}
"""
            
            completion = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert at extracting structured data from web content and returning JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=500 
            )
            
            response_content = completion.choices[0].message.content
            if response_content:
                if response_content.strip().startswith("```json"):
                    response_content = response_content.strip()[7:-3].strip()
                elif response_content.strip().startswith("```"):
                    response_content = response_content.strip()[3:-3].strip()

                return json.loads(response_content)
            else:
                print("❌ GPT returned empty response.")
                return {}

        except Exception as e:
            print(f"❌ GPT enrichment failed: {e}")
            return {}


class ConferenceMiniFilter:
    """Simplified filtering for conference data."""
    
    def __init__(self):
        """Initialize the filter."""
        self.target_locations = [
            "san francisco", "sf", "bay area", "silicon valley",
            "new york", "nyc", "new york city", "manhattan",
            "boston", "seattle", "austin", "denver",
            "remote", "online", "virtual"
        ]
        
        self.ai_keywords = [
            "artificial intelligence", "machine learning", "deep learning",
            "computer vision", "nlp", "natural language processing",
            "ai", "ml", "data science", "robotics", "mlops"
        ]
    
    def filter_conferences(self, conferences: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter conferences based on location, date, and relevance criteria.
        
        Args:
            conferences: List of conference data
            
        Returns:
            Filtered list of conferences
        """
        filtered = []
        
        for conference in conferences:
            if self._passes_filters(conference):
                filtered.append(conference)
        
        return filtered
    
    def _passes_filters(self, conference: Dict[str, Any]) -> bool:
        """Check if conference passes all filters."""
        
        # Location filter
        if not self._passes_location_filter(conference):
            return False
        
        # Date filter
        if not self._passes_date_filter(conference):
            return False
        
        # Relevance filter (AI/ML related)
        if not self._passes_relevance_filter(conference):
            return False
        
        # Quality filter
        if not self._passes_quality_filter(conference):
            return False
        
        return True
    
    def _passes_location_filter(self, conference: Dict[str, Any]) -> bool:
        """Check if conference location matches target locations."""
        location = conference.get('location', '').lower()
        
        if not location:
            return True  # Allow if no location specified
        
        return any(target in location for target in self.target_locations)
    
    def _passes_date_filter(self, conference: Dict[str, Any]) -> bool:
        """Check if conference date is in the future."""
        start_date = conference.get('start_date')
        
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
    
    def _passes_relevance_filter(self, conference: Dict[str, Any]) -> bool:
        """Check if conference is AI/ML related."""
        # Check name, description, and themes
        text_to_check = ' '.join([
            conference.get('name', ''),
            conference.get('description', ''),
            ' '.join(conference.get('themes', []))
        ]).lower()
        
        # Check URL as well
        url = conference.get('url', '').lower()
        text_to_check += ' ' + url
        
        return any(keyword in text_to_check for keyword in self.ai_keywords)
    
    def _passes_quality_filter(self, conference: Dict[str, Any]) -> bool:
        """Basic quality checks."""
        name = conference.get('name', '')
        url = conference.get('url', '')
        
        # Must have name and URL
        if not name or not url:
            return False
        
        # Name should be substantial
        if len(name) < 5:
            return False
        
        # URL should be valid
        if not url.startswith(('http://', 'https://')):
            return False
        
        # Check for spam patterns
        spam_patterns = ['win', 'prize', 'free money', 'click here']
        name_lower = name.lower()
        if any(pattern in name_lower for pattern in spam_patterns):
            return False
        
        return True 