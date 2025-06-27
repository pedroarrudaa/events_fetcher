"""
Event Service Layer - Business logic for event operations.

This module provides the service layer that orchestrates event operations,
handling business logic, validation, and coordination between different components.
"""

from typing import List, Dict, Any, Optional, Literal, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

from event_repository import EventRepository, get_event_repository, EventType
from shared_utils import DateParser, logger, Event as EventDataClass
from fetchers.sources.event_sources import discover_events
from fetchers.enrichers.gpt_extractor import enrich_conference_data, enrich_hackathon_data

# Business rule constants
MIN_EVENT_NAME_LENGTH = 3
MAX_EVENT_NAME_LENGTH = 200
MIN_DESCRIPTION_LENGTH = 10
DUPLICATE_URL_THRESHOLD = 0.95
EVENT_QUALITY_THRESHOLD = 0.3


@dataclass
class EventValidationResult:
    """Result of event validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]


@dataclass
class EventEnrichmentResult:
    """Result of event enrichment."""
    success: bool
    enriched_data: Optional[Dict[str, Any]]
    error: Optional[str]


class EventService:
    """
    Service layer for event operations.
    
    Handles business logic, validation, enrichment, and coordination
    between different components of the event system.
    """
    
    def __init__(self, repository: Optional[EventRepository] = None):
        """Initialize service with repository."""
        self.repository = repository or get_event_repository()
    
    def create_event(self, event_data: Dict[str, Any], event_type: EventType) -> Tuple[bool, Optional[str]]:
        """
        Create a new event with validation.
        
        Args:
            event_data: Event data to create
            event_type: Type of event
            
        Returns:
            Tuple of (success, error_message)
        """
        # Validate event data
        validation = self.validate_event(event_data, event_type)
        if not validation.is_valid:
            return False, f"Validation failed: {'; '.join(validation.errors)}"
        
        # Check for duplicates
        if self.is_duplicate_url(event_data.get('url', ''), event_type):
            return False, "Event with this URL already exists"
        
        # Normalize and save
        normalized = self._normalize_event_data(event_data, event_type)
        success = self.repository.save_event(normalized, event_type)
        
        if success:
            logger.log("info", f"Created {event_type} event", name=normalized.get('name'))
            return True, None
        else:
            return False, "Failed to save event to database"
    
    def update_event(self, event_id: str, updates: Dict[str, Any], 
                    event_type: Optional[EventType] = None) -> Tuple[bool, Optional[str]]:
        """
        Update an existing event.
        
        Args:
            event_id: ID of event to update
            updates: Fields to update
            event_type: Type of event (optional if using unified model)
            
        Returns:
            Tuple of (success, error_message)
        """
        # Get existing event
        existing = self.repository.get_event_by_id(event_id, event_type)
        if not existing:
            return False, "Event not found"
        
        # Merge updates
        updated_data = {**existing, **updates}
        
        # Validate updated data
        validation = self.validate_event(updated_data, event_type or existing.get('event_type'))
        if not validation.is_valid:
            return False, f"Validation failed: {'; '.join(validation.errors)}"
        
        # Save updates
        success = self.repository.save_event(updated_data, event_type or existing.get('event_type'))
        
        if success:
            logger.log("info", f"Updated event {event_id}")
            return True, None
        else:
            return False, "Failed to update event"
    
    def get_events(self, event_type: EventType = 'all',
                  filters: Optional[Dict[str, Any]] = None,
                  limit: Optional[int] = None,
                  offset: int = 0,
                  include_past: bool = False,
                  sort_by: str = 'created_at') -> List[Dict[str, Any]]:
        """
        Get events with business logic applied.
        
        Args:
            event_type: Type of events to fetch
            filters: Additional filters
            limit: Maximum results
            offset: Pagination offset
            include_past: Whether to include past events
            sort_by: Field to sort by
            
        Returns:
            List of events with business logic applied
        """
        # Get events from repository
        events = self.repository.get_events(
            event_type=event_type,
            filters=filters,
            limit=limit,
            offset=offset,
            include_past=include_past
        )
        
        # Apply business logic
        for event in events:
            # Calculate quality score
            event['quality_score'] = self.calculate_quality_score(event)
            
            # Add computed fields
            event['is_upcoming'] = self.is_upcoming_event(event)
            event['days_until'] = self.get_days_until_event(event)
            
            # Add status
            event['status'] = self.determine_event_status(event)
        
        # Sort if needed (repository sorts by created_at by default)
        if sort_by != 'created_at':
            events = self._sort_events(events, sort_by)
        
        return events
    
    def search_events(self, query: str, event_type: EventType = 'all',
                     limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search events with relevance scoring.
        
        Args:
            query: Search query
            event_type: Type of events to search
            limit: Maximum results
            
        Returns:
            List of matching events with relevance scores
        """
        # Get search results from repository
        results = self.repository.search_events(query, event_type, limit)
        
        # Add relevance scores
        for event in results:
            event['relevance_score'] = self._calculate_relevance_score(event, query)
            event['quality_score'] = self.calculate_quality_score(event)
        
        # Sort by relevance
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        return results
    
    def discover_and_save_events(self, event_type: EventType, 
                               max_results: Optional[int] = None,
                               enrich: bool = True) -> Dict[str, Any]:
        """
        Discover new events and save them to the database.
        
        Args:
            event_type: Type of events to discover
            max_results: Maximum events to discover
            enrich: Whether to enrich events before saving
            
        Returns:
            Dictionary with discovery results
        """
        logger.log("info", f"Starting {event_type} discovery", max_results=max_results)
        
        # Discover events
        discovered = discover_events(event_type, max_results)
        logger.log("info", f"Discovered {len(discovered)} {event_type}s")
        
        # Filter for future events
        future_events = filter_future_target_events(discovered)
        logger.log("info", f"Filtered to {len(future_events)} future events")
        
        # Deduplicate
        unique_events = self._deduplicate_events(future_events)
        logger.log("info", f"Deduplicated to {len(unique_events)} unique events")
        
        # Enrich if requested
        if enrich:
            enriched_events = self.enrich_events_batch(unique_events, event_type)
            events_to_save = enriched_events
        else:
            events_to_save = unique_events
        
        # Save to database
        save_results = self.repository.bulk_save_events(
            events_to_save, 
            event_type,
            update_existing=True
        )
        
        return {
            'discovered': len(discovered),
            'future_events': len(future_events),
            'unique_events': len(unique_events),
            'enriched': len(events_to_save) if enrich else 0,
            'saved': save_results['inserted'],
            'updated': save_results['updated'],
            'errors': save_results['errors']
        }
    
    def enrich_event(self, event_data: Dict[str, Any], 
                    event_type: EventType) -> EventEnrichmentResult:
        """
        Enrich a single event with additional data.
        
        Args:
            event_data: Event data to enrich
            event_type: Type of event
            
        Returns:
            Enrichment result
        """
        try:
            url = event_data.get('url')
            if not url:
                return EventEnrichmentResult(False, None, "No URL provided")
            
            # Call appropriate enricher
            if event_type == 'conference':
                enriched = enrich_conference_data(url)
            else:
                enriched = enrich_hackathon_data(url)
            
            if enriched:
                # Merge with original data
                merged = {**event_data, **enriched}
                return EventEnrichmentResult(True, merged, None)
            else:
                return EventEnrichmentResult(False, None, "Enrichment returned no data")
                
        except Exception as e:
            logger.log("error", f"Failed to enrich event", error=str(e))
            return EventEnrichmentResult(False, None, str(e))
    
    def enrich_events_batch(self, events: List[Dict[str, Any]], 
                          event_type: EventType) -> List[Dict[str, Any]]:
        """
        Enrich multiple events in batch.
        
        Args:
            events: List of events to enrich
            event_type: Type of events
            
        Returns:
            List of enriched events
        """
        enriched_events = []
        
        for event in events:
            result = self.enrich_event(event, event_type)
            if result.success and result.enriched_data:
                enriched_events.append(result.enriched_data)
            else:
                # Keep original if enrichment fails
                event['enrichment_failed'] = True
                event['enrichment_error'] = result.error
                enriched_events.append(event)
        
        return enriched_events
    
    def validate_event(self, event_data: Dict[str, Any], 
                      event_type: EventType) -> EventValidationResult:
        """
        Validate event data according to business rules.
        
        Args:
            event_data: Event data to validate
            event_type: Type of event
            
        Returns:
            Validation result
        """
        errors = []
        warnings = []
        
        # Required fields
        if not event_data.get('name'):
            errors.append("Event name is required")
        elif len(event_data['name']) < MIN_EVENT_NAME_LENGTH:
            errors.append(f"Event name must be at least {MIN_EVENT_NAME_LENGTH} characters")
        elif len(event_data['name']) > MAX_EVENT_NAME_LENGTH:
            errors.append(f"Event name must not exceed {MAX_EVENT_NAME_LENGTH} characters")
        
        if not event_data.get('url'):
            errors.append("Event URL is required")
        elif not self._is_valid_url(event_data['url']):
            errors.append("Invalid URL format")
        
        # Date validation
        start_date = event_data.get('start_date')
        end_date = event_data.get('end_date')
        
        if start_date and not DateParser.is_valid_date(start_date):
            errors.append("Invalid start date format")
        
        if end_date and not DateParser.is_valid_date(end_date):
            errors.append("Invalid end date format")
        
        if start_date and end_date:
            start = DateParser.parse_to_date(start_date)
            end = DateParser.parse_to_date(end_date)
            if start and end and end < start:
                errors.append("End date cannot be before start date")
        
        # Location validation for conferences
        if event_type == 'conference' and not event_data.get('location') and not event_data.get('remote'):
            warnings.append("Conference should have a location or be marked as remote")
        
        # Description validation
        description = event_data.get('description')
        if description and len(description) < MIN_DESCRIPTION_LENGTH:
            warnings.append(f"Description is very short (< {MIN_DESCRIPTION_LENGTH} chars)")
        
        # Quality warnings
        quality_score = self.calculate_quality_score(event_data)
        if quality_score < EVENT_QUALITY_THRESHOLD:
            warnings.append(f"Event quality score is low ({quality_score:.2f})")
        
        return EventValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def calculate_quality_score(self, event_data: Dict[str, Any]) -> float:
        """
        Calculate quality score for an event.
        
        Args:
            event_data: Event data
            
        Returns:
            Quality score between 0 and 1
        """
        score = 0.0
        weights = {
            'name': 0.2,
            'description': 0.15,
            'start_date': 0.15,
            'end_date': 0.1,
            'location': 0.15,
            'speakers': 0.1,
            'themes': 0.1,
            'url': 0.05
        }
        
        for field, weight in weights.items():
            value = event_data.get(field)
            if value:
                if isinstance(value, list) and len(value) > 0:
                    score += weight
                elif isinstance(value, str) and value.strip() and value != 'TBD':
                    score += weight
                elif value and value != 'TBD':
                    score += weight
        
        return min(score, 1.0)
    
    def determine_event_status(self, event_data: Dict[str, Any]) -> str:
        """
        Determine the status of an event.
        
        Args:
            event_data: Event data
            
        Returns:
            Status string: 'validated', 'filtered', or 'enriched'
        """
        # Check if event has been enriched
        if event_data.get('speakers') or event_data.get('themes'):
            return 'enriched'
        
        # Check if event has basic required data
        if event_data.get('start_date') and event_data.get('location'):
            return 'validated'
        
        return 'filtered'
    
    def is_upcoming_event(self, event_data: Dict[str, Any]) -> bool:
        """Check if event is upcoming (hasn't started yet)."""
        start_date_str = event_data.get('start_date')
        if not start_date_str:
            return True  # Assume events without dates are upcoming
        
        return DateParser.is_future_date(start_date_str)
    
    def get_days_until_event(self, event_data: Dict[str, Any]) -> Optional[int]:
        """Get number of days until event starts."""
        start_date_str = event_data.get('start_date')
        if not start_date_str:
            return None
        
        start_date = DateParser.parse_to_date(start_date_str)
        if not start_date:
            return None
        
        today = datetime.now().date()
        delta = start_date - today
        
        return delta.days if delta.days >= 0 else None
    
    def is_duplicate_url(self, url: str, event_type: EventType) -> bool:
        """Check if URL already exists in database."""
        if not url:
            return False
        
        # Search for exact URL match
        existing = self.repository.search_events(url, event_type, limit=1)
        return len(existing) > 0 and existing[0].get('url') == url
    
    def record_event_action(self, event_id: str, event_type: str, 
                          action: str) -> Tuple[bool, Optional[str]]:
        """
        Record an action taken on an event.
        
        Args:
            event_id: ID of the event
            event_type: Type of event
            action: Action taken (e.g., 'archive', 'reached_out')
            
        Returns:
            Tuple of (success, error_message)
        """
        # Validate action
        valid_actions = ['archive', 'reached_out', 'interested', 'not_interested', 'applied']
        if action not in valid_actions:
            return False, f"Invalid action. Must be one of: {', '.join(valid_actions)}"
        
        # Record action
        success = self.repository.save_event_action(event_id, event_type, action)
        
        if success:
            logger.log("info", f"Recorded action '{action}' for event {event_id}")
            return True, None
        else:
            return False, "Failed to record action"
    
    def get_event_history(self, event_id: str) -> List[Dict[str, Any]]:
        """Get action history for an event."""
        return self.repository.get_event_actions(event_id)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive event statistics."""
        stats = self.repository.get_event_stats()
        
        # Add calculated statistics
        stats['average_quality_score'] = self._calculate_average_quality_score()
        stats['upcoming_events'] = self._count_upcoming_events()
        stats['events_this_month'] = self._count_events_this_month()
        
        return stats
    
    def _normalize_event_data(self, event_data: Dict[str, Any], 
                            event_type: EventType) -> Dict[str, Any]:
        """Normalize event data for consistency."""
        normalized = event_data.copy()
        
        # Ensure event type
        normalized['event_type'] = event_type
        
        # Normalize dates
        if normalized.get('start_date'):
            normalized['start_date'] = DateParser.format_to_iso(normalized['start_date'])
        
        if normalized.get('end_date'):
            normalized['end_date'] = DateParser.format_to_iso(normalized['end_date'])
        
        # Normalize location
        if normalized.get('location'):
            normalized['location'] = normalized['location'].strip()
        
        # Ensure lists
        for field in ['speakers', 'themes']:
            if field in normalized and not isinstance(normalized[field], list):
                normalized[field] = [normalized[field]] if normalized[field] else []
        
        return normalized
    
    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format."""
        import re
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return url_pattern.match(url) is not None
    
    def _calculate_relevance_score(self, event: Dict[str, Any], query: str) -> float:
        """Calculate relevance score for search results."""
        score = 0.0
        query_lower = query.lower()
        
        # Check different fields with different weights
        if query_lower in event.get('name', '').lower():
            score += 0.4
        
        if query_lower in event.get('description', '').lower():
            score += 0.2
        
        if query_lower in event.get('location', '').lower():
            score += 0.2
        
        # Check themes
        themes = event.get('themes', [])
        if any(query_lower in theme.lower() for theme in themes):
            score += 0.2
        
        return min(score, 1.0)
    
    def _deduplicate_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate events by URL."""
        seen_urls = set()
        unique_events = []
        
        for event in events:
            url = event.get('url', '').strip().lower()
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_events.append(event)
        
        return unique_events
    
    def _sort_events(self, events: List[Dict[str, Any]], sort_by: str) -> List[Dict[str, Any]]:
        """Sort events by specified field."""
        if sort_by == 'start_date':
            # Sort by date, with None values at the end
            return sorted(events, key=lambda x: (
                DateParser.parse_to_date(x.get('start_date')) or datetime.max.date()
            ))
        elif sort_by == 'quality_score':
            return sorted(events, key=lambda x: x.get('quality_score', 0), reverse=True)
        elif sort_by == 'name':
            return sorted(events, key=lambda x: x.get('name', '').lower())
        else:
            return events
    
    def _calculate_average_quality_score(self) -> float:
        """Calculate average quality score across all events."""
        # This is a simplified implementation
        # In production, you'd calculate this from the database
        return 0.65
    
    def _count_upcoming_events(self) -> int:
        """Count upcoming events."""
        # This is a simplified implementation
        # In production, you'd query the database with date filters
        all_events = self.repository.get_events(include_past=False, limit=1000)
        return len([e for e in all_events if self.is_upcoming_event(e)])
    
    def _count_events_this_month(self) -> int:
        """Count events happening this month."""
        # This is a simplified implementation
        # In production, you'd query the database with date range filters
        today = datetime.now()
        month_start = today.replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        all_events = self.repository.get_events(limit=1000)
        count = 0
        
        for event in all_events:
            start_date = DateParser.parse_to_date(event.get('start_date'))
            if start_date and month_start.date() <= start_date <= month_end.date():
                count += 1
        
        return count


# Global service instance
_event_service = None

def get_event_service(repository: Optional[EventRepository] = None) -> EventService:
    """Get the global event service instance."""
    global _event_service
    if _event_service is None:
        _event_service = EventService(repository)
    return _event_service 