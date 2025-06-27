"""
Tests for BaseSourceDiscovery - Unified source discovery functionality.

This module tests the base class that eliminates duplicate code patterns
between conference and hackathon source discovery modules.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

# Import the modules to test
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fetchers.sources.base_source_discovery import BaseSourceDiscovery, BaseSiteConfig


class TestSourceDiscovery(BaseSourceDiscovery):
    """Test implementation of BaseSourceDiscovery for testing."""
    
    def _init_event_config(self):
        """Initialize test configuration."""
        self.test_keywords = ['test', 'event', 'sample']
        self.test_sources = [
            {
                'name': 'TestSource',
                'base_url': 'https://example.com',
                'search_urls': ['https://example.com/events'],
                'url_patterns': ['/event/'],
                'max_pages': 1,
                'reliability': 0.8,
                'use_api': False
            }
        ]
    
    def get_event_keywords(self) -> List[str]:
        """Return test keywords."""
        return self.test_keywords
    
    def get_sources_config(self) -> List[Dict[str, Any]]:
        """Return test source configuration."""
        return self.test_sources
    
    def _is_relevant_event(self, url: str, text: str, source_config: Dict[str, Any]) -> bool:
        """Check if content is relevant for testing."""
        return any(keyword in text.lower() for keyword in self.test_keywords)


class TestBaseSourceDiscovery(unittest.TestCase):
    """Test cases for BaseSourceDiscovery functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.discovery = TestSourceDiscovery('test')
    
    def test_initialization(self):
        """Test that the base class initializes correctly."""
        self.assertEqual(self.discovery.event_type, 'test')
        self.assertIsNotNone(self.discovery.scraper)
        self.assertIsNotNone(self.discovery.enricher)
        self.assertIsNotNone(self.discovery.query_generator)
    
    def test_get_event_keywords(self):
        """Test event keywords retrieval."""
        keywords = self.discovery.get_event_keywords()
        self.assertIn('test', keywords)
        self.assertIn('event', keywords)
        self.assertIn('sample', keywords)
    
    def test_get_sources_config(self):
        """Test source configuration retrieval."""
        sources = self.discovery.get_sources_config()
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]['name'], 'TestSource')
        self.assertEqual(sources[0]['reliability'], 0.8)
    
    def test_clean_event_name(self):
        """Test event name cleaning functionality."""
        # Test normal case
        clean_name = self.discovery._clean_event_name("  Test Event Name  ")
        self.assertEqual(clean_name, "Test Event Name")
        
        # Test empty name
        clean_name = self.discovery._clean_event_name("")
        self.assertEqual(clean_name, "Unknown Test")
        
        # Test long name truncation
        long_name = "A" * 150
        clean_name = self.discovery._clean_event_name(long_name)
        self.assertEqual(len(clean_name), 100)
    
    def test_calculate_quality_score(self):
        """Test quality score calculation."""
        source_config = {'reliability': 0.7}
        
        # Test base scoring
        score = self.discovery._calculate_quality_score(
            "https://example.com/event", 
            "Test event for 2025", 
            source_config
        )
        
        # Should get base score + year bonus + detail bonus
        expected_min = 0.7 + 0.1 + 0.05  # reliability + year + detail
        self.assertGreaterEqual(score, expected_min)
        self.assertLessEqual(score, 1.0)
    
    def test_deduplicate_and_rank(self):
        """Test deduplication and ranking functionality."""
        events = [
            {'url': 'https://example.com/event1', 'quality_score': 0.8},
            {'url': 'https://example.com/event2', 'quality_score': 0.9},
            {'url': 'https://example.com/event1', 'quality_score': 0.7},  # Duplicate
            {'url': 'https://example.com/event3', 'quality_score': 0.6}
        ]
        
        unique_events = self.discovery._deduplicate_and_rank(events)
        
        # Should have 3 unique events
        self.assertEqual(len(unique_events), 3)
        
        # Should be ranked by quality (highest first)
        scores = [event['quality_score'] for event in unique_events]
        self.assertEqual(scores, sorted(scores, reverse=True))
    
    def test_build_page_url(self):
        """Test page URL building for pagination."""
        base_url = "https://example.com/events"
        
        # Page 1 should return original URL
        page1_url = self.discovery._build_page_url(base_url, 1)
        self.assertEqual(page1_url, base_url)
        
        # Page 2+ should add pagination
        page2_url = self.discovery._build_page_url(base_url, 2)
        self.assertIn("page=2", page2_url)
    
    def test_is_valid_url_pattern(self):
        """Test URL pattern validation."""
        source_config = {'url_patterns': ['/event/', '/conference/']}
        
        # Valid URL
        self.assertTrue(self.discovery._is_valid_url_pattern(
            "https://example.com/event/123", source_config))
        
        # Invalid URL
        self.assertFalse(self.discovery._is_valid_url_pattern(
            "https://example.com/blog/post", source_config))
    
    def test_has_event_keywords(self):
        """Test event keyword detection."""
        # Text with keywords
        self.assertTrue(self.discovery._has_event_keywords("This is a test event"))
        
        # Text without keywords
        self.assertFalse(self.discovery._has_event_keywords("This is about something else"))


class TestBaseSiteConfig(unittest.TestCase):
    """Test cases for BaseSiteConfig helper class."""
    
    def test_site_config_creation(self):
        """Test site configuration creation."""
        config = BaseSiteConfig(
            name="Test Site",
            base_url="https://example.com",
            search_urls=["https://example.com/search"],
            url_patterns=["/event/"],
            reliability=0.9
        )
        
        self.assertEqual(config.name, "Test Site")
        self.assertEqual(config.reliability, 0.9)
        self.assertEqual(len(config.search_urls), 1)
    
    def test_site_config_to_dict(self):
        """Test converting site configuration to dictionary."""
        config = BaseSiteConfig(
            name="Test Site",
            base_url="https://example.com",
            search_urls=["https://example.com/search"]
        )
        
        config_dict = config.to_dict()
        
        self.assertIn('name', config_dict)
        self.assertIn('base_url', config_dict)
        self.assertIn('search_urls', config_dict)
        self.assertEqual(config_dict['name'], "Test Site")


if __name__ == '__main__':
    # NOTE: These tests focus on the core base class functionality
    # Manual testing recommended for:
    # - Integration with actual website scraping
    # - Configuration file loading and validation
    # - External API interactions
    # - Rate limiting effectiveness
    
    print("Running BaseSourceDiscovery tests...")
    print("NOTE: Manual testing required for external integrations")
    
    unittest.main() 