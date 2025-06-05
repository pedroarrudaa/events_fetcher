"""
GPT-based extractor for structured hackathon data.
"""
import json
import os
import re
from datetime import datetime
from typing import Dict, Any, Optional, List
from openai import OpenAI
from dotenv import load_dotenv
from hackathon_fetcher.utils.firecrawl import FirecrawlFetcher
import sys
sys.path.append('..')

import requests
from bs4 import BeautifulSoup

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
    """Extract detailed hackathon information using OpenAI GPT."""
    
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
    
    def _fetch_content_fallback(self, url: str) -> Dict[str, str]:
        """
        Fallback content fetcher using requests and BeautifulSoup.
        
        Args:
            url: URL to fetch content from
            
        Returns:
            Dictionary with 'html' and 'markdown' content
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Extract text content (simple markdown conversion)
            html_content = response.text
            text_content = soup.get_text()
            
            # Clean up whitespace
            lines = (line.strip() for line in text_content.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            markdown_content = '\\n'.join(chunk for chunk in chunks if chunk)
            
            return {
                'html': html_content,
                'markdown': markdown_content
            }
            
        except Exception as e:
            print(f"⚠️ Fallback content fetch failed for {url}: {str(e)}")
            return {
                'html': '',
                'markdown': ''
            }
    
    def extract_hackathon_data(self, html_content: str, markdown_content: str, url: str) -> Dict[str, Any]:
        """
        Extract structured data from hackathon content.
        
        Args:
            html_content: Raw HTML content
            markdown_content: Markdown content from Firecrawl
            url: Original URL of the hackathon
            
        Returns:
            Dictionary with extracted hackathon data
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
                        "content": "You are an expert at extracting structured information from hackathon websites. Always respond with valid JSON only."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=1500,  # Increased from 1000 to match conference extractor
                temperature=0.1  # Low temperature for consistent extraction
            )
            
            # Check if response content exists
            if not response.choices or not response.choices[0].message or response.choices[0].message.content is None:
                return {
                    'extraction_success': False,
                    'url': url,
                    'error': "OpenAI API returned empty response"
                }
            
            # Parse the JSON response
            result_text = response.choices[0].message.content.strip()
            
            # Clean up the response in case GPT adds markdown formatting
            if result_text.startswith('```json'):
                result_text = result_text[7:]
            if result_text.endswith('```'):
                result_text = result_text[:-3]
            
            result_text = result_text.strip()
            
            extracted_data = json.loads(result_text)
            
            # **FIX: Handle case where GPT returns a list instead of a dictionary**
            if isinstance(extracted_data, list):
                if len(extracted_data) > 0 and isinstance(extracted_data[0], dict):
                    # Take the first element if it's a list of dictionaries
                    extracted_data = extracted_data[0]
                    print(f"⚠️ GPT returned a list, using first element for {url}")
                else:
                    # Return error if list doesn't contain valid data
                    return {
                        'extraction_success': False,
                        'url': url,
                        'error': "GPT returned invalid list format",
                        'raw_response': result_text[:500]
                    }
            elif not isinstance(extracted_data, dict):
                # Handle case where it's neither list nor dict
                return {
                    'extraction_success': False,
                    'url': url,
                    'error': f"GPT returned unexpected data type: {type(extracted_data)}",
                    'raw_response': result_text[:500]
                }
            
            # Validate extracted data structure
            extracted_data = self._validate_and_clean_extracted_data(extracted_data, url)
            
            # If GPT didn't extract dates, try fallback date extraction
            if not extracted_data.get('start_date') and not extracted_data.get('end_date'):
                content_for_dates = markdown_content if markdown_content.strip() else html_content
                fallback_dates = extract_dates_from_text(content_for_dates)
                
                if fallback_dates.get('start_date'):
                    extracted_data['start_date'] = fallback_dates['start_date']
                if fallback_dates.get('end_date'):
                    extracted_data['end_date'] = fallback_dates['end_date']
                if fallback_dates.get('registration_deadline') and not extracted_data.get('registration_deadline'):
                    extracted_data['registration_deadline'] = fallback_dates['registration_deadline']
            
            # Add metadata
            extracted_data['extraction_success'] = True
            extracted_data['url'] = url
            extracted_data['extraction_method'] = 'gpt-4o-mini'
            
            return extracted_data
            
        except json.JSONDecodeError as e:
            # Safely get raw response content
            raw_response = None
            if 'response' in locals() and response.choices and response.choices[0].message:
                raw_response = response.choices[0].message.content
            
            return {
                'extraction_success': False,
                'url': url,
                'error': f"JSON parsing error: {str(e)}",
                'raw_response': raw_response
            }
        except Exception as e:
            return {
                'extraction_success': False,
                'url': url,
                'error': f"Extraction error: {str(e)}"
            }
    
    def _create_extraction_prompt(self, content: str, url: str) -> str:
        """Create the enhanced extraction prompt for GPT."""
        return f"""
Extract structured information from this hackathon webpage content and return it as a JSON object.

URL: {url}

CONTENT:
{content}

Please extract the following fields and return ONLY a valid JSON object. Only extract what's AVAILABLE ON THE PAGE - do not guess or make assumptions:

{{
    "name": "Name of the hackathon",
    "url": "{url}",
    "remote": true/false (whether it's remote/virtual),
    "in_person": true/false (whether it has in-person component),
    "city": "City name if in-person or hybrid, null if fully remote",
    "short_description": "Brief description (1-2 sentences max)",
    "prizes": ["List of prizes/awards with amounts if mentioned"],
    "sponsors": ["List of sponsor names if mentioned"],
    "judges": ["List of judge names with titles/companies if mentioned"],
    "start_date": "Start date in YYYY-MM-DD format (e.g., 2025-07-14) or null",
    "end_date": "End date in YYYY-MM-DD format (e.g., 2025-07-16) or null",
    "registration_deadline": "Registration deadline in YYYY-MM-DD format or null",
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

👥 JUDGES EXTRACTION:
- Look for judge panels, judging committees, mentors, advisors
- Extract name, company/organization, and job title when available
- Format: {{"name": "John Smith", "company": "Google", "title": "Senior Engineer"}}
- Include both technical judges and industry experts
- Look for sections like "Meet the Judges", "Judging Panel", "Advisory Board"

🏆 PRIZES EXTRACTION:
- Look for prize money, awards, recognition programs, cash prizes
- Extract specific amounts when mentioned (e.g., "$5000 Grand Prize")
- Include non-monetary prizes like internships, credits, hardware, mentorship
- Example: ["$10,000 Grand Prize", "$5,000 Second Place", "AWS Credits for all teams"]
- Look for sections like "Prizes", "Awards", "What You Can Win"

🏢 SPONSORS EXTRACTION:
- Look for sponsor logos, sponsor lists, "supported by", "partners", "backed by"
- Extract company/organization names only
- Include both title sponsors and supporting partners
- Look for different sponsor tiers (Gold, Silver, Bronze, etc.)
- Check footer areas and sidebar sponsor sections

🎯 THEMES EXTRACTION:
- Look for tracks, categories, challenge themes, focus areas, problem statements
- Example: ["AI/ML", "Blockchain", "Healthcare", "Sustainability", "Fintech"]
- Include both technical themes and application domains
- Look for sections like "Tracks", "Categories", "Challenge Areas", "Focus Themes"

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
- Be especially thorough when looking for prizes, judges, and sponsors as these are key hackathon features

EXAMPLES OF VALID EXTRACTION:
- prizes: ["$10,000 Grand Prize", "$5,000 Second Place", "AWS Credits for all participants", "Mentorship from industry experts"]
- judges: [{{"name": "Sarah Chen", "company": "Microsoft", "title": "Principal Engineer"}}, {{"name": "Alex Rodriguez", "company": "OpenAI", "title": "Research Scientist"}}]
- sponsors: ["Google", "Microsoft", "OpenAI", "GitHub", "AWS"]
- themes: ["Artificial Intelligence", "Web3", "Climate Tech", "Healthcare Innovation"]
- start_date: "2025-07-14" (ONLY if date is clearly stated and in 2025+)

LOCATION EXAMPLES:
- Valid: "San Francisco, CA" → city: "San Francisco"
- Valid: "Remote/Virtual" → remote: true, city: null
- Valid: "New York City" → city: "New York"
- Invalid: "London, UK" → city: null, remote: false
- Invalid: "Austin, TX" → city: null, remote: false
"""
    
    def extract_with_fallback(self, html_content: str, markdown_content: str, 
                             url: str, basic_details: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Extract with fallback to basic details.
        
        Args:
            html_content: Raw HTML content
            markdown_content: Markdown content from Firecrawl
            url: URL of the hackathon
            basic_details: Basic details from scraper (fallback)
            
        Returns:
            Extracted data dictionary
        """
        # Try full extraction first
        result = self.extract_hackathon_data(html_content, markdown_content, url)
        
        # If extraction failed and we have basic details, merge them
        if not result.get('extraction_success') and basic_details:
            print("🔄 GPT extraction failed, using basic details as fallback...")
            
            # Use basic details as base
            fallback_data = {
                'name': basic_details.get('name', result.get('name', 'Unknown Hackathon')),
                'url': url,
                'remote': basic_details.get('likely_remote', False),
                'in_person': basic_details.get('likely_inperson', True),
                'city': 'Unknown',
                'short_description': 'Details available on the website',
                'start_date': None,
                'end_date': None,
                'registration_deadline': None,
                'themes': [],
                'judges': [],
                'prizes': [],
                'sponsors': [],
                'eligibility': [],
                'format': 'Unknown',
                'extraction_success': False,
                'extraction_method': 'basic_fallback'
            }
            
            return fallback_data
        
        return result

    def extract_missing_fields_fallback(self, html_content: str, markdown_content: str, 
                                       url: str, missing_fields: List[str], 
                                       current_event: Dict[str, Any]) -> Dict[str, Any]:
        """
        **IMPROVEMENT 5: Enhanced fallback extraction for missing critical fields**
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
        
        # **IMPROVEMENT 5: Enhanced field descriptions for better extraction**
        field_descriptions = {
            'organizers': 'the companies, organizations, universities, or people organizing this hackathon',
            'modality': 'whether this hackathon is Remote, In-Person, or Hybrid format',
            'sponsors': 'companies or organizations sponsoring this hackathon (providing funding, prizes, etc.)',
            'judges': 'people or organizations judging this hackathon (evaluating submissions)',
            'prizes': 'specific prizes, awards, cash amounts, or rewards offered in this hackathon'
        }
        
        field_prompts = []
        for field in missing_fields:
            if field in field_descriptions:
                field_prompts.append(f"- {field}: {field_descriptions[field]}")
        
        if not field_prompts:
            print("⚠️ No valid fields to extract in fallback")
            return {}
        
        # **IMPROVEMENT 5: Use longer content for better extraction, with smart truncation**
        content_to_use = markdown_content
        if not content_to_use.strip() and html_content:
            # Extract text from HTML as fallback
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                for script in soup(["script", "style"]):
                    script.decompose()
                content_to_use = soup.get_text()
            except:
                content_to_use = html_content
        
        # Smart truncation - prefer content with hackathon-related keywords
        max_chars = 10000  # Increased from 8000
        if len(content_to_use) > max_chars:
            # Try to find sections with relevant keywords
            hackathon_keywords = ['hackathon', 'sponsor', 'judge', 'prize', 'organiz', 'remote', 'virtual', 'in-person']
            lines = content_to_use.split('\n')
            relevant_lines = []
            other_lines = []
            
            for line in lines:
                line_lower = line.lower()
                if any(keyword in line_lower for keyword in hackathon_keywords):
                    relevant_lines.append(line)
                else:
                    other_lines.append(line)
            
            # Prioritize relevant content
            content_parts = relevant_lines + other_lines
            content_to_use = '\n'.join(content_parts)[:max_chars]

        # **IMPROVEMENT 5: Enhanced prompt with better context and examples**
        prompt = f"""Extract the following missing information for this hackathon. Be thorough and look for any mentions of these items in the content.

Fields to find:
{chr(10).join(field_prompts)}

Current hackathon info:
- Name: {current_event.get('name', 'Unknown')}
- URL: {url}
- Description: {(current_event.get('description', '') or current_event.get('short_description', ''))[:200]}

Content to analyze:
{content_to_use}

Instructions:
- Look carefully for any mentions of sponsors, organizers, judges, prizes, or event format
- For organizers/sponsors/judges, include company names, university names, or person names
- For modality, determine if it's "Remote", "In-Person", or "Hybrid" based on location info
- For prizes, include specific amounts, items, or types of rewards mentioned
- If a field cannot be determined from the content, omit it entirely
- Return only valid, meaningful data

Respond in JSON format with only the fields that you can find:

Example response:
{{
    "organizers": ["Stanford University", "Google"],
    "modality": "Remote",
    "sponsors": ["Microsoft", "AWS"],
    "judges": ["Tech Industry Experts", "University Professors"],
    "prizes": ["$10,000 Grand Prize", "Free Cloud Credits", "Mentorship Opportunities"]
}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a data extraction specialist focused on hackathon events. Extract only the specific requested fields from event content. Be thorough but only return data you can confidently find. Return valid JSON only."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Very low temperature for consistent extraction
                max_tokens=1000  # Increased from 800
            )
            
            # Check if response content exists
            if not response.choices or not response.choices[0].message or response.choices[0].message.content is None:
                print("⚠️ OpenAI API returned empty response")
                return {}
            
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
                
                # Validate and return only the fields that were successfully extracted
                validated_fields = {}
                for field, value in extracted_fields.items():
                    if field in missing_fields and value:
                        # Additional validation for specific field types
                        if field == 'modality':
                            if isinstance(value, str) and value.strip() in ['Remote', 'In-Person', 'Hybrid']:
                                validated_fields[field] = value.strip()
                                print(f"   🎯 Extracted {field}: {value.strip()}")
                        elif field in ['organizers', 'sponsors', 'judges', 'prizes']:
                            if isinstance(value, list):
                                # Filter out empty strings and very short entries
                                clean_list = [str(item).strip() for item in value if len(str(item).strip()) > 2]
                                if clean_list:
                                    validated_fields[field] = clean_list
                                    print(f"   🎯 Extracted {field}: {len(clean_list)} items - {', '.join(clean_list[:2])}{'...' if len(clean_list) > 2 else ''}")
                            elif isinstance(value, str) and len(value.strip()) > 2:
                                # Convert single string to list
                                validated_fields[field] = [value.strip()]
                                print(f"   🎯 Extracted {field}: {value.strip()}")
                
                return validated_fields
                
            except json.JSONDecodeError as e:
                print(f"⚠️ Failed to parse fallback extraction JSON: {e}")
                print(f"   Raw response: {content[:200]}...")
                return {}
            
        except Exception as e:
            print(f"⚠️ Fallback extraction API call failed: {e}")
            return {}
    
    def _validate_and_clean_extracted_data(self, extracted_data: Dict[str, Any], url: str) -> Dict[str, Any]:
        """
        Validate and clean the extracted data structure.
        
        Args:
            extracted_data: The extracted data from GPT
            url: The original URL of the hackathon
            
        Returns:
            Validated and cleaned extracted data
        """
        # Validate extracted data structure
        if not isinstance(extracted_data, dict):
            raise ValueError("Extracted data is not a valid JSON object")
        
        # Ensure core extracted fields are present (these should come from GPT)
        expected_fields = [
            'name', 'remote', 'in_person', 'city', 'short_description',
            'start_date', 'end_date', 'registration_deadline', 'themes', 
            'prizes', 'sponsors', 'judges', 'eligibility'
        ]
        
        for field in expected_fields:
            if field not in extracted_data:
                extracted_data[field] = None  # Set to None if missing rather than raising error
        
        # Validate list fields are actually lists
        list_fields = ['themes', 'prizes', 'sponsors', 'judges']
        for field in list_fields:
            if extracted_data.get(field) is not None and not isinstance(extracted_data[field], list):
                # Try to convert strings to lists
                if isinstance(extracted_data[field], str):
                    extracted_data[field] = [item.strip() for item in extracted_data[field].split(',') if item.strip()]
                else:
                    extracted_data[field] = []
        
        # Validate boolean fields
        boolean_fields = ['remote', 'in_person']
        for field in boolean_fields:
            if extracted_data.get(field) is not None:
                if isinstance(extracted_data[field], str):
                    extracted_data[field] = extracted_data[field].lower() in ['true', '1', 'yes']
                else:
                    extracted_data[field] = bool(extracted_data[field])
        
        # Ensure URL is set correctly
        extracted_data['url'] = url
        
        return extracted_data

def enrich_hackathon_data(raw_hackathons: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Enrich hackathon data with detailed information from their pages.
    Enhanced with fallback enrichment for missing critical fields.
    
    Args:
        raw_hackathons: List of raw hackathon dictionaries with basic info
        
    Returns:
        List of enriched hackathon dictionaries
    """
    # Check if global variables exist, otherwise set defaults
    try:
        global firecrawl_calls, test_mode
        firecrawl_calls = firecrawl_calls if 'firecrawl_calls' in globals() else 0
        test_mode = test_mode if 'test_mode' in globals() else False
    except NameError:
        # If globals don't exist, create them
        firecrawl_calls = 0
        test_mode = False
    
    if not raw_hackathons:
        print("❌ No hackathons to enrich!")
        return []
    
    print(f"🔍 Enriching {len(raw_hackathons)} hackathons with detailed data...")
    
    enriched_hackathons = []
    successful_enrichments = 0
    fallback_enrichments = 0
    
    extractor = GPTExtractor()
    fetcher = FirecrawlFetcher()
    
    for i, hackathon in enumerate(raw_hackathons):
        print(f"\n--- [{i+1}/{len(raw_hackathons)}] Enriching: {hackathon.get('name', 'Unknown')} ---")
        
        if test_mode and i >= 1:
            print("🧪 Test mode: Limiting to 1 hackathon")
            break
        
        url = hackathon.get('url')
        if not url:
            print("❌ No URL found, skipping...")
            enriched_hackathons.append(hackathon)
            continue
        
        try:
            # First, try to get content using Firecrawl
            print(f"🔗 Fetching content from: {url}")
            firecrawl_calls += 1
            
            result = fetcher.scrape_url(url)
            
            if result['success']:
                html_content = result.get('html', '')
                markdown_content = result.get('markdown', '')
                
                print(f"✅ Content fetched successfully")
                print(f"   HTML length: {len(html_content)} chars")
                print(f"   Markdown length: {len(markdown_content)} chars")
                
                # Initial enrichment attempt
                enriched_data = extractor.extract_hackathon_data(
                    html_content, markdown_content, url
                )
                
                # Check if enrichment was successful
                if enriched_data.get('extraction_success'):
                    print("✅ GPT extraction successful")
                    
                    # Merge with original data
                    merged_hackathon = {**hackathon, **enriched_data}
                    
                    # **IMPROVEMENT 5: Enhanced check for missing critical fields and attempt fallback enrichment**
                    missing_critical_fields = []
                    
                    # Check for organizers
                    organizers = merged_hackathon.get('organizers', [])
                    if not organizers or (isinstance(organizers, list) and len(organizers) == 0) or (isinstance(organizers, str) and not organizers.strip()):
                        missing_critical_fields.append('organizers')
                    
                    # Check for modality (remote/in-person info)
                    modality = merged_hackathon.get('modality', '')
                    if not modality or modality.strip().lower() in ['unknown', 'tbd', 'n/a', '']:
                        missing_critical_fields.append('modality')
                    
                    # Check for sponsors
                    sponsors = merged_hackathon.get('sponsors', [])
                    if not sponsors or (isinstance(sponsors, list) and len(sponsors) == 0) or (isinstance(sponsors, str) and not sponsors.strip()):
                        missing_critical_fields.append('sponsors')
                    
                    # **IMPROVEMENT 5: Also check for judges and prizes**
                    judges = merged_hackathon.get('judges', [])
                    if not judges or (isinstance(judges, list) and len(judges) == 0) or (isinstance(judges, str) and not judges.strip()):
                        missing_critical_fields.append('judges')
                    
                    prizes = merged_hackathon.get('prizes', [])
                    if not prizes or (isinstance(prizes, list) and len(prizes) == 0) or (isinstance(prizes, str) and not prizes.strip()):
                        missing_critical_fields.append('prizes')
                    
                    # **IMPROVEMENT 5: If we have missing critical fields, attempt fallback enrichment**
                    if missing_critical_fields:
                        print(f"🔄 Missing critical fields: {', '.join(missing_critical_fields)}. Attempting fallback enrichment...")
                        
                        try:
                            fallback_data = extractor.extract_missing_fields_fallback(
                                html_content, markdown_content, url, missing_critical_fields, merged_hackathon
                            )
                            
                            if fallback_data:
                                print(f"✅ Fallback enrichment successful for: {', '.join(fallback_data.keys())}")
                                # **IMPROVEMENT 5: Merge the fallback results into the event**
                                for field, value in fallback_data.items():
                                    if value:  # Only update if we got meaningful data
                                        merged_hackathon[field] = value
                                        print(f"   📝 Updated {field}: {value if isinstance(value, str) else f'{len(value)} items'}")
                                fallback_enrichments += 1
                            else:
                                print("⚠️ Fallback enrichment found no additional data")
                                
                        except Exception as fallback_error:
                            print(f"⚠️ Fallback enrichment failed: {fallback_error}")
                    else:
                        print("✅ All critical fields present, no fallback needed")
                    
                    enriched_hackathons.append(merged_hackathon)
                    successful_enrichments += 1
                    
                else:
                    print("❌ GPT extraction failed")
                    # Keep original data but mark as failed
                    hackathon['extraction_success'] = False
                    enriched_hackathons.append(hackathon)
            
            else:
                print(f"❌ Failed to fetch content: {result['error']}")
                
                # Try fallback content fetcher
                print("🔄 Attempting fallback content fetch...")
                fallback_content = extractor._fetch_content_fallback(url)
                
                if fallback_content['html'] or fallback_content['markdown']:
                    print("✅ Fallback content fetch successful")
                    
                    enriched_data = extractor.extract_hackathon_data(
                        fallback_content['html'], 
                        fallback_content['markdown'], 
                        url
                    )
                    
                    if enriched_data.get('extraction_success'):
                        print("✅ GPT extraction successful with fallback content")
                        merged_hackathon = {**hackathon, **enriched_data}
                        enriched_hackathons.append(merged_hackathon)
                        successful_enrichments += 1
                    else:
                        print("❌ GPT extraction failed with fallback content")
                        hackathon['extraction_success'] = False
                        enriched_hackathons.append(hackathon)
                else:
                    print("❌ Fallback content fetch also failed")
                    hackathon['extraction_success'] = False
                    enriched_hackathons.append(hackathon)
                    
        except Exception as e:
            print(f"💥 Error enriching hackathon: {str(e)}")
            hackathon['extraction_success'] = False
            enriched_hackathons.append(hackathon)
    
    print(f"\n🎯 Enrichment Summary:")
    print(f"   • Total hackathons processed: {len(raw_hackathons)}")
    print(f"   • Successful enrichments: {successful_enrichments}")
    print(f"   • Fallback enrichments: {fallback_enrichments}")
    print(f"   • Failed enrichments: {len(raw_hackathons) - successful_enrichments}")
    print(f"   • Success rate: {(successful_enrichments/len(raw_hackathons)*100):.1f}%")
    
    return enriched_hackathons 