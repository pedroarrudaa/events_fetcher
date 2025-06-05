import os
import re
import json
import asyncio
from urllib.parse import urljoin, urlparse
from tavily import TavilyClient
import requests
from bs4 import BeautifulSoup
import time
from typing import List

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

# Enhanced search queries for better fallback coverage
FALLBACK_QUERIES = [
    "developer conference 2025 San Francisco virtual speakers",
    "Python conference 2025 New York agenda registration",
    "JavaScript summit 2025 Bay Area virtual tickets",
    "DevOps conference 2025 remote speakers",
    "cloud computing conference 2025 SF NYC",
    "startup tech event 2025 Silicon Valley"
]

# Domain reputation scoring for better filtering
TRUSTED_DOMAINS = {
    # High reputation conference domains
    'eventbrite.com': 0.9,
    'meetup.com': 0.8,
    'conference.ieee.org': 0.95,
    'acm.org': 0.95,
    'oreilly.com': 0.9,
    'techcrunch.com': 0.85,
    'venturebeat.com': 0.8,
    'infoq.com': 0.85,
    'kdnuggets.com': 0.8,
    'towards-data-science.medium.com': 0.75,
    'conferencelist.info': 0.7,
    'conferenceindex.org': 0.7,
    'allconferences.com': 0.6,
    # University domains get high scores
    '.edu': 0.9,
    # Organization domains
    '.org': 0.75,
    # Professional networks
    'linkedin.com': 0.6,
}

BLACKLISTED_DOMAINS = {
    'facebook.com', 'twitter.com', 'instagram.com', 'youtube.com',
    'pinterest.com', 'tiktok.com', 'snapchat.com',
    'reddit.com', 'quora.com', 'stackoverflow.com',
    'wikipedia.org', 'wikimedia.org',
    'amazon.com', 'ebay.com', 'alibaba.com',
    'indeed.com', 'glassdoor.com', 'monster.com',
    'craigslist.org', 'gumtree.com',
    'spam-site.com', 'fake-conferences.com'  # Add known spam domains
}

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

def get_domain_reputation_score(url: str) -> float:
    """
    Calculate a reputation score for a domain based on trustworthiness.
    
    Args:
        url: URL to score
        
    Returns:
        Float between 0.0 and 1.0, where 1.0 is most trusted
    """
    try:
        domain = urlparse(url).netloc.lower()
        
        # Check blacklist first
        if any(blacklisted in domain for blacklisted in BLACKLISTED_DOMAINS):
            return 0.0
        
        # Check exact matches in trusted domains
        if domain in TRUSTED_DOMAINS:
            return TRUSTED_DOMAINS[domain]
        
        # Check for partial matches (like .edu, .org)
        for trusted_pattern, score in TRUSTED_DOMAINS.items():
            if trusted_pattern.startswith('.') and domain.endswith(trusted_pattern):
                return score
            elif trusted_pattern in domain:
                return score * 0.8  # Slightly lower for partial matches
        
        # Default score for unknown domains
        if any(tld in domain for tld in ['.com', '.net', '.io', '.co']):
            return 0.5  # Neutral for common TLDs
        
        return 0.3  # Lower for unusual TLDs
        
    except Exception:
        return 0.1  # Very low for malformed URLs

def validate_tavily_result(result: dict) -> tuple[bool, str]:
    """
    Validate a Tavily search result for quality and relevance.
    
    Args:
        result: Tavily search result dictionary
        
    Returns:
        Tuple of (is_valid, reason)
    """
    url = result.get('url', '')
    title = result.get('title', '')
    content = result.get('content', '')
    
    # Check domain reputation
    reputation_score = get_domain_reputation_score(url)
    if reputation_score < 0.3:
        return False, f"Low domain reputation: {reputation_score}"
    
    # Check for conference-related content
    conference_keywords = [
        'conference', 'summit', 'symposium', 'expo', 'convention',
        'workshop', 'meetup', 'event', 'gathering', 'forum',
        'speakers', 'keynote', 'agenda', 'registration', 'tickets'
    ]
    
    combined_text = f"{title} {content}".lower()
    keyword_matches = sum(1 for keyword in conference_keywords if keyword in combined_text)
    
    if keyword_matches < 2:
        return False, f"Insufficient conference keywords: {keyword_matches}"
    
    # Check for 2025 content (future events)
    if '2025' not in combined_text and '2024' not in combined_text:
        return False, "No current/future year mentioned"
    
    # Check for spam indicators
    spam_indicators = [
        'click here', 'free money', 'guaranteed', 'limited time',
        'act now', 'exclusive offer', 'download now', 'sign up now'
    ]
    
    spam_matches = sum(1 for indicator in spam_indicators if indicator in combined_text)
    if spam_matches > 2:
        return False, f"Too many spam indicators: {spam_matches}"
    
    # Check minimum content length
    if len(combined_text) < 50:
        return False, "Content too short"
    
    return True, "Valid result"

def enhanced_search_conference_links() -> List[dict]:
    """
    Enhanced search for conference URLs using Tavily API with better filtering.
    
    Returns:
        List of validated search results with metadata
    """
    if not client:
        print("❌ Tavily client not initialized (missing API key). Skipping search.")
        return []
    
    all_results = []
    queries_to_try = QUERIES.copy()
    
    for query in queries_to_try:
        print(f"🔎 Searching Tavily: {query}")
        try:
            results = client.search(query=query, max_results=MAX_RESULTS_PER_QUERY)
            
            for result in results.get("results", []):
                # Validate each result
                is_valid, reason = validate_tavily_result(result)
                
                if is_valid:
                    # Add metadata
                    enhanced_result = {
                        **result,
                        'search_query': query,
                        'domain_reputation': get_domain_reputation_score(result.get('url', '')),
                        'validation_reason': reason
                    }
                    all_results.append(enhanced_result)
                    print(f"   ✅ Valid: {result.get('title', 'No title')[:50]}...")
                else:
                    print(f"   ❌ Filtered: {reason} - {result.get('title', 'No title')[:30]}...")
                    
        except Exception as e:
            print(f"❌ Error searching for '{query}': {e}")
            continue
    
    # If we have too few results, try fallback queries
    if len(all_results) < 5:
        print(f"🔄 Only found {len(all_results)} results, trying fallback queries...")
        
        for fallback_query in FALLBACK_QUERIES[:3]:  # Try first 3 fallback queries
            print(f"🔎 Fallback search: {fallback_query}")
            try:
                results = client.search(query=fallback_query, max_results=3)
                
                for result in results.get("results", []):
                    is_valid, reason = validate_tavily_result(result)
                    
                    if is_valid:
                        enhanced_result = {
                            **result,
                            'search_query': fallback_query,
                            'domain_reputation': get_domain_reputation_score(result.get('url', '')),
                            'validation_reason': reason,
                            'is_fallback': True
                        }
                        all_results.append(enhanced_result)
                        print(f"   ✅ Fallback valid: {result.get('title', 'No title')[:50]}...")
                        
                        # Stop if we have enough results
                        if len(all_results) >= 15:
                            break
                            
            except Exception as e:
                print(f"❌ Error in fallback search for '{fallback_query}': {e}")
                continue
            
            if len(all_results) >= 15:
                break
    
    # Sort by domain reputation (highest first)
    all_results.sort(key=lambda x: x.get('domain_reputation', 0), reverse=True)
    
    print(f"🎯 Enhanced search complete: {len(all_results)} validated results")
    return all_results

def search_conference_links():
    """Legacy function - now calls enhanced search for backward compatibility."""
    results = enhanced_search_conference_links()
    return [result['url'] for result in results]

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
    """Get conferences from Tavily search results with enhanced filtering and fallbacks."""
    try:
        print("🌍 Starting enhanced Tavily discovery with multi-stage filtering...")
        
        # Step 1: Get enhanced search results with intelligent filtering
        search_results = enhanced_search_conference_links()
        if not search_results:
            print("❌ No search results from enhanced Tavily search")
            return []
        
        print(f"📊 Enhanced search returned {len(search_results)} raw results")
        
        # Step 2: Apply multi-stage intelligent filtering
        high_quality_urls = process_search_results_with_intelligent_filtering(search_results)
        
        if not high_quality_urls:
            print("❌ No URLs passed intelligent filtering")
            return []
        
        print(f"🎯 {len(high_quality_urls)} URLs passed intelligent filtering")
        
        # Step 3: Expand aggregator pages if any
        print("🔍 Checking for aggregator pages to expand...")
        expanded_urls = []
        aggregator_count = 0
        
        for url in high_quality_urls:
            if is_aggregator_url(url):
                print(f"📄 Found aggregator page: {url}")
                aggregator_count += 1
                try:
                    expanded = expand_aggregator_page(url)
                    if expanded:
                        expanded_urls.extend(expanded)
                        print(f"   ✅ Expanded to {len(expanded)} conference URLs")
                    else:
                        # Keep original URL if expansion fails
                        expanded_urls.append(url)
                        print(f"   ⚠️ Expansion failed, keeping original URL")
                except Exception as e:
                    print(f"   ❌ Error expanding aggregator {url}: {e}")
                    expanded_urls.append(url)  # Fallback to original
            else:
                expanded_urls.append(url)
        
        print(f"📊 Expansion complete: {aggregator_count} aggregators processed")
        print(f"🔗 Total URLs after expansion: {len(expanded_urls)}")
        
        # Step 4: Final URL validation and cleanup
        final_urls = []
        seen_urls = set()
        
        for url in expanded_urls:
            normalized = normalize_url(url)
            if normalized not in seen_urls and is_valid_conference_url(url):
                final_urls.append(url)
                seen_urls.add(normalized)
        
        print(f"✅ Final URL list: {len(final_urls)} unique, validated URLs")
        
        # Step 5: Load existing enriched data to avoid re-processing
        output_file = "data/enriched_conferences.json"
        enriched_urls = set()
        
        if os.path.exists(output_file):
            try:
                with open(output_file, 'r') as f:
                    enriched = json.load(f)
                    enriched_urls = {event.get("url") for event in enriched if "url" in event}
                print(f"📚 Found {len(enriched_urls)} already enriched URLs, skipping them")
            except Exception as e:
                print(f"⚠️ Error loading existing enriched URLs: {e}")
        
        # Filter new URLs that haven't been enriched yet
        urls_to_process = [url for url in final_urls if url not in enriched_urls]
        print(f"🔍 {len(urls_to_process)} new URLs to process (out of {len(final_urls)} total)")
        
        if not urls_to_process:
            print("ℹ️ All URLs have already been processed")
            return []
        
        # Step 6: Process URLs with enhanced error handling and fallbacks
        events = []
        failed_urls = []
        success_count = 0
        
        print(f"🌐 Processing {len(urls_to_process)} URLs for conference extraction")
        
        for i, url in enumerate(urls_to_process, 1):
            try:
                print(f"🌐 [{i}/{len(urls_to_process)}] Extracting info from: {url}")
                
                # Try primary extraction
                data = safe_firecrawl_call(url)
                
                if data:
                    # Enhanced validation with quality scoring
                    if validate_extracted_conference_data(data):
                        events.append(data)
                        success_count += 1
                        quality_score = data.get('quality_score', 0)
                        print(f"✅ Successfully extracted conference data from {url} (quality: {quality_score:.2f})")
                    else:
                        print(f"⚠️ Extracted data failed enhanced validation for {url}")
                        failed_urls.append(url)
                else:
                    print(f"⚠️ No conference data extracted from {url}")
                    failed_urls.append(url)
                    
            except Exception as url_error:
                print(f"❌ Error processing URL {url}: {url_error}")
                failed_urls.append(url)
                continue
        
        # Step 7: Enhanced fallback processing for failed URLs
        if failed_urls and len(events) < 3:
            print(f"🔄 Attempting enhanced fallback processing for {len(failed_urls)} failed URLs...")
            
            # Try up to 5 fallbacks, prioritizing higher-scored original results
            failed_with_scores = []
            for url in failed_urls:
                # Find original result score if available
                original_score = 0.5  # Default
                for result in search_results:
                    if result.get('url') == url:
                        original_score = result.get('comprehensive_score', 0.5)
                        break
                failed_with_scores.append((url, original_score))
            
            # Sort by score and try top failures
            failed_with_scores.sort(key=lambda x: x[1], reverse=True)
            
            for url, score in failed_with_scores[:5]:
                try:
                    print(f"🔄 Enhanced fallback attempt for: {url} (score: {score:.2f})")
                    
                    # Try alternative extraction with more lenient validation
                    fallback_data = enhanced_fallback_extraction_method(url)
                    
                    if fallback_data and fallback_data.get('extraction_success'):
                        # Apply lighter validation for fallback data
                        if validate_fallback_data(fallback_data):
                            events.append(fallback_data)
                            print(f"✅ Enhanced fallback extraction successful for {url}")
                        else:
                            print(f"⚠️ Fallback data failed validation for {url}")
                    
                except Exception as fallback_error:
                    print(f"❌ Enhanced fallback failed for {url}: {fallback_error}")
                    continue
        
        # Step 8: Final quality assessment and reporting
        high_quality_count = sum(1 for event in events if event.get('quality_score', 0) >= 0.7)
        medium_quality_count = sum(1 for event in events if 0.4 <= event.get('quality_score', 0) < 0.7)
        low_quality_count = len(events) - high_quality_count - medium_quality_count
        
        print(f"🎯 Enhanced Tavily discovery complete:")
        print(f"   • Initial search results: {len(search_results)}")
        print(f"   • After intelligent filtering: {len(high_quality_urls)}")
        print(f"   • After expansion: {len(expanded_urls)}")
        print(f"   • Final validated URLs: {len(final_urls)}")
        print(f"   • Successfully extracted: {len(events)}")
        print(f"   • Failed extractions: {len(failed_urls)}")
        print(f"   • Quality breakdown: {high_quality_count} high, {medium_quality_count} medium, {low_quality_count} low")
        
        return events
        
    except Exception as e:
        print(f"❌ Error in enhanced get_conferences_from_google: {e}")
        return []

def validate_extracted_conference_data(data: dict) -> bool:
    """
    Enhanced validation of extracted conference data for quality and completeness.
    
    Args:
        data: Extracted conference data dictionary
        
    Returns:
        True if data meets enhanced quality standards
    """
    try:
        # Check if extraction was successful
        if not data.get('extraction_success', False):
            return False
        
        # Enhanced name validation
        name = data.get('name', '').strip()
        if not name or len(name) < 5:
            return False
        
        # Check for spam-like names with more patterns
        spam_patterns = [
            r'^[A-Z\s]+$',  # All caps
            r'^\d+',        # Starts with number
            r'click here', r'register now', r'free trial',
            r'download now', r'sign up', r'subscribe',
            r'^(unknown|tbd|n/a|none)$',  # Generic placeholders
            r'^(conference|event|summit|meeting)\s*$',  # Just generic words
            r'^.{1,3}$',    # Too short (1-3 characters)
            r'^\W+$'        # Only special characters
        ]
        
        for pattern in spam_patterns:
            if re.search(pattern, name, re.I):
                print(f"   ❌ Rejected spam-like name: {name}")
                return False
        
        # Check quality score if available
        quality_score = data.get('quality_score', 0)
        if quality_score < 0.3:  # Minimum quality threshold
            print(f"   ❌ Rejected low quality score: {quality_score}")
            return False
        
        # Check for meaningful content beyond just name
        description = data.get('short_description', '') or data.get('description', '')
        speakers = data.get('speakers', [])
        themes = data.get('themes', [])
        start_date = data.get('start_date')
        city = data.get('city')
        remote = data.get('remote')
        
        # Calculate content richness score
        content_score = 0
        
        if description and len(description) > 30:
            content_score += 0.3
            # Extra points for meaningful descriptions
            meaningful_desc_words = ['conference', 'speakers', 'sessions', 'networking', 'learn', 'discuss', 'industry']
            if sum(1 for word in meaningful_desc_words if word in description.lower()) >= 2:
                content_score += 0.2
        
        if speakers and len([s for s in speakers if s and len(str(s)) > 3]) > 0:
            content_score += 0.2
        
        if start_date and start_date not in ['unknown', 'tbd', 'n/a', None]:
            content_score += 0.15
        
        if (city and city.lower() not in ['unknown', 'tbd', 'n/a']) or remote is True:
            content_score += 0.15
        
        if themes and len(themes) > 0:
            content_score += 0.1
        
        # Require minimum content richness
        if content_score < 0.25:
            print(f"   ❌ Rejected insufficient content richness: {content_score}")
            return False
        
        # Final validation - check for obvious non-conference indicators
        all_text = f"{name} {description}".lower()
        
        non_conference_indicators = [
            'blog post', 'article', 'tutorial', 'guide', 'course',
            'user profile', 'sign up', 'subscription', 'newsletter',
            'platform', 'software', 'tool', 'service',
            'case study', 'white paper', 'documentation',
            'pricing', 'demo', 'trial'
        ]
        
        spam_score = sum(1 for indicator in non_conference_indicators if indicator in all_text)
        if spam_score > 2:
            print(f"   ❌ Rejected too many non-conference indicators: {spam_score}")
            return False
        
        print(f"   ✅ Validated conference data: {name[:50]}... (quality: {quality_score}, content: {content_score})")
        return True
        
    except Exception as e:
        print(f"   ❌ Validation error: {e}")
        return False

def enhanced_fallback_extraction_method(url: str) -> dict:
    """
    Enhanced fallback extraction method with multiple strategies.
    
    Args:
        url: URL to extract from
        
    Returns:
        Conference data or None if all methods fail
    """
    print(f"🔧 Attempting enhanced fallback extraction for: {url}")
    
    try:
        # Strategy 1: Try requests with different user agents
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (compatible; conference-bot/2.0; +https://example.com/bot)'
        ]
        
        html_content = None
        for ua in user_agents:
            try:
                headers = {'User-Agent': ua, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}
                response = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
                response.raise_for_status()
                html_content = response.text
                break
            except Exception as e:
                print(f"   ⚠️ User agent {ua[:30]}... failed: {e}")
                continue
        
        if not html_content:
            print(f"   ❌ All request methods failed for {url}")
            return None
        
        # Strategy 2: Enhanced basic parsing with ML-like features
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove noise
        for tag in soup(['script', 'style', 'nav', 'footer', 'aside', 'header']):
            tag.decompose()
        
        # Extract title with confidence scoring
        title_candidates = []
        
        # Check multiple title sources with confidence scores
        title_sources = [
            (soup.find('h1'), 0.9),
            (soup.find('title'), 0.7),
            (soup.find('meta', {'property': 'og:title'}), 0.8),
            (soup.find('meta', {'name': 'twitter:title'}), 0.8),
            (soup.find('h2'), 0.6)
        ]
        
        for source, confidence in title_sources:
            if source:
                if source.name == 'meta':
                    text = source.get('content', '').strip()
                else:
                    text = source.get_text().strip()
                
                if text and len(text) > 5:
                    # Score based on conference indicators
                    conf_score = 0
                    conf_words = ['conference', 'summit', 'symposium', 'expo', 'workshop', '2024', '2025']
                    for word in conf_words:
                        if word.lower() in text.lower():
                            conf_score += 0.1
                    
                    total_score = confidence + conf_score
                    title_candidates.append((text, total_score))
        
        # Select best title
        if title_candidates:
            title = max(title_candidates, key=lambda x: x[1])[0]
            # Clean title
            title = re.sub(r'\s*[-|]\s*(home|homepage).*$', '', title, flags=re.I)
            title = re.sub(r'\s+', ' ', title).strip()
        else:
            return None
        
        # Enhanced description extraction
        description = None
        desc_candidates = []
        
        # Try multiple description sources
        meta_descs = [
            soup.find('meta', {'name': 'description'}),
            soup.find('meta', {'property': 'og:description'}),
            soup.find('meta', {'name': 'twitter:description'})
        ]
        
        for meta in meta_descs:
            if meta:
                desc = meta.get('content', '').strip()
                if desc and len(desc) > 20:
                    desc_candidates.append((desc, 0.8))
        
        # Try content extraction
        content_selectors = [
            ('.description', 0.9),
            ('.summary', 0.9),
            ('.intro', 0.8),
            ('p.lead', 0.7),
            ('p:first-of-type', 0.6)
        ]
        
        for selector, confidence in content_selectors:
            elem = soup.select_one(selector)
            if elem:
                desc = elem.get_text().strip()
                if 30 <= len(desc) <= 300:
                    desc_candidates.append((desc, confidence))
        
        if desc_candidates:
            description = max(desc_candidates, key=lambda x: x[1])[0]
        
        # Extract structured information
        text_content = soup.get_text().lower()
        
        # Enhanced remote detection
        remote_patterns = [
            r'virtual\s+(conference|event|summit)',
            r'online\s+(conference|event|summit)',
            r'remote\s+(conference|event|summit)',
            r'webinar', r'zoom\s+meeting', r'teams\s+meeting'
        ]
        
        is_remote = any(re.search(pattern, text_content) for pattern in remote_patterns)
        
        # Enhanced location extraction
        city = None
        if not is_remote:
            location_patterns = [
                r'(?:location|venue|address):\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                r'(?:in|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),?\s*(?:CA|NY|TX|USA)',
                r'([A-Z][a-z]+),\s*(?:California|New York|Texas|USA)'
            ]
            
            for pattern in location_patterns:
                match = re.search(pattern, text_content, re.I)
                if match:
                    city = match.group(1).strip()
                    if len(city) > 2:
                        break
        
        # Create enhanced conference data
        conference_data = {
            'name': title,
            'url': url,
            'short_description': description or 'Conference information extracted via enhanced fallback method',
            'remote': is_remote,
            'city': city,
            'start_date': None,
            'end_date': None,
            'registration_deadline': None,
            'speakers': [],
            'sponsors': [],
            'ticket_price': None,
            'is_paid': None,
            'themes': [],
            'eligibility': None,
            'extraction_success': True,
            'extraction_method': 'enhanced-fallback',
            'quality_score': 0.4,  # Medium quality for fallback
            'quality_flags': ['enhanced_fallback', 'basic_extraction']
        }
        
        print(f"✅ Enhanced fallback extraction successful: {title[:50]}...")
        return conference_data
        
    except Exception as e:
        print(f"❌ Enhanced fallback extraction failed: {e}")
        return None

def validate_fallback_data(data: dict) -> bool:
    """
    Validate fallback data with more lenient criteria.
    
    Args:
        data: Fallback conference data
        
    Returns:
        True if data meets minimum fallback standards
    """
    name = data.get('name', '').strip()
    
    # Basic name validation
    if not name or len(name) < 5:
        return False
    
    # Check for obvious spam
    if any(spam in name.lower() for spam in ['click here', 'register now', 'download']):
        return False
    
    # Must have some description or location info
    description = data.get('short_description', '')
    city = data.get('city')
    remote = data.get('remote')
    
    if not description and not city and not remote:
        return False
    
    return True

def process_search_results_with_intelligent_filtering(search_results: List[dict]) -> List[str]:
    """
    Process search results with multi-stage intelligent filtering.
    
    Args:
        search_results: Raw search results from Tavily
        
    Returns:
        List of high-quality, filtered URLs
    """
    print(f"🎯 Processing {len(search_results)} search results with intelligent filtering...")
    
    # Stage 1: Basic validation and scoring
    stage1_results = []
    for result in search_results:
        is_valid, reason = validate_tavily_result(result)
        if is_valid:
            # Add enhanced scoring
            url = result.get('url', '')
            title = result.get('title', '')
            content = result.get('content', '')
            
            # Calculate comprehensive score
            score = calculate_comprehensive_result_score(result)
            
            enhanced_result = {
                **result,
                'comprehensive_score': score,
                'validation_reason': reason
            }
            stage1_results.append(enhanced_result)
            print(f"   ✅ Stage 1 pass: {title[:50]}... (score: {score:.2f})")
        else:
            print(f"   ❌ Stage 1 fail: {result.get('title', 'No title')[:50]}... - {reason}")
    
    print(f"📊 Stage 1 complete: {len(stage1_results)}/{len(search_results)} passed basic validation")
    
    # Stage 2: Intelligent content analysis
    stage2_results = []
    for result in stage1_results:
        if analyze_result_content_quality(result):
            stage2_results.append(result)
            print(f"   ✅ Stage 2 pass: {result.get('title', '')[:50]}...")
        else:
            print(f"   ❌ Stage 2 fail: {result.get('title', '')[:50]}... - content quality issues")
    
    print(f"📊 Stage 2 complete: {len(stage2_results)}/{len(stage1_results)} passed content analysis")
    
    # Stage 3: Deduplication and final ranking
    stage3_results = deduplicate_and_rank_results(stage2_results)
    
    print(f"📊 Stage 3 complete: {len(stage3_results)} unique, ranked results")
    
    # Extract URLs and return
    final_urls = [result['url'] for result in stage3_results[:20]]  # Top 20 results
    return final_urls

def calculate_comprehensive_result_score(result: dict) -> float:
    """
    Calculate a comprehensive quality score for a search result.
    
    Args:
        result: Search result dictionary
        
    Returns:
        Comprehensive quality score (0.0 to 1.0)
    """
    score = 0.0
    
    url = result.get('url', '')
    title = result.get('title', '')
    content = result.get('content', '')
    
    # Domain reputation (40% weight)
    domain_score = get_domain_reputation_score(url)
    score += domain_score * 0.4
    
    # Title quality (25% weight)
    title_score = 0.0
    if title:
        # Length bonus
        if 20 <= len(title) <= 100:
            title_score += 0.3
        
        # Conference keyword bonus
        conf_keywords = ['conference', 'summit', 'symposium', 'expo', 'workshop', '2024', '2025']
        keyword_matches = sum(1 for keyword in conf_keywords if keyword.lower() in title.lower())
        title_score += min(0.4, keyword_matches * 0.1)
        
        # Professional title indicators
        if any(indicator in title.lower() for indicator in ['annual', 'international', 'global', 'tech', 'ai', 'data']):
            title_score += 0.2
        
        # Penalty for spam indicators
        if any(spam in title.lower() for spam in ['click here', 'register now', 'free trial']):
            title_score -= 0.3
    
    score += min(1.0, title_score) * 0.25
    
    # Content quality (25% weight)
    content_score = 0.0
    if content:
        # Length bonus
        if 100 <= len(content) <= 1000:
            content_score += 0.3
        
        # Conference-related content
        conf_content_words = ['speakers', 'agenda', 'sessions', 'networking', 'presentations', 'keynote', 'registration']
        content_matches = sum(1 for word in conf_content_words if word.lower() in content.lower())
        content_score += min(0.4, content_matches * 0.08)
        
        # Date/location indicators
        if any(indicator in content.lower() for indicator in ['2024', '2025', 'march', 'april', 'may', 'june']):
            content_score += 0.1
        
        # Professional language
        if any(term in content.lower() for term in ['industry', 'professional', 'expert', 'leader']):
            content_score += 0.1
    
    score += min(1.0, content_score) * 0.25
    
    # URL structure quality (10% weight)
    url_score = 0.0
    if url:
        # Prefer shorter, cleaner URLs
        if len(url) < 100:
            url_score += 0.3
        
        # Conference-related path
        if any(keyword in url.lower() for keyword in ['conference', 'event', 'summit', '2024', '2025']):
            url_score += 0.4
        
        # Penalty for complex URLs with many parameters
        if url.count('?') > 1 or url.count('&') > 3:
            url_score -= 0.3
    
    score += max(0.0, url_score) * 0.1
    
    return min(1.0, max(0.0, score))

def analyze_result_content_quality(result: dict) -> bool:
    """
    Analyze the content quality of a search result for conference relevance.
    
    Args:
        result: Search result dictionary
        
    Returns:
        True if content quality is sufficient
    """
    title = result.get('title', '').lower()
    content = result.get('content', '').lower()
    url = result.get('url', '').lower()
    
    all_text = f"{title} {content}"
    
    # Check for minimum conference indicators
    conference_indicators = [
        'conference', 'summit', 'symposium', 'expo', 'convention',
        'workshop', 'meetup', 'event', 'gathering', 'congress',
        'speakers', 'keynote', 'agenda', 'sessions', 'networking'
    ]
    
    indicator_count = sum(1 for indicator in conference_indicators if indicator in all_text)
    if indicator_count < 2:
        return False
    
    # Check for future event indicators
    future_indicators = ['2024', '2025', 'upcoming', 'registration open', 'early bird', 'call for papers']
    has_future_indicators = any(indicator in all_text for indicator in future_indicators)
    
    # Check for quality signals
    quality_signals = [
        'international', 'annual', 'professional', 'industry',
        'expert', 'leader', 'innovation', 'research', 'academic'
    ]
    
    quality_signal_count = sum(1 for signal in quality_signals if signal in all_text)
    
    # Red flags for non-conference content
    red_flags = [
        'blog post', 'article series', 'tutorial', 'course',
        'user profile', 'sign up now', 'free trial',
        'white paper', 'case study', 'documentation',
        'software platform', 'business solution'
    ]
    
    red_flag_count = sum(1 for flag in red_flags if flag in all_text)
    
    # Decision logic
    if red_flag_count > 1:
        return False
    
    if indicator_count >= 3 and (has_future_indicators or quality_signal_count >= 2):
        return True
    
    if indicator_count >= 4:
        return True
    
    return False

def deduplicate_and_rank_results(results: List[dict]) -> List[dict]:
    """
    Remove duplicates and rank results by comprehensive score.
    
    Args:
        results: List of validated search results
        
    Returns:
        Deduplicated and ranked results
    """
    print("🔄 Deduplicating and ranking results...")
    
    # Group by normalized URL to remove duplicates
    url_groups = {}
    for result in results:
        url = result.get('url', '')
        normalized_url = normalize_url(url)
        
        if normalized_url not in url_groups:
            url_groups[normalized_url] = []
        url_groups[normalized_url].append(result)
    
    # Keep the highest scored result from each group
    deduplicated = []
    for url, group in url_groups.items():
        if len(group) == 1:
            deduplicated.append(group[0])
        else:
            # Keep the one with highest comprehensive score
            best_result = max(group, key=lambda x: x.get('comprehensive_score', 0))
            deduplicated.append(best_result)
    
    # Sort by comprehensive score (highest first)
    ranked_results = sorted(deduplicated, key=lambda x: x.get('comprehensive_score', 0), reverse=True)
    
    print(f"✅ Deduplication complete: {len(ranked_results)} unique results (from {len(results)} total)")
    
    return ranked_results 