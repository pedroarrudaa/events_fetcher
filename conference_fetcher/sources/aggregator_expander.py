"""
Aggregator page expander for extracting conference links from blog posts and list pages.
"""
import requests
import re
from bs4 import BeautifulSoup
from typing import List, Set
from urllib.parse import urljoin, urlparse
import time


def is_aggregator_url(url: str) -> bool:
    """
    Detect if a URL is likely an aggregator page (blog post, list page, etc.).
    
    Args:
        url: URL to check
        
    Returns:
        True if URL looks like an aggregator page
    """
    url_lower = url.lower()
    
    # Common aggregator patterns
    aggregator_patterns = [
        '/blog/',
        '/posts/',
        '/news/',
        '/articles/',
        '/events/',
        '/conferences/',
        '/list',
        '/roundup',
        '/digest',
        '/weekly',
        '/monthly',
        '/collection',
        'conferences-',
        'events-',
        'upcoming',
        'calendar'
    ]
    
    # Known aggregator domains
    aggregator_domains = [
        'tryolabs.com',
        'eventbrite.com',
        'meetup.com',
        'conferencelist.info',
        'conferenceindex.org',
        'allconferences.com',
        'papercrowd.com',
        'waset.org'
    ]
    
    # Check patterns in URL path
    for pattern in aggregator_patterns:
        if pattern in url_lower:
            return True
    
    # Check if domain is a known aggregator
    domain = urlparse(url).netloc.lower()
    for aggregator_domain in aggregator_domains:
        if aggregator_domain in domain:
            return True
    
    return False


def looks_like_conference_link(url: str, base_domain: str = None) -> bool:
    """
    Check if a URL looks like it leads to a conference page.
    Enhanced with better filtering and scoring.
    
    Args:
        url: URL to check
        base_domain: Base domain to help with context
        
    Returns:
        True if URL looks like a conference link
    """
    url_lower = url.lower()
    
    # Enhanced conference-related keywords in URL
    conference_keywords = [
        'conference', 'summit', 'symposium', 'workshop', 'seminar',
        'congress', 'convention', 'meeting', 'forum', 'expo',
        'festival', 'event', 'gathering', 'bootcamp', 'hackathon',
        'tech', 'ai', 'ml', 'data', 'dev', 'code', 'software',
        '2024', '2025', 'annual', 'international', 'virtual',
        'speakers', 'keynote', 'agenda', 'registration', 'cfp'
    ]
    
    # Enhanced skip patterns for better filtering
    skip_patterns = [
        'facebook.com', 'twitter.com', 'linkedin.com', 'instagram.com',
        'youtube.com', 'github.com', 'mailto:', 'tel:', '#',
        '.pdf', '.doc', '.ppt', '.jpg', '.png', '.gif', '.zip',
        '/login', '/signup', '/register', '/contact', '/about',
        '/terms', '/privacy', '/cookie', '/legal', '/careers',
        '/blog/', '/news/', '/press/', '/media/', '/resources/',
        '/download', '/demo', '/trial', '/pricing', '/support',
        '/user/', '/profile/', '/account/', '/settings/',
        '/search', '/category/', '/tag/', '/archive/',
        # Enhanced spam/low-quality indicators
        'fake-conferences.com', 'spam-events.org',
        '/affiliate/', '/ref=', '?utm_', '&utm_',
        '/unsubscribe', '/opt-out', '/blacklist',
        'trustpilot.com', '/reviews/', '/testimonials/',
        '/status', 'status.', 'statuspage.',
        # Platform-specific patterns that aren't conferences
        '/community/t5/', '/viewprofilepage/', '/user-id/',
        '/form/', '/subscribe/', '/newsletter/',
        '/use-case/', '/case-study/', '/whitepaper/',
        '/business/', '/enterprise/', '/solutions/',
        '/platform/', '/software/', '/app/', '/tool'
    ]
    
    # Check for exclusion patterns first
    if any(pattern in url_lower for pattern in skip_patterns):
        return False
    
    # Must have http/https
    if not url_lower.startswith(('http://', 'https://')):
        return False
    
    # Check for conference keywords (need at least one)
    keyword_found = any(keyword in url_lower for keyword in conference_keywords)
    
    # Additional scoring for URL structure
    if keyword_found:
        # Bonus points for good URL structure
        url_parts = url_lower.replace('https://', '').replace('http://', '').split('/')
        
        # Prefer URLs with fewer, meaningful path segments
        if len(url_parts) <= 4:  # Domain + up to 3 path segments
            return True
        
        # Check if path contains meaningful conference indicators
        path_text = '/'.join(url_parts[1:])  # Exclude domain
        meaningful_paths = ['events', 'conferences', '2024', '2025', 'register']
        
        if any(path in path_text for path in meaningful_paths):
            return True
    
    return keyword_found


def extract_links_from_content(html_content: str, base_url: str) -> List[str]:
    """
    Extract all links from HTML content that look like conference pages.
    Enhanced with better scoring and fallback mechanisms.
    
    Args:
        html_content: HTML content to parse
        base_url: Base URL for resolving relative links
        
    Returns:
        List of absolute URLs that look like conference pages, sorted by quality
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        links_with_scores = []
        base_domain = urlparse(base_url).netloc
        
        # Find all <a> tags with href attributes
        for link_tag in soup.find_all('a', href=True):
            href = link_tag.get('href', '').strip()
            if not href:
                continue
            
            # Convert relative URLs to absolute
            absolute_url = urljoin(base_url, href)
            
            # Check if it looks like a conference link
            if looks_like_conference_link(absolute_url, base_domain):
                # Score the link based on context
                score = calculate_link_quality_score(link_tag, absolute_url)
                links_with_scores.append((absolute_url, score))
        
        # Also look for URLs in text content with enhanced patterns
        text_content = soup.get_text()
        
        # Enhanced URL patterns for conference detection
        url_patterns = [
            r'https?://[^\s<>"\']+(?:conference|summit|event|expo|symposium)[^\s<>"\']*',
            r'https?://[^\s<>"\']+/(?:events?|conferences?)[^\s<>"\']*',
            r'https?://[^\s<>"\']+(?:2024|2025)[^\s<>"\']*(?:conference|summit|event)[^\s<>"\']*',
            r'https?://[^\s<>"\']+(?:register|registration|cfp|call.for.papers)[^\s<>"\']*'
        ]
        
        for pattern in url_patterns:
            text_urls = re.findall(pattern, text_content, re.IGNORECASE)
            for url in text_urls:
                if looks_like_conference_link(url, base_domain):
                    # Text URLs get lower score since they're not proper links
                    links_with_scores.append((url, 0.3))
        
        # Remove duplicates and sort by score
        unique_links = {}
        for url, score in links_with_scores:
            normalized_url = url.lower().rstrip('/')
            if normalized_url not in unique_links or unique_links[normalized_url] < score:
                unique_links[normalized_url] = score
        
        # Sort by score (highest first) and return URLs
        sorted_links = sorted(unique_links.items(), key=lambda x: x[1], reverse=True)
        return [url for url, score in sorted_links]
        
    except Exception as e:
        print(f"❌ Error parsing HTML content: {str(e)}")
        return []


def calculate_link_quality_score(link_tag, url: str) -> float:
    """
    Calculate quality score for a link based on context and content.
    
    Args:
        link_tag: BeautifulSoup link element
        url: Absolute URL
        
    Returns:
        Quality score between 0.0 and 1.0
    """
    score = 0.5  # Base score
    
    try:
        # Check link text
        link_text = link_tag.get_text().strip().lower()
        
        # High-value link text patterns
        high_value_patterns = [
            'register', 'registration', 'buy tickets', 'learn more',
            'event details', 'conference info', 'agenda', 'speakers',
            'call for papers', 'cfp', 'submit', 'attend'
        ]
        
        for pattern in high_value_patterns:
            if pattern in link_text:
                score += 0.2
                break
        
        # Check if link is in a list or structured content
        parent = link_tag.parent
        if parent and parent.name in ['li', 'td', 'div']:
            score += 0.1
        
        # Check for conference-related classes or IDs
        classes = ' '.join(link_tag.get('class', [])).lower()
        link_id = link_tag.get('id', '').lower()
        
        conference_indicators = ['event', 'conference', 'register', 'ticket']
        if any(indicator in classes or indicator in link_id for indicator in conference_indicators):
            score += 0.15
        
        # URL quality indicators
        url_lower = url.lower()
        if any(indicator in url_lower for indicator in ['register', 'ticket', 'event', 'conference']):
            score += 0.1
        
        # Penalize very long URLs or those with many parameters
        if len(url) > 200 or url.count('?') > 1 or url.count('&') > 3:
            score -= 0.2
        
        return max(0.0, min(1.0, score))  # Clamp between 0 and 1
        
    except Exception:
        return 0.3  # Default score if analysis fails


def expand_aggregator_page(url: str) -> List[str]:
    """
    Download and extract conference links from an aggregator page.
    Enhanced with better error handling and fallback mechanisms.
    
    Args:
        url: URL of the aggregator page to expand
        
    Returns:
        List of unique conference URLs found on the page
    """
    print(f"🔍 Expanding aggregator page: {url}")
    
    conference_links = []
    
    # Try primary method first
    try:
        # Add delay to be respectful
        time.sleep(1)
        
        # Download the page content with better headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Extract links from the content
        conference_links = extract_links_from_content(response.text, url)
        
    except requests.RequestException as e:
        print(f"⚠️ Primary request failed for {url}: {str(e)}")
        
        # Fallback: Try with simpler headers
        try:
            print(f"🔄 Trying fallback request for {url}")
            simple_headers = {'User-Agent': 'Mozilla/5.0 (compatible; conference-bot/1.0)'}
            response = requests.get(url, headers=simple_headers, timeout=15)
            response.raise_for_status()
            conference_links = extract_links_from_content(response.text, url)
            
        except Exception as fallback_error:
            print(f"❌ Fallback request also failed for {url}: {str(fallback_error)}")
            return []
            
    except Exception as e:
        print(f"❌ Error processing aggregator page {url}: {str(e)}")
        return []
    
    # Remove duplicates and the original URL
    unique_links = list(set(conference_links))
    if url in unique_links:
        unique_links.remove(url)
    
    # Additional quality filtering
    filtered_links = []
    for link in unique_links:
        # Calculate quality score for each link
        link_score = get_domain_reputation_score_for_aggregator(link)
        
        if link_score >= 0.3:  # Minimum quality threshold
            filtered_links.append(link)
        else:
            print(f"   ❌ Filtered low-quality link: {link}")
    
    print(f"✅ Found {len(filtered_links)} quality conference links from aggregator")
    
    # Log some examples (first 3)
    for i, link in enumerate(filtered_links[:3]):
        print(f"   🔗 {link}")
    
    if len(filtered_links) > 3:
        print(f"   ... and {len(filtered_links) - 3} more")
    
    return filtered_links


def get_domain_reputation_score_for_aggregator(url: str) -> float:
    """
    Get domain reputation score specifically for aggregator-discovered URLs.
    
    Args:
        url: URL to score
        
    Returns:
        Reputation score between 0.0 and 1.0
    """
    try:
        domain = urlparse(url).netloc.lower()
        
        # High-reputation conference domains
        trusted_domains = {
            'eventbrite.com': 0.9,
            'meetup.com': 0.8,
            'ieee.org': 0.95,
            'acm.org': 0.95,
            'conferencealerts.com': 0.7,
            'allconferences.com': 0.6,
            'conferenceindex.org': 0.7,
        }
        
        # Check exact matches
        if domain in trusted_domains:
            return trusted_domains[domain]
        
        # Check for educational institutions
        if domain.endswith('.edu'):
            return 0.9
        
        # Check for organization domains
        if domain.endswith('.org'):
            return 0.75
        
        # Default scoring based on TLD
        if any(tld in domain for tld in ['.com', '.net', '.io']):
            return 0.5
        
        return 0.3
        
    except Exception:
        return 0.1


def expand_multiple_aggregators(urls: List[str]) -> List[str]:
    """
    Expand multiple aggregator URLs and return all discovered conference links.
    Enhanced with better error handling and result validation.
    
    Args:
        urls: List of aggregator URLs to expand
        
    Returns:
        Combined list of all discovered conference URLs
    """
    all_conference_links = []
    successful_expansions = 0
    failed_expansions = 0
    
    print(f"🔄 Starting expansion of {len(urls)} potential aggregator URLs...")
    
    for i, url in enumerate(urls, 1):
        print(f"📊 [{i}/{len(urls)}] Processing: {url}")
        
        try:
            if is_aggregator_url(url):
                print(f"   🔍 Detected as aggregator, expanding...")
                conference_links = expand_aggregator_page(url)
                
                if conference_links:
                    all_conference_links.extend(conference_links)
                    successful_expansions += 1
                    print(f"   ✅ Expanded successfully: {len(conference_links)} links found")
                else:
                    print(f"   ⚠️ No conference links found in aggregator")
                    # Still include original URL as fallback
                    all_conference_links.append(url)
                    failed_expansions += 1
            else:
                # If not an aggregator, include the original URL
                print(f"   ➡️ Not an aggregator, including original URL")
                all_conference_links.append(url)
                
        except Exception as e:
            print(f"   ❌ Error expanding {url}: {str(e)}")
            # Include original URL as fallback
            all_conference_links.append(url)
            failed_expansions += 1
    
    # Remove duplicates while preserving order
    seen = set()
    unique_links = []
    for link in all_conference_links:
        normalized = link.lower().rstrip('/')
        if normalized not in seen:
            seen.add(normalized)
            unique_links.append(link)
    
    print(f"🎯 Aggregator expansion complete:")
    print(f"   • URLs processed: {len(urls)}")
    print(f"   • Successful expansions: {successful_expansions}")
    print(f"   • Failed expansions: {failed_expansions}")
    print(f"   • Total unique links: {len(unique_links)}")
    
    return unique_links


# Example usage and testing
if __name__ == "__main__":
    # Test the aggregator expansion
    test_urls = [
        "https://tryolabs.com/blog/2024/01/ai-conferences",
        "https://example.com/conferences-2024",
    ]
    
    for test_url in test_urls:
        print(f"\n🧪 Testing: {test_url}")
        print(f"   Is aggregator: {is_aggregator_url(test_url)}")
        
        if is_aggregator_url(test_url):
            links = expand_aggregator_page(test_url)
            print(f"   Found {len(links)} conference links") 