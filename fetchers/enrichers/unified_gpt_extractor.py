"""
Unified GPT Extractor - Consolidates conference and hackathon extraction logic
"""

import logging
from typing import Dict, List, Any, Literal
from shared_utils import EventGPTExtractor

# Configure logging
logger = logging.getLogger(__name__)

EventType = Literal['conference', 'hackathon']


class UnifiedGPTExtractor(EventGPTExtractor):
    """Unified GPT extractor for both conferences and hackathons using parameterized event type."""
    
    def __init__(self, event_type: EventType):
        """
        Initialize unified extractor with specified event type.
        
        Args:
            event_type: Either 'conference' or 'hackathon'
        """
        super().__init__(event_type)
        self.event_type = event_type


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
    extractor = UnifiedGPTExtractor('conference')
    return extractor.enrich_data(raw_conferences, force_reenrich)


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
    extractor = UnifiedGPTExtractor('hackathon')
    return extractor.enrich_data(raw_hackathons, force_reenrich)


# For backward compatibility
def extract_conference_details(url: str, content: str = None) -> Dict[str, Any]:
    """Legacy function for backward compatibility."""
    extractor = UnifiedGPTExtractor('conference')
    return extractor.extract_details(url, content)


def extract_hackathon_details(url: str, content: str = None) -> Dict[str, Any]:
    """Legacy function for backward compatibility."""
    extractor = UnifiedGPTExtractor('hackathon')
    return extractor.extract_details(url, content)


# Convenience classes for backward compatibility
class ConferenceGPTExtractor(UnifiedGPTExtractor):
    """Conference-specific GPT extractor for backward compatibility."""
    
    def __init__(self):
        super().__init__('conference')


class HackathonGPTExtractor(UnifiedGPTExtractor):
    """Hackathon-specific GPT extractor for backward compatibility."""
    
    def __init__(self):
        super().__init__('hackathon') 