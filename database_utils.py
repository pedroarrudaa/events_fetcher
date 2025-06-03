"""
Database utilities for saving hackathons and conferences to PostgreSQL database using SQLAlchemy.
"""
import os
import json
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, text, Column, Integer, String, Boolean, DateTime, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert, UUID
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# SQLAlchemy setup
Base = declarative_base()

class Hackathon(Base):
    """SQLAlchemy model for hackathons table."""
    __tablename__ = 'hackathons'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    url = Column(String, unique=True, nullable=False)
    date = Column(String)  # Can represent start_date or date range
    start_date = Column(String)
    end_date = Column(String)
    location = Column(String)
    city = Column(String)
    remote = Column(Boolean, default=False)
    description = Column(Text)
    short_description = Column(Text)
    speakers = Column(JSON)
    sponsors = Column(JSON)
    ticket_price = Column(JSON)
    is_paid = Column(Boolean, default=False)
    themes = Column(JSON)
    source = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class Conference(Base):
    """SQLAlchemy model for conferences table."""
    __tablename__ = 'conferences'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    url = Column(String, unique=True, nullable=False)
    date = Column(String)  # Can represent start_date or date range
    start_date = Column(String)
    end_date = Column(String)
    location = Column(String)
    city = Column(String)
    remote = Column(Boolean, default=False)
    description = Column(Text)
    short_description = Column(Text)
    speakers = Column(JSON)
    sponsors = Column(JSON)
    ticket_price = Column(JSON)
    is_paid = Column(Boolean, default=False)
    themes = Column(JSON)
    source = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

# Database engine and session
_engine = None
_Session = None

def get_db_engine():
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        # Use environment variable for database URL
        database_url = os.getenv('DATABASE_URL')
        
        if not database_url:
            raise ValueError(
                "DATABASE_URL environment variable is required.\n"
                "Please set it in your .env file or environment.\n"
                "For Railway PostgreSQL, use the EXTERNAL connection string (not the internal one).\n"
                "Example: postgresql://postgres:password@host:port/database"
            )
            
        print(f"🔗 Connecting to database: {database_url.split('@')[0]}@***")
            
        _engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_recycle=300,
            echo=False  # Set to True for SQL debugging
        )
    return _engine

def get_db_session():
    """Get or create the database session factory."""
    global _Session
    if _Session is None:
        _Session = sessionmaker(bind=get_db_engine())
    return _Session()

def create_tables() -> None:
    """
    Create the hackathons and conferences tables if they don't exist.
    """
    try:
        engine = get_db_engine()
        Base.metadata.create_all(engine)
        print(f"✅ Database tables 'hackathons' and 'conferences' created/verified in PostgreSQL")
    except Exception as e:
        print(f"❌ Error creating tables: {str(e)}")
        raise

def _normalize_event_data(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize event data to match database schema with required fields.
    
    Args:
        event: Raw event data dictionary
        
    Returns:
        Normalized event data dictionary
    """
    normalized = {}
    
    # Map common fields
    field_mappings = {
        'name': ['name', 'title'],
        'url': ['url', 'link'],
        'date': ['date', 'start_date', 'event_date'],
        'start_date': ['start_date', 'date', 'event_date'],
        'end_date': ['end_date'],
        'location': ['location', 'city', 'venue'],
        'city': ['city', 'location', 'venue'],
        'remote': ['remote', 'is_remote'],
        'description': ['description', 'short_description', 'summary'],
        'short_description': ['short_description', 'description', 'summary'],
        'speakers': ['speakers'],
        'sponsors': ['sponsors'],
        'ticket_price': ['ticket_price', 'price', 'cost'],
        'is_paid': ['is_paid', 'paid'],
        'themes': ['themes', 'topics', 'categories'],
        'source': ['source', 'data_source']
    }
    
    for db_field, possible_keys in field_mappings.items():
        value = None
        for key in possible_keys:
            if key in event:
                value = event[key]
                break
        
        # Handle special cases
        if db_field == 'remote':
            if isinstance(value, str):
                normalized[db_field] = value.lower() in ['true', '1', 'yes', 'remote']
            else:
                normalized[db_field] = bool(value) if value is not None else False
        elif db_field == 'is_paid':
            if isinstance(value, str):
                normalized[db_field] = value.lower() in ['true', '1', 'yes', 'paid']
            else:
                normalized[db_field] = bool(value) if value is not None else False
        elif db_field in ['speakers', 'sponsors', 'themes']:
            # Handle JSON fields - keep as JSON-serializable objects
            if isinstance(value, list):
                normalized[db_field] = value
            elif isinstance(value, str) and value:
                # Try to parse comma-separated strings into lists
                normalized[db_field] = [item.strip() for item in value.split(',') if item.strip()]
            else:
                normalized[db_field] = [] if value is None else [str(value)]
        elif db_field == 'ticket_price':
            # Handle ticket price as JSON - could be string, number, or object
            if isinstance(value, (dict, list)):
                normalized[db_field] = value
            elif value is not None:
                normalized[db_field] = {"price": str(value)}
            else:
                normalized[db_field] = None
        else:
            normalized[db_field] = str(value) if value is not None else None
    
    # Ensure we have required fields (id, name, date, url, location, description)
    if not normalized.get('url'):
        raise ValueError("Event must have a URL")
    if not normalized.get('name'):
        normalized['name'] = f"Event at {normalized.get('url', 'Unknown')}"
    if not normalized.get('date') and not normalized.get('start_date'):
        normalized['date'] = 'TBD'
    if not normalized.get('location') and not normalized.get('city'):
        if normalized.get('remote'):
            normalized['location'] = 'Remote'
        else:
            normalized['location'] = 'TBD'
    if not normalized.get('description') and not normalized.get('short_description'):
        normalized['description'] = 'No description available'
    
    return normalized

def save_to_db(events: List[Dict[str, Any]], table_name: str, 
               update_existing: bool = False) -> Dict[str, int]:
    """
    Save events to the specified table (hackathons or conferences) using SQLAlchemy.
    
    Args:
        events: List of event data dictionaries
        table_name: Name of the table ('hackathons' or 'conferences')
        update_existing: Whether to update existing entries with the same URL
        
    Returns:
        Dictionary with counts: {'inserted': int, 'updated': int, 'skipped': int, 'errors': int}
    """
    if not events:
        print("❌ No events to save to database!")
        return {'inserted': 0, 'updated': 0, 'skipped': 0, 'errors': 0}
    
    if table_name not in ['hackathons', 'conferences']:
        raise ValueError("table_name must be either 'hackathons' or 'conferences'")
    
    # Get the appropriate model class
    model_class = Hackathon if table_name == 'hackathons' else Conference
    
    # Ensure tables exist
    create_tables()
    
    session = get_db_session()
    counts = {'inserted': 0, 'updated': 0, 'skipped': 0, 'errors': 0}
    
    print(f"💾 Saving {len(events)} events to {table_name} table...")
    print(f"⚙️ Update mode: {'UPDATE' if update_existing else 'INSERT_ONLY'}")
    
    try:
        for event in events:
            try:
                # Normalize event data
                normalized_event = _normalize_event_data(event)
                
                if update_existing:
                    # Use PostgreSQL UPSERT with SQLAlchemy
                    stmt = insert(model_class).values(**normalized_event)
                    
                    # Define what fields to update on conflict (exclude id, url, created_at)
                    update_dict = {
                        key: stmt.excluded[key] 
                        for key in normalized_event.keys() 
                        if key not in ['url', 'created_at']
                    }
                    
                    upsert_stmt = stmt.on_conflict_do_update(
                        index_elements=['url'],
                        set_=update_dict
                    )
                    
                    result = session.execute(upsert_stmt)
                    
                    # Check if it was an insert or update by querying
                    existing = session.query(model_class).filter_by(url=normalized_event['url']).first()
                    if existing.created_at.timestamp() > (datetime.utcnow().timestamp() - 5):  # Created within last 5 seconds
                        counts['inserted'] += 1
                    else:
                        counts['updated'] += 1
                        
                else:
                    # Check if URL already exists
                    existing = session.query(model_class).filter_by(url=normalized_event['url']).first()
                    
                    if existing:
                        counts['skipped'] += 1
                    else:
                        # Insert new record
                        new_event = model_class(**normalized_event)
                        session.add(new_event)
                        counts['inserted'] += 1
                
            except Exception as e:
                print(f"❌ Error saving event {event.get('name', 'Unknown')}: {str(e)}")
                counts['errors'] += 1
                continue
        
        # Commit all changes
        session.commit()
        
    except Exception as e:
        session.rollback()
        print(f"❌ Database transaction failed: {str(e)}")
        raise
    finally:
        session.close()
    
    # Print summary
    print(f"✅ Database save complete:")
    print(f"   • Table: {table_name}")
    print(f"   • Inserted: {counts['inserted']}")
    print(f"   • Updated: {counts['updated']}")
    print(f"   • Skipped: {counts['skipped']}")
    print(f"   • Errors: {counts['errors']}")
    print(f"   • Database: Railway PostgreSQL via SQLAlchemy")
    
    return counts

def get_events_from_db(table_name: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Retrieve events from the specified table.
    
    Args:
        table_name: Name of the table ('hackathons' or 'conferences')
        limit: Optional limit on number of records to return
        
    Returns:
        List of event dictionaries
    """
    if table_name not in ['hackathons', 'conferences']:
        raise ValueError("table_name must be either 'hackathons' or 'conferences'")
    
    # Get the appropriate model class
    model_class = Hackathon if table_name == 'hackathons' else Conference
    
    session = get_db_session()
    
    try:
        query = session.query(model_class).order_by(model_class.created_at.desc())
        
        if limit:
            query = query.limit(limit)
        
        results = query.all()
        
        # Convert to list of dictionaries
        events = []
        for result in results:
            event = {
                'id': str(result.id),
                'name': result.name,
                'url': result.url,
                'date': result.date,
                'start_date': result.start_date,
                'end_date': result.end_date,
                'location': result.location,
                'city': result.city,
                'remote': result.remote,
                'description': result.description,
                'short_description': result.short_description,
                'speakers': result.speakers,
                'sponsors': result.sponsors,
                'ticket_price': result.ticket_price,
                'is_paid': result.is_paid,
                'themes': result.themes,
                'source': result.source,
                'created_at': result.created_at.isoformat() if result.created_at else None
            }
            events.append(event)
        
        return events
        
    finally:
        session.close()

def get_db_stats() -> Dict[str, Any]:
    """
    Get statistics about the database contents.
    
    Returns:
        Dictionary with database statistics
    """
    session = get_db_session()
    
    try:
        stats = {}
        
        for table_name, model_class in [('hackathons', Hackathon), ('conferences', Conference)]:
            # Total count
            total = session.query(model_class).count()
            
            # Remote count
            remote = session.query(model_class).filter(model_class.remote == True).count()
            
            # Recent entries (last 24 hours)
            yesterday = datetime.utcnow() - timedelta(hours=24)
            recent = session.query(model_class).filter(model_class.created_at >= yesterday).count()
            
            stats[table_name] = {
                'total': total,
                'remote': remote,
                'in_person': total - remote,
                'recent_24h': recent
            }
        
        # Source breakdown across both tables
        source_stats = {}
        
        # Get sources from hackathons
        hackathon_sources = session.query(Hackathon.source).distinct().all()
        for (source,) in hackathon_sources:
            if source:
                count = session.query(Hackathon).filter(Hackathon.source == source).count()
                source_stats[f"hackathons_{source}"] = count
        
        # Get sources from conferences
        conference_sources = session.query(Conference.source).distinct().all()
        for (source,) in conference_sources:
            if source:
                count = session.query(Conference).filter(Conference.source == source).count()
                source_stats[f"conferences_{source}"] = count
        
        stats['sources'] = source_stats
        stats['database'] = 'Railway PostgreSQL (SQLAlchemy)'
        
        return stats
        
    except Exception as e:
        print(f"❌ Error getting database stats: {str(e)}")
        return {
            'hackathons': {'total': 0, 'remote': 0, 'in_person': 0, 'recent_24h': 0},
            'conferences': {'total': 0, 'remote': 0, 'in_person': 0, 'recent_24h': 0},
            'sources': {},
            'database': 'Railway PostgreSQL (SQLAlchemy) - Error'
        }
    finally:
        session.close() 