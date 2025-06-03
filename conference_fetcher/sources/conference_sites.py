"""
Conference scrapers for specific websites to extract upcoming AI-related conferences.
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict, Any
import re
import time

def scrape_neurips_conferences(limit: int = 2) -> List[Dict[str, Any]]:
    """
    Scrape NeurIPS conferences from https://neurips.cc/Conferences/2025
    
    Args:
        limit: Maximum number of conferences to extract
        
    Returns:
        List of conference data dictionaries
    """
    conferences = []
    
    try:
        url = "https://neurips.cc/Conferences/2025"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract conference information
        # Look for title and dates
        title_elem = soup.find('h1') or soup.find('h2', string=re.compile(r'NeurIPS|2025', re.I))
        
        conference_name = "NeurIPS 2025"
        if title_elem:
            title_text = title_elem.get_text(strip=True)
            if "2025" in title_text or "NeurIPS" in title_text:
                conference_name = title_text
        
        # Look for date information
        start_date = None
        end_date = None
        
        # Common patterns for dates on conference sites
        date_patterns = [
            r'(\w+\s+\d+)(?:st|nd|rd|th)?\s*[-–]\s*(\d+)(?:st|nd|rd|th)?,?\s*2025',
            r'December\s+\d+(?:st|nd|rd|th)?\s*[-–]\s*\d+(?:st|nd|rd|th)?,?\s*2025',
            r'2025-\d{2}-\d{2}'
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, soup.get_text(), re.IGNORECASE)
            if matches:
                # NeurIPS is typically in December
                start_date = "2025-12-09"  # Approximate
                end_date = "2025-12-15"
                break
        
        conference = {
            "name": conference_name,
            "url": url,
            "start_date": start_date,
            "end_date": end_date,
            "city": "New Orleans, LA",  # NeurIPS 2025 location
            "remote": False,
            "source": "neurips"
        }
        
        conferences.append(conference)
        
    except Exception as e:
        print(f"Error scraping NeurIPS: {e}")
    
    return conferences[:limit]

def scrape_icml_conferences(limit: int = 2) -> List[Dict[str, Any]]:
    """
    Scrape ICML conferences from https://icml.cc/Conferences/2025
    
    Args:
        limit: Maximum number of conferences to extract
        
    Returns:
        List of conference data dictionaries
    """
    conferences = []
    
    try:
        url = "https://icml.cc/Conferences/2025"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract conference information
        conference_name = "ICML 2025"
        
        # Look for actual conference name
        title_elem = soup.find('h1') or soup.find('h2', string=re.compile(r'ICML|2025', re.I))
        if title_elem:
            title_text = title_elem.get_text(strip=True)
            if "2025" in title_text or "ICML" in title_text:
                conference_name = title_text
        
        # ICML is typically in July
        start_date = "2025-07-21"
        end_date = "2025-07-27"
        
        # Look for date information in the page
        text_content = soup.get_text()
        date_matches = re.findall(r'July\s+\d+(?:st|nd|rd|th)?\s*[-–]\s*\d+(?:st|nd|rd|th)?,?\s*2025', text_content, re.IGNORECASE)
        if date_matches:
            # Try to parse the found dates
            try:
                date_text = date_matches[0]
                # Extract day numbers
                days = re.findall(r'\d+', date_text)
                if len(days) >= 2:
                    start_date = f"2025-07-{int(days[0]):02d}"
                    end_date = f"2025-07-{int(days[1]):02d}"
            except:
                pass
        
        conference = {
            "name": conference_name,
            "url": url,
            "start_date": start_date,
            "end_date": end_date,
            "city": "Vienna, Austria",  # ICML 2025 expected location
            "remote": False,
            "source": "icml"
        }
        
        conferences.append(conference)
        
    except Exception as e:
        print(f"Error scraping ICML: {e}")
    
    return conferences[:limit]

def scrape_ai4_conferences(limit: int = 2) -> List[Dict[str, Any]]:
    """
    Scrape AI conferences from https://ai4.io/
    
    Args:
        limit: Maximum number of conferences to extract
        
    Returns:
        List of conference data dictionaries
    """
    conferences = []
    
    try:
        url = "https://ai4.io/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Look for upcoming events/conferences
        event_elements = soup.find_all(['div', 'article', 'section'], class_=re.compile(r'event|conference|card', re.I))
        
        for i, element in enumerate(event_elements[:limit]):
            if i >= limit:
                break
                
            # Extract event name
            name_elem = element.find(['h1', 'h2', 'h3', 'h4'])
            event_name = "AI4 Conference"
            if name_elem:
                event_name = name_elem.get_text(strip=True)
            
            # Look for dates
            date_text = element.get_text()
            start_date = None
            end_date = None
            
            # Look for 2025 dates
            date_match = re.search(r'(\w+\s+\d+)(?:st|nd|rd|th)?\s*[-–]?\s*(\d+)?(?:st|nd|rd|th)?,?\s*2025', date_text, re.IGNORECASE)
            if date_match:
                try:
                    month_day = date_match.group(1)
                    end_day = date_match.group(2)
                    # Try to parse the date
                    start_date = datetime.strptime(f"{month_day} 2025", "%B %d %Y").strftime("%Y-%m-%d")
                    if end_day:
                        month = month_day.split()[0]
                        end_date = datetime.strptime(f"{month} {end_day} 2025", "%B %d %Y").strftime("%Y-%m-%d")
                    else:
                        end_date = start_date
                except:
                    pass
            
            # Look for location
            city = None
            location_patterns = [r'in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', r'@\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)']
            for pattern in location_patterns:
                location_match = re.search(pattern, date_text)
                if location_match:
                    city = location_match.group(1)
                    break
            
            # Determine if remote
            remote = bool(re.search(r'virtual|online|remote', date_text, re.IGNORECASE))
            
            conference = {
                "name": event_name,
                "url": url,
                "start_date": start_date,
                "end_date": end_date,
                "city": city,
                "remote": remote,
                "source": "ai4"
            }
            
            conferences.append(conference)
        
    except Exception as e:
        print(f"Error scraping AI4: {e}")
    
    print(f"✅ Found {len(conferences)} conferences from AI4")
    return conferences[:limit]

def scrape_marktechpost_events(limit: int = 2) -> List[Dict[str, Any]]:
    """
    Scrape AI events from https://events.marktechpost.com/
    
    Args:
        limit: Maximum number of events to extract
        
    Returns:
        List of conference data dictionaries
    """
    conferences = []
    
    try:
        url = "https://events.marktechpost.com/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Look for event listings
        event_elements = soup.find_all(['div', 'article', 'li'], class_=re.compile(r'event|post|card|item', re.I))
        
        for i, element in enumerate(event_elements[:limit * 2]):  # Check more elements
            if len(conferences) >= limit:
                break
                
            # Extract event name
            name_elem = element.find(['h1', 'h2', 'h3', 'h4', 'a'])
            if not name_elem:
                continue
                
            event_name = name_elem.get_text(strip=True)
            
            # Skip if not AI-related or too short
            if len(event_name) < 5 or not re.search(r'AI|artificial|machine|learning|data|tech', event_name, re.I):
                continue
            
            # Get event URL if available
            event_url = url
            link_elem = element.find('a')
            if link_elem and link_elem.get('href'):
                href = link_elem.get('href')
                if href.startswith('http'):
                    event_url = href
                elif href.startswith('/'):
                    event_url = f"https://events.marktechpost.com{href}"
            
            # Look for dates
            date_text = element.get_text()
            start_date = None
            end_date = None
            
            # Look for 2025 dates
            date_patterns = [
                r'(\w+\s+\d+)(?:st|nd|rd|th)?\s*[-–]\s*(\d+)(?:st|nd|rd|th)?,?\s*2025',
                r'2025-(\d{2})-(\d{2})',
                r'(\d{1,2})/(\d{1,2})/2025'
            ]
            
            for pattern in date_patterns:
                date_match = re.search(pattern, date_text, re.IGNORECASE)
                if date_match:
                    try:
                        if 'st|nd|rd|th' in pattern:
                            month_day = date_match.group(1)
                            end_day = date_match.group(2) if len(date_match.groups()) > 1 else None
                            start_date = datetime.strptime(f"{month_day} 2025", "%B %d %Y").strftime("%Y-%m-%d")
                            if end_day:
                                month = month_day.split()[0]
                                end_date = datetime.strptime(f"{month} {end_day} 2025", "%B %d %Y").strftime("%Y-%m-%d")
                            else:
                                end_date = start_date
                        elif '2025-' in pattern:
                            start_date = f"2025-{date_match.group(1)}-{date_match.group(2)}"
                            end_date = start_date
                        break
                    except:
                        continue
            
            # Look for location
            city = None
            location_match = re.search(r'(?:in|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', date_text)
            if location_match:
                city = location_match.group(1)
            
            # Determine if remote
            remote = bool(re.search(r'virtual|online|remote|webinar', date_text, re.IGNORECASE))
            
            conference = {
                "name": event_name,
                "url": event_url,
                "start_date": start_date,
                "end_date": end_date,
                "city": city,
                "remote": remote,
                "source": "marktechpost"
            }
            
            conferences.append(conference)
        
    except Exception as e:
        print(f"Error scraping MarkTechPost: {e}")
    
    print(f"✅ Found {len(conferences)} conferences from MarkTechPost")
    return conferences[:limit]

def scrape_techmeme_events(limit: int = 2) -> List[Dict[str, Any]]:
    """
    Scrape AI events from https://techmeme.com/events
    
    Args:
        limit: Maximum number of events to extract
        
    Returns:
        List of conference data dictionaries
    """
    conferences = []
    
    try:
        url = "https://techmeme.com/events"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Look for proper event listings with more specific selectors
        event_elements = []
        
        # Try to find actual event links and structured content
        potential_events = soup.find_all('a', href=True)
        
        for link in potential_events:
            href = link.get('href', '')
            link_text = link.get_text(strip=True)
            
            # Skip if the link is just back to techmeme events page or generic
            if href == url or 'techmeme.com/events' in href or len(link_text) < 10:
                continue
            
            # Look for specific conference/event patterns in href
            if re.search(r'conference|summit|event|expo|symposium', href, re.I):
                # Get the parent element for more context
                parent = link.parent
                if parent:
                    event_elements.append((link, parent))
        
        # If no specific conference links found, try a different approach
        if not event_elements:
            # Look for text that mentions specific conferences
            all_text = soup.get_text()
            
            # Look for well-formed conference names with dates
            conference_patterns = [
                r'([A-Z][a-zA-Z\s&]+(?:Conference|Summit|Expo|Symposium))\s+[\d\w\s,-]+2025',
                r'([A-Z][a-zA-Z\s&]+2025)\s+(?:Conference|Summit)',
                r'(AI\s+[A-Z][a-zA-Z\s]+)\s+[\d\w\s,-]+2025'
            ]
            
            for pattern in conference_patterns:
                matches = re.findall(pattern, all_text, re.IGNORECASE)
                for match in matches[:limit]:
                    if len(conferences) >= limit:
                        break
                    
                    # Validate the conference name
                    conf_name = match.strip()
                    
                    # Skip generic or low-quality names
                    skip_patterns = [
                        r'^[A-Z\s]+$',  # All caps
                        r'^\w+\s*$',    # Single word
                        r'Global\s+Congress$',  # Generic congress
                        r'^\d+',        # Starts with number
                        r'events?$',    # Ends with 'event' or 'events'
                    ]
                    
                    should_skip = False
                    for skip_pattern in skip_patterns:
                        if re.search(skip_pattern, conf_name, re.I):
                            should_skip = True
                            break
                    
                    if should_skip:
                        continue
                    
                    # Only include if it looks like a legitimate conference name
                    if len(conf_name) > 5 and len(conf_name) < 100:
                        conference = {
                            "name": conf_name,
                            "url": url,  # Use the page URL as we don't have specific links
                            "start_date": None,
                            "end_date": None,
                            "city": None,
                            "remote": None,
                            "source": "techmeme"
                        }
                        conferences.append(conference)
        else:
            # Process the found event elements
            for link, parent in event_elements[:limit]:
                if len(conferences) >= limit:
                    break
                
                link_text = link.get_text(strip=True)
                href = link.get('href', '')
                
                # Skip obviously bad names
                if len(link_text) < 5 or link_text.lower() in ['events', 'conferences', 'more']:
                    continue
                
                # Validate conference name quality
                skip_patterns = [
                    r'^[A-Z\s]+$',  # All caps
                    r'^\w+\s*$',    # Single word
                    r'Global\s+Congress$',  # Generic congress
                    r'^\d+',        # Starts with number
                    r'events?$',    # Ends with 'event' or 'events'
                ]
                
                should_skip = False
                for skip_pattern in skip_patterns:
                    if re.search(skip_pattern, link_text, re.I):
                        should_skip = True
                        break
                
                if should_skip:
                    continue
                
                # Try to extract additional context from parent element
                parent_text = parent.get_text() if parent else link_text
                
                # Look for dates in the surrounding context
                start_date = None
                end_date = None
                
                date_match = re.search(r'(\w+\s+\d+)(?:st|nd|rd|th)?\s*[-–]?\s*(\d+)?(?:st|nd|rd|th)?,?\s*2025', parent_text, re.IGNORECASE)
                if date_match:
                    try:
                        month_day = date_match.group(1)
                        end_day = date_match.group(2)
                        start_date = datetime.strptime(f"{month_day} 2025", "%B %d %Y").strftime("%Y-%m-%d")
                        if end_day:
                            month = month_day.split()[0]
                            end_date = datetime.strptime(f"{month} {end_day} 2025", "%B %d %Y").strftime("%Y-%m-%d")
                        else:
                            end_date = start_date
                    except:
                        pass
                
                # Look for location
                city = None
                location_patterns = [
                    r'(?:in|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                    r',\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*$'
                ]
                for pattern in location_patterns:
                    location_match = re.search(pattern, parent_text)
                    if location_match:
                        city = location_match.group(1)
                        break
                
                # Determine if remote
                remote = bool(re.search(r'virtual|online|remote|webinar', parent_text, re.IGNORECASE))
                
                # Use the actual event URL if available, otherwise the source page
                event_url = href if href.startswith('http') else url
                
                conference = {
                    "name": link_text,
                    "url": event_url,
                    "start_date": start_date,
                    "end_date": end_date,
                    "city": city,
                    "remote": remote,
                    "source": "techmeme"
                }
                
                conferences.append(conference)
        
        # Final quality check - remove any conferences with generic names
        filtered_conferences = []
        for conf in conferences:
            name = conf.get('name', '').strip()
            
            # Additional quality filters
            if (len(name) > 5 and 
                not name.isupper() and  # Not all uppercase
                not re.match(r'^[\w\s]*Global\s+Congress[\w\s]*$', name, re.I) and  # Not generic Global Congress
                'techmeme.com' not in name.lower() and  # Not the site name
                name.lower() not in ['datacloud global congress', 'global congress']):  # Specific exclusions
                filtered_conferences.append(conf)
        
        conferences = filtered_conferences
        
    except Exception as e:
        print(f"Error scraping Techmeme: {e}")
    
    print(f"✅ Found {len(conferences)} quality conferences from Techmeme")
    return conferences[:limit]

def get_conference_events(limit_per_site: int = 2) -> List[Dict[str, Any]]:
    """
    Aggregate conference events from all scraped sites.
    
    Args:
        limit_per_site: Maximum number of conferences to extract per site
        
    Returns:
        Combined list of conference events from all sources
    """
    print("🌐 Scraping conferences from direct conference sites...")
    
    all_conferences = []
    
    # Define all scrapers
    scrapers = [
        ("NeurIPS", scrape_neurips_conferences),
        ("ICML", scrape_icml_conferences),
        ("AI4", scrape_ai4_conferences),
        ("MarkTechPost", scrape_marktechpost_events),
        ("Techmeme", scrape_techmeme_events),
    ]
    
    for site_name, scraper_func in scrapers:
        try:
            print(f"📡 Scraping {site_name}...")
            conferences = scraper_func(limit_per_site)
            
            # Add timestamp and validate data
            for conference in conferences:
                conference['fetched_at'] = datetime.now().isoformat()
                
                # Ensure all required fields are present
                required_fields = ['name', 'url', 'start_date', 'end_date', 'city', 'remote', 'source']
                for field in required_fields:
                    if field not in conference:
                        conference[field] = None
            
            all_conferences.extend(conferences)
            print(f"✅ Found {len(conferences)} conferences from {site_name}")
            
            # Small delay between requests to be respectful
            time.sleep(1)
            
        except Exception as e:
            print(f"❌ Error scraping {site_name}: {str(e)}")
            continue
    
    print(f"🎯 Total conferences scraped: {len(all_conferences)}")
    return all_conferences

# For backward compatibility with existing code
def get_conference_urls(*args, **kwargs):
    """Backward compatibility function."""
    return get_conference_events(*args, **kwargs) 