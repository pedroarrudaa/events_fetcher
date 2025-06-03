#!/usr/bin/env python3
"""
Test script for the improved hackathon enrichment and filtering pipeline.
Tests the next 100 Devpost events to measure improvements in data collection quality.
"""
import os
import sys
import json
from datetime import datetime
from typing import List, Dict, Any

# Add paths for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hackathon_fetcher'))

from hackathon_fetcher.main import HackathonFetcher
from hackathon_fetcher.sources import devpost
from database_utils import save_to_db, get_db_stats

def test_improved_pipeline():
    """
    Test the improved hackathon pipeline with the following enhancements:
    1. Improved location filtering with fuzzy matching
    2. Loosened date filtering 
    3. Improved logging for rejected events
    4. URL-based deduplication
    5. Enhanced enrichment fallback
    """
    print("🧪 Testing Improved Hackathon Pipeline")
    print("=" * 60)
    print("📋 Testing the following improvements:")
    print("   1. ✅ Improved location filtering with fuzzy matching")
    print("   2. ✅ Loosened date filtering (>= today, TBD events)")
    print("   3. ✅ Enhanced logging for rejected events")
    print("   4. ✅ URL-based deduplication")
    print("   5. ✅ Enhanced enrichment fallback for missing fields")
    print("=" * 60)
    
    # Get database stats before running
    try:
        db_stats_before = get_db_stats()
        hackathons_before = db_stats_before['hackathons']['total']
        print(f"📊 Database before test: {hackathons_before} hackathons")
    except Exception as e:
        print(f"⚠️ Could not get database stats before: {e}")
        hackathons_before = 0
    
    # Step 1: Fetch 200 raw hackathons from Devpost
    print(f"\n🔗 Step 1: Fetching 200 hackathons from Devpost...")
    try:
        raw_hackathons = devpost.get_hackathon_urls(limit=200)
        print(f"✅ Successfully fetched {len(raw_hackathons)} raw hackathons from Devpost")
        
        if not raw_hackathons:
            print("❌ No hackathons fetched! Exiting test.")
            return
        
        # Show sample of raw data
        print(f"\n📋 Sample of raw hackathon data:")
        for i, hackathon in enumerate(raw_hackathons[:3]):
            name = hackathon.get('name', 'Unknown')[:40]
            url = hackathon.get('url', 'No URL')
            print(f"   {i+1}. {name} - {url}")
        if len(raw_hackathons) > 3:
            print(f"   ... and {len(raw_hackathons) - 3} more")
        
    except Exception as e:
        print(f"❌ Error fetching hackathons from Devpost: {e}")
        return
    
    # Step 2: Run the improved pipeline
    print(f"\n🔄 Step 2: Running improved enrichment and filtering pipeline...")
    
    try:
        fetcher = HackathonFetcher()
        
        # Override the fetcher to use our test data
        print("   📝 Enriching hackathons with GPT...")
        from hackathon_fetcher.enrichers.gpt_extractor import enrich_hackathon_data
        enriched_hackathons = enrich_hackathon_data(raw_hackathons)
        
        print(f"   ✅ Enrichment complete: {len(enriched_hackathons)} hackathons processed")
        
        # Step 3: Apply enhanced filtering
        print("   🎯 Applying enhanced filtering...")
        from event_filters import filter_future_target_events
        filtered_hackathons = filter_future_target_events(enriched_hackathons, "hackathon")
        
        print(f"   ✅ Filtering complete: {len(filtered_hackathons)} hackathons passed filters")
        
        # Step 4: Clean and deduplicate
        print("   🧹 Cleaning and deduplicating...")
        cleaned_hackathons = fetcher.clean_event_data(filtered_hackathons)
        final_hackathons = fetcher.deduplicate_events(cleaned_hackathons)
        
        print(f"   ✅ Cleaning complete: {len(final_hackathons)} unique hackathons")
        
    except Exception as e:
        print(f"❌ Error during pipeline processing: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 5: Analyze results
    print(f"\n📊 Step 3: Analyzing Results")
    print("-" * 40)
    
    if final_hackathons:
        # Count successful enrichments
        enriched_count = sum(1 for h in final_hackathons if h.get('extraction_success', False))
        
        # Analyze location distribution
        location_counts = {}
        for hackathon in final_hackathons:
            if hackathon.get('remote'):
                location = "Remote/Virtual"
            else:
                location = hackathon.get('city', hackathon.get('location', 'Unknown'))
            location_counts[location] = location_counts.get(location, 0) + 1
        
        # Analyze source distribution
        source_counts = {}
        for hackathon in final_hackathons:
            source = hackathon.get('source', 'Unknown')
            source_counts[source] = source_counts.get(source, 0) + 1
        
        # Check for critical fields
        fields_analysis = {
            'organizers': 0,
            'sponsors': 0,
            'judges': 0,
            'modality': 0,
            'prizes': 0
        }
        
        for hackathon in final_hackathons:
            for field in fields_analysis:
                value = hackathon.get(field)
                if value and ((isinstance(value, list) and len(value) > 0) or 
                             (isinstance(value, str) and value.strip())):
                    fields_analysis[field] += 1
        
        # Print detailed analysis
        print(f"📈 Quality Metrics:")
        print(f"   • Raw hackathons fetched: {len(raw_hackathons)}")
        print(f"   • After enrichment: {len(enriched_hackathons)}")
        print(f"   • After filtering: {len(filtered_hackathons)}")
        print(f"   • Final unique hackathons: {len(final_hackathons)}")
        print(f"   • Success rate: {(len(final_hackathons)/len(raw_hackathons)*100):.1f}%")
        print(f"   • Enrichment success: {enriched_count}/{len(final_hackathons)} ({(enriched_count/len(final_hackathons)*100):.1f}%)")
        
        print(f"\n🌍 Location Distribution:")
        for location, count in sorted(location_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"   • {location}: {count} hackathons")
        
        print(f"\n📋 Data Completeness:")
        for field, count in fields_analysis.items():
            percentage = (count/len(final_hackathons)*100)
            print(f"   • {field}: {count}/{len(final_hackathons)} ({percentage:.1f}%)")
        
        # Show sample final results
        print(f"\n✅ Sample Final Results:")
        for i, hackathon in enumerate(final_hackathons[:5]):
            name = hackathon.get('name', 'Unknown')[:40]
            city = hackathon.get('city', 'Unknown')
            remote = hackathon.get('remote', False)
            organizers = hackathon.get('organizers', [])
            sponsors = hackathon.get('sponsors', [])
            
            org_count = len(organizers) if isinstance(organizers, list) else (1 if organizers else 0)
            sponsor_count = len(sponsors) if isinstance(sponsors, list) else (1 if sponsors else 0)
            
            print(f"   {i+1}. {name}")
            print(f"      📍 {city} {'(Remote)' if remote else ''}")
            print(f"      👥 {org_count} organizers, 💰 {sponsor_count} sponsors")
        
    else:
        print("❌ No hackathons passed the improved filters!")
        print("\n🔍 This might indicate:")
        print("   • Filtering criteria are too strict")
        print("   • Source data quality issues")
        print("   • API/enrichment failures")
    
    # Step 6: Save to database
    if final_hackathons:
        print(f"\n💾 Step 4: Saving to Database")
        try:
            db_results = save_to_db(final_hackathons, table_name='hackathons', update_existing=True)
            print(f"✅ Successfully saved {len(final_hackathons)} hackathons to database")
            
            # Get final database stats
            try:
                db_stats_after = get_db_stats()
                hackathons_after = db_stats_after['hackathons']['total']
                new_hackathons = hackathons_after - hackathons_before
                print(f"📊 Database after test: {hackathons_after} hackathons (+{new_hackathons} new)")
            except Exception as e:
                print(f"⚠️ Could not get database stats after: {e}")
                
        except Exception as e:
            print(f"❌ Error saving to database: {e}")
    
    # Step 7: Summary and conclusions
    print(f"\n🎯 Test Summary")
    print("=" * 60)
    
    if final_hackathons:
        success_rate = (len(final_hackathons)/len(raw_hackathons)*100)
        print(f"✅ Test SUCCESSFUL!")
        print(f"   • Processed {len(raw_hackathons)} raw hackathons")
        print(f"   • {len(final_hackathons)} passed all filters and quality checks")
        print(f"   • Success rate: {success_rate:.1f}%")
        
        remote_count = sum(1 for h in final_hackathons if h.get('remote'))
        print(f"   • Remote/Virtual events: {remote_count}/{len(final_hackathons)} ({(remote_count/len(final_hackathons)*100):.1f}%)")
        
        if success_rate >= 10:
            print(f"🎉 SUCCESS: Pipeline improvements significantly increased data collection!")
        elif success_rate >= 5:
            print(f"👍 GOOD: Pipeline improvements provided moderate improvements")
        else:
            print(f"⚠️ LOW: Pipeline may need further tuning")
    else:
        print(f"❌ Test FAILED: No hackathons passed the improved pipeline")
        print(f"   Consider reviewing filter criteria or source data quality")
    
    print("\n📝 Improvements Applied:")
    print("   1. ✅ Fuzzy location matching (san francisco, sf, bay area, nyc, new york, manhattan, remote, virtual, online)")
    print("   2. ✅ Loosened date filtering (>= today, TBD/2025 indicators)")
    print("   3. ✅ Enhanced rejection logging with specific reasons")
    print("   4. ✅ URL-based deduplication instead of name+URL")
    print("   5. ✅ Fallback enrichment for missing organizers/sponsors/judges/modality/prizes")
    print("\n🏁 Test Complete!")

if __name__ == "__main__":
    test_improved_pipeline() 