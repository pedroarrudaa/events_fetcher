"""
Base Source Discovery - Unified foundation for conference and hackathon sources.

This module provides a common base class that consolidates shared functionality
between conference and hackathon discovery systems, eliminating code duplication
while maintaining event-type-specific configurations.
"""

import os
import re
import time
import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup

from shared_utils import (
    WebScraper, EventGPTExtractor, QueryGenerator, 
    performance_monitor, is_valid_event_url, logger
)


class BaseSourceDiscovery(ABC):
    """
    Abstract base class for event source discovery.
    
    Provides common functionality for both conference and hackathon sources
    while allowing event-type-specific implementations through abstract methods.
    """
    
    def __init__(self, event_type: str):
        """
        Initialize base source discovery.
        
        Args:
            event_type: Type of events to discover ('conference' or 'hackathon')
        """
        self.event_type = event_type
        self.scraper = WebScraper()
        self.enricher = EventGPTExtractor(event_type)
        self.query_generator = QueryGenerator()
        
        # Initialize event-type-specific configurations
        self._setup_configurations()
        
        # Initialize external API clients if needed
        self._setup_external_clients()
    
    @abstractmethod
    def _setup_configurations(self):
        """Setup event-type-specific configurations. Must be implemented by subclasses."""
        pass
    
    @abstractmethod  
    def _get_event_keywords(self) -> List[str]:
        """Get keywords specific to the event type. Must be implemented by subclasses."""
        pass
    
    @abstractmethod
    def _get_target_locations(self) -> List[str]:
        """Get target locations for the event type. Must be implemented by subclasses."""
        pass
    
    def _setup_external_clients(self):
        """Setup external API clients (Tavily, etc.)."""
        try:
            from tavily import TavilyClient
            tavily_key = os.getenv("TAVILY_API_KEY")
            self.tavily_client = TavilyClient(api_key=tavily_key) if tavily_key else None
        except ImportError:
            self.tavily_client = None
            logger.log("warning", "Tavily not available - install with: pip install tavily-python")
    
    @performance_monitor
    def discover_all_events(self, max_results: int = 200) -> List[Dict[str, Any]]:
        """
        Main discovery method - discovers events from all configured sources.
        
        Args:
            max_results: Maximum number of events to return
            
        Returns:
            List of discovered event dictionaries
        """
        logger.log("info", f"Starting unified {self.event_type} discovery (target: {max_results})")
        all_events = []
        
        # 1. Search-based discovery (if available)
        if hasattr(self, '_search_with_external_apis') and len(all_events) < max_results:
            remaining_needed = max_results - len(all_events)
            search_results = self._search_with_external_apis(remaining_needed)
            all_events.extend(search_results)
            logger.log("info", f"Search APIs found {len(search_results)} {self.event_type}s")
        
        # 2. Site scraping (if configured)
        if hasattr(self, '_scrape_configured_sites') and len(all_events) < max_results:
            site_results = self._scrape_configured_sites()
            all_events.extend(site_results)
            logger.log("info", f"Site scraping found {len(site_results)} {self.event_type}s")
        
        # 3. API sources (if configured)
        if hasattr(self, '_fetch_from_api_sources') and len(all_events) < max_results:
            api_results = self._fetch_from_api_sources()
            all_events.extend(api_results)
            logger.log("info", f"API sources found {len(api_results)} {self.event_type}s")
        
        # 4. Aggregator expansion (if configured)
        if hasattr(self, '_expand_aggregators') and len(all_events) < max_results:
            expanded_results = self._expand_aggregators(all_events)
            all_events = expanded_results
        
        # 5. Deduplicate and rank
        unique_events = self._deduplicate_and_rank(all_events)
        
        # 6. Apply final limit
        final_results = unique_events[:max_results] if max_results else unique_events
        
        logger.log("info", f"Discovery completed", 
                  event_type=self.event_type,
                  total_found=len(all_events), 
                  unique=len(unique_events), 
                  final=len(final_results),
                  target=max_results)
        
        return final_results
    
    def _is_target_location(self, event: Dict[str, Any]) -> bool:
        """
        Check if event is in target locations.
        Can be overridden by subclasses for specific location logic.
        """
        text_to_check = ' '.join([
            event.get('name', '').lower(),
            event.get('description', '').lower(),
            event.get('location', '').lower(),
            event.get('url', '').lower()
        ])
        
        # Check for excluded locations first (if defined)
        if hasattr(self, 'excluded_locations'):
            for excluded in self.excluded_locations:
                if excluded in text_to_check:
                    return False
        
        # Check for target locations
        target_locations = self._get_target_locations()
        for location in target_locations:
            if location in text_to_check:
                return True
        
        return False
    
    def _process_search_result(self, result: Dict[str, Any], source: str, query: str) -> Optional[Dict[str, Any]]:
        """Process a search result into standardized event format."""
        url = result.get('url', '')
        title = result.get('title', '')
        content = result.get('content', '')
        
        if not url or not is_valid_event_url(url):
            return None
        
        # Check relevance using event-specific keywords
        combined_text = f"{title} {content}".lower()
        event_keywords = self._get_event_keywords()
        if not any(keyword in combined_text for keyword in event_keywords):
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
    
    def _calculate_quality_score(self, url: str, content: str) -> float:
        """
        Calculate quality score for an event.
        Can be enhanced by subclasses for event-specific scoring.
        """
        score = 0.5  # Base score
        
        # URL quality
        if hasattr(self, 'trusted_domains'):
            domain = urlparse(url).netloc.lower()
            for trusted_domain, domain_score in self.trusted_domains.items():
                if trusted_domain in domain:
                    score = max(score, domain_score)
                    break
        
        # Content quality indicators
        content_lower = content.lower()
        event_keywords = self._get_event_keywords()
        
        # Keyword relevance
        keyword_matches = sum(1 for keyword in event_keywords if keyword in content_lower)
        score += min(keyword_matches * 0.1, 0.3)
        
        # Content length (more content usually means better quality)
        if len(content) > 500:
            score += 0.1
        elif len(content) > 200:
            score += 0.05
        
        # Date information presence
        date_indicators = ['date', 'when', '2025', '2026', 'january', 'february', 'march']
        if any(indicator in content_lower for indicator in date_indicators):
            score += 0.1
        
        # Location information presence
        location_indicators = ['where', 'location', 'venue', 'address']
        if any(indicator in content_lower for indicator in location_indicators):
            score += 0.1
        
        return min(score, 1.0)  # Cap at 1.0
    
    def _deduplicate_and_rank(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate events and rank by quality score."""
        # Deduplicate by URL
        unique_events = []
        seen_urls = set()
        
        for event in events:
            url = event.get('url', '').strip().lower()
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_events.append(event)
        
        # Sort by quality score (descending)
        unique_events.sort(key=lambda x: x.get('quality_score', 0), reverse=True)
        
        return unique_events
    
    def _extract_from_element(self, element: BeautifulSoup, site_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract event data from HTML element (common implementation)."""
        text = element.get_text(strip=True)
        
        # Filter for event-related content
        event_keywords = self._get_event_keywords()
        if not any(keyword in text.lower() for keyword in event_keywords):
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
        name = text.split('\n')[0][:100] if text else f'Unknown {self.event_type.title()}'
        
        return {
            'name': name,
            'url': url,
            'description': text[:300],
            'source': site_config['name'].lower().replace(' ', '_'),
            'discovery_method': 'site_scraping',
            'quality_score': self._calculate_quality_score(url, text)
        }
    
    def _build_page_url(self, base_url: str, page: int) -> str:
        """Build paginated URL for different platforms."""
        if page == 1:
            return base_url
        
        # Different sources use different pagination patterns
        if 'devpost.com' in base_url:
            return f"{base_url}?page={page}"
        elif 'eventbrite.com' in base_url:
            return f"{base_url}?page={page}"
        elif 'meetup.com' in base_url:
            return f"{base_url}?page={page}"
        else:
            return base_url  # Many sources don't have pagination
    
    def _is_aggregator_url(self, url: str) -> bool:
        """Check if URL points to an aggregator page that should be expanded."""
        aggregator_patterns = [
            'events', 'hackathons', 'conferences', 'calendar', 'schedule',
            'upcoming', 'list', 'directory', 'archive'
        ]
        
        url_lower = url.lower()
        return any(pattern in url_lower for pattern in aggregator_patterns)


class ConferenceSourceMixin:
    """Mixin class providing conference-specific functionality."""
    
    def _setup_conference_configurations(self):
        """Setup conference-specific configurations."""
        self.trusted_domains = {
            'lu.ma': 0.95, 'eventbrite.com': 0.9, 'meetup.com': 0.8, 
            'ieee.org': 0.95, 'acm.org': 0.95, 'oreilly.com': 0.9, 
            'techcrunch.com': 0.85, 'aiml.events': 0.85, 'techmeme.com': 0.75,
            'luma.com': 0.8, 'conference.com': 0.7, 'tech.events': 0.8
        }
        
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


class HackathonSourceMixin:
    """Mixin class providing hackathon-specific functionality."""
    
    def _setup_hackathon_configurations(self):
        """Setup hackathon-specific configurations."""
        self.sources = [
            {
                'name': 'Devpost',
                'base_url': 'https://devpost.com',
                'use_api': True,
                'search_urls': ['https://devpost.com/hackathons'],
                'url_patterns': ['/hackathons/'],
                'keywords': ['hackathon', 'hack', 'challenge', 'contest'],
                'max_pages': 5,
                'reliability': 0.95
            },
            {
                'name': 'MLH',
                'base_url': 'https://mlh.io',
                'use_api': False,
                'search_urls': ['https://mlh.io/seasons/2025/events'],
                'url_patterns': ['/events/', '/event/'],
                'keywords': ['hackathon', 'hack', 'mlh'],
                'max_pages': 1,
                'reliability': 0.95
            },
            {
                'name': 'Eventbrite',
                'base_url': 'https://www.eventbrite.com',
                'use_api': False,
                'search_urls': [
                    'https://www.eventbrite.com/d/online/hackathon',
                    'https://www.eventbrite.com/d/online/hack',
                    'https://www.eventbrite.com/d/online/coding-challenge'
                ],
                'url_patterns': ['/e/'],
                'keywords': ['hackathon', 'hack', 'coding', 'programming'],
                'max_pages': 3,
                'reliability': 0.7
            }
        ]


# NOTE: This base class consolidates common functionality between conference 
# and hackathon sources. Testing requires manual verification of:
# - External API integrations (Tavily, Devpost, etc.)
# - Web scraping across different platforms  
# - Event type specific filtering logic
# Manual testing recommended for: API rate limits, site structure changes, content parsing 