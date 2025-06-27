"""
Base Source Discovery - Unified foundation for event source discovery.

This module provides the common functionality shared between conference
and hackathon source discovery, eliminating code duplication and providing
a consistent interface for extending to new event types.
"""

import os
import re
import time
import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup

from shared_utils import (
    WebScraper, EventGPTExtractor, QueryGenerator, 
    performance_monitor, is_valid_event_url, logger
)


class BaseSourceDiscovery(ABC):
    """
    Abstract base class for unified event source discovery.
    
    Provides common functionality for scraping, API calls, pagination,
    quality scoring, and deduplication that is shared between conference
    and hackathon discovery systems.
    """
    
    def __init__(self, event_type: str):
        """
        Initialize base source discovery.
        
        Args:
            event_type: Type of events ('conference' or 'hackathon')
        """
        self.event_type = event_type
        self.scraper = WebScraper()
        self.enricher = EventGPTExtractor(event_type)
        self.query_generator = QueryGenerator()
        
        # Initialize event-specific configurations
        self._init_event_config()
    
    @abstractmethod
    def _init_event_config(self):
        """Initialize event-type specific configuration. Must be implemented by subclasses."""
        pass
    
    @abstractmethod
    def get_event_keywords(self) -> List[str]:
        """Get keywords specific to this event type. Must be implemented by subclasses."""
        pass
    
    @abstractmethod
    def get_sources_config(self) -> List[Dict[str, Any]]:
        """Get source configurations. Must be implemented by subclasses."""
        pass
    
    @abstractmethod
    def _is_relevant_event(self, url: str, text: str, source_config: Dict[str, Any]) -> bool:
        """Check if content is relevant to this event type. Must be implemented by subclasses."""
        pass
    
    @performance_monitor
    def discover_all_events(self, max_results: int) -> List[Dict[str, Any]]:
        """
        Discover events from all configured sources.
        
        Args:
            max_results: Maximum number of events to return
            
        Returns:
            List of event dictionaries
        """
        logger.log("info", f"Starting unified {self.event_type} discovery")
        all_events = []
        
        for source_config in self.get_sources_config():
            try:
                if source_config.get('use_api', False):
                    source_events = self._scrape_api_source(source_config)
                else:
                    source_events = self._scrape_source(source_config)
                    
                all_events.extend(source_events)
                logger.log("info", f"{source_config['name']} found {len(source_events)} {self.event_type}s")
                
                # Rate limiting between sources
                time.sleep(2)
                
            except Exception as e:
                logger.log("error", f"Failed to scrape {source_config['name']}", error=str(e))
        
        # Deduplicate and rank
        unique_events = self._deduplicate_and_rank(all_events)
        
        # Limit results
        final_results = unique_events[:max_results]
        
        logger.log("info", f"{self.event_type.title()} discovery completed", 
                  total_found=len(all_events), 
                  unique=len(unique_events), 
                  final=len(final_results))
        
        return final_results
    
    def _scrape_api_source(self, source_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Scrape a source using its API endpoint. Can be overridden by subclasses."""
        events = []
        source_name = source_config['name']
        
        logger.log("info", f"Using API for {source_name}")
        
        try:
            # Default API handling - subclasses can override for specific APIs
            events = self._handle_api_source(source_config)
            
        except Exception as e:
            logger.log("error", f"API error for {source_name}", error=str(e))
            # Fallback to regular scraping if API fails
            logger.log("info", f"Falling back to regular scraping for {source_name}")
            events = self._scrape_source(source_config)
        
        return events
    
    def _handle_api_source(self, source_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Handle API-specific logic. Can be overridden by subclasses."""
        # Default implementation falls back to scraping
        return self._scrape_source(source_config)
    
    def _scrape_source(self, source_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Scrape a single event source with pagination support."""
        events = []
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
                    
                    # Extract events from page
                    page_events = self._extract_events_from_page(
                        result['content'], source_config)
                    
                    if not page_events:
                        break  # No more results
                    
                    events.extend(page_events)
                    
                    # Rate limiting between pages
                    if page < source_config['max_pages']:
                        time.sleep(1)
                
            except Exception as e:
                logger.log("error", f"Error scraping {search_url}", error=str(e))
        
        return events
    
    def _build_page_url(self, base_url: str, page: int) -> str:
        """Build paginated URL using common patterns."""
        if page == 1:
            return base_url
        
        # Common pagination patterns
        if 'devpost.com' in base_url:
            return f"{base_url}?page={page}"
        elif 'eventbrite.com' in base_url:
            return f"{base_url}?page={page}"
        elif 'meetup.com' in base_url:
            return f"{base_url}&page={page}"
        else:
            return base_url  # Many sources don't have pagination
    
    def _extract_events_from_page(self, content: str, source_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract event data from a scraped page."""
        try:
            soup = BeautifulSoup(content, 'html.parser')
            events = []
            
            # Find all links that might be events
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                link_text = link.get_text(strip=True)
                
                if not href or len(link_text) < 5:
                    continue
                
                # Convert relative URLs to absolute
                absolute_url = urljoin(source_config['base_url'], href)
                
                # Check if this looks like a relevant event
                if self._is_relevant_event(absolute_url, link_text, source_config):
                    event = {
                        'name': self._clean_event_name(link_text),
                        'url': absolute_url,
                        'description': self._extract_description(link),
                        'source': source_config['name'].lower(),
                        'discovery_method': 'source_scraping',
                        'quality_score': self._calculate_quality_score(
                            absolute_url, link_text, source_config)
                    }
                    events.append(event)
            
            return events[:20]  # Limit per page to avoid overwhelming results
            
        except Exception as e:
            logger.log("error", f"Error extracting {self.event_type}s from page", error=str(e))
            return []
    
    def _clean_event_name(self, raw_name: str) -> str:
        """Clean and format event name."""
        if not raw_name:
            return f'Unknown {self.event_type.title()}'
        
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
        """
        Calculate base quality score for an event.
        Can be overridden by subclasses for event-specific scoring.
        """
        score = source_config.get('reliability', 0.5)  # Base score from source reliability
        
        # Common quality indicators
        text_lower = text.lower()
        
        # Current/future year indicators
        if any(year in text_lower for year in ['2024', '2025']):
            score += 0.1
        
        # Detail length bonus
        if len(text) > 30:
            score += 0.05
        
        # URL quality (avoid spam/placeholder URLs)
        if not any(spam in url.lower() for spam in ['test', 'example', 'placeholder']):
            score += 0.05
        
        return min(score, 1.0)
    
    def _deduplicate_and_rank(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicates by URL and rank by quality score."""
        seen_urls: Set[str] = set()
        unique_events = []
        
        for event in events:
            url = event.get('url', '').lower().strip('/')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_events.append(event)
        
        # Sort by quality score (highest first)
        return sorted(unique_events, 
                     key=lambda x: x.get('quality_score', 0), 
                     reverse=True)
    
    def _is_valid_url_pattern(self, url: str, source_config: Dict[str, Any]) -> bool:
        """Check if URL matches expected patterns for this source."""
        if not url or not is_valid_event_url(url):
            return False
        
        # Check URL patterns for this source
        url_lower = url.lower()
        url_patterns = source_config.get('url_patterns', [])
        
        if url_patterns:
            return any(pattern in url_lower for pattern in url_patterns)
        
        return True  # No specific patterns required
    
    def _has_event_keywords(self, text: str) -> bool:
        """Check if text contains relevant event keywords."""
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.get_event_keywords())


class BaseSiteConfig:
    """
    Base configuration class for site-specific scraping configurations.
    Provides a structured way to define site-specific settings.
    """
    
    def __init__(self, name: str, base_url: str, search_urls: List[str], 
                 url_patterns: List[str] = None, keywords: List[str] = None,
                 max_pages: int = 1, reliability: float = 0.5, 
                 use_api: bool = False, selectors: List[str] = None):
        self.name = name
        self.base_url = base_url
        self.search_urls = search_urls
        self.url_patterns = url_patterns or []
        self.keywords = keywords or []
        self.max_pages = max_pages
        self.reliability = reliability
        self.use_api = use_api
        self.selectors = selectors or []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary format."""
        return {
            'name': self.name,
            'base_url': self.base_url,
            'search_urls': self.search_urls,
            'url_patterns': self.url_patterns,
            'keywords': self.keywords,
            'max_pages': self.max_pages,
            'reliability': self.reliability,
            'use_api': self.use_api,
            'selectors': self.selectors
        }


# NOTE: This base class eliminates duplicate patterns found in conference_sources.py
# and hackathon_sources.py. Manual testing recommended for:
# - API integrations (Devpost, Tavily, external services)
# - Website scraping resilience
# - Rate limiting effectiveness
# The base patterns are tested through subclass implementations. 