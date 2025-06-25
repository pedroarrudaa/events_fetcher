"""
FastAPI backend for serving unified events data from hackathons and conferences tables.
"""
import os
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from database_utils import get_db_manager, Hackathon, Conference, save_event_action, get_event_action
from shared_utils import DateParser
from sqlalchemy.exc import SQLAlchemyError

app = FastAPI(title="Events API", description="API for managing hackathons and conferences", version="1.0.0")

# Get frontend URL from environment variable for production
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://events-dashboard-nprw.onrender.com",
        "https://events-api-nprw.onrender.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Event(BaseModel):
    """Pydantic model for unified event response."""
    id: str
    title: str
    type: str  # "hackathon" or "conference"
    location: str
    start_date: str
    end_date: str
    url: str
    status: str  # "validated", "filtered", or "enriched"

class EventActionRequest(BaseModel):
    """Pydantic model for event action requests."""
    event_id: str
    event_type: str  # "hackathon" or "conference"
    action: str  # "archive" or "reached_out"

class EventActionResponse(BaseModel):
    """Pydantic model for event action responses."""
    action: str
    timestamp: str

def normalize_event_data(event_obj, event_type: str) -> Event:
    """
    Convert database object to unified Event model.
    """
    # Handle both SQLAlchemy objects and dictionaries
    if hasattr(event_obj, '__dict__'):
        data = {
            'id': str(event_obj.id),
            'name': event_obj.name,
            'url': event_obj.url,
            'location': event_obj.location or 'TBD',
            'start_date': event_obj.start_date or 'TBD',
            'end_date': event_obj.end_date or 'TBD',
        }
    else:
        data = event_obj

    # Determine status based on data completeness
    status = "validated"  # Default status
    if not data.get('start_date') or data.get('start_date') == 'TBD':
        status = "filtered"
    elif data.get('location') and data.get('location') != 'TBD' and data.get('start_date') != 'TBD':
        status = "enriched"

    return Event(
        id=data.get('id', ''),
        title=data.get('name', 'Untitled Event'),
        type=event_type,
        location=data.get('location', 'TBD'),
        start_date=data.get('start_date', 'TBD'),
        end_date=data.get('end_date', 'TBD'),
        url=data.get('url', ''),
        status=status
    )

def parse_date_string(date_str: str) -> Optional[date]:
    """
    Parse various date string formats to datetime.date object.
    Uses unified DateParser for consistency across the application.
    """
    return DateParser.parse_to_date(date_str)

def is_event_future_only(start_date_str: str, end_date_str: str = None) -> bool:
    """
    Check if an event is in the future (hasn't started yet).
    Only return True for events that start in the future.
    Uses unified DateParser for consistency.
    """
    return DateParser.is_future_date(start_date_str)

def get_event_sort_key(event: Event) -> tuple:
    """
    Generate a sort key for events. Events with valid dates come first,
    sorted by start date. Events without valid dates come last.
    """
    start_date = parse_date_string(event.start_date)
    
    if start_date is None:
        # Events without valid dates go to the end
        return (1, date.max)
    else:
        # Events with valid dates come first, sorted by date
        return (0, start_date)

@app.get("/events", response_model=List[Event])
async def get_events(
    type_filter: Optional[str] = Query(None, description="Filter by event type: hackathon, conference"),
    location_filter: Optional[str] = Query(None, description="Filter by location"),
    status_filter: Optional[str] = Query(None, description="Filter by status: validated, filtered, enriched"),
    limit: Optional[int] = Query(None, description="Limit number of results"),
    offset: int = Query(0, description="Number of records to skip for pagination"),
    include_past: bool = Query(False, description="Include events that have already started/ended")
):
    """
    High-performance unified list of events with optimized database queries.
    Events are filtered to show only future events (that haven't started yet) by default and sorted by start date.
    """
    try:
        def get_optimized_events():
            """Get events using optimized database operations."""
            db_manager = get_db_manager()
            events = []
            
            with db_manager.get_session() as session:
                # Build efficient database filters
                def build_query(model_class):
                    query = session.query(model_class).order_by(model_class.created_at.desc())
                    
                    # Apply database-level filters for better performance
                    if location_filter and location_filter.lower() != "all":
                        query = query.filter(model_class.location.ilike(f'%{location_filter}%'))
                    
                    return query
                
                # Efficiently fetch hackathons
                if not type_filter or type_filter.lower() in ['hackathon', 'all']:
                    hackathons_query = build_query(Hackathon)
                    # Don't limit initially, we'll sort and limit later
                    if offset:
                        hackathons_query = hackathons_query.offset(offset // 2)
                    
                    # Use yield_per for memory efficiency with large datasets
                    for hackathon in hackathons_query.yield_per(100):
                        event = normalize_event_data(hackathon, "hackathon")
                        
                        # Filter out past events unless specifically requested
                        if not include_past and not is_event_future_only(event.start_date, event.end_date):
                            continue
                        
                        # Apply status filter efficiently
                        if status_filter and status_filter.lower() != "all":
                            if event.status.lower() != status_filter.lower():
                                continue
                        
                        events.append(event)
                
                # Efficiently fetch conferences
                if not type_filter or type_filter.lower() in ['conference', 'all']:
                    conferences_query = build_query(Conference)
                    if offset:
                        conferences_query = conferences_query.offset(offset // 2)
                    
                    # Use yield_per for memory efficiency
                    for conference in conferences_query.yield_per(100):
                        event = normalize_event_data(conference, "conference")
                        
                        # Filter out past events unless specifically requested
                        if not include_past and not is_event_future_only(event.start_date, event.end_date):
                            continue
                        
                        # Apply status filter efficiently
                        if status_filter and status_filter.lower() != "all":
                            if event.status.lower() != status_filter.lower():
                                continue
                        
                        events.append(event)
                
                # Sort events by start date (closest first)
                def get_sort_date(event):
                    """Get date for sorting, with fallback"""
                    parsed = parse_date_string(event.start_date)
                    if parsed is None:
                        return date.max  # Put events without dates at the end
                    return parsed
                
                # Sort events: valid dates first (by date), then events without dates
                events.sort(key=lambda event: (
                    0 if parse_date_string(event.start_date) is not None else 1,  # Valid dates first
                    get_sort_date(event),  # Then by date
                    event.title  # Then by title as tiebreaker
                ))
                
                # Apply final limit after sorting
                if limit:
                    events = events[:limit]
                
                return events
        
        return get_optimized_events()
        
    except SQLAlchemyError as e:
        print(f"ERROR: Database error in /events: {e}")
        raise HTTPException(status_code=503, detail=f"Database connection error: {str(e)}")
    except Exception as e:
        print(f"ERROR: Error fetching events: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "Events API is running", "version": "1.0.1", "sorting": "updated"}

@app.get("/health")
async def health_check():
    """Health check endpoint with database connectivity test."""
    try:
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            # Test database connection
            hackathon_count = session.query(Hackathon).count()
            conference_count = session.query(Conference).count()
        
        return {
            "status": "healthy",
            "database": "connected",
            "hackathons": hackathon_count,
            "conferences": conference_count
        }
    except Exception as e:
        return {
            "status": "healthy",
            "database": "disconnected",
            "error": str(e)
        }

@app.post("/event-action")
async def create_event_action(request: EventActionRequest):
    """
    Create a new manual action for an event.
    """
    try:
        success = save_event_action(request.event_id, request.event_type, request.action)
        
        if success:
            return {"message": "Action saved successfully", "success": True}
        else:
            raise HTTPException(status_code=400, detail="Failed to save action")
            
    except Exception as e:
        print(f"Error creating event action: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/event-action/{event_id}")
async def get_event_action_endpoint(event_id: str):
    """
    Get the latest action for an event.
    """
    try:
        action_data = get_event_action(event_id)
        
        if action_data:
            return EventActionResponse(
                action=action_data['action'],
                timestamp=action_data['timestamp']
            )
        else:
            return None
            
    except Exception as e:
        print(f"Error getting event action: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 