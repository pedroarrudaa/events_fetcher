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
            # Use the correct API format for version 1.13.5
            params = {
                'formats': ['markdown', 'html']
            }
            
            result = self.app.scrape_url(url, params=params)
            
            # Handle different response types - might be object or dict
            if hasattr(result, '__dict__'):
                # If it's an object, convert to dict
                result_dict = result.__dict__ if hasattr(result, '__dict__') else {}
            elif isinstance(result, dict):
                result_dict = result
            else:
                # Try to access as attributes
                result_dict = {
                    'success': getattr(result, 'success', True),
                    'data': getattr(result, 'data', None),
                    'markdown': getattr(result, 'markdown', ''),
                    'html': getattr(result, 'html', ''),
                    'metadata': getattr(result, 'metadata', {}),
                    'error': getattr(result, 'error', None)
                }
            
            # Check for success
            success = result_dict.get('success', True)
            if success:
                # Extract data - might be in 'data' key or at root level
                data = result_dict.get('data', result_dict)
                
                return {
                    'success': True,
                    'url': url,
                    'markdown': data.get('markdown', result_dict.get('markdown', '')),
                    'html': data.get('html', result_dict.get('html', '')),
                    'metadata': data.get('metadata', result_dict.get('metadata', {}))
                }
            else:
                return {
                    'success': False,
                    'url': url,
                    'error': result_dict.get('error', 'Unknown error occurred')
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
            
            return {
                'success': result.get('success', True),
                'url': url,
                'data': result.get('data', []),
                'error': result.get('error') if not result.get('success', True) else None
            }
            
        except Exception as e:
            return {
                'success': False,
                'url': url,
                'error': f"Exception occurred: {str(e)}"
            } 