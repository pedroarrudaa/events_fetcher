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
            'lu.ma': 0.95, 'eventbrite.com': 0.9, 'meetup.com': 0.8, 
            'ieee.org': 0.95, 'acm.org': 0.95, 'oreilly.com': 0.9, 
            'techcrunch.com': 0.85, 'aiml.events': 0.85, 'techmeme.com': 0.75,
            'luma.com': 0.8, 'conference.com': 0.7, 'tech.events': 0.8
        }
        
        # Target locations - conferences must be in these areas (NO VIRTUAL/REMOTE)
        self.target_locations = [
            # San Francisco area
            'san francisco', 'sf',
            # New York area  
            'new york', 'nyc', 'manhattan', 'brooklyn', 'queens', 'bronx',
            'new york city', 'ny',
        ]
        
        # Excluded locations/terms - these will be filtered out
        self.excluded_locations = [
            'virtual', 'online', 'remote', 'worldwide', 'global', 'digital',
            'webinar', 'livestream', 'streaming', 'zoom', 'teams'
        ]
        
        self.conference_sites = [
            {
                'name': 'Eventbrite AI SF',
                'url': 'https://www.eventbrite.com/d/ca--san-francisco/artificial-intelligence/',
                'selectors': ['.event-card', '.eds-event-card', '[data-event-id]']
            },
            {
                'name': 'Meetup SF AI',
                'url': 'https://www.meetup.com/find/?keywords=artificial%20intelligence&location=San%20Francisco%2C%20CA',
                'selectors': ['.event-item', '[data-event-id]', '.search-result']
            },
            {
                'name': 'Luma AI SF',
                'url': 'https://lu.ma/discover?dates=upcoming&location=San+Francisco%2C+CA&q=AI',
                'selectors': ['.event-card', '[data-event]', '.event-item', 'article']
            },
            {
                'name': 'Luma AI NYC',
                'url': 'https://lu.ma/discover?dates=upcoming&location=New+York%2C+NY&q=AI',
                'selectors': ['.event-card', '[data-event]', '.event-item', 'article']
            },
            {
                'name': 'AI ML Events',
                'url': 'https://aiml.events/',
                'selectors': ['.event-card', '.event-item', '[data-event]', 'article']
            },
            {
                'name': 'TechMeme Events',
                'url': 'https://www.techmeme.com/events',
                'selectors': ['div[class*="event"]', '.item', 'article']
            }
        ]
        
        self.conference_keywords = [
            # Event types
            'conference', 'summit', 'symposium', 'workshop', 'expo', 'meetup', 'demo day',
            # GenAI specific terms (perfect for your calendar)
            'generative ai', 'genai', 'llm', 'large language model', 'chatgpt', 'gpt',
            'foundation models', 'transformer', 'prompt engineering', 'ai agent',
            # Broader AI terms
            'artificial intelligence', 'machine learning', 'deep learning', 'neural network',
            'ai research', 'ai safety', 'ai ethics', 'ai startup', 'ai developer',
            # Tech/startup ecosystem
            'tech', 'technology', 'startup', 'innovation', 'developer', 'founder',
            'venture capital', 'demo day', 'pitch', 'product launch'
        ]
    
    @performance_monitor
    def discover_all_conferences(self, max_results: int = 200) -> List[Dict[str, Any]]:
        """
        Discover conferences from all available sources with early stopping.
        
        Args:
            max_results: Maximum number of conferences to return (controls processing)
            
        Returns:
            List of conference dictionaries
        """
        logger.log("info", f"Starting efficient conference discovery (target: {max_results})")
        all_conferences = []
        
        # 1. Quick site scraping first (usually fast)
        if len(all_conferences) < max_results:
            site_results = self._scrape_conference_sites()
            all_conferences.extend(site_results)
            logger.log("info", f"Site scraping found {len(site_results)} conferences")
        
        # 2. Efficient Tavily search with early stopping
        if len(all_conferences) < max_results and self.tavily_client:
            remaining_needed = max_results - len(all_conferences)
            tavily_results = self._search_with_tavily_limited(remaining_needed)
            all_conferences.extend(tavily_results)
            logger.log("info", f"Tavily search found {len(tavily_results)} conferences")
        
        # 3. Expand aggregators only if needed
        if len(all_conferences) < max_results:
            expanded_results = self._expand_aggregators(all_conferences)
            all_conferences = expanded_results
        
        # 4. Deduplicate and rank
        unique_conferences = self._deduplicate_and_rank(all_conferences)
        
        # 5. Apply final limit
        final_results = unique_conferences[:max_results] if max_results else unique_conferences
        
        logger.log("info", f"Efficient discovery completed", 
                  total_found=len(all_conferences), 
                  unique=len(unique_conferences), 
                  final=len(final_results),
                  target=max_results,
                  efficiency=f"{len(final_results)}/{max_results}")
        
        return final_results
    
    def _search_with_tavily_limited(self, max_conferences: int) -> List[Dict[str, Any]]:
        """Search for conferences using Tavily with early stopping."""
        if not self.tavily_client:
            return []
        
        conferences = []
        queries = self._generate_efficient_queries()  # Use smart query generation
        
        print(f" Efficient Tavily search (target: {max_conferences} conferences, {len(queries)} queries max)")
        
        for i, query in enumerate(queries, 1):
            # Early stopping - we have enough conferences
            if len(conferences) >= max_conferences:
                print(f"🎯 Target reached! Stopping at {len(conferences)} conferences (query {i-1}/{len(queries)})")
                break
                
            try:
                print(f"  Query {i}: {query}")
                    
                response = self.tavily_client.search(
                    query=query,
                    search_depth="basic",
                    max_results=6,  # Moderate results per query
                    include_domains=list(self.trusted_domains.keys())
                )
                
                query_results = 0
                for result in response.get('results', []):
                    conference = self._process_search_result(result, 'tavily', query)
                    if conference and self._is_target_location(conference):
                        conferences.append(conference)
                        query_results += 1
                        
                        # Stop this query if we have enough
                        if len(conferences) >= max_conferences:
                            break
                
                print(f"    Found {query_results} valid conferences (total: {len(conferences)})")
                time.sleep(0.4)  # Rate limiting
                
            except Exception as e:
                logger.log("error", f"Tavily search failed for query: {query}", error=str(e))
        
        print(f" Efficient Tavily search completed: {len(conferences)} conferences found")
        return conferences
    
    def _generate_efficient_queries(self) -> List[str]:
        """Generate a smaller set of high-quality queries."""
        # Start with the most effective queries based on our debug results
        core_queries = [
            # Generative AI focused searches (perfect for your calendar)
            '"generative AI conference" San Francisco 2025',
            '"LLM conference" San Francisco 2025',
            '"ChatGPT conference" Bay Area 2025',
            '"AI startup" conference San Francisco 2025',
            '"foundation models" conference SF 2025',
            
            # Platform-specific searches for GenAI
            'eventbrite.com "generative AI" San Francisco 2025',
            'eventbrite.com "LLM" Bay Area 2025',
            'eventbrite.com "AI developer" San Francisco 2025',
            'meetup.com "generative AI" San Francisco',
            'lu.ma "AI conference" San Francisco 2025',
            'lu.ma "generative AI" New York 2025',
            'lu.ma "LLM meetup" Bay Area 2025',
            
            # Company/brand specific (high-value for GenAI calendar)
            'OpenAI DevDay 2025 San Francisco',
            'Anthropic conference 2025',
            'Google AI conference San Francisco 2025',
            'Microsoft AI conference Bay Area 2025',
            'Meta AI conference Silicon Valley 2025',
            'NVIDIA AI conference 2025',
            
            # Developer/researcher focused
            '"AI research conference" Stanford 2025',
            '"AI developer conference" San Francisco 2025',
            '"prompt engineering conference" Bay Area 2025',
            '"AI safety conference" Silicon Valley 2025',
            
            # Startup ecosystem (relevant for GenAI SF community)
            'AI startup demo day San Francisco 2025',
            'YCombinator AI demo day 2025',
            'TechCrunch AI Disrupt 2025'
        ]
        
        return core_queries
    
    def _is_target_location(self, conference: Dict[str, Any]) -> bool:
        """Check if conference is in target locations (SF/NY PHYSICAL ONLY)."""
        # Check in title, description, and any location field
        text_to_check = ' '.join([
            conference.get('name', '').lower(),
            conference.get('description', '').lower(),
            conference.get('location', '').lower(),
            conference.get('url', '').lower()
        ])
        
        # First, exclude any virtual/remote conferences
        for excluded in self.excluded_locations:
            if excluded in text_to_check:
                return False
        
        # Then, check if it mentions any target location
        for location in self.target_locations:
            if location in text_to_check:
                return True
        
        # If no location is found, exclude it (we only want explicitly located conferences)
        return False
    
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
def discover_conferences(max_results: int = 200) -> List[Dict[str, Any]]:
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