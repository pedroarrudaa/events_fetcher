"""
FastAPI backend for serving unified events data from hackathons and conferences tables.
"""
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from database_utils import get_db_session, Hackathon, Conference, save_event_action, get_event_action
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
            'start_date': event_obj.start_date or event_obj.date or 'TBD',
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

@app.get("/events", response_model=List[Event])
async def get_events(
    type_filter: Optional[str] = Query(None, description="Filter by event type: hackathon, conference"),
    location_filter: Optional[str] = Query(None, description="Filter by location"),
    status_filter: Optional[str] = Query(None, description="Filter by status: validated, filtered, enriched"),
    limit: Optional[int] = Query(100, description="Limit number of results")
):
    """
    Get unified list of events from both hackathons and conferences tables.
    """
    try:
        session = get_db_session()
        events = []
        
        # Fetch hackathons
        hackathons_query = session.query(Hackathon)
        if limit:
            hackathons_query = hackathons_query.limit(limit // 2 if limit > 1 else 1) # Ensure at least 1 if limit is 1
        hackathons = hackathons_query.all()
        
        for hackathon in hackathons:
            event = normalize_event_data(hackathon, "hackathon")
            events.append(event)
        
        # Fetch conferences
        conferences_query = session.query(Conference)
        if limit:
            # Adjust limit for conferences based on how many hackathons were fetched
            remaining_limit = limit - len(events)
            if remaining_limit > 0:
                conferences_query = conferences_query.limit(remaining_limit)
            else: # if limit was already met by hackathons, or limit was small
                conferences_query = conferences_query.limit(limit // 2 if limit > 1 else 1)

        conferences = conferences_query.all()
        
        for conference in conferences:
            event = normalize_event_data(conference, "conference")
            events.append(event)
        
        session.close()
        
        # Apply filters
        if type_filter and type_filter.lower() != "all":
            events = [e for e in events if e.type.lower() == type_filter.lower()]
        
        if location_filter and location_filter.lower() != "all":
            events = [e for e in events if location_filter.lower() in e.location.lower()]
        
        if status_filter and status_filter.lower() != "all":
            events = [e for e in events if e.status.lower() == status_filter.lower()]
        
        return events
        
    except SQLAlchemyError as e:
        print(f"❌ Database error in /events: {e}")
        raise HTTPException(status_code=503, detail=f"Database connection error: {str(e)}")
    except Exception as e:
        print(f"❌ Error fetching events: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

def get_mock_events(
    type_filter: Optional[str] = None,
    location_filter: Optional[str] = None, 
    status_filter: Optional[str] = None,
    limit: Optional[int] = 100
) -> List[Event]:
    """
    Return mock events data for testing when database is not available.
    """
    mock_events = [
        Event(
            id="123e4567-e89b-12d3-a456-426614174000",
            title="AI/ML Hackathon 2024",
            type="hackathon",
            location="San Francisco, CA",
            start_date="2024-02-15",
            end_date="2024-02-17",
            url="https://example.com/ai-hackathon",
            status="validated"
        ),
        Event(
            id="987fcdeb-51a2-43d1-9f12-345678901234",
            title="TechCrunch Disrupt 2024",
            type="conference",
            location="San Francisco, CA",
            start_date="2024-03-10",
            end_date="2024-03-12",
            url="https://techcrunch.com/disrupt",
            status="enriched"
        ),
        Event(
            id="456789ab-cdef-1234-5678-90abcdef1234",
            title="Global React Conference",
            type="conference",
            location="New York, NY",
            start_date="2024-04-05",
            end_date="2024-04-07",
            url="https://react.global",
            status="validated"
        ),
        Event(
            id="fedcba98-7654-3210-fedc-ba9876543210",
            title="Blockchain Hackathon",
            type="hackathon",
            location="Remote",
            start_date="2024-03-20",
            end_date="2024-03-22",
            url="https://blockchain-hack.com",
            status="filtered"
        ),
        Event(
            id="abcdef12-3456-7890-abcd-ef1234567890",
            title="DevOps Summit 2024",
            type="conference",
            location="Remote",
            start_date="2024-05-15",
            end_date="2024-05-16",
            url="https://devops-summit.io",
            status="enriched"
        ),
        Event(
            id="13579bdf-2468-ace0-1357-9bdf2468ace0",
            title="Climate Tech Hackathon",
            type="hackathon",
            location="New York, NY",
            start_date="2024-04-12",
            end_date="2024-04-14",
            url="https://climate-tech-hack.org",
            status="validated"
        ),
        Event(
            id="2468ace0-1357-9bdf-2468-ace013579bdf",
            title="Data Science Conference",
            type="conference",
            location="San Francisco, CA",
            start_date="2024-06-01",
            end_date="2024-06-03",
            url="https://datasci-conf.com",
            status="enriched"
        ),
        Event(
            id="abcdef12-1111-2222-3333-fedcba987654",
            title="Mobile App Hackathon",
            type="hackathon",
            location="Remote",
            start_date="2024-05-25",
            end_date="2024-05-27",
            url="https://mobile-hack.dev",
            status="filtered"
        ),
        Event(
            id="abcdef12-4444-5555-6666-fedcba987654",
            title="Cybersecurity Summit",
            type="conference",
            location="New York, NY",
            start_date="2024-07-10",
            end_date="2024-07-12",
            url="https://cybersec-summit.net",
            status="validated"
        ),
        Event(
            id="abcdef12-7777-8888-9999-fedcba987654",
            title="Green Energy Hackathon",
            type="hackathon",
            location="San Francisco, CA",
            start_date="2024-06-20",
            end_date="2024-06-22",
            url="https://green-energy-hack.org",
            status="enriched"
        )
    ]
    
    # Apply filters
    if type_filter and type_filter.lower() != "all":
        mock_events = [e for e in mock_events if e.type.lower() == type_filter.lower()]
    
    if location_filter and location_filter.lower() != "all":
        mock_events = [e for e in mock_events if location_filter.lower() in e.location.lower()]
    
    if status_filter and status_filter.lower() != "all":
        mock_events = [e for e in mock_events if e.status.lower() == status_filter.lower()]
    
    if limit:
        mock_events = mock_events[:limit]
    
    return mock_events

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "Events API is running", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """Health check endpoint with database connectivity test."""
    try:
        session = get_db_session()
        # Test database connection
        hackathon_count = session.query(Hackathon).count()
        conference_count = session.query(Conference).count()
        session.close()
        
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
            "note": "Using mock data",
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