#!/usr/bin/env python3
"""
Events Dashboard CLI - Unified command-line interface for event operations.

This CLI provides a clean, consistent interface for all event operations including:
- Discovering events from various sources
- Enriching event data
- Managing the database
- Running the API server
- Generating reports
"""

import click
import sys
import os
from typing import Optional, List
from datetime import datetime
from tabulate import tabulate

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from event_service import get_event_service
from event_repository import get_event_repository
from database_utils import create_tables, get_db_stats
from shared_utils import logger
from config import (
    EVENT_MAX_RESULTS_CONFERENCE, EVENT_MAX_RESULTS_HACKATHON,
    BANNER_WIDTH, SECTION_SEPARATOR_WIDTH
)


def print_banner(text: str, width: int = BANNER_WIDTH):
    """Print a formatted banner."""
    print("=" * width)
    print(text.center(width))
    print("=" * width)


def print_section(text: str, width: int = SECTION_SEPARATOR_WIDTH):
    """Print a section separator."""
    print(f"\n{'-' * width}")
    print(text)
    print(f"{'-' * width}")


@click.group()
@click.version_option(version='2.0.0')
def cli():
    """Events Dashboard CLI - Manage hackathons and conferences."""
    pass


@cli.command()
@click.option('--type', 'event_type', type=click.Choice(['hackathon', 'conference', 'all']), 
              default='all', help='Type of events to discover')
@click.option('--limit', type=int, help='Maximum number of events to discover')
@click.option('--enrich/--no-enrich', default=True, help='Whether to enrich discovered events')
@click.option('--dry-run', is_flag=True, help='Show what would be discovered without saving')
def discover(event_type: str, limit: Optional[int], enrich: bool, dry_run: bool):
    """Discover new events from various sources."""
    print_banner(f"Event Discovery - {event_type.upper()}")
    
    service = get_event_service()
    
    # Handle 'all' by running both types
    if event_type == 'all':
        types = ['hackathon', 'conference']
    else:
        types = [event_type]
    
    total_results = {}
    
    for evt_type in types:
        print_section(f"Discovering {evt_type}s")
        
        # Determine limit
        if limit:
            type_limit = limit // len(types) if event_type == 'all' else limit
        else:
            type_limit = EVENT_MAX_RESULTS_HACKATHON if evt_type == 'hackathon' else EVENT_MAX_RESULTS_CONFERENCE
        
        print(f"Target: {type_limit} {evt_type}s")
        print(f"Enrichment: {'Enabled' if enrich else 'Disabled'}")
        
        if dry_run:
            print("\n🔍 DRY RUN - No data will be saved")
            # Just discover without saving
            from fetchers.sources.event_sources import discover_events
            events = discover_events(evt_type, type_limit)
            
            print(f"\nWould discover {len(events)} {evt_type}s:")
            for i, event in enumerate(events[:5]):
                print(f"  {i+1}. {event.get('name', 'Unknown')[:60]}")
                print(f"     URL: {event.get('url', 'N/A')[:80]}")
            
            if len(events) > 5:
                print(f"  ... and {len(events) - 5} more")
        else:
            # Run actual discovery
            results = service.discover_and_save_events(
                event_type=evt_type,
                max_results=type_limit,
                enrich=enrich
            )
            
            total_results[evt_type] = results
            
            # Print results
            print(f"\n✅ Discovery Results:")
            print(f"  • Discovered: {results['discovered']}")
            print(f"  • Future events: {results['future_events']}")
            print(f"  • Unique events: {results['unique_events']}")
            if enrich:
                print(f"  • Enriched: {results['enriched']}")
            print(f"  • Saved: {results['saved']}")
            print(f"  • Updated: {results['updated']}")
            if results['errors'] > 0:
                print(f"  • Errors: {results['errors']} ⚠️")
    
    # Summary
    if not dry_run and event_type == 'all':
        print_section("Summary")
        total_saved = sum(r['saved'] for r in total_results.values())
        total_updated = sum(r['updated'] for r in total_results.values())
        print(f"Total events saved: {total_saved}")
        print(f"Total events updated: {total_updated}")


@cli.command()
@click.option('--type', 'event_type', type=click.Choice(['hackathon', 'conference', 'all']), 
              default='all', help='Type of events to list')
@click.option('--location', help='Filter by location')
@click.option('--status', type=click.Choice(['all', 'validated', 'filtered', 'enriched']), 
              default='all', help='Filter by status')
@click.option('--limit', type=int, default=20, help='Number of events to show')
@click.option('--include-past', is_flag=True, help='Include past events')
@click.option('--format', 'output_format', type=click.Choice(['table', 'json', 'csv']), 
              default='table', help='Output format')
def list(event_type: str, location: Optional[str], status: str, limit: int, 
         include_past: bool, output_format: str):
    """List events from the database."""
    service = get_event_service()
    
    # Build filters
    filters = {}
    if location:
        filters['location'] = location
    
    # Get events
    events = service.get_events(
        event_type=event_type,
        filters=filters,
        limit=limit,
        include_past=include_past,
        sort_by='start_date'
    )
    
    # Apply status filter
    if status != 'all':
        events = [e for e in events if e.get('status') == status]
    
    # Format output
    if output_format == 'json':
        import json
        print(json.dumps(events, indent=2))
    elif output_format == 'csv':
        import csv
        import sys
        if events:
            writer = csv.DictWriter(sys.stdout, fieldnames=events[0].keys())
            writer.writeheader()
            writer.writerows(events)
    else:  # table
        if not events:
            print("No events found matching criteria.")
            return
        
        # Prepare table data
        headers = ['Name', 'Type', 'Date', 'Location', 'Status', 'Quality']
        rows = []
        
        for event in events:
            name = event.get('name', 'Unknown')[:40]
            evt_type = event.get('event_type', 'unknown')
            start_date = event.get('start_date', 'TBD')
            location = event.get('location', 'TBD')[:30]
            status = event.get('status', 'unknown')
            quality = f"{event.get('quality_score', 0):.2f}"
            
            rows.append([name, evt_type, start_date, location, status, quality])
        
        print(f"\nShowing {len(rows)} events:")
        print(tabulate(rows, headers=headers, tablefmt='grid'))


@cli.command()
@click.argument('query')
@click.option('--type', 'event_type', type=click.Choice(['hackathon', 'conference', 'all']), 
              default='all', help='Type of events to search')
@click.option('--limit', type=int, default=10, help='Maximum results')
def search(query: str, event_type: str, limit: int):
    """Search for events by name, location, or description."""
    service = get_event_service()
    
    print(f"🔍 Searching for: '{query}'")
    
    results = service.search_events(query, event_type, limit)
    
    if not results:
        print("No events found matching your search.")
        return
    
    print(f"\nFound {len(results)} matching events:\n")
    
    for i, event in enumerate(results, 1):
        print(f"{i}. {event.get('name', 'Unknown')}")
        print(f"   Type: {event.get('event_type', 'unknown')}")
        print(f"   Location: {event.get('location', 'TBD')}")
        print(f"   Date: {event.get('start_date', 'TBD')}")
        print(f"   Relevance: {event.get('relevance_score', 0):.2f}")
        print(f"   URL: {event.get('url', 'N/A')}")
        print()


@cli.command()
def stats():
    """Show database statistics."""
    print_banner("Events Dashboard Statistics")
    
    service = get_event_service()
    stats = service.get_statistics()
    
    # Basic stats
    print_section("Event Counts")
    print(f"Total Events: {stats.get('total_events', 0)}")
    print(f"  • Hackathons: {stats.get('total_hackathons', 0)}")
    print(f"  • Conferences: {stats.get('total_conferences', 0)}")
    
    print_section("Recent Activity (Last 30 days)")
    print(f"Recent Events: {stats.get('recent_events', 0)}")
    print(f"  • Hackathons: {stats.get('recent_hackathons', 0)}")
    print(f"  • Conferences: {stats.get('recent_conferences', 0)}")
    
    print_section("Upcoming Events")
    print(f"Total Upcoming: {stats.get('upcoming_events', 0)}")
    print(f"This Month: {stats.get('events_this_month', 0)}")
    
    # Quality metrics
    print_section("Quality Metrics")
    avg_quality = stats.get('average_quality_score', 0)
    print(f"Average Quality Score: {avg_quality:.2f}")
    
    # Location breakdown
    if stats.get('events_by_location'):
        print_section("Top Locations")
        locations = sorted(
            stats['events_by_location'].items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:10]
        
        for location, count in locations:
            print(f"  • {location}: {count}")


@cli.command()
@click.option('--drop', is_flag=True, help='Drop existing tables first')
def init_db(drop: bool):
    """Initialize the database tables."""
    print_banner("Database Initialization")
    
    if drop:
        print("⚠️  WARNING: This will drop all existing tables!")
        if not click.confirm("Are you sure you want to continue?"):
            print("Aborted.")
            return
    
    try:
        create_tables()
        print("✅ Database tables created successfully!")
        
        # Show current stats
        stats = get_db_stats()
        print(f"\nCurrent database state:")
        print(f"  • Hackathons: {stats.get('hackathons_count', 0)}")
        print(f"  • Conferences: {stats.get('conferences_count', 0)}")
        
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        sys.exit(1)


@cli.command()
@click.option('--host', default='0.0.0.0', help='Host to bind to')
@click.option('--port', default=8000, help='Port to bind to')
@click.option('--reload', is_flag=True, help='Enable auto-reload for development')
def serve(host: str, port: int, reload: bool):
    """Run the FastAPI server."""
    print_banner("Starting Events API Server")
    print(f"Server: http://{host}:{port}")
    print(f"Docs: http://{host}:{port}/docs")
    print(f"Auto-reload: {'Enabled' if reload else 'Disabled'}")
    print("\nPress CTRL+C to stop the server\n")
    
    import uvicorn
    uvicorn.run(
        "backend:app",
        host=host,
        port=port,
        reload=reload
    )


@cli.command()
@click.argument('event_id')
@click.argument('action', type=click.Choice(['archive', 'reached_out', 'interested', 'not_interested', 'applied']))
@click.option('--type', 'event_type', type=click.Choice(['hackathon', 'conference']), 
              required=True, help='Type of event')
def record_action(event_id: str, action: str, event_type: str):
    """Record an action taken on an event."""
    service = get_event_service()
    
    success, error = service.record_event_action(event_id, event_type, action)
    
    if success:
        print(f"✅ Action '{action}' recorded for {event_type} {event_id}")
    else:
        print(f"❌ Failed to record action: {error}")


@cli.command()
@click.option('--url', help='Test enrichment on a specific URL')
@click.option('--type', 'event_type', type=click.Choice(['hackathon', 'conference']), 
              default='conference', help='Type of event')
def test_enrichment(url: Optional[str], event_type: str):
    """Test the enrichment process."""
    print_banner("Enrichment Test")
    
    if not url:
        # Use a sample URL
        sample_urls = {
            'conference': 'https://www.ai-expo.net/',
            'hackathon': 'https://devpost.com/hackathons'
        }
        url = sample_urls.get(event_type)
        print(f"Using sample URL: {url}")
    
    service = get_event_service()
    
    print(f"\n🔍 Testing enrichment for {event_type}...")
    print(f"URL: {url}")
    
    # Create minimal event data
    event_data = {
        'url': url,
        'name': 'Test Event'
    }
    
    result = service.enrich_event(event_data, event_type)
    
    if result.success:
        print("\n✅ Enrichment successful!")
        print("\nEnriched data:")
        
        import json
        print(json.dumps(result.enriched_data, indent=2))
    else:
        print(f"\n❌ Enrichment failed: {result.error}")


@cli.command()
def cleanup():
    """Clean up temporary files and old data."""
    print_banner("Cleanup")
    
    # Clean up old log files
    log_dir = "logs"
    if os.path.exists(log_dir):
        import glob
        old_logs = glob.glob(os.path.join(log_dir, "*.log"))
        if old_logs:
            print(f"Found {len(old_logs)} log files")
            if click.confirm("Delete old log files?"):
                for log_file in old_logs:
                    os.remove(log_file)
                print("✅ Log files deleted")
    
    # Clean up data directory
    data_dir = "data"
    if os.path.exists(data_dir):
        import glob
        old_files = glob.glob(os.path.join(data_dir, "*.json"))
        if old_files:
            print(f"\nFound {len(old_files)} data files")
            for f in old_files[:5]:
                print(f"  • {os.path.basename(f)}")
            if len(old_files) > 5:
                print(f"  ... and {len(old_files) - 5} more")
            
            if click.confirm("Delete old data files?"):
                for data_file in old_files:
                    os.remove(data_file)
                print("✅ Data files deleted")
    
    print("\n✅ Cleanup completed")


if __name__ == '__main__':
    cli() 