"""
Event Filters - Filtering logic for events.

This module contains all the filtering logic for events, including
date filtering, location filtering, and quality filtering.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, date

from shared_utils import DateParser, logger


def filter_future_target_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter events to only include future events that match target criteria.
    
    Args:
        events: List of event dictionaries
        
    Returns:
        List of filtered events
    """
    filtered_events = []
    
    for event in events:
        # Check if event is in the future
        if not is_future_event(event):
            continue
        
        # Check if event matches target location criteria
        if not is_target_location(event):
            continue
        
        # Check minimum quality
        if not meets_quality_threshold(event):
            continue
        
        filtered_events.append(event)
    
    logger.log("info", f"Filtered {len(events)} events to {len(filtered_events)} future target events")
    return filtered_events


def is_future_event(event: Dict[str, Any]) -> bool:
    """
    Check if an event is in the future.
    
    Args:
        event: Event dictionary
        
    Returns:
        True if event is in the future, False otherwise
    """
    start_date_str = event.get('start_date')
    
    # If no start date, assume it's future
    if not start_date_str or start_date_str == 'TBD':
        return True
    
    return DateParser.is_future_date(start_date_str)


def is_target_location(event: Dict[str, Any]) -> bool:
    """
    Check if event is in a target location.
    
    For conferences: Must be in SF/NYC or remote
    For hackathons: Can be anywhere including online
    
    Args:
        event: Event dictionary
        
    Returns:
        True if event is in target location
    """
    event_type = event.get('event_type', event.get('source', 'unknown'))
    location = (event.get('location') or '').lower()
    is_remote = event.get('remote', False)
    
    # Hackathons can be anywhere
    if 'hackathon' in event_type:
        return True
    
    # Conferences must be in target locations
    target_locations = [
        'san francisco', 'sf', 'bay area', 'silicon valley',
        'palo alto', 'mountain view', 'santa clara', 'san jose',
        'new york', 'nyc', 'manhattan', 'brooklyn', 'new york city'
    ]
    
    # Check if remote/online
    if is_remote or any(term in location for term in ['online', 'virtual', 'remote']):
        return True
    
    # Check if in target location
    return any(target in location for target in target_locations)


def meets_quality_threshold(event: Dict[str, Any], threshold: float = 0.2) -> bool:
    """
    Check if event meets minimum quality threshold.
    
    Args:
        event: Event dictionary
        threshold: Minimum quality score (default 0.2)
        
    Returns:
        True if event meets quality threshold
    """
    # Calculate basic quality score if not present
    if 'quality_score' not in event:
        score = calculate_basic_quality_score(event)
    else:
        score = event.get('quality_score', 0)
    
    return score >= threshold


def calculate_basic_quality_score(event: Dict[str, Any]) -> float:
    """
    Calculate a basic quality score for an event.
    
    Args:
        event: Event dictionary
        
    Returns:
        Quality score between 0 and 1
    """
    score = 0.0
    
    # Has name
    if event.get('name') and event['name'] != 'TBD':
        score += 0.3
    
    # Has URL
    if event.get('url'):
        score += 0.2
    
    # Has date
    if event.get('start_date') and event['start_date'] != 'TBD':
        score += 0.2
    
    # Has location
    if event.get('location') and event['location'] != 'TBD':
        score += 0.2
    
    # Has description
    if event.get('description'):
        score += 0.1
    
    return min(score, 1.0)


def filter_by_date_range(events: List[Dict[str, Any]], 
                        start_date: Optional[date] = None,
                        end_date: Optional[date] = None) -> List[Dict[str, Any]]:
    """
    Filter events by date range.
    
    Args:
        events: List of event dictionaries
        start_date: Start of date range (inclusive)
        end_date: End of date range (inclusive)
        
    Returns:
        List of events within date range
    """
    filtered = []
    
    for event in events:
        event_start = DateParser.parse_to_date(event.get('start_date'))
        
        if not event_start:
            # Include events without dates if no start_date filter
            if not start_date:
                filtered.append(event)
            continue
        
        # Check date range
        if start_date and event_start < start_date:
            continue
        
        if end_date and event_start > end_date:
            continue
        
        filtered.append(event)
    
    return filtered


def filter_by_keywords(events: List[Dict[str, Any]], 
                      keywords: List[str],
                      fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Filter events by keywords in specified fields.
    
    Args:
        events: List of event dictionaries
        keywords: List of keywords to search for
        fields: List of fields to search in (default: name, description, themes)
        
    Returns:
        List of events matching keywords
    """
    if not keywords:
        return events
    
    if not fields:
        fields = ['name', 'description', 'themes']
    
    filtered = []
    keywords_lower = [k.lower() for k in keywords]
    
    for event in events:
        # Build searchable text from specified fields
        search_text = ''
        for field in fields:
            value = event.get(field)
            if value:
                if isinstance(value, list):
                    search_text += ' '.join(str(v) for v in value) + ' '
                else:
                    search_text += str(value) + ' '
        
        search_text = search_text.lower()
        
        # Check if any keyword matches
        if any(keyword in search_text for keyword in keywords_lower):
            filtered.append(event)
    
    return filtered


def filter_tech_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter events to only include tech-related events.
    
    Args:
        events: List of event dictionaries
        
    Returns:
        List of tech-related events
    """
    tech_keywords = [
        'ai', 'artificial intelligence', 'machine learning', 'ml', 'deep learning',
        'data science', 'data', 'analytics', 'tech', 'technology', 'software',
        'programming', 'coding', 'developer', 'engineering', 'startup', 'innovation',
        'blockchain', 'crypto', 'web3', 'cloud', 'devops', 'security', 'cyber',
        'iot', 'robotics', 'ar', 'vr', 'metaverse', 'quantum', 'api', 'saas',
        'fintech', 'healthtech', 'edtech', 'biotech', 'cleantech'
    ]
    
    non_tech_keywords = [
        'real estate', 'property', 'mortgage', 'insurance', 'accounting',
        'legal', 'law', 'fitness', 'gym', 'yoga', 'cooking', 'fashion',
        'beauty', 'cosmetics', 'entertainment', 'music', 'film', 'art',
        'painting', 'sculpture', 'dance', 'theater', 'literature'
    ]
    
    filtered = []
    
    for event in events:
        # Build searchable text
        search_text = f"{event.get('name', '')} {event.get('description', '')} {' '.join(event.get('themes', []))}"
        search_text = search_text.lower()
        
        # Skip if contains non-tech keywords
        if any(keyword in search_text for keyword in non_tech_keywords):
            continue
        
        # Include if contains tech keywords
        if any(keyword in search_text for keyword in tech_keywords):
            filtered.append(event)
    
    return filtered


def deduplicate_events(events: List[Dict[str, Any]], key: str = 'url') -> List[Dict[str, Any]]:
    """
    Remove duplicate events based on a key field.
    
    Args:
        events: List of event dictionaries
        key: Field to use for deduplication (default: 'url')
        
    Returns:
        List of unique events
    """
    seen = set()
    unique = []
    
    for event in events:
        value = event.get(key)
        if value:
            value_normalized = str(value).strip().lower()
            if value_normalized not in seen:
                seen.add(value_normalized)
                unique.append(event)
        else:
            # Keep events without the key field
            unique.append(event)
    
    return unique 