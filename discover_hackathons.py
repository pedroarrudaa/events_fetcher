#!/usr/bin/env python3
"""
Discover Hackathons (SF, NY, and Online)

This script focuses on finding hackathons in SF, NY, and online/virtual hackathons
that are relevant for the tech community.
"""

import sys
from datetime import datetime
from typing import List, Dict, Any, Optional

# Add parent directory to path
sys.path.insert(0, '.')

from event_service import get_event_service
from shared_utils import logger


def discover_tech_hackathons(include_online: bool = True, max_results: int = 100) -> Dict[str, Any]:
    """
    Discover hackathons in SF, NY, and optionally online.
    
    Args:
        include_online: Whether to include online/virtual hackathons
        max_results: Maximum hackathons to discover
        
    Returns:
        Discovery results summary
    """
    service = get_event_service()
    
    logger.log("info", f"Starting hackathon discovery (online: {include_online})")
    
    # Run discovery with enrichment
    results = service.discover_and_save_events(
        event_type='hackathon',
        max_results=max_results,
        enrich=True
    )
    
    # Get the newly discovered hackathons
    hackathons = service.get_events(
        event_type='hackathon',
        limit=results['saved'] + results['updated'],
        sort_by='created_at'
    )
    
    # Categorize hackathons
    categorized = {
        'sf': [],
        'ny': [],
        'online': [],
        'other': []
    }
    
    location_keywords = {
        'sf': ['san francisco', 'sf', 'bay area', 'silicon valley', 'palo alto', 'mountain view', 'berkeley'],
        'ny': ['new york', 'nyc', 'manhattan', 'brooklyn', 'new york city', 'ny'],
        'online': ['online', 'virtual', 'remote', 'worldwide', 'global', 'digital', 'anywhere']
    }
    
    for hack in hackathons:
        location = (hack.get('location') or '').lower()
        remote = hack.get('remote', False)
        
        categorized_flag = False
        
        # Check location keywords
        for category, keywords in location_keywords.items():
            if any(keyword in location for keyword in keywords):
                categorized[category].append(hack)
                hack['category'] = category
                categorized_flag = True
                break
        
        # Check if it's remote
        if not categorized_flag and remote:
            categorized['online'].append(hack)
            hack['category'] = 'online'
            categorized_flag = True
        
        # If not categorized, put in other
        if not categorized_flag:
            categorized['other'].append(hack)
            hack['category'] = 'other'
    
    # Filter based on include_online
    filtered_hackathons = []
    if include_online:
        filtered_hackathons = categorized['sf'] + categorized['ny'] + categorized['online']
    else:
        filtered_hackathons = categorized['sf'] + categorized['ny']
    
    # Summary
    summary = {
        'total_discovered': results['discovered'],
        'total_saved': results['saved'],
        'sf_hackathons': len(categorized['sf']),
        'ny_hackathons': len(categorized['ny']),
        'online_hackathons': len(categorized['online']),
        'other_hackathons': len(categorized['other']),
        'hackathons': filtered_hackathons
    }
    
    return summary


def format_hackathon_details(hackathon: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format hackathon details for display/export.
    
    Args:
        hackathon: Raw hackathon data
        
    Returns:
        Formatted hackathon data
    """
    return {
        'title': hackathon.get('name', 'Untitled Hackathon'),
        'category': hackathon.get('category', 'unknown'),
        'start_date': hackathon.get('start_date', 'TBD'),
        'end_date': hackathon.get('end_date', hackathon.get('start_date', 'TBD')),
        'location': hackathon.get('location', 'TBD'),
        'is_online': hackathon.get('remote', False) or hackathon.get('category') == 'online',
        'description': hackathon.get('description', ''),
        'url': hackathon.get('url', ''),
        'themes': hackathon.get('themes', []),
        'prize_pool': hackathon.get('ticket_price', 'TBD'),  # Often contains prize info
        'is_ai_focused': any(
            keyword in (hackathon.get('name', '') + hackathon.get('description', '')).lower()
            for keyword in ['ai', 'artificial intelligence', 'llm', 'gpt', 'genai', 
                          'machine learning', 'neural', 'transformer', 'data']
        ),
        'source': hackathon.get('source', 'unknown')
    }


def export_hackathons_by_category(hackathons: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Export hackathons organized by category.
    
    Args:
        hackathons: List of hackathon data
        
    Returns:
        Dictionary with hackathons organized by category
    """
    exports = {
        'sf': [],
        'ny': [],
        'online': []
    }
    
    for hack in hackathons:
        formatted = format_hackathon_details(hack)
        category = hack.get('category', 'other')
        
        if category in exports:
            exports[category].append(formatted)
    
    # Sort each category by date
    for category in exports:
        exports[category].sort(
            key=lambda x: x['start_date'] if x['start_date'] != 'TBD' else '9999-12-31'
        )
    
    return exports


def main():
    """Main function to discover and export hackathons."""
    print("=== Hackathon Discovery (SF, NY, and Online) ===\n")
    
    # Discover hackathons
    results = discover_tech_hackathons(include_online=True, max_results=200)
    
    print(f"Total hackathons discovered: {results['total_discovered']}")
    print(f"Total hackathons saved: {results['total_saved']}")
    print(f"San Francisco hackathons: {results['sf_hackathons']}")
    print(f"New York hackathons: {results['ny_hackathons']}")
    print(f"Online hackathons: {results['online_hackathons']}")
    print(f"Other locations: {results['other_hackathons']}")
    
    # Export by category
    exports = export_hackathons_by_category(results['hackathons'])
    
    # Display sample results
    for category, hackathons in exports.items():
        if hackathons:
            print(f"\n--- {category.upper()} Hackathons ---")
            for i, hack in enumerate(hackathons[:5], 1):
                print(f"{i}. {hack['title']}")
                print(f"   Date: {hack['start_date']} - {hack['end_date']}")
                print(f"   Location: {hack['location']}")
                print(f"   Online: {'Yes' if hack['is_online'] else 'No'}")
                print(f"   AI-Focused: {'Yes' if hack['is_ai_focused'] else 'No'}")
                print(f"   URL: {hack['url']}")
                print(f"   Source: {hack['source']}")
                print()
            
            if len(hackathons) > 5:
                print(f"... and {len(hackathons) - 5} more {category} hackathons\n")
    
    # Save to JSON files
    import json
    
    # Combined file for all hackathons
    all_hackathons = []
    for hackathons in exports.values():
        all_hackathons.extend(hackathons)
    
    with open('all_hackathons.json', 'w') as f:
        json.dump(all_hackathons, f, indent=2)
    
    # Separate files by category
    for category, hackathons in exports.items():
        filename = f'{category}_hackathons.json'
        with open(filename, 'w') as f:
            json.dump(hackathons, f, indent=2)
        print(f"✅ Exported {len(hackathons)} hackathons to {filename}")
    
    print("\n📁 All hackathon data exported successfully!")
    print("Files created:")
    print("- all_hackathons.json (all hackathons)")
    print("- sf_hackathons.json (San Francisco)")
    print("- ny_hackathons.json (New York)")
    print("- online_hackathons.json (Virtual/Online)")


if __name__ == '__main__':
    main() 