#!/usr/bin/env python3
"""
Enhanced Events Dashboard Runner with Crawl4AI Integration
Tests and runs hackathon and conference scripts with Crawl4AI support
"""

import asyncio
import json
import sys
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

# Try to import Crawl4AI functionality
try:
    from crawl4ai_integration import (
        Crawl4AIEventScraper, 
        crawl4ai_scrape_url, 
        crawl4ai_discover_events,
        crawl4ai_check_availability,
        test_crawl4ai_integration,
        crawl4ai_scrape_multiple_urls
    )
    CRAWL4AI_AVAILABLE = True
except ImportError as e:
    print(f"  Crawl4AI integration not available: {e}")
    CRAWL4AI_AVAILABLE = False

# Import existing event fetcher
try:
    from event_fetcher import run_event_fetcher
    from database_utils import get_db_manager, Hackathon, Conference
    from shared_utils import logger, EventProcessor, FileManager
except ImportError as e:
    print(f" Failed to import event fetcher modules: {e}")
    print(" Make sure you're in the correct directory and dependencies are installed")
    sys.exit(1)


class EventsDashboardRunner:
    """
    Enhanced runner for the events dashboard with Crawl4AI integration.
    Provides testing, running, and monitoring capabilities.
    """
    
    def __init__(self):
        """Initialize the events dashboard runner."""
        self.crawl4ai_available = CRAWL4AI_AVAILABLE
        self.results = {
            'hackathons': {'success': 0, 'failed': 0, 'total': 0},
            'conferences': {'success': 0, 'failed': 0, 'total': 0},
            'crawl4ai_tests': {'success': False, 'errors': []},
            'start_time': datetime.now(),
            'end_time': None
        }
    
    def print_banner(self):
        """Print a nice banner for the script."""
        print("=" * 80)
        print(" EVENTS DASHBOARD - HACKATHONS & CONFERENCES RUNNER")
        print("=" * 80)
        print(f" Started at: {self.results['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f" Crawl4AI Available: {' Yes' if self.crawl4ai_available else ' No'}")
        print("=" * 80)
    
    async def test_crawl4ai_functionality(self) -> bool:
        """Test Crawl4AI functionality with sample URLs."""
        if not self.crawl4ai_available:
            self.results['crawl4ai_tests']['errors'].append("Crawl4AI not available")
            return False
        
        print("\n TESTING CRAWL4AI FUNCTIONALITY")
        print("-" * 50)
        
        try:
            # Test basic availability check
            print("✓ Checking Crawl4AI availability...")
            available = crawl4ai_check_availability()
            if not available:
                self.results['crawl4ai_tests']['errors'].append("Crawl4AI availability check failed")
                return False
            
            # Test sample event scraping with proper concurrency control
            print(" Testing event page scraping...")
            sample_urls = [
                "https://devpost.com/hackathons",  # Devpost listing
                "https://mlh.io/seasons/2025/events"  # MLH events
            ]
            
            # Use the new batch scraping function with semaphore management
            test_passed = True
            
            try:
                print(f"   Testing {len(sample_urls)} URLs with concurrency control...")
                results = await crawl4ai_scrape_multiple_urls(sample_urls, max_concurrent=2, extract_structured=True)
                
                for i, result in enumerate(results):
                    url = sample_urls[i] if i < len(sample_urls) else "unknown"
                    if result.get('success'):
                        print(f"     Success - URL: {url[:50]}...")
                        print(f"     Word count: {result.get('word_count', 0)}")
                        print(f"     Title: {result.get('title', 'N/A')[:50]}...")
                    else:
                        print(f"     Failed - URL: {url[:50]}... - {result.get('error', 'Unknown error')}")
                        test_passed = False
                        self.results['crawl4ai_tests']['errors'].append(f"Failed to scrape {url}")
                
            except Exception as e:
                print(f"     Exception during batch testing: {str(e)}")
                test_passed = False
                self.results['crawl4ai_tests']['errors'].append(f"Batch testing exception: {str(e)}")
            
            self.results['crawl4ai_tests']['success'] = test_passed
            print(f" Crawl4AI test {' PASSED' if test_passed else ' FAILED'}")
            return test_passed
            
        except Exception as e:
            error_msg = f"Crawl4AI testing failed: {str(e)}"
            print(f" {error_msg}")
            self.results['crawl4ai_tests']['errors'].append(error_msg)
            return False
    
    def run_event_fetcher_with_monitoring(self, event_type: str, limit: int = None) -> Dict[str, Any]:
        """Run event fetcher with monitoring and error tracking."""
        print(f"\n RUNNING {event_type.upper()} FETCHER")
        print("-" * 50)
        
        start_time = time.time()
        
        try:
            # Run the event fetcher
            print(f" Starting {event_type} fetcher...")
            if limit:
                print(f" Processing limit: {limit} events")
            
            run_event_fetcher(event_type, limit)
            
            # Check results in database
            db_stats = self._check_database_stats(event_type)
            
            execution_time = time.time() - start_time
            
            result = {
                'success': True,
                'execution_time': execution_time,
                'database_stats': db_stats,
                'error': None
            }
            
            self.results[f'{event_type}s']['success'] = db_stats.get('total', 0)
            self.results[f'{event_type}s']['total'] = db_stats.get('total', 0)
            
            print(f" {event_type.capitalize()} fetcher completed successfully")
            print(f"  Execution time: {execution_time:.2f}s")
            print(f" Database stats: {db_stats}")
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Failed to run {event_type} fetcher: {str(e)}"
            
            result = {
                'success': False,
                'execution_time': execution_time,
                'database_stats': {},
                'error': error_msg
            }
            
            self.results[f'{event_type}s']['failed'] = 1
            self.results[f'{event_type}s']['total'] = 1
            
            print(f" {error_msg}")
            return result
    
    def _check_database_stats(self, event_type: str) -> Dict[str, int]:
        """Check database statistics for events."""
        try:
            db_manager = get_db_manager()
            
            with db_manager.get_session() as session:
                if event_type == 'hackathon':
                    total = session.query(Hackathon).count()
                    recent = session.query(Hackathon).filter(
                        Hackathon.created_at >= datetime.now().date()
                    ).count()
                else:  # conference
                    total = session.query(Conference).count()
                    recent = session.query(Conference).filter(
                        Conference.created_at >= datetime.now().date()
                    ).count()
            
            return {
                'total': total,
                'recent': recent,  # Added today
            }
            
        except Exception as e:
            print(f"  Could not check database stats: {e}")
            return {'total': 0, 'recent': 0}
    
    async def run_crawl4ai_event_discovery(self, max_events: int = 10) -> Dict[str, Any]:
        """Test Crawl4AI event discovery functionality with proper concurrency control."""
        if not self.crawl4ai_available:
            return {'success': False, 'error': 'Crawl4AI not available'}
        
        print(f"\n TESTING CRAWL4AI EVENT DISCOVERY")
        print("-" * 50)
        
        try:
            # Test event discovery from listing pages with controlled concurrency
            listing_urls = [
                "https://devpost.com/hackathons",
                "https://mlh.io/seasons/2025/events"
            ]
            
            all_discovered = []
            
            for listing_url in listing_urls:
                print(f" Discovering events from: {listing_url}")
                
                try:
                    # Use the updated function with concurrency control
                    events = await crawl4ai_discover_events(
                        listing_url, 
                        max_events=max_events//len(listing_urls),
                        max_concurrent=2  # Conservative concurrency for testing
                    )
                    print(f"   Found {len(events)} events")
                    
                    # Show sample results
                    for i, event in enumerate(events[:3]):  # Show first 3
                        if event.get('success'):
                            title = event.get('title', 'No title')[:40]
                            print(f"    {i+1}. {title}...")
                    
                    all_discovered.extend(events)
                    
                except Exception as e:
                    print(f"   Error discovering from {listing_url}: {e}")
            
            successful_discoveries = sum(1 for e in all_discovered if e.get('success', False))
            
            result = {
                'success': len(all_discovered) > 0,
                'total_discovered': len(all_discovered),
                'successful': successful_discoveries,
                'events': all_discovered
            }
            
            print(f" Discovery results: {successful_discoveries}/{len(all_discovered)} successful")
            return result
            
        except Exception as e:
            error_msg = f"Crawl4AI discovery failed: {str(e)}"
            print(f" {error_msg}")
            return {'success': False, 'error': error_msg}
    
    def print_final_report(self):
        """Print final execution report."""
        self.results['end_time'] = datetime.now()
        execution_time = (self.results['end_time'] - self.results['start_time']).total_seconds()
        
        print("\n" + "=" * 80)
        print(" FINAL EXECUTION REPORT")
        print("=" * 80)
        print(f"  Total execution time: {execution_time:.2f}s")
        print(f" Completed at: {self.results['end_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Event fetcher results
        print("\n EVENT FETCHER RESULTS:")
        for event_type in ['hackathons', 'conferences']:
            stats = self.results[event_type]
            print(f"  {event_type.capitalize():12}: {stats['success']:3d} success, {stats['failed']:3d} failed, {stats['total']:3d} total")
        
        # Crawl4AI results
        print(f"\n CRAWL4AI INTEGRATION:")
        crawl4ai_stats = self.results['crawl4ai_tests']
        print(f"  Status: {' Working' if crawl4ai_stats['success'] else ' Failed'}")
        if crawl4ai_stats['errors']:
            print(f"  Errors: {len(crawl4ai_stats['errors'])}")
            for error in crawl4ai_stats['errors'][:3]:  # Show first 3 errors
                print(f"    • {error}")
        
        print("=" * 80)
    
    async def run_comprehensive_test(self, limit_per_type: int = 5):
        """Run comprehensive test of all functionality."""
        self.print_banner()
        
        # Test Crawl4AI functionality
        await self.test_crawl4ai_functionality()
        
        # Test Crawl4AI event discovery
        if self.crawl4ai_available:
            await self.run_crawl4ai_event_discovery(max_events=10)
        
        # Run hackathons fetcher
        hackathon_result = self.run_event_fetcher_with_monitoring('hackathon', limit_per_type)
        
        # Run conferences fetcher  
        conference_result = self.run_event_fetcher_with_monitoring('conference', limit_per_type)
        
        # Print final report
        self.print_final_report()
        
        return {
            'hackathons': hackathon_result,
            'conferences': conference_result,
            'crawl4ai_available': self.crawl4ai_available,
            'overall_success': (
                hackathon_result.get('success', False) and 
                conference_result.get('success', False)
            )
        }


async def main():
    """Main execution function."""
    print(" Starting Events Dashboard with Crawl4AI Integration...")
    
    # Create runner instance
    runner = EventsDashboardRunner()
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Run events dashboard with Crawl4AI integration')
    parser.add_argument('--limit', type=int, default=5, help='Limit events per type (default: 5)')
    parser.add_argument('--test-only', action='store_true', help='Only run Crawl4AI tests')
    parser.add_argument('--hackathons-only', action='store_true', help='Only run hackathons fetcher')
    parser.add_argument('--conferences-only', action='store_true', help='Only run conferences fetcher')
    
    args = parser.parse_args()
    
    try:
        if args.test_only:
            # Only test Crawl4AI functionality
            runner.print_banner()
            await runner.test_crawl4ai_functionality()
            if runner.crawl4ai_available:
                await runner.run_crawl4ai_event_discovery()
        
        elif args.hackathons_only:
            # Only run hackathons
            runner.print_banner()
            runner.run_event_fetcher_with_monitoring('hackathon', args.limit)
        
        elif args.conferences_only:
            # Only run conferences
            runner.print_banner()
            runner.run_event_fetcher_with_monitoring('conference', args.limit)
        
        else:
            # Run comprehensive test
            await runner.run_comprehensive_test(args.limit)
        
        runner.print_final_report()
        
    except KeyboardInterrupt:
        print("\n Execution interrupted by user")
        runner.print_final_report()
        sys.exit(1)
    except Exception as e:
        print(f"\n Unexpected error: {e}")
        runner.print_final_report()
        sys.exit(1)


if __name__ == "__main__":
    # Run the main function
    asyncio.run(main()) 