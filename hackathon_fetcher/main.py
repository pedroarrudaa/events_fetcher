"""
Main script for fetching and enriching hackathon data.
"""
import os
import sys
import json
import pandas as pd
import logging
from datetime import datetime
from typing import List, Dict, Any

# Add the current directory to the path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# Add the parent directory to the path for database utilities
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from hackathon_fetcher's sources directory
from hackathon_fetcher.sources import devpost, mlh, hackerearth, hackathon_com
from hackathon_fetcher.enrichers.gpt_extractor import GPTExtractor, enrich_hackathon_data
from database_utils import save_to_db, get_db_stats
from event_filters import filter_future_target_events, EventFilter
from gpt_validation import validate_events_batch
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Firecrawl credit tracking and test mode
firecrawl_calls = 0
test_mode = "--test" in sys.argv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HackathonFetcher:
    """Main class for orchestrating hackathon data collection."""
    
    def __init__(self):
        """Initialize the fetcher with scrapers and extractors."""
        self.gpt_extractor = GPTExtractor()
        self.event_filter = EventFilter()
        self.output_dir = "output"
        self.ensure_output_dir()
    
    def ensure_output_dir(self):
        """Ensure the output directory exists."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
    
    def fetch_hackathon_urls_from_all_sources(self, limit_per_source: int = 2) -> List[Dict[str, Any]]:
        """
        Fetch hackathon URLs from all available sources.
        
        Args:
            limit_per_source: Maximum number of hackathons to fetch from each source (None for unlimited)
            
        Returns:
            Combined list of hackathon URLs from all sources
        """
        logger.info("🌐 Fetching hackathon URLs from all sources...")
        
        all_hackathons = []
        
        # Convert None to a very large number for unlimited
        actual_limit = 1000 if limit_per_source is None else limit_per_source
        
        # Define all sources with their functions
        sources = [
            ("Devpost", devpost.get_hackathon_urls),
            ("MLH", mlh.get_hackathon_urls),
            ("HackerEarth", hackerearth.get_hackathon_urls),
            ("Hackathon.com", hackathon_com.get_hackathon_urls),
        ]
        
        for source_name, source_func in sources:
            try:
                logger.info(f"\n--- Fetching from {source_name} ---")
                hackathons = source_func(limit=actual_limit)
                all_hackathons.extend(hackathons)
                logger.info(f"✅ Got {len(hackathons)} hackathons from {source_name}")
                
            except Exception as e:
                logger.error(f"❌ Error fetching from {source_name}: {str(e)}")
                continue
        
        logger.info(f"\n📋 Total hackathons collected: {len(all_hackathons)}")
        return all_hackathons
    
    def fetch_hackathons(self, limit_per_source: int = 2, enable_enrichment: bool = True) -> List[Dict[str, Any]]:
        """
        Fetch and optionally enrich hackathon data.
        
        Args:
            limit_per_source: Maximum number of hackathons to fetch from each source (None for unlimited)
            enable_enrichment: Whether to enrich data with APIs (enabled by default)
            
        Returns:
            List of hackathon data (enriched if enabled)
        """
        logger.info("🚀 Starting hackathon data collection...")
        
        # Step 1: Get hackathon URLs from all sources
        raw_hackathons = self.fetch_hackathon_urls_from_all_sources(limit_per_source)
        
        if not raw_hackathons:
            logger.error("❌ No hackathon URLs found from any source!")
            return []
        
        if not enable_enrichment:
            logger.warning("⚠️ Enrichment is DISABLED to save API credits")
            logger.info("   The results will contain basic URL data only")
            
            # Apply filtering even without enrichment
            logger.info("🔍 Applying date and location filtering to basic data...")
            filtered_hackathons = filter_future_target_events(raw_hackathons, "hackathon")
            return filtered_hackathons
        
        # Step 2: Enrich data using GPT extraction
        logger.info("\n🔍 Enriching hackathon data with GPT...")
        enriched_hackathons = enrich_hackathon_data(raw_hackathons)
        
        # Step 3: Apply comprehensive filtering after enrichment
        logger.info("\n🎯 Applying enhanced filtering (future events + target locations)...")
        filtered_hackathons = filter_future_target_events(enriched_hackathons, "hackathon")
        
        return filtered_hackathons
    
    def save_to_csv(self, hackathons: List[Dict[str, Any]], filename: str = None) -> str:
        """
        Save hackathon data to CSV.
        
        Args:
            hackathons: List of hackathon data dictionaries
            filename: Optional custom filename
            
        Returns:
            Path to the saved CSV file
        """
        if not hackathons:
            print("❌ No hackathon data to save!")
            return None
        
        # Generate filename if not provided
        if not filename:
            filename = "hackathons.csv"
        
        filepath = os.path.join(self.output_dir, filename)
        
        # Convert to DataFrame
        df = pd.DataFrame(hackathons)
        
        # Save to CSV
        df.to_csv(filepath, index=False)
        
        print(f"💾 Saved {len(hackathons)} hackathons to CSV: {filepath}")
        return filepath
    
    def save_to_json(self, hackathons: List[Dict[str, Any]], filename: str = None) -> str:
        """
        Save hackathon data to JSON.
        
        Args:
            hackathons: List of hackathon data dictionaries
            filename: Optional custom filename
            
        Returns:
            Path to the saved JSON file
        """
        if not hackathons:
            print("❌ No hackathon data to save!")
            return None
        
        # Generate filename if not provided
        if not filename:
            filename = "hackathons.json"
        
        filepath = os.path.join(self.output_dir, filename)
        
        # Save to JSON with pretty formatting
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(hackathons, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Saved {len(hackathons)} hackathons to JSON: {filepath}")
        return filepath
    
    def clean_event_data(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Clean and normalize hackathon event data before saving.
        
        Args:
            events: List of hackathon event dictionaries
            
        Returns:
            List of cleaned hackathon event dictionaries
        """
        print("🧹 Cleaning event data...")
        
        cleaned = []
        for event in events:
            # Create a copy to avoid modifying the original
            clean_event = event.copy()
            
            # Remove unwanted fields (but preserve extraction_success for summary calculation)
            clean_event.pop("extraction_method", None) 
            clean_event.pop("eligibility", None)
            
            # Normalize remote field
            if "remote" in clean_event:
                clean_event["remote"] = bool(clean_event["remote"])
            elif clean_event.get("in_person") is True:
                clean_event["remote"] = False
            else:
                clean_event["remote"] = False
            
            # Remove in_person field entirely
            clean_event.pop("in_person", None)
            
            cleaned.append(clean_event)
        
        print(f"✅ Cleaned {len(cleaned)} events")
        return cleaned
    
    def deduplicate_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        **IMPROVEMENT 4: Remove duplicate events based on URL (not name+URL combination)**
        
        Args:
            events: List of hackathon event dictionaries
            
        Returns:
            List of deduplicated hackathon event dictionaries
        """
        print("🔍 Deduplicating events...")
        
        seen_urls = set()
        deduped = []
        
        for event in events:
            # **IMPROVEMENT 4: Use event.url as the unique key, not event.name**
            url = (event.get("url") or "").strip().lower()
            
            if not url:
                # Skip events without URLs as they can't be properly deduplicated
                print(f"⚠️ Skipping event without URL: {event.get('name', 'Unknown')[:30]}")
                continue
            
            if url not in seen_urls:
                seen_urls.add(url)
                deduped.append(event)
            else:
                # **IMPROVEMENT 4: Log skipped duplicates with URL**
                print(f"🗑️ Duplicate skipped by URL: {url}")
        
        removed_count = len(events) - len(deduped)
        if removed_count > 0:
            print(f"🗑️ Removed {removed_count} duplicate events")
        print(f"✅ Kept {len(deduped)} unique events")
        
        return deduped
    
    def run(self, limit_per_source: int = 2, enable_enrichment: bool = True):
        """
        Run the complete hackathon fetching pipeline.
        
        Args:
            limit_per_source: Maximum number of hackathons to fetch from each source (None for unlimited)
            enable_enrichment: Whether to enable API-based enrichment
        """
        global firecrawl_calls, test_mode
        
        print("🎯 Hackathon Fetcher Starting...")
        print(f"Settings: limit_per_source={limit_per_source}, enrichment={'ENABLED' if enable_enrichment else 'DISABLED'}")
        
        if test_mode:
            print("🧪 Test mode is ON: pipeline will be limited to 1 event")
        
        try:
            # Fetch and optionally enrich hackathons
            hackathons = self.fetch_hackathons(
                limit_per_source=limit_per_source,
                enable_enrichment=enable_enrichment
            )
            
            # Initialize with empty list if None returned
            if hackathons is None:
                hackathons = []
            
            # Check if we have any hackathons at all
            if not hackathons:
                print("❌ No hackathons were successfully collected from any source!")
                print("\n🔧 Troubleshooting steps:")
                print("   • Check if API keys are properly set in environment variables")
                print("   • Verify network connectivity")
                print("   • Try running again later if rate limits were hit")
                print("   • Consider increasing limit_per_source for more results")
                print("   • Check if hackathon sources are accessible")
                
                # Still try to show database stats even if no new data
                try:
                    db_stats = get_db_stats()
                    print(f"\n📊 Current Database Statistics:")
                    print(f"   🗄️ Total hackathons in DB: {db_stats['hackathons']['total']}")
                    print(f"   🌐 Remote hackathons: {db_stats['hackathons']['remote']}")
                    print(f"   🏢 In-person hackathons: {db_stats['hackathons']['in_person']}")
                    print(f"   📅 Added in last 24h: {db_stats['hackathons']['recent_24h']}")
                except Exception as db_error:
                    print(f"   ⚠️ Could not retrieve database stats: {db_error}")
                
                return
            
            print(f"✅ Total hackathons collected: {len(hackathons)}")
            
            # Clean the data before saving
            try:
                cleaned_hackathons = self.clean_event_data(hackathons)
            except Exception as clean_error:
                print(f"⚠️ Error cleaning data: {clean_error}")
                cleaned_hackathons = hackathons  # Use original data
            
            # Deduplicate events
            try:
                deduped_hackathons = self.deduplicate_events(cleaned_hackathons)
            except Exception as dedup_error:
                print(f"⚠️ Error deduplicating: {dedup_error}")
                deduped_hackathons = cleaned_hackathons  # Use cleaned data without deduplication
            
            # Check if we have any hackathons after processing
            if not deduped_hackathons:
                print("❌ No hackathons remained after cleaning and deduplication!")
                return
            
            # GPT-based validation before saving to database
            print("\n🤖 Running GPT validation to ensure data quality...")
            try:
                validated_hackathons, rejected_hackathons = validate_events_batch(deduped_hackathons, "hackathon")
                
                if rejected_hackathons:
                    print(f"🚫 GPT rejected {len(rejected_hackathons)} low-quality entries:")
                    for event in rejected_hackathons[:3]:  # Show first 3 examples
                        name = event.get('name', 'Unknown')[:50]
                        url = event.get('url', 'No URL')
                        print(f"   ❌ {name}... → {url}")
                    if len(rejected_hackathons) > 3:
                        print(f"   ... and {len(rejected_hackathons) - 3} more")
                
                print(f"✅ GPT approved {len(validated_hackathons)} legitimate hackathons")
                deduped_hackathons = validated_hackathons
                
            except Exception as gpt_error:
                print(f"⚠️ GPT validation failed: {gpt_error}")
                print("   Continuing without validation to avoid blocking legitimate events")
                # Continue with original deduped_hackathons

            # Check if we have any hackathons after validation
            if not deduped_hackathons:
                print("❌ No hackathons remained after GPT validation!")
                print("   This might indicate all events were flagged as low-quality")
                print("   Consider checking the source data or validation criteria")
                return

            # Count successful enrichments BEFORE final cleanup
            enriched_count = sum(1 for h in deduped_hackathons if h.get('extraction_success', False))
            
            # Final cleanup: Remove extraction_success field before saving
            for event in deduped_hackathons:
                event.pop("extraction_success", None)
            
            # Save to files with error handling
            csv_path = None
            json_path = None
            
            try:
                csv_path = self.save_to_csv(deduped_hackathons)
            except Exception as csv_error:
                print(f"⚠️ Failed to save CSV: {csv_error}")
            
            try:
                json_path = self.save_to_json(deduped_hackathons)
            except Exception as json_error:
                print(f"⚠️ Failed to save JSON: {json_error}")
            
            # Save to database with error handling
            db_results = None
            try:
                db_results = save_to_db(deduped_hackathons, table_name='hackathons', update_existing=True)
            except Exception as db_error:
                print(f"⚠️ Failed to save to database: {db_error}")
                print("   • Check if DATABASE_URL is properly set")
                print("   • Verify database connectivity and permissions")
            
            # Generate summary with error handling
            try:
                # Print summary
                total_sources = len(set(h.get('source', 'unknown') for h in deduped_hackathons))
                sources_summary = {}
                for h in deduped_hackathons:
                    source = h.get('source', 'unknown')
                    sources_summary[source] = sources_summary.get(source, 0) + 1
                
                print(f"\n🎉 Summary:")
                print(f"   • Total hackathons collected: {len(hackathons)}")
                print(f"   • After deduplication: {len(deduped_hackathons)}")
                print(f"   • Successfully enriched: {enriched_count}/{len(deduped_hackathons)}")
                print(f"   • Sources used: {total_sources}")
                for source, count in sources_summary.items():
                    print(f"     - {source}: {count} hackathons")
                print(f"   • Enrichment: {'ENABLED' if enable_enrichment else 'DISABLED'}")
                
                # Show file paths only if successful
                if csv_path:
                    print(f"   • CSV output: {csv_path}")
                if json_path:
                    print(f"   • JSON output: {json_path}")
                    
            except Exception as summary_error:
                print(f"⚠️ Error generating summary: {summary_error}")
                print(f"   📊 Successfully processed {len(deduped_hackathons)} hackathons")
            
            # Firecrawl usage summary
            print(f"\n🔥 [Firecrawl Usage] Total API calls this run: {firecrawl_calls}")
            if test_mode:
                print("🧪 Test mode was ON: pipeline limited to 1 event")
            
            # Get and display database statistics with error handling
            try:
                db_stats = get_db_stats()
                print(f"\n📊 Database Statistics:")
                print(f"   🗄️ Total hackathons in DB: {db_stats['hackathons']['total']}")
                print(f"   🌐 Remote hackathons: {db_stats['hackathons']['remote']}")
                print(f"   🏢 In-person hackathons: {db_stats['hackathons']['in_person']}")
                print(f"   📅 Added in last 24h: {db_stats['hackathons']['recent_24h']}")
            except Exception as db_stats_error:
                print(f"⚠️ Could not retrieve database statistics: {db_stats_error}")
                
        except Exception as e:
            print(f"💥 Error during execution: {str(e)}")
            print(f"\n🔧 This error might be due to:")
            print(f"   • API rate limits (OpenAI, source APIs)")
            print(f"   • Network connectivity issues")
            print(f"   • Missing environment variables (API keys)")
            print(f"   • Database connection problems")
            print(f"\n🎯 Suggested actions:")
            print(f"   • Wait a few minutes and try again")
            print(f"   • Check your .env file for missing API keys")
            print(f"   • Reduce limit_per_source")
            print(f"   • Try disabling enrichment (enable_enrichment=False)")
            print(f"   • Check network connectivity")
            
            # Firecrawl usage summary even on error
            print(f"\n🔥 [Firecrawl Usage] Total API calls this run: {firecrawl_calls}")
            if test_mode:
                print("🧪 Test mode was ON: pipeline limited to 1 event")
            
            raise

def main():
    """Main entry point."""
    print("🏁 Welcome to the Hackathon Fetcher!")
    
    try:
        fetcher = HackathonFetcher()
        
        # Run with enrichment enabled and limited results for faster processing
        fetcher.run(
            limit_per_source=300,  # Increased from 50 to 300 to get many more hackathons from all sources
            enable_enrichment=True  # Enable enrichment to get full data
        )
        
    except Exception as e:
        print(f"💥 Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 