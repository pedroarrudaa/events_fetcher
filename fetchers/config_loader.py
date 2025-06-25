"""
Configuration Loader - Centralized configuration management for event sources.

This module loads and validates YAML configuration files, providing
a clean interface for accessing event-specific settings without
hardcoded values scattered throughout the codebase.
"""

import os
import yaml
from typing import Dict, Any, List, Optional
from pathlib import Path
import logging

from shared_utils import logger


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""
    pass


class ConfigLoader:
    """
    Centralized configuration loader for event discovery sources.
    
    Loads YAML configuration files and provides validated access
    to event-specific settings, eliminating hardcoded values.
    """
    
    def __init__(self, config_dir: str = None):
        """
        Initialize configuration loader.
        
        Args:
            config_dir: Directory containing configuration files.
                       Defaults to 'configs' in project root.
        """
        if config_dir is None:
            # Default to configs directory in project root
            project_root = Path(__file__).parent.parent
            config_dir = project_root / 'configs'
        
        self.config_dir = Path(config_dir)
        self._configs = {}
        self._loaded = False
    
    def load_all_configs(self) -> Dict[str, Dict[str, Any]]:
        """
        Load all configuration files.
        
        Returns:
            Dictionary mapping event types to their configurations
        """
        if self._loaded:
            return self._configs
        
        logger.log("info", f"Loading configurations from {self.config_dir}")
        
        try:
            # Load conference configuration
            conference_config = self._load_config_file('conference_sources.yaml')
            self._configs['conference'] = conference_config
            
            # Load hackathon configuration  
            hackathon_config = self._load_config_file('hackathon_sources.yaml')
            self._configs['hackathon'] = hackathon_config
            
            # Validate loaded configurations
            self._validate_configurations()
            
            self._loaded = True
            logger.log("info", "All configurations loaded successfully")
            
        except Exception as e:
            logger.log("error", f"Failed to load configurations: {str(e)}")
            raise ConfigurationError(f"Configuration loading failed: {str(e)}")
        
        return self._configs
    
    def get_config(self, event_type: str) -> Dict[str, Any]:
        """
        Get configuration for specific event type.
        
        Args:
            event_type: 'conference' or 'hackathon'
            
        Returns:
            Configuration dictionary for the event type
        """
        if not self._loaded:
            self.load_all_configs()
        
        if event_type not in self._configs:
            raise ConfigurationError(f"Configuration not found for event type: {event_type}")
        
        return self._configs[event_type]
    
    def get_target_locations(self, event_type: str) -> List[str]:
        """Get target locations for event type."""
        config = self.get_config(event_type)
        return config.get('target_locations', [])
    
    def get_event_keywords(self, event_type: str) -> List[str]:
        """Get event keywords for filtering."""
        config = self.get_config(event_type)
        if event_type == 'conference':
            return config.get('conference_keywords', [])
        elif event_type == 'hackathon':
            return config.get('hackathon_keywords', [])
        return []
    
    def get_sources_config(self, event_type: str) -> List[Dict[str, Any]]:
        """Get source configurations for event type."""
        config = self.get_config(event_type)
        return config.get('sources', [])
    
    def get_trusted_domains(self, event_type: str) -> Dict[str, float]:
        """Get trusted domains with reliability scores."""
        config = self.get_config(event_type)
        return config.get('trusted_domains', {})
    
    def get_discovery_settings(self, event_type: str) -> Dict[str, Any]:
        """Get discovery settings for event type."""
        config = self.get_config(event_type)
        return config.get('discovery_settings', {})
    
    def get_search_queries(self, event_type: str) -> List[str]:
        """Get search query templates."""
        config = self.get_config(event_type)
        return config.get('search_queries', [])
    
    def get_excluded_locations(self, event_type: str) -> List[str]:
        """Get excluded locations (for conferences)."""
        config = self.get_config(event_type)
        return config.get('excluded_locations', [])
    
    def get_online_indicators(self, event_type: str) -> List[str]:
        """Get online indicators (for hackathons)."""
        config = self.get_config(event_type)
        return config.get('online_indicators', [])
    
    def get_devpost_api_config(self) -> Dict[str, Any]:
        """Get Devpost API configuration."""
        hackathon_config = self.get_config('hackathon')
        return hackathon_config.get('devpost_api', {})
    
    def get_quality_scoring_config(self, event_type: str) -> Dict[str, Any]:
        """Get quality scoring configuration."""
        config = self.get_config(event_type)
        return config.get('quality_scoring', {})
    
    def _load_config_file(self, filename: str) -> Dict[str, Any]:
        """Load a single YAML configuration file."""
        config_path = self.config_dir / filename
        
        if not config_path.exists():
            raise ConfigurationError(f"Configuration file not found: {config_path}")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            if not isinstance(config, dict):
                raise ConfigurationError(f"Invalid configuration format in {filename}")
            
            logger.log("info", f"Loaded configuration from {filename}")
            return config
            
        except yaml.YAMLError as e:
            raise ConfigurationError(f"YAML parsing error in {filename}: {str(e)}")
        except Exception as e:
            raise ConfigurationError(f"Error reading {filename}: {str(e)}")
    
    def _validate_configurations(self):
        """Validate loaded configurations for required fields."""
        required_fields = {
            'conference': [
                'target_locations', 'conference_keywords', 'trusted_domains',
                'conference_sites', 'discovery_settings'
            ],
            'hackathon': [
                'target_locations', 'hackathon_keywords', 'sources',
                'discovery_settings'
            ]
        }
        
        for event_type, config in self._configs.items():
            required = required_fields.get(event_type, [])
            
            for field in required:
                if field not in config:
                    raise ConfigurationError(
                        f"Required field '{field}' missing from {event_type} configuration"
                    )
                
                # Check that lists aren't empty
                if isinstance(config[field], list) and not config[field]:
                    logger.log("warning", f"Empty list for {field} in {event_type} configuration")
        
        logger.log("info", "Configuration validation completed")


# Global configuration loader instance
_config_loader = None

def get_config_loader() -> ConfigLoader:
    """
    Get the global configuration loader instance.
    
    Returns:
        ConfigLoader instance
    """
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
        _config_loader.load_all_configs()
    return _config_loader


def get_event_config(event_type: str) -> Dict[str, Any]:
    """
    Convenience function to get configuration for an event type.
    
    Args:
        event_type: 'conference' or 'hackathon'
        
    Returns:
        Configuration dictionary
    """
    return get_config_loader().get_config(event_type)


# NOTE: Configuration loading requires YAML files to be present.
# Manual testing recommended for:
# - YAML file validation and parsing
# - Configuration field completeness
# - Default value handling
# This module centralizes all hardcoded configuration values. 