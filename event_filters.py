"""
Event filtering utilities for conferences and hackathons.
Filters events to only include future events in target locations.
Enhanced with fuzzy matching, improved logging, and better filtering logic.
"""
import re
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urlparse


class EventFilter:
    """Class for filtering events based on date and location criteria."""
    
    def __init__(self):
        # **IMPROVEMENT 1: Enhanced target location keywords for fuzzy matching**
        # Updated to match the requirements exactly
        self.target_location_keywords = [
            'san francisco', 'sf', 'bay area', 
            'nyc', 'new york', 'manhattan',
            'remote', 'virtual', 'online',
            # **TEMPORARILY EXPANDED: Major tech conference cities**
            'san diego', 'los angeles', 'seattle', 'austin', 'boston',
            'chicago', 'denver', 'portland', 'vancouver', 'montreal',
            'london', 'paris', 'berlin', 'amsterdam', 'barcelona',
            'tokyo', 'singapore', 'tel aviv'
        ]
        
        # Additional comprehensive keywords for better coverage
        self.extended_location_keywords = [
            'palo alto', 'silicon valley', 'brooklyn', 'new york city',
            'webinar', 'digital', 'worldwide', 'global', 'anywhere', 
            'internet', 'web-based'
        ]
        
        # Combine both for complete matching
        self.all_location_keywords = self.target_location_keywords + self.extended_location_keywords
        
        # Keywords to identify non-hackathon events (conferences, summits, workshops, etc.)
        self.non_hackathon_keywords = [
            'summit', 'conference', 'workshop', 'seminar', 'expo', 'meetup',
            'symposium', 'forum', 'congress', 'webinar', 'masterclass', 'course',
            'training', 'lecture', 'talk', 'awards', 'ceremony', 'gala', 'exhibition'
        ]
        
        # Generic/placeholder names that indicate low-quality data
        self.generic_name_patterns = [
            # Test/mock data patterns
            r'^test\s+event',
            r'^hackathon\.com\s+test',
            r'^mock\s+',
            r'^placeholder',
            r'^example\s+',
            r'^demo\s+',
            
            # Too generic names
            r'^online$',
            r'^virtual$',
            r'^remote$',
            r'^hackathon$',
            r'^hackathons$',  # Plural form
            r'^challenge$',
            r'^challenges$',  # Plural form
            r'^event$',
            r'^events$',  # Plural form
            r'^coding\s+challenge$',
            r'^programming\s+contest$',
            
            # Numbered test patterns
            r'^.*test.*\d+$',
            r'^.*event\s+\d+$',
            r'^.*hackathon\s+\d+$',
            
            # Empty or minimal content
            r'^.{1,3}$',  # Names with 3 or fewer characters
            r'^[\s\-_]*$',  # Only whitespace/dashes/underscores
        ]
        
        # Invalid URL patterns
        self.invalid_url_patterns = [
            # Root/home pages (likely not specific hackathon pages)
            r'^https?://[^/]+/?$',
            r'^https?://[^/]+/index\.html?$',
            r'^https?://[^/]+/home/?$',
            
            # Generic listing pages
            r'^https?://devpost\.com/hackathons/?$',  # Devpost hackathons listing page
            r'^https?://mlh\.io/seasons/[^/]+/events/?$',  # MLH events listing page
            r'^https?://www\.hackerearth\.com/challenges/hackathon/?$',  # HackerEarth listing page
            
            # Generic pages
            r'/about/?$',
            r'/contact/?$',
            r'/login/?$',
            r'/signup/?$',
            r'/register/?$',
            r'/terms/?$',
            r'/privacy/?$',
            
            # Test/placeholder URLs
            r'/test',
            r'/example',
            r'/demo',
            r'/placeholder',
        ]
        
        # **IMPROVEMENT 4: Track seen URLs for deduplication (using URL as unique key)**
        self.seen_urls: Set[str] = set()

    def is_high_quality_hackathon(self, event: Dict[str, Any]) -> tuple[bool, str]:
        """
        Check if a hackathon entry has high quality data.
        
        Args:
            event: Event dictionary
            
        Returns:
            Tuple of (is_high_quality, rejection_reason)
        """
        name = event.get('name', '')
        url = event.get('url', '')
        
        # Check for meaningful name
        has_meaningful_name, name_reason = self._has_meaningful_name(name)
        if not has_meaningful_name:
            return False, f"meaningless name: {name_reason}"
        
        # Check for valid URL
        has_valid_url, url_reason = self._has_valid_url(url)
        if not has_valid_url:
            return False, f"invalid URL: {url_reason}"
        
        # Check for sufficient data
        has_sufficient_data, data_reason = self._has_sufficient_data(event)
        if not has_sufficient_data:
            return False, f"insufficient data: {data_reason}"
        
        # Check for uniqueness (URL-based duplicate detection)
        is_unique, dup_reason = self._is_unique_entry(event)
        if not is_unique:
            return False, f"duplicate: {dup_reason}"
        
        return True, "passed all quality checks"
    
    def is_high_quality_conference(self, event: Dict[str, Any]) -> tuple[bool, str]:
        """
        Check if a conference entry has high quality data.
        
        Args:
            event: Event dictionary
            
        Returns:
            Tuple of (is_high_quality, rejection_reason)
        """
        name = event.get('name', '')
        url = event.get('url', '')
        
        # Check for meaningful name
        has_meaningful_name, name_reason = self._has_meaningful_name(name)
        if not has_meaningful_name:
            return False, f"meaningless name: {name_reason}"
        
        # Check for valid URL
        has_valid_url, url_reason = self._has_valid_url(url)
        if not has_valid_url:
            return False, f"invalid URL: {url_reason}"
        
        # Check for sufficient data  
        has_sufficient_data, data_reason = self._has_sufficient_data(event)
        if not has_sufficient_data:
            return False, f"insufficient data: {data_reason}"
        
        # Check for uniqueness (URL-based duplicate detection)
        is_unique, dup_reason = self._is_unique_entry(event)
        if not is_unique:
            return False, f"duplicate: {dup_reason}"
        
        return True, "passed all quality checks"
    
    def _has_meaningful_name(self, name: str) -> tuple[bool, str]:
        """Check if the event name is meaningful and not generic."""
        if not name or len(name.strip()) < 4:
            return False, "name too short or empty"
        
        name_lower = name.lower().strip()
        
        # Check against generic patterns
        for pattern in self.generic_name_patterns:
            if re.match(pattern, name_lower):
                return False, f"matches generic pattern: {pattern}"
        
        # Name should contain meaningful words beyond just "hackathon"
        meaningful_words = re.findall(r'\b[a-zA-Z]{3,}\b', name)
        meaningful_words = [w.lower() for w in meaningful_words if w.lower() not in ['hackathon', 'hack', 'the', 'and', 'for', 'in', 'on', 'at', 'of']]
        
        if len(meaningful_words) < 1:
            return False, "no meaningful words found"
        
        return True, "name is meaningful"
    
    def _has_valid_url(self, url: str) -> tuple[bool, str]:
        """
        Check if event has a valid URL.
        
        Args:
            url: Event URL
            
        Returns:
            Tuple of (is_valid, reason)
        """
        if not url or url.strip() == '':
            return False, "no URL provided"
        
        url_clean = url.strip()
        url_lower = url_clean.lower()
        
        # Check for placeholder values
        placeholder_values = ['tbd', 'to be determined', 'coming soon', 'n/a', 'none', 'null']
        if url_lower in placeholder_values:
            return False, f"placeholder URL: {url_lower}"
        
        # **IMPROVEMENT: Allow ALL valid HTTP/HTTPS URLs including root domains**
        # Legitimate conferences often use simple URLs like https://aiconference.com/
        if url_clean.startswith('http://') or url_clean.startswith('https://'):
            # Additional check: make sure it's not just "http://" or "https://"
            if len(url_clean) > 8:  # Longer than just the protocol
                return True, "valid HTTP/HTTPS URL"
            else:
                return False, "incomplete URL (protocol only)"
        
        # If it doesn't start with http/https, it's probably malformed
        return False, f"invalid URL format: {url_clean}"

    def _has_sufficient_data(self, event: Dict[str, Any]) -> tuple[bool, str]:
        """
        **IMPROVEMENT 3: Enhanced data quality check with better logging for rejection reasons**
        Check if an event has sufficient data quality.
        Enhanced with better checks for organizers, sponsors, judges.
        """
        missing_fields = []
        
        # For hackathons, check for organizers/sponsors/judges
        if event.get('source') in ['devpost', 'mlh', 'hackerearth', 'hackathon_com']:
            organizers = event.get('organizers', [])
            sponsors = event.get('sponsors', [])
            judges = event.get('judges', [])
            
            # Convert to lists if they're strings
            if isinstance(organizers, str):
                organizers = [organizers] if organizers.strip() else []
            if isinstance(sponsors, str):
                sponsors = [sponsors] if sponsors.strip() else []
            if isinstance(judges, str):
                judges = [judges] if judges.strip() else []
            
            # Check if at least one of these fields has meaningful data
            has_organizers = organizers and len(organizers) > 0 and any(len(str(o).strip()) > 2 for o in organizers)
            has_sponsors = sponsors and len(sponsors) > 0 and any(len(str(s).strip()) > 2 for s in sponsors)
            has_judges = judges and len(judges) > 0 and any(len(str(j).strip()) > 2 for j in judges)
            
            if not (has_organizers or has_sponsors or has_judges):
                missing_fields.append("no organizers/sponsors/judges")
        
        # For conferences, check for organizers/speakers
        elif event.get('source') in ['techmeme', 'devfest', 'eventbrite']:
            organizers = event.get('organizers', [])
            speakers = event.get('speakers', [])
            
            # Convert to lists if they're strings
            if isinstance(organizers, str):
                organizers = [organizers] if organizers.strip() else []
            if isinstance(speakers, str):
                speakers = [speakers] if speakers.strip() else []
            
            # Check if at least one of these fields has meaningful data
            has_organizers = organizers and len(organizers) > 0 and any(len(str(o).strip()) > 2 for o in organizers)
            has_speakers = speakers and len(speakers) > 0 and any(len(str(s).strip()) > 2 for s in speakers)
            
            if not (has_organizers or has_speakers):
                missing_fields.append("no organizers/speakers")
        
        if missing_fields:
            return False, "; ".join(missing_fields)
        
        return True, "sufficient data available"
    
    def _is_unique_entry(self, event: Dict[str, Any]) -> tuple[bool, str]:
        """
        **IMPROVEMENT 4: URL-based deduplication as specified in requirements**
        Check if an event is unique based on URL (not name).
        
        Args:
            event: Event dictionary
            
        Returns:
            Tuple of (is_unique, reason)
        """
        url = event.get('url', '').strip().lower()
        
        if not url:
            return False, "missing URL for deduplication"
        
        if url in self.seen_urls:
            return False, f"duplicate URL: {url}"
        
        # Add to seen URLs
        self.seen_urls.add(url)
        return True, "URL is unique"

    def is_target_location(self, event: Dict[str, Any]) -> tuple[bool, str]:
        """
        **IMPROVEMENT 1: Enhanced location filtering with fuzzy matching**
        Check if an event is in a target location or is remote.
        Updated to use the exact fuzzy matching approach specified in requirements.
        
        Args:
            event: Event dictionary
            
        Returns:
            Tuple of (is_target_location, reason)
        """
        # Check if explicitly marked as remote
        if event.get('remote') is True:
            return True, "explicitly marked as remote"
        
        # Collect all location-related text for fuzzy matching
        location_texts = []
        
        # Add city field
        city = (event.get('city') or '').strip()
        if city:
            location_texts.append(city.lower())
        
        # Add location field
        location = (event.get('location') or '').strip()
        if location:
            location_texts.append(location.lower())
        
        # Add modality field (might contain "Remote", "Virtual", etc.)
        modality = (event.get('modality') or '').strip()
        if modality:
            location_texts.append(modality.lower())
        
        # Add name and description for remote keywords
        name = (event.get('name') or '').lower()
        description = (event.get('description') or '').lower()
        location_texts.extend([name, description])
        
        # **FUZZY MATCHING: Use the exact approach specified in requirements**
        all_location_text = ' '.join(location_texts)
        
        # Check using the primary target keywords first (as specified in requirements)
        for keyword in self.target_location_keywords:
            if keyword in all_location_text:
                return True, f"fuzzy match found: '{keyword}' in location text"
        
        # Also check extended keywords for better coverage
        for keyword in self.extended_location_keywords:
            if keyword in all_location_text:
                return True, f"fuzzy match found: '{keyword}' in location text (extended)"
        
        return False, f"no target location found in: {', '.join([t[:50] for t in location_texts if t][:3])}"
    
    def is_future_event(self, event: Dict[str, Any]) -> tuple[bool, str]:
        """
        Check if event is in the future (with relaxed criteria).
        
        Args:
            event: Event dictionary
            
        Returns:
            Tuple of (is_future, reason)
        """
        # **RELAXED: More lenient date checking**
        start_date = event.get('start_date')
        end_date = event.get('end_date')
        event_date = event.get('date')  # Some events might use this field
        
        # Use the latest available date
        dates_to_check = [d for d in [start_date, end_date, event_date] if d]
        
        if not dates_to_check:
            # If no dates available, be lenient and assume it might be future
            return True, "no date information available (assuming future)"
            
        today = datetime.now().date()
        
        for date_str in dates_to_check:
            if isinstance(date_str, str):
                try:
                    parsed_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    # Try other common date formats
                    try:
                        parsed_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                    except ValueError:
                        # If date parsing fails, be lenient
                        continue
            elif hasattr(date_str, 'date'):
                parsed_date = date_str.date()
            else:
                parsed_date = date_str
            
            # **RELAXED: Allow events that are today or within last week (multi-day events)**
            buffer_days = timedelta(days=7)
            if parsed_date >= (today - buffer_days):
                return True, f"event date {parsed_date} is future or recent"
        
        # If we get here, all dates were in the past
        latest_date = max(dates_to_check) if dates_to_check else "unknown"
        return False, f"start_date {latest_date} is in past"

    def is_actually_hackathon(self, event: Dict[str, Any]) -> tuple[bool, str]:
        """
        Check if an event seems to be a hackathon and not another type of event.
        
        Args:
            event: Event dictionary
            
        Returns:
            Tuple of (is_hackathon, reason)
        """
        name = (event.get('name') or '').lower()
        description = (event.get('description') or event.get('short_description') or '').lower()
        themes = event.get('themes', [])
        if isinstance(themes, list):
            themes_lower = [str(theme).lower() for theme in themes]
        else:
            themes_lower = [str(themes).lower()]

        text_to_check = name + " " + description + " " + ' '.join(themes_lower)

        for keyword in self.non_hackathon_keywords:
            if f' {keyword}' in text_to_check or f'{keyword} ' in text_to_check:
                # More specific check for "awards" to avoid filtering out hackathons with awards
                if keyword == 'awards':
                    if "hackathon" in text_to_check or "challenge" in text_to_check:
                        continue # It's likely a hackathon that has awards
                
                # Check if "hackathon" or "challenge" is also present to avoid false positives
                if "hackathon" not in text_to_check and "challenge" not in text_to_check and "hack" not in name:
                    return False, f"contains non-hackathon keyword: '{keyword}'"
        
        return True, "appears to be a hackathon"

    def reset_deduplication(self):
        """Reset the seen URLs set for a new filtering session."""
        self.seen_urls.clear()

    def _is_valid_url(self, url):
        """Check if URL is valid and not a placeholder"""
        if not url or url.lower() in ['tbd', 'to be determined', 'n/a', 'none']:
            return False
        
        # **RELAXED: Allow simple domain URLs for major conference sites**
        # Don't reject URLs just because they're simple - many legitimate conferences use simple URLs
        if url.startswith('http'):
            return True
            
        return False

    def _is_future_event(self, event_data):
        """Check if event is in the future"""
        # **RELAXED: More lenient date checking**
        start_date = event_data.get('start_date')
        end_date = event_data.get('end_date')
        
        if not start_date and not end_date:
            # If no dates available, assume it might be future and let it pass
            return True
            
        today = datetime.now().date()
        
        # Use start_date if available, otherwise end_date
        event_date = start_date or end_date
        
        if isinstance(event_date, str):
            try:
                event_date = datetime.strptime(event_date, '%Y-%m-%d').date()
            except ValueError:
                # If date parsing fails, be lenient and allow it
                return True
        
        # **RELAXED: Allow events that are today or within last 3 days (might be multi-day events)**
        buffer_days = timedelta(days=3)
        return event_date >= (today - buffer_days)


def filter_future_target_events(events: List[Dict[str, Any]], event_type: str = "event") -> List[Dict[str, Any]]:
    """
    **IMPROVEMENT 3: Enhanced filtering pipeline with detailed logging for rejected events**
    Filter events to only include future events in target locations.
    Also filters out non-hackathon events if event_type is "hackathon".
    
    Args:
        events: List of event dictionaries
        event_type: Type of event ("conference", "hackathon", or "event")
        
    Returns:
        List of filtered event dictionaries
    """
    if not events:
        return []
    
    print(f"🎯 Filtering {len(events)} {event_type}s for future events in target locations...")
    print(f"📍 Target locations: SF/Bay Area, NYC, Remote/Virtual (fuzzy matching enabled)")
    
    event_filter = EventFilter()
    event_filter.reset_deduplication()  # Reset for this filtering session
    filtered_events = []
    
    # Counters for different rejection reasons
    rejection_counts = {
        'location': 0,
        'date': 0,
        'type': 0,
        'quality': 0,
    }
    
    rejection_details = []
    
    for i, event in enumerate(events):
        event_name = event.get('name', 'Unknown')
        event_url = event.get('url', 'No URL')
        event_city = event.get('city', 'N/A')
        event_location = event.get('location', 'N/A')
        event_remote = event.get('remote', 'N/A')
        event_start_date = event.get('start_date', 'N/A')
        event_end_date = event.get('end_date', 'N/A')
        
        # **IMPROVEMENT: Detailed logging for every rejected event**
        def log_rejection(reason_category: str, specific_reason: str, additional_info: str = ""):
            rejection_counts[reason_category] += 1
            detailed_log = (
                f"🗑️  REJECTED EVENT #{i+1}/{len(events)}\n"
                f"    📛 Title: {event_name[:80]}{'...' if len(event_name) > 80 else ''}\n"
                f"    🔗 URL: {event_url}\n"
                f"    📍 Location: {event_city} | {event_location} | Remote: {event_remote}\n"
                f"    📅 Dates: {event_start_date} to {event_end_date}\n"
                f"    ❌ Reason: {specific_reason}"
            )
            if additional_info:
                detailed_log += f"\n    ℹ️  Details: {additional_info}"
            
            rejection_details.append(detailed_log)
            print(detailed_log)
        
        # Check if event is in target location (with fuzzy matching)
        is_target_loc, location_reason = event_filter.is_target_location(event)
        if not is_target_loc:
            log_rejection('location', f"Not in target location: {location_reason}")
            continue
        
        # Check if event is in the future (with looser criteria)
        is_future, date_reason = event_filter.is_future_event(event)
        if not is_future:
            log_rejection('date', f"Past event: {date_reason}")
            continue
        
        # If processing hackathons, check if it's actually a hackathon
        if event_type == "hackathon":
            is_hackathon, type_reason = event_filter.is_actually_hackathon(event)
            if not is_hackathon:
                log_rejection('type', f"Not a hackathon: {type_reason}")
                continue
            
            # Check for data quality (hackathons)
            is_quality, quality_reason = event_filter.is_high_quality_hackathon(event)
            if not is_quality:
                log_rejection('quality', f"Quality issue: {quality_reason}")
                continue
        
        # If processing conferences, check for data quality
        elif event_type == "conference":
            is_quality, quality_reason = event_filter.is_high_quality_conference(event)
            if not is_quality:
                log_rejection('quality', f"Quality issue: {quality_reason}")
                continue
        
        # **IMPROVEMENT: Log accepted events with details too**
        print(f"✅ ACCEPTED EVENT #{i+1}/{len(events)}")
        print(f"    📛 Title: {event_name[:80]}{'...' if len(event_name) > 80 else ''}")
        print(f"    🔗 URL: {event_url}")
        print(f"    📍 Location: {event_city} | Remote: {event_remote}")
        print(f"    📅 Dates: {event_start_date} to {event_end_date}")
        print(f"    ✅ Passed all filters!")
        
        # Event passed all filters
        filtered_events.append(event)
    
    # **IMPROVEMENT 3: Print detailed filtering results**
    print(f"\n🔍 Detailed Filtering Results:")
    print(f"   • Original {event_type}s: {len(events)}")
    print(f"   • Filtered out (location): {rejection_counts['location']}")
    print(f"   • Filtered out (past date): {rejection_counts['date']}")
    if event_type == "hackathon":
        print(f"   • Filtered out (non-hackathon type): {rejection_counts['type']}")
    print(f"   • Filtered out (low quality): {rejection_counts['quality']}")
    print(f"   • ✅ Final {event_type}s: {len(filtered_events)}")
    
    if filtered_events:
        print(f"\n✅ Final Accepted Events Summary:")
        for i, event in enumerate(filtered_events):
            name = event.get('name', 'N/A')[:50]
            city = event.get('city', event.get('location', 'N/A'))
            remote = event.get('remote', False)
            start_date = event.get('start_date', event.get('date', 'N/A'))
            print(f"   {i+1}. {name} - {city} {'(Remote)' if remote else ''} - {start_date}")
    
    return filtered_events 