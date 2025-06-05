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
from urllib.parse import urlparse

# Load environment variables
load_dotenv()

def validate_date_string(date_str: str) -> Optional[str]:
    """
    Validate and normalize a date string to YYYY-MM-DD format.
    
    Args:
        date_str: Input date string in various formats
        
    Returns:
        Normalized date string in YYYY-MM-DD format or None if invalid
    """
    if not date_str or not isinstance(date_str, str):
        return None
    
    # Clean the input
    date_str = date_str.strip()
    
    # Check for invalid patterns first
    invalid_patterns = [
        r'^(unknown|tbd|n/a|none|null|empty)$',
        r'^invalid|error|fail',
        r'(coming soon|to be announced|stay tuned)'
    ]
    
    for pattern in invalid_patterns:
        if re.search(pattern, date_str.lower()):
            return None
    
    try:
        # Pattern 1: Already in YYYY-MM-DD format (ISO)
        iso_pattern = r'^(\d{4})-(\d{1,2})-(\d{1,2})$'
        iso_match = re.match(iso_pattern, date_str)
        if iso_match:
            year, month, day = map(int, iso_match.groups())
            # Validate ranges BEFORE attempting datetime creation
            if not (2025 <= year <= 2030 and 1 <= month <= 12 and 1 <= day <= 31):
                return None
            try:
                # Validate actual date
                datetime(year, month, day)
                return f"{year:04d}-{month:02d}-{day:02d}"
            except ValueError:
                return None
        
        # Pattern 2: MM/DD/YYYY or MM-DD-YYYY
        us_pattern = r'^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$'
        us_match = re.match(us_pattern, date_str)
        if us_match:
            month, day, year = map(int, us_match.groups())
            # Validate ranges BEFORE attempting datetime creation
            if not (2025 <= year <= 2030 and 1 <= month <= 12 and 1 <= day <= 31):
                return None
            try:
                datetime(year, month, day)
                return f"{year:04d}-{month:02d}-{day:02d}"
            except ValueError:
                return None
        
        # Pattern 3: Month DD, YYYY or Month DD YYYY
        month_day_year_pattern = r'^([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?\s*,?\s*(\d{4})$'
        month_match = re.match(month_day_year_pattern, date_str, re.IGNORECASE)
        if month_match:
            month_name, day, year = month_match.groups()
            day, year = int(day), int(year)
            
            # Convert month name to number
            month_map = {
                'january': 1, 'jan': 1, 'february': 2, 'feb': 2, 'march': 3, 'mar': 3,
                'april': 4, 'apr': 4, 'may': 5, 'june': 6, 'jun': 6,
                'july': 7, 'jul': 7, 'august': 8, 'aug': 8, 'september': 9, 'sep': 9, 'sept': 9,
                'october': 10, 'oct': 10, 'november': 11, 'nov': 11, 'december': 12, 'dec': 12
            }
            
            month_num = month_map.get(month_name.lower())
            if not month_num or not (2025 <= year <= 2030 and 1 <= day <= 31):
                return None
            try:
                datetime(year, month_num, day)
                return f"{year:04d}-{month_num:02d}-{day:02d}"
            except ValueError:
                return None
        
        # Pattern 4: YYYY Month DD or YYYY-Month-DD
        year_month_day_pattern = r'^(\d{4})\s*[-/]?\s*([a-z]+)\s*[-/]?\s*(\d{1,2})$'
        year_month_match = re.match(year_month_day_pattern, date_str, re.IGNORECASE)
        if year_month_match:
            year, month_name, day = year_month_match.groups()
            year, day = int(year), int(day)
            
            month_map = {
                'january': 1, 'jan': 1, 'february': 2, 'feb': 2, 'march': 3, 'mar': 3,
                'april': 4, 'apr': 4, 'may': 5, 'june': 6, 'jun': 6,
                'july': 7, 'jul': 7, 'august': 8, 'aug': 8, 'september': 9, 'sep': 9, 'sept': 9,
                'october': 10, 'oct': 10, 'november': 11, 'nov': 11, 'december': 12, 'dec': 12
            }
            
            month_num = month_map.get(month_name.lower())
            if not month_num or not (2025 <= year <= 2030 and 1 <= day <= 31):
                return None
            try:
                datetime(year, month_num, day)
                return f"{year:04d}-{month_num:02d}-{day:02d}"
            except ValueError:
                return None
        
        # If no pattern matches, return None
        return None
        
    except Exception as e:
        print(f"⚠️ Date validation error for '{date_str}': {e}")
        return None

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
    """Enhanced GPT-based extractor for structured conference data."""
    
    def __init__(self, dry_run: bool = False, log_enrichment_errors: bool = False):
        """
        Initialize the GPT extractor.
        
        Args:
            dry_run: If True, skip actual API calls and return mock data
            log_enrichment_errors: If True, log detailed error information
        """
        load_dotenv()
        self.dry_run = dry_run
        self.log_enrichment_errors = log_enrichment_errors
        
        if not dry_run:
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable is required")
            self.client = OpenAI(api_key=api_key)
        else:
            self.client = None
            print("🏃‍♂️ GPT Extractor running in DRY RUN mode - no API calls will be made")
        
        # Track enrichment statistics
        self.enrichment_stats = {
            'total_processed': 0,
            'successful_extractions': 0,
            'failed_extractions': 0,
            'errors': []
        }
    
    def extract_conference_data(self, html_content: str, markdown_content: str, url: str) -> Dict[str, Any]:
        """
        Extract structured conference data from HTML/markdown content using GPT.
        
        Args:
            html_content: Raw HTML content
            markdown_content: Markdown content from Firecrawl
            url: Original URL of the conference
            
        Returns:
            Dictionary with extracted conference data
        """
        # Track processing
        self.enrichment_stats['total_processed'] += 1
        
        # Handle dry run mode
        if self.dry_run:
            print(f"🏃‍♂️ DRY RUN: Skipping GPT extraction for {url}")
            return {
                'extraction_success': True,
                'url': url,
                'name': f"[DRY RUN] Conference from {urlparse(url).netloc}",
                'extraction_method': 'dry-run',
                'dry_run': True,
                'remote': True,
                'city': 'Virtual',
                'short_description': 'Dry run mode - no actual extraction performed',
                'start_date': '2025-06-15',
                'end_date': '2025-06-16',
                'registration_deadline': None,
                'speakers': [],
                'sponsors': [],
                'ticket_price': [],
                'is_paid': False,
                'themes': ['Technology'],
                'eligibility': 'All'
            }
        
        # If OpenAI client failed to initialize, return basic data without enrichment
        if self.client is None:
            error_msg = "OpenAI client not available - GPT enrichment disabled"
            if self.log_enrichment_errors:
                self.enrichment_stats['errors'].append({
                    'url': url,
                    'error': error_msg,
                    'timestamp': datetime.now().isoformat()
                })
            self.enrichment_stats['failed_extractions'] += 1
            return {
                'extraction_success': False,
                'url': url,
                'error': error_msg,
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
                model="gpt-4o-mini",
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
                
                # **FIX: Handle case where GPT returns a list instead of a dictionary**
                if isinstance(extracted_data, list):
                    if len(extracted_data) > 0 and isinstance(extracted_data[0], dict):
                        # Take the first element if it's a list of dictionaries
                        extracted_data = extracted_data[0]
                        print(f"⚠️ GPT returned a list, using first element for {url}")
                    else:
                        # Create a minimal dictionary if list doesn't contain valid data
                        error_msg = "GPT returned invalid list format"
                        if self.log_enrichment_errors:
                            self.enrichment_stats['errors'].append({
                                'url': url,
                                'error': error_msg,
                                'raw_response': result_text[:500],
                                'timestamp': datetime.now().isoformat()
                            })
                        self.enrichment_stats['failed_extractions'] += 1
                        print(f"❌ GPT returned invalid list format for {url}")
                        return {
                            'extraction_success': False,
                            'url': url,
                            'error': error_msg,
                            'extraction_method': 'gpt-list-error',
                            'raw_response': result_text[:500]
                        }
                elif not isinstance(extracted_data, dict):
                    # Handle case where it's neither list nor dict
                    error_msg = f"GPT returned unexpected data type: {type(extracted_data)}"
                    if self.log_enrichment_errors:
                        self.enrichment_stats['errors'].append({
                            'url': url,
                            'error': error_msg,
                            'raw_response': result_text[:500],
                            'timestamp': datetime.now().isoformat()
                        })
                    self.enrichment_stats['failed_extractions'] += 1
                    print(f"❌ GPT returned unexpected data type for {url}: {type(extracted_data)}")
                    return {
                        'extraction_success': False,
                        'url': url,
                        'error': error_msg,
                        'extraction_method': 'gpt-type-error',
                        'raw_response': result_text[:500]
                    }
                
            except json.JSONDecodeError as e:
                error_msg = f"JSON parsing failed: {e}"
                if self.log_enrichment_errors:
                    self.enrichment_stats['errors'].append({
                        'url': url,
                        'error': error_msg,
                        'raw_response': result_text[:500],
                        'timestamp': datetime.now().isoformat()
                    })
                self.enrichment_stats['failed_extractions'] += 1
                print(f"❌ Failed to parse GPT JSON response: {e}")
                return {
                    'extraction_success': False,
                    'url': url,
                    'error': error_msg,
                    'extraction_method': 'gpt-json-error',
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
                self.enrichment_stats['successful_extractions'] += 1
                print(f"✅ GPT extraction successful for: {validated_data.get('name')}")
            else:
                self.enrichment_stats['failed_extractions'] += 1
                error_msg = "Missing basic conference information"
                if self.log_enrichment_errors:
                    self.enrichment_stats['errors'].append({
                        'url': url,
                        'error': error_msg,
                        'extracted_data': validated_data,
                        'timestamp': datetime.now().isoformat()
                    })
                print(f"⚠️ GPT extraction incomplete - missing basic info")
                validated_data['error'] = error_msg
            
            return validated_data
            
        except Exception as e:
            error_msg = f"GPT API call failed: {e}"
            if self.log_enrichment_errors:
                self.enrichment_stats['errors'].append({
                    'url': url,
                    'error': error_msg,
                    'timestamp': datetime.now().isoformat()
                })
            print(f"❌ {error_msg}")
            
            # **IMPROVEMENT: Try fallback extraction with basic parsing**
            try:
                fallback_data = self.extract_with_fallback(html_content, markdown_content, url)
                # Even if fallback fails, still log the event with basic URL info
                if not fallback_data.get('extraction_success'):
                    self.enrichment_stats['failed_extractions'] += 1
                    fallback_data = {
                        'name': f"Conference at {url.split('/')[-2] if '/' in url else url}",
                        'url': url,
                        'extraction_success': False,
                        'extraction_method': 'minimal-fallback',
                        'error': error_msg,
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
                else:
                    self.enrichment_stats['successful_extractions'] += 1
                return fallback_data
            except Exception as fallback_error:
                fallback_error_msg = f"Both GPT and fallback failed: {e}"
                if self.log_enrichment_errors:
                    self.enrichment_stats['errors'].append({
                        'url': url,
                        'error': fallback_error_msg,
                        'fallback_error': str(fallback_error),
                        'timestamp': datetime.now().isoformat()
                    })
                print(f"❌ Fallback extraction also failed: {fallback_error}")
                self.enrichment_stats['failed_extractions'] += 1
                
                # **IMPROVEMENT: Always return basic data to preserve the event**
                return {
                    'name': f"Conference at {url.split('/')[-2] if '/' in url else 'Unknown Site'}",
                    'url': url,
                    'extraction_success': False,
                    'extraction_method': 'error-fallback',
                    'error': fallback_error_msg,
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
    
    def get_enrichment_stats(self) -> Dict[str, Any]:
        """Get enrichment statistics and errors."""
        return self.enrichment_stats.copy()

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
        Extract conference data with multiple fallback strategies.
        Enhanced with better retry logic and alternative methods.
        
        Args:
            html_content: Raw HTML content
            markdown_content: Markdown content from Firecrawl
            url: URL of the conference
            basic_details: Optional basic details to merge with extracted data
            
        Returns:
            Dictionary with extracted conference data
        """
        print(f"🔄 Starting enhanced extraction with fallbacks for: {url}")
        
        # Track attempted methods
        attempted_methods = []
        
        # Method 1: Primary GPT extraction
        try:
            print("🤖 Attempting primary GPT extraction...")
            result = self.extract_conference_data(html_content, markdown_content, url)
            attempted_methods.append("primary_gpt")
            
            if result.get('extraction_success'):
                print("✅ Primary GPT extraction successful")
                return result
            else:
                print("⚠️ Primary GPT extraction failed, trying fallbacks...")
                
        except Exception as e:
            print(f"❌ Primary GPT extraction error: {e}")
            attempted_methods.append("primary_gpt_failed")
        
        # Method 2: Simplified content extraction
        try:
            print("🔄 Attempting simplified content extraction...")
            simplified_result = self._extract_with_simplified_content(html_content, markdown_content, url)
            attempted_methods.append("simplified_content")
            
            if simplified_result.get('extraction_success'):
                print("✅ Simplified content extraction successful")
                return simplified_result
            else:
                print("⚠️ Simplified content extraction failed, trying basic extraction...")
                
        except Exception as e:
            print(f"❌ Simplified content extraction error: {e}")
            attempted_methods.append("simplified_content_failed")
        
        # Method 3: Basic HTML parsing fallback
        try:
            print("🔄 Attempting basic HTML parsing...")
            basic_result = self._extract_with_basic_parsing(html_content, url)
            attempted_methods.append("basic_parsing")
            
            if basic_result.get('extraction_success'):
                print("✅ Basic HTML parsing successful")
                return basic_result
            else:
                print("⚠️ Basic HTML parsing failed...")
                
        except Exception as e:
            print(f"❌ Basic HTML parsing error: {e}")
            attempted_methods.append("basic_parsing_failed")
        
        # Method 4: Minimal data extraction (last resort)
        print("🔄 Using minimal data extraction as last resort...")
        attempted_methods.append("minimal_fallback")
        
        minimal_result = self._create_minimal_conference_data(url, basic_details)
        minimal_result['attempted_methods'] = attempted_methods
        
        return minimal_result
    
    def _extract_with_simplified_content(self, html_content: str, markdown_content: str, url: str) -> Dict[str, Any]:
        """
        Extract using simplified content and more focused prompts.
        
        Args:
            html_content: Raw HTML content
            markdown_content: Markdown content
            url: Conference URL
            
        Returns:
            Extracted conference data
        """
        if self.client is None:
            return {
                'extraction_success': False,
                'url': url,
                'error': "OpenAI client not available",
                'extraction_method': 'simplified-no-client'
            }
        
        # Use shorter, more focused content
        content_to_use = markdown_content[:5000] if markdown_content else ""
        
        if not content_to_use and html_content:
            # Extract text from HTML
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            for script in soup(["script", "style"]):
                script.decompose()
            content_to_use = soup.get_text()[:5000]
        
        if not content_to_use:
            return {
                'extraction_success': False,
                'url': url,
                'error': "No content available for extraction",
                'extraction_method': 'simplified-no-content'
            }
        
        # Create simplified prompt focused on key information
        simplified_prompt = f"""
Extract basic conference information from this webpage content. Return ONLY a JSON object.

URL: {url}
CONTENT: {content_to_use}

Extract only what you can clearly identify:
{{
    "name": "Conference name (required)",
    "start_date": "Start date in YYYY-MM-DD format or null",
    "city": "City name or null if remote",
    "remote": true/false,
    "short_description": "Brief description if available",
    "speakers": ["speaker names if clearly mentioned"],
    "is_paid": true/false/null
}}

If you cannot determine a field, set it to null. Focus on accuracy over completeness.
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": simplified_prompt}],
                max_tokens=800,
                temperature=0.1
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Clean the response
            if result_text.startswith('```json'):
                result_text = result_text[7:]
            if result_text.endswith('```'):
                result_text = result_text[:-3]
            result_text = result_text.strip()
            
            # Parse JSON
            extracted_data = json.loads(result_text)
            
            # **FIX: Handle case where GPT returns a list instead of a dictionary**
            if isinstance(extracted_data, list):
                if len(extracted_data) > 0 and isinstance(extracted_data[0], dict):
                    # Take the first element if it's a list of dictionaries
                    extracted_data = extracted_data[0]
                    print(f"⚠️ GPT returned a list in simplified extraction, using first element for {url}")
                else:
                    # Return error if list doesn't contain valid data
                    return {
                        'extraction_success': False,
                        'url': url,
                        'error': "GPT returned invalid list format in simplified extraction",
                        'extraction_method': 'simplified-list-error',
                        'raw_response': result_text[:200]
                    }
            elif not isinstance(extracted_data, dict):
                # Handle case where it's neither list nor dict
                return {
                    'extraction_success': False,
                    'url': url,
                    'error': f"GPT returned unexpected data type in simplified extraction: {type(extracted_data)}",
                    'extraction_method': 'simplified-type-error',
                    'raw_response': result_text[:200]
                }
            
            # Validate basic requirements
            if not extracted_data.get('name') or len(str(extracted_data.get('name', '')).strip()) < 3:
                return {
                    'extraction_success': False,
                    'url': url,
                    'error': "No valid conference name extracted",
                    'extraction_method': 'simplified-invalid-name'
                }
            
            # Fill in missing fields with defaults
            default_fields = {
                'url': url,
                'remote': None,
                'city': None,
                'short_description': None,
                'start_date': None,
                'end_date': None,
                'registration_deadline': None,
                'speakers': [],
                'sponsors': [],
                'ticket_price': None,
                'is_paid': None,
                'themes': [],
                'eligibility': None,
                'extraction_success': True,
                'extraction_method': 'simplified-gpt'
            }
            
            for field, default_value in default_fields.items():
                if field not in extracted_data:
                    extracted_data[field] = default_value
            
            return extracted_data
            
        except json.JSONDecodeError as e:
            return {
                'extraction_success': False,
                'url': url,
                'error': f"Simplified JSON parsing failed: {e}",
                'extraction_method': 'simplified-json-error',
                'raw_response': result_text[:200] if 'result_text' in locals() else "No response"
            }
        except Exception as e:
            return {
                'extraction_success': False,
                'url': url,
                'error': f"Simplified extraction failed: {e}",
                'extraction_method': 'simplified-error'
            }
    
    def _extract_with_basic_parsing(self, html_content: str, url: str) -> Dict[str, Any]:
        """
        Extract using basic HTML parsing without GPT.
        Enhanced with better content extraction and validation.
        
        Args:
            html_content: Raw HTML content
            url: Conference URL
            
        Returns:
            Basic conference data extracted from HTML
        """
        try:
            from bs4 import BeautifulSoup
            import re
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove script and style tags for cleaner text
            for script in soup(["script", "style", "nav", "footer"]):
                script.decompose()
            
            # Extract title with multiple fallback strategies
            title = None
            title_sources = [
                # Primary sources
                soup.find('h1'),
                soup.find('title'),
                soup.find('meta', {'property': 'og:title'}),
                soup.find('meta', {'name': 'twitter:title'}),
                # Fallback sources
                soup.find('h2'),
                soup.find('h3'),
                soup.find('meta', {'name': 'title'})
            ]
            
            for source in title_sources:
                if source:
                    if source.name == 'meta':
                        title = source.get('content', '').strip()
                    else:
                        title = source.get_text().strip()
                    
                    # Validate title quality
                    if title and len(title) > 3 and title.lower() not in ['home', 'page', 'site']:
                        # Clean up common title suffixes
                        title = re.sub(r'\s*[-|]\s*(home|homepage|site|website).*$', '', title, flags=re.I)
                        title = re.sub(r'\s+', ' ', title).strip()
                        if len(title) > 3:
                            break
            
            if not title:
                return {
                    'extraction_success': False,
                    'url': url,
                    'error': "No meaningful title found in HTML",
                    'extraction_method': 'basic-parsing-no-title'
                }
            
            # Extract description with multiple strategies
            description = None
            desc_sources = [
                soup.find('meta', {'name': 'description'}),
                soup.find('meta', {'property': 'og:description'}),
                soup.find('meta', {'name': 'twitter:description'}),
                soup.find('meta', {'name': 'summary'})
            ]
            
            for source in desc_sources:
                if source:
                    desc = source.get('content', '').strip()
                    if desc and len(desc) > 20:
                        description = desc
                        break
            
            # If no meta description, try to extract from content
            if not description:
                # Look for intro paragraphs or summary sections
                for selector in ['p.intro', 'p.summary', '.description', '.about', 'p:first-of-type']:
                    desc_elem = soup.select_one(selector)
                    if desc_elem:
                        desc = desc_elem.get_text().strip()
                        if len(desc) > 30 and len(desc) < 500:
                            description = desc
                            break
            
            # Extract additional information from structured data
            text_content = soup.get_text().lower()
            
            # Detect if event is remote/virtual
            remote_indicators = [
                'virtual', 'online', 'remote', 'webinar', 'zoom', 'teams',
                'digital event', 'online conference', 'virtual summit'
            ]
            is_remote = any(indicator in text_content for indicator in remote_indicators)
            
            # Extract location information
            city = None
            if not is_remote:
                # Look for location patterns
                location_patterns = [
                    r'(?:in|at|@)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),?\s*([A-Z][A-Z]|California|New York|Texas)',
                    r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*(CA|NY|TX|USA|United States)',
                    r'Location:?\s*([A-Z][a-z]+(?:(?:\s+[A-Z][a-z]+)*)?)'
                ]
                
                for pattern in location_patterns:
                    matches = re.findall(pattern, text_content, re.I)
                    if matches:
                        if isinstance(matches[0], tuple):
                            city = matches[0][0].strip()
                        else:
                            city = matches[0].strip()
                        if len(city) > 2:
                            break
            
            # Extract date information
            start_date = None
            current_year = datetime.now().year
            
            # Date patterns for 2024/2025
            date_patterns = [
                r'(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:st|nd|rd|th)?,?\s*(?:2024|2025)',
                r'\d{1,2}[/-]\d{1,2}[/-](?:2024|2025)',
                r'(?:2024|2025)[/-]\d{1,2}[/-]\d{1,2}'
            ]
            
            for pattern in date_patterns:
                date_matches = re.findall(pattern, text_content, re.I)
                if date_matches:
                    try:
                        # Try to parse the first reasonable looking date
                        date_str = date_matches[0]
                        # Basic date normalization would go here
                        if '2024' in date_str or '2025' in date_str:
                            start_date = date_str
                            break
                    except:
                        continue
            
            # Extract speakers (basic)
            speakers = []
            speaker_patterns = [
                r'speaker[s]?:?\s*([A-Z][a-z]+\s+[A-Z][a-z]+)',
                r'keynote:?\s*([A-Z][a-z]+\s+[A-Z][a-z]+)',
                r'presented? by:?\s*([A-Z][a-z]+\s+[A-Z][a-z]+)'
            ]
            
            for pattern in speaker_patterns:
                speaker_matches = re.findall(pattern, text_content, re.I)
                speakers.extend([match.strip() for match in speaker_matches if len(match.strip()) > 3])
            
            # Remove duplicates
            speakers = list(set(speakers))[:5]  # Limit to 5 speakers
            
            # Detect if paid
            is_paid = None
            if any(word in text_content for word in ['free', 'no cost', 'complimentary']):
                is_paid = False
            elif any(word in text_content for word in ['$', 'price', 'cost', 'fee', 'ticket', 'registration fee']):
                is_paid = True
            
            # Create conference data with quality validation
            conference_data = {
                'name': title,
                'url': url,
                'short_description': description or 'Event information extracted from webpage',
                'remote': is_remote,
                'city': city,
                'start_date': start_date,
                'end_date': None,
                'registration_deadline': None,
                'speakers': speakers,
                'sponsors': [],
                'ticket_price': None,
                'is_paid': is_paid,
                'themes': [],
                'eligibility': None,
                'extraction_success': True,
                'extraction_method': 'basic-html-parsing'
            }
            
            # Apply quality validation
            validated_data = self._validate_and_clean_extracted_data(conference_data, url)
            
            print(f"✅ Basic HTML parsing successful: {title[:50]}...")
            return validated_data
            
        except Exception as e:
            return {
                'extraction_success': False,
                'url': url,
                'error': f"Basic HTML parsing failed: {str(e)}",
                'extraction_method': 'basic-parsing-error'
            }
    
    def _create_minimal_conference_data(self, url: str, basic_details: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Create minimal conference data as absolute last resort.
        Enhanced with better name generation and URL analysis.
        
        Args:
            url: Conference URL
            basic_details: Optional basic details to merge
            
        Returns:
            Minimal conference data structure
        """
        from urllib.parse import urlparse
        
        # Try to generate a reasonable name from URL
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        path = parsed.path.lower()
        
        # Generate name from domain and path
        name = None
        
        # Check if domain suggests conference content
        if 'conf' in domain or 'event' in domain or 'summit' in domain:
            # Extract meaningful part from domain
            domain_parts = domain.replace('www.', '').split('.')
            main_part = domain_parts[0]
            if len(main_part) > 3:
                name = f"{main_part.title()} Conference"
        
        # Try to extract from path
        if not name and path:
            path_parts = [p for p in path.split('/') if p and len(p) > 2]
            if path_parts:
                # Look for conference-related path segments
                conf_paths = [p for p in path_parts if any(keyword in p for keyword in ['conf', 'event', 'summit', '2024', '2025'])]
                if conf_paths:
                    name = conf_paths[0].replace('-', ' ').replace('_', ' ').title()
                    if not any(word in name.lower() for word in ['conference', 'event', 'summit']):
                        name += " Conference"
        
        # Fallback name generation
        if not name:
            domain_clean = domain.replace('www.', '').split('.')[0]
            name = f"Conference at {domain_clean.title()}"
        
        minimal_data = {
            'name': name,
            'url': url,
            'short_description': 'Conference details could not be automatically extracted. Please check the website for more information.',
            'remote': None,
            'city': None,
            'start_date': None,
            'end_date': None,
            'registration_deadline': None,
            'speakers': [],
            'sponsors': [],
            'ticket_price': None,
            'is_paid': None,
            'themes': [],
            'eligibility': None,
            'extraction_success': False,  # Mark as failed since this is minimal
            'extraction_method': 'minimal-fallback',
            'error': 'All extraction methods failed, created minimal data',
            'quality_score': 0.1,  # Very low quality
            'quality_flags': ['minimal_fallback', 'very_low_quality']
        }
        
        # Merge any available basic details
        if basic_details:
            for key, value in basic_details.items():
                if value is not None and key in minimal_data:
                    minimal_data[key] = value
                    if key in ['name', 'description', 'city']:
                        minimal_data['quality_score'] += 0.05
        
        return minimal_data

    def extract_missing_fields_fallback(self, html_content: str, markdown_content: str, 
                                       url: str, missing_fields: List[str], 
                                       current_event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Attempt to extract specific missing fields using improved focused GPT prompts.
        Enhanced with better field descriptions and format requirements.
        
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
        
        # **ENHANCED: Improved field descriptions with format requirements**
        field_descriptions = {
            'name': 'the title/name of this conference or event',
            'city': 'the location/city where this conference takes place (must be San Francisco/Bay Area, NYC, or null if remote)',
            'start_date': 'the start date of this conference in YYYY-MM-DD format (must be 2025 or later)',
            'end_date': 'the end date of this conference in YYYY-MM-DD format (must be 2025 or later)',
            'organizers': 'the companies, organizations, or people organizing this conference',
            'sponsors': 'companies or organizations sponsoring this conference',
            'speakers': 'speakers, presenters, or keynote speakers at this conference with their details',
            'venue': 'the venue, location, or address where this conference takes place',
            'ticket_price': 'the cost, price, or fee to attend this conference',
            'themes': 'the topics, tracks, or subject areas covered by this conference',
            'registration_deadline': 'the deadline to register for this conference in YYYY-MM-DD format'
        }
        
        # **NEW: Create formatted field request list as specified**
        requested_fields = []
        field_mapping = {
            'name': 'title',
            'city': 'location', 
            'start_date': 'start date',
            'end_date': 'end date',
            'organizers': 'organizers',
            'sponsors': 'sponsors', 
            'speakers': 'speakers'
        }
        
        # Build the requested fields string in the specified format
        formatted_fields = []
        for field in missing_fields:
            if field in field_descriptions:
                display_name = field_mapping.get(field, field)
                formatted_fields.append(display_name)
                requested_fields.append(f"- {field}: {field_descriptions[field]}")
        
        if not requested_fields:
            return {}
        
        # Create the formatted request string
        fields_request = ", ".join(formatted_fields)
        
        # Use shorter content for focused extraction
        content_to_use = markdown_content[:8000] if len(markdown_content) > 8000 else markdown_content
        if not content_to_use and html_content:
            # Extract text from HTML as fallback
            soup = BeautifulSoup(html_content, 'html.parser')
            for script in soup(["script", "style"]):
                script.decompose()
            content_to_use = soup.get_text()[:8000]
        
        # **ENHANCED: Improved prompt with better format specification and validation**
        prompt = f"""I need you to extract the following missing information for this conference: {fields_request}

🎯 REQUIRED FIELDS TO FIND:
{chr(10).join(requested_fields)}

📋 CURRENT CONFERENCE INFO:
- Name: {current_event.get('name', 'Unknown')}
- URL: {url}

🔍 CONTENT TO ANALYZE:
{content_to_use}

📝 RESPONSE FORMAT REQUIREMENTS:
- Return ONLY valid JSON with the fields you can find
- If a field cannot be determined from the content, omit it entirely
- Use null for missing information - DO NOT GUESS

📅 DATE FORMAT REQUIREMENTS:
- All dates must be in YYYY-MM-DD format (e.g., "2025-07-14")
- Only extract dates for events in 2025 or later
- Pre-validate dates before including them

🏗️ STRUCTURED DATA FORMATS:
- organizers: ["Company Name", "Organization Name"] (array of strings)
- speakers: [{{"name": "Full Name", "company": "Company", "title": "Job Title"}}] (array of objects)
- sponsors: ["Sponsor 1", "Sponsor 2"] (array of strings)  
- themes: ["Theme 1", "Theme 2"] (array of strings)
- ticket_price: [{{"label": "Early Bird", "price": "$99"}}] (array of pricing objects)
- city: "San Francisco" or "New York" or null (must be SF/Bay Area, NYC, or null)
- venue: "Venue Name or Address" (string)

🎯 QUALITY REQUIREMENTS:
- Only extract information that is clearly visible in the content
- For speaker objects, include name, company, and title when available
- For pricing, extract different tiers if available
- Validate all dates using the validate_date_string criteria

✅ EXAMPLE VALID RESPONSE:
{{
    "organizers": ["Tech Conference Inc", "AI Foundation"],
    "speakers": [
        {{"name": "Dr. Jane Smith", "company": "Google", "title": "AI Research Director"}},
        {{"name": "John Doe", "company": "Meta", "title": "VP Engineering"}}
    ],
    "sponsors": ["Microsoft", "OpenAI"],
    "start_date": "2025-07-14",
    "end_date": "2025-07-16",
    "themes": ["Artificial Intelligence", "Machine Learning"]
}}

⚠️ IMPORTANT: 
- Do not include any explanatory text, only the JSON response
- Pre-validate all dates to ensure they are in correct YYYY-MM-DD format
- Only include information that is explicitly mentioned in the content"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a specialized data extraction expert. Extract only the specifically requested fields from conference content. Always pre-validate dates and return only valid JSON."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1000  # Increased token limit for better extraction
            )
            
            content = response.choices[0].message.content.strip()
            
            # Clean up response formatting
            if content.startswith('```json'):
                content = content[7:]
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()
            
            # Parse JSON response
            try:
                extracted_fields = json.loads(content)
                
                # **FIX: Handle case where GPT returns a list instead of a dictionary**
                if isinstance(extracted_fields, list):
                    if len(extracted_fields) > 0 and isinstance(extracted_fields[0], dict):
                        # Take the first element if it's a list of dictionaries
                        extracted_fields = extracted_fields[0]
                        print(f"⚠️ GPT returned a list in fallback extraction, using first element for {url}")
                    else:
                        # Return empty dict if list doesn't contain valid data
                        print(f"⚠️ GPT returned invalid list format in fallback extraction for {url}")
                        return {}
                elif not isinstance(extracted_fields, dict):
                    # Return empty dict if it's neither list nor dict
                    print(f"⚠️ GPT returned unexpected data type in fallback extraction for {url}: {type(extracted_fields)}")
                    return {}
                
                # **ENHANCED: Validate extracted fields with improved validation**
                validated_fields = {}
                for field, value in extracted_fields.items():
                    if field in missing_fields and value:
                        # **NEW: Enhanced validation for specific field types**
                        if field in ['start_date', 'end_date', 'registration_deadline']:
                            # Use the new date validation function
                            validated_date = validate_date_string(str(value))
                            if validated_date:
                                validated_fields[field] = validated_date
                                print(f"✅ Validated {field}: {validated_date}")
                            else:
                                print(f"⚠️ Invalid date for {field}: {value}")
                        
                        elif field in ['organizers', 'sponsors', 'themes'] and isinstance(value, list):
                            # Filter out empty strings and very short entries
                            clean_list = [str(item).strip() for item in value if len(str(item).strip()) > 2]
                            if clean_list:
                                validated_fields[field] = clean_list
                        
                        elif field == 'speakers' and isinstance(value, list):
                            # Validate speaker objects
                            valid_speakers = []
                            for speaker in value:
                                if isinstance(speaker, dict) and speaker.get('name'):
                                    if len(str(speaker['name']).strip()) > 2:
                                        valid_speakers.append({
                                            'name': str(speaker['name']).strip(),
                                            'company': str(speaker.get('company', '')).strip(),
                                            'title': str(speaker.get('title', '')).strip()
                                        })
                            if valid_speakers:
                                validated_fields[field] = valid_speakers
                        
                        elif field == 'ticket_price' and isinstance(value, list):
                            # Validate pricing objects
                            valid_prices = []
                            for price in value:
                                if isinstance(price, dict) and price.get('label') and price.get('price'):
                                    valid_prices.append({
                                        'label': str(price['label']).strip(),
                                        'price': str(price['price']).strip()
                                    })
                            if valid_prices:
                                validated_fields[field] = valid_prices
                        
                        elif field in ['name', 'city', 'venue'] and isinstance(value, str):
                            clean_value = value.strip()
                            if len(clean_value) > 2 and clean_value.lower() not in ['unknown', 'tbd', 'n/a']:
                                # **NEW: Special validation for city field**
                                if field == 'city':
                                    # Validate city is in allowed locations
                                    allowed_cities = [
                                        'san francisco', 'sf', 'bay area', 'silicon valley', 
                                        'palo alto', 'mountain view', 'santa clara', 'san jose',
                                        'new york', 'ny', 'nyc', 'manhattan', 'brooklyn'
                                    ]
                                    if any(city in clean_value.lower() for city in allowed_cities):
                                        # Normalize city names
                                        if any(sf in clean_value.lower() for sf in ['san francisco', 'sf', 'bay area', 'silicon valley']):
                                            validated_fields[field] = 'San Francisco'
                                        elif any(ny in clean_value.lower() for ny in ['new york', 'ny', 'nyc', 'manhattan']):
                                            validated_fields[field] = 'New York'
                                        else:
                                            validated_fields[field] = clean_value
                                else:
                                    validated_fields[field] = clean_value
                
                if validated_fields:
                    print(f"✅ Successfully extracted {len(validated_fields)} missing fields: {list(validated_fields.keys())}")
                else:
                    print("⚠️ No valid fields could be extracted from fallback attempt")
                
                return validated_fields
                
            except json.JSONDecodeError as e:
                print(f"⚠️ Failed to parse fallback extraction JSON: {e}")
                print(f"Raw response: {content[:200]}...")
                return {}
            
        except Exception as e:
            print(f"⚠️ Fallback extraction API call failed: {e}")
            return {}

    def _validate_and_clean_extracted_data(self, extracted_data: Dict[str, Any], url: str) -> Dict[str, Any]:
        """
        Enhanced validation and cleaning of extracted data with quality scoring.
        
        Args:
            extracted_data: Raw extracted data from GPT
            url: Original URL for context
            
        Returns:
            Cleaned and validated data with quality indicators
        """
        # Initialize quality scoring
        quality_score = 0.0
        quality_flags = []
        
        # Clean and validate name
        name = str(extracted_data.get('name', '')).strip()
        if name and name.lower() not in ['unknown', 'n/a', 'tbd', 'none', '']:
            # Check for quality name indicators
            if len(name) >= 10 and any(word in name.lower() for word in ['conference', 'summit', 'symposium', 'expo', 'workshop']):
                quality_score += 0.3
                quality_flags.append('meaningful_name')
            elif len(name) >= 5:
                quality_score += 0.1
                quality_flags.append('basic_name')
            
            # Penalize spammy names
            spam_patterns = [
                r'^[A-Z\s]+$',  # All caps
                r'click here', r'register now', r'free trial',
                r'^\d+\s*[-.]?\s*\d*$',  # Just numbers
                r'^(conference|event|summit)\s*$'  # Just generic words
            ]
            
            if any(re.search(pattern, name, re.I) for pattern in spam_patterns):
                quality_score -= 0.2
                quality_flags.append('spammy_name')
        else:
            name = f"Event at {urlparse(url).netloc}"
            quality_flags.append('auto_generated_name')
        
        extracted_data['name'] = name
        
        # Validate and score description quality
        description = str(extracted_data.get('short_description', '')).strip()
        if description and description.lower() not in ['unknown', 'n/a', 'tbd', 'none', '']:
            if len(description) >= 50:
                quality_score += 0.2
                quality_flags.append('detailed_description')
            elif len(description) >= 20:
                quality_score += 0.1
                quality_flags.append('basic_description')
            
            # Check for meaningful content
            meaningful_words = ['conference', 'speakers', 'presentations', 'networking', 'sessions', 'learn', 'discuss', 'industry', 'technology']
            if sum(1 for word in meaningful_words if word in description.lower()) >= 2:
                quality_score += 0.1
                quality_flags.append('meaningful_content')
        
        # Validate date information with enhanced pre-validation
        start_date = extracted_data.get('start_date')
        end_date = extracted_data.get('end_date')
        registration_deadline = extracted_data.get('registration_deadline')
        
        # **NEW: Pre-validate all date strings to prevent Invalid Date errors**
        if start_date:
            validated_start = validate_date_string(str(start_date))
            if validated_start:
                extracted_data['start_date'] = validated_start
                # Validate it's a future date
                try:
                    parsed_date = datetime.strptime(validated_start, '%Y-%m-%d').date()
                    if parsed_date >= datetime.now().date():
                        quality_score += 0.2
                        quality_flags.append('future_date')
                    else:
                        quality_score += 0.05
                        quality_flags.append('past_date')
                except ValueError:
                    # This shouldn't happen with pre-validation, but safety check
                    extracted_data['start_date'] = None
                    quality_flags.append('date_validation_failed')
            else:
                extracted_data['start_date'] = None
                quality_flags.append('invalid_start_date')
        
        if end_date:
            validated_end = validate_date_string(str(end_date))
            if validated_end:
                extracted_data['end_date'] = validated_end
                quality_score += 0.1
                quality_flags.append('has_end_date')
            else:
                extracted_data['end_date'] = None
                quality_flags.append('invalid_end_date')
        
        if registration_deadline:
            validated_deadline = validate_date_string(str(registration_deadline))
            if validated_deadline:
                extracted_data['registration_deadline'] = validated_deadline
                quality_score += 0.05
                quality_flags.append('has_deadline')
            else:
                extracted_data['registration_deadline'] = None
                quality_flags.append('invalid_deadline')
        
        # Validate location information
        city = extracted_data.get('city')
        remote = extracted_data.get('remote')
        
        if remote is True:
            quality_score += 0.1
            quality_flags.append('remote_event')
        elif city and city.lower() not in ['unknown', 'tbd', 'n/a', 'none']:
            quality_score += 0.15
            quality_flags.append('has_location')
        
        # Validate speakers
        speakers = extracted_data.get('speakers', [])
        if speakers and len(speakers) > 0:
            # Filter out generic speaker entries
            valid_speakers = [s for s in speakers if s and len(str(s).strip()) > 3 and str(s).lower() not in ['tbd', 'unknown', 'n/a']]
            if valid_speakers:
                quality_score += min(0.15, len(valid_speakers) * 0.03)
                quality_flags.append('has_speakers')
                extracted_data['speakers'] = valid_speakers
            else:
                extracted_data['speakers'] = []
        
        # Validate pricing information
        ticket_price = extracted_data.get('ticket_price')
        is_paid = extracted_data.get('is_paid')
        
        if ticket_price and str(ticket_price).lower() not in ['unknown', 'tbd', 'n/a', 'none']:
            quality_score += 0.05
            quality_flags.append('has_pricing')
        elif is_paid is not None:
            quality_score += 0.03
            quality_flags.append('has_payment_info')
        
        # Calculate final quality assessment
        extracted_data['quality_score'] = round(quality_score, 2)
        extracted_data['quality_flags'] = quality_flags
        
        # Determine if extraction should be considered successful
        min_quality_threshold = 0.4  # Require at least 40% quality score
        has_basic_requirements = (
            len(name) >= 5 and 
            name.lower() not in ['unknown', 'n/a', 'tbd'] and
            quality_score >= min_quality_threshold
        )
        
        # Additional validation for very low quality
        if quality_score < 0.2:
            quality_flags.append('very_low_quality')
        elif quality_score >= 0.7:
            quality_flags.append('high_quality')
        
        return extracted_data

def enrich_conference_data(raw_conferences: List[Dict[str, Any]], force_reenrich: bool = False) -> List[Dict[str, Any]]:
    """
    Enrich conference data with detailed information from their pages.
    Enhanced with fallback enrichment for missing critical fields.
    
    Args:
        raw_conferences: List of raw conference dictionaries with basic info
        force_reenrich: If True, force re-enrichment even if already enriched
        
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
    
    if force_reenrich:
        print(f"🔄 Force re-enrichment mode: enriching {len(raw_conferences)} conferences (skipping enrichment checks)...")
    else:
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
        # Skip enrichment if already enriched (UNLESS force_reenrich is True)
        if not force_reenrich and (conference.get("speakers") or conference.get("sponsors")):
            print(f"[⏩ Skip] Already enriched: {conference.get('name')}")
            enriched_conferences.append(conference)
            continue
        
        if force_reenrich and (conference.get("speakers") or conference.get("sponsors")):
            print(f"[🔄 Force] Re-enriching already processed: {conference.get('name')}")
            
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