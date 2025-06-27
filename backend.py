"""
FastAPI backend for serving unified events data.

This backend now uses the EventService layer for all business logic,
providing a clean separation of concerns.
"""
import os
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from event_service import get_event_service, EventService
from event_repository import EventType
from shared_utils import logger

app = FastAPI(
    title="Events API", 
    description="Unified API for managing hackathons and conferences", 
    version="2.0.0"
)

# Get frontend URL from environment variable for production
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        FRONTEND_URL,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize service
event_service: EventService = get_event_service()


class EventResponse(BaseModel):
    """Unified event response model."""
    id: str
    title: str
    type: str  # "hackathon" or "conference"
    location: str
    start_date: str
    end_date: str
    url: str
    status: str  # "validated", "filtered", or "enriched"
    quality_score: float
    is_upcoming: bool
    days_until: Optional[int]


class EventActionRequest(BaseModel):
    """Event action request model."""
    event_id: str
    event_type: str  # "hackathon" or "conference"
    action: str  # "archive", "reached_out", etc.


class EventActionResponse(BaseModel):
    """Event action response model."""
    action: str
    timestamp: str


class EventDiscoveryRequest(BaseModel):
    """Event discovery request model."""
    event_type: str  # "hackathon" or "conference"
    max_results: Optional[int] = None
    enrich: bool = True


def event_to_response(event: Dict[str, Any]) -> EventResponse:
    """Convert service event to API response."""
    return EventResponse(
        id=event.get('id', ''),
        title=event.get('name', 'Untitled Event'),
        type=event.get('event_type', 'unknown'),
        location=event.get('location', 'TBD'),
        start_date=event.get('start_date', 'TBD'),
        end_date=event.get('end_date', 'TBD'),
        url=event.get('url', ''),
        status=event.get('status', 'filtered'),
        quality_score=event.get('quality_score', 0.0),
        is_upcoming=event.get('is_upcoming', True),
        days_until=event.get('days_until')
    )


@app.get("/events", response_model=List[EventResponse])
async def get_events(
    type_filter: Optional[str] = Query(None, description="Filter by event type: hackathon, conference"),
    location_filter: Optional[str] = Query(None, description="Filter by location"),
    status_filter: Optional[str] = Query(None, description="Filter by status: validated, filtered, enriched"),
    limit: Optional[int] = Query(None, description="Limit number of results"),
    offset: int = Query(0, description="Number of records to skip for pagination"),
    include_past: bool = Query(False, description="Include events that have already started/ended"),
    sort_by: str = Query("created_at", description="Sort by: created_at, start_date, quality_score, name")
):
    """
    Get events with filtering, pagination, and sorting.
    
    Uses the EventService for all business logic, providing consistent
    quality scores, status determination, and date calculations.
    """
    try:
        # Map type filter to EventType
        event_type: EventType = 'all'
        if type_filter:
            if type_filter.lower() == 'hackathon':
                event_type = 'hackathon'
            elif type_filter.lower() == 'conference':
                event_type = 'conference'
        
        # Build filters
        filters = {}
        if location_filter and location_filter.lower() != "all":
            filters['location'] = location_filter
        
        # Get events from service
        events = event_service.get_events(
            event_type=event_type,
            filters=filters,
            limit=limit,
            offset=offset,
            include_past=include_past,
            sort_by=sort_by
        )
        
        # Apply status filter if provided
        if status_filter and status_filter.lower() != "all":
            events = [e for e in events if e.get('status', '').lower() == status_filter.lower()]
        
        # Convert to response model
        return [event_to_response(event) for event in events]
        
    except SQLAlchemyError as e:
        logger.log("error", "Database error in /events", error=str(e))
        raise HTTPException(status_code=503, detail="Database connection error")
    except Exception as e:
        logger.log("error", "Error fetching events", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/events/search", response_model=List[EventResponse])
async def search_events(
    q: str = Query(..., description="Search query"),
    type_filter: Optional[str] = Query(None, description="Filter by event type"),
    limit: int = Query(50, description="Maximum results")
):
    """
    Search events by name, location, or description.
    
    Returns results sorted by relevance score.
    """
    try:
        # Map type filter
        event_type: EventType = 'all'
        if type_filter:
            if type_filter.lower() == 'hackathon':
                event_type = 'hackathon'
            elif type_filter.lower() == 'conference':
                event_type = 'conference'
        
        # Search using service
        results = event_service.search_events(q, event_type, limit)
        
        # Convert to response model
        return [event_to_response(event) for event in results]
        
    except Exception as e:
        logger.log("error", "Error searching events", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/events/discover")
async def discover_events(request: EventDiscoveryRequest):
    """
    Discover and save new events.
    
    This endpoint triggers event discovery, enrichment, and saving.
    """
    try:
        # Validate event type
        if request.event_type not in ['hackathon', 'conference']:
            raise HTTPException(status_code=400, detail="Invalid event type")
        
        # Run discovery
        results = event_service.discover_and_save_events(
            event_type=request.event_type,
            max_results=request.max_results,
            enrich=request.enrich
        )
        
        return {
            "success": True,
            "results": results,
            "message": f"Successfully discovered and saved {results['saved']} new {request.event_type}s"
        }
        
    except Exception as e:
        logger.log("error", "Error discovering events", error=str(e))
        raise HTTPException(status_code=500, detail=f"Discovery failed: {str(e)}")


@app.post("/event-action")
async def create_event_action(request: EventActionRequest):
    """
    Record an action taken on an event.
    
    Valid actions: archive, reached_out, interested, not_interested, applied
    """
    try:
        success, error = event_service.record_event_action(
            request.event_id,
            request.event_type,
            request.action
        )
        
        if success:
            return {"message": "Action recorded successfully", "success": True}
        else:
            raise HTTPException(status_code=400, detail=error)
            
    except Exception as e:
        logger.log("error", "Error creating event action", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/event-action/{event_id}")
async def get_event_actions(event_id: str):
    """
    Get all actions for an event.
    
    Returns the complete action history for the event.
    """
    try:
        actions = event_service.get_event_history(event_id)
        
        if actions:
            # Return the most recent action in the expected format
            latest = actions[0]
            return EventActionResponse(
                action=latest['action'],
                timestamp=latest['timestamp']
            )
        else:
            return None
            
    except Exception as e:
        logger.log("error", "Error getting event actions", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/stats")
async def get_statistics():
    """
    Get comprehensive event statistics.
    
    Returns counts, averages, and other useful metrics.
    """
    try:
        stats = event_service.get_statistics()
        return stats
        
    except Exception as e:
        logger.log("error", "Error getting statistics", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "message": "Events API is running",
        "version": "2.0.0",
        "features": ["unified-events", "search", "discovery", "actions", "statistics"]
    }


@app.get("/health")
async def health_check():
    """
    Detailed health check with database connectivity test.
    """
    try:
        # Get basic stats to test database
        stats = event_service.get_statistics()
        
        return {
            "status": "healthy",
            "database": "connected",
            "total_events": stats.get('total_events', 0),
            "hackathons": stats.get('total_hackathons', 0),
            "conferences": stats.get('total_conferences', 0),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 