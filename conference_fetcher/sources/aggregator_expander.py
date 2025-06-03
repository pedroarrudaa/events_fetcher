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
    
    Args:
        url: URL to check
        base_domain: Base domain to help with context
        
    Returns:
        True if URL looks like a conference link
    """
    url_lower = url.lower()
    
    # Conference-related keywords in URL
    conference_keywords = [
        'conference', 'summit', 'symposium', 'workshop', 'seminar',
        'congress', 'convention', 'meeting', 'forum', 'expo',
        'festival', 'event', 'gathering', 'bootcamp', 'hackathon',
        'tech', 'ai', 'ml', 'data', 'dev', 'code', 'software',
        '2024', '2025', 'annual', 'international'
    ]
    
    # Check for conference keywords
    keyword_found = any(keyword in url_lower for keyword in conference_keywords)
    
    # Skip common non-conference pages
    skip_patterns = [
        'facebook.com', 'twitter.com', 'linkedin.com', 'instagram.com',
        'youtube.com', 'github.com', 'mailto:', 'tel:', '#',
        '.pdf', '.doc', '.ppt', '.jpg', '.png', '.gif',
        '/login', '/signup', '/register', '/contact', '/about',
        '/terms', '/privacy', '/cookie', '/legal'
    ]
    
    # Skip if matches exclusion patterns
    if any(pattern in url_lower for pattern in skip_patterns):
        return False
    
    # Must have http/https
    if not url_lower.startswith(('http://', 'https://')):
        return False
    
    return keyword_found


def extract_links_from_content(html_content: str, base_url: str) -> List[str]:
    """
    Extract all links from HTML content that look like conference pages.
    
    Args:
        html_content: HTML content to parse
        base_url: Base URL for resolving relative links
        
    Returns:
        List of absolute URLs that look like conference pages
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        links = set()
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
                links.add(absolute_url)
        
        # Also look for URLs in text content (sometimes links are mentioned but not linked)
        text_content = soup.get_text()
        url_pattern = r'https?://[^\s<>"\']+(?:conference|summit|event|tech|ai|ml|data)[^\s<>"\']*'
        text_urls = re.findall(url_pattern, text_content, re.IGNORECASE)
        
        for url in text_urls:
            if looks_like_conference_link(url, base_domain):
                links.add(url)
        
        return list(links)
        
    except Exception as e:
        print(f"❌ Error parsing HTML content: {str(e)}")
        return []


def expand_aggregator_page(url: str) -> List[str]:
    """
    Download and extract conference links from an aggregator page.
    
    Args:
        url: URL of the aggregator page to expand
        
    Returns:
        List of unique conference URLs found on the page
    """
    print(f"🔍 Expanding aggregator page: {url}")
    
    try:
        # Add delay to be respectful
        time.sleep(1)
        
        # Download the page content
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Extract links from the content
        conference_links = extract_links_from_content(response.text, url)
        
        # Remove duplicates and the original URL
        unique_links = list(set(conference_links))
        if url in unique_links:
            unique_links.remove(url)
        
        print(f"✅ Found {len(unique_links)} potential conference links from aggregator")
        
        # Log some examples (first 3)
        for i, link in enumerate(unique_links[:3]):
            print(f"   🔗 {link}")
        
        if len(unique_links) > 3:
            print(f"   ... and {len(unique_links) - 3} more")
        
        return unique_links
        
    except requests.RequestException as e:
        print(f"❌ Error downloading aggregator page {url}: {str(e)}")
        return []
    except Exception as e:
        print(f"❌ Error processing aggregator page {url}: {str(e)}")
        return []


def expand_multiple_aggregators(urls: List[str]) -> List[str]:
    """
    Expand multiple aggregator URLs and return all discovered conference links.
    
    Args:
        urls: List of aggregator URLs to expand
        
    Returns:
        Combined list of all discovered conference URLs
    """
    all_conference_links = []
    
    for url in urls:
        if is_aggregator_url(url):
            conference_links = expand_aggregator_page(url)
            all_conference_links.extend(conference_links)
        else:
            # If not an aggregator, include the original URL
            all_conference_links.append(url)
    
    # Remove duplicates
    return list(set(all_conference_links))


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