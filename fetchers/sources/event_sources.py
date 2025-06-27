"""
Conferences and Hackathons enhanced event discovery from multiple sources
"""

import os
import re
import sys
import time
import json
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional, Literal, Union
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup

# Add parent directories to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import (
    EVENT_MAX_RESULTS_CONFERENCE, EVENT_MAX_RESULTS_HACKATHON, EVENT_TAVILY_MAX_RESULTS,
    EVENT_TAVILY_SLEEP, EVENT_SITE_SCRAPING_SLEEP, EVENT_SOURCE_SLEEP,
    EVENT_DESCRIPTION_MAX_LENGTH, EVENT_NAME_MAX_LENGTH, EVENT_MIN_TEXT_LENGTH,
    EVENT_MIN_LINK_TEXT_LENGTH, EVENT_AGGREGATOR_EXPANSION_LIMIT, EVENT_QUALITY_BASE_SCORE,
    EVENT_QUALITY_BONUS_INCREMENT, EVENT_QUALITY_MAX_SCORE, EVENT_API_TIMEOUT, EVENT_API_PER_PAGE
)

from shared_utils import (
    WebScraper, QueryGenerator, 
    performance_monitor, is_valid_event_url, logger
)

# Import enhanced scraper if available
try:
    from fetchers.scrapers.enhanced_scraper import EnhancedScraper
    ENHANCED_SCRAPER_AVAILABLE = True
except ImportError:
    ENHANCED_SCRAPER_AVAILABLE = False

EventType = Literal['conference', 'hackathon']


class EventKeywords:
    """Organized keywords for different event types."""
    
    # Core event types
    CONFERENCE_TYPES = ['conference', 'summit', 'symposium', 'workshop', 'expo', 'meetup']
    HACKATHON_TYPES = ['hackathon', 'hack', 'coding challenge', 'programming contest', 
                      'developer challenge', 'coding competition', 'tech challenge']
    
    # Generative AI / LLM specific terms (high priority for conferences)
    GENAI_TERMS = [
        'generative ai', 'genai', 'llm', 'large language model',
        'chatgpt', 'gpt', 'foundation models', 'transformer',
        'prompt engineering', 'ai agent', 'llama', 'claude',
        'multimodal ai', 'vision language model'
    ]
    
    # Broader AI/ML terms
    AI_ML_TERMS = [
        'artificial intelligence', 'machine learning', 'deep learning',
        'neural network', 'ai research', 'ai safety', 'ai ethics',
        'computer vision', 'natural language processing', 'nlp',
        'reinforcement learning', 'data science'
    ]
    
    # Tech industry terms
    TECH_TERMS = [
        'tech', 'technology', 'startup', 'innovation', 'developer',
        'founder', 'venture capital', 'demo day', 'pitch',
        'product launch', 'devops', 'cloud computing'
    ]
    
    # Company/Platform specific
    COMPANY_BRANDS = [
        'openai', 'anthropic', 'google', 'microsoft', 'meta',
        'nvidia', 'hugging face', 'aws', 'azure', 'cohere',
        'stability ai', 'midjourney', 'runpod'
    ]
    
    @classmethod
    def get_keywords_for_type(cls, event_type: EventType) -> List[str]:
        """Get keywords for specific event type."""
        if event_type == 'conference':
            return (cls.CONFERENCE_TYPES + cls.GENAI_TERMS + cls.AI_ML_TERMS + 
                   cls.TECH_TERMS + cls.COMPANY_BRANDS)
        else:  # hackathon
            return cls.HACKATHON_TYPES + cls.AI_ML_TERMS + cls.TECH_TERMS
    
    @classmethod
    def get_priority_keywords(cls, event_type: EventType) -> List[str]:
        """Get high-priority keywords for focused searches."""
        if event_type == 'conference':
            return cls.CONFERENCE_TYPES + cls.GENAI_TERMS
        else:  # hackathon
            return cls.HACKATHON_TYPES


class TrustedDomains:
    """Event platform trust scores and validation."""
    
    DOMAINS = {
        # Premium platforms (95% trust)
        'lu.ma': 0.95, 'ieee.org': 0.95, 'acm.org': 0.95, 'devpost.com': 0.95,
        
        # Established platforms (90% trust)
        'eventbrite.com': 0.9, 'oreilly.com': 0.9, 'mlh.io': 0.9,
        
        # Good platforms (80-85% trust)
        'meetup.com': 0.8, 'luma.com': 0.8, 'techcrunch.com': 0.85,
        'aiml.events': 0.85, 'tech.events': 0.8,
        
        # Decent platforms (70-75% trust)
        'techmeme.com': 0.75, 'conference.com': 0.7
    }
    
    @classmethod
    def get_score(cls, url: str) -> float:
        """Get trust score for a URL domain."""
        domain = urlparse(url.lower()).netloc.replace('www.', '')
        return cls.DOMAINS.get(domain, 0.3)
    
    @classmethod
    def get_trusted_domains_list(cls) -> List[str]:
        """Get list of trusted domain names."""
        return list(cls.DOMAINS.keys())


class EventLocations:
    """Target and excluded location configurations."""
    
    TARGET_LOCATIONS = [
        # San Francisco Bay Area
        'san francisco', 'sf', 'bay area', 'silicon valley',
        'palo alto', 'mountain view', 'santa clara', 'san jose',
        
        # New York Area
        'new york', 'nyc', 'manhattan', 'brooklyn', 'queens',
        'bronx', 'new york city', 'ny',
        
        # Online/Virtual (for hackathons)
        'online', 'virtual', 'remote', 'worldwide', 'global'
    ]
    
    EXCLUDED_LOCATIONS = [
        # Virtual exclusions (for conferences only)
        'webinar', 'livestream', 'streaming', 'zoom', 'teams', 'anywhere'
    ]
    
    @classmethod
    def is_target_location(cls, text: str, event_type: EventType) -> bool:
        """Check if text contains target location."""
        text_lower = text.lower()
        
        # For conferences, exclude virtual events
        if event_type == 'conference':
            virtual_terms = ['virtual', 'online', 'remote', 'worldwide', 'global']
            if any(excluded in text_lower for excluded in cls.EXCLUDED_LOCATIONS + virtual_terms):
                return False
        
        # Check for target locations
        return any(location in text_lower for location in cls.TARGET_LOCATIONS)


class DevpostAPI:
    """Dedicated Devpost API handler for hackathons."""
    
    @staticmethod
    def fetch_hackathons(pages: int = 5) -> List[Dict[str, Any]]:
        """Fetch hackathons from Devpost API."""
        hackathons = []
        base_url = "https://devpost.com/api/hackathons"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://devpost.com/hackathons',
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        online_indicators = [
            'online', 'virtual', 'remote', 'global', 'worldwide', 'digital',
            'internet', 'from home', 'anywhere'
        ]
        
        target_locations = [
            'san francisco', 'sf', 'bay area', 'silicon valley', 'california', 'ca',
            'new york', 'ny', 'nyc', 'new york city', 'manhattan', 'brooklyn',
            'online', 'virtual', 'remote', 'worldwide', 'global'
        ]
        
        # Fetch general hackathons
        for page in range(1, pages + 1):
            try:
                params = {
                    'search': '',
                    'page': page,
                    'per_page': EVENT_API_PER_PAGE,
                    'status[]': 'open'
                }
                
                response = requests.get(base_url, headers=headers, params=params, timeout=EVENT_API_TIMEOUT)
                
                if response.status_code == 200:
                    data = response.json()
                    hackathons_data = data.get('hackathons', data if isinstance(data, list) else data.get('data', []))
                    
                    if not hackathons_data:
                        break
                    
                    for item in hackathons_data:
                        hackathon = DevpostAPI._process_hackathon_item(
                            item, online_indicators, target_locations
                        )
                        if hackathon:
                            hackathons.append(hackathon)
                    
                    time.sleep(1)
                else:
                    break
                    
            except Exception as e:
                logger.log("error", f"Devpost API error on page {page}: {str(e)}")
                break
        
        return hackathons
    
    @staticmethod
    def _process_hackathon_item(item: Dict[str, Any], online_indicators: List[str], 
                               target_locations: List[str]) -> Optional[Dict[str, Any]]:
        """Process individual hackathon item from API."""
        try:
            location = item.get('location', '').strip().lower()
            online = item.get('online', False)
            title = item.get('title', '').strip().lower()
            
            # Determine if hackathon is online
            is_online = (
                online or
                any(indicator in location for indicator in online_indicators) or
                any(indicator in title for indicator in online_indicators) or
                location == ''
            )
            
            # Check if hackathon matches target locations
            is_target_location = (
                is_online or
                any(target in location for target in target_locations)
            )
            
            if not is_target_location:
                return None
            
            url = item.get('url', '').strip()
            if url and not url.startswith('http'):
                url = f"https://devpost.com{url}"
            
            return {
                'name': item.get('title', '').strip(),
                'url': url,
                'description': f"Deadline: {item.get('submission_deadline', 'TBD')}",
                'location': item.get('location', '').strip(),
                'online': is_online,
                'source': 'devpost',
                'discovery_method': 'api',
                'quality_score': 0.9,
                'discovered_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.log("error", f"Error processing Devpost item: {str(e)}")
            return None


class UnifiedEventSources:
    """Unified event discovery for conferences and hackathons."""
    
    def __init__(self, event_type: EventType):
        self.event_type = event_type
        self.scraper = WebScraper()
        self.enhanced_scraper = EnhancedScraper() if ENHANCED_SCRAPER_AVAILABLE else None
        self.enricher = None  # Enrichment now handled by EventService
        self.query_generator = QueryGenerator()
        
        # Initialize Tavily client (for conferences)
        self.tavily_client = None
        if event_type == 'conference':
            try:
                from tavily import TavilyClient
                tavily_key = os.getenv("TAVILY_API_KEY")
                self.tavily_client = TavilyClient(api_key=tavily_key) if tavily_key else None
            except ImportError:
                logger.log("warning", "Tavily not available")
        
        # Event-specific configurations
        self.config = self._get_event_config()
    
    def _get_event_config(self) -> Dict[str, Any]:
        """Get configuration for specific event type."""
        if self.event_type == 'conference':
            return {
                'max_results': EVENT_MAX_RESULTS_CONFERENCE,
                'sites': [
                    {
                        'name': 'Eventbrite AI SF',
                        'url': 'https://www.eventbrite.com/d/ca--san-francisco/artificial-intelligence/',
                        'selectors': ['.event-card', '.eds-event-card', '[data-event-id]']
                    },
                    {
                        'name': 'Luma AI SF',
                        'url': 'https://lu.ma/discover?dates=upcoming&location=San+Francisco%2C+CA&q=AI',
                        'selectors': ['.event-card', '[data-event]', '.event-item', 'article']
                    },
                    {
                        'name': 'AI ML Events',
                        'url': 'https://aiml.events/',
                        'selectors': ['.event-card', '.event-item', '[data-event]', 'article']
                    }
                ]
            }
        else:  # hackathon
            return {
                'max_results': EVENT_MAX_RESULTS_HACKATHON,
                'sources': [
                    {
                        'name': 'Devpost',
                        'base_url': 'https://devpost.com',
                        'use_api': True,
                        'search_urls': ['https://devpost.com/hackathons'],
                        'url_patterns': ['/hackathons/'],
                        'max_pages': 5,
                        'reliability': 0.95
                    },
                    {
                        'name': 'MLH',
                        'base_url': 'https://mlh.io',
                        'use_api': False,
                        'search_urls': ['https://mlh.io/seasons/2025/events'],
                        'url_patterns': ['/events/', '/event/'],
                        'max_pages': 1,
                        'reliability': 0.95
                    }
                ]
            }
    
    @performance_monitor
    def discover_all_events(self, max_results: Optional[int] = None) -> List[Dict[str, Any]]:
        """Discover events from all sources."""
        if max_results is None:
            max_results = self.config['max_results']
        
        logger.log("info", f"Starting {self.event_type} discovery (target: {max_results})")
        all_events = []
        
        if self.event_type == 'conference':
            all_events = self._discover_conferences(max_results)
        else:  # hackathon
            all_events = self._discover_hackathons(max_results)
        
        # Deduplicate and rank
        unique_events = self._deduplicate_and_rank(all_events)
        final_results = unique_events[:max_results]
        
        logger.log("info", f"{self.event_type} discovery completed: {len(final_results)}/{max_results}")
        return final_results
    
    def _discover_conferences(self, max_results: int) -> List[Dict[str, Any]]:
        """Discover conferences using site scraping and Tavily search."""
        conferences = []
        
        # Step 1: Site scraping
        if len(conferences) < max_results:
            site_results = self._scrape_sites()
            conferences.extend(site_results)
            logger.log("info", f"Site scraping: {len(site_results)} conferences")
        
        # Step 2: Tavily search (if available)
        if len(conferences) < max_results and self.tavily_client:
            remaining_needed = max_results - len(conferences)
            tavily_results = self._search_with_tavily(remaining_needed)
            conferences.extend(tavily_results)
            logger.log("info", f"Tavily search: {len(tavily_results)} conferences")
        
        return conferences
    
    def _discover_hackathons(self, max_results: int) -> List[Dict[str, Any]]:
        """Discover hackathons using API and site scraping."""
        hackathons = []
        
        for source_config in self.config['sources']:
            try:
                if source_config.get('use_api', False):
                    source_events = self._scrape_api_source(source_config)
                else:
                    source_events = self._scrape_source(source_config)
                
                hackathons.extend(source_events)
                logger.log("info", f"{source_config['name']} found {len(source_events)} hackathons")
                
                time.sleep(EVENT_SOURCE_SLEEP)
                
            except Exception as e:
                logger.log("error", f"Failed to scrape {source_config['name']}", error=str(e))
        
        return hackathons
    
    def _scrape_sites(self) -> List[Dict[str, Any]]:
        """Scrape configured event sites."""
        events = []
        
        for site in self.config['sites']:
            try:
                site_events = self._scrape_single_site(site)
                events.extend(site_events)
                time.sleep(EVENT_SITE_SCRAPING_SLEEP)
            except Exception as e:
                logger.log("error", f"Failed to scrape {site['name']}", error=str(e))
        
        return events
    
    def _scrape_single_site(self, site_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Scrape individual event site."""
        # Use enhanced scraper for better results
        if self.enhanced_scraper:
            result = self.enhanced_scraper.scrape(site_config['url'])
        else:
            result = self.scraper.scrape(site_config['url'], use_crawl4ai=True)
        
        if not result['success']:
            logger.log("warning", f"Failed to scrape {site_config['name']}", error=result.get('error'))
            return []
        
        soup = BeautifulSoup(result['content'], 'html.parser')
        events = []
        
        for selector in site_config['selectors']:
            elements = soup.select(selector)
            
            for element in elements:
                event = self._extract_from_element(element, site_config)
                if event:
                    events.append(event)
        
        return events
    
    def _extract_from_element(self, element: BeautifulSoup, site_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract event data from HTML element."""
        text = element.get_text(strip=True)
        
        # Filter by keywords and length
        if (len(text) < EVENT_MIN_TEXT_LENGTH or 
            not any(keyword in text.lower() for keyword in EventKeywords.get_priority_keywords(self.event_type))):
            return None
        
        # Extract URL
        url = site_config['url']
        link = element.find('a', href=True)
        if link and link.get('href'):
            url = urljoin(site_config['url'], link.get('href'))
        
        # Extract name
        name = text.split('\n')[0][:EVENT_NAME_MAX_LENGTH] if text else f'Unknown {self.event_type.title()}'
        
        return {
            'name': name,
            'url': url,
            'description': text[:EVENT_DESCRIPTION_MAX_LENGTH],
            'source': site_config['name'].lower().replace(' ', '_'),
            'discovery_method': 'site_scraping',
            'quality_score': self._calculate_quality_score(url, text)
        }
    
    def _search_with_tavily(self, max_events: int) -> List[Dict[str, Any]]:
        """Search using Tavily API (conferences only)."""
        if not self.tavily_client:
            return []
        
        events = []
        queries = self._generate_search_queries()
        
        for query in queries:
            if len(events) >= max_events:
                break
                
            try:
                response = self.tavily_client.search(
                    query=query,
                    search_depth="basic",
                    max_results=EVENT_TAVILY_MAX_RESULTS,
                    include_domains=TrustedDomains.get_trusted_domains_list()
                )
                
                for result in response.get('results', []):
                    event = self._process_search_result(result, 'tavily', query)
                    if event and EventLocations.is_target_location(
                        f"{event.get('name', '')} {event.get('description', '')}", self.event_type
                    ):
                        events.append(event)
                        
                        if len(events) >= max_events:
                            break
                
                time.sleep(EVENT_TAVILY_SLEEP)
                
            except Exception as e:
                logger.log("error", f"Tavily search failed: {query}", error=str(e))
        
        return events
    
    def _generate_search_queries(self) -> List[str]:
        """Generate search queries for conferences."""
        return [
            '"generative AI conference" San Francisco 2025',
            '"LLM conference" San Francisco 2025',
            '"AI startup" conference San Francisco 2025',
            'eventbrite.com "generative AI" San Francisco 2025',
            'lu.ma "AI conference" San Francisco 2025',
            'OpenAI DevDay 2025 San Francisco'
        ]
    
    def _scrape_api_source(self, source_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Scrape source using API."""
        if source_config['name'] == 'Devpost':
            return DevpostAPI.fetch_hackathons(pages=source_config['max_pages'])
        return []
    
    def _scrape_source(self, source_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Scrape source using web scraping."""
        events = []
        
        for search_url in source_config['search_urls']:
            try:
                result = self.scraper.scrape(search_url, use_firecrawl=False)
                
                if result['success']:
                    page_events = self._extract_events_from_page(result['content'], source_config)
                    events.extend(page_events)
                
            except Exception as e:
                logger.log("error", f"Error scraping {search_url}", error=str(e))
        
        return events
    
    def _extract_events_from_page(self, content: str, source_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract event data from a page."""
        try:
            soup = BeautifulSoup(content, 'html.parser')
            events = []
            
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                link_text = link.get_text(strip=True)
                
                if not href or len(link_text) < EVENT_MIN_LINK_TEXT_LENGTH:
                    continue
                
                absolute_url = urljoin(source_config['base_url'], href)
                
                if self._is_event_url(absolute_url, source_config, link_text):
                    event = {
                        'name': self._clean_event_name(link_text),
                        'url': absolute_url,
                        'description': '',
                        'source': source_config['name'].lower(),
                        'discovery_method': 'source_scraping',
                        'quality_score': self._calculate_quality_score(absolute_url, link_text, source_config)
                    }
                    events.append(event)
            
            return events[:EVENT_AGGREGATOR_EXPANSION_LIMIT]
            
        except Exception as e:
            logger.log("error", f"Error extracting events from page", error=str(e))
            return []
    
    def _is_event_url(self, url: str, source_config: Dict[str, Any], link_text: str) -> bool:
        """Check if URL looks like an event."""
        if not url or not is_valid_event_url(url):
            return False
        
        url_lower = url.lower()
        if not any(pattern in url_lower for pattern in source_config['url_patterns']):
            return False
        
        combined_text = f"{url} {link_text}".lower()
        return any(keyword in combined_text for keyword in EventKeywords.get_keywords_for_type(self.event_type))
    
    def _clean_event_name(self, raw_name: str) -> str:
        """Clean and format event name."""
        if not raw_name:
            return f'Unknown {self.event_type.title()}'
        
        cleaned = re.sub(r'\s+', ' ', raw_name.strip())
        return cleaned[:EVENT_NAME_MAX_LENGTH] if len(cleaned) > EVENT_NAME_MAX_LENGTH else cleaned
    
    def _process_search_result(self, result: Dict[str, Any], source: str, query: str) -> Optional[Dict[str, Any]]:
        """Process search result into event format."""
        url = result.get('url', '')
        title = result.get('title', '')
        content = result.get('content', '')
        
        if not url or not is_valid_event_url(url):
            return None
        
        combined_text = f"{title} {content}".lower()
        if not any(keyword in combined_text for keyword in EventKeywords.get_keywords_for_type(self.event_type)):
            return None
        
        return {
            'name': title,
            'url': url,
            'description': content[:EVENT_DESCRIPTION_MAX_LENGTH],
            'source': source,
            'discovery_method': 'search',
            'search_query': query,
            'quality_score': self._calculate_quality_score(url, combined_text)
        }
    
    def _calculate_quality_score(self, url: str, content: str, source_config: Optional[Dict[str, Any]] = None) -> float:
        """Calculate quality score for an event."""
        score = EVENT_QUALITY_BASE_SCORE
        
        # Domain reputation boost
        domain_score = TrustedDomains.get_score(url)
        score = max(score, domain_score)
        
        # Source reliability boost
        if source_config:
            score = max(score, source_config.get('reliability', EVENT_QUALITY_BASE_SCORE))
        
        # Content quality indicators
        content_lower = content.lower()
        
        if len(content) > EVENT_NAME_MAX_LENGTH:
            score += EVENT_QUALITY_BONUS_INCREMENT
        
        if any(year in content for year in ['2024', '2025']):
            score += EVENT_QUALITY_BONUS_INCREMENT
        
        # Event-specific quality indicators
        if self.event_type == 'conference':
            if any(indicator in content_lower for indicator in ['registration', 'speakers', 'agenda', 'tickets']):
                score += EVENT_QUALITY_BONUS_INCREMENT
        else:  # hackathon
            if any(indicator in content_lower for indicator in ['prize', 'award', 'winner', 'deadline']):
                score += EVENT_QUALITY_BONUS_INCREMENT
        
        return min(score, EVENT_QUALITY_MAX_SCORE)
    
    def _deduplicate_and_rank(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicates and rank by quality."""
        seen_urls = set()
        unique_events = []
        
        for event in events:
            url = event.get('url', '').lower().strip('/')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_events.append(event)
        
        return sorted(unique_events, key=lambda x: x.get('quality_score', 0), reverse=True)


# Main discovery functions
@performance_monitor
def discover_conferences(max_results: Optional[int] = None) -> List[Dict[str, Any]]:
    """Discover conferences from all sources."""
    sources = UnifiedEventSources('conference')
    return sources.discover_all_events(max_results)


@performance_monitor
def discover_hackathons(max_results: Optional[int] = None) -> List[Dict[str, Any]]:
    """Discover hackathons from all sources."""
    sources = UnifiedEventSources('hackathon')
    return sources.discover_all_events(max_results)


@performance_monitor
def discover_events(event_type: EventType, max_results: Optional[int] = None) -> List[Dict[str, Any]]:
    """Unified function to discover events of any type."""
    sources = UnifiedEventSources(event_type)
    return sources.discover_all_events(max_results)


# Legacy compatibility functions
def enhanced_search_conference_links() -> List[Dict[str, Any]]:
    """Legacy compatibility."""
    return discover_conferences(20)

def get_conference_urls(*args, **kwargs) -> List[Dict[str, Any]]:
    """Legacy compatibility."""
    return discover_conferences(30)

def get_conference_events() -> List[Dict[str, Any]]:
    """Legacy compatibility."""
    return discover_conferences(40)

def get_hackathon_urls() -> List[Dict[str, Any]]:
    """Legacy compatibility."""
    return discover_hackathons(50)

def get_devpost_hackathons() -> List[Dict[str, Any]]:
    """Legacy compatibility."""
    hackathons = discover_hackathons(60)
    return [h for h in hackathons if h.get('source') == 'devpost']

def get_eventbrite_hackathons() -> List[Dict[str, Any]]:
    """Legacy compatibility."""
    hackathons = discover_hackathons(60)
    return [h for h in hackathons if h.get('source') == 'eventbrite']

def get_mlh_hackathons() -> List[Dict[str, Any]]:
    """Legacy compatibility."""
    hackathons = discover_hackathons(60)
    return [h for h in hackathons if h.get('source') == 'mlh'] 