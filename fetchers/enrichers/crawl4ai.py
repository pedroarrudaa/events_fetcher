"""
Crawl4AI Integration for enhanced web scraping with extraction capabilities.

This module provides async web crawling with JavaScript rendering support.
"""

import os
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

# Import configuration
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import (
    CRAWL4AI_CONTENT_THRESHOLD, CRAWL4AI_MIN_WORDS, CRAWL4AI_DELAY_BEFORE_RETURN,
    CRAWL4AI_JS_WAIT_SHORT, CRAWL4AI_PAGE_TIMEOUT, CRAWL4AI_MAX_CONCURRENT,
    CRAWL4AI_MAX_EVENTS, CRAWL4AI_BATCH_SLEEP, CRAWL4AI_LISTING_TIMEOUT,
    CRAWL4AI_USER_AGENT
)

# Check Crawl4AI availability
try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
    from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
    from crawl4ai.content_filter_strategy import PruningContentFilter
    
    CRAWL4AI_AVAILABLE = not os.environ.get('DISABLE_CRAWL4AI', '').lower() in ['1', 'true', 'yes']
except ImportError as e:
    print(f"  Crawl4AI not available: {e}")
    CRAWL4AI_AVAILABLE = False


class Crawl4AIEventScraper:
    """Enhanced event scraper using Crawl4AI with concurrency control."""
    
    def __init__(self):
        if not CRAWL4AI_AVAILABLE:
            raise ImportError("Crawl4AI is not installed. Run: pip install crawl4ai && crawl4ai-setup")
        
        self.browser_config = BrowserConfig(
            headless=True,
            verbose=False,
            user_agent=CRAWL4AI_USER_AGENT
        )
        
        self.crawler = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.crawler = AsyncWebCrawler(config=self.browser_config)
        await self.crawler.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.crawler:
            await self.crawler.__aexit__(exc_type, exc_val, exc_tb)
    
    async def scrape_single(self, url: str, extract_structured: bool = True) -> Dict[str, Any]:
        """Scrape a single URL with Crawl4AI."""
        try:
            # Configure content filtering
            content_filter = PruningContentFilter(
                threshold=CRAWL4AI_CONTENT_THRESHOLD,
                threshold_type="fixed",
                min_word_threshold=CRAWL4AI_MIN_WORDS
            )
            
            # Configure run parameters
            run_config = CrawlerRunConfig(
                delay_before_return_html=CRAWL4AI_DELAY_BEFORE_RETURN,
                js_code=[
                    f"await new Promise(resolve => setTimeout(resolve, {CRAWL4AI_JS_WAIT_SHORT}));",
                    "window.scrollTo(0, document.body.scrollHeight);",
                    f"await new Promise(resolve => setTimeout(resolve, {CRAWL4AI_JS_WAIT_SHORT}));",
                ],
                cache_mode=CacheMode.BYPASS,
                page_timeout=CRAWL4AI_PAGE_TIMEOUT,
                wait_for_images=False,
                markdown_generator=DefaultMarkdownGenerator(),
                content_filter=content_filter
            )
            
            # Add extraction strategy if requested
            if extract_structured:
                run_config.extraction_strategy = JsonCssExtractionStrategy(
                    schema={
                        "name": "event",
                        "baseSelector": "body",
                        "fields": [
                            {"name": "title", "selector": "h1, h2, title", "type": "text"},
                            {"name": "date", "selector": "[class*='date'], [id*='date'], time", "type": "text"},
                            {"name": "location", "selector": "[class*='location'], [class*='venue'], address", "type": "text"},
                            {"name": "description", "selector": "[class*='description'], [class*='summary'], .content", "type": "text"},
                            {"name": "links", "selector": "a[href]", "type": "list", "attribute": "href"}
                        ]
                    }
                )
            
            # Execute crawl
            result = await self.crawler.arun(url, config=run_config)
            
            return {
                'success': result.success,
                'content': result.html if result.success else '',
                'markdown': result.markdown if result.success else '',
                'metadata': {
                    'title': result.metadata.get('title', '') if result.success else '',
                    'extracted': result.extracted_content if result.success and extract_structured else None,
                    'links': result.links if result.success else [],
                    'error': result.error_message if not result.success else None
                },
                'url': url
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'content': '',
                'url': url
            }
    
    async def scrape_multiple(self, urls: List[str], max_concurrent: int = CRAWL4AI_MAX_CONCURRENT) -> List[Dict[str, Any]]:
        """Scrape multiple URLs concurrently."""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def scrape_with_limit(url: str) -> Dict[str, Any]:
            async with semaphore:
                return await self.scrape_single(url)
        
        tasks = [scrape_with_limit(url) for url in urls]
        results = []
        
        # Process in batches to avoid overwhelming the system
        batch_size = max_concurrent * 2
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            
            # Process results
            for result in batch_results:
                if isinstance(result, Exception):
                    results.append({
                        'success': False,
                        'error': str(result),
                        'content': '',
                        'url': urls[i + results.index(result)]
                    })
                else:
                    results.append(result)
            
            # Sleep between batches
            if i + batch_size < len(tasks):
                await asyncio.sleep(CRAWL4AI_BATCH_SLEEP)
        
        return results
    
    async def discover_events(self, listing_url: str, max_events: int = CRAWL4AI_MAX_EVENTS,
                            max_concurrent: int = CRAWL4AI_MAX_CONCURRENT) -> List[Dict[str, Any]]:
        """Discover event URLs from a listing page and scrape them."""
        # First, scrape the listing page
        listing_config = CrawlerRunConfig(
            js_code=["window.scrollTo(0, document.body.scrollHeight);"],
            wait_for_timeout=CRAWL4AI_LISTING_TIMEOUT
        )
        
        listing_result = await self.crawler.arun(listing_url, config=listing_config)
        
        if not listing_result.success:
            return []
        
        # Extract event URLs from the listing
        event_urls = []
        for link in listing_result.links[:max_events]:
            if self._is_event_url(link.get('href', '')):
                event_urls.append(link['href'])
        
        # Scrape individual event pages
        if event_urls:
            return await self.scrape_multiple(event_urls, max_concurrent)
        
        return []
    
    def _is_event_url(self, url: str) -> bool:
        """Check if URL is likely an event page."""
        event_indicators = ['event', 'conference', 'hackathon', 'summit', 'workshop', 'meetup']
        url_lower = url.lower()
        return any(indicator in url_lower for indicator in event_indicators)


# Convenience functions for integration
async def crawl4ai_scrape_url(url: str, extract_structured: bool = True,
                             **kwargs) -> Dict[str, Any]:
    """Scrape a single URL with Crawl4AI."""
    if not CRAWL4AI_AVAILABLE:
        return {'success': False, 'error': 'Crawl4AI not available', 'content': ''}
    
    async with Crawl4AIEventScraper() as scraper:
        return await scraper.scrape_single(url, extract_structured)


async def crawl4ai_scrape_multiple_urls(urls: List[str], max_concurrent: int = CRAWL4AI_MAX_CONCURRENT,
                                      **kwargs) -> List[Dict[str, Any]]:
    """Scrape multiple URLs with Crawl4AI."""
    if not CRAWL4AI_AVAILABLE:
        return [{'success': False, 'error': 'Crawl4AI not available', 'url': url} for url in urls]
    
    async with Crawl4AIEventScraper() as scraper:
        return await scraper.scrape_multiple(urls, max_concurrent)


async def crawl4ai_discover_events(listing_url: str, max_events: int = CRAWL4AI_MAX_EVENTS,
                                 max_concurrent: int = CRAWL4AI_MAX_CONCURRENT) -> List[Dict[str, Any]]:
    """Discover and scrape events from a listing page."""
    if not CRAWL4AI_AVAILABLE:
        return []
    
    async with Crawl4AIEventScraper() as scraper:
        return await scraper.discover_events(listing_url, max_events, max_concurrent)


def crawl4ai_check_availability() -> bool:
    """Check if Crawl4AI is available."""
    return CRAWL4AI_AVAILABLE


# Test function
async def test_crawl4ai_integration():
    """Basic test of Crawl4AI integration."""
    if not CRAWL4AI_AVAILABLE:
        print("Crawl4AI not available for testing")
        return
    
    test_url = "https://www.eventbrite.com/d/ca--san-francisco/ai-conference/"
    async with Crawl4AIEventScraper() as scraper:
        result = await scraper.scrape_single(test_url)
        print(f"Success: {result['success']}")
        print(f"Content length: {len(result.get('content', ''))}")
        print(f"Metadata: {result.get('metadata', {})}")


if __name__ == '__main__':
    asyncio.run(test_crawl4ai_integration()) 