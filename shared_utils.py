import os
import json
import requests
import re
import time
import csv
import asyncio
import logging
from datetime import datetime, date
from dataclasses import dataclass, field, fields
from typing import List, Dict, Any, Optional, Callable, Union
from functools import lru_cache, wraps
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager, asynccontextmanager
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import aiohttp
from openai import OpenAI
from firecrawl import FirecrawlApp
from dotenv import load_dotenv
from config import *

# Load environment
load_dotenv()

# Add import for crawl4ai integration at the top
try:
    # Crawl4AI disabled - using simple scraping instead
    # from fetchers.enrichers.crawl4ai import crawl4ai_scrape_url, crawl4ai_check_availability
    CRAWL4AI_AVAILABLE = False
except ImportError:
    CRAWL4AI_AVAILABLE = False

# Import enhanced scraper at the top
try:
    from fetchers.scrapers.enhanced_scraper import EnhancedScraper, enhanced_scrape_url, enhanced_scrape_multiple
    ENHANCED_SCRAPER_AVAILABLE = True
except ImportError:
    ENHANCED_SCRAPER_AVAILABLE = False
    logger.log("warning", "Enhanced scraper not available, using basic scraping")

# Unified Logger with context
class Logger:
    def __init__(self):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger("EventsDashboard")
    
    def log(self, level: str, msg: str, **ctx):
        context = " | ".join(f"{k}={v}" for k, v in ctx.items()) if ctx else ""
        message = f"{msg} | {context}" if context else msg
        getattr(self.logger, level.lower())(message)

# Global instances
logger = Logger()

# Performance monitoring decorator
def performance_monitor(func):
    """Simple performance monitoring decorator."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = datetime.now()
        try:
            result = func(*args, **kwargs)
            duration = (datetime.now() - start_time).total_seconds()
            print(f"    {func.__name__} completed in {duration:.2f}s")
            return result
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            print(f"   {func.__name__} failed after {duration:.2f}s: {e}")
            raise
    return wrapper

# Enhanced Singleton metaclass
class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]

# Unified HTTP Client with sync/async capabilities and concurrency control
class HTTPClient(metaclass=Singleton):
    def __init__(self):
        self.session = self._create_session()
        self.connector = None
    
    def _create_session(self):
        session = requests.Session()
        retry = Retry(total=HTTP_MAX_RETRIES, backoff_factor=HTTP_BACKOFF_FACTOR, 
                     status_forcelist=[429, 500, 502, 503, 504])
        session.mount("http://", HTTPAdapter(max_retries=retry))
        session.mount("https://", HTTPAdapter(max_retries=retry))
        session.headers.update({'User-Agent': ENHANCED_USER_AGENT})
        return session
    
    def get(self, url: str, **kwargs) -> requests.Response:
        return self.session.get(url, timeout=kwargs.get('timeout', HTTP_TIMEOUT_STANDARD), **kwargs)
    
    @asynccontextmanager
    async def async_session(self, semaphore: Optional[asyncio.Semaphore] = None):
        """Async session with optional semaphore for concurrency control."""
        if not self.connector:
            self.connector = aiohttp.TCPConnector(limit=50, limit_per_host=20)
        
        if semaphore:
            async with semaphore:
                async with aiohttp.ClientSession(connector=self.connector, headers={'User-Agent': ENHANCED_USER_AGENT}) as session:
                    yield session
        else:
            async with aiohttp.ClientSession(connector=self.connector, headers={'User-Agent': ENHANCED_USER_AGENT}) as session:
                yield session

# External service clients
class ServiceClients(metaclass=Singleton):
    def __init__(self):
        self.openai = self._init_openai()
        self.firecrawl = self._init_firecrawl()
    
    def _init_openai(self):
        try:
            return OpenAI(api_key=os.getenv('OPENAI_API_KEY')) if os.getenv('OPENAI_API_KEY') else None
        except Exception as e:
            logger.log("error", "OpenAI init failed", error=str(e))
            return None
    
    def _init_firecrawl(self):
        try:
            return FirecrawlApp(api_key=os.getenv('FIRECRAWL_API_KEY')) if os.getenv('FIRECRAWL_API_KEY') else None
        except Exception as e:
            logger.log("error", "Firecrawl init failed", error=str(e))
            return None

# Data processing utilities with method chaining
@dataclass
class Event:
    """Unified event data structure with flexible field handling."""
    url: str = ""
    name: str = "TBD"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    remote: bool = False
    description: Optional[str] = None
    speakers: List[str] = field(default_factory=list)
    themes: List[str] = field(default_factory=list)
    ticket_price: Optional[str] = None
    is_paid: bool = False
    source: str = ""
    quality_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Additional fields for compatibility
    discovery_method: Optional[str] = None
    source_reliability: float = 0.0
    data_completeness: float = 0.0
    enrichment_status: Optional[str] = None
    enrichment_error: Optional[str] = None
    source_page_quality: float = 0.0
    
    def __post_init__(self):
        """Handle any unexpected fields by storing them in metadata."""
        pass
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """Create Event from dictionary, handling unexpected fields gracefully."""
        # Get all field names from the dataclass
        field_names = {f.name for f in fields(cls)}
        
        # Separate known fields from unknown ones
        known_fields = {k: v for k, v in data.items() if k in field_names}
        unknown_fields = {k: v for k, v in data.items() if k not in field_names}
        
        # Create event with known fields
        event = cls(**known_fields)
        
        # Store unknown fields in metadata
        if unknown_fields:
            if not event.metadata:
                event.metadata = {}
            event.metadata.update(unknown_fields)
        
        return event

class WebScraper:
    """Enhanced web scraper with intelligent method selection."""
    
    def __init__(self):
        self.http_client = HTTPClient()
        self.enhanced_scraper = EnhancedScraper() if ENHANCED_SCRAPER_AVAILABLE else None
        
    async def scrape_async(self, url: str, use_crawl4ai: bool = True, use_firecrawl: bool = False,
                          max_retries: int = 3, semaphore: Optional[asyncio.Semaphore] = None) -> Dict[str, Any]:
        """Async scraping with enhanced scraper support and automatic fallback."""
        if semaphore:
            async with semaphore:
                return await self._scrape_async_internal(url, use_crawl4ai, use_firecrawl, max_retries)
        else:
            return await self._scrape_async_internal(url, use_crawl4ai, use_firecrawl, max_retries)
    
    async def _scrape_async_internal(self, url: str, use_crawl4ai: bool = True,
                                   use_firecrawl: bool = False, max_retries: int = 3) -> Dict[str, Any]:
        """Internal async scraping implementation."""
        
        # Use enhanced scraper if available
        if self.enhanced_scraper and use_crawl4ai:
            try:
                result = await self.enhanced_scraper.scrape_async(url)
                if result['success']:
                    return result
                logger.log("warning", f"Enhanced scraper failed, falling back", error=result.get('error'))
            except Exception as e:
                logger.log("error", "Enhanced scraper error", error=str(e))
        
        # Fallback to Firecrawl if requested
        if use_firecrawl:
            try:
                clients = ServiceClients()
                if clients.firecrawl:
                    result = clients.firecrawl.scrape_url(url, {'formats': ['html']})
                    if result.get('success'):
                        return {
                            'success': True,
                            'content': result.get('html', ''),
                            'method': 'firecrawl',
                            'url': url
                        }
            except Exception as e:
                logger.log("error", "Firecrawl error", error=str(e))
        
        # Final fallback to simple requests
        return await self._simple_scrape_async(url, max_retries)
    
    async def _simple_scrape_async(self, url: str, max_retries: int = 3) -> Dict[str, Any]:
        """Simple async scraping with requests."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._scrape_sync_only, url, False, max_retries)
    
    async def scrape_multiple_async(self, urls: List[str], max_concurrent: int = 5,
                                  use_crawl4ai: bool = True, use_firecrawl: bool = False) -> List[Dict[str, Any]]:
        """
        Scrape multiple URLs concurrently with enhanced scraper.
        
        Args:
            urls: List of URLs to scrape
            max_concurrent: Maximum concurrent requests
            use_crawl4ai: Whether to use enhanced scraper
            use_firecrawl: Whether to use Firecrawl as fallback
            
        Returns:
            List of scraping results
        """
        if self.enhanced_scraper and use_crawl4ai:
            try:
                return await self.enhanced_scraper.scrape_multiple_async(urls, max_concurrent)
            except Exception as e:
                logger.log("error", "Enhanced batch scraping failed", error=str(e))
        
        # Fallback to semaphore-based scraping
        semaphore = asyncio.Semaphore(max_concurrent)
        tasks = [
            self.scrape_async(url, use_crawl4ai, use_firecrawl, semaphore=semaphore)
            for url in urls
        ]
        return await asyncio.gather(*tasks)
    
    def scrape(self, url: str, use_crawl4ai: bool = True, use_firecrawl: bool = False, max_retries: int = 3) -> Dict[str, Any]:
        """
        Synchronous scraping wrapper.
        
        Args:
            url: URL to scrape
            use_crawl4ai: Whether to use enhanced scraper
            use_firecrawl: Whether to use Firecrawl as fallback
            max_retries: Maximum retry attempts
            
        Returns:
            Scraping result dictionary
        """
        try:
            return asyncio.run(self.scrape_async(url, use_crawl4ai, use_firecrawl, max_retries))
        except RuntimeError:
            # If already in async context, use sync method
            return self._scrape_sync_only(url, use_firecrawl, max_retries)
    
    def _scrape_sync_only(self, url: str, use_firecrawl: bool = False, max_retries: int = 3) -> Dict[str, Any]:
        """Synchronous scraping using requests only."""
        for attempt in range(max_retries):
            try:
                response = self.http_client.get(url, timeout=HTTP_TIMEOUT_STANDARD)
                response.raise_for_status()
                
                return {
                    'success': True,
                    'content': response.text,
                    'method': 'requests',
                    'url': url,
                    'metadata': {
                        'status_code': response.status_code,
                        'attempt': attempt + 1
                    }
                }
            except Exception as e:
                if attempt == max_retries - 1:
                    return {
                        'success': False,
                        'error': str(e),
                        'method': 'requests',
                        'content': '',
                        'url': url
                    }
                time.sleep(2 ** attempt)  # Exponential backoff

class ContentEnricher:
    """AI-powered content enricher for events using GPT-4."""
    
    def __init__(self, event_type: str):
        self.event_type = event_type
        self.clients = ServiceClients()
        self.scraper = WebScraper()
    
    def enrich(self, url: str, content: str = None) -> Event:
        """Enrich event from URL using AI extraction."""
        try:
            # Scrape content if not provided
            if not content:
                logger.log("info", f"Scraping {url} for enrichment")
                
                # Use enhanced scraper with intelligent method selection
                result = self.scraper.scrape(url, use_crawl4ai=True)
                
                if not result['success']:
                    logger.log("error", f"Failed to scrape {url}", error=result.get('error'))
                    return Event(url=url, name='Scraping failed', metadata={'scrape_error': result.get('error')})
                
                content = result['content']
                
                # Log scraping method used
                logger.log("info", f"Scraped with method: {result.get('method', 'unknown')}")

            if not self.clients.openai:
                return Event(url=url, name='OpenAI unavailable')
            
            prompt = f"""Extract {self.event_type} details from the webpage content and return ONLY valid JSON.

IMPORTANT: Only extract events that are clearly related to technology, AI, software, data science, startups, or tech innovation. 
REJECT events about: real estate, finance (unless fintech), healthcare (unless healthtech), education (unless edtech), 
legal services, accounting, traditional business, fitness, entertainment, or other non-tech topics.

Focus on extracting accurate dates and locations. For dates, use YYYY-MM-DD format.
For locations, be specific (city, state/country). Only accept events in San Francisco/Bay Area or New York City.
Mark as remote only if explicitly virtual/online.

Return this exact JSON structure:
{{"name": "exact event name", "start_date": "YYYY-MM-DD or null", "end_date": "YYYY-MM-DD or null", 
"location": "specific city, state/country or null", "city": "city name or null", 
"remote": false, "description": "brief description", "speakers": [], 
"ticket_price": "price or null", "is_paid": false, "themes": []}}

If the event is not tech-related or not in SF/NYC, return: {{"name": "Not a tech event", "start_date": null, "end_date": null, "location": null, "city": null, "remote": false, "description": "Event not relevant to tech/AI focus", "speakers": [], "ticket_price": null, "is_paid": false, "themes": []}}

If information is missing, use null not "TBD". Extract what you can find."""
            
            response = self.clients.openai.chat.completions.create(
                model=GPT_MODEL_STANDARD,
                messages=[{"role": "system", "content": prompt}, {"role": "user", "content": content}],
                max_tokens=GPT_MAX_TOKENS_STANDARD,
                temperature=0.1
            )
            
            response_text = response.choices[0].message.content.strip()
            if not response_text:
                logger.log("warning", "Empty OpenAI response", url=url)
                return Event(url=url, name='Empty AI response')
            
            try:
                # Clean the response - remove markdown code blocks if present
                cleaned_response = response_text.strip()
                if cleaned_response.startswith('```json'):
                    cleaned_response = cleaned_response[7:]  # Remove ```json
                if cleaned_response.startswith('```'):
                    cleaned_response = cleaned_response[3:]   # Remove ```
                if cleaned_response.endswith('```'):
                    cleaned_response = cleaned_response[:-3]  # Remove trailing ```
                cleaned_response = cleaned_response.strip()
                
                result = json.loads(cleaned_response)
                if not isinstance(result, dict):
                    logger.log("warning", "OpenAI response not a dictionary", url=url, response=cleaned_response[:100])
                    return Event(url=url, name='Invalid AI response format')
                
                # Create Event object from extracted data
                return Event(
                    url=url,
                    name=result.get('name', 'Unknown Event'),
                    start_date=result.get('start_date'),
                    end_date=result.get('end_date'),
                    location=result.get('location'),
                    city=result.get('city'),
                    remote=result.get('remote', False),
                    description=result.get('description'),
                    speakers=result.get('speakers', []),
                    themes=result.get('themes', []),
                    ticket_price=result.get('ticket_price'),
                    is_paid=result.get('is_paid', False),
                    source=f'{self.event_type}_gpt',
                    quality_score=self._calculate_quality_score(result)
                )
            except json.JSONDecodeError as e:
                logger.log("error", "Failed to parse OpenAI JSON response", url=url, error=str(e), response=response_text[:200])
                return Event(url=url, name='AI parsing failed', metadata={'ai_response': response_text[:200]})
            
        except Exception as e:
            logger.log("error", "Enrichment failed", url=url, error=str(e))
            return Event(url=url, name='Enrichment failed', metadata={'error': str(e)})
    
    def _calculate_quality_score(self, data: Dict[str, Any]) -> float:
        """Calculate quality score for extracted data."""
        score = 0.0
        weights = {
            'name': 0.25,
            'start_date': 0.2,
            'location': 0.2,
            'description': 0.15,
            'speakers': 0.1,
            'themes': 0.1
        }
        
        for field, weight in weights.items():
            value = data.get(field)
            if value and str(value).strip() not in ['', 'null', 'None', 'TBD']:
                if isinstance(value, list) and len(value) > 0:
                    score += weight
                elif isinstance(value, str) and value:
                    score += weight
                elif value:
                    score += weight
        
        return min(score, 1.0)

class FileManager:
    """Streamlined file operations - database-only storage."""
    
    @staticmethod
    def save_events(events: List[Event], event_type: str, base_filename: str = None) -> Dict[str, str]:
        """Events are stored in database only. File generation removed for efficiency."""
        if not events:
            return {}
        
        logger.log("info", f"Processed {len(events)} {event_type}s - stored in database only")
        return {'status': 'database_only', 'count': len(events)}

class ParallelProcessor:
    """Simplified parallel processing utilities."""
    
    @staticmethod
    def process(items: List[Any], processor: Callable, max_workers: int = 10, batch_size: int = 50) -> List[Any]:
        """
        Process items in parallel using ThreadPoolExecutor.
        
        Args:
            items: List of items to process
            processor: Function to apply to each item
            max_workers: Maximum number of worker threads
            batch_size: Size of each batch (for progress tracking)
            
        Returns:
            List of processed results
        """
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Process in batches for better progress tracking
            for i in range(0, len(items), batch_size):
                batch = items[i:i + batch_size]
                
                # Submit batch tasks
                future_to_item = {executor.submit(processor, item): item for item in batch}
                
                # Collect results as they complete
                for future in as_completed(future_to_item):
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        logger.log("error", "Parallel processing failed", error=str(e))
                        # Add failed item with error info
                        item = future_to_item[future]
                        results.append({'error': str(e), 'item': item})
                
                print(f"  Processed batch: {len(results)}/{len(items)} items")
        
        return results

class ParallelAsyncProcessor:
    """Async parallel processing utilities with semaphore management."""
    
    @staticmethod
    async def process_async(items: List[Any], async_processor: Callable, 
                           max_concurrent: int = 5, batch_size: int = 20) -> List[Any]:
        """
        Process items asynchronously with proper semaphore management.
        
        Args:
            items: List of items to process
            async_processor: Async function to apply to each item
            max_concurrent: Maximum number of concurrent operations
            batch_size: Size of each batch (for progress tracking)
            
        Returns:
            List of processed results
        """
        if not items:
            return []
        
        print(f"🔄 Processing {len(items)} items asynchronously (max_concurrent={max_concurrent})")
        
        # Create semaphore within the async context to ensure it's created in the same event loop
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_semaphore(item):
            """Process single item with semaphore control."""
            async with semaphore:
                try:
                    return await async_processor(item)
                except Exception as e:
                    logger.log("error", "Async processing failed", error=str(e))
                    return {'error': str(e), 'item': item}
        
        results = []
        
        # Process in batches for better progress tracking
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            print(f"  Processing batch {i//batch_size + 1}: {len(batch)} items")
            
            # Create tasks for the batch
            tasks = [process_with_semaphore(item) for item in batch]
            
            # Execute batch concurrently
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle results and exceptions
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.log("error", "Batch processing error", error=str(result))
                    results.append({'error': str(result), 'item': 'unknown'})
                else:
                    results.append(result)
            
            print(f"  Completed batch: {len(results)}/{len(items)} items")
            
            # Small delay between batches to be respectful to servers
            if i + batch_size < len(items):
                await asyncio.sleep(0.1)
        
        successful = sum(1 for r in results if not isinstance(r, dict) or 'error' not in r)
        print(f"✅ Async processing completed: {successful}/{len(items)} successful")
        
        return results

# Search query generator with concise implementation
class QueryGenerator:
    """Enhanced search query generator for current, relevant conferences."""
    
    def __init__(self):
        self.cities = ["San Francisco", "New York", "San Francisco Bay Area", "NYC", "Manhattan", "Silicon Valley"]
        self.remote_terms = ["virtual", "remote", "online"]
        
    def generate(self, event_type: str, year: int = 2025) -> List[str]:
        """Generate search queries for event type."""
        if event_type == 'conference':
            # Core AI/Tech conference keywords
            base_keywords = [
                "AI conference", "artificial intelligence conference", "machine learning conference", 
                "data science conference", "tech conference", "developer conference",
                "ML summit", "AI summit", "tech summit", "software conference",
                "startup conference", "innovation conference"
            ]
            
            # SF/NY focused locations (PHYSICAL ONLY)
            sf_locations = ["San Francisco", "San Francisco Bay Area", "Silicon Valley", "SF", "Palo Alto", "Mountain View"]
            ny_locations = ["New York", "NYC", "Manhattan", "Brooklyn", "New York City"]
            
            queries = []
            
            # Generate targeted location-based searches (NO VIRTUAL)
            for keyword in base_keywords:
                # San Francisco area
                for location in sf_locations:
                    queries.append(f'"{keyword}" {location} {year}')
                    queries.append(f'{keyword} {location} {year}')
                
                # New York area  
                for location in ny_locations:
                    queries.append(f'"{keyword}" {location} {year}')
                    queries.append(f'{keyword} {location} {year}')
            
            # Add specific high-value tech conferences with location
            specific_conferences = [
                f"NeurIPS {year} San Francisco", f"ICML {year} New York", f"ICLR {year} San Francisco",
                f"TechCrunch Disrupt {year} San Francisco", f"AI Summit {year} New York", 
                f"Strata Data Conference {year} San Francisco", f"O'Reilly AI Conference {year}",
                f"Google I/O {year} San Francisco", f"Microsoft Build {year} New York"
            ]
            queries.extend(specific_conferences)
            
            # Add platform-specific searches for SF/NY
            for location in sf_locations + ny_locations:
                queries.append(f"eventbrite.com AI conference {location} {year}")
                queries.append(f"meetup.com tech conference {location} {year}")
            
        else:  # hackathon
            keywords = ["hackathon", "coding competition", "tech challenge", "developer contest"]
            sf_locations = ["San Francisco", "Silicon Valley", "SF", "Palo Alto"]
            ny_locations = ["New York", "NYC", "Manhattan", "Brooklyn"]
            queries = []
            for keyword in keywords:
                for city in sf_locations + ny_locations:
                    queries.append(f"{keyword} {city} {year}")
                queries.append(f'"{keyword}" {year}')
        
        return queries  # Remove the limit - let the discovery function handle limits

# Utility functions
class DateParser:
    """
    Unified date parsing class that consolidates all date format handling
    across the events dashboard. Provides a single source of truth for
    date validation, parsing, and formatting.
    """
    
    # Comprehensive list of supported date formats from all components
    SUPPORTED_FORMATS = [
        # ISO and standard formats
        '%Y-%m-%d',           # 2025-01-15 (ISO format - preferred)
        '%Y-%m-%d %H:%M:%S',  # 2025-01-15 14:30:00 (with timestamp)
        '%Y/%m/%d',           # 2025/01/15
        
        # US formats
        '%m/%d/%Y',           # 01/15/2025 (US format)
        '%m-%d-%Y',           # 01-15-2025
        
        # European formats  
        '%d/%m/%Y',           # 15/01/2025 (European format)
        '%d-%m-%Y',           # 15-01-2025
        
        # Written month formats
        '%B %d, %Y',          # January 15, 2025 (full month name)
        '%b %d, %Y',          # Jan 15, 2025 (abbreviated month name)
        '%B %d %Y',           # January 15 2025 (no comma)
        '%b %d %Y',           # Jan 15 2025 (no comma)
        
        # Additional common formats
        '%Y.%m.%d',           # 2025.01.15
        '%d.%m.%Y',           # 15.01.2025
        '%m.%d.%Y',           # 01.15.2025
    ]
    
    @classmethod
    def parse_to_date(cls, date_str: str) -> Optional[date]:
        """
        Parse various date string formats to datetime.date object.
        
        Args:
            date_str: Date string to parse
            
        Returns:
            datetime.date object or None if parsing fails
        """
        if not date_str or not isinstance(date_str, str):
            return None
            
        # Clean and validate input
        date_str = date_str.strip()
        if not date_str or date_str.upper() in ('TBD', 'N/A', 'NONE', ''):
            return None
        
        # Try each format until one works
        for fmt in cls.SUPPORTED_FORMATS:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        
        # If none of the standard formats work, return None
        return None
    
    @classmethod
    def parse_to_datetime(cls, date_str: str) -> Optional[datetime]:
        """
        Parse date string to datetime object (preserves time if present).
        
        Args:
            date_str: Date string to parse
            
        Returns:
            datetime object or None if parsing fails
        """
        if not date_str or not isinstance(date_str, str):
            return None
            
        date_str = date_str.strip()
        if not date_str or date_str.upper() in ('TBD', 'N/A', 'NONE', ''):
            return None
        
        # Try each format until one works
        for fmt in cls.SUPPORTED_FORMATS:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        return None
    
    @classmethod
    def format_to_iso(cls, date_str: str) -> Optional[str]:
        """
        Parse date string and return in ISO format (YYYY-MM-DD).
        
        Args:
            date_str: Date string to parse and format
            
        Returns:
            ISO formatted date string or None if parsing fails
        """
        parsed_date = cls.parse_to_date(date_str)
        if parsed_date:
            return parsed_date.strftime('%Y-%m-%d')
        return None
    
    @classmethod
    def is_future_date(cls, date_str: str, reference_date: Optional[date] = None) -> bool:
        """
        Check if a date string represents a future date.
        
        Args:
            date_str: Date string to check
            reference_date: Date to compare against (defaults to today)
            
        Returns:
            True if date is in the future, False otherwise.
            Returns False for unparseable dates (TBD, invalid, etc.)
        """
        parsed_date = cls.parse_to_date(date_str)
        if parsed_date is None:
            # If we can't parse the date, it's not a valid future date
            return False
        
        if reference_date is None:
            reference_date = date.today()
        
        return parsed_date > reference_date
    
    @classmethod
    def is_valid_date(cls, date_str: str) -> bool:
        """
        Check if a date string can be successfully parsed.
        
        Args:
            date_str: Date string to validate
            
        Returns:
            True if date can be parsed, False otherwise
        """
        return cls.parse_to_date(date_str) is not None
    
    @classmethod
    def get_supported_formats(cls) -> List[str]:
        """
        Get list of all supported date formats.
        
        Returns:
            List of format strings
        """
        return cls.SUPPORTED_FORMATS.copy()

# Legacy compatibility functions that now use DateParser
def validate_date(date_str: str) -> Optional[str]:
    """Validate and normalize date string. (Legacy function - use DateParser.format_to_iso)"""
    return DateParser.format_to_iso(date_str)

def deduplicate_by_url(events: List[Event]) -> List[Event]:
    """Remove duplicate events by URL."""
    seen = set()
    unique = []
    for event in events:
        url_key = event.url.lower().strip().rstrip('/')
        if url_key not in seen:
            seen.add(url_key)
            unique.append(event)
    return unique

def is_valid_event_url(url: str) -> bool:
    """Check if URL is valid for events (not generic/administrative pages)."""
    if not url or not isinstance(url, str):
        return False
    
    url_lower = url.lower()
    
    # Invalid keywords that indicate non-event pages
    invalid_keywords = [
        "login", "privacy", "terms", "about", "help", "contact", "careers", 
        "support", "settings", "register", "signup", "logout", "account",
        "linkedin.com", "twitter.com", "facebook.com", "instagram.com",
        "youtube.com", "github.com", "/api/", "/static/", "redirect?",
        "community-guidelines", "california-consumer-privacy", "legal/"
    ]
    
    # Check for invalid keywords
    if any(keyword in url_lower for keyword in invalid_keywords):
        return False
    
    # Valid event-related keywords (at least one should be present)
    valid_keywords = [
        "hackathon", "event", "challenge", "competition", "contest", 
        "summit", "conference", "workshop", "coding", "programming",
        "hack", "tech", "innovation", "startup", "dev", "developer"
    ]
    
    # URL should contain at least one valid keyword
    return any(keyword in url_lower for keyword in valid_keywords)

def generate_summary(events: List[Event], event_type: str) -> Dict[str, Any]:
    """Generate event summary statistics."""
    if not events:
        return {}
    
    return {
        'total_count': len(events),
        'remote_count': sum(1 for e in events if e.remote),
        'with_dates': sum(1 for e in events if e.start_date),
        'avg_quality': sum(e.quality_score for e in events) / len(events),
        'sources': {src: count for src, count in 
                   {e.source: sum(1 for ev in events if ev.source == e.source) for e in events}.items()},
        'top_cities': {city: count for city, count in 
                      {e.city: sum(1 for ev in events if ev.city == e.city) for e in events if e.city}.items()},
        'event_type': event_type
    }

# Legacy compatibility
def clean_event_data(events: List[Dict[str, Any]], event_type: str = "events") -> List[Dict[str, Any]]:
    """Legacy wrapper for event cleaning."""
    # Simply return events as-is since EventProcessor was removed
    # The new EventService handles all processing
    return events 