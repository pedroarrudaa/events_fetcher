# This file consolidates all hard-coded values for better maintainability

import os

# HTTP Configuration
HTTP_TIMEOUT_SHORT = 10         # Short timeout for quick requests
HTTP_TIMEOUT_STANDARD = 15      # Standard timeout for most requests
HTTP_TIMEOUT_LONG = 60          # Long timeout for heavy requests

# HTTP Connection Pooling and Retry Configuration
HTTP_MAX_RETRIES = 3            # Maximum number of HTTP retries
HTTP_BACKOFF_FACTOR = 0.3       # Backoff factor for retries
HTTP_BACKOFF_INITIAL = 1        # Initial backoff time in seconds

# Enhanced User Agent for better request handling
ENHANCED_USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'

# API Configuration
OPENAI_TIMEOUT_READ = 60.0
OPENAI_TIMEOUT_WRITE = 60.0
OPENAI_TIMEOUT_CONNECT = 10.0

# GPT Processing Configuration
GPT_MODEL_STANDARD = "gpt-4.1-mini"          # Standard GPT model
GPT_MODEL_ADVANCED = "gpt-4.1-mini"
GPT_TEMPERATURE_STANDARD = 0.1                 # Low temperature for consistent extraction
GPT_TIMEOUT_STANDARD = 60                      # GPT request timeout
GPT_MAX_CONTENT_CHARS = 12000                  # Conservative limit for GPT content
GPT_MAX_TOKENS_STANDARD = 1000                 # Standard token limit
GPT_MAX_TOKENS_ADVANCED = 2000                 # Advanced token limit
GPT_MAX_TOKENS_REDUCED = 1000                  # Reduced token limit
GPT_MAX_TOKENS_MINIMAL = 800                   # Minimal token limit
GPT_TEMPERATURE = 0.1                          # Low temperature for consistent extraction

# Retry Configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_INITIAL_BACKOFF = 5     # seconds
DEFAULT_BACKOFF_FACTOR = 2

# Rate Limiting (sleep times)
RATE_LIMIT_SHORT = 1            # Short delay between requests
RATE_LIMIT_MEDIUM = 2           # Medium delay for rate limiting
RATE_LIMIT_LONG = 3             # Long delay for heavy scraping
RATE_LIMIT_DEVPOST = 7          # Special delay for Devpost

# Content Processing
MAX_TITLE_LENGTH = 100          # Maximum title length for logging
MAX_DESCRIPTION_LENGTH = 300    # Maximum description length
MAX_SHORT_DESCRIPTION = 200     # Maximum short description length
TRUNCATED_CONTENT_SUFFIX = "...[CONTENT TRUNCATED]"

# Display Configuration
MAX_DISPLAY_TITLE = 50         # Maximum characters in display titles
MAX_DISPLAY_URL = 100          # Maximum characters in display URLs  
MAX_DISPLAY_DESCRIPTION = 200  # Maximum characters in display descriptions
MAX_DISPLAY_NAME = 60           # Maximum name length for display
MAX_DISPLAY_SHORT = 50          # Maximum short text display
MAX_DISPLAY_VERY_SHORT = 30     # Maximum very short text display

# Response Truncation
MAX_RAW_RESPONSE_DISPLAY = 500  # Maximum raw response length to display
MAX_ERROR_RESPONSE_DISPLAY = 200  # Maximum error response length

# Summary Configuration
MAX_CITIES_DISPLAY = 20         # Maximum cities to show in summary
MAX_TOPICS_DISPLAY = 15         # Maximum topics to show in summary
MAX_EXAMPLES_DISPLAY = 3        # Maximum examples to show
MAX_QUALITY_EXAMPLES = 3        # Maximum quality examples

# Filtering Configuration  
MAX_SPEAKERS_LIMIT = 5          # Maximum speakers to keep
MAX_CONTENT_FOR_DATES = 8000    # Maximum content length for date extraction
MAX_CONTENT_FOR_PARSING = 50000  # Maximum content length for basic parsing

# File Processing
MAX_HTML_SIZE_LOG = None        # No limit on HTML size logging (use actual size)
MAX_PAGE_TITLE_LOG = 60         # Maximum page title length for logging

# Database Configuration (from README.md)
MAX_POOL_SIZE = 10
POOL_TIMEOUT = 30
STATEMENT_TIMEOUT = 60000       # 60 seconds

# Additional Database Configuration Constants
DB_MAX_OVERFLOW = 20            # Maximum database connection overflow
DB_POOL_RECYCLE = 3600          # Pool recycle time in seconds (1 hour)
DB_DEFAULT_BATCH_SIZE = 1000    # Default batch size for bulk operations
DB_URL_ENRICHED_BATCH_SIZE = 500  # Batch size for marking URLs as enriched

# Database Field Length Limits
DB_EVENT_NAME_MAX_LENGTH = 500      # Maximum event name length
DB_EVENT_URL_MAX_LENGTH = 1000      # Maximum event URL length
DB_EVENT_DATE_MAX_LENGTH = 100      # Maximum date field length
DB_EVENT_LOCATION_MAX_LENGTH = 200  # Maximum location field length
DB_EVENT_CITY_MAX_LENGTH = 100      # Maximum city field length
DB_EVENT_TICKET_PRICE_MAX_LENGTH = 100  # Maximum ticket price field length
DB_EVENT_SOURCE_MAX_LENGTH = 100    # Maximum source field length

# Database Query Configuration
DB_RECENT_EVENTS_DAYS = 30      # Days to look back for recent events

# Source-specific Configuration
MAX_PAGES_EVENTBRITE = 5        # Maximum pages to scrape from Eventbrite
MAX_PAGES_DEVPOST = 10          # Maximum pages to scrape from Devpost
MAX_PAGES_HACKEREARTH = 3       # Maximum pages to scrape from HackerEarth

# Content Quality Thresholds
MIN_CONTENT_QUALITY_SCORE = 0.5  # Minimum content quality to accept
MIN_DATA_COMPLETENESS = 0.3       # Minimum data completeness required

# Parallel Processing Configuration
MAX_CONCURRENT_EXTRACTIONS = None   # Maximum concurrent GPT extractions
DEFAULT_BATCH_SIZE = 10          # Default batch size for parallel processing
DEFAULT_MAX_WORKERS = 5          # Default maximum workers for thread pools 

# Additional headers to avoid bot detection
DEFAULT_HEADERS = {
    'User-Agent': ENHANCED_USER_AGENT,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"'
}

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///events_dashboard.db')

# File paths
EVENTS_DIR = "data"
CONFERENCES_FILE = f"{EVENTS_DIR}/conferences.json"
HACKATHONS_FILE = f"{EVENTS_DIR}/hackathons.json"

# Event processing
DEDUPE_THRESHOLD = 0.85
QUALITY_THRESHOLD = 0.3

# Geographic filters
TARGET_LOCATIONS = [
    'san francisco', 'sf', 'silicon valley', 'bay area',
    'new york', 'nyc', 'manhattan', 'brooklyn', 'new york city'
]

EXCLUDED_TERMS = [
    'virtual', 'online', 'remote', 'webinar', 'digital',
    'livestream', 'streaming', 'zoom', 'teams', 'worldwide'
]

# API Configuration
FIRECRAWL_MAX_RETRIES = 2
FIRECRAWL_TIMEOUT = 30

# Parallel processing
MAX_WORKERS_DEFAULT = 5
BATCH_SIZE_DEFAULT = 10

# Discovery limits
MAX_CONFERENCES_DEFAULT = 200
MAX_HACKATHONS_DEFAULT = 200

# Site-specific configuration
CONFERENCE_SITES = [
    {
        'name': 'Eventbrite',
        'base_url': 'https://www.eventbrite.com',
        'search_path': '/d/ca--san-francisco/conferences/',
        'selectors': ['.event-card', '.card-container', '[data-event-id]']
    },
    {
        'name': 'Meetup',
        'base_url': 'https://www.meetup.com',
        'search_path': '/find/events/?keywords=conference&location=San+Francisco',
        'selectors': ['.event-item', '[data-event-id]', '.search-result']
    }
]

# Rate limiting
REQUEST_DELAY = 1.0

# Enable Crawl4AI for enhanced scraping capabilities
CRAWL4AI_AVAILABLE = True

# Events Dashboard Runner Configuration
BANNER_WIDTH = 80                       # Width of banners and separators
SECTION_SEPARATOR_WIDTH = 50            # Width of section separators
DEFAULT_EVENT_LIMIT = 5                 # Default limit for events per type
DEFAULT_DISCOVERY_EVENTS = 10           # Default events for discovery testing
TEST_CONCURRENCY_LIMIT = 2              # Concurrency limit for testing
DISCOVERY_CONCURRENCY_LIMIT = 2         # Concurrency limit for discovery
SAMPLE_RESULTS_DISPLAY_COUNT = 3        # Number of sample results to display
MAX_ERRORS_DISPLAY = 3                  # Maximum errors to display in reports
URL_DISPLAY_LENGTH = 50                 # Length for URL display truncation
TITLE_DISPLAY_LENGTH = 40               # Length for title display truncation
DECIMAL_PLACES = 2                      # Decimal places for time formatting
STATS_COLUMN_WIDTH = 12                 # Column width for statistics display
STATS_NUMBER_WIDTH = 3                  # Number width for statistics display

# Crawl4AI Configuration
CRAWL4AI_CONTENT_THRESHOLD = 0.3        # Content filtering threshold
CRAWL4AI_MIN_WORDS = 5                  # Minimum words threshold
CRAWL4AI_DELAY_BEFORE_RETURN = 3.0      # Delay before returning HTML
CRAWL4AI_JS_WAIT_SHORT = 1000           # Short JavaScript wait time (ms)
CRAWL4AI_PAGE_TIMEOUT = 15000           # Page timeout (ms)
CRAWL4AI_MAX_CONCURRENT = 3             # Default max concurrent requests
CRAWL4AI_MAX_EVENTS = 20                # Default max events to discover
CRAWL4AI_BATCH_SLEEP = 2                # Sleep between batches (seconds)
CRAWL4AI_LISTING_TIMEOUT = 5000         # Timeout for listing pages (ms)
CRAWL4AI_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Event Sources Configuration (unified for conferences and hackathons)
EVENT_MAX_RESULTS_CONFERENCE = 200      # Default maximum conference results
EVENT_MAX_RESULTS_HACKATHON = 60        # Default maximum hackathon results
EVENT_TAVILY_MAX_RESULTS = 6            # Results per Tavily query
EVENT_TAVILY_SLEEP = 0.4                # Sleep between Tavily queries (seconds)
EVENT_SITE_SCRAPING_SLEEP = 1           # Sleep between site scraping (seconds)
EVENT_SOURCE_SLEEP = 2                  # Sleep between different sources (seconds)
EVENT_DESCRIPTION_MAX_LENGTH = 300      # Maximum description length
EVENT_NAME_MAX_LENGTH = 100             # Maximum event name length
EVENT_MIN_TEXT_LENGTH = 10              # Minimum text length for filtering
EVENT_MIN_LINK_TEXT_LENGTH = 5          # Minimum link text length
EVENT_AGGREGATOR_EXPANSION_LIMIT = 20   # Maximum results from aggregator expansion
EVENT_QUALITY_BASE_SCORE = 0.5          # Base quality score
EVENT_QUALITY_BONUS_INCREMENT = 0.1     # Quality score increment
EVENT_QUALITY_MAX_SCORE = 1.0           # Maximum quality score
EVENT_API_TIMEOUT = 15                  # API request timeout (seconds)
EVENT_API_PER_PAGE = 20                 # API results per page 