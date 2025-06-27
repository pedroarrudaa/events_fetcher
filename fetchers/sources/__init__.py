"""Sources package - Event discovery from various platforms."""

# Import from event_sources only (unified implementation)
from .event_sources import discover_conferences, discover_hackathons, discover_events

__all__ = ['discover_conferences', 'discover_hackathons', 'discover_events'] 