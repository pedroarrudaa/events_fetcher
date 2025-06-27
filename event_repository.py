"""
Event Repository Pattern - Centralized data access layer for events.

This module provides a clean interface for all event-related database operations,
abstracting away the complexity of SQL queries and providing a consistent API.
"""

from typing import List, Dict, Any, Optional, Literal, Iterator
from datetime import datetime, timedelta
from contextlib import contextmanager
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session

from database_utils import get_db_manager, Event, Hackathon, Conference, EventActions
from shared_utils import DateParser, logger

EventType = Literal['hackathon', 'conference', 'all']


class EventRepository:
    """
    Repository pattern for event data access.
    
    Provides a clean, consistent interface for all event database operations,
    supporting both the unified Event model and legacy separate tables.
    """
    
    def __init__(self, use_unified_model: bool = True):
        """
        Initialize repository.
        
        Args:
            use_unified_model: Whether to use the unified Event table or legacy separate tables
        """
        self.db_manager = get_db_manager()
        self.use_unified_model = use_unified_model
    
    @contextmanager
    def get_session(self) -> Iterator[Session]:
        """Get database session context manager."""
        with self.db_manager.get_session() as session:
            yield session
    
    def save_event(self, event_data: Dict[str, Any], event_type: EventType) -> bool:
        """
        Save a single event.
        
        Args:
            event_data: Event data dictionary
            event_type: Type of event ('hackathon' or 'conference')
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            with self.get_session() as session:
                if self.use_unified_model:
                    event_data['event_type'] = event_type
                    event = Event(**self._normalize_event_data(event_data))
                    session.add(event)
                else:
                    model_class = Hackathon if event_type == 'hackathon' else Conference
                    event = model_class(**self._normalize_event_data(event_data))
                    session.add(event)
                
                session.commit()
                return True
                
        except Exception as e:
            logger.log("error", f"Failed to save event", error=str(e))
            return False
    
    def bulk_save_events(self, events: List[Dict[str, Any]], event_type: EventType, 
                        update_existing: bool = True) -> Dict[str, int]:
        """
        Bulk save events with upsert capability.
        
        Args:
            events: List of event data dictionaries
            event_type: Type of events
            update_existing: Whether to update existing events
            
        Returns:
            Dictionary with counts of inserted, updated, and errors
        """
        if self.use_unified_model:
            # Add event_type to all events
            for event in events:
                event['event_type'] = event_type
            return self.db_manager.bulk_save_events(events, 'events', update_existing)
        else:
            table_name = 'hackathons' if event_type == 'hackathon' else 'conferences'
            return self.db_manager.bulk_save_events(events, table_name, update_existing)
    
    def get_events(self, event_type: EventType = 'all', 
                  filters: Optional[Dict[str, Any]] = None,
                  limit: Optional[int] = None,
                  offset: int = 0,
                  include_past: bool = False) -> List[Dict[str, Any]]:
        """
        Get events with flexible filtering.
        
        Args:
            event_type: Type of events to fetch ('hackathon', 'conference', or 'all')
            filters: Additional filters to apply
            limit: Maximum number of results
            offset: Number of results to skip
            include_past: Whether to include past events
            
        Returns:
            List of event dictionaries
        """
        events = []
        
        with self.get_session() as session:
            if self.use_unified_model:
                query = session.query(Event)
                
                # Apply event type filter
                if event_type != 'all':
                    query = query.filter(Event.event_type == event_type)
            else:
                # Handle legacy separate tables
                if event_type == 'all':
                    # Fetch from both tables
                    hackathons = self._get_from_legacy_table(session, Hackathon, filters, limit, offset, include_past)
                    conferences = self._get_from_legacy_table(session, Conference, filters, limit, offset, include_past)
                    
                    # Merge and sort
                    events.extend([{**h, 'event_type': 'hackathon'} for h in hackathons])
                    events.extend([{**c, 'event_type': 'conference'} for c in conferences])
                    
                    # Sort by created_at descending
                    events.sort(key=lambda x: x.get('created_at', ''), reverse=True)
                    
                    # Apply final limit
                    if limit:
                        events = events[:limit]
                    
                    return events
                else:
                    model_class = Hackathon if event_type == 'hackathon' else Conference
                    query = session.query(model_class)
            
            # Apply filters
            if filters:
                for field, value in filters.items():
                    if hasattr(query.column_descriptions[0]['type'], field):
                        query = query.filter(getattr(query.column_descriptions[0]['type'], field) == value)
            
            # Filter out past events unless requested
            if not include_past:
                # This is a simplified filter - in production you'd parse dates properly
                today = datetime.now().strftime('%Y-%m-%d')
                query = query.filter(
                    or_(
                        query.column_descriptions[0]['type'].start_date >= today,
                        query.column_descriptions[0]['type'].start_date == None
                    )
                )
            
            # Order and paginate
            query = query.order_by(query.column_descriptions[0]['type'].created_at.desc())
            
            if offset:
                query = query.offset(offset)
            
            if limit:
                query = query.limit(limit)
            
            # Convert to dictionaries
            for event in query:
                event_dict = self._model_to_dict(event)
                if self.use_unified_model:
                    events.append(event_dict)
                else:
                    event_dict['event_type'] = event_type
                    events.append(event_dict)
        
        return events
    
    def get_event_by_id(self, event_id: str, event_type: Optional[EventType] = None) -> Optional[Dict[str, Any]]:
        """Get a single event by ID."""
        with self.get_session() as session:
            if self.use_unified_model:
                event = session.query(Event).filter(Event.id == event_id).first()
                if event:
                    return self._model_to_dict(event)
            else:
                # Try both tables if event_type not specified
                if event_type == 'hackathon' or event_type is None:
                    event = session.query(Hackathon).filter(Hackathon.id == event_id).first()
                    if event:
                        result = self._model_to_dict(event)
                        result['event_type'] = 'hackathon'
                        return result
                
                if event_type == 'conference' or event_type is None:
                    event = session.query(Conference).filter(Conference.id == event_id).first()
                    if event:
                        result = self._model_to_dict(event)
                        result['event_type'] = 'conference'
                        return result
        
        return None
    
    def search_events(self, query: str, event_type: EventType = 'all', 
                     limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search events by name, location, or description.
        
        Args:
            query: Search query string
            event_type: Type of events to search
            limit: Maximum results
            
        Returns:
            List of matching events
        """
        events = []
        search_pattern = f'%{query}%'
        
        with self.get_session() as session:
            if self.use_unified_model:
                query_obj = session.query(Event)
                
                if event_type != 'all':
                    query_obj = query_obj.filter(Event.event_type == event_type)
                
                query_obj = query_obj.filter(
                    or_(
                        Event.name.ilike(search_pattern),
                        Event.location.ilike(search_pattern),
                        Event.description.ilike(search_pattern),
                        Event.city.ilike(search_pattern)
                    )
                )
                
                query_obj = query_obj.order_by(Event.created_at.desc()).limit(limit)
                
                for event in query_obj:
                    events.append(self._model_to_dict(event))
            else:
                # Search both legacy tables
                if event_type in ['hackathon', 'all']:
                    hackathon_results = self._search_legacy_table(
                        session, Hackathon, search_pattern, limit if event_type == 'hackathon' else limit // 2
                    )
                    events.extend([{**h, 'event_type': 'hackathon'} for h in hackathon_results])
                
                if event_type in ['conference', 'all']:
                    conference_results = self._search_legacy_table(
                        session, Conference, search_pattern, limit if event_type == 'conference' else limit // 2
                    )
                    events.extend([{**c, 'event_type': 'conference'} for c in conference_results])
        
        return events[:limit]
    
    def get_event_stats(self) -> Dict[str, Any]:
        """Get comprehensive event statistics."""
        stats = {}
        
        with self.get_session() as session:
            if self.use_unified_model:
                # Total events by type
                stats['total_hackathons'] = session.query(Event).filter(Event.event_type == 'hackathon').count()
                stats['total_conferences'] = session.query(Event).filter(Event.event_type == 'conference').count()
                
                # Recent events (last 30 days)
                recent_date = datetime.utcnow() - timedelta(days=30)
                stats['recent_hackathons'] = session.query(Event).filter(
                    and_(Event.event_type == 'hackathon', Event.created_at >= recent_date)
                ).count()
                stats['recent_conferences'] = session.query(Event).filter(
                    and_(Event.event_type == 'conference', Event.created_at >= recent_date)
                ).count()
                
                # Events by location
                stats['events_by_location'] = {}
                location_counts = session.query(
                    Event.location, func.count(Event.id)
                ).group_by(Event.location).all()
                
                for location, count in location_counts:
                    if location:
                        stats['events_by_location'][location] = count
            else:
                # Use legacy tables
                stats['total_hackathons'] = session.query(Hackathon).count()
                stats['total_conferences'] = session.query(Conference).count()
                
                recent_date = datetime.utcnow() - timedelta(days=30)
                stats['recent_hackathons'] = session.query(Hackathon).filter(
                    Hackathon.created_at >= recent_date
                ).count()
                stats['recent_conferences'] = session.query(Conference).filter(
                    Conference.created_at >= recent_date
                ).count()
            
            stats['total_events'] = stats['total_hackathons'] + stats['total_conferences']
            stats['recent_events'] = stats['recent_hackathons'] + stats['recent_conferences']
        
        return stats
    
    def save_event_action(self, event_id: str, event_type: str, action: str) -> bool:
        """Save an action taken on an event."""
        return self.db_manager.save_event_action(event_id, event_type, action)
    
    def get_event_actions(self, event_id: str) -> List[Dict[str, Any]]:
        """Get all actions for an event."""
        actions = []
        
        with self.get_session() as session:
            query = session.query(EventActions).filter(
                EventActions.event_id == event_id
            ).order_by(EventActions.timestamp.desc())
            
            for action in query:
                actions.append({
                    'action': action.action,
                    'timestamp': action.timestamp.isoformat(),
                    'event_type': action.event_type
                })
        
        return actions
    
    def _normalize_event_data(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize event data for database insertion."""
        normalized = {}
        
        # Map common field names
        field_mapping = {
            'title': 'name',
            'event_name': 'name',
            'event_url': 'url',
            'link': 'url',
            'venue': 'location',
            'is_remote': 'remote',
            'is_virtual': 'remote',
            'online': 'remote',
            'tags': 'themes',
            'topics': 'themes',
            'price': 'ticket_price',
            'cost': 'ticket_price'
        }
        
        # Apply field mapping
        for key, value in event_data.items():
            mapped_key = field_mapping.get(key, key)
            normalized[mapped_key] = value
        
        # Ensure required fields
        if 'name' not in normalized:
            normalized['name'] = 'Unnamed Event'
        
        if 'url' not in normalized:
            normalized['url'] = ''
        
        # Clean and validate fields
        if 'start_date' in normalized and normalized['start_date']:
            normalized['start_date'] = DateParser.format_to_iso(normalized['start_date'])
        
        if 'end_date' in normalized and normalized['end_date']:
            normalized['end_date'] = DateParser.format_to_iso(normalized['end_date'])
        
        # Ensure boolean fields
        normalized['remote'] = bool(normalized.get('remote', False))
        normalized['is_paid'] = bool(normalized.get('is_paid', False))
        
        # Ensure list fields
        if 'speakers' in normalized and not isinstance(normalized['speakers'], list):
            normalized['speakers'] = [normalized['speakers']] if normalized['speakers'] else []
        
        if 'themes' in normalized and not isinstance(normalized['themes'], list):
            normalized['themes'] = [normalized['themes']] if normalized['themes'] else []
        
        return normalized
    
    def _model_to_dict(self, model) -> Dict[str, Any]:
        """Convert SQLAlchemy model to dictionary."""
        result = {}
        
        for column in model.__table__.columns:
            value = getattr(model, column.name)
            
            # Handle datetime
            if isinstance(value, datetime):
                value = value.isoformat()
            
            result[column.name] = value
        
        return result
    
    def _get_from_legacy_table(self, session: Session, model_class, filters: Optional[Dict[str, Any]],
                              limit: Optional[int], offset: int, include_past: bool) -> List[Dict[str, Any]]:
        """Helper to get events from legacy tables."""
        query = session.query(model_class)
        
        # Apply filters
        if filters:
            for field, value in filters.items():
                if hasattr(model_class, field):
                    query = query.filter(getattr(model_class, field) == value)
        
        # Filter out past events
        if not include_past:
            today = datetime.now().strftime('%Y-%m-%d')
            query = query.filter(
                or_(
                    model_class.start_date >= today,
                    model_class.start_date == None
                )
            )
        
        # Order and paginate
        query = query.order_by(model_class.created_at.desc())
        
        if offset:
            query = query.offset(offset)
        
        if limit:
            query = query.limit(limit)
        
        return [self._model_to_dict(event) for event in query]
    
    def _search_legacy_table(self, session: Session, model_class, search_pattern: str, 
                           limit: int) -> List[Dict[str, Any]]:
        """Helper to search legacy tables."""
        query = session.query(model_class).filter(
            or_(
                model_class.name.ilike(search_pattern),
                model_class.location.ilike(search_pattern),
                model_class.description.ilike(search_pattern),
                model_class.city.ilike(search_pattern)
            )
        ).order_by(model_class.created_at.desc()).limit(limit)
        
        return [self._model_to_dict(event) for event in query]


# Global repository instance
_event_repository = None

def get_event_repository(use_unified_model: bool = True) -> EventRepository:
    """Get the global event repository instance."""
    global _event_repository
    if _event_repository is None:
        _event_repository = EventRepository(use_unified_model)
    return _event_repository 