"""
GPT-based extractor for structured conference data.
"""
import json
import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Dict, Any, Optional, List
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def extract_dates_from_text(text: str) -> Dict[str, Optional[str]]:
    """
    Extract dates from text using regex patterns as a fallback method.
    
    Args:
        text: Text content to search for dates
        
    Returns:
        Dictionary with start_date, end_date, registration_deadline or None
    """
    if not text:
        return {"start_date": None, "end_date": None, "registration_deadline": None}
    
    dates = {"start_date": None, "end_date": None, "registration_deadline": None}
    
    try:
        # Clean text
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Pattern 1: "July 14-16, 2025" or "July 14th-16th, 2025"
        pattern1 = r'(\w+)\s+(\d+)(?:st|nd|rd|th)?\s*[-–]\s*(\d+)(?:st|nd|rd|th)?,?\s*(\d{4})'
        match1 = re.search(pattern1, text, re.IGNORECASE)
        if match1:
            month, start_day, end_day, year = match1.groups()
            try:
                start_date = datetime.strptime(f"{month} {start_day} {year}", "%B %d %Y")
                end_date = datetime.strptime(f"{month} {end_day} {year}", "%B %d %Y")
                dates["start_date"] = start_date.strftime("%Y-%m-%d")
                dates["end_date"] = end_date.strftime("%Y-%m-%d")
            except ValueError:
                try:
                    start_date = datetime.strptime(f"{month} {start_day} {year}", "%b %d %Y")
                    end_date = datetime.strptime(f"{month} {end_day} {year}", "%b %d %Y")
                    dates["start_date"] = start_date.strftime("%Y-%m-%d")
                    dates["end_date"] = end_date.strftime("%Y-%m-%d")
                except ValueError:
                    pass
        
        # Pattern 2: "Friday July 14, 2025 to Jul 16, 2025"
        pattern2 = r'(\w+)\s+(\w+)\s+(\d+),?\s+(\d{4}).*?to\s+(\w+)\s+(\d+),?\s+(\d{4})?'
        match2 = re.search(pattern2, text, re.IGNORECASE)
        if match2 and not dates["start_date"]:
            start_month, start_day, start_year = match2.group(2), match2.group(3), match2.group(4)
            end_month, end_day = match2.group(5), match2.group(6)
            end_year = match2.group(7) if match2.group(7) else start_year
            
            try:
                start_date = datetime.strptime(f"{start_month} {start_day} {start_year}", "%B %d %Y")
                end_date = datetime.strptime(f"{end_month} {end_day} {end_year}", "%B %d %Y")
                dates["start_date"] = start_date.strftime("%Y-%m-%d")
                dates["end_date"] = end_date.strftime("%Y-%m-%d")
            except ValueError:
                try:
                    start_date = datetime.strptime(f"{start_month} {start_day} {start_year}", "%b %d %Y")
                    end_date = datetime.strptime(f"{end_month} {end_day} {end_year}", "%b %d %Y")
                    dates["start_date"] = start_date.strftime("%Y-%m-%d")
                    dates["end_date"] = end_date.strftime("%Y-%m-%d")
                except ValueError:
                    pass
        
        # Pattern 3: Registration deadline patterns
        deadline_patterns = [
            r'(?:registration|submit|deadline|due).*?(?:by|until|before)\s+(\w+\s+\d+,?\s+\d{4})',
            r'(?:deadline|due|submit by|closes)\s*:?\s*(\w+\s+\d+,?\s+\d{4})',
            r'(\w+\s+\d+,?\s+\d{4}).*?(?:deadline|due|registration closes)'
        ]
        
        for pattern in deadline_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                try:
                    deadline_date = datetime.strptime(date_str, "%B %d, %Y")
                    dates["registration_deadline"] = deadline_date.strftime("%Y-%m-%d")
                    break
                except ValueError:
                    try:
                        deadline_date = datetime.strptime(date_str, "%b %d, %Y")
                        dates["registration_deadline"] = deadline_date.strftime("%Y-%m-%d")
                        break
                    except ValueError:
                        try:
                            deadline_date = datetime.strptime(date_str, "%B %d %Y")
                            dates["registration_deadline"] = deadline_date.strftime("%Y-%m-%d")
                            break
                        except ValueError:
                            pass
        
        # Pattern 4: ISO date format YYYY-MM-DD
        iso_dates = re.findall(r'\d{4}-\d{2}-\d{2}', text)
        if iso_dates and not dates["start_date"]:
            dates["start_date"] = iso_dates[0]
            if len(iso_dates) > 1:
                dates["end_date"] = iso_dates[1]
            else:
                dates["end_date"] = iso_dates[0]
        
    except Exception as e:
        print(f"Date extraction error: {e}")
    
    return dates

class GPTExtractor:
    """Extract structured data from conference pages using OpenAI GPT."""
    
    def __init__(self):
        """Initialize with OpenAI API key."""
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        # Initialize OpenAI client with custom httpx client to avoid proxies parameter issue
        try:
            import httpx
            # Create a custom httpx client without the problematic proxies parameter
            custom_httpx_client = httpx.Client()
            self.client = OpenAI(api_key=api_key, http_client=custom_httpx_client)
        except Exception as e:
            # Fallback: try basic initialization without custom client
            try:
                self.client = OpenAI(api_key=api_key)
            except Exception as e2:
                print(f"❌ Failed to initialize OpenAI client: {e2}")
                self.client = None
        
        self.model = "gpt-4o-mini"  # Using GPT-4 mini as specified
    
    def extract_conference_data(self, html_content: str, markdown_content: str, url: str) -> Dict[str, Any]:
        """
        Extract structured data from conference content.
        
        Args:
            html_content: Raw HTML content
            markdown_content: Markdown content from Firecrawl
            url: Original URL of the conference
            
        Returns:
            Dictionary with extracted conference data
        """
        # If OpenAI client failed to initialize, return basic data without enrichment
        if self.client is None:
            return {
                'extraction_success': False,
                'url': url,
                'error': "OpenAI client not available - GPT enrichment disabled",
                'extraction_method': 'fallback-no-gpt'
            }
        
        try:
            # Use markdown content as it's cleaner for LLM processing
            content_to_analyze = markdown_content if markdown_content.strip() else html_content
            
            # Truncate content if too long (GPT has token limits)
            max_chars = 12000  # Conservative limit for GPT-4 mini
            if len(content_to_analyze) > max_chars:
                content_to_analyze = content_to_analyze[:max_chars] + "...[CONTENT TRUNCATED]"
            
            prompt = self._create_extraction_prompt(content_to_analyze, url)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at extracting structured information from conference websites. Always respond with valid JSON only."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=1500,
                temperature=0.1  # Low temperature for consistent extraction
            )
            
            # Parse the JSON response
            result_text = response.choices[0].message.content.strip()
            
            # Clean up the response in case GPT adds markdown formatting
            if result_text.startswith('```json'):
                result_text = result_text[7:]
            if result_text.endswith('```'):
                result_text = result_text[:-3]
            
            try:
                extracted_data = json.loads(result_text)
            except json.JSONDecodeError as e:
                print(f"❌ Failed to parse GPT JSON response: {e}")
                return {
                    'extraction_success': False,
                    'url': url,
                    'error': f"JSON parsing failed: {e}",
                    'extraction_method': 'gpt-failed',
                    'raw_response': result_text[:500]
                }
            
            # **IMPROVEMENT: More lenient validation - don't fail for missing optional fields**
            validated_data = self._validate_and_clean_extracted_data(extracted_data, url)
            
            # **IMPROVEMENT: Consider extraction successful if we have basic info**
            # Don't require all fields to be present - just name and some useful data
            has_basic_info = (
                validated_data.get('name') and 
                len(str(validated_data.get('name', '')).strip()) > 3 and
                validated_data.get('name', '').lower() not in ['unknown', 'n/a', 'tbd']
            )
            
            # Mark as successful if we have basic info, even if some fields are missing
            validated_data['extraction_success'] = has_basic_info
            validated_data['extraction_method'] = 'gpt'
            validated_data['url'] = url
            
            if has_basic_info:
                print(f"✅ GPT extraction successful for: {validated_data.get('name')}")
            else:
                print(f"⚠️ GPT extraction incomplete - missing basic info")
                validated_data['error'] = "Missing basic conference information"
            
            return validated_data
            
        except Exception as e:
            print(f"❌ GPT API call failed: {e}")
            
            # **IMPROVEMENT: Try fallback extraction with basic parsing**
            try:
                fallback_data = self.extract_with_fallback(html_content, markdown_content, url)
                # Even if fallback fails, still log the event with basic URL info
                if not fallback_data.get('extraction_success'):
                    fallback_data = {
                        'name': f"Conference at {url.split('/')[-2] if '/' in url else url}",
                        'url': url,
                        'extraction_success': False,
                        'extraction_method': 'minimal-fallback',
                        'error': f"GPT failed: {e}",
                        'remote': None,
                        'city': None,
                        'short_description': None,
                        'start_date': None,
                        'end_date': None,
                        'registration_deadline': None,
                        'speakers': [],
                        'sponsors': [],
                        'ticket_price': [],
                        'is_paid': None,
                        'themes': [],
                        'eligibility': None
                    }
                return fallback_data
            except Exception as fallback_error:
                print(f"❌ Fallback extraction also failed: {fallback_error}")
                
                # **IMPROVEMENT: Always return basic data to preserve the event**
                return {
                    'name': f"Conference at {url.split('/')[-2] if '/' in url else 'Unknown Site'}",
                    'url': url,
                    'extraction_success': False,
                    'extraction_method': 'error-fallback',
                    'error': f"Both GPT and fallback failed: {e}",
                    'remote': None,
                    'city': None,
                    'short_description': None,
                    'start_date': None,
                    'end_date': None,
                    'registration_deadline': None,
                    'speakers': [],
                    'sponsors': [],
                    'ticket_price': [],
                    'is_paid': None,
                    'themes': [],
                    'eligibility': None
                }
    
    def _create_extraction_prompt(self, content: str, url: str) -> str:
        """Create the enhanced extraction prompt for GPT."""
        return f"""
Extract structured information from this conference webpage content and return it as a JSON object.

URL: {url}

CONTENT:
{content}

Please extract the following fields and return ONLY a valid JSON object. Only extract what's AVAILABLE ON THE PAGE - do not guess or make assumptions:

{{
    "name": "Name of the conference",
    "url": "{url}",
    "remote": true/false (whether it's remote/virtual),
    "city": "City name if in-person or hybrid, null if fully remote",
    "short_description": "Brief description (1-2 sentences max)",
    "start_date": "Start date in YYYY-MM-DD format (e.g., 2025-07-14) or null",
    "end_date": "End date in YYYY-MM-DD format (e.g., 2025-07-16) or null",
    "registration_deadline": "Registration deadline in YYYY-MM-DD format or null",
    "speakers": [
        {{"name": "Speaker Name", "company": "Company/Organization", "title": "Job Title"}}
    ],
    "sponsors": ["List of sponsor names if mentioned"],
    "ticket_price": [
        {{"label": "Early Bird", "price": "$99"}},
        {{"label": "Standard", "price": "$199"}}
    ],
    "is_paid": true/false (based on whether ticket prices are present),
    "themes": ["List of themes/tracks if mentioned"],
    "eligibility": "Who can participate (students, professionals, etc.)"
}}

🚨 CRITICAL BUSINESS REQUIREMENTS:
1. ONLY extract events happening in 2025 or later (NO PAST EVENTS)
2. ONLY include events in: San Francisco/Bay Area, New York/NYC, OR Remote/Virtual
3. If event location is not clearly one of these, set city to null and remote to false

📍 LOCATION VALIDATION - Only accept these locations:
• San Francisco, SF, Bay Area, Silicon Valley, Palo Alto, Mountain View, Santa Clara, San Jose
• New York, NY, NYC, Manhattan, Brooklyn
• Remote, Virtual, Online, Webinar, Anywhere

📅 DATE EXTRACTION RULES:
- Look for patterns like: "July 14-16, 2025", "Friday July 14, 2025 to Jul 16", "July 14th - 16th, 2025"
- Convert ALL dates to YYYY-MM-DD format (ISO 8601)
- If only one date is mentioned, use it for both start_date and end_date
- Pay special attention to registration deadlines vs event dates
- Look for keywords like "starts", "begins", "ends", "until", "registration closes", "submit by"
- REJECT any dates before 2025-01-01 (current year requirement)

👥 SPEAKERS EXTRACTION:
- Look for speaker lists, keynote speakers, featured speakers
- Extract name, company/organization, and job title when available
- Format: {{"name": "Sahar Mor", "company": "Meta", "title": "VP of Open Source"}}
- Include keynote speakers, panel speakers, and workshop leaders
- Look for sections like "Speakers", "Keynotes", "Featured Speakers"

💰 PRICING EXTRACTION:
- Look for ticket prices, registration fees, admission costs
- Extract different pricing tiers (Early Bird, Student, Regular, etc.)
- Format: {{"label": "Early Bird", "price": "$99"}}
- Set is_paid to true if any prices are found, false if explicitly free

🏢 SPONSORS EXTRACTION:
- Look for sponsor logos, sponsor lists, "supported by", "partners"
- Extract company/organization names only
- Include different sponsor tiers and partners

🎯 THEMES EXTRACTION:
- Look for conference tracks, sessions, topics, focus areas
- Include both technical topics and application domains
- Example: ["AI/ML", "DevOps", "Cloud Computing", "Cybersecurity"]

⚠️ STRICT FILTERING RULES:
1. If event dates are in 2024 or earlier, DO NOT EXTRACT - return null for all fields
2. If location is not SF/Bay Area, NYC, or Remote, set city=null and remote=false
3. Use null for missing information - DO NOT GUESS
4. Only extract information that is clearly visible on the page
5. For lists, extract up to 10 items maximum to avoid overwhelming the response

QUALITY GUIDELINES:
- Return ONLY valid JSON, no other text
- All dates must be in YYYY-MM-DD format
- Keep descriptions concise and factual
- For boolean fields (remote, is_paid), be as accurate as possible based on content

EXAMPLES OF VALID EXTRACTION:
- ticket_price: [{{"label": "Early Bird", "price": "$99"}}, {{"label": "Standard", "price": "$199"}}]
- speakers: [{{"name": "Sahar Mor", "company": "Meta", "title": "VP of Open Source"}}, {{"name": "Alex Smith", "company": "Google", "title": "AI Research Director"}}]
- sponsors: ["Google", "Microsoft", "OpenAI", "Meta"]
- themes: ["Artificial Intelligence", "Machine Learning", "Cloud Computing", "DevOps"]
- start_date: "2025-07-14" (ONLY if date is clearly stated and in 2025+)

LOCATION EXAMPLES:
- Valid: "San Francisco, CA" → city: "San Francisco"
- Valid: "Virtual Conference" → remote: true, city: null
- Valid: "New York City" → city: "New York"
- Invalid: "London, UK" → city: null, remote: false
- Invalid: "Berlin, Germany" → city: null, remote: false
"""
    
    def extract_with_fallback(self, html_content: str, markdown_content: str, 
                             url: str, basic_details: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Extract data with fallback to basic parsing if GPT fails.
        
        Args:
            html_content: Raw HTML content
            markdown_content: Markdown content
            url: Original URL
            basic_details: Basic details from HTML parsing
            
        Returns:
            Dictionary with extracted data
        """
        # Try GPT extraction first
        gpt_result = self.extract_conference_data(html_content, markdown_content, url)
        
        if gpt_result.get('extraction_success', False):
            return gpt_result
        
        # Fallback to basic extraction
        print(f"GPT extraction failed for {url}, using fallback method")
        
        # Try to extract dates from content using regex fallback
        content_for_dates = markdown_content if markdown_content.strip() else html_content
        extracted_dates = extract_dates_from_text(content_for_dates)
        
        fallback_result = {
            'name': 'Unknown Conference',
            'url': url,
            'remote': None,
            'city': None,
            'short_description': None,
            'start_date': extracted_dates.get('start_date'),
            'end_date': extracted_dates.get('end_date'),
            'registration_deadline': extracted_dates.get('registration_deadline'),
            'speakers': [],
            'sponsors': [],
            'ticket_price': [],
            'is_paid': None,
            'themes': [],
            'eligibility': None,
            'extraction_success': False,
            'extraction_method': 'fallback',
            'gpt_error': gpt_result.get('error', 'Unknown error')
        }
        
        # Use basic details if available
        if basic_details:
            fallback_result['remote'] = basic_details.get('likely_remote', None)
        
        return fallback_result 

    def extract_missing_fields_fallback(self, html_content: str, markdown_content: str, 
                                       url: str, missing_fields: List[str], 
                                       current_event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Attempt to extract specific missing fields using a focused GPT prompt.
        This is called when initial enrichment succeeds but critical fields are missing.
        
        Args:
            html_content: Raw HTML content
            markdown_content: Markdown content
            url: URL of the event
            missing_fields: List of field names that are missing
            current_event: Current event data to provide context
            
        Returns:
            Dictionary with extracted missing fields (if any)
        """
        if not self.client:
            print("❌ OpenAI client not available for fallback enrichment")
            return {}
        
        # Create focused prompt for missing fields
        field_descriptions = {
            'organizers': 'the companies, organizations, or people organizing this conference',
            'speakers': 'speakers, presenters, or keynote speakers at this conference',
            'sponsors': 'companies or organizations sponsoring this conference',
            'venue': 'the venue, location, or address where this conference takes place',
            'ticket_price': 'the cost, price, or fee to attend this conference'
        }
        
        field_prompts = []
        for field in missing_fields:
            if field in field_descriptions:
                field_prompts.append(f"- {field}: {field_descriptions[field]}")
        
        if not field_prompts:
            return {}
        
        # Use shorter content for focused extraction
        content_to_use = markdown_content[:8000] if len(markdown_content) > 8000 else markdown_content
        if not content_to_use and html_content:
            # Extract text from HTML as fallback
            soup = BeautifulSoup(html_content, 'html.parser')
            for script in soup(["script", "style"]):
                script.decompose()
            content_to_use = soup.get_text()[:8000]
        
        prompt = f"""Extract the following missing information for this conference:

{chr(10).join(field_prompts)}

Current conference info:
- Name: {current_event.get('name', 'Unknown')}
- URL: {url}

Content to analyze:
{content_to_use}

Respond in JSON format with only the fields that you can find. If a field cannot be determined, omit it entirely.
For organizers/speakers/sponsors, provide as an array of strings.
For ticket_price, provide as a string (e.g., "Free", "$299", "Contact for pricing").

Example response:
{{
    "organizers": ["Tech Conference Inc", "AI Foundation"],
    "speakers": ["Dr. Jane Smith", "John Doe"],
    "ticket_price": "$199"
}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a data extraction specialist. Extract only the specific requested fields from conference content. Return valid JSON only."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=800
            )
            
            content = response.choices[0].message.content.strip()
            
            # Parse JSON response
            try:
                extracted_fields = json.loads(content)
                
                # Validate extracted fields
                validated_fields = {}
                for field, value in extracted_fields.items():
                    if field in missing_fields and value:
                        # Additional validation for specific field types
                        if field in ['organizers', 'speakers', 'sponsors'] and isinstance(value, list):
                            # Filter out empty strings and very short entries
                            clean_list = [str(item).strip() for item in value if len(str(item).strip()) > 2]
                            if clean_list:
                                validated_fields[field] = clean_list
                        elif field in ['ticket_price', 'venue'] and isinstance(value, str):
                            if len(value.strip()) > 2:
                                validated_fields[field] = value.strip()
                
                return validated_fields
                
            except json.JSONDecodeError as e:
                print(f"⚠️ Failed to parse fallback extraction JSON: {e}")
                return {}
            
        except Exception as e:
            print(f"⚠️ Fallback extraction API call failed: {e}")
            return {}

    def _validate_and_clean_extracted_data(self, extracted_data: Dict[str, Any], url: str) -> Dict[str, Any]:
        """
        Validate and clean the extracted data structure.
        
        Args:
            extracted_data: The extracted data from GPT
            url: The original URL of the conference
            
        Returns:
            Validated and cleaned extracted data
        """
        # Validate extracted data structure
        if not isinstance(extracted_data, dict):
            raise ValueError("Extracted data is not a valid JSON object")
        
        # Ensure core extracted fields are present (these should come from GPT)
        expected_fields = [
            'name', 'remote', 'city', 'short_description',
            'start_date', 'end_date', 'registration_deadline', 'themes', 
            'speakers', 'sponsors', 'ticket_price', 'is_paid', 'eligibility'
        ]
        
        for field in expected_fields:
            if field not in extracted_data:
                extracted_data[field] = None  # Set to None if missing rather than raising error
        
        # Validate list fields are actually lists
        list_fields = ['themes', 'speakers', 'sponsors']
        for field in list_fields:
            if extracted_data.get(field) is not None and not isinstance(extracted_data[field], list):
                # Try to convert strings to lists
                if isinstance(extracted_data[field], str):
                    extracted_data[field] = [item.strip() for item in extracted_data[field].split(',') if item.strip()]
                else:
                    extracted_data[field] = []
        
        # Validate boolean fields
        boolean_fields = ['remote', 'is_paid']
        for field in boolean_fields:
            if extracted_data.get(field) is not None:
                if isinstance(extracted_data[field], str):
                    extracted_data[field] = extracted_data[field].lower() in ['true', '1', 'yes']
                else:
                    extracted_data[field] = bool(extracted_data[field])
        
        # Ensure URL is set correctly
        extracted_data['url'] = url
        
        return extracted_data

def enrich_conference_data(raw_conferences: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Enrich conference data with detailed information from their pages.
    Enhanced with fallback enrichment for missing critical fields.
    
    Args:
        raw_conferences: List of raw conference dictionaries with basic info
        
    Returns:
        List of enriched conference dictionaries
    """
    from conference_fetcher.utils.firecrawl import FirecrawlFetcher
    
    # Access global test_mode from main module
    try:
        import conference_fetcher.conference_fetcher as main_module
        test_mode = getattr(main_module, 'test_mode', False)
    except Exception:
        test_mode = False
    
    if not raw_conferences:
        print("❌ No conferences to enrich!")
        return []
    
    print(f"🔍 Enriching {len(raw_conferences)} conferences with detailed data...")
    
    enriched_conferences = []
    successful_enrichments = 0
    fallback_enrichments = 0
    extractor = GPTExtractor()
    fetcher = FirecrawlFetcher()
    local_firecrawl_calls = 0
    
    # Limit enrichment to just 1 event for testing purposes if test mode is on
    limit = 1 if test_mode else len(raw_conferences)
    for i, conference in enumerate(raw_conferences[:limit], 1):
        # Skip enrichment if already enriched
        if conference.get("speakers") or conference.get("sponsors"):
            print(f"[⏩ Skip] Already enriched: {conference.get('name')}")
            enriched_conferences.append(conference)
            continue
            
        print(f"\n--- [{i}/{limit}] Enriching: {conference.get('name', 'Unknown')} ---")
        
        try:
            # Fetch content from the URL
            url = conference.get('url', '')
            if not url:
                print(f"❌ No URL provided for {conference.get('name', 'Unknown')}")
                enriched_conferences.append({
                    **conference,
                    'extraction_success': False,
                    'error': 'No URL provided'
                })
                continue
            
            print(f"🔗 Fetching content from: {url}")
            result = None
            markdown_content = ''
            
            # Try requests + BeautifulSoup first (free)
            try:
                print(f"🌐 Trying to scrape with requests...")
                response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
                html_content = response.text

                # Basic validation
                if "<html" not in html_content.lower() or "captcha" in html_content.lower() or "access denied" in html_content.lower():
                    raise Exception("Weak HTML or blocked")

                print("✅ Successfully scraped with requests")
                
                # Convert HTML to basic markdown using BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()
                
                # Get text content as simple markdown
                markdown_content = soup.get_text()
                
                # Create success response format compatible with Firecrawl
                result = {
                    'success': True,
                    'html': html_content,
                    'markdown': markdown_content,
                    'method': 'requests'
                }
                
            except Exception as e:
                print(f"⚠️ Requests failed: {e}")
                print(f"🔥 Falling back to Firecrawl...")
                
                try:
                    result = fetcher.scrape_url(url)
                    local_firecrawl_calls += 1
                    # Update global counter
                    try:
                        main_module.firecrawl_calls += 1
                    except Exception:
                        pass
                    print(f"✅ Firecrawl success")
                    result['method'] = 'firecrawl'
                except Exception as firecrawl_error:
                    print(f"❌ Firecrawl error: {firecrawl_error}")
                    result = {'success': False, 'error': str(firecrawl_error)}
            
            if not result['success']:
                print(f"❌ Failed to fetch content: {result.get('error', 'Unknown error')}")
                # Add basic data with error info
                enriched_conferences.append({
                    **conference,
                    'extraction_success': False,
                    'error': f"Failed to fetch content: {result.get('error', 'Unknown error')}"
                })
                continue
            
            # Extract structured data using GPT
            html_content = result.get('html', '')
            markdown_content = result.get('markdown', '')
            scraping_method = result.get('method', 'unknown')
            
            print(f"🤖 Running GPT extraction...")
            enriched_data = extractor.extract_conference_data(html_content, markdown_content, url)
            
            # Add scraping method to the result
            enriched_data['scraping_method'] = scraping_method
            
            # Merge with original data, giving preference to enriched data
            merged_conference = {
                **conference,  # Original data (name, url, source)
                **enriched_data,  # Enriched data from GPT
                'source': conference.get('source', 'unknown')  # Preserve original source
            }
            
            # Check if enrichment was successful
            if enriched_data.get('extraction_success'):
                print("✅ GPT extraction successful")
                
                # **NEW: Check for missing critical fields and attempt fallback enrichment**
                missing_critical_fields = []
                
                # Check for organizers  
                organizers = merged_conference.get('organizers', [])
                if not organizers or (isinstance(organizers, list) and len(organizers) == 0) or (isinstance(organizers, str) and not organizers.strip()):
                    missing_critical_fields.append('organizers')
                
                # Check for speakers
                speakers = merged_conference.get('speakers', [])
                if not speakers or (isinstance(speakers, list) and len(speakers) == 0) or (isinstance(speakers, str) and not speakers.strip()):
                    missing_critical_fields.append('speakers')
                
                # Check for sponsors
                sponsors = merged_conference.get('sponsors', [])
                if not sponsors or (isinstance(sponsors, list) and len(sponsors) == 0) or (isinstance(sponsors, str) and not sponsors.strip()):
                    missing_critical_fields.append('sponsors')
                
                # If we have missing critical fields, attempt fallback enrichment
                if missing_critical_fields:
                    print(f"🔄 Missing critical fields: {', '.join(missing_critical_fields)}. Attempting fallback enrichment...")
                    
                    try:
                        fallback_data = extractor.extract_missing_fields_fallback(
                            html_content, markdown_content, url, missing_critical_fields, merged_conference
                        )
                        
                        if fallback_data:
                            print(f"✅ Fallback enrichment successful for: {', '.join(fallback_data.keys())}")
                            # Merge fallback data
                            for field, value in fallback_data.items():
                                if value:  # Only update if we got meaningful data
                                    merged_conference[field] = value
                            fallback_enrichments += 1
                        else:
                            print("⚠️ Fallback enrichment found no additional data")
                            
                    except Exception as fallback_error:
                        print(f"⚠️ Fallback enrichment failed: {fallback_error}")
                
                successful_enrichments += 1
            else:
                print("❌ GPT extraction failed")
            
            # Ensure required fields are present
            required_fields = [
                'name', 'url', 'remote', 'city', 'short_description',
                'start_date', 'end_date', 'registration_deadline', 'themes', 
                'speakers', 'sponsors', 'ticket_price', 'is_paid', 'eligibility', 
                'extraction_success', 'extraction_method', 'source'
            ]
            
            for field in required_fields:
                if field not in merged_conference:
                    merged_conference[field] = None
            
            enriched_conferences.append(merged_conference)
            
            if merged_conference.get('extraction_success', False):
                print(f"✅ Successfully enriched: {merged_conference.get('name', 'Unknown')} [via {scraping_method}]")
            else:
                print(f"⚠️ Enrichment failed: {merged_conference.get('name', 'Unknown')} [via {scraping_method}]")
                
        except Exception as e:
            print(f"💥 Error enriching {conference.get('name', 'Unknown')}: {str(e)}")
            # Add the basic data with error info
            enriched_conferences.append({
                **conference,
                'extraction_success': False,
                'error': f"Enrichment error: {str(e)}"
            })
    
    # Add remaining non-enriched conferences if test mode limited the processing
    if test_mode and len(raw_conferences) > 1:
        for conference in raw_conferences[1:]:
            enriched_conferences.append({
                **conference,
                'extraction_success': False,
                'error': 'Skipped due to test mode limit (1 event only)'
            })
    
    print(f"\n🎯 Conference Enrichment Summary:")
    print(f"   • Total conferences processed: {len(raw_conferences)}")
    print(f"   • Successful enrichments: {successful_enrichments}")
    print(f"   • Fallback enrichments: {fallback_enrichments}")
    print(f"   • Failed enrichments: {len(raw_conferences) - successful_enrichments}")
    print(f"   • Success rate: {(successful_enrichments/len(raw_conferences)*100):.1f}%")
    print(f"   • Firecrawl calls made: {local_firecrawl_calls}" + (" (limited to 1 for testing)" if test_mode else ""))
    
    return enriched_conferences 