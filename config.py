# Configuration constants to replace magic numbers throughout the project
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
GPT_MODEL_STANDARD = "gpt-3.5-turbo"          # Standard GPT model
GPT_MODEL_ADVANCED = "gpt-4"
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
MAX_CITIES_DISPLAY = 10         # Maximum cities to show in summary
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

# Source-specific Configuration
MAX_PAGES_EVENTBRITE = 5        # Maximum pages to scrape from Eventbrite
MAX_PAGES_DEVPOST = 10          # Maximum pages to scrape from Devpost
MAX_PAGES_HACKEREARTH = 3       # Maximum pages to scrape from HackerEarth

# Content Quality Thresholds
MIN_CONTENT_QUALITY_SCORE = 0.5  # Minimum content quality to accept
MIN_DATA_COMPLETENESS = 0.3       # Minimum data completeness required

# Parallel Processing Configuration
MAX_CONCURRENT_EXTRACTIONS = 5   # Maximum concurrent GPT extractions
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
MAX_HACKATHONS_DEFAULT = 60

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

# Disable Crawl4AI due to dependency conflicts - system works fine without it
CRAWL4AI_AVAILABLE = False 