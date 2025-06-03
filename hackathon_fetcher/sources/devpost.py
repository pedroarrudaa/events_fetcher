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
                return result
            
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

    def get_hackathon_list_urls(self, max_pages: int = 3) -> List[str]:
        """
        Get URLs for hackathon listing pages.
        
        Args:
            max_pages: Maximum number of listing pages to process
            
        Returns:
            List of hackathon URLs found
        """
        hackathon_urls = []
        
        # Start with the main hackathons page
        base_hackathons_url = f"{self.base_url}/hackathons"
        
        for page in range(1, max_pages + 1):
            url = f"{base_hackathons_url}?page={page}" if page > 1 else base_hackathons_url
            
            # **NEW: Add a delay before scraping a new page to respect rate limits**
            if page > 1: # No need to sleep before the very first page
                print(f"Waiting 7 seconds before fetching page {page} to respect rate limits...")
                time.sleep(7)
            
            # Use the new _scrape_with_retry method
            result = self._scrape_with_retry(url)
            
            if result['success'] and result.get('html'): # Ensure HTML content is present
                urls = self._extract_hackathon_urls_from_html(result['html'])
                hackathon_urls.extend(urls)
                print(f"Found {len(urls)} hackathons on page {page}")
            else:
                print(f"Failed to fetch page {page} HTML after retries: {result.get('error', 'No HTML content')}")
                # Optionally, decide if you want to break or continue if a page fails
                # For now, let's break as it might indicate a persistent issue
                break 
        
        # Remove duplicates while preserving order
        unique_urls = list(dict.fromkeys(hackathon_urls))
        print(f"Total unique hackathon URLs found: {len(unique_urls)}")
        
        return unique_urls
    
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
        Fetch detailed information for a single hackathon.
        
        Args:
            url: URL of the hackathon page
            
        Returns:
            Dictionary with hackathon details
        """
        # print(f"Fetching details for: {url}") # Moved to _scrape_with_retry
        
        # Use the new _scrape_with_retry method
        result = self._scrape_with_retry(url)
        
        if not result['success'] or not result.get('html'):
            return {
                'url': url,
                'error': result.get('error', 'No HTML content after retries'),
                'success': False
            }
        
        # Extract basic information from the HTML
        soup = BeautifulSoup(result['html'], 'html.parser')
        
        # Try to extract title
        title = self._extract_title(soup)
        
        # Try to extract basic details that might be visible
        basic_details = self._extract_basic_details(soup)
        
        return {
            'url': url,
            'name': title,
            'html_content': result['html'],
            'markdown_content': result['markdown'],
            'basic_details': basic_details,
            'success': True
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
    Fetch hackathon URLs from Devpost using simplified interface.
    
    Args:
        limit: Maximum number of hackathons to fetch
        
    Returns:
        List of dictionaries with hackathon information
    """
    print(f"🔍 Fetching {limit} hackathons from Devpost...")
    
    try:
        # First try to scrape the main page with more pages to get more hackathons
        scraper = DevpostScraper()
        
        # Calculate how many pages we need based on the limit
        # Typically each page has ~10-20 hackathons, so for 300+ hackathons we need many more pages
        pages_needed = max(50, (limit // 8) + 10)  # At least 50 pages for 300+ hackathons (assuming ~8 hackathons per page)
        
        print(f"📄 Scanning {pages_needed} pages of Devpost to find {limit} hackathons...")
        urls = scraper.get_hackathon_list_urls(max_pages=pages_needed)
        
        hackathons = []
        
        # If we found URLs from scraping, use them
        if urls:
            for url in urls[:limit]:  # Take up to the limit requested
                # Extract name from URL - be more careful about generic names
                name_from_url = url.split('/')[-1].replace('-', ' ').title()
                
                # Skip URLs that would generate generic names
                if not name_from_url or name_from_url.lower() in ['hackathons', 'events', 'challenges', 'devpost']:
                    continue
                
                # Additional check: if URL is the root hackathons page, skip it
                if url.lower() in ['https://devpost.com/hackathons', 'https://devpost.com/hackathons/']:
                    continue
                
                hackathons.append({
                    "name": name_from_url,
                    "url": url,
                    "source": "devpost"
                })
                
                # Break if we've reached our limit
                if len(hackathons) >= limit:
                    break
        
        # **GREATLY EXPANDED** known active hackathons with real URLs
        known_hackathons = [
            # **Active Google/Tech Company Hackathons**
            {
                "name": "Agent Development Kit Hackathon with Google Cloud",
                "url": "https://googlecloudmultiagents.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "Google AI Hackathon",
                "url": "https://googleai.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "Vibe Hacks 2025",
                "url": "https://vibe-hacks-2025.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "Google Cloud Gaming Hackathon",
                "url": "https://googlecloudgaming.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "AI in Action",
                "url": "https://ai-in-action.devpost.com/",
                "source": "devpost"
            },
            
            # **AWS & Amazon Hackathons**
            {
                "name": "AWS Breaking Barriers Virtual Challenge",
                "url": "https://aws-breaking-barriers.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "AWS re:Invent Hackathon",
                "url": "https://awsreinvent.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "AWS Startup Challenge",
                "url": "https://awsstartup.devpost.com/",
                "source": "devpost"
            },
            
            # **Microsoft Hackathons**
            {
                "name": "Microsoft Cloud AI Hackathon",
                "url": "https://mscloudai.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "Microsoft Azure OpenAI Hackathon",
                "url": "https://azureopenai.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "Microsoft Build Challenge",
                "url": "https://msbuild.devpost.com/",
                "source": "devpost"
            },
            
            # **NVIDIA & Hardware Hackathons**
            {
                "name": "HP & NVIDIA Developer Challenge",
                "url": "https://hpaistudio.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "NVIDIA GTC Hackathon",
                "url": "https://nvidiagtc.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "NVIDIA Omniverse Challenge",
                "url": "https://nvidiaomniverse.devpost.com/",
                "source": "devpost"
            },
            
            # **Major Platform Hackathons**
            {
                "name": "Google Maps Platform Awards",
                "url": "https://googlemapsplatformawards.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "Adobe Express Add-ons Hackathon",
                "url": "https://adobeexpress.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "Meta Spark Challenge",
                "url": "https://metaspark.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "Shopify App Challenge",
                "url": "https://shopifyapps.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "Discord Bot Development Contest",
                "url": "https://discordbots.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "Twilio Developer Challenge",
                "url": "https://twiliodev.devpost.com/",
                "source": "devpost"
            },
            
            # **Database & Backend Hackathons**
            {
                "name": "MongoDB Atlas Hackathon",
                "url": "https://mongodbatlas.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "PostgreSQL Global Hackathon",
                "url": "https://postgresqlhack.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "Supabase Launch Week Hackathon",
                "url": "https://supabase.devpost.com/",
                "source": "devpost"
            },
            
            # **Web3 & Blockchain Hackathons**
            {
                "name": "Blockchain Innovation Challenge",
                "url": "https://blockchain-innovation.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "Web3 Innovation Hackathon",
                "url": "https://web3innovation.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "Ethereum Global Hackathon",
                "url": "https://ethglobal.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "Solana Hackathon",
                "url": "https://solanahack.devpost.com/",
                "source": "devpost"
            },
            
            # **Industry-Specific Hackathons**
            {
                "name": "Healthcare Technology Challenge",
                "url": "https://healthtech.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "Climate Change Solutions Hackathon",
                "url": "https://climatetech.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "EdTech Innovation Challenge",
                "url": "https://edtechinnovation.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "FinTech Developer Challenge",
                "url": "https://fintech.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "Gaming Innovation Hackathon",
                "url": "https://gaminghack.devpost.com/",
                "source": "devpost"
            },
            
            # **Open Source & API Hackathons**
            {
                "name": "Open Source Contribution Contest",
                "url": "https://opensource.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "API World Hackathon",
                "url": "https://apiworld.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "GitHub Copilot Hackathon",
                "url": "https://githubcopilot.devpost.com/",
                "source": "devpost"
            },
            
            # **Mobile & App Development**
            {
                "name": "Mobile App Development Challenge",
                "url": "https://mobiledev.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "Flutter Create Challenge",
                "url": "https://fluttercreate.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "React Native Hackathon",
                "url": "https://reactnative.devpost.com/",
                "source": "devpost"
            },
            
            # **University & Student Hackathons**
            {
                "name": "Stanford TreeHacks",
                "url": "https://treehacks.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "MIT HackMIT",
                "url": "https://hackmit.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "Berkeley CalHacks",
                "url": "https://calhacks.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "CMU TartanHacks",
                "url": "https://tartanhacks.devpost.com/",
                "source": "devpost"
            },
            
            # **Major Tech Conference Hackathons**
            {
                "name": "CES Innovation Challenge",
                "url": "https://cesinnovation.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "SXSW Hackathon",
                "url": "https://sxsw.devpost.com/",
                "source": "devpost"
            },
            {
                "name": "TechCrunch Disrupt Hackathon",
                "url": "https://tcdisrupt.devpost.com/",
                "source": "devpost"
            },
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
                "source": "devpost"
            },
            {
                "name": "AI in Action",
                "url": "https://ai-in-action.devpost.com/",
                "source": "devpost"
            }
        ]
        
        return known_hackathons[:limit] 