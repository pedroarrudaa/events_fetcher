import os
import re
import json
import asyncio
from urllib.parse import urljoin, urlparse
from tavily import TavilyClient
import requests
from bs4 import BeautifulSoup
import time

# Import the new aggregator expander
from sources.aggregator_expander import (
    is_aggregator_url, 
    expand_aggregator_page, 
    expand_multiple_aggregators
)

# Note: The original import was for a function that doesn't exist in gpt_extractor.py
# from ..enrichers.gpt_extractor import extract_conference_info_from_url
# Instead, we'll import the actual available functions
from enrichers.gpt_extractor import GPTExtractor
from utils.firecrawl import FirecrawlFetcher

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# Initialize client only if API key is available
if TAVILY_API_KEY:
    client = TavilyClient(api_key=TAVILY_API_KEY)
else:
    client = None
    print("⚠️ TAVILY_API_KEY not found in environment variables. Tavily search will be skipped.")

# More specific search queries to get higher quality results
QUERIES = [
    "AI conference 2025 registration Bay Area speakers",
    "machine learning summit 2025 speakers agenda San Francisco",
    "tech conference 2025 call for papers NYC virtual",
    "generative AI conference 2025 keynote speakers virtual registration",
    "software engineering conference 2025 San Francisco agenda",
    "data science summit 2025 New York speakers virtual"
]

# Keywords that indicate a URL is likely an individual event page
EVENT_KEYWORDS = ['/event/', '/conference/', '/summit/', '/symposium/', '/workshop/', 
                 '/meeting/', '/expo/', '/forum/', '/gathering/', 'events/', 'conferences/']

# Keywords that suggest a page might be an aggregator/list page
AGGREGATOR_KEYWORDS = ['events', 'conferences', 'calendar', 'listing', 'directory', 
                      'upcoming', 'schedule', 'index', 'list', 'all-events']

# Stricter limits to prevent data quality issues
MAX_RESULTS_PER_QUERY = 5  # Reduced from 10
MAX_TOTAL_LINKS = 20       # Reduced from 50
MAX_CONFERENCES_TO_PROCESS = 10  # Process only top candidates

def normalize_url(url):
    """Normalize URL for deduplication (lowercase, strip trailing slash)."""
    if not url:
        return ""
    url = url.lower().strip()
    if url.endswith('/'):
        url = url[:-1]
    return url

def looks_us_remote_sf_ny(url: str) -> bool:
    """Check if URL looks like it's related to remote events or events in SF/NY."""
    url = url.lower()
    return (
        "remote" in url
        or "virtual" in url
        or "sanfrancisco" in url
        or "sf" in url
        or "newyork" in url
        or "nyc" in url
        or "usa" in url
        or "us" in url
    )

def is_valid_conference_url(url):
    """Check if URL looks like it could be a conference/event page."""
    if not url or not isinstance(url, str):
        return False
    
    url_lower = url.lower()
    
    # Check for event-related keywords in the URL
    for keyword in EVENT_KEYWORDS:
        if keyword in url_lower:
            return True
    
    # Check for conference-related words in the URL
    conference_words = ['conference', 'summit', 'symposium', 'workshop', 'expo', 
                       'forum', 'meeting', 'seminar', 'convention']
    for word in conference_words:
        if word in url_lower:
            return True
    
    return False

def might_be_aggregator(url):
    """Check if URL might be an aggregator/list page."""
    if not url:
        return False
    
    url_lower = url.lower()
    
    # Check for aggregator keywords
    for keyword in AGGREGATOR_KEYWORDS:
        if keyword in url_lower:
            return True
    
    return False

def extract_conference_links_from_page(url):
    """Extract conference/event links from an aggregator page."""
    try:
        print(f"🔍 Checking aggregator page: {url}")
        
        # Fetch the page content
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract all links
        links = []
        for a_tag in soup.find_all('a', href=True):
            href = a_tag.get('href')
            if not href:
                continue
            
            # Convert relative URLs to absolute
            full_url = urljoin(url, href)
            
            # Filter for URLs that look like conference pages
            if is_valid_conference_url(full_url):
                links.append(full_url)
        
        # Remove duplicates and normalize
        unique_links = list(set(normalize_url(link) for link in links if link))
        
        print(f"🔍 Expanded aggregator page: {url} → {len(unique_links)} event links")
        return unique_links
        
    except Exception as e:
        print(f"⚠️ Error extracting links from {url}: {e}")
        return []

def expand_aggregator_urls(initial_urls):
    """Expand aggregator URLs to find individual conference pages using the new aggregator expander."""
    print(f"🔍 Starting enhanced aggregator expansion for {len(initial_urls)} initial URLs")
    
    # Use the new aggregator expander module
    expanded_urls = expand_multiple_aggregators(initial_urls)
    
    print(f"🎯 Enhanced aggregator expansion complete")
    print(f"🎯 Final URL count: {len(expanded_urls)} (started with {len(initial_urls)})")
    
    return expanded_urls

def search_conference_links():
    """Search for conference URLs using Tavily API."""
    if not client:
        print("❌ Tavily client not initialized (missing API key). Skipping search.")
        return []
    
    urls = set()
    for query in QUERIES:
        print(f"🔎 Searching Tavily: {query}")
        try:
            results = client.search(query=query, max_results=MAX_RESULTS_PER_QUERY)
            for r in results.get("results", []):
                urls.add(r["url"])
        except Exception as e:
            print(f"❌ Error searching for '{query}': {e}")
    return list(urls)

def safe_firecrawl_call(url, retries=3):
    """
    Safely call Firecrawl with retry logic for rate limiting.
    
    Args:
        url: URL to process
        retries: Number of retry attempts
        
    Returns:
        Conference data or None if failed
    """
    for attempt in range(retries):
        try:
            return extract_conference_info_from_url(url)
        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "rate limit" in error_str or "too many requests" in error_str:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                print(f"⏳ Rate limit hit for {url}, retrying in {wait_time}s... (attempt {attempt + 1}/{retries})")
                time.sleep(wait_time)
            else:
                print(f"❌ Non-rate-limit error for {url}: {e}")
                return None
    
    print(f"❌ Skipping {url} after {retries} retries due to rate limiting.")
    return None

def extract_conference_info_from_url(url):
    """
    Extract conference information from a URL using GPT extractor.
    This function was referenced in the original code but didn't exist,
    so I'm implementing it here.
    """
    try:
        # Access global firecrawl_calls from main module
        try:
            import conference_fetcher.conference_fetcher as main_module
            main_module.firecrawl_calls += 1
        except Exception:
            # If we can't access the global counter, just continue
            pass
        
        # Initialize the fetcher and extractor
        fetcher = FirecrawlFetcher()
        extractor = GPTExtractor()
        
        # Fetch content from URL
        try:
            result = fetcher.scrape_url(url)
        except Exception as e:
            print(f"[Firecrawl Error] {url} → {e}")
            return None
        
        # Handle different response formats
        if hasattr(result, 'get'):
            # Dictionary-style response
            if not result.get('success', True):
                print(f"⚠️ Failed to fetch content from {url}: {result.get('error', 'Unknown error')}")
                return None
            html_content = result.get('html', '')
            markdown_content = result.get('markdown', '')
        else:
            # Object-style response - try accessing attributes directly
            try:
                if hasattr(result, 'success') and not result.success:
                    print(f"⚠️ Failed to fetch content from {url}: {getattr(result, 'error', 'Unknown error')}")
                    return None
                
                # Try to get content from object attributes
                html_content = getattr(result, 'html', '') or ''
                markdown_content = getattr(result, 'markdown', '') or ''
                
                # If no content in direct attributes, try data attribute
                if not html_content and not markdown_content and hasattr(result, 'data'):
                    data = result.data
                    if isinstance(data, dict):
                        html_content = data.get('html', '')
                        markdown_content = data.get('markdown', '')
                    
            except Exception as attr_error:
                print(f"⚠️ Error accessing response attributes from {url}: {attr_error}")
                return None
        
        # Check if we got any content
        if not html_content and not markdown_content:
            print(f"⚠️ No content retrieved from {url}")
            return None
        
        # Extract conference data using GPT
        conference_data = extractor.extract_conference_data(html_content, markdown_content, url)
        
        if conference_data and conference_data.get('extraction_success'):
            return conference_data
        else:
            print(f"⚠️ Failed to extract conference data from {url}")
            return None
            
    except Exception as e:
        print(f"❌ Error extracting info from {url}: {e}")
        return None

def get_conferences_from_google():
    """Get conferences from Tavily search results with aggregator expansion."""
    try:
        # Get initial URLs from Tavily search
        initial_urls = search_conference_links()
        
        if not initial_urls:
            print("⚠️ No URLs found from Tavily search")
            return []
        
        print(f"🔍 Found {len(initial_urls)} initial URLs from Tavily search")
        
        # Expand aggregator URLs to find individual conference pages
        expanded_urls = expand_aggregator_urls(initial_urls)
        
        if not expanded_urls:
            print("⚠️ No URLs after aggregator expansion")
            return []
        
        # Pre-filter URLs to likely remote, SF, or NY events
        filtered_urls = [url for url in expanded_urls if looks_us_remote_sf_ny(url)]
        
        # Load already enriched URLs (if exists) to avoid re-processing
        enriched_urls = set()
        output_file = "output/conferences.json"
        if os.path.exists(output_file):
            try:
                with open(output_file, 'r') as f:
                    enriched = json.load(f)
                    enriched_urls = {event.get("url") for event in enriched if "url" in event}
                print(f"📚 Found {len(enriched_urls)} already enriched URLs, skipping them")
            except Exception as e:
                print(f"⚠️ Error loading existing enriched URLs: {e}")
        
        # Filter new URLs that haven't been enriched yet
        urls_to_process = [url for url in filtered_urls if url not in enriched_urls]
        print(f"🔍 {len(urls_to_process)} new URLs to process (out of {len(filtered_urls)} filtered URLs)")
        
        # Apply stricter limits to prevent data quality issues
        all_urls = urls_to_process[:MAX_TOTAL_LINKS]
        print(f"⚠️ Limiting Tavily processing to {len(all_urls)} URLs with stricter quality filters")
        
        # Further filter for higher quality by checking URL patterns
        quality_urls = []
        for url in all_urls:
            url_lower = url.lower()
            # Prefer URLs that clearly indicate conferences/events
            if any(indicator in url_lower for indicator in [
                'conference', 'summit', 'event', 'expo', 'symposium',
                'workshop', 'meetup', 'convention', 'forum'
            ]):
                quality_urls.append(url)
        
        # If quality filtering removed too many, fall back to original list
        if len(quality_urls) < 5 and len(all_urls) >= 5:
            print(f"⚠️ Quality filtering left only {len(quality_urls)} URLs, using top {min(MAX_CONFERENCES_TO_PROCESS, len(all_urls))} original URLs")
            final_urls = all_urls[:MAX_CONFERENCES_TO_PROCESS]
        else:
            final_urls = quality_urls[:MAX_CONFERENCES_TO_PROCESS]
        
        print(f"🎯 Processing {len(final_urls)} high-quality URLs (reduced from {len(urls_to_process)} candidates)")

        events = []
        print(f"🌐 Processing {len(final_urls)} URLs for conference extraction")
        
        for i, url in enumerate(final_urls, 1):
            try:
                print(f"🌐 [{i}/{len(final_urls)}] Extracting info from: {url}")
                data = safe_firecrawl_call(url)
                if data:
                    events.append(data)
                    print(f"✅ Successfully extracted conference data from {url}")
                else:
                    print(f"⚠️ No conference data extracted from {url}")
            except Exception as url_error:
                print(f"❌ Error processing URL {url}: {url_error}")
                continue
        
        print(f"🎯 Successfully extracted {len(events)} conferences from {len(final_urls)} URLs")
        return events
        
    except Exception as e:
        print(f"❌ Error in get_conferences_from_google: {e}")
        return [] 