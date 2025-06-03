"""
Firecrawl utility for fetching content from websites.
"""
import os
from typing import Dict, Any, Optional
from firecrawl import FirecrawlApp
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class FirecrawlFetcher:
    """Helper class to fetch content using Firecrawl API."""
    
    def __init__(self):
        """Initialize with API key from environment."""
        api_key = os.getenv('FIRECRAWL_API_KEY')
        if not api_key:
            raise ValueError("FIRECRAWL_API_KEY not found in environment variables")
        
        # Initialize FirecrawlApp with just the API key - no additional parameters
        self.app = FirecrawlApp(api_key=api_key)
    
    def scrape_url(self, url: str, include_tags: Optional[list] = None, 
                   exclude_tags: Optional[list] = None) -> Dict[str, Any]:
        """
        Scrape a single URL and return the content.
        
        Args:
            url: The URL to scrape
            include_tags: HTML tags to include in scraping (deprecated parameter)
            exclude_tags: HTML tags to exclude from scraping (deprecated parameter)
            
        Returns:
            Dictionary with scraped content including 'markdown' and 'html' keys
        """
        try:
            # Use basic scrape_url without formats parameter for better compatibility
            result = self.app.scrape_url(url)
            
            # Handle both dictionary and object response formats
            if hasattr(result, 'get'):
                # Dictionary-style response
                success = result.get('success', True)
                data = result.get('data', result)
                error = result.get('error', 'Unknown error occurred')
                
                if success:
                    return {
                        'success': True,
                        'url': url,
                        'markdown': data.get('markdown', '') if hasattr(data, 'get') else getattr(data, 'markdown', ''),
                        'html': data.get('html', '') if hasattr(data, 'get') else getattr(data, 'html', ''),
                        'metadata': data.get('metadata', {}) if hasattr(data, 'get') else getattr(data, 'metadata', {})
                    }
                else:
                    return {
                        'success': False,
                        'url': url,
                        'error': error
                    }
            else:
                # Object-style response (ScrapeResponse object)
                success = getattr(result, 'success', True)
                
                if success:
                    # Try to get data from the response object
                    markdown = getattr(result, 'markdown', '')
                    html = getattr(result, 'html', '')
                    metadata = getattr(result, 'metadata', {})
                    
                    # If no direct attributes, try to get from data attribute
                    if not markdown and not html and hasattr(result, 'data'):
                        data = result.data
                        if isinstance(data, dict):
                            markdown = data.get('markdown', '')
                            html = data.get('html', '')
                            metadata = data.get('metadata', {})
                        else:
                            markdown = getattr(data, 'markdown', '')
                            html = getattr(data, 'html', '')
                            metadata = getattr(data, 'metadata', {})
                    
                    return {
                        'success': True,
                        'url': url,
                        'markdown': markdown,
                        'html': html,
                        'metadata': metadata
                    }
                else:
                    error = getattr(result, 'error', 'Unknown error occurred')
                    return {
                        'success': False,
                        'url': url,
                        'error': error
                    }
                
        except Exception as e:
            return {
                'success': False,
                'url': url,
                'error': f"Exception occurred: {str(e)}"
            }
    
    def crawl_site(self, url: str, max_pages: int = 10, 
                   include_paths: Optional[list] = None,
                   exclude_paths: Optional[list] = None) -> Dict[str, Any]:
        """
        Crawl a website starting from the given URL.
        
        Args:
            url: The starting URL to crawl
            max_pages: Maximum number of pages to crawl
            include_paths: URL patterns to include
            exclude_paths: URL patterns to exclude
            
        Returns:
            Dictionary with crawled content
        """
        try:
            # Use the updated API format for version 2.7.0
            result = self.app.crawl_url(
                url,
                limit=max_pages
            )
            
            # Handle both dictionary and object response formats
            if hasattr(result, 'get'):
                # Dictionary-style response
                success = result.get('success', True)
                data = result.get('data', [])
                error = result.get('error')
            else:
                # Object-style response
                success = getattr(result, 'success', True)
                data = getattr(result, 'data', [])
                error = getattr(result, 'error', None)
            
            return {
                'success': success,
                'url': url,
                'data': data,
                'error': error if not success else None
            }
            
        except Exception as e:
            return {
                'success': False,
                'url': url,
                'error': f"Exception occurred: {str(e)}"
            } 