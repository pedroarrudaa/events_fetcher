"""
GPT-based validation utility for events before database insertion.
This prevents blog posts, profiles, service pages, and duplicated events from polluting the DB.
"""
import os
import logging
from typing import Dict, Any, Optional
from openai import OpenAI

# Configure logging
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = None
try:
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if openai_api_key:
        # Initialize with basic client to avoid proxies parameter issues
        try:
            import httpx
            # Create a custom httpx client without the problematic proxies parameter
            custom_httpx_client = httpx.Client()
            client = OpenAI(api_key=openai_api_key, http_client=custom_httpx_client)
        except Exception as e:
            # Fallback: try basic initialization without custom client
            try:
                client = OpenAI(api_key=openai_api_key)
            except Exception as e2:
                logger.error(f"❌ Failed to initialize OpenAI client: {e2}")
                client = None
    else:
        logger.warning("⚠️ OPENAI_API_KEY not found in environment variables")
except Exception as e:
    logger.error(f"❌ Failed to initialize OpenAI client: {e}")
    client = None

def validate_event_with_gpt(event: Dict[str, Any], event_type: str = "conference") -> bool:
    """
    Validate if an event is legitimate using GPT.
    
    Args:
        event: Event dictionary with name, description, url, etc.
        event_type: Type of event ("conference" or "hackathon")
        
    Returns:
        True if the event appears to be legitimate, False otherwise
    """
    if not client:
        logger.warning("⚠️ GPT validation skipped - OpenAI client not initialized")
        return True  # Default to accepting if GPT is unavailable
    
    try:
        # Extract event details with safe defaults
        name = event.get('name', 'No name provided')
        description = event.get('description', 'No description provided')
        short_description = event.get('short_description', '')
        url = event.get('url', 'No URL provided')
        start_date = event.get('start_date', 'No date provided')
        source = event.get('source', 'Unknown source')
        location = event.get('city', 'No location provided')
        
        # Combine descriptions for better context
        full_description = f"{description} {short_description}".strip()
        if not full_description:
            full_description = "No description available"
        
        prompt = f"""
You are validating {event_type} data for a tech events database. 

Analyze the following event and determine if it's a legitimate tech {event_type}. 
Return ONLY "YES" or "NO" - no explanation needed.

Event Details:
- Name: {name}
- Description: {full_description}
- URL: {url}
- Start Date: {start_date}
- Location: {location}
- Source: {source}

REJECT if it's any of these:
- Blog posts or articles
- User profiles or community profiles  
- Status pages or system monitoring pages
- Ticketing tools or event management platforms
- Company marketing pages or product demos
- Educational courses or tutorials
- Business service pages
- Sign-up forms or subscription pages
- Documentation or help pages
- Job postings or career pages

ACCEPT if it's a legitimate tech {event_type} with:
- Clear event dates and schedule
- Speaker lineup or agenda
- Registration information
- Venue details (for in-person) or virtual event access
- Professional tech focus (AI, ML, software development, etc.)

Answer: YES or NO
        """.strip()

        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Using more cost-effective model
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=10  # Only need YES/NO
        )
        
        result = response.choices[0].message.content.strip().upper()
        is_valid = result == "YES"
        
        # Log the decision for monitoring
        if not is_valid:
            logger.info(f"🚫 GPT rejected {event_type}: {name} - {url}")
        else:
            logger.debug(f"✅ GPT approved {event_type}: {name}")
            
        return is_valid
        
    except Exception as e:
        logger.error(f"❌ GPT validation error for {event.get('name', 'Unknown')}: {e}")
        # Default to accepting if validation fails to avoid blocking legitimate events
        return True

def validate_events_batch(events: list, event_type: str = "conference") -> tuple:
    """
    Validate a batch of events using GPT.
    
    Args:
        events: List of event dictionaries
        event_type: Type of events ("conference" or "hackathon")
        
    Returns:
        Tuple of (valid_events, rejected_events)
    """
    if not events:
        return [], []
    
    valid_events = []
    rejected_events = []
    
    logger.info(f"🔍 GPT validating {len(events)} {event_type}s...")
    
    for i, event in enumerate(events, 1):
        try:
            if validate_event_with_gpt(event, event_type):
                valid_events.append(event)
            else:
                rejected_events.append(event)
                
            # Progress indicator for large batches
            if i % 10 == 0:
                logger.info(f"   Processed {i}/{len(events)} events...")
                
        except Exception as e:
            logger.error(f"❌ Error validating event {i}: {e}")
            # Default to accepting on error
            valid_events.append(event)
    
    logger.info(f"✅ GPT validation complete: {len(valid_events)} accepted, {len(rejected_events)} rejected")
    
    # Log sample rejections for monitoring
    if rejected_events:
        logger.info("🚫 Sample rejected events:")
        for event in rejected_events[:3]:
            name = event.get('name', 'Unknown')[:50]
            url = event.get('url', 'No URL')
            logger.info(f"   - {name}... → {url}")
    
    return valid_events, rejected_events 