#!/usr/bin/env python3
"""
Hackathon Mini - Simplified hackathon fetcher
A minimal, self-contained version of the hackathon data collection pipeline.
"""

import os
import sys
import json
from datetime import datetime
from typing import List, Dict, Any

# Add parent directories to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from logic import HackathonMiniScraper, HackathonMiniEnricher, HackathonMiniFilter
from render import HackathonRenderer
from database_utils import Hackathon, get_db_session, create_tables

class HackathonMini:
    """Main orchestrator for the simplified hackathon pipeline."""
    
    def __init__(self, use_test_db: bool = True):
        """Initialize the mini pipeline."""
        self.scraper = HackathonMiniScraper()
        self.enricher = HackathonMiniEnricher()
        self.filter = HackathonMiniFilter()
        self.renderer = HackathonRenderer()
        self.use_test_db = use_test_db
        
        # Ensure output directory exists
        self.output_dir = "output"
        os.makedirs(self.output_dir, exist_ok=True)
        
        print("🚀 Hackathon Mini Pipeline Initialized")
        print(f"📂 Output directory: {self.output_dir}")
        print(f"🔧 Test mode: {'ENABLED' if use_test_db else 'DISABLED'}")
    
    def run(self, limit: int = 5, enable_enrichment: bool = True, save_to_db: bool = False) -> List[Dict[str, Any]]:
        """
        Run the complete hackathon pipeline.
        
        Args:
            limit: Maximum number of hackathons to fetch
            enable_enrichment: Whether to use GPT enrichment
            save_to_db: Whether to save to database (test mode only)
            
        Returns:
            List of processed hackathon data
        """
        print(f"\n🎯 Starting pipeline with limit={limit}, enrichment={enable_enrichment}")
        
        # Step 1: Fetch hackathon URLs
        print("\n📡 Step 1: Fetching hackathon URLs...")
        raw_urls = self.scraper.fetch_hackathon_urls(limit=limit)
        
        if not raw_urls:
            print("❌ No hackathon URLs found!")
            return []
        
        print(f"✅ Found {len(raw_urls)} hackathon URLs")
        
        # Step 2: Enrich data (optional)
        if enable_enrichment:
            print("\n🧠 Step 2: Enriching with GPT...")
            enriched_data = self.enricher.enrich_hackathons(raw_urls)
        else:
            print("\n⏭️ Step 2: Skipping enrichment")
            enriched_data = [{"url": url, "name": f"Hackathon at {url}", "source": "mini"} for url in raw_urls]
        
        # Step 3: Filter and clean data
        print("\n🔍 Step 3: Filtering data...")
        filtered_data = self.filter.filter_hackathons(enriched_data)
        
        print(f"✅ {len(filtered_data)} hackathons passed filters")
        
        # Step 4: Generate outputs
        print("\n📄 Step 4: Generating outputs...")
        
        # Save to JSON
        json_path = os.path.join(self.output_dir, "hackathons_mini.json")
        with open(json_path, 'w') as f:
            json.dump(filtered_data, f, indent=2)
        print(f"💾 Saved JSON: {json_path}")
        
        # Generate HTML report
        html_path = self.renderer.generate_html_report(filtered_data, self.output_dir)
        print(f"🌐 Generated HTML: {html_path}")
        
        # Generate CSV
        csv_path = self.renderer.generate_csv_report(filtered_data, self.output_dir)
        print(f"📊 Generated CSV: {csv_path}")
        
        # Step 5: Save to database (test mode only)
        if save_to_db and self.use_test_db:
            print("\n💾 Step 5: Saving to test database...")
            self._save_to_test_db(filtered_data)
        
        print(f"\n✅ Pipeline completed! Processed {len(filtered_data)} hackathons")
        return filtered_data
    
    def _save_to_test_db(self, hackathons: List[Dict[str, Any]]) -> None:
        """Save hackathons to test database."""
        try:
            # Create tables if they don't exist
            create_tables()
            
            session = get_db_session()
            saved_count = 0
            
            for hack_data in hackathons:
                # Convert to database model
                hackathon = Hackathon(
                    name=hack_data.get('name', 'Unknown'),
                    url=hack_data.get('url', ''),
                    start_date=hack_data.get('start_date'),
                    end_date=hack_data.get('end_date'),
                    location=hack_data.get('location'),
                    remote=hack_data.get('remote', False),
                    description=hack_data.get('description'),
                    source=hack_data.get('source', 'hackathon_mini')
                )
                
                # Check if URL already exists
                existing = session.query(Hackathon).filter_by(url=hackathon.url).first()
                if not existing:
                    session.add(hackathon)
                    saved_count += 1
            
            session.commit()
            session.close()
            
            print(f"✅ Saved {saved_count} new hackathons to test database")
            
        except Exception as e:
            print(f"❌ Database save failed: {e}")


def main():
    """Main entry point."""
    print("🏁 Hackathon Mini Pipeline")
    print("=" * 50)
    
    # Parse command line arguments
    limit = 10
    enable_enrichment = True
    save_to_db = False
    
    # Check for arguments
    if len(sys.argv) > 1:
        if "--limit" in sys.argv:
            idx = sys.argv.index("--limit")
            if idx + 1 < len(sys.argv):
                limit = int(sys.argv[idx + 1])
        
        if "--no-enrichment" in sys.argv:
            enable_enrichment = False
        
        if "--save-db" in sys.argv:
            save_to_db = True
    
    print(f"🎯 Configuration:")
    print(f"   • Limit: {limit} hackathons")
    print(f"   • Enrichment: {'ON' if enable_enrichment else 'OFF'}")
    print(f"   • Save to DB: {'ON' if save_to_db else 'OFF'}")
    
    # Create and run pipeline
    pipeline = HackathonMini(use_test_db=True)
    results = pipeline.run(
        limit=limit,
        enable_enrichment=enable_enrichment,
        save_to_db=save_to_db
    )
    
    # Summary
    print(f"\n🎉 Pipeline Summary:")
    print(f"   • Total hackathons: {len(results)}")
    print(f"   • Output files: output/hackathons_mini.*")
    
    if results:
        locations = [h.get('location', 'Unknown') for h in results]
        unique_locations = set(locations)
        print(f"   • Locations found: {len(unique_locations)}")
        print(f"   • Sample locations: {list(unique_locations)[:3]}")


if __name__ == "__main__":
    main() 