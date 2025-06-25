"""
Unit tests for BaseSourceDiscovery class.

Tests the common functionality extracted into the base class to ensure
the refactoring maintains correct behavior.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fetchers.sources.base_source import BaseSourceDiscovery
from event_type_configs import get_event_config


class TestableSourceDiscovery(BaseSourceDiscovery):
    """Testable implementation of BaseSourceDiscovery for unit testing."""
    
    def _setup_configurations(self):
        """Setup test configurations."""
        self.test_keywords = ['test', 'demo', 'sample']
        self.test_locations = ['san francisco', 'new york']
        self.trusted_domains = {'example.com': 0.9, 'test.com': 0.8}
    
    def _get_event_keywords(self) -> List[str]:
        """Return test keywords."""
        return self.test_keywords
    
    def _get_target_locations(self) -> List[str]:
        """Return test locations."""
        return self.test_locations


class TestBaseSourceDiscovery(unittest.TestCase):
    """Test cases for BaseSourceDiscovery class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.source = TestableSourceDiscovery('test')
    
    def test_initialization(self):
        """Test that the base class initializes correctly."""
        self.assertEqual(self.source.event_type, 'test')
        self.assertIsNotNone(self.source.scraper)
        self.assertIsNotNone(self.source.enricher)
        self.assertIsNotNone(self.source.query_generator)
    
    def test_get_event_keywords(self):
        """Test that event keywords are returned correctly."""
        keywords = self.source._get_event_keywords()
        self.assertEqual(keywords, ['test', 'demo', 'sample'])
    
    def test_get_target_locations(self):
        """Test that target locations are returned correctly."""
        locations = self.source._get_target_locations()
        self.assertEqual(locations, ['san francisco', 'new york'])
    
    def test_is_target_location_positive(self):
        """Test location matching for valid locations."""
        # Test event with San Francisco
        event = {
            'name': 'Test Conference in San Francisco',
            'description': 'A great tech event',
            'location': 'SF',
            'url': 'https://example.com/event'
        }
        self.assertTrue(self.source._is_target_location(event))
        
        # Test event with New York
        event['name'] = 'Test Hackathon NYC'
        event['location'] = 'New York'
        self.assertTrue(self.source._is_target_location(event))
    
    def test_is_target_location_negative(self):
        """Test location matching for invalid locations."""
        # Test event with non-target location
        event = {
            'name': 'Test Conference in London',
            'description': 'A great tech event',
            'location': 'London, UK',
            'url': 'https://example.com/event'
        }
        self.assertFalse(self.source._is_target_location(event))
    
    def test_process_search_result_valid(self):
        """Test processing valid search results."""
        result = {
            'url': 'https://example.com/test-conference',
            'title': 'Test Conference 2025',
            'content': 'This is a demo conference with test speakers'
        }
        
        processed = self.source._process_search_result(result, 'test_source', 'test query')
        
        self.assertIsNotNone(processed)
        self.assertEqual(processed['name'], 'Test Conference 2025')
        self.assertEqual(processed['url'], 'https://example.com/test-conference')
        self.assertEqual(processed['source'], 'test_source')
        self.assertEqual(processed['discovery_method'], 'search')
        self.assertIn('quality_score', processed)
    
    def test_process_search_result_irrelevant(self):
        """Test processing irrelevant search results."""
        result = {
            'url': 'https://example.com/random-page',
            'title': 'Random Page',
            'content': 'This is about cooking and recipes'
        }
        
        processed = self.source._process_search_result(result, 'test_source', 'test query')
        self.assertIsNone(processed)
    
    def test_calculate_quality_score_trusted_domain(self):
        """Test quality score calculation for trusted domains."""
        score = self.source._calculate_quality_score(
            'https://example.com/event',
            'This is a test demo event with detailed content and speaker information'
        )
        
        # Should be high due to trusted domain
        self.assertGreater(score, 0.8)
    
    def test_calculate_quality_score_unknown_domain(self):
        """Test quality score calculation for unknown domains."""
        score = self.source._calculate_quality_score(
            'https://unknown.com/event',
            'Short text'
        )
        
        # Should be lower due to unknown domain and short content
        self.assertLess(score, 0.7)
    
    def test_deduplicate_and_rank(self):
        """Test deduplication and ranking functionality."""
        events = [
            {'url': 'https://example.com/event1', 'quality_score': 0.8},
            {'url': 'https://example.com/event2', 'quality_score': 0.9},
            {'url': 'https://example.com/event1', 'quality_score': 0.7},  # Duplicate
            {'url': 'https://example.com/event3', 'quality_score': 0.6}
        ]
        
        unique_events = self.source._deduplicate_and_rank(events)
        
        # Should have 3 unique events
        self.assertEqual(len(unique_events), 3)
        
        # Should be sorted by quality score (highest first)
        scores = [event['quality_score'] for event in unique_events]
        self.assertEqual(scores, sorted(scores, reverse=True))
        
        # Should contain the higher-scored version of the duplicate
        urls = [event['url'] for event in unique_events]
        self.assertIn('https://example.com/event1', urls)
        self.assertIn('https://example.com/event2', urls)
        self.assertIn('https://example.com/event3', urls)
    
    def test_build_page_url(self):
        """Test URL pagination building."""
        # Test page 1 (should return original URL)
        url1 = self.source._build_page_url('https://example.com/events', 1)
        self.assertEqual(url1, 'https://example.com/events')
        
        # Test devpost pagination
        url2 = self.source._build_page_url('https://devpost.com/hackathons', 2)
        self.assertEqual(url2, 'https://devpost.com/hackathons?page=2')
        
        # Test eventbrite pagination
        url3 = self.source._build_page_url('https://eventbrite.com/events', 3)
        self.assertEqual(url3, 'https://eventbrite.com/events?page=3')
    
    def test_is_aggregator_url(self):
        """Test aggregator URL detection."""
        # Test aggregator URLs
        self.assertTrue(self.source._is_aggregator_url('https://example.com/events/list'))
        self.assertTrue(self.source._is_aggregator_url('https://example.com/hackathons/calendar'))
        self.assertTrue(self.source._is_aggregator_url('https://example.com/conferences/upcoming'))
        
        # Test non-aggregator URLs
        self.assertFalse(self.source._is_aggregator_url('https://example.com/single-event'))
        self.assertFalse(self.source._is_aggregator_url('https://example.com/about'))
    
    @patch('fetchers.sources.base_source.logger')
    def test_discover_all_events_integration(self, mock_logger):
        """Test the main discovery method integration."""
        # NOTE: This is a basic integration test.
        # Full testing requires manual verification of external APIs
        
        # Mock the discovery methods
        self.source._search_with_external_apis = Mock(return_value=[
            {'name': 'Test Event 1', 'url': 'https://example.com/1', 'quality_score': 0.8}
        ])
        self.source._scrape_configured_sites = Mock(return_value=[
            {'name': 'Test Event 2', 'url': 'https://example.com/2', 'quality_score': 0.7}
        ])
        
        # Test discovery
        events = self.source.discover_all_events(max_results=10)
        
        # Should return combined results
        self.assertEqual(len(events), 2)
        self.assertTrue(mock_logger.log.called)


class TestEventTypeConfigIntegration(unittest.TestCase):
    """Test integration with event type configurations."""
    
    def test_conference_config_loading(self):
        """Test that conference configuration loads correctly."""
        config = get_event_config('conference')
        
        self.assertEqual(config.event_type, 'conference')
        self.assertEqual(config.max_results, 200)
        self.assertEqual(config.table_name, 'conferences')
        self.assertIn('artificial intelligence', config.keywords)
        self.assertIn('san francisco', config.target_locations)
        self.assertIn('virtual', config.excluded_locations)
    
    def test_hackathon_config_loading(self):
        """Test that hackathon configuration loads correctly."""
        config = get_event_config('hackathon')
        
        self.assertEqual(config.event_type, 'hackathon')
        self.assertEqual(config.max_results, 60)
        self.assertEqual(config.table_name, 'hackathons')
        self.assertIn('hackathon', config.keywords)
        self.assertIn('san francisco', config.target_locations)
        # Hackathons don't exclude virtual events
        self.assertEqual(config.excluded_locations, [])
    
    def test_invalid_event_type(self):
        """Test handling of invalid event types."""
        with self.assertRaises(ValueError):
            get_event_config('invalid_type')


if __name__ == '__main__':
    # NOTE: These tests validate the base class functionality and configuration loading.
    # External API integrations and web scraping require manual testing due to:
    # - API rate limits and authentication requirements
    # - Dynamic website content and structure changes  
    # - Network dependencies not suitable for automated testing
    #
    # Manual testing recommended for:
    # - Tavily API integration and search functionality
    # - Devpost API rate limits and response parsing
    # - Website scraping across different platforms
    # - Event filtering logic with real data
    
    unittest.main() 