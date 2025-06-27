#!/usr/bin/env python3
"""
Discover AI Conferences in San Francisco and New York

This script focuses on finding AI/ML conferences specifically in SF and NY
for the generativeaisf.com and lu.ma/genai-ny calendars.
"""

import sys
from datetime import datetime
from typing import List, Dict, Any

# Add parent directory to path
sys.path.insert(0, '.')

from event_service import get_event_service
from shared_utils import logger


def discover_ai_conferences(cities: List[str] = ['sf', 'ny'], max_results: int = 100) -> Dict[str, Any]:
    """
    Discover AI conferences in specific cities.
    
    Args:
        cities: List of cities to target ('sf', 'ny')
        max_results: Maximum conferences to discover
        
    Returns:
        Discovery results summary
    """
    service = get_event_service()
    
    logger.log("info", f"Starting AI conference discovery for {', '.join(cities)}")
    
    # Run discovery with enrichment
    results = service.discover_and_save_events(
        event_type='conference',
        max_results=max_results,
        enrich=True
    )
    
    # Get the newly discovered conferences for filtering
    conferences = service.get_events(
        event_type='conference',
        limit=results['saved'] + results['updated'],
        sort_by='created_at'
    )
    
    # Filter by target cities
    city_filters = {
        'sf': ['san francisco', 'sf', 'bay area', 'silicon valley', 'palo alto', 'mountain view'],
        'ny': ['new york', 'nyc', 'manhattan', 'brooklyn', 'new york city', 'ny']
    }
    
    filtered_conferences = []
    for conf in conferences:
        location = (conf.get('location') or '').lower()
        city = (conf.get('city') or '').lower()
        
        # Check if conference is in target cities
        for target_city, keywords in city_filters.items():
            if target_city in cities:
                if any(keyword in location or keyword in city for keyword in keywords):
                    conf['target_city'] = target_city
                    filtered_conferences.append(conf)
                    break
    
    # Summary
    summary = {
        'total_discovered': results['discovered'],
        'total_saved': results['saved'],
        'sf_conferences': len([c for c in filtered_conferences if c.get('target_city') == 'sf']),
        'ny_conferences': len([c for c in filtered_conferences if c.get('target_city') == 'ny']),
        'conferences': filtered_conferences
    }
    
    return summary


def export_for_calendar(conferences: List[Dict[str, Any]], city: str) -> List[Dict[str, Any]]:
    """
    Format conferences for calendar export.
    
    Args:
        conferences: List of conference data
        city: Target city ('sf' or 'ny')
        
    Returns:
        List of formatted events for calendar
    """
    calendar_events = []
    
    for conf in conferences:
        if conf.get('target_city') != city:
            continue
            
        # Format for calendar
        event = {
            'title': conf.get('name', 'Untitled Conference'),
            'start_date': conf.get('start_date', 'TBD'),
            'end_date': conf.get('end_date', conf.get('start_date', 'TBD')),
            'location': conf.get('location', 'TBD'),
            'description': conf.get('description', ''),
            'url': conf.get('url', ''),
            'themes': conf.get('themes', []),
            'speakers': conf.get('speakers', []),
            'is_ai_focused': any(
                keyword in (conf.get('name', '') + conf.get('description', '')).lower()
                for keyword in ['ai', 'artificial intelligence', 'llm', 'gpt', 'genai', 
                              'machine learning', 'neural', 'transformer']
            )
        }
        
        calendar_events.append(event)
    
    # Sort by date
    calendar_events.sort(key=lambda x: x['start_date'] if x['start_date'] != 'TBD' else '9999-12-31')
    
    return calendar_events


def main():
    """Main function to discover and export conferences."""
    print("=== AI Conference Discovery for SF & NY ===\n")
    
    # Discover conferences
    results = discover_ai_conferences(cities=['sf', 'ny'], max_results=200)
    
    print(f"Total conferences discovered: {results['total_discovered']}")
    print(f"Total conferences saved: {results['total_saved']}")
    print(f"San Francisco conferences: {results['sf_conferences']}")
    print(f"New York conferences: {results['ny_conferences']}")
    
    # Export for each city
    if results['sf_conferences'] > 0:
        print("\n--- San Francisco Conferences ---")
        sf_events = export_for_calendar(results['conferences'], 'sf')
        for i, event in enumerate(sf_events[:10], 1):
            print(f"{i}. {event['title']}")
            print(f"   Date: {event['start_date']}")
            print(f"   Location: {event['location']}")
            print(f"   AI-Focused: {'Yes' if event['is_ai_focused'] else 'No'}")
            print(f"   URL: {event['url']}")
            print()
        
        if len(sf_events) > 10:
            print(f"... and {len(sf_events) - 10} more SF conferences\n")
    
    if results['ny_conferences'] > 0:
        print("\n--- New York Conferences ---")
        ny_events = export_for_calendar(results['conferences'], 'ny')
        for i, event in enumerate(ny_events[:10], 1):
            print(f"{i}. {event['title']}")
            print(f"   Date: {event['start_date']}")
            print(f"   Location: {event['location']}")
            print(f"   AI-Focused: {'Yes' if event['is_ai_focused'] else 'No'}")
            print(f"   URL: {event['url']}")
            print()
        
        if len(ny_events) > 10:
            print(f"... and {len(ny_events) - 10} more NY conferences\n")
    
    # Save to JSON for manual upload to calendars
    import json
    
    with open('sf_conferences.json', 'w') as f:
        json.dump(export_for_calendar(results['conferences'], 'sf'), f, indent=2)
    
    with open('ny_conferences.json', 'w') as f:
        json.dump(export_for_calendar(results['conferences'], 'ny'), f, indent=2)
    
    print("\n✅ Conference data exported to sf_conferences.json and ny_conferences.json")
    print("You can now upload these to your calendars at:")
    print("- http://generativeaisf.com/")
    print("- https://lu.ma/genai-ny")


if __name__ == '__main__':
    main() 