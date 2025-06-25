"""
Streamlined event filtering utilities for conferences and hackathons.
"""
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Set, Optional
from dataclasses import dataclass, field
from functools import lru_cache
from shared_utils import DateParser

@dataclass
class FilterConfig:
    """Configuration for event filtering."""
    target_locations: List[str] = field(default_factory=lambda: [
        'san francisco', 'sf', 'bay area', 'nyc', 'new york', 'manhattan',
        'remote'
    ])

    invalid_patterns: List[str] = field(default_factory=lambda: [
        r'^test\s+event', r'^mock\s+', r'^placeholder', r'^example\s+', r'^demo\s+',
        r'^online$', r'^virtual$', r'^remote$', r'^hackathon$', r'^event$',
        r'^.{1,3}$', r'^[\s\-_]*$', r'^https?://[^/]+/?$', r'/test', r'/demo'
    ])
    
    non_hackathon_keywords: List[str] = field(default_factory=lambda: [
        'summit', 'conference', 'workshop', 'seminar', 'expo', 'meetup',
        'symposium', 'forum', 'congress', 'webinar', 'masterclass', 'course'
    ])

class EventFilter:
    """Enhanced event filtering with tech relevance and location standardization."""
    
    # Non-tech keywords that should exclude events (unless combined with tech terms)
    NON_TECH_KEYWORDS = {
        'escrow', 'real estate', 'property', 'mortgage', 'loan', 'banking', 'insurance',
        'accounting', 'tax', 'legal', 'law', 'medical', 'healthcare', 'pharmacy',
        'restaurant', 'food service', 'retail', 'fashion', 'beauty', 'cosmetics',
        'construction', 'plumbing', 'electrical', 'hvac', 'automotive', 'mechanic',
        'fitness', 'yoga', 'wellness', 'spa', 'travel', 'tourism', 'hotel',
        'education', 'teaching', 'k-12', 'elementary', 'middle school', 'high school',
        'nonprofit', 'charity', 'fundraising', 'volunteer', 'community service',
        'sports', 'recreation', 'entertainment', 'music', 'art', 'photography',
        'training course', 'certification course', 'professional training',
        'essentials training', 'foundation training', 'learning course', 'exin bcs',
        'bcs training', 'certification program', 'training program'
    }
    
    # Tech keywords that should preserve events even if non-tech keywords present
    TECH_KEYWORDS = {
        'ai', 'artificial intelligence', 'machine learning', 'ml', 'deep learning',
        'data science', 'analytics', 'big data', 'blockchain', 'cryptocurrency',
        'fintech', 'regtech', 'insurtech', 'proptech', 'edtech', 'healthtech',
        'software', 'programming', 'coding', 'development', 'api', 'cloud',
        'devops', 'cybersecurity', 'iot', 'internet of things', 'robotics',
        'automation', 'digital', 'tech', 'technology', 'startup', 'venture',
        'saas', 'platform', 'algorithm', 'neural network', 'nlp', 'computer vision'
    }
    
    # Valid target locations
    TARGET_LOCATIONS = {'San Francisco', 'New York'}
    
    # Location mapping for standardization
    LOCATION_MAPPINGS = {
        # San Francisco variations
        'san francisco': 'San Francisco',
        'sf': 'San Francisco', 
        'san francisco, ca': 'San Francisco',
        'san francisco, california': 'San Francisco',
        'san francisco bay area': 'San Francisco',
        'silicon valley': 'San Francisco',
        'silicon valley, california': 'San Francisco',
        'palo alto': 'San Francisco',
        'mountain view': 'San Francisco',
        'sunnyvale': 'San Francisco',
        'cupertino': 'San Francisco',
        'redwood city': 'San Francisco',
        'san jose': 'San Francisco',
        
        # New York variations  
        'new york': 'New York',
        'ny': 'New York',
        'nyc': 'New York',
        'new york city': 'New York',
        'new york, ny': 'New York',
        'manhattan': 'New York',
        'brooklyn': 'New York',
        'queens': 'New York'
    }
    
    def __init__(self, config: FilterConfig = None):
        self.config = config or FilterConfig()
        self.seen_urls: Set[str] = set()
        
        # Compile patterns once for performance
        self._invalid_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.config.invalid_patterns]
        self._location_pattern = '|'.join(re.escape(loc) for loc in self.config.target_locations)
        
        self.date_parser = DateParser()
    
    def filter_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply all filters: future dates, target locations, tech relevance."""
        filtered_events = []
        
        for event in events:
            # Skip if not future date
            if not self._is_future_event(event.get('start_date', '')):
                continue
            
            # Skip if not target location
            if not self.is_target_location(event.get('location', '')):
                continue
            
            # Skip if not tech relevant
            if not self.is_tech_relevant(
                event.get('name', ''), 
                event.get('description', '')
            ):
                continue
            
            # Standardize location for consistency
            standardized_location = self.standardize_location(event.get('location', ''))
            if standardized_location:
                event['location'] = standardized_location
            
            filtered_events.append(event)
        
        return filtered_events
    
    def _is_future_event(self, event_date: str) -> bool:
        """Check if event date is in the future."""
        return self.date_parser.is_future_date(event_date)
    
    def is_tech_relevant(self, event_name: str, description: str = "") -> bool:
        """Check if event is tech-relevant using keyword analysis."""
        text = f"{event_name} {description}".lower()
        
        # Check for tech keywords
        has_tech_keywords = any(keyword in text for keyword in self.TECH_KEYWORDS)
        
        # Check for non-tech keywords
        has_non_tech_keywords = any(keyword in text for keyword in self.NON_TECH_KEYWORDS)
        
        # Allow if has tech keywords, or no non-tech keywords found
        return has_tech_keywords or not has_non_tech_keywords
    
    def standardize_location(self, location: str) -> Optional[str]:
        """Standardize location to San Francisco or New York, return None if not target location."""
        if not location or location.lower() in ['tbd', 'none', 'null']:
            return None
            
        location_lower = location.lower().strip()
        
        # Direct mapping
        if location_lower in self.LOCATION_MAPPINGS:
            return self.LOCATION_MAPPINGS[location_lower]
        
        # Fuzzy matching for variations
        for pattern, standard in self.LOCATION_MAPPINGS.items():
            if pattern in location_lower:
                return standard
        
        return None  # Not a target location
    
    def is_target_location(self, location: str) -> bool:
        """Check if location is in target cities (SF or NY)."""
        standardized = self.standardize_location(location)
        return standardized in self.TARGET_LOCATIONS
    
    def reset_deduplication(self):
        """Reset URL deduplication tracking."""
        self.seen_urls.clear()
    
    def _has_meaningful_name(self, name: str) -> bool:
        """Check if name is meaningful and not generic."""
        if not name or len(name.strip()) < 4:
            return False
        
        name_lower = name.lower().strip()
        
        # Check against invalid patterns
        if any(pattern.match(name_lower) for pattern in self._invalid_patterns):
            return False
        
        # Must have meaningful words beyond common ones
        meaningful_words = [w for w in re.findall(r'\b[a-zA-Z]{3,}\b', name)
                          if w.lower() not in {'hackathon', 'hack', 'the', 'and', 'for', 'in', 'on', 'at', 'of'}]
        
        return len(meaningful_words) >= 1
    
    def _has_valid_url(self, url: str) -> bool:
        """Check if URL is valid and specific."""
        if not url or not url.strip():
            return False
        
        url_lower = url.lower()
        
        # Check against invalid URL patterns
        return not any(pattern.search(url_lower) for pattern in self._invalid_patterns if r'http' in pattern.pattern)
    
    def _has_sufficient_data(self, event: Dict[str, Any]) -> bool:
        """Check if event has sufficient data quality."""
        required_fields = ['name', 'url']
        if not all(event.get(field) for field in required_fields):
            return False
        
        # At least one of: date info, location, or description
        optional_data = [
            event.get('start_date'), event.get('date'), event.get('location'),
            event.get('city'), event.get('description')
        ]
        
        return any(data and str(data).strip() not in {'TBD', 'N/A', ''} for data in optional_data)
    
    def _is_unique(self, url: str) -> bool:
        """Check URL uniqueness."""
        if not url:
            return False
        
        normalized_url = url.lower().strip().rstrip('/')
        if normalized_url in self.seen_urls:
            return False
        
        self.seen_urls.add(normalized_url)
        return True
    
    def _is_actually_hackathon(self, event: Dict[str, Any]) -> bool:
        """Check if event is actually a hackathon."""
        content = ' '.join(filter(None, [
            str(event.get('name', '')),
            str(event.get('description', ''))
        ])).lower()
        
        # Must not be primarily a non-hackathon event
        non_hackathon_count = sum(1 for keyword in self.config.non_hackathon_keywords 
                                 if keyword in content)
        
        # Allow some conference-like keywords but not too many
        return non_hackathon_count <= 2

# Convenience functions
def filter_future_target_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter events to only future events in target locations."""
    filter_instance = EventFilter()
    return filter_instance.filter_events(events)

def create_custom_filter(target_locations: List[str] = None, 
                        additional_invalid_patterns: List[str] = None) -> EventFilter:
    """Create a custom event filter with specific configuration."""
    config = FilterConfig()
    
    if target_locations:
        config.target_locations = target_locations
    
    if additional_invalid_patterns:
        config.invalid_patterns.extend(additional_invalid_patterns)
    
    return EventFilter(config)

# Legacy compatibility
def is_target_location(event: Dict[str, Any]) -> Tuple[bool, str]:
    """Legacy function for backward compatibility."""
    filter_instance = EventFilter()
    result = filter_instance.is_target_location(event.get('location', ''))
    return result, "target location" if result else "not target location"

def is_future_event(event: Dict[str, Any]) -> Tuple[bool, str]:
    """Legacy function for backward compatibility."""
    filter_instance = EventFilter()
    result = filter_instance._is_future_event(event.get('start_date', ''))
    return result, "future event" if result else "past event" 