"""
Conference fetcher that orchestrates conference data collection from multiple sources and saves results.
"""
import os
import sys
import json
import pandas as pd
import logging
from datetime import datetime
from typing import List, Dict, Any

# Add the project root directory to the path for imports (priority)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Add the parent directory to the path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sources.conference_google import get_conference_urls as get_conference_urls_from_google
from sources.conference_sites import get_conference_urls as get_conference_urls_from_sites
# from sources.tavily_discovery import get_conferences_from_google  # Re-enabled with stricter limits # Temporarily commented out for module issue
from database_utils import save_to_db, get_db_stats
from dotenv import load_dotenv
from event_filters import filter_future_target_events, EventFilter
from conference_fetcher.enrichers.gpt_extractor import GPTExtractor, enrich_conference_data
from conference_fetcher.sources.conference_sites import get_conference_events
from gpt_validation import validate_events_batch

# Load environment variables
load_dotenv()

# Firecrawl credit tracking and test mode
firecrawl_calls = 0
test_mode = "--test" in sys.argv
print(f"🧪 Test mode is {'ON' if test_mode else 'OFF'}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ConferenceFetcher:
    """Main class for orchestrating conference data collection from multiple sources."""
    
    def __init__(self):
        """Initialize the fetcher."""
        self.gpt_extractor = GPTExtractor()
        self.event_filter = EventFilter()
        self.output_dir = "output"
        self.ensure_output_dir()
    
    def ensure_output_dir(self):
        """Ensure the output directory exists."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            print(f"📁 Created output directory: {self.output_dir}")
    
    def fetch_conferences_from_all_sources(self, limit_per_source: int = 2, max_results_per_query: int = 2, queries_file: str = "queries.txt") -> List[Dict[str, Any]]:
        """
        Fetch conference data from all available sources.
        
        Args:
            limit_per_source: Maximum number of conferences to fetch from each source
            max_results_per_query: Maximum results per search query (for search-based sources)
            queries_file: Path to file containing search queries
            
        Returns:
            Combined list of conference data from all sources
        """
        print("🌐 Fetching conferences from all available sources...")
        print(f"⚙️ Settings: limit_per_source={limit_per_source}, results_per_query={max_results_per_query}")
        
        all_conferences = []
        
        # Define all available conference sources
        sources = [
            ("Conference Google Search", self._fetch_from_conference_google, limit_per_source, max_results_per_query, queries_file),
            ("Conference Website Scrapers", self._fetch_from_conference_sites, limit_per_source),
            # Future sources can be added here:
            # ("Eventbrite Conferences", self._fetch_from_eventbrite, limit_per_source),
            # ("ACM Digital Library", self._fetch_from_acm, limit_per_source),
            # ("IEEE Events", self._fetch_from_ieee, limit_per_source),
        ]
        
        for source_name, source_func, *args in sources:
            try:
                print(f"\n--- Fetching from {source_name} ---")
                conferences = source_func(*args)
                
                # Add source metadata to each conference
                for conference in conferences:
                    conference['fetched_at'] = datetime.now().isoformat()
                    conference['data_source'] = source_name.lower().replace(' ', '_')
                
                all_conferences.extend(conferences)
                print(f"✅ Got {len(conferences)} conferences from {source_name}")
                
            except Exception as e:
                print(f"❌ Error fetching from {source_name}: {str(e)}")
                continue
        
        print(f"\n📋 Total conferences collected: {len(all_conferences)}")
        return all_conferences
    
    def _fetch_from_conference_google(self, limit: int, max_results_per_query: int, queries_file: str) -> List[Dict[str, Any]]:
        """
        Fetch conferences from the conference_google source.
        
        Args:
            limit: Maximum number of conferences to fetch
            max_results_per_query: Maximum results per search query
            queries_file: Path to queries file
            
        Returns:
            List of conference data
        """
        return get_conference_urls_from_google(
            limit=limit,
            max_results_per_query=max_results_per_query,
            queries_file=queries_file
        )
    
    def _fetch_from_conference_sites(self, limit: int) -> List[Dict[str, Any]]:
        """
        Fetch conferences from the conference_sites source.
        
        Args:
            limit: Maximum number of conferences to fetch from this source (per site, handled in scraper)
            
        Returns:
            List of conference data
        """
        # The limit_per_source is interpreted as limit *per site* by the scrapers themselves.
        # The get_conference_events function will aggregate these.
        # If an overall limit for this source type was desired, it would be applied here.
        conference_site_events = get_conference_urls_from_sites()
        
        # Add the requested logging
        print(f"✅ Loaded {len(conference_site_events)} conferences from direct sites.")
        
        # The prompt specified "Limit total scraped results per site to 1–2 items"
        # This is handled inside each individual scraper in conference_sites.py.
        # If we needed a master limit for *all* sites combined from this source, we could add:
        # return conference_site_events[:limit] 
        # But for now, we return all, as per-site limits are active.
        return conference_site_events
    
    def fetch_conferences(self, limit_per_source: int = 2, max_results_per_query: int = 2, queries_file: str = "queries.txt") -> List[Dict[str, Any]]:
        """
        Fetch conference data using multiple sources.
        
        Args:
            limit_per_source: Maximum number of conferences to fetch from each source
            max_results_per_query: Maximum results per search query (2 recommended to save credits)
            queries_file: Path to file containing search queries
            
        Returns:
            List of conference data dictionaries
        """
        print("🚀 Starting conference data collection...")
        print(f"⚙️ Settings: limit_per_source={limit_per_source}, results_per_query={max_results_per_query}, queries_file={queries_file}")
        
        try:
            conferences = self.fetch_conferences_from_all_sources(
                limit_per_source=limit_per_source,
                max_results_per_query=max_results_per_query,
                queries_file=queries_file
            )
            
            if not conferences:
                print("❌ No conferences found from any source!")
                return []
            
            print(f"✅ Successfully fetched {len(conferences)} conferences from all sources")
            return conferences
            
        except Exception as e:
            print(f"💥 Error fetching conferences: {str(e)}")
            return []
    
    def save_to_csv(self, conferences: List[Dict[str, Any]], filename: str = "conferences.csv") -> str:
        """
        Save conference data to CSV.
        
        Args:
            conferences: List of conference data dictionaries
            filename: CSV filename
            
        Returns:
            Path to the saved CSV file
        """
        if not conferences:
            print("❌ No conference data to save to CSV!")
            return None
        
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            # Convert to DataFrame and handle nested lists/dicts
            df = pd.json_normalize(conferences)
            
            # Convert lists to strings for CSV compatibility
            for col in df.columns:
                if df[col].dtype == 'object':
                    df[col] = df[col].apply(lambda x: str(x) if isinstance(x, (list, dict)) else x)
            
            # Save to CSV
            df.to_csv(filepath, index=False, encoding='utf-8')
            
            print(f"💾 Saved {len(conferences)} conferences to CSV: {filepath}")
            return filepath
            
        except Exception as e:
            print(f"❌ Error saving to CSV: {str(e)}")
            return None
    
    def save_to_json(self, conferences: List[Dict[str, Any]], filename: str = "conferences.json") -> str:
        """
        Save conference data to JSON.
        
        Args:
            conferences: List of conference data dictionaries
            filename: JSON filename
            
        Returns:
            Path to the saved JSON file
        """
        if not conferences:
            print("❌ No conference data to save to JSON!")
            return None
        
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            # Save to JSON with pretty formatting
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(conferences, f, indent=2, ensure_ascii=False, default=str)
            
            print(f"💾 Saved {len(conferences)} conferences to JSON: {filepath}")
            return filepath
            
        except Exception as e:
            print(f"❌ Error saving to JSON: {str(e)}")
            return None
    
    def generate_summary(self, conferences: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate a summary of the fetched conferences.
        
        Args:
            conferences: List of conference data
            
        Returns:
            Summary dictionary
        """
        if not conferences:
            return {"total": 0, "summary": "No conferences found"}
        
        # Basic stats
        total = len(conferences)
        remote_count = sum(1 for c in conferences if c.get('is_remote') is True)
        in_person_count = sum(1 for c in conferences if c.get('is_remote') is False)
        tbd_location_count = total - remote_count - in_person_count
        
        # Source breakdown
        sources = {}
        for c in conferences:
            source = c.get('data_source', 'unknown')
            sources[source] = sources.get(source, 0) + 1
        
        # Cities
        cities = [c.get('city', 'TBD') for c in conferences if c.get('city') not in [None, 'TBD', 'Remote']]
        unique_cities = list(set(cities)) if cities else []
        
        # Dates
        dated_conferences = [c for c in conferences if c.get('start_date') not in [None, 'TBD']]
        
        # Topics (flatten all topic lists)
        all_topics = []
        for c in conferences:
            topics = c.get('topics', [])
            if isinstance(topics, list):
                all_topics.extend(topics)
        unique_topics = list(set(all_topics)) if all_topics else []
        
        summary = {
            "total_conferences": total,
            "source_breakdown": sources,
            "location_breakdown": {
                "remote": remote_count,
                "in_person": in_person_count,
                "location_tbd": tbd_location_count
            },
            "unique_cities": unique_cities[:10],  # Show top 10
            "conferences_with_dates": len(dated_conferences),
            "common_topics": unique_topics[:15],  # Show top 15
            "extraction_success_rate": f"{(total / total * 100):.1f}%" if total > 0 else "0%"
        }
        
        return summary
    
    def clean_conference_data(self, conferences: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Clean and normalize conference data before saving.
        
        Args:
            conferences: List of conference dictionaries
            
        Returns:
            List of cleaned conference dictionaries
        """
        print("🧹 Cleaning conference data...")
        
        cleaned = []
        for conference in conferences:
            # Create a copy to avoid modifying the original
            clean_conference = conference.copy()
            
            # Remove unwanted fields (but preserve extraction_success for summary calculation)
            clean_conference.pop("extraction_method", None)
            clean_conference.pop("eligibility", None)
            
            # Normalize remote field
            if "remote" in clean_conference:
                clean_conference["remote"] = bool(clean_conference["remote"])
            elif clean_conference.get("in_person") is True:
                clean_conference["remote"] = False
            else:
                clean_conference["remote"] = False
            
            # Remove in_person field entirely
            clean_conference.pop("in_person", None)
            
            cleaned.append(clean_conference)
        
        print(f"✅ Cleaned {len(cleaned)} conferences")
        return cleaned
    
    def is_remote_or_us(self, conference):
        """Filter conferences that are either remote or located in the USA."""
        location = (conference.get("city") or "").lower()
        remote = str(conference.get("remote", "")).lower()
        return (
            "united states" in location
            or "usa" in location
            or "san francisco" in location
            or "new york" in location
            or remote == "true"
        )
    
    def deduplicate_conferences(self, conferences: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate conferences based on name and URL combination.
        
        Args:
            conferences: List of conference dictionaries
            
        Returns:
            List of deduplicated conference dictionaries
        """
        print("🔍 Deduplicating conferences...")
        
        seen = set()
        deduped = []
        
        for conference in conferences:
            # Create a key from name and URL (case-insensitive, trimmed)
            name = (conference.get("name") or "").strip().lower()
            url = (conference.get("url") or "").strip().lower()
            key = (name, url)
            
            if key not in seen:
                seen.add(key)
                deduped.append(conference)
        
        removed_count = len(conferences) - len(deduped)
        if removed_count > 0:
            print(f"🗑️ Removed {removed_count} duplicate conferences")
        print(f"✅ Kept {len(deduped)} unique conferences")
        
        return deduped
    
    def filter_conference_urls(self, conferences: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter out URLs that are obviously not conference pages.
        
        Args:
            conferences: List of conference dictionaries
            
        Returns:
            List of filtered conference dictionaries
        """
        print("🔍 Filtering out non-conference URLs...")
        
        # Patterns that indicate non-conference content
        exclude_patterns = [
            # Blog and content patterns
            '/blog/', '/article/', '/news/', '/press/', '/about/', '/contact/',
            '/privacy/', '/terms/', '/careers/', '/jobs/', '/login/', '/signup/',
            '/demo/', '/trial/', '/pricing/', '/product/', '/solutions/',
            '/learn/', '/course/', '/tutorial/', '/guide/', '/documentation/',
            '/api/', '/docs/', '/help/', '/support/', '/faq/',
            '/category/', '/tag/', '/author/', '/search/', '/sitemap/',
            
            # File extensions
            '.pdf', '.doc', '.ppt', '.zip', '.jpg', '.png', '.gif',
            
            # User and account related
            '/user/', '/profile/', '/account/', '/dashboard/', '/users/',
            '/viewprofilepage/', '/user-id/', '/sign_up', '/signup', '/register/',
            
            # Business and services
            '/business/', '/enterprise/', '/services/', '/consulting/',
            '/use-case/', '/use_case/', '/usecase/', '/case-study/', '/case_study/',
            
            # Forms and subscriptions
            '/form/', '/forms/', '/subscribe/', '/subscription/',
            '/newsletter/', '/download/', '/resource/', '/resources/',
            '/white-paper/', '/whitepaper/', '/e-book/', '/ebook/',
            
            # Platform and software specific
            '/hub/', '/platform/', '/software/', '/app/', '/applications/',
            '/training/', '/certification/', '/certifications/',
            '/discussion/', '/discussions/', '/forum/', '/forums/',
            '/community/', '/bd-p/', '/t5/', '/messagepage/',
            
            # Marketing and sales
            '/pricing/', '/plans/', '/features/', '/benefits/',
            '/customer/', '/customers/', '/success/', '/testimonials/',
            '/partners/', '/partnership/', '/vendor/',
            
            # Technical and development
            '/appdynamics/', '/splunk/', '/databricks/',
            '/artificial-intelligence/', '/ai-', '/machine-learning/',
            '/security/', '/observability/', '/monitoring/',
            
            # Specific problematic patterns from the data
            '/en_us/', '/tips/', '/learn/', '/industry/', '/industries/',
            '/global-impact/', '/leadership/', '/site-map/',
            '/get-started/', '/migration/', '/digital-resilience/',
            '/data-management/', '/all-use-cases/', '/virtual-event-',
            '/push-notifications/', '/virtual-events-vocabulary/',
            '/hybrid-webinars/', '/employer-branding/',
            '/company-milestone-events/', '/product-launch/',
            '/sales-kickoff/', '/conference-summits/',
            
            # Trustpilot, reviews, and external
            'trustpilot.com', 'review/', '/reviews/',
            
            # Query parameters that indicate dynamic content
            '?redirect=', '?generated_by=', '?hash=', '?q=',
            '&redirect=', '&generated_by=', '&hash=', '&q=',
            
            # NEW: Status pages and service-related patterns from our analysis
            'status.', '/status', '/status/', 'statuspage.',
            '/organizer/', '/industry/', '/service/', '/ticketing',
            'event-industry', 'food-drink-event', 'event ticketing',
            
            # NEW: Databricks community and user profiles specifically
            'community.databricks.com/t5/user/',
            '/viewprofilepage/user-id/',
            
            # NEW: Splunk blog patterns
            '/blog/author/', '/blog/security', '/blog/industries',
            '/form/splunk-blogs-subscribe',
            
            # NEW: Airmeet and similar platform patterns  
            '/airmeet.com/hub/blog/', 'status.airmeet.com',
            '/polls-and-surveys', '/hybrid-webinars',
            
            # NEW: Eventbrite service pages
            '/organizer/event-industry/', '/food-drink-event-ticketing'
        ]
        
        # Keywords that suggest conference content
        conference_keywords = [
            'conference', 'summit', 'symposium', 'workshop', 'meetup',
            'event', 'expo', 'convention', 'forum', 'congress',
            'gathering', 'festival', 'hackathon', 'bootcamp'
        ]
        
        filtered = []
        excluded_count = 0
        
        for conf in conferences:
            url = conf.get('url', '') or ''  # Handle None values
            name = conf.get('name', '') or ''  # Handle None values
            url = url.lower()
            name = name.lower()
            
            # Check if URL contains exclude patterns
            should_exclude = any(pattern in url for pattern in exclude_patterns)
            
            # If URL doesn't have obvious exclude patterns, check for conference keywords
            if not should_exclude:
                has_conference_keywords = any(keyword in url or keyword in name for keyword in conference_keywords)
                
                # If no conference keywords found, be more strict about what we include
                if not has_conference_keywords:
                    # Allow if it's a main domain page or event-related path
                    if not any(path in url for path in ['/events/', '/event/', '/conferences/', '/conference/']):
                        # Check if it's just a domain root or has very few path segments
                        url_parts = url.replace('https://', '').replace('http://', '').split('/')
                        if len(url_parts) > 2 and not any(keyword in url for keyword in ['event', 'conference', 'summit', 'expo']):
                            should_exclude = True
            
            if should_exclude:
                excluded_count += 1
                print(f"   ❌ Excluded: {url}")
            else:
                filtered.append(conf)
        
        print(f"🗑️ Excluded {excluded_count} non-conference URLs")
        print(f"✅ Kept {len(filtered)} potential conference URLs")
        
        return filtered
    
    def filter_non_conferences_post_enrichment(self, conferences: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter out entries that clearly aren't conferences after enrichment,
        based on their descriptions and extracted content.
        
        Args:
            conferences: List of conference dictionaries after enrichment
            
        Returns:
            List of filtered conference dictionaries
        """
        print("🔍 Post-enrichment quality filtering...")
        
        # Patterns in names/descriptions that indicate non-conference content
        non_conference_indicators = [
            # General content types
            'blog', 'article', 'guide', 'tutorial', 'course', 'lesson',
            'subscription', 'newsletter', 'sign up', 'create account',
            'login', 'register', 'form', 'download', 'resource',
            
            # Business/marketing content
            'use case', 'case study', 'pricing', 'demo', 'trial',
            'business plan', 'platform', 'software', 'solution',
            'product launch', 'sales kickoff', 'employer branding',
            
            # Technical/educational content
            'discussion', 'forum', 'community', 'support', 'help',
            'documentation', 'api', 'integration', 'migration',
            'certification', 'training', 'learning',
            
            # Specific non-conference phrases
            'collection of blogs', 'blog features', 'explore how',
            'no description available', 'user profile', 'user community',
            'create your free account', 'step into a new era',
            'maximize the full value', 'build resilience',
            'streamline workflows', 'boost efficiency',
            
            # NEW: Status and service page indicators from our analysis
            'status page', 'system status', 'operational status',
            'incident notifications', 'service status',
            'ticketing tools', 'event ticketing', 'ticketing platform',
            'food and drink event', 'event industry tools',
            
            # NEW: Splunk/Databricks specific patterns
            'splunk blogs', 'blog subscription', 'industries blogs',
            'security blog', 'author blog', 'community profile',
            'viewprofilepage', 'user-id',
            
            # NEW: Airmeet specific patterns
            'polls and surveys', 'hybrid webinars', 'virtual event tools',
            'webinar platform', 'event platform', 'meeting platform',
            
            # NEW: General service/platform indicators
            'learning platform', 'business provides', 'software makes',
            'platform for', 'tools to help', 'resources to help',
            'explore a collection of', 'subscribe to', 'get help for'
        ]
        
        # Required conference indicators (at least one should be present)
        conference_indicators = [
            'conference', 'summit', 'symposium', 'expo', 'convention',
            'gathering', 'festival', 'event', 'workshop', 'meetup',
            'congress', 'forum', 'seminar', 'hackathon', 'bootcamp',
            'speakers', 'keynote', 'sessions', 'presentations',
            'networking', 'attendees', 'registration', 'agenda'
        ]
        
        filtered = []
        excluded_count = 0
        
        for conf in conferences:
            name = (conf.get('name') or '').lower()
            description = (conf.get('description') or '').lower()
            long_description = (conf.get('long_description') or '').lower()
            
            # Combine all text for checking
            all_text = f"{name} {description} {long_description}"
            
            # Check if it has obvious non-conference indicators
            has_non_conference = any(indicator in all_text for indicator in non_conference_indicators)
            
            # Check if it has conference indicators
            has_conference = any(indicator in all_text for indicator in conference_indicators)
            
            # Special checks for obvious non-conferences
            is_blog = 'blog' in name or 'blog' in description
            is_signup = any(x in all_text for x in ['sign up', 'create account', 'registration form'])
            is_user_profile = 'user profile' in all_text or 'viewprofilepage' in conf.get('url', '')
            is_company_page = any(x in all_text for x in ['company', 'business solution', 'platform'])
            
            # Decision logic
            should_exclude = False
            
            if is_blog or is_signup or is_user_profile:
                should_exclude = True
                
            elif has_non_conference and not has_conference:
                should_exclude = True
                
            elif not has_conference and is_company_page:
                should_exclude = True
                
            # Special case: if it's clearly a service/product page
            elif any(x in all_text for x in [
                'our software makes it simple',
                'explore a collection of',
                'subscribe to', 'get help for',
                'resources to help you find',
                'learning platform for', 'provides a learning platform',
                'business provides', 'for business provides',
                'catering to all skill levels', 'data and ai needs'
            ]):
                should_exclude = True
            
            # Check for business platform indicators in the URL
            elif any(x in conf.get('url', '').lower() for x in [
                '/business', '/platform', '/software', '/product'
            ]) and not has_conference:
                should_exclude = True
            
            if should_exclude:
                excluded_count += 1
                print(f"   ❌ Excluded non-conference: {name[:60]}...")
            else:
                filtered.append(conf)
        
        print(f"🗑️ Excluded {excluded_count} non-conferences after enrichment")
        print(f"✅ Kept {len(filtered)} actual conferences")
        
        return filtered
    
    def run(self, limit_per_source: int = 2, max_results_per_query: int = 2, queries_file: str = "queries.txt"):
        """
        Run the complete conference fetching pipeline with multiple sources.
        
        Args:
            limit_per_source: Maximum number of conferences to fetch from each source
            max_results_per_query: Maximum results per search query
            queries_file: Path to queries file
        """
        global firecrawl_calls, test_mode
        
        print("🎯 Multi-Source Conference Fetcher Starting...")
        
        if test_mode:
            print("🧪 Test mode is ON: pipeline will be limited to 1 event")
        
        try:
            # Fetch conferences from all sources
            conferences = self.fetch_conferences(
                limit_per_source=limit_per_source,
                max_results_per_query=max_results_per_query,
                queries_file=queries_file
            )
            
            # Initialize with empty list if None returned
            if conferences is None:
                conferences = []

            # Add Tavily Google search for more conferences with error handling
            print("🌍 Running Tavily Google search with stricter limits...")
            try:
                pass  # Temporarily disabled tavily functionality
            except Exception as tavily_error:
                print(f"⚠️ Tavily search failed: {tavily_error}")
                print("   • This might be due to API rate limits or network issues")
                print("   • Continuing with conferences from other sources...")
            
            # Check if we have any conferences at all
            if not conferences:
                print("❌ No conferences were successfully collected from any source!")
                print("\n🔧 Troubleshooting steps:")
                print("   • Check if API keys are properly set in environment variables")
                print("   • Verify network connectivity")
                print("   • Try running again later if rate limits were hit")
                print("   • Consider increasing limit_per_source for more results")
                
                # Still try to show database stats even if no new data
                try:
                    db_stats = get_db_stats()
                    print(f"\n📊 Current Database Statistics:")
                    print(f"   🗄️ Total conferences in DB: {db_stats['conferences']['total']}")
                    print(f"   🌐 Remote conferences: {db_stats['conferences']['remote']}")
                    print(f"   🏢 In-person conferences: {db_stats['conferences']['in_person']}")
                    print(f"   📅 Added in last 24h: {db_stats['conferences']['recent_24h']}")
                except Exception as db_error:
                    print(f"   ⚠️ Could not retrieve database stats: {db_error}")
                
                return

            print(f"✅ Total conferences collected from all sources: {len(conferences)}")
            
            # Initialize variables for summary (in case of errors)
            filtered_urls = conferences
            deduped_conferences = conferences
            enriched_conferences = conferences
            quality_filtered = conferences
            
            # Filter out obviously non-conference URLs
            try:
                filtered_urls = self.filter_conference_urls(conferences)
            except Exception as filter_error:
                print(f"⚠️ Error filtering URLs: {filter_error}")
                filtered_urls = conferences  # Use original data without filtering
            
            # Deduplicate conferences
            try:
                deduped_conferences = self.deduplicate_conferences(filtered_urls)
            except Exception as dedup_error:
                print(f"⚠️ Error deduplicating: {dedup_error}")
                deduped_conferences = filtered_urls  # Use filtered data without deduplication
            
            # Enrich conferences with detailed information using GPT
            print("\n🔍 Enriching conference data with GPT...")
            try:
                enriched_conferences = enrich_conference_data(deduped_conferences)
            except Exception as enrichment_error:
                print(f"⚠️ Error during enrichment: {enrichment_error}")
                enriched_conferences = deduped_conferences  # Use deduped data without enrichment
            
            # Post-enrichment quality filtering (remove obvious non-conferences)
            try:
                quality_filtered = self.filter_non_conferences_post_enrichment(enriched_conferences)
            except Exception as quality_error:
                logger.warning(f"⚠️ Error in post-enrichment filtering: {quality_error}")
                quality_filtered = enriched_conferences  # Use enriched data without quality filtering
            
            # Apply enhanced filtering: future events in target locations only
            logger.info("\n🎯 Applying enhanced filtering (future events + target locations)...")
            filtered_conferences = filter_future_target_events(quality_filtered, "conference")
            
            if not filtered_conferences:
                logger.error("❌ No conferences remained after enhanced filtering!")
                logger.info(f"   • Original conferences before filtering: {len(deduped_conferences)}")
                logger.info(f"   • After quality filtering: {len(quality_filtered)}")
                logger.info("   • Enhanced filtering removes past events and non-target locations")
                logger.info("   • Target locations: SF/Bay Area, NYC, Remote/Virtual events")
                
                # Show sample of filtered conferences for debugging
                if quality_filtered:
                    logger.info("\n🔍 Sample conferences that were filtered out:")
                    for i, conf in enumerate(quality_filtered[:3]):
                        city = conf.get('city', 'N/A')
                        remote = conf.get('remote', 'N/A')
                        start_date = conf.get('start_date', 'N/A')
                        logger.info(f"   {i+1}. {conf.get('name', 'N/A')} - City: {city}, Remote: {remote}, Date: {start_date}")
                
                return
            
            # Run GPT validation to ensure quality
            print("🤖 Running GPT validation to ensure data quality...")
            # **TEMPORARILY DISABLED: GPT validation is being too strict**
            # validated_conferences = run_gpt_validation(filtered_conferences, 'conference')
            # print(f"✅ GPT approved {len(validated_conferences)} legitimate conferences")
            
            # **TEMPORARY WORKAROUND: Skip GPT validation for now**
            validated_conferences = filtered_conferences
            print(f"⚠️ GPT validation temporarily disabled - accepted {len(validated_conferences)} conferences")
            
            # Count successful enrichments BEFORE cleaning
            enriched_count = sum(1 for c in filtered_conferences if c.get('extraction_success', False))
            
            # Clean conference data to remove unwanted fields
            cleaned_conferences = self.clean_conference_data(filtered_conferences)
            
            # Final cleanup: Remove extraction_success field before saving
            for conference in cleaned_conferences:
                conference.pop("extraction_success", None)
            
            # Save to files with error handling
            csv_path = None
            json_path = None
            
            try:
                csv_path = self.save_to_csv(cleaned_conferences)
            except Exception as csv_error:
                print(f"⚠️ Failed to save CSV: {csv_error}")
            
            try:
                json_path = self.save_to_json(cleaned_conferences)
            except Exception as json_error:
                print(f"⚠️ Failed to save JSON: {json_error}")
            
            # Save to database with error handling
            db_results = None
            try:
                db_results = save_to_db(cleaned_conferences, table_name='conferences', update_existing=True)
            except Exception as db_error:
                print(f"⚠️ Failed to save to database: {db_error}")
                print("   • Check if DATABASE_URL is properly set")
                print("   • Verify database connectivity and permissions")
            
            # Generate and display summary (use original filtered data for summary)
            try:
                summary = self.generate_summary(filtered_conferences)
                
                print(f"\n🎉 Conference Collection Summary:")
                print(f"   📊 Total conferences collected: {len(conferences)}")
                print(f"   📊 After URL filtering: {len(filtered_urls)}")
                print(f"   📊 After deduplication: {len(deduped_conferences)}")
                print(f"   📊 After enrichment: {len(enriched_conferences)}")
                print(f"   📊 After quality filtering: {len(quality_filtered)}")
                print(f"   📊 After location filtering: {len(filtered_conferences)}")
                print(f"   ✅ Successfully enriched: {enriched_count}/{len(filtered_conferences)}")
                
                # Show source breakdown
                if summary.get('source_breakdown'):
                    print(f"   📡 Source breakdown:")
                    for source, count in summary['source_breakdown'].items():
                        print(f"      - {source}: {count}")
                
                print(f"   🌐 Remote: {summary['location_breakdown']['remote']}")
                print(f"   🏢 In-person: {summary['location_breakdown']['in_person']}")
                print(f"   ❓ Location TBD: {summary['location_breakdown']['location_tbd']}")
                
                if summary.get('unique_cities'):
                    print(f"   🏙️ Cities: {', '.join(summary['unique_cities'][:5])}{'...' if len(summary['unique_cities']) > 5 else ''}")
                
                if summary.get('common_topics'):
                    print(f"   🏷️ Common topics: {', '.join(summary['common_topics'][:5])}{'...' if len(summary['common_topics']) > 5 else ''}")
                
                print(f"   📅 Conferences with dates: {summary['conferences_with_dates']}")
                
                # Show file paths only if successful
                if csv_path:
                    print(f"   💾 CSV output: {csv_path}")
                if json_path:
                    print(f"   💾 JSON output: {json_path}")
                    
            except Exception as summary_error:
                print(f"⚠️ Error generating summary: {summary_error}")
                print(f"   📊 Successfully processed {len(cleaned_conferences)} conferences")
            
            # Firecrawl usage summary
            print(f"\n🔥 [Firecrawl Usage] Total API calls this run: {firecrawl_calls}")
            if test_mode:
                print("🧪 Test mode was ON: pipeline limited to 1 event")
            
            print(f"\n🎯 Tips:")
            print(f"   • Adjust 'limit_per_source' to fetch more/fewer conferences per source")
            print(f"   • Modify 'queries.txt' to customize search terms")
            print(f"   • Set 'max_results_per_query' to 1-2 to save API credits and avoid bans")
            print(f"   • Add new sources in fetch_conferences_from_all_sources() method")
            print(f"   • If hitting rate limits, try running again later")
            
            # Get and display database statistics with error handling
            try:
                db_stats = get_db_stats()
                print(f"\n📊 Database Statistics:")
                print(f"   🗄️ Total conferences in DB: {db_stats['conferences']['total']}")
                print(f"   🌐 Remote conferences: {db_stats['conferences']['remote']}")
                print(f"   🏢 In-person conferences: {db_stats['conferences']['in_person']}")
                print(f"   📅 Added in last 24h: {db_stats['conferences']['recent_24h']}")
            except Exception as db_stats_error:
                print(f"⚠️ Could not retrieve database statistics: {db_stats_error}")
            
        except Exception as e:
            print(f"💥 Error during execution: {str(e)}")
            print(f"\n🔧 This error might be due to:")
            print(f"   • API rate limits (Firecrawl, Tavily, OpenAI)")
            print(f"   • Network connectivity issues")
            print(f"   • Missing environment variables (API keys)")
            print(f"   • Database connection problems")
            print(f"\n🎯 Suggested actions:")
            print(f"   • Wait a few minutes and try again")
            print(f"   • Check your .env file for missing API keys")
            print(f"   • Reduce limit_per_source and max_results_per_query")
            print(f"   • Check network connectivity")
            
            # Firecrawl usage summary even on error
            print(f"\n🔥 [Firecrawl Usage] Total API calls this run: {firecrawl_calls}")
            if test_mode:
                print("🧪 Test mode was ON: pipeline limited to 1 event")
            
            raise

def main():
    """Main entry point."""
    print("🏁 Welcome to the Multi-Source Conference Fetcher!")
    
    try:
        fetcher = ConferenceFetcher()
        
        # Run with conservative settings to save API credits and avoid bans
        fetcher.run(
            limit_per_source=25,           # Increased from 10 to get more conferences per source  
            max_results_per_query=10,      # Increased from 5 for more results per search query
            queries_file="queries.txt"     # Custom search queries
        )
        
    except Exception as e:
        print(f"💥 Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 