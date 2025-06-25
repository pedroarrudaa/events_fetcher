"""
Event Type Configurations - Centralized settings for conference and hackathon systems.

This module consolidates all event-type-specific configurations, eliminating
hardcoded parameters scattered throughout the codebase and providing a single
source of truth for system behavior.
"""

from typing import Dict, List, Any
from dataclasses import dataclass, field


@dataclass
class EventTypeConfig:
    """Base configuration class for event types."""
    event_type: str
    max_results: int
    table_name: str
    keywords: List[str] = field(default_factory=list)
    target_locations: List[str] = field(default_factory=list)
    excluded_locations: List[str] = field(default_factory=list)
    trusted_domains: Dict[str, float] = field(default_factory=dict)
    sources: List[Dict[str, Any]] = field(default_factory=list)
    search_sites: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ConferenceConfig(EventTypeConfig):
    """Configuration specific to conferences."""
    
    def __post_init__(self):
        self.event_type = 'conference'
        self.max_results = 200
        self.table_name = 'conferences'
        
        # Conference-specific keywords
        self.keywords = [
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
        
        # Target locations - conferences must be in these areas (NO VIRTUAL/REMOTE)
        self.target_locations = [
            # San Francisco area
            'san francisco', 'sf', 'bay area', 'silicon valley', 'palo alto', 
            'mountain view', 'sunnyvale', 'cupertino', 'redwood city', 'san jose',
            # New York area  
            'new york', 'nyc', 'manhattan', 'brooklyn', 'queens', 'bronx',
            'new york city', 'ny'
        ]
        
        # Excluded locations/terms - these will be filtered out
        self.excluded_locations = [
            'virtual', 'online', 'remote', 'worldwide', 'global', 'digital',
            'webinar', 'livestream', 'streaming', 'zoom', 'teams'
        ]
        
        # Trusted domains with quality scores
        self.trusted_domains = {
            'lu.ma': 0.95, 'eventbrite.com': 0.9, 'meetup.com': 0.8, 
            'ieee.org': 0.95, 'acm.org': 0.95, 'oreilly.com': 0.9, 
            'techcrunch.com': 0.85, 'aiml.events': 0.85, 'techmeme.com': 0.75,
            'luma.com': 0.8, 'conference.com': 0.7, 'tech.events': 0.8
        }
        
        # Conference-specific sites for scraping
        self.search_sites = [
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


@dataclass
class HackathonConfig(EventTypeConfig):
    """Configuration specific to hackathons."""
    
    def __post_init__(self):
        self.event_type = 'hackathon'
        self.max_results = 60
        self.table_name = 'hackathons'
        
        # Hackathon-specific keywords
        self.keywords = [
            'hackathon', 'hack', 'coding challenge', 'programming contest',
            'developer challenge', 'coding competition', 'tech challenge'
        ]
        
        # Target locations for hackathons (includes online/virtual)
        self.target_locations = [
            # Physical locations
            'san francisco', 'sf', 'bay area', 'silicon valley', 'california', 'ca',
            'new york', 'ny', 'nyc', 'new york city', 'manhattan', 'brooklyn',
            # Online/virtual locations
            'online', 'virtual', 'remote', 'worldwide', 'global'
        ]
        
        # Hackathons generally don't exclude online events
        self.excluded_locations = []
        
        # Trusted domains for hackathons
        self.trusted_domains = {
            'devpost.com': 0.95,
            'mlh.io': 0.95,
            'eventbrite.com': 0.7,
            'hackerearth.com': 0.8,
            'challengepost.com': 0.9
        }
        
        # Hackathon-specific sources
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


class EventTypeConfigManager:
    """Manager class for accessing event type configurations."""
    
    _configs = {
        'conference': ConferenceConfig(),
        'hackathon': HackathonConfig()
    }
    
    @classmethod
    def get_config(cls, event_type: str) -> EventTypeConfig:
        """
        Get configuration for specified event type.
        
        Args:
            event_type: Type of event ('conference' or 'hackathon')
            
        Returns:
            Event type configuration object
            
        Raises:
            ValueError: If event type is not supported
        """
        if event_type not in cls._configs:
            raise ValueError(f"Unsupported event type: {event_type}. "
                           f"Supported types: {list(cls._configs.keys())}")
        
        return cls._configs[event_type]
    
    @classmethod
    def get_all_configs(cls) -> Dict[str, EventTypeConfig]:
        """Get all available event type configurations."""
        return cls._configs.copy()
    
    @classmethod
    def register_config(cls, event_type: str, config: EventTypeConfig):
        """
        Register a new event type configuration.
        
        Args:
            event_type: Name of the event type
            config: Configuration object for the event type
        """
        cls._configs[event_type] = config


# Pre-instantiated configurations for easy access
CONFERENCE_CONFIG = ConferenceConfig()
HACKATHON_CONFIG = HackathonConfig()

# Configuration lookup dictionary
EVENT_CONFIGS = {
    'conference': CONFERENCE_CONFIG,
    'hackathon': HACKATHON_CONFIG
}


def get_event_config(event_type: str) -> EventTypeConfig:
    """
    Convenience function to get event configuration.
    
    Args:
        event_type: Type of event ('conference' or 'hackathon')
        
    Returns:
        Event type configuration object
    """
    return EventTypeConfigManager.get_config(event_type)


# NOTE: This configuration module centralizes all event-type parameters.
# Testing considerations:
# - Configuration loading and access patterns
# - Event type validation logic  
# - Parameter completeness for each event type
# Manual testing recommended for: Configuration consistency, missing parameters 