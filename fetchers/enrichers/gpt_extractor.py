"""
GPT Extractor - Simplified enrichment for events.
"""

from typing import Dict, List, Any
from shared_utils import ContentEnricher, logger


def enrich_conference_data(url: str) -> Dict[str, Any]:
    """
    Legacy function to enrich a single conference.
    
    Args:
        url: Conference URL to enrich
        
    Returns:
        Enriched conference data
    """
    try:
        enricher = ContentEnricher('conference')
        event = enricher.enrich(url)
        return event.__dict__
    except Exception as e:
        logger.log("error", f"Conference enrichment failed: {str(e)}", url=url)
        return {'url': url, 'enrichment_error': str(e)}


def enrich_hackathon_data(url: str) -> Dict[str, Any]:
    """
    Legacy function to enrich a single hackathon.
    
    Args:
        url: Hackathon URL to enrich
        
    Returns:
        Enriched hackathon data
    """
    try:
        enricher = ContentEnricher('hackathon')
        event = enricher.enrich(url)
        return event.__dict__
    except Exception as e:
        logger.log("error", f"Hackathon enrichment failed: {str(e)}", url=url)
        return {'url': url, 'enrichment_error': str(e)}


# Legacy batch functions (simplified implementations)
def enrich_conference_batch(raw_conferences: List[Dict[str, Any]], 
                          force_reenrich: bool = False) -> List[Dict[str, Any]]:
    """Legacy batch enrichment for conferences."""
    enriched = []
    enricher = ContentEnricher('conference')
    
    for conf in raw_conferences:
        if 'url' in conf:
            try:
                event = enricher.enrich(conf['url'])
                enriched_data = event.__dict__
                # Merge with original data
                enriched_data.update({k: v for k, v in conf.items() if k not in enriched_data})
                enriched.append(enriched_data)
            except Exception as e:
                logger.log("error", f"Batch enrichment failed for {conf.get('url')}: {str(e)}")
                conf['enrichment_error'] = str(e)
                enriched.append(conf)
        else:
            enriched.append(conf)
    
    return enriched


def enrich_hackathon_batch(raw_hackathons: List[Dict[str, Any]], 
                         force_reenrich: bool = False) -> List[Dict[str, Any]]:
    """Legacy batch enrichment for hackathons."""
    enriched = []
    enricher = ContentEnricher('hackathon')
    
    for hack in raw_hackathons:
        if 'url' in hack:
            try:
                event = enricher.enrich(hack['url'])
                enriched_data = event.__dict__
                # Merge with original data
                enriched_data.update({k: v for k, v in hack.items() if k not in enriched_data})
                enriched.append(enriched_data)
            except Exception as e:
                logger.log("error", f"Batch enrichment failed for {hack.get('url')}: {str(e)}")
                hack['enrichment_error'] = str(e)
                enriched.append(hack)
        else:
            enriched.append(hack)
    
    return enriched 