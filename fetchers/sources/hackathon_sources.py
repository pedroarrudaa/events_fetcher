"""
Unified Hackathon Sources - Consolidated hackathon discovery.

"""

import os
import re
import time
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup

from shared_utils import (
    WebScraper, EventGPTExtractor, QueryGenerator, 
    performance_monitor, is_valid_event_url, logger
)


class UnifiedHackathonSources:
    """
    Unified hackathon discovery from all sources.
    
    Combines Devpost, Eventbrite, MLH, Hackathon.com, and HackerEarth
    into a single clean interface.
    """
    
    def __init__(self):
        """Initialize unified hackathon sources."""
        self.scraper = WebScraper()
        self.enricher = EventGPTExtractor('hackathon')
        self.query_generator = QueryGenerator()
        
        # Source configurations
        self.sources = [
            {
                'name': 'Devpost',
                'base_url': 'https://devpost.com',
                'search_urls': ['https://devpost.com/hackathons'],
                'url_patterns': ['/hackathons/'],
                'keywords': ['hackathon', 'hack', 'challenge', 'contest'],
                'max_pages': 5,
                'reliability': 0.9
            },
            {
                'name': 'MLH',
                'base_url': 'https://mlh.io',
                'search_urls': ['https://mlh.io/seasons/2025/events'],
                'url_patterns': ['/events/', '/event/'],
                'keywords': ['hackathon', 'hack', 'mlh'],
                'max_pages': 1,
                'reliability': 0.95
            },
            {
                'name': 'Eventbrite',
                'base_url': 'https://www.eventbrite.com',
                'search_urls': [
                    'https://www.eventbrite.com/d/online/hackathon',
                    'https://www.eventbrite.com/d/online/hack',
                    'https://www.eventbrite.com/d/online/coding-challenge'
                ],
                'url_patterns': ['/e/'],
                'keywords': ['hackathon', 'hack', 'coding', 'programming'],
                'max_pages': 3,
                'reliability': 0.7
            },
            {
                'name': 'HackerEarth',
                'base_url': 'https://www.hackerearth.com',
                'search_urls': [
                    'https://www.hackerearth.com/challenges/hackathon/',
                    'https://www.hackerearth.com/challenges/'
                ],
                'url_patterns': ['/challenges/', '/challenge/'],
                'keywords': ['hackathon', 'challenge', 'coding', 'programming'],
                'max_pages': 3,
                'reliability': 0.8
            },
            {
                'name': 'Hackathon.com',
                'base_url': 'https://www.hackathon.com',
                'search_urls': ['https://www.hackathon.com/events'],
                'url_patterns': ['/events/'],
                'keywords': ['hackathon', 'event', 'challenge'],
                'max_pages': 3,
                'reliability': 0.6
            }
        ]
        
        self.hackathon_keywords = [
            'hackathon', 'hack', 'coding challenge', 'programming contest',
            'developer challenge', 'coding competition', 'tech challenge'
        ]
    
    @performance_monitor
    def discover_all_hackathons(self, max_results: int = 60) -> List[Dict[str, Any]]:
        """
        Discover hackathons from all available sources.
        
        Args:
            max_results: Maximum number of hackathons to return
            
        Returns:
            List of hackathon dictionaries
        """
        logger.log("info", "Starting unified hackathon discovery")
        all_hackathons = []
        
        for source_config in self.sources:
            try:
                source_hackathons = self._scrape_source(source_config)
                all_hackathons.extend(source_hackathons)
                logger.log("info", f"{source_config['name']} found {len(source_hackathons)} hackathons")
                
                # Rate limiting between sources
                time.sleep(2)
                
            except Exception as e:
                logger.log("error", f"Failed to scrape {source_config['name']}", error=str(e))
        
        # Deduplicate and rank
        unique_hackathons = self._deduplicate_and_rank(all_hackathons)
        
        # Limit results
        final_results = unique_hackathons[:max_results]
        
        logger.log("info", f"Hackathon discovery completed", 
                  total_found=len(all_hackathons), 
                  unique=len(unique_hackathons), 
                  final=len(final_results))
        
        return final_results
    
    def _scrape_source(self, source_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Scrape a single hackathon source."""
        hackathons = []
        source_name = source_config['name']
        
        logger.log("info", f"Scraping {source_name}")
        
        for search_url in source_config['search_urls']:
            try:
                # Handle pagination for sources that support it
                for page in range(1, source_config['max_pages'] + 1):
                    page_url = self._build_page_url(search_url, page)
                    
                    result = self.scraper.scrape(page_url, use_firecrawl=False)
                    
                    if not result['success']:
                        logger.log("warning", f"Failed to scrape {source_name} page {page}", 
                                 error=result.get('error'))
                        break
                    
                    # Extract URLs from page
                    page_hackathons = self._extract_hackathons_from_page(
                        result['content'], source_config)
                    
                    if not page_hackathons:
                        break  # No more results
                    
                    hackathons.extend(page_hackathons)
                    
                    # Rate limiting between pages
                    if page < source_config['max_pages']:
                        time.sleep(1)
                
            except Exception as e:
                logger.log("error", f"Error scraping {search_url}", error=str(e))
        
        return hackathons
    
    def _build_page_url(self, base_url: str, page: int) -> str:
        """Build paginated URL."""
        if page == 1:
            return base_url
        
        # Different sources use different pagination patterns
        if 'devpost.com' in base_url:
            return f"{base_url}?page={page}"
        elif 'eventbrite.com' in base_url:
            return f"{base_url}?page={page}"
        else:
            return base_url  # Many sources don't have pagination
    
    def _extract_hackathons_from_page(self, content: str, source_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract hackathon data from a page."""
        try:
            soup = BeautifulSoup(content, 'html.parser')
            hackathons = []
            
            # Find all links
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                link_text = link.get_text(strip=True)
                
                if not href or len(link_text) < 5:
                    continue
                
                # Convert relative URLs to absolute
                absolute_url = urljoin(source_config['base_url'], href)
                
                # Check if this looks like a hackathon
                if self._is_hackathon_url(absolute_url, source_config, link_text):
                    hackathon = {
                        'name': self._clean_hackathon_name(link_text),
                        'url': absolute_url,
                        'description': self._extract_description(link),
                        'source': source_config['name'].lower(),
                        'discovery_method': 'source_scraping',
                        'quality_score': self._calculate_quality_score(
                            absolute_url, link_text, source_config)
                    }
                    hackathons.append(hackathon)
            
            return hackathons[:20]  # Limit per page
            
        except Exception as e:
            logger.log("error", f"Error extracting hackathons from page", error=str(e))
            return []
    
    def _is_hackathon_url(self, url: str, source_config: Dict[str, Any], link_text: str) -> bool:
        """Check if URL looks like a hackathon."""
        if not url or not is_valid_event_url(url):
            return False
        
        # Check URL patterns for this source
        url_lower = url.lower()
        if not any(pattern in url_lower for pattern in source_config['url_patterns']):
            return False
        
        # Check for hackathon keywords in URL or text
        combined_text = f"{url} {link_text}".lower()
        return any(keyword in combined_text for keyword in self.hackathon_keywords)
    
    def _clean_hackathon_name(self, raw_name: str) -> str:
        """Clean and format hackathon name."""
        if not raw_name:
            return 'Unknown Hackathon'
        
        # Remove extra whitespace and truncate
        cleaned = re.sub(r'\s+', ' ', raw_name.strip())
        return cleaned[:100] if len(cleaned) > 100 else cleaned
    
    def _extract_description(self, link_element) -> str:
        """Extract description from link context."""
        try:
            # Try to find description in surrounding elements
            parent = link_element.parent
            if parent:
                # Look for description in nearby elements
                for sibling in parent.find_all(['p', 'div', 'span']):
                    text = sibling.get_text(strip=True)
                    if len(text) > 20 and len(text) < 300:
                        return text
            
            return ''
        except:
            return ''
    
    def _calculate_quality_score(self, url: str, text: str, source_config: Dict[str, Any]) -> float:
        """Calculate quality score for a hackathon."""
        score = source_config['reliability']  # Base score from source reliability
        
        # Content quality indicators
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['2024', '2025']):
            score += 0.1
        
        if any(word in text_lower for word in ['prize', 'award', 'winner']):
            score += 0.05
        
        if any(word in text_lower for word in ['virtual', 'online', 'remote']):
            score += 0.05
        
        if len(text) > 30:  # Detailed name/description
            score += 0.05
        
        return min(score, 1.0)
    
    def _deduplicate_and_rank(self, hackathons: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicates and rank by quality."""
        seen_urls = set()
        unique_hackathons = []
        
        for hackathon in hackathons:
            url = hackathon.get('url', '').lower().strip('/')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_hackathons.append(hackathon)
        
        # Sort by quality score
        return sorted(unique_hackathons, 
                     key=lambda x: x.get('quality_score', 0), 
                     reverse=True)


# Main discovery function
@performance_monitor
def discover_hackathons(max_results: int = 60) -> List[Dict[str, Any]]:
    """
    Main function to discover hackathons from all sources.
    
    Args:
        max_results: Maximum hackathons to return
        
    Returns:
        List of hackathon dictionaries
    """
    sources = UnifiedHackathonSources()
    return sources.discover_all_hackathons(max_results)


# Backward compatibility functions
def get_hackathon_urls() -> List[Dict[str, Any]]:
    """Legacy compatibility for all sources."""
    return discover_hackathons(50)


# Individual source compatibility functions
def get_devpost_hackathons() -> List[Dict[str, Any]]:
    """Legacy compatibility for devpost.py."""
    hackathons = discover_hackathons(60)
    return [h for h in hackathons if h.get('source') == 'devpost']

def get_eventbrite_hackathons() -> List[Dict[str, Any]]:
    """Legacy compatibility for eventbrite.py."""
    hackathons = discover_hackathons(60)
    return [h for h in hackathons if h.get('source') == 'eventbrite']

def get_mlh_hackathons() -> List[Dict[str, Any]]:
    """Legacy compatibility for mlh.py."""
    hackathons = discover_hackathons(60)
    return [h for h in hackathons if h.get('source') == 'mlh']

def get_hackathon_com_hackathons() -> List[Dict[str, Any]]:
    """Legacy compatibility for hackathon_com.py."""
    hackathons = discover_hackathons(60)
    return [h for h in hackathons if h.get('source') == 'hackathon.com']

def get_hackerearth_hackathons() -> List[Dict[str, Any]]:
    """Legacy compatibility for hackerearth.py."""
    hackathons = discover_hackathons(60)
    return [h for h in hackathons if h.get('source') == 'hackerearth'] 