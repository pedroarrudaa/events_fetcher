"""
Hackathon GPT Extractor - Simplified using shared EventGPTExtractor.

This module provides a thin wrapper around the unified EventGPTExtractor
for hackathon-specific functionality.
"""

import logging
from typing import Dict, List, Any
from shared_utils import EventGPTExtractor

# Configure logging
logger = logging.getLogger(__name__)


class HackathonGPTExtractor(EventGPTExtractor):
    """Hackathon-specific GPT extractor using unified framework."""
    
    def __init__(self):
        """Initialize hackathon extractor."""
        super().__init__('hackathon')


def enrich_hackathon_data(raw_hackathons: List[Dict[str, Any]], 
                         force_reenrich: bool = False) -> List[Dict[str, Any]]:
    """
    Main function to enrich hackathon data.
    
    Args:
        raw_hackathons: List of raw hackathon data
        force_reenrich: Whether to force re-enrichment (currently unused)
        
    Returns:
        List of enriched hackathon data with processing statistics
    """
    extractor = HackathonGPTExtractor()
    return extractor.enrich_data(raw_hackathons, force_reenrich)


# For backward compatibility
def extract_hackathon_details(url: str, content: str = None) -> Dict[str, Any]:
    """Legacy function for backward compatibility."""
    extractor = HackathonGPTExtractor()
    return extractor.extract_details(url, content) 