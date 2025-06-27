"""
Enhanced Web Scraper with Hybrid Crawl4AI Integration

This module provides an intelligent scraping system that automatically
selects the best scraping method based on the target website.
"""

import asyncio
import time
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import requests

# Import from parent modules
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import (
    CRAWL4AI_AVAILABLE, HTTP_TIMEOUT_STANDARD, DEFAULT_HEADERS,
    CRAWL4AI_PAGE_TIMEOUT, CRAWL4AI_JS_WAIT_SHORT
)
from shared_utils import logger, HTTPClient

# Try to import Crawl4AI if available
if CRAWL4AI_AVAILABLE:
    try:
        from fetchers.enrichers.crawl4ai import crawl4ai_scrape_url, crawl4ai_check_availability
        CRAWL4AI_ENABLED = crawl4ai_check_availability()
    except ImportError:
        CRAWL4AI_ENABLED = False
        logger.log("warning", "Crawl4AI module not found, disabling Crawl4AI support")
else:
    CRAWL4AI_ENABLED = False


class SiteProfile:
    """Website profiling for optimal scraper selection"""
    
    # JavaScript-heavy sites that require dynamic rendering
    JS_HEAVY_SITES = [
        'eventbrite.com', 'meetup.com', 'lu.ma', 'luma.com',
        'devpost.com', 'mlh.io', 'hopin.com', 'airmeet.com'
    ]
    
    # Sites that work well with simple scraping
    STATIC_SITES = [
        'ieee.org', 'acm.org', 'oreilly.com', 'infoq.com',
        'conferences.ieee.org', 'events.linuxfoundation.org'
    ]
    
    # Sites that may block automated requests
    PROTECTED_SITES = [
        'linkedin.com', 'facebook.com', 'ticketmaster.com'
    ]
    
    @classmethod
    def analyze_url(cls, url: str) -> Dict[str, Any]:
        """Analyze URL to determine optimal scraping strategy"""
        domain = urlparse(url).netloc.replace('www.', '')
        
        profile = {
            'url': url,
            'domain': domain,
            'requires_js': False,
            'is_protected': False,
            'is_static': False,
            'recommended_method': 'auto',
            'fallback_methods': ['simple', 'selenium']
        }
        
        # Check site categories
        if domain in cls.JS_HEAVY_SITES:
            profile['requires_js'] = True
            profile['recommended_method'] = 'crawl4ai' if CRAWL4AI_ENABLED else 'selenium'
            profile['fallback_methods'] = ['selenium', 'simple']
        elif domain in cls.STATIC_SITES:
            profile['is_static'] = True
            profile['recommended_method'] = 'simple'
            profile['fallback_methods'] = ['crawl4ai', 'selenium']
        elif domain in cls.PROTECTED_SITES:
            profile['is_protected'] = True
            profile['recommended_method'] = 'selenium'
            profile['fallback_methods'] = ['crawl4ai']
        
        return profile


class EnhancedScraper:
    """Hybrid scraper with intelligent method selection and fallback"""
    
    def __init__(self):
        self.http_client = HTTPClient()
        self.selenium_driver = None
        
    def __del__(self):
        """Cleanup Selenium driver if initialized"""
        if self.selenium_driver:
            try:
                self.selenium_driver.quit()
            except:
                pass
    
    async def scrape_async(self, url: str, force_method: Optional[str] = None) -> Dict[str, Any]:
        """
        Asynchronously scrape URL with intelligent method selection
        
        Args:
            url: URL to scrape
            force_method: Force specific method ('crawl4ai', 'simple', 'selenium', 'auto')
            
        Returns:
            Dict with success status, content, method used, and metadata
        """
        start_time = time.time()
        
        # Analyze site profile
        profile = SiteProfile.analyze_url(url)
        
        # Determine scraping method
        if force_method and force_method != 'auto':
            method = force_method
        else:
            method = profile['recommended_method']
        
        logger.log("info", f"Scraping {url} with method: {method}")
        
        # Try primary method
        result = await self._try_scrape_method(url, method, profile)
        
        # If failed, try fallback methods
        if not result['success'] and not force_method:
            for fallback_method in profile['fallback_methods']:
                if fallback_method != method:
                    logger.log("info", f"Trying fallback method: {fallback_method}")
                    result = await self._try_scrape_method(url, fallback_method, profile)
                    if result['success']:
                        break
        
        # Add timing and profile info
        result['scrape_time'] = time.time() - start_time
        result['site_profile'] = profile
        
        return result
    
    async def _try_scrape_method(self, url: str, method: str, profile: Dict[str, Any]) -> Dict[str, Any]:
        """Try specific scraping method"""
        try:
            if method == 'crawl4ai' and CRAWL4AI_ENABLED:
                return await self._scrape_with_crawl4ai(url)
            elif method == 'selenium':
                return await self._scrape_with_selenium(url)
            elif method == 'simple':
                return await self._scrape_with_requests(url)
            else:
                # Auto mode - try based on profile
                if profile['requires_js'] and CRAWL4AI_ENABLED:
                    return await self._scrape_with_crawl4ai(url)
                elif profile['requires_js']:
                    return await self._scrape_with_selenium(url)
                else:
                    return await self._scrape_with_requests(url)
        except Exception as e:
            logger.log("error", f"Scraping failed with {method}", error=str(e))
            return {
                'success': False,
                'error': str(e),
                'method': method,
                'content': '',
                'url': url
            }
    
    async def _scrape_with_crawl4ai(self, url: str) -> Dict[str, Any]:
        """Scrape using Crawl4AI"""
        if not CRAWL4AI_ENABLED:
            return {'success': False, 'error': 'Crawl4AI not available', 'method': 'crawl4ai'}
        
        try:
            result = await crawl4ai_scrape_url(url, extract_structured=True)
            return {
                'success': result.get('success', False),
                'content': result.get('content', ''),
                'method': 'crawl4ai',
                'url': url,
                'metadata': result.get('metadata', {})
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'method': 'crawl4ai',
                'content': '',
                'url': url
            }
    
    async def _scrape_with_selenium(self, url: str) -> Dict[str, Any]:
        """Scrape using Selenium WebDriver"""
        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._scrape_with_selenium_sync, url)
    
    def _scrape_with_selenium_sync(self, url: str) -> Dict[str, Any]:
        """Synchronous Selenium scraping"""
        driver = None
        try:
            # Setup Chrome options
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument(f'user-agent={DEFAULT_HEADERS["User-Agent"]}')
            
            # Initialize driver
            driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(CRAWL4AI_PAGE_TIMEOUT // 1000)  # Convert to seconds
            
            # Load page
            driver.get(url)
            
            # Wait for content to load
            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            # Additional wait for JavaScript
            time.sleep(CRAWL4AI_JS_WAIT_SHORT / 1000)  # Convert to seconds
            
            # Get page source
            content = driver.page_source
            
            return {
                'success': True,
                'content': content,
                'method': 'selenium',
                'url': url,
                'metadata': {
                    'title': driver.title,
                    'current_url': driver.current_url
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'method': 'selenium',
                'content': '',
                'url': url
            }
        finally:
            if driver:
                driver.quit()
    
    async def _scrape_with_requests(self, url: str) -> Dict[str, Any]:
        """Scrape using simple requests"""
        try:
            response = self.http_client.get(url, timeout=HTTP_TIMEOUT_STANDARD)
            response.raise_for_status()
            
            return {
                'success': True,
                'content': response.text,
                'method': 'simple',
                'url': url,
                'metadata': {
                    'status_code': response.status_code,
                    'headers': dict(response.headers)
                }
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'method': 'simple',
                'content': '',
                'url': url
            }
    
    def scrape(self, url: str, force_method: Optional[str] = None) -> Dict[str, Any]:
        """Synchronous wrapper for scraping"""
        return asyncio.run(self.scrape_async(url, force_method))
    
    async def scrape_multiple_async(self, urls: List[str], max_concurrent: int = 5,
                                  force_method: Optional[str] = None) -> List[Dict[str, Any]]:
        """Scrape multiple URLs concurrently"""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def scrape_with_semaphore(url: str) -> Dict[str, Any]:
            async with semaphore:
                return await self.scrape_async(url, force_method)
        
        tasks = [scrape_with_semaphore(url) for url in urls]
        return await asyncio.gather(*tasks)
    
    def analyze_content_quality(self, content: str) -> Dict[str, Any]:
        """Analyze scraped content quality"""
        if not content:
            return {'quality_score': 0, 'issues': ['No content']}
        
        soup = BeautifulSoup(content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        text = soup.get_text()
        text_length = len(text.strip())
        
        # Quality indicators
        has_title = bool(soup.find('title'))
        has_headings = bool(soup.find_all(['h1', 'h2', 'h3']))
        has_paragraphs = len(soup.find_all('p')) > 2
        has_links = len(soup.find_all('a', href=True)) > 5
        
        # Calculate quality score
        quality_score = 0.0
        if text_length > 500:
            quality_score += 0.3
        if has_title:
            quality_score += 0.2
        if has_headings:
            quality_score += 0.2
        if has_paragraphs:
            quality_score += 0.2
        if has_links:
            quality_score += 0.1
        
        issues = []
        if text_length < 500:
            issues.append('Content too short')
        if not has_title:
            issues.append('No title found')
        if not has_headings:
            issues.append('No headings found')
        
        return {
            'quality_score': min(quality_score, 1.0),
            'text_length': text_length,
            'has_title': has_title,
            'has_headings': has_headings,
            'has_paragraphs': has_paragraphs,
            'has_links': has_links,
            'issues': issues
        }


# Convenience functions for backward compatibility
async def enhanced_scrape_url(url: str, method: Optional[str] = None) -> Dict[str, Any]:
    """Enhanced scraping with automatic method selection"""
    scraper = EnhancedScraper()
    return await scraper.scrape_async(url, force_method=method)


async def enhanced_scrape_multiple(urls: List[str], max_concurrent: int = 5,
                                 method: Optional[str] = None) -> List[Dict[str, Any]]:
    """Enhanced batch scraping"""
    scraper = EnhancedScraper()
    return await scraper.scrape_multiple_async(urls, max_concurrent, method)


def test_enhanced_scraper():
    """Test the enhanced scraper with different sites"""
    test_urls = [
        'https://www.eventbrite.com/d/ca--san-francisco/ai-conference/',
        'https://ieee.org/conferences',
        'https://devpost.com/hackathons'
    ]
    
    scraper = EnhancedScraper()
    
    for url in test_urls:
        print(f"\nTesting: {url}")
        result = scraper.scrape(url)
        
        if result['success']:
            quality = scraper.analyze_content_quality(result['content'])
            print(f"  Method: {result['method']}")
            print(f"  Quality Score: {quality['quality_score']:.2f}")
            print(f"  Content Length: {quality['text_length']} chars")
            print(f"  Scrape Time: {result.get('scrape_time', 0):.2f}s")
            if quality['issues']:
                print(f"  Issues: {', '.join(quality['issues'])}")
        else:
            print(f"  Failed: {result.get('error', 'Unknown error')}")


if __name__ == '__main__':
    test_enhanced_scraper() 