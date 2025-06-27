"""
Event enrichment modules.
"""

from .gpt_extractor import (
    enrich_conference_data,
    enrich_hackathon_data,
    enrich_conference_batch,
    enrich_hackathon_batch
)

# Optional Crawl4AI imports
try:
    from .crawl4ai import (
        crawl4ai_scrape_url,
        crawl4ai_scrape_multiple_urls,
        crawl4ai_discover_events,
        crawl4ai_check_availability,
        CRAWL4AI_AVAILABLE
    )
except ImportError:
    CRAWL4AI_AVAILABLE = False
    crawl4ai_scrape_url = None
    crawl4ai_scrape_multiple_urls = None
    crawl4ai_discover_events = None
    crawl4ai_check_availability = lambda: False

__all__ = [
    'enrich_conference_data',
    'enrich_hackathon_data',
    'enrich_conference_batch',
    'enrich_hackathon_batch',
    'crawl4ai_scrape_url',
    'crawl4ai_scrape_multiple_urls',
    'crawl4ai_discover_events',
    'crawl4ai_check_availability',
    'CRAWL4AI_AVAILABLE'
] 