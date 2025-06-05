#!/usr/bin/env python3
"""
CLI tool for recording manual actions on events.

Usage:
    python record_action.py --event-id=<uuid> --event-type=<hackathon|conference> --action=<archive|reached_out>

Examples:
    python record_action.py --event-id=123e4567-e89b-12d3-a456-426614174000 --event-type=hackathon --action=reached_out
    python record_action.py --event-id=987fcdeb-51a2-43d1-9f12-345678901234 --event-type=conference --action=archive
"""

import argparse
import sys
import os
from datetime import datetime

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database_utils import save_event_action, get_event_action, create_tables

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Record manual actions on events',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--event-id',
        required=True,
        help='UUID of the event'
    )
    
    parser.add_argument(
        '--event-type',
        required=True,
        choices=['hackathon', 'conference'],
        help='Type of event (hackathon or conference)'
    )
    
    parser.add_argument(
        '--action',
        required=True,
        choices=['archive', 'reached_out'],
        help='Action to record (archive or reached_out)'
    )
    
    parser.add_argument(
        '--list',
        action='store_true',
        help='List current action for the specified event'
    )
    
    return parser.parse_args()

def main():
    """Main CLI entry point."""
    print("🎯 Event Action Recorder")
    print("=" * 50)
    
    try:
        args = parse_arguments()
        
        # Ensure database tables exist
        print("🔧 Initializing database...")
        create_tables()
        
        if args.list:
            # List current action for the event
            print(f"\n📋 Checking action for event: {args.event_id}")
            action_data = get_event_action(args.event_id)
            
            if action_data:
                print(f"✅ Found action:")
                print(f"   • Event ID: {action_data['event_id']}")
                print(f"   • Event Type: {action_data['event_type']}")
                print(f"   • Action: {action_data['action']}")
                print(f"   • Timestamp: {action_data['timestamp']}")
            else:
                print(f"📭 No action found for event: {args.event_id}")
        else:
            # Record new action
            print(f"\n📝 Recording action...")
            print(f"   • Event ID: {args.event_id}")
            print(f"   • Event Type: {args.event_type}")
            print(f"   • Action: {args.action}")
            print(f"   • Timestamp: {datetime.utcnow().isoformat()}")
            
            success = save_event_action(args.event_id, args.event_type, args.action)
            
            if success:
                print(f"\n✅ Action recorded successfully!")
                
                # Show the recorded action
                action_data = get_event_action(args.event_id)
                if action_data:
                    print(f"\n📋 Confirmed action:")
                    print(f"   • Action: {action_data['action']}")
                    print(f"   • Timestamp: {action_data['timestamp']}")
            else:
                print(f"\n❌ Failed to record action. Check the event ID and type.")
                sys.exit(1)
        
    except KeyboardInterrupt:
        print(f"\n\n⚠️ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 