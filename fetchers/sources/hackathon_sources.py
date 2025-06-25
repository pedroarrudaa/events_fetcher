"""
Unified Hackathon Sources - Consolidated hackathon discovery.

Refactored to use the unified BaseSourceDiscovery class, eliminating
code duplication while preserving all hackathon-specific functionality.
"""

import os
import re
import time
import json
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup

from shared_utils import (
    WebScraper, EventGPTExtractor, QueryGenerator, 
    performance_monitor, is_valid_event_url, logger
)
from .base_source_discovery import BaseSourceDiscovery
from ..config_loader import get_config_loader


def fetch_devpost_hackathons(pages: int = 1) -> List[Dict[str, Any]]:
    """
    Fetch open hackathons from Devpost public API with location filtering.
    
    NOTE: This function uses configuration-driven filtering but loads config
    locally to maintain standalone functionality for legacy compatibility.
    
    Args:
        pages: Number of pages to fetch (default: 1)
        
    Returns:
        List of hackathon dictionaries with title, url, submission_deadline, location, and online
    """
    hackathons = []
    
    # Load configuration (try to use global config, fall back to defaults)
    try:
        config_loader = get_config_loader()
        devpost_config = config_loader.get_devpost_api_config()
        target_locations = config_loader.get_target_locations('hackathon')
        online_indicators = config_loader.get_online_indicators('hackathon')
        
        base_url = devpost_config.get('base_url', "https://devpost.com/api/hackathons")
        headers = devpost_config.get('headers', {})
        default_params = devpost_config.get('default_params', {})
        rate_limit_delay = devpost_config.get('rate_limit_delay', 1.0)
        rate_limit_429_delay = devpost_config.get('rate_limit_429_delay', 5.0)
    except:
        # Fallback to hardcoded values if config loading fails
        base_url = "https://devpost.com/api/hackathons"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://devpost.com/hackathons',
            'X-Requested-With': 'XMLHttpRequest'
        }
        default_params = {'per_page': 20, 'status': 'open'}
        target_locations = [
            'san francisco', 'sf', 'bay area', 'silicon valley', 'california', 'ca',
            'new york', 'ny', 'nyc', 'new york city', 'manhattan', 'brooklyn',
            'online', 'virtual', 'remote', 'worldwide', 'global'
        ]
        online_indicators = [
            'online', 'virtual', 'remote', 'global', 'worldwide', 'digital',
            'internet', 'from home', 'anywhere'
        ]
        rate_limit_delay = 1.0
        rate_limit_429_delay = 5.0
    
    # First try to get hackathons with general search
    for page in range(1, pages + 1):
        try:
            params = {
                'search': '',  # Get all hackathons, not just AI
                'page': page,
                **default_params  # Use configured parameters
            }
            
            logger.log("info", f"Fetching Devpost hackathons page {page}")
            
            response = requests.get(base_url, headers=headers, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract hackathons from response
                if 'hackathons' in data:
                    hackathons_data = data['hackathons']
                elif isinstance(data, list):
                    hackathons_data = data
                else:
                    hackathons_data = data.get('data', [])
                
                if not hackathons_data:
                    logger.log("info", f"No more hackathons found on page {page}")
                    break
                
                for item in hackathons_data:
                    try:
                        location = item.get('location', '').strip().lower()
                        online = item.get('online', False)
                        title = item.get('title', '').strip().lower()
                        
                        # Check if hackathon is online based on multiple indicators
                        is_online = (
                            online or
                            any(indicator in location for indicator in online_indicators) or
                            any(indicator in title for indicator in online_indicators) or
                            location == ''  # Empty location often means online
                        )
                        
                        # Check if hackathon matches our target locations
                        is_target_location = (
                            is_online or  # Include if determined to be online
                            any(target in location for target in target_locations)
                        )
                        
                        if not is_target_location:
                            continue  # Skip hackathons not in target locations
                        
                        hackathon = {
                            'title': item.get('title', '').strip(),
                            'url': item.get('url', '').strip(),
                            'submission_deadline': item.get('submission_deadline', ''),
                            'location': item.get('location', '').strip(),
                            'online': is_online,  # Use our calculated online status
                            'source': 'Devpost',
                            'quality_score': 0.9,
                            'discovered_at': datetime.now().isoformat()
                        }
                        
                        # Clean up URL
                        if hackathon['url'] and not hackathon['url'].startswith('http'):
                            hackathon['url'] = f"https://devpost.com{hackathon['url']}"
                        
                        # Only add valid hackathons
                        if hackathon['title'] and hackathon['url']:
                            hackathons.append(hackathon)
                            logger.log("info", f"Added hackathon: {hackathon['title']} (Location: {hackathon['location']}, Online: {hackathon['online']})")
                            
                    except Exception as e:
                        logger.log("error", f"Error processing hackathon item: {str(e)}")
                        continue
                
                logger.log("info", f"Fetched {len(hackathons_data)} hackathons from page {page}")
                
                # Rate limiting between pages (use configured delay)
                if page < pages:
                    time.sleep(rate_limit_delay)
                    
            elif response.status_code == 429:
                logger.log("warning", "Rate limited by Devpost API")
                time.sleep(rate_limit_429_delay)  # Use configured delay for rate limits
                break
            else:
                logger.log("warning", f"Devpost API returned status {response.status_code}")
                break
                
        except requests.exceptions.RequestException as e:
            logger.log("error", f"Request error on page {page}: {str(e)}")
            break
        except Exception as e:
            logger.log("error", f"Unexpected error on page {page}: {str(e)}")
            break
    
    # Also search specifically for different types of hackathons
    specific_searches = [
        {'search': 'hackathon', 'location': 'San Francisco'},
        {'search': 'hackathon', 'location': 'New York'},
        {'search': 'ai hackathon', 'location': ''},
        {'search': 'tech hackathon', 'location': ''},
        {'search': 'online hackathon', 'location': ''},
        {'search': 'virtual hackathon', 'location': ''},
        {'search': 'startup hackathon', 'location': ''},
    ]
    
    for search_params in specific_searches:
        try:
            params = {
                'search': search_params['search'],
                'page': 1,
                'per_page': 20,  # Increased from 10 to 20
                'status[]': 'open'
            }
            
            if search_params['location']:
                params['location'] = search_params['location']
            
            logger.log("info", f"Searching specifically for: {search_params}")
            
            response = requests.get(base_url, headers=headers, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract hackathons from response
                if 'hackathons' in data:
                    hackathons_data = data['hackathons']
                elif isinstance(data, list):
                    hackathons_data = data
                else:
                    hackathons_data = data.get('data', [])
                
                for item in hackathons_data:
                    try:
                        location = item.get('location', '').strip().lower()
                        online = item.get('online', False)
                        title = item.get('title', '').strip().lower()
                        
                        # Check if hackathon is online based on multiple indicators
                        is_online = (
                            online or
                            any(indicator in location for indicator in online_indicators) or
                            any(indicator in title for indicator in online_indicators) or
                            location == ''  # Empty location often means online
                        )
                        
                        # Check if hackathon matches our target locations
                        is_target_location = (
                            is_online or  # Include if determined to be online
                            any(target in location for target in target_locations)
                        )
                        
                        if not is_target_location:
                            continue  # Skip hackathons not in target locations
                        
                        url = item.get('url', '').strip()
                        if url and not url.startswith('http'):
                            url = f"https://devpost.com{url}"
                        
                        # Check for duplicates
                        if any(h['url'] == url for h in hackathons):
                            continue
                        
                        hackathon = {
                            'title': item.get('title', '').strip(),
                            'url': url,
                            'submission_deadline': item.get('submission_deadline', ''),
                            'location': item.get('location', '').strip(),
                            'online': is_online,  # Use our calculated online status
                            'source': 'Devpost',
                            'quality_score': 0.9,
                            'discovered_at': datetime.now().isoformat()
                        }
                        
                        if hackathon['title'] and hackathon['url']:
                            hackathons.append(hackathon)
                            logger.log("info", f"Added from specific search: {hackathon['title']} (Location: {hackathon['location']}, Online: {hackathon['online']})")
                            
                    except Exception as e:
                        logger.log("error", f"Error processing specific search item: {str(e)}")
                        continue
                        
            time.sleep(1)  # Rate limiting
            
        except Exception as e:
            logger.log("error", f"Error in specific search: {str(e)}")
            continue
    
    logger.log("info", f"Total hackathons fetched from Devpost API: {len(hackathons)} (filtered for SF/NY/Online)")
    return hackathons


class UnifiedHackathonSources(BaseSourceDiscovery):
    """
    Unified hackathon discovery from all sources.
    
    Refactored to inherit from BaseSourceDiscovery, eliminating duplicate
    code while preserving hackathon-specific functionality like Devpost API
    integration and location filtering for remote events.
    """
    
    def _init_event_config(self):
        """Initialize hackathon-specific configuration from external files."""
        self.config_loader = get_config_loader()
        self.config = self.config_loader.get_config('hackathon')
        
        # Load from configuration files instead of hardcoded values
        self.sources = self.config_loader.get_sources_config('hackathon')
        self.hackathon_keywords = self.config_loader.get_event_keywords('hackathon')
        self.target_locations = self.config_loader.get_target_locations('hackathon')
        self.online_indicators = self.config_loader.get_online_indicators('hackathon')
        self.discovery_settings = self.config_loader.get_discovery_settings('hackathon')
        self.devpost_api_config = self.config_loader.get_devpost_api_config()
        self.quality_scoring_config = self.config_loader.get_quality_scoring_config('hackathon')
    
    def get_event_keywords(self) -> List[str]:
        """Get hackathon-specific keywords."""
        return self.hackathon_keywords
    
    def get_sources_config(self) -> List[Dict[str, Any]]:
        """Get source configurations for hackathons."""
        return self.sources
    
    def _is_relevant_event(self, url: str, text: str, source_config: Dict[str, Any]) -> bool:
        """Check if content is relevant to hackathons."""
        # Use base URL pattern validation
        if not self._is_valid_url_pattern(url, source_config):
            return False
        
        # Check for hackathon keywords
        if not self._has_event_keywords(text):
            return False
        
        return True
    
    @performance_monitor
    def discover_all_hackathons(self, max_results: int = 60) -> List[Dict[str, Any]]:
        """
        Discover hackathons from all available sources.
        
        Uses the base class discover_all_events method which handles the common
        source iteration, API vs scraping logic, and deduplication.
        
        Args:
            max_results: Maximum number of hackathons to return
            
        Returns:
            List of hackathon dictionaries
        """
        # Use base class method which handles all the common logic
        return self.discover_all_events(max_results)
    
    def _handle_api_source(self, source_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Handle hackathon-specific API sources, particularly Devpost."""
        hackathons = []
        source_name = source_config['name']
        
        if source_name == 'Devpost':
            hackathons = self._fetch_devpost_api_hackathons(source_config)
        else:
            # For non-API sources, use the base class scraping
            hackathons = self._scrape_source(source_config)
        
        return hackathons
    
    def _fetch_devpost_api_hackathons(self, source_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetch hackathons from Devpost API using configuration."""
        hackathons = []
        
        try:
            # Use the configuration-driven Devpost API fetcher
            max_pages = self.devpost_api_config.get('max_pages', 10)
            hackathons = fetch_devpost_hackathons(pages=max_pages)
                
        except Exception as e:
            logger.log("error", f"Devpost API error: {str(e)}")
            
        return hackathons
    

    
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
        """Calculate quality score for a hackathon using configuration."""
        # Get scoring configuration
        scoring = self.quality_scoring_config
        base_score_key = scoring.get('base_score_key', 'reliability')
        score = source_config.get(base_score_key, 0.5)
        
        # Content quality indicators from configuration
        text_lower = text.lower()
        
        # Year bonus
        if any(word in text_lower for word in ['2024', '2025']):
            score += scoring.get('year_bonus', 0.1)
        
        # Prize/award bonus
        if any(word in text_lower for word in ['prize', 'award', 'winner']):
            score += scoring.get('prize_bonus', 0.05)
        
        # Online accessibility bonus
        if any(word in text_lower for word in ['virtual', 'online', 'remote']):
            score += scoring.get('online_bonus', 0.05)
        
        # Detail length bonus
        if len(text) > 30:
            score += scoring.get('detail_bonus', 0.05)
        
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