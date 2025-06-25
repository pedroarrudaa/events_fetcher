"""
Streamlined event filtering utilities for conferences and hackathons.
"""
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Set
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
    """Streamlined event filter with pattern matching and quality checks."""
    
    def __init__(self, config: FilterConfig = None):
        self.config = config or FilterConfig()
        self.seen_urls: Set[str] = set()
        
        # Compile patterns once for performance
        self._invalid_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.config.invalid_patterns]
        self._location_pattern = '|'.join(re.escape(loc) for loc in self.config.target_locations)
    
    def filter_events(self, events: List[Dict[str, Any]], event_type: str = "hackathon") -> List[Dict[str, Any]]:
        """Filter events with comprehensive quality checks."""
        filtered = []
        
        for event in events:
            if self._is_high_quality(event, event_type):
                filtered.append(event)
        
        return filtered
    
    def _is_high_quality(self, event: Dict[str, Any], event_type: str) -> bool:
        """Comprehensive quality check for events."""
        checks = [
            self._has_meaningful_name(event.get('name', '')),
            self._has_valid_url(event.get('url', '')),
            self._has_sufficient_data(event),
            self._is_unique(event.get('url', '')),
            self._is_future_event(event),
            self._is_target_location(event)
        ]
        
        # For hackathons, add hackathon-specific check
        if event_type == "hackathon":
            checks.append(self._is_actually_hackathon(event))
        
        return all(checks)
    
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
    
    def _is_target_location(self, event: Dict[str, Any]) -> bool:
        """Check if event is in target location."""
        location_text = ' '.join(filter(None, [
            str(event.get('location', '')),
            str(event.get('city', '')),
            str(event.get('name', '')),
            str(event.get('description', ''))
        ])).lower()
        
        # Use compiled pattern for performance
        return bool(re.search(self._location_pattern, location_text, re.IGNORECASE))
    
    def _is_future_event(self, event: Dict[str, Any]) -> bool:
        """Check if event is in the future using unified DateParser."""
        date_fields = ['start_date', 'date', 'end_date']
        
        for field in date_fields:
            date_str = event.get(field)
            if not date_str:
                continue
            
            # Use unified DateParser for consistent parsing
            if DateParser.is_valid_date(str(date_str)):
                return DateParser.is_future_date(str(date_str))
        
        # If no valid date found, assume it's future (benefit of doubt for events without dates)
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
    
    def reset_deduplication(self):
        """Reset URL deduplication tracking."""
        self.seen_urls.clear()

# Convenience functions
def filter_future_target_events(events: List[Dict[str, Any]], event_type: str = "hackathon") -> List[Dict[str, Any]]:
    """Filter events to only include high-quality future events in target locations."""
    filter_instance = EventFilter()
    return filter_instance.filter_events(events, event_type)

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
    result = filter_instance._is_target_location(event)
    return result, "target location" if result else "not target location"

def is_future_event(event: Dict[str, Any]) -> Tuple[bool, str]:
    """Legacy function for backward compatibility."""
    filter_instance = EventFilter()
    result = filter_instance._is_future_event(event)
    return result, "future event" if result else "past event" 