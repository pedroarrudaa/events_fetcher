"""
Conference GPT Extractor - Simplified using shared EventGPTExtractor.

This module provides a thin wrapper around the unified EventGPTExtractor
for conference-specific functionality.
"""

import logging
from typing import Dict, List, Any
from shared_utils import EventGPTExtractor

# Configure logging
logger = logging.getLogger(__name__)


class ConferenceGPTExtractor(EventGPTExtractor):
    """Conference-specific GPT extractor using unified framework."""
    
    def __init__(self):
        """Initialize conference extractor."""
        super().__init__('conference')


def enrich_conference_data(raw_conferences: List[Dict[str, Any]], 
                          force_reenrich: bool = False) -> List[Dict[str, Any]]:
    """
    Main function to enrich conference data.
    
    Args:
        raw_conferences: List of raw conference data
        force_reenrich: Whether to force re-enrichment (currently unused)
        
    Returns:
        List of enriched conference data with processing statistics
    """
    extractor = ConferenceGPTExtractor()
    return extractor.enrich_data(raw_conferences, force_reenrich)


# For backward compatibility
def extract_conference_details(url: str, content: str = None) -> Dict[str, Any]:
    """Legacy function for backward compatibility."""
    extractor = ConferenceGPTExtractor()
    return extractor.extract_details(url, content) 