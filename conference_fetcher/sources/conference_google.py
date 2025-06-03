"""
Conference source for fetching AI-related conferences using Google-style search.
"""
import os
import json
from typing import List, Dict, Any
from tavily import TavilyClient
from openai import OpenAI
from utils.firecrawl import FirecrawlFetcher
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class ConferenceGoogleScraper:
    """Scraper for AI conferences using Tavily search and OpenAI extraction."""
    
    def __init__(self, queries_file: str = "queries.txt"):
        """Initialize the scraper with Tavily and OpenAI clients."""
        self.tavily_client = TavilyClient(api_key=os.getenv('TAVILY_API_KEY'))
        
        # Initialize OpenAI client with better error handling
        try:
            import httpx
            # Create a custom httpx client without the problematic proxies parameter
            custom_httpx_client = httpx.Client()
            self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'), http_client=custom_httpx_client)
        except Exception as e:
            # Fallback: try basic initialization without custom client
            try:
                self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
            except Exception as e2:
                print(f"❌ Failed to initialize OpenAI client: {e2}")
                self.openai_client = None
        
        self.firecrawl_fetcher = FirecrawlFetcher()
        
        # Load search queries from file
        self.search_queries = self._load_queries_from_file(queries_file)
    
    def _load_queries_from_file(self, queries_file: str) -> List[str]:
        """
        Load search queries from a text file.
        
        Args:
            queries_file: Path to the queries file (relative to project root)
            
        Returns:
            List of search query strings
        """
        try:
            # Handle relative path to project root
            if not os.path.isabs(queries_file):
                queries_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), queries_file)
            
            with open(queries_file, 'r', encoding='utf-8') as f:
                queries = [line.strip() for line in f if line.strip()]
            
            print(f"📋 Loaded {len(queries)} search queries from {queries_file}")
            return queries
            
        except FileNotFoundError:
            print(f"⚠️ Queries file not found: {queries_file}")
            print("Using fallback hardcoded queries")
            # Fallback to hardcoded queries
            return [
                "AI conference San Francisco 2025",
                "Agentic AI workshop virtual",
                "LLM events USA 2025",
                "machine learning conference 2025",
                "artificial intelligence summit 2025"
            ]
        except Exception as e:
            print(f"⚠️ Error loading queries file: {str(e)}")
            print("Using fallback hardcoded queries")
            # Fallback to hardcoded queries
            return [
                "AI conference San Francisco 2025",
                "Agentic AI workshop virtual",
                "LLM events USA 2025",
                "machine learning conference 2025",
                "artificial intelligence summit 2025"
            ]
    
    def search_conferences(self, limit_per_query: int = 3) -> List[Dict[str, Any]]:
        """
        Search for AI conferences using Tavily API.
        
        Args:
            limit_per_query: Maximum number of results per search query
            
        Returns:
            List of search results with URLs and basic info
        """
        all_results = []
        
        for query in self.search_queries:
            print(f"Searching for: {query}")
            
            try:
                # Use Tavily to search
                response = self.tavily_client.search(
                    query=query,
                    search_depth="basic",
                    max_results=limit_per_query
                )
                
                for result in response.get('results', []):
                    conference_data = {
                        'url': result.get('url', ''),
                        'title': result.get('title', ''),
                        'snippet': result.get('content', ''),
                        'search_query': query
                    }
                    all_results.append(conference_data)
                    
                print(f"Found {len(response.get('results', []))} results for '{query}'")
                
            except Exception as e:
                print(f"Error searching for '{query}': {str(e)}")
                continue
        
        # Remove duplicates based on URL
        unique_results = []
        seen_urls = set()
        for result in all_results:
            if result['url'] not in seen_urls:
                unique_results.append(result)
                seen_urls.add(result['url'])
        
        print(f"Total unique conference results found: {len(unique_results)}")
        return unique_results
    
    def extract_page_content(self, url: str) -> Dict[str, Any]:
        """
        Extract content from a conference page using Firecrawl or requests.
        
        Args:
            url: URL of the conference page
            
        Returns:
            Dictionary with page content and extraction status
        """
        print(f"Extracting content from: {url}")
        
        # Try Firecrawl first
        try:
            result = self.firecrawl_fetcher.scrape_url(url)
            if result['success']:
                return {
                    'success': True,
                    'content': result['markdown'],
                    'html': result['html'],
                    'method': 'firecrawl'
                }
        except Exception as e:
            print(f"Firecrawl failed for {url}: {str(e)}")
        
        # Fallback to requests
        try:
            response = requests.get(url, timeout=30, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            response.raise_for_status()
            
            return {
                'success': True,
                'content': response.text,
                'html': response.text,
                'method': 'requests'
            }
            
        except Exception as e:
            print(f"Requests failed for {url}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'content': '',
                'html': ''
            }
    
    def extract_conference_data_with_ai(self, content: str, url: str) -> Dict[str, Any]:
        """
        Use OpenAI to extract structured conference data from page content.
        
        Args:
            content: Raw page content (HTML or markdown)
            url: Original URL for reference
            
        Returns:
            Dictionary with extracted conference fields
        """
        print(f"Extracting structured data with AI for: {url}")
        
        # Create a prompt for GPT to extract conference information
        prompt = f"""
Extract conference information from the following web page content. Return ONLY a valid JSON object with these exact fields:

{{
  "name": "Conference name",
  "url": "{url}",
  "is_remote": true/false,
  "city": "City name or 'Remote' or 'TBD'",
  "start_date": "YYYY-MM-DD or 'TBD'",
  "end_date": "YYYY-MM-DD or 'TBD'",
  "topics": ["topic1", "topic2"],
  "sponsors": ["sponsor1", "sponsor2"],
  "speakers": ["speaker1", "speaker2"],
  "price": "Price info or 'TBD' or 'Free'",
  "organizer": "Organizing company/institution"
}}

Rules:
- Use "TBD" for any field that cannot be determined from the content
- For is_remote: true if virtual/online, false if in-person, null if unclear
- For dates: use YYYY-MM-DD format or "TBD"
- For arrays: include up to 5 items max, or empty array if none found
- Return ONLY the JSON object, no other text

Web page content:
{content[:4000]}...
"""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert at extracting structured conference information from web pages. Always return valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            
            # Parse the JSON response
            json_text = response.choices[0].message.content.strip()
            
            # Clean up the response to ensure it's valid JSON
            if json_text.startswith('```json'):
                json_text = json_text[7:]
            if json_text.endswith('```'):
                json_text = json_text[:-3]
            
            conference_data = json.loads(json_text)
            
            # Ensure all required fields are present
            required_fields = ['name', 'url', 'is_remote', 'city', 'start_date', 'end_date', 'topics', 'sponsors', 'speakers', 'price', 'organizer']
            for field in required_fields:
                if field not in conference_data:
                    conference_data[field] = 'TBD' if field not in ['topics', 'sponsors', 'speakers'] else []
            
            return conference_data
            
        except json.JSONDecodeError as e:
            print(f"JSON parsing error for {url}: {str(e)}")
            return self._create_fallback_data(url)
        except Exception as e:
            print(f"AI extraction error for {url}: {str(e)}")
            return self._create_fallback_data(url)
    
    def _create_fallback_data(self, url: str) -> Dict[str, Any]:
        """Create fallback conference data when AI extraction fails."""
        return {
            'name': 'TBD',
            'url': url,
            'is_remote': None,
            'city': 'TBD',
            'start_date': 'TBD',
            'end_date': 'TBD',
            'topics': [],
            'sponsors': [],
            'speakers': [],
            'price': 'TBD',
            'organizer': 'TBD',
            'extraction_error': True
        }
    
    def get_conference_details(self, url: str) -> Dict[str, Any]:
        """
        Get detailed conference information for a single URL.
        
        Args:
            url: URL of the conference page
            
        Returns:
            Dictionary with complete conference details
        """
        # Extract page content
        content_result = self.extract_page_content(url)
        
        if not content_result['success']:
            return {
                'url': url,
                'error': content_result.get('error', 'Content extraction failed'),
                'success': False
            }
        
        # Extract structured data using AI
        conference_data = self.extract_conference_data_with_ai(
            content_result['content'], 
            url
        )
        
        # Add metadata
        conference_data['extraction_method'] = content_result['method']
        conference_data['success'] = True
        
        return conference_data


def get_conference_urls(limit: int = 3, max_results_per_query: int = 2, queries_file: str = "queries.txt") -> List[Dict[str, Any]]:
    """
    Fetch conference data using Google-style search.
    
    Args:
        limit: Maximum number of conferences to return
        max_results_per_query: Maximum number of results per search query (2-3 recommended)
        queries_file: Path to file containing search queries
        
    Returns:
        List of conference dictionaries with complete information
    """
    try:
        scraper = ConferenceGoogleScraper(queries_file=queries_file)
        
        # Search for conferences with limited results per query
        search_results = scraper.search_conferences(limit_per_query=max_results_per_query)
        
        if not search_results:
            print("❌ No search results found from any query")
            return []
        
        # Limit total results to save API credits
        limited_results = search_results[:limit]
        print(f"🎯 Processing {len(limited_results)} conference URLs (limited from {len(search_results)} found)")
        
        conferences = []
        for i, result in enumerate(limited_results, 1):
            try:
                print(f"\n--- Processing conference {i}/{len(limited_results)} ---")
                conference_data = scraper.get_conference_details(result['url'])
                
                if conference_data.get('success', False):
                    conferences.append(conference_data)
                    print(f"✅ Successfully processed: {conference_data.get('name', 'TBD')}")
                else:
                    print(f"❌ Failed to get details for {result['url']}: {conference_data.get('error', 'Unknown error')}")
                    
            except Exception as e:
                print(f"❌ Error processing {result.get('url', 'unknown URL')}: {str(e)}")
                continue
        
        print(f"\n🎉 Successfully processed {len(conferences)} out of {len(limited_results)} conferences")
        return conferences
        
    except Exception as e:
        print(f"💥 Critical error in conference fetching: {str(e)}")
        return []


if __name__ == "__main__":
    # Test the scraper with limited results
    print("🧪 Testing Conference Google Scraper...")
    conferences = get_conference_urls(limit=3, max_results_per_query=2)
    print(f"\n📊 Test Results: Found {len(conferences)} conferences")
    for i, conf in enumerate(conferences, 1):
        print(f"{i}. {conf.get('name', 'TBD')} - {conf.get('city', 'TBD')} ({conf.get('url', 'No URL')})") 