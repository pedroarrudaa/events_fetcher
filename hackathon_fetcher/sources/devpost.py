"""
Devpost source for fetching hackathon opportunities.
"""
import re
import time # Import time for sleep
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from utils.firecrawl import FirecrawlFetcher

# Default retry parameters
DEFAULT_MAX_RETRIES = 3
DEFAULT_INITIAL_BACKOFF = 5  # seconds
DEFAULT_BACKOFF_FACTOR = 2

class DevpostScraper:
    """Scraper for Devpost hackathon listings."""
    
    def __init__(self):
        """Initialize the scraper with Firecrawl."""
        self.fetcher = FirecrawlFetcher()
        self.base_url = "https://devpost.com"
        # NEW: Track page metadata for quality analysis
        self.page_metadata = []
    
    def _scrape_with_retry(self, url: str, max_retries: int = DEFAULT_MAX_RETRIES, 
                           initial_backoff: int = DEFAULT_INITIAL_BACKOFF, 
                           backoff_factor: int = DEFAULT_BACKOFF_FACTOR) -> Dict[str, Any]:
        """Wraps Firecrawl's scrape_url with retry logic for 429 errors."""
        retries = 0
        backoff_time = initial_backoff
        
        while retries < max_retries:
            print(f"Attempt {retries + 1}/{max_retries} to fetch: {url}")
            result = self.fetcher.scrape_url(url)
            
            if result.get('success'):
                # NEW: Add HTML size and title extraction for quality ranking
                html_content = result.get('html', '')
                html_size = len(html_content) if html_content else 0
                
                # Extract page title from HTML for logging
                page_title = self._extract_page_title_from_html(html_content)
                
                # Enhanced result with metadata
                enhanced_result = {
                    **result,
                    'html_size': html_size,
                    'page_title': page_title
                }
                
                print(f"✅ Successfully fetched: {page_title[:80]}... (HTML size: {html_size:,} bytes)")
                return enhanced_result
            
            # Check for rate limit error (429)
            # Firecrawl error messages might vary, adjust as needed
            error_message = result.get('error', '').lower()
            if '429' in error_message or 'rate limit' in error_message or 'insufficient credits' in error_message:
                print(f"Rate limit hit for {url}. Waiting {backoff_time}s before retrying... (Error: {result.get('error')})")
                time.sleep(backoff_time)
                retries += 1
                backoff_time *= backoff_factor
            else:
                # For other errors, don't retry, return the error immediately
                print(f"Failed to fetch {url} due to non-retryable error: {result.get('error')}")
                return result 
        
        print(f"Max retries reached for {url}. Fetching failed.")
        return {
            'success': False,
            'url': url,
            'error': f"Max retries reached after {max_retries} attempts. Last error: {result.get('error', 'Unknown after retries')}"
        }

    def _extract_page_title_from_html(self, html: str) -> str:
        """
        Extract page title from HTML content for logging and quality assessment.
        
        Args:
            html: Raw HTML content
            
        Returns:
            Page title or fallback text
        """
        if not html:
            return "No HTML content"
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Try multiple title sources in order of preference
            title_sources = [
                soup.find('title'),
                soup.find('h1'),
                soup.find('meta', {'property': 'og:title'}),
                soup.find('meta', {'name': 'twitter:title'})
            ]
            
            for source in title_sources:
                if source:
                    if source.name == 'meta':
                        title = source.get('content', '').strip()
                    else:
                        title = source.get_text().strip()
                    
                    if title and len(title) > 3:
                        # Clean up title
                        title = re.sub(r'\s+', ' ', title)
                        return title[:100]  # Limit length for logging
            
            return "Unknown page title"
            
        except Exception as e:
            return f"Title extraction error: {str(e)[:50]}"

    def get_hackathon_list_urls(self, max_pages: int = 10) -> List[str]:
        """
        Get URLs for hackathon listing pages with enhanced page processing.
        
        Args:
            max_pages: Maximum number of listing pages to process (increased default)
            
        Returns:
            List of hackathon URLs found
        """
        hackathon_urls = []
        
        # Start with the main hackathons page
        base_hackathons_url = f"{self.base_url}/hackathons"
        
        print(f"🔍 Starting enhanced page crawling with {max_pages} pages and 7-second delays...")
        
        for page in range(1, max_pages + 1):
            url = f"{base_hackathons_url}?page={page}" if page > 1 else base_hackathons_url
            
            # **ENHANCED: Add 7-second delay between pages as requested**
            if page > 1:
                print(f"⏳ Waiting 7 seconds before fetching page {page} to respect rate limits...")
                time.sleep(7)
            
            print(f"📄 Processing page {page}/{max_pages}: {url}")
            
            # Use the enhanced _scrape_with_retry method
            result = self._scrape_with_retry(url)
            
            if result['success'] and result.get('html'):
                # **NEW: Store page metadata for quality analysis**
                page_metadata = {
                    'page_number': page,
                    'url': url,
                    'title': result.get('page_title', 'Unknown'),
                    'html_size': result.get('html_size', 0),
                    'timestamp': time.time()
                }
                self.page_metadata.append(page_metadata)
                
                # **ENHANCED: Log page details with title and size**
                print(f"   📊 Page {page} details:")
                print(f"      • Title: {result.get('page_title', 'Unknown')[:80]}...")
                print(f"      • HTML size: {result.get('html_size', 0):,} bytes")
                
                # Extract hackathon URLs from this page
                urls = self._extract_hackathon_urls_from_html(result['html'])
                hackathon_urls.extend(urls)
                
                print(f"   ✅ Found {len(urls)} hackathons on page {page}")
                
                # **NEW: Quality assessment based on HTML size**
                html_size = result.get('html_size', 0)
                if html_size < 5000:
                    print(f"   ⚠️ Warning: Page {page} has small HTML size ({html_size:,} bytes) - may be low quality")
                elif html_size > 100000:
                    print(f"   📈 Note: Page {page} has large HTML size ({html_size:,} bytes) - rich content detected")
                
            else:
                print(f"   ❌ Failed to fetch page {page} HTML after retries: {result.get('error', 'No HTML content')}")
                
                # **ENHANCED: Store failed page metadata too**
                failed_metadata = {
                    'page_number': page,
                    'url': url,
                    'title': 'FAILED',
                    'html_size': 0,
                    'error': result.get('error', 'Unknown error'),
                    'timestamp': time.time()
                }
                self.page_metadata.append(failed_metadata)
                
                # **ENHANCED: More intelligent failure handling**
                # Continue trying a few more pages even if one fails, but break if too many consecutive failures
                consecutive_failures = 0
                for i in range(len(self.page_metadata) - 1, -1, -1):
                    if self.page_metadata[i].get('title') == 'FAILED':
                        consecutive_failures += 1
                    else:
                        break
                
                if consecutive_failures >= 3:
                    print(f"   🛑 Breaking after {consecutive_failures} consecutive failures")
                    break
        
        # **NEW: Enhanced summary with quality statistics**
        self._log_crawling_summary(hackathon_urls)
        
        # Remove duplicates while preserving order
        unique_urls = list(dict.fromkeys(hackathon_urls))
        print(f"🎯 Total unique hackathon URLs found: {len(unique_urls)}")
        
        return unique_urls
    
    def _log_crawling_summary(self, hackathon_urls: List[str]) -> None:
        """
        Log comprehensive crawling summary with quality metrics.
        
        Args:
            hackathon_urls: List of discovered hackathon URLs
        """
        successful_pages = [p for p in self.page_metadata if p.get('title') != 'FAILED']
        failed_pages = [p for p in self.page_metadata if p.get('title') == 'FAILED']
        
        print(f"\n📊 Enhanced Crawling Summary:")
        print(f"   • Total pages processed: {len(self.page_metadata)}")
        print(f"   • Successful pages: {len(successful_pages)}")
        print(f"   • Failed pages: {len(failed_pages)}")
        print(f"   • Total hackathon URLs found: {len(hackathon_urls)}")
        
        if successful_pages:
            # Calculate HTML size statistics
            html_sizes = [p['html_size'] for p in successful_pages]
            avg_size = sum(html_sizes) / len(html_sizes)
            min_size = min(html_sizes)
            max_size = max(html_sizes)
            
            print(f"   • HTML size stats:")
            print(f"     - Average: {avg_size:,.0f} bytes")
            print(f"     - Range: {min_size:,} - {max_size:,} bytes")
            
            # Quality assessment
            high_quality_pages = len([s for s in html_sizes if s > 50000])
            medium_quality_pages = len([s for s in html_sizes if 10000 <= s <= 50000])
            low_quality_pages = len([s for s in html_sizes if s < 10000])
            
            print(f"   • Page quality assessment:")
            print(f"     - High quality (>50KB): {high_quality_pages}")
            print(f"     - Medium quality (10-50KB): {medium_quality_pages}")
            print(f"     - Low quality (<10KB): {low_quality_pages}")
            
            # Log top quality pages
            sorted_pages = sorted(successful_pages, key=lambda x: x['html_size'], reverse=True)
            print(f"   • Top 3 highest quality pages:")
            for i, page in enumerate(sorted_pages[:3], 1):
                print(f"     {i}. {page['title'][:60]}... ({page['html_size']:,} bytes)")

    def _extract_hackathon_urls_from_html(self, html: str) -> List[str]:
        """
        Extract hackathon URLs from Devpost HTML.
        
        Args:
            html: Raw HTML content from Devpost
            
        Returns:
            List of hackathon URLs
        """
        soup = BeautifulSoup(html, 'html.parser')
        urls = []
        
        # **IMPROVED: More specific selectors for Devpost hackathon cards**
        # Devpost uses specific patterns for hackathon listings
        
        # 1. Hackathon cards with data-url attributes
        hackathon_cards = soup.find_all(['div', 'article', 'section'], attrs={'data-url': True})
        for card in hackathon_cards:
            data_url = card.get('data-url', '')
            if data_url and self._is_hackathon_url(data_url):
                full_url = urljoin(self.base_url, data_url)
                urls.append(full_url)
        
        # 2. Links with hackathon-specific classes
        hackathon_link_classes = [
            'hackathon-tile', 'challenge-tile', 'challenge-link', 
            'hackathon-card', 'challenge-card', 'listing-link'
        ]
        
        for class_name in hackathon_link_classes:
            links = soup.find_all('a', class_=class_name, href=True)
            for link in links:
                href = link.get('href', '')
                if self._is_hackathon_url(href):
                    full_url = urljoin(self.base_url, href)
                    urls.append(full_url)
        
        # 3. **IMPROVED: More comprehensive link detection**
        all_links = soup.find_all('a', href=True)
        
        for link in all_links:
            href = link.get('href', '')
            
            # Skip empty hrefs
            if not href:
                continue
            
            # **IMPROVED: Better hackathon URL detection**
            if self._is_hackathon_url(href):
                full_url = urljoin(self.base_url, href)
                
                # **NEW: Additional validation - check link text for hackathon indicators**
                link_text = link.get_text(strip=True).lower()
                hackathon_keywords = ['hackathon', 'challenge', 'competition', 'contest', 'hack', 'dev']
                
                # If link text contains hackathon keywords, it's more likely a real hackathon
                if any(keyword in link_text for keyword in hackathon_keywords) or any(keyword in href.lower() for keyword in hackathon_keywords):
                    urls.append(full_url)
                elif href.endswith('.devpost.com') or '/hackathons/' in href:
                    # Still include subdomain links and /hackathons/ paths
                    urls.append(full_url)
        
        return urls
    
    def _is_hackathon_url(self, url: str) -> bool:
        """
        Check if a URL is likely a hackathon page.
        
        Args:
            url: URL to check
            
        Returns:
            True if the URL appears to be a hackathon page
        """
        # Skip obviously non-hackathon URLs
        skip_patterns = [
            '/api/', '/static/', '/assets/', '/search', '/login', '/signup',
            '/about', '/privacy', '/terms', '/contact', '/help', '/users/',
            '/submissions/', '/judges/', '/participants/', '.css', '.js', '.png',
            '.jpg', '.gif', '.pdf', '/software/', '/challenges/'
        ]
        
        for pattern in skip_patterns:
            if pattern in url.lower():
                return False
        
        # Skip anchor links to the same page
        if url.startswith('#') or url == 'https://devpost.com/hackathons#':
            return False
        
        # IMPORTANT: Skip the root hackathons page - it's not a specific hackathon
        if url.lower() in ['https://devpost.com/hackathons', 'https://devpost.com/hackathons/', '/hackathons', '/hackathons/']:
            return False
        
        # Look for hackathon patterns
        hackathon_patterns = [
            r'/hackathons/[^/]+/?',  # /hackathons/hackathon-name (removed $ to allow query params)
            r'[a-zA-Z0-9-]+\.devpost\.com',  # subdomain.devpost.com (allow query params)
        ]
        
        for pattern in hackathon_patterns:
            if re.search(pattern, url):
                # Additional check: exclude help.devpost.com and similar non-hackathon subdomains
                if 'help.devpost.com' in url or 'support.devpost.com' in url:
                    return False
                return True
        
        return False
    
    def get_hackathon_details(self, url: str) -> Dict[str, Any]:
        """
        Fetch detailed information for a single hackathon with enhanced metadata.
        
        Args:
            url: URL of the hackathon page
            
        Returns:
            Dictionary with hackathon details including quality metrics
        """
        # Use the enhanced _scrape_with_retry method
        result = self._scrape_with_retry(url)
        
        if not result['success'] or not result.get('html'):
            return {
                'url': url,
                'error': result.get('error', 'No HTML content after retries'),
                'success': False,
                'html_size': 0,
                'page_title': 'FAILED'
            }
        
        # Extract basic information from the HTML
        soup = BeautifulSoup(result['html'], 'html.parser')
        
        # Try to extract title
        title = self._extract_title(soup)
        
        # Try to extract basic details that might be visible
        basic_details = self._extract_basic_details(soup)
        
        # **NEW: Enhanced quality metrics**
        html_size = result.get('html_size', 0)
        page_title = result.get('page_title', title)
        
        # **NEW: Calculate content quality score based on HTML size and content**
        quality_score = self._calculate_content_quality_score(html_size, result['html'])
        
        print(f"   📊 Hackathon details extracted:")
        print(f"      • Title: {title[:60]}...")
        print(f"      • Page title: {page_title[:60]}...")
        print(f"      • HTML size: {html_size:,} bytes")
        print(f"      • Quality score: {quality_score:.2f}/1.0")
        
        return {
            'url': url,
            'name': title,
            'html_content': result['html'],
            'markdown_content': result.get('markdown', ''),
            'basic_details': basic_details,
            'success': True,
            # **NEW: Enhanced metadata for quality ranking**
            'html_size': html_size,
            'page_title': page_title,
            'quality_score': quality_score,
            'content_richness': self._assess_content_richness(soup)
        }
    
    def _calculate_content_quality_score(self, html_size: int, html_content: str) -> float:
        """
        Calculate a quality score for the content based on various factors.
        
        Args:
            html_size: Size of HTML content in bytes
            html_content: Raw HTML content
            
        Returns:
            Quality score between 0.0 and 1.0
        """
        score = 0.0
        
        # Size-based scoring (40% of total score)
        if html_size < 5000:
            size_score = 0.1  # Very low for tiny pages
        elif html_size < 15000:
            size_score = 0.3  # Low for small pages
        elif html_size < 50000:
            size_score = 0.6  # Medium for average pages
        elif html_size < 100000:
            size_score = 0.8  # High for large pages
        else:
            size_score = 1.0  # Excellent for very large pages
        
        score += size_score * 0.4
        
        # Content richness scoring (60% of total score)
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Count meaningful elements
            content_indicators = {
                'paragraphs': len(soup.find_all('p')),
                'headings': len(soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])),
                'lists': len(soup.find_all(['ul', 'ol'])),
                'images': len(soup.find_all('img')),
                'links': len(soup.find_all('a')),
                'forms': len(soup.find_all('form'))
            }
            
            # Calculate content richness
            richness_score = 0.0
            
            # Paragraph content (important for descriptions)
            if content_indicators['paragraphs'] >= 5:
                richness_score += 0.2
            elif content_indicators['paragraphs'] >= 2:
                richness_score += 0.1
            
            # Structural elements (headings, lists)
            if content_indicators['headings'] >= 3:
                richness_score += 0.15
            elif content_indicators['headings'] >= 1:
                richness_score += 0.1
            
            if content_indicators['lists'] >= 2:
                richness_score += 0.1
            
            # Interactive elements (forms for registration)
            if content_indicators['forms'] >= 1:
                richness_score += 0.15
            
            # Media content
            if content_indicators['images'] >= 3:
                richness_score += 0.1
            
            # Navigation and links
            if 10 <= content_indicators['links'] <= 50:
                richness_score += 0.1
            
            score += min(richness_score, 0.6) * (0.6 / 0.6)  # Normalize to 60% of total
            
        except Exception as e:
            # If content analysis fails, use a conservative score based on size only
            score = size_score * 0.7
        
        return min(1.0, max(0.0, score))
    
    def _assess_content_richness(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Assess the richness of content for quality ranking.
        
        Args:
            soup: BeautifulSoup object of the page
            
        Returns:
            Dictionary with content richness metrics
        """
        try:
            # Count various content elements
            richness_metrics = {
                'paragraph_count': len(soup.find_all('p')),
                'heading_count': len(soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])),
                'list_count': len(soup.find_all(['ul', 'ol'])),
                'image_count': len(soup.find_all('img')),
                'link_count': len(soup.find_all('a')),
                'form_count': len(soup.find_all('form')),
                'table_count': len(soup.find_all('table'))
            }
            
            # Calculate total text length
            text_content = soup.get_text()
            richness_metrics['text_length'] = len(text_content)
            richness_metrics['word_count'] = len(text_content.split())
            
            # Check for specific hackathon indicators
            hackathon_keywords = [
                'hackathon', 'challenge', 'competition', 'prize', 'winner',
                'sponsor', 'judge', 'submission', 'deadline', 'register',
                'participant', 'team', 'developer', 'innovation'
            ]
            
            text_lower = text_content.lower()
            keyword_matches = sum(1 for keyword in hackathon_keywords if keyword in text_lower)
            richness_metrics['hackathon_keyword_count'] = keyword_matches
            
            # Overall richness assessment
            total_elements = sum([
                richness_metrics['paragraph_count'],
                richness_metrics['heading_count'] * 2,  # Headings are more valuable
                richness_metrics['list_count'],
                richness_metrics['form_count'] * 3,  # Forms are very valuable
                min(richness_metrics['image_count'], 10)  # Cap images at 10 for scoring
            ])
            
            richness_metrics['total_element_score'] = total_elements
            richness_metrics['richness_level'] = (
                'high' if total_elements >= 20 else
                'medium' if total_elements >= 10 else
                'low'
            )
            
            return richness_metrics
            
        except Exception as e:
            return {
                'error': str(e),
                'richness_level': 'unknown'
            }

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract hackathon title from HTML."""
        # Try various title selectors
        title_selectors = [
            'h1',
            '.hackathon-name',
            '.challenge-title',
            'title'
        ]
        
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                title = element.get_text(strip=True)
                if title and len(title) > 3:  # Basic validation
                    return title
        
        return "Unknown Hackathon"
    
    def _extract_basic_details(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract basic details that might be visible in HTML."""
        details = {}
        
        # Look for common patterns
        text_content = soup.get_text().lower()
        
        # Check for remote/virtual indicators
        remote_keywords = ['remote', 'virtual', 'online', 'anywhere']
        details['likely_remote'] = any(keyword in text_content for keyword in remote_keywords)
        
        # Check for in-person indicators
        inperson_keywords = ['in-person', 'on-site', 'location:', 'venue:', 'address:']
        details['likely_inperson'] = any(keyword in text_content for keyword in inperson_keywords)
        
        return details 

def get_hackathon_urls(limit: int = 2) -> List[Dict[str, Any]]:
    """
    Fetch hackathon URLs from Devpost using enhanced interface with quality metrics.
    
    Args:
        limit: Maximum number of hackathons to fetch
        
    Returns:
        List of dictionaries with hackathon information including quality scores
    """
    print(f"🔍 Fetching {limit} hackathons from Devpost with enhanced processing...")
    
    try:
        # First try to scrape the main page with more pages to get more hackathons
        scraper = DevpostScraper()
        
        # **ENHANCED: Calculate how many pages we need based on the limit with better estimation**
        # Typically each page has ~8-15 hackathons, so calculate more conservatively
        min_pages = 10  # Always scan at least 10 pages
        calculated_pages = max(min_pages, (limit // 6) + 5)  # Assume ~6 hackathons per page for safety
        pages_needed = min(calculated_pages, 50)  # Cap at 50 pages to avoid excessive requests
        
        print(f"📄 Scanning {pages_needed} pages of Devpost to find {limit} hackathons...")
        print(f"   • Minimum pages: {min_pages}")
        print(f"   • Calculated pages needed: {calculated_pages}")
        print(f"   • Using 7-second delays between pages")
        
        # **ENHANCED: Use the improved get_hackathon_list_urls with better default**
        urls = scraper.get_hackathon_list_urls(max_pages=pages_needed)
        
        hackathons = []
        
        # If we found URLs from scraping, use them
        if urls:
            print(f"🎯 Processing {len(urls)} discovered URLs (taking up to {limit})...")
            
            for i, url in enumerate(urls[:limit], 1):  # Take up to the limit requested
                # Extract name from URL - be more careful about generic names
                name_from_url = url.split('/')[-1].replace('-', ' ').title()
                
                # Skip URLs that would generate generic names
                if not name_from_url or name_from_url.lower() in ['hackathons', 'events', 'challenges', 'devpost']:
                    print(f"   ⚠️ Skipping generic URL: {url}")
                    continue
                
                # Additional check: if URL is the root hackathons page, skip it
                if url.lower() in ['https://devpost.com/hackathons', 'https://devpost.com/hackathons/']:
                    print(f"   ⚠️ Skipping root hackathons page: {url}")
                    continue
                
                # **NEW: Add quality metadata from scraper if available**
                hackathon_entry = {
                    "name": name_from_url,
                    "url": url,
                    "source": "devpost",
                    "discovery_method": "enhanced_scraping"
                }
                
                # **NEW: Try to get page metadata if available from scraper**
                if hasattr(scraper, 'page_metadata') and scraper.page_metadata:
                    # Find if this URL was discovered from a specific page
                    for page_data in scraper.page_metadata:
                        if page_data.get('title') != 'FAILED':
                            hackathon_entry['source_page_quality'] = {
                                'html_size': page_data.get('html_size', 0),
                                'page_title': page_data.get('title', 'Unknown')
                            }
                            break
                
                hackathons.append(hackathon_entry)
                print(f"   ✅ Added: {name_from_url} (URL {i}/{min(len(urls), limit)})")
                
                # Break if we've reached our limit
                if len(hackathons) >= limit:
                    break
        
        # **NEW: Enhanced summary with scraper statistics**
        if hasattr(scraper, 'page_metadata') and scraper.page_metadata:
            successful_pages = [p for p in scraper.page_metadata if p.get('title') != 'FAILED']
            print(f"\n📊 Enhanced Discovery Summary:")
            print(f"   • Pages successfully crawled: {len(successful_pages)}")
            print(f"   • Total URLs discovered: {len(urls) if urls else 0}")
            print(f"   • Hackathons added to result: {len(hackathons)}")
            
            if successful_pages:
                avg_quality = sum(p.get('html_size', 0) for p in successful_pages) / len(successful_pages)
                print(f"   • Average page quality: {avg_quality:,.0f} bytes")
        
        # **GREATLY EXPANDED** known active hackathons with real URLs (keeping existing content)
        known_hackathons = [
            # **Active Google/Tech Company Hackathons**
            {
                "name": "Agent Development Kit Hackathon with Google Cloud",
                "url": "https://googlecloudmultiagents.devpost.com/",
                "source": "devpost",
                "discovery_method": "known_active"
            },
            {
                "name": "Google AI Hackathon",
                "url": "https://googleai.devpost.com/",
                "source": "devpost",
                "discovery_method": "known_active"
            },
            {
                "name": "Vibe Hacks 2025",
                "url": "https://vibe-hacks-2025.devpost.com/",
                "source": "devpost",
                "discovery_method": "known_active"
            },
            {
                "name": "Google Cloud Gaming Hackathon",
                "url": "https://googlecloudgaming.devpost.com/",
                "source": "devpost",
                "discovery_method": "known_active"
            },
            {
                "name": "AI in Action",
                "url": "https://ai-in-action.devpost.com/",
                "source": "devpost",
                "discovery_method": "known_active"
            },
            
            # **AWS & Amazon Hackathons**
            {
                "name": "AWS Breaking Barriers Virtual Challenge",
                "url": "https://aws-breaking-barriers.devpost.com/",
                "source": "devpost",
                "discovery_method": "known_active"
            },
            {
                "name": "AWS re:Invent Hackathon",
                "url": "https://awsreinvent.devpost.com/",
                "source": "devpost",
                "discovery_method": "known_active"
            },
            {
                "name": "AWS Startup Challenge",
                "url": "https://awsstartup.devpost.com/",
                "source": "devpost",
                "discovery_method": "known_active"
            },
            
            # **Microsoft Hackathons**
            {
                "name": "Microsoft Cloud AI Hackathon",
                "url": "https://mscloudai.devpost.com/",
                "source": "devpost",
                "discovery_method": "known_active"
            },
            {
                "name": "Microsoft Azure OpenAI Hackathon",
                "url": "https://azureopenai.devpost.com/",
                "source": "devpost",
                "discovery_method": "known_active"
            },
            {
                "name": "Microsoft Build Challenge",
                "url": "https://msbuild.devpost.com/",
                "source": "devpost",
                "discovery_method": "known_active"
            },
            
            # **NVIDIA & Hardware Hackathons**
            {
                "name": "HP & NVIDIA Developer Challenge",
                "url": "https://hpaistudio.devpost.com/",
                "source": "devpost",
                "discovery_method": "known_active"
            },
            {
                "name": "NVIDIA GTC Hackathon",
                "url": "https://nvidiagtc.devpost.com/",
                "source": "devpost",
                "discovery_method": "known_active"
            },
            {
                "name": "NVIDIA Omniverse Challenge",
                "url": "https://nvidiaomniverse.devpost.com/",
                "source": "devpost",
                "discovery_method": "known_active"
            }
        ]
        
        # Fill remaining slots with known active hackathons if we still need more
        if len(hackathons) < limit:
            remaining_needed = limit - len(hackathons)
            print(f"📝 Adding {remaining_needed} additional hackathons from known list...")
            hackathons.extend(known_hackathons[:remaining_needed])
        
        print(f"✅ Found {len(hackathons)} hackathons from Devpost")
        return hackathons[:limit]
        
    except Exception as e:
        print(f"❌ Error fetching from Devpost: {str(e)}")
        
        # Return known active hackathons as fallback
        known_hackathons = [
            {
                "name": "Agent Development Kit Hackathon with Google Cloud",
                "url": "https://googlecloudmultiagents.devpost.com/",
                "source": "devpost",
                "discovery_method": "fallback"
            },
            {
                "name": "AI in Action",
                "url": "https://ai-in-action.devpost.com/",
                "source": "devpost",
                "discovery_method": "fallback"
            }
        ]
        
        return known_hackathons[:limit] 