"""
Unified Event Fetcher - Consolidates conference and hackathon fetching.

"""

import json
import os
import sys
from datetime import datetime
from typing import List, Dict, Any, Literal

from shared_utils import (
    EventProcessor, FileManager, ContentEnricher,
    ParallelProcessor, Event, generate_summary
)
from database_utils import bulk_save_to_db, mark_urls_as_enriched_bulk
from fetchers.sources.conference_sources import discover_conferences
from fetchers.sources.hackathon_sources import discover_hackathons
from fetchers.enrichers.conference_gpt_extractor import enrich_conference_data
from fetchers.enrichers.hackathon_gpt_extractor import enrich_hackathon_data


EventType = Literal['conference', 'hackathon']


class UnifiedEventFetcher:
    """
    Unified event fetcher for both conferences and hackathons.
    
    Eliminates code duplication and provides a consistent interface
    for fetching, enriching, and saving events.
    """
    
    def __init__(self, event_type: EventType):
        """Initialize unified event fetcher."""
        self.event_type = event_type
        self.processor = EventProcessor(event_type)
        self.file_manager = FileManager()
        self.content_enricher = ContentEnricher(event_type)
        
        # Event type specific configuration
        self.config = {
            'conference': {
                'discover_func': discover_conferences,
                'max_results': 50,
                'table_name': 'conferences'
            },
            'hackathon': {
                'discover_func': discover_hackathons,
                'max_results': 60,
                'table_name': 'hackathons'
            }
        }[event_type]
    
    def fetch_all_events(self) -> List[Dict[str, Any]]:
        """
        Fetch events from all sources using unified framework.
        """
        print(f"Starting unified {self.event_type} fetching...")
        
        try:
            # Use the unified discovery function
            events = self.config['discover_func'](max_results=self.config['max_results'])
            print(f"Found {len(events)} {self.event_type}s from unified sources")
            return events
        except Exception as e:
            print(f"Error fetching {self.event_type}s: {str(e)}")
            return []
    
    def enrich_events_parallel(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Enrich events using parallel processing.
        """
        print(f"Starting parallel enrichment of {len(events)} {self.event_type}s...")
        
        # Use ParallelProcessor for efficient parallel enrichment
        def enrich_single_event(event):
            try:
                url = event.get('url')
                name = event.get('name', 'Unknown')
                
                # Debug logging
                print(f"DEBUG: Enriching {name[:30]}... | URL: {url[:60]}...")
                
                if not url or not isinstance(url, str):
                    print(f"DEBUG: Invalid URL for {name}")
                    event['enrichment_status'] = 'failed'
                    event['enrichment_error'] = 'Invalid or missing URL'
                    return event
                
                # Validate URL format
                if not (url.startswith('http://') or url.startswith('https://')):
                    url = 'https://' + url.lstrip('/')
                    print(f"DEBUG: Fixed URL format: {url[:60]}...")
                
                # Extract details using unified enrichment framework
                event_obj = self.content_enricher.enrich(url)
                
                if event_obj and hasattr(event_obj, '__dict__'):
                    details = event_obj.__dict__
                    # Clean up None values and empty strings
                    details = {k: v for k, v in details.items() if v is not None and v != ''}
                    
                    # Merge with original event data (prioritize enriched data)
                    enriched = {**event, **details}
                    enriched['enrichment_status'] = 'success'
                    print(f"DEBUG: Successfully enriched {name[:30]}...")
                    return enriched
                else:
                    print(f"DEBUG: Enrichment returned no data for {name}")
                    event['enrichment_status'] = 'failed'
                    event['enrichment_error'] = 'No data returned from enrichment'
                    return event
                
            except Exception as e:
                print(f"ERROR: Enriching {self.event_type} {event.get('name', 'Unknown')}: {e}")
                event['enrichment_status'] = 'error'
                event['enrichment_error'] = str(e)
                return event
        
        # Process in parallel batches with controlled concurrency
        enriched_events = ParallelProcessor.process(
            events,
            enrich_single_event,
            max_workers=5,   # Conservative for API limits
            batch_size=10    # Small batches for GPT API limits
        )
        
        # Mark URLs as enriched in bulk
        enriched_urls = [event.get('url') for event in enriched_events if event.get('url')]
        if enriched_urls:
            mark_urls_as_enriched_bulk(enriched_urls, self.event_type)
        
        print(f"Parallel enrichment completed. Processed {len(enriched_events)} {self.event_type}s.")
        successful = sum(1 for e in enriched_events if e.get('enrichment_status') == 'success')
        failed = len(enriched_events) - successful
        print(f"Successful extractions: {successful}")
        print(f"Failed extractions: {failed}")
        
        return enriched_events
    
    def save_events(self, events: List[Dict[str, Any]]) -> Dict[str, str]:
        """Save events using file manager."""
        # Convert dict to Event objects for saving
        event_objects = [Event.from_dict(event) for event in events]
        return FileManager.save_events(event_objects, self.event_type)
    
    def generate_summary(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate summary using shared utils function."""
        event_objects = [Event.from_dict(event) for event in events]
        return generate_summary(event_objects, self.event_type)
    
    def deduplicate_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate events by URL."""
        unique_events = []
        seen_urls = set()
        
        for event in events:
            url = event.get('url', '').strip().lower()
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_events.append(event)
        
        return unique_events


def run_event_fetcher(event_type: EventType, limit: int = None):
    """
    Main event fetching function with unified architecture.
    
    Args:
        event_type: Type of events to fetch ('conference' or 'hackathon')
        limit: Maximum number of events to process (optional)
    """
    print(f"=== Unified {event_type.title()} Fetcher ===")
    if limit:
        print(f"Processing limit: {limit} {event_type}s")
    
    try:
        # Initialize unified fetcher
        fetcher = UnifiedEventFetcher(event_type)
        
        # Fetch events from all sources
        all_events = fetcher.fetch_all_events()
        
        if not all_events:
            print(f"No {event_type}s found from any source.")
            return
        
        # Remove duplicates by URL
        unique_events = fetcher.deduplicate_events(all_events)
        print(f"After deduplication: {len(unique_events)} unique {event_type}s")
        
        # Apply limit if specified
        if limit and limit > 0:
            unique_events = unique_events[:limit]
            print(f"Applied limit: processing {len(unique_events)} {event_type}s")
        
        # Save to database using bulk operations
        print(f"Saving {event_type}s to database...")
        save_results = bulk_save_to_db(unique_events, fetcher.config['table_name'])
        print(f"Database save results: {save_results}")
        
        # Enrich events with parallel processing
        enriched_events = fetcher.enrich_events_parallel(unique_events)
        
        # Log processing completion (data already in database)
        result = fetcher.save_events(enriched_events)
        print(f"{event_type.title()} processing completed: {result}")
        
        # Generate and display summary
        summary = fetcher.generate_summary(enriched_events)
        print(f"\n=== {event_type.title()} Summary ===")
        print(f"Total {event_type}s: {summary.get('total_count', 0)}")
        print(f"Remote {event_type}s: {summary.get('remote_count', 0)}")
        print(f"{event_type}s with dates: {summary.get('with_dates', 0)}")
        
        if summary.get('sources'):
            print(f"\nSources breakdown:")
            for source, count in summary['sources'].items():
                print(f"  {source}: {count}")
        
        print(f"\n=== {event_type.title()} fetching completed successfully ===")
        
    except Exception as e:
        print(f"Error in main {event_type} fetching: {e}")
        raise


def main():
    """Main entry point for command line usage."""
    if len(sys.argv) < 2:
        print("Usage: python event_fetcher.py <conference|hackathon> [limit]")
        print("Example: python event_fetcher.py conference 20")
        sys.exit(1)
    
    event_type = sys.argv[1].lower()
    if event_type not in ['conference', 'hackathon']:
        print("Error: Event type must be 'conference' or 'hackathon'")
        sys.exit(1)
    
    # Parse optional limit
    limit = None
    if len(sys.argv) > 2:
        try:
            limit = int(sys.argv[2])
            if limit <= 0:
                print("Limit must be a positive integer")
                sys.exit(1)
        except ValueError:
            print("Invalid limit value. Please provide a positive integer.")
            sys.exit(1)
    
    run_event_fetcher(event_type, limit)


if __name__ == "__main__":
    main() 