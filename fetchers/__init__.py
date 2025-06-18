"""
Fetchers package - Unified event discovery and enrichment.

This package consolidates all event fetching functionality for
conferences and hackathons into a clean, organized structure.
"""

from .sources.conference_sources import discover_conferences
from .sources.hackathon_sources import discover_hackathons
from .enrichers.conference_gpt_extractor import enrich_conference_data
from .enrichers.hackathon_gpt_extractor import enrich_hackathon_data

__all__ = [
    'discover_conferences',
    'discover_hackathons', 
    'enrich_conference_data',
    'enrich_hackathon_data'
] 