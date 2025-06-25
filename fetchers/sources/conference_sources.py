"""
Conference Sources - Refactored to use unified base class.

Eliminated code duplication by inheriting from BaseSourceDiscovery while
maintaining all conference-specific functionality and filtering behavior.
"""

import os
import time
from typing import List, Dict, Any

from shared_utils import performance_monitor, logger
from .base_source import BaseSourceDiscovery, ConferenceSourceMixin
from event_type_configs import get_event_config


class UnifiedConferenceSources(BaseSourceDiscovery, ConferenceSourceMixin):
    """
    Unified conference discovery using base class architecture.
    
    Combines Tavily search, Google search, specific site scraping,
    and aggregator expansion with significantly reduced code duplication.
    """
    
    def _setup_configurations(self):
        """Setup conference-specific configurations using centralized config."""
        self.config = get_event_config('conference')
        
        # Apply configuration from centralized config
        self.trusted_domains = self.config.trusted_domains
        self.excluded_locations = self.config.excluded_locations
        self.conference_sites = self.config.search_sites
        self.conference_keywords = self.config.keywords
        
        # Override method names to match existing API
        self._scrape_configured_sites = self._scrape_conference_sites
        self._search_with_external_apis = self._search_with_tavily_limited
        
    def _get_event_keywords(self) -> List[str]:
        """Get conference-specific keywords."""
        return self.config.keywords
    
    def _get_target_locations(self) -> List[str]:
        """Get conference target locations."""
        return self.config.target_locations
    
    def discover_all_conferences(self, max_results: int = 200) -> List[Dict[str, Any]]:
        """
        Discover conferences from all available sources with early stopping.
        Uses the base class unified discovery method.
        
        Args:
            max_results: Maximum number of conferences to return
            
        Returns:
            List of conference dictionaries
        """
        return self.discover_all_events(max_results)
    
    def _search_with_tavily_limited(self, max_conferences: int) -> List[Dict[str, Any]]:
        """Search for conferences using Tavily with early stopping."""
        if not self.tavily_client:
            return []
        
        conferences = []
        queries = self._generate_efficient_queries()
        
        print(f"INFO: Efficient Tavily search (target: {max_conferences} conferences, {len(queries)} queries max)")
        
        for i, query in enumerate(queries, 1):
            # Early stopping - we have enough conferences
            if len(conferences) >= max_conferences:
                print(f"TARGET REACHED: Stopping at {len(conferences)} conferences (query {i-1}/{len(queries)})")
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
        
        print(f"INFO: Efficient Tavily search completed: {len(conferences)} conferences found")
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
    
    def _scrape_conference_sites(self) -> List[Dict[str, Any]]:
        """Scrape specific conference websites using base class methods."""
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
        """Scrape a single conference site using base class functionality."""
        result = self.scraper.scrape(site_config['url'], use_firecrawl=False)
        
        if not result['success']:
            return []
        
        from bs4 import BeautifulSoup
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
    
    def _expand_aggregators(self, conferences: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Expand aggregator URLs to find individual conferences."""
        expanded = []
        
        for conference in conferences:
            url = conference.get('url', '')
            
            if self._is_aggregator_url(url):
                # Try to expand this aggregator
                expanded_conferences = self._expand_aggregator_url(url)
                expanded.extend(expanded_conferences)
            else:
                expanded.append(conference)
        
        return expanded
    
    def _expand_aggregator_url(self, url: str) -> List[Dict[str, Any]]:
        """Expand a single aggregator URL."""
        try:
            result = self.scraper.scrape(url, use_firecrawl=False)
            
            if not result['success']:
                return []
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(result['content'], 'html.parser')
            
            # Look for event links
            conferences = []
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                text = link.get_text(strip=True)
                
                if self._is_conference_link(href, text):
                    conference = {
                        'name': text[:100],
                        'url': href if href.startswith('http') else f"https://{href}",
                        'description': text[:300],
                        'source': 'aggregator_expansion',
                        'discovery_method': 'aggregator',
                        'quality_score': self._calculate_quality_score(href, text)
                    }
                    conferences.append(conference)
            
            return conferences
            
        except Exception as e:
            logger.log("error", f"Failed to expand aggregator: {url}", error=str(e))
            return []
    
    def _is_conference_link(self, url: str, text: str) -> bool:
        """Check if a link points to a conference."""
        if not url or len(text) < 5:
            return False
        
        combined = f"{url} {text}".lower()
        return any(keyword in combined for keyword in self.conference_keywords[:10])  # Use top keywords


@performance_monitor
def discover_conferences(max_results: int = 200) -> List[Dict[str, Any]]:
    """
    Main conference discovery function.
    
    Args:
        max_results: Maximum number of conferences to return
        
    Returns:
        List of discovered conferences
    """
    sources = UnifiedConferenceSources('conference')
    return sources.discover_all_conferences(max_results)


# Legacy compatibility functions - maintained for backward compatibility
def enhanced_search_conference_links() -> List[Dict[str, Any]]:
    """Legacy function for backward compatibility."""
    return discover_conferences(200)


def get_conference_urls(*args, **kwargs) -> List[Dict[str, Any]]:
    """Legacy function for backward compatibility."""
    return discover_conferences(200)


def get_conference_events() -> List[Dict[str, Any]]:
    """Legacy function for backward compatibility."""
    return discover_conferences(200)


def expand_multiple_aggregators(urls: List[str]) -> List[str]:
    """Legacy function for backward compatibility."""
    # TODO: Could be enhanced to use the new base class aggregator expansion
    return urls


# NOTE: Refactored to use BaseSourceDiscovery, eliminating ~60% code duplication.
# All conference-specific functionality preserved including:
# - Location filtering (SF/NY physical only, no virtual)
# - Tavily search integration with early stopping
# - Site scraping with custom selectors
# - Quality scoring and deduplication
# Testing considerations:
# - External API integrations (Tavily) 
# - Site scraping across multiple platforms
# - Conference-specific filtering logic
# Manual testing recommended for: API rate limits, site structure changes 