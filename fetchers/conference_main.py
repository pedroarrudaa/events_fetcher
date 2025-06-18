"""
Conference Fetcher - Legacy wrapper using unified event fetcher.

This module maintains backward compatibility while using the new
unified event fetcher architecture.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from event_fetcher import run_event_fetcher


def main(limit: int = None):
    """
    Main conference fetching function - legacy wrapper.
    
    Args:
        limit: Maximum number of conferences to process (optional)
    """
    run_event_fetcher('conference', limit)


if __name__ == "__main__":
    # Parse command line arguments for limit
    limit = None
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
            if limit <= 0:
                print("Limit must be a positive integer")
                sys.exit(1)
        except ValueError:
            print("Invalid limit value. Please provide a positive integer.")
            sys.exit(1)
    
    main(limit) 