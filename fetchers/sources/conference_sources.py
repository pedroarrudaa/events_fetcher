"""
Unified Conference Sources - Clean, consolidated event discovery.

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


class UnifiedConferenceSources:
    """
    Unified conference discovery from all sources.
    
    Combines Tavily search, Google search, specific site scraping,
    and aggregator expansion into a single clean interface.
    """
    
    def __init__(self):
        """Initialize unified conference sources."""
        self.scraper = WebScraper()
        self.enricher = EventGPTExtractor('conference')
        self.query_generator = QueryGenerator()
        
        # Tavily client setup
        try:
            from tavily import TavilyClient
            tavily_key = os.getenv("TAVILY_API_KEY")
            self.tavily_client = TavilyClient(api_key=tavily_key) if tavily_key else None
        except ImportError:
            self.tavily_client = None
            logger.log("warning", "Tavily not available - install with: pip install tavily-python")
        
        # Configuration
        self.trusted_domains = {
            'eventbrite.com': 0.9, 'meetup.com': 0.8, 'ieee.org': 0.95,
            'acm.org': 0.95, 'oreilly.com': 0.9, 'techcrunch.com': 0.85,
            'ai4.io': 0.8, 'marktechpost.com': 0.7, 'techmeme.com': 0.75
        }
        
        self.conference_sites = [
            {
                'name': 'AI4',
                'url': 'https://ai4.io/',
                'selectors': ['div[class*="event"]', 'div[class*="conference"]', '.card']
            },
            {
                'name': 'MarkTechPost Events',
                'url': 'https://events.marktechpost.com/',
                'selectors': ['div[class*="event"]', 'article', '.post']
            },
            {
                'name': 'TechMeme Events',
                'url': 'https://www.techmeme.com/events',
                'selectors': ['div[class*="event"]', '.item', 'article']
            }
        ]
        
        self.conference_keywords = [
            'conference', 'summit', 'symposium', 'workshop', 'expo',
            'ai', 'artificial intelligence', 'machine learning', 'data science'
        ]
    
    @performance_monitor
    def discover_all_conferences(self, max_results: int = 50) -> List[Dict[str, Any]]:
        """
        Discover conferences from all available sources.
        
        Args:
            max_results: Maximum number of conferences to return
            
        Returns:
            List of conference dictionaries
        """
        logger.log("info", "Starting unified conference discovery")
        all_conferences = []
        
        # 1. Tavily search
        if self.tavily_client:
            tavily_results = self._search_with_tavily()
            all_conferences.extend(tavily_results)
            logger.log("info", f"Tavily search found {len(tavily_results)} conferences")
        
        # 2. Specific site scraping
        site_results = self._scrape_conference_sites()
        all_conferences.extend(site_results)
        logger.log("info", f"Site scraping found {len(site_results)} conferences")
        
        # 3. Expand any aggregator URLs found
        expanded_results = self._expand_aggregators(all_conferences)
        all_conferences = expanded_results
        
        # 4. Deduplicate and rank
        unique_conferences = self._deduplicate_and_rank(all_conferences)
        
        # 5. Limit results
        final_results = unique_conferences[:max_results]
        
        logger.log("info", f"Conference discovery completed", 
                  total_found=len(all_conferences), 
                  unique=len(unique_conferences), 
                  final=len(final_results))
        
        return final_results
    
    def _search_with_tavily(self) -> List[Dict[str, Any]]:
        """Search for conferences using Tavily."""
        if not self.tavily_client:
            return []
        
        conferences = []
        queries = self.query_generator.generate('conference', 2025)[:8]  # Limit queries
        
        for query in queries:
            try:
                response = self.tavily_client.search(
                    query=query,
                    search_depth="basic",
                    max_results=5,
                    include_domains=list(self.trusted_domains.keys())
                )
                
                for result in response.get('results', []):
                    conference = self._process_search_result(result, 'tavily', query)
                    if conference:
                        conferences.append(conference)
                
                time.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                logger.log("error", f"Tavily search failed for query: {query}", error=str(e))
        
        return conferences
    
    def _scrape_conference_sites(self) -> List[Dict[str, Any]]:
        """Scrape specific conference websites."""
        conferences = []
        
        for site in self.conference_sites:
            try:
                site_conferences = self._scrape_single_site(site)
                conferences.extend(site_conferences)
                time.sleep(1)  # Rate limiting
                
            except Exception as e:
                logger.log("error", f"Failed to scrape {site['name']}", error=str(e))
        
        return conferences
    
    def _scrape_single_site(self, site_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Scrape a single conference site."""
        result = self.scraper.scrape(site_config['url'], use_firecrawl=False)
        
        if not result['success']:
            return []
        
        soup = BeautifulSoup(result['content'], 'html.parser')
        conferences = []
        
        # Find event elements
        for selector in site_config['selectors']:
            elements = soup.select(selector)
            
            for element in elements:
                conference = self._extract_from_element(element, site_config)
                if conference:
                    conferences.append(conference)
        
        return conferences
    
    def _extract_from_element(self, element: BeautifulSoup, site_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract conference data from HTML element."""
        text = element.get_text(strip=True)
        
        # Filter for conference-related content
        if not any(keyword in text.lower() for keyword in self.conference_keywords):
            return None
        
        if len(text) < 10:  # Too short
            return None
        
        # Extract URL
        url = site_config['url']  # Default
        link = element.find('a', href=True)
        if link:
            href = link.get('href')
            if href:
                url = urljoin(site_config['url'], href)
        
        # Extract name (first meaningful line)
        name = text.split('\n')[0][:100] if text else 'Unknown Conference'
        
        return {
            'name': name,
            'url': url,
            'description': text[:300],
            'source': site_config['name'].lower().replace(' ', '_'),
            'discovery_method': 'site_scraping',
            'quality_score': self._calculate_quality_score(url, text)
        }
    
    def _process_search_result(self, result: Dict[str, Any], source: str, query: str) -> Optional[Dict[str, Any]]:
        """Process a search result into conference format."""
        url = result.get('url', '')
        title = result.get('title', '')
        content = result.get('content', '')
        
        if not url or not is_valid_event_url(url):
            return None
        
        # Check relevance
        combined_text = f"{title} {content}".lower()
        if not any(keyword in combined_text for keyword in self.conference_keywords):
            return None
        
        return {
            'name': title,
            'url': url,
            'description': content[:300],
            'source': source,
            'discovery_method': 'search',
            'search_query': query,
            'quality_score': self._calculate_quality_score(url, combined_text)
        }
    
    def _expand_aggregators(self, conferences: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Expand aggregator URLs to find individual conferences."""
        expanded = []
        
        for conference in conferences:
            url = conference.get('url', '')
            
            if self._is_aggregator_url(url):
                # Try to expand aggregator
                sub_conferences = self._expand_aggregator_url(url)
                if sub_conferences:
                    expanded.extend(sub_conferences)
                else:
                    expanded.append(conference)  # Keep original if expansion fails
            else:
                expanded.append(conference)
        
        return expanded
    
    def _is_aggregator_url(self, url: str) -> bool:
        """Check if URL is likely an aggregator page."""
        if not url:
            return False
        
        aggregator_patterns = [
            '/blog/', '/posts/', '/news/', '/articles/', '/events/',
            '/list', '/roundup', '/digest', '/calendar'
        ]
        
        return any(pattern in url.lower() for pattern in aggregator_patterns)
    
    def _expand_aggregator_url(self, url: str) -> List[Dict[str, Any]]:
        """Expand an aggregator URL to find individual conferences."""
        result = self.scraper.scrape(url, use_firecrawl=False)
        
        if not result['success']:
            return []
        
        soup = BeautifulSoup(result['content'], 'html.parser')
        conferences = []
        
        # Look for conference links
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            link_text = link.get_text(strip=True)
            
            if not href or len(link_text) < 5:
                continue
            
            absolute_url = urljoin(url, href)
            
            # Check if this looks like a conference
            if (is_valid_event_url(absolute_url) and 
                any(keyword in link_text.lower() for keyword in self.conference_keywords)):
                
                conferences.append({
                    'name': link_text[:100],
                    'url': absolute_url,
                    'description': f'Found via aggregator: {url}',
                    'source': 'aggregator_expansion',
                    'discovery_method': 'aggregator_expansion',
                    'quality_score': self._calculate_quality_score(absolute_url, link_text)
                })
        
        return conferences[:20]  # Limit expansion results
    
    def _calculate_quality_score(self, url: str, content: str) -> float:
        """Calculate quality score for a conference."""
        score = 0.5  # Base score
        
        # Domain reputation
        for domain, domain_score in self.trusted_domains.items():
            if domain in url.lower():
                score = max(score, domain_score)
                break
        
        # Content quality indicators
        if len(content) > 100:
            score += 0.1
        
        if any(keyword in content.lower() for keyword in ['registration', 'speakers', 'agenda']):
            score += 0.1
        
        if any(year in content for year in ['2024', '2025']):
            score += 0.1
        
        return min(score, 1.0)
    
    def _deduplicate_and_rank(self, conferences: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicates and rank by quality."""
        seen_urls = set()
        unique_conferences = []
        
        for conference in conferences:
            url = conference.get('url', '').lower().strip('/')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_conferences.append(conference)
        
        # Sort by quality score
        return sorted(unique_conferences, 
                     key=lambda x: x.get('quality_score', 0), 
                     reverse=True)


# Main discovery function
@performance_monitor
def discover_conferences(max_results: int = 50) -> List[Dict[str, Any]]:
    """
    Main function to discover conferences from all sources.
    
    Args:
        max_results: Maximum conferences to return
        
    Returns:
        List of conference dictionaries
    """
    sources = UnifiedConferenceSources()
    return sources.discover_all_conferences(max_results)


# Backward compatibility functions
def enhanced_search_conference_links() -> List[Dict[str, Any]]:
    """Legacy compatibility for tavily_discovery."""
    return discover_conferences(20)

def get_conference_urls(*args, **kwargs) -> List[Dict[str, Any]]:
    """Legacy compatibility for conference_google."""
    return discover_conferences(30)

def get_conference_events() -> List[Dict[str, Any]]:
    """Legacy compatibility for conference_sites."""
    return discover_conferences(40)

def expand_multiple_aggregators(urls: List[str]) -> List[str]:
    """Legacy compatibility for aggregator_expander."""
    sources = UnifiedConferenceSources()
    conferences = []
    
    for url in urls:
        if sources._is_aggregator_url(url):
            expanded = sources._expand_aggregator_url(url)
            conferences.extend(expanded)
        else:
            conferences.append({'url': url})
    
    return [c.get('url') for c in conferences if c.get('url')] 