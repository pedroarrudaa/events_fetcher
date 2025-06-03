#!/usr/bin/env python3
"""
Test script for GPT validation functionality.
"""
import os
from gpt_validation import validate_event_with_gpt, validate_events_batch

# Test events - mix of legitimate and problematic entries
test_conferences = [
    {
        "name": "AI Summit 2025",
        "description": "Premier artificial intelligence conference featuring keynote speakers, technical sessions, and networking opportunities for ML engineers and data scientists.",
        "url": "https://ai-summit-2025.com/conference",
        "start_date": "2025-03-15",
        "city": "San Francisco",
        "source": "test"
    },
    {
        "name": "Splunk Security Blog",
        "description": "Explore how Splunk blogs help you stay informed about the latest security trends and best practices in cybersecurity.",
        "url": "https://www.splunk.com/blog/security/author/john-smith",
        "start_date": "TBD",
        "city": "TBD",
        "source": "tavily"
    },
    {
        "name": "Databricks Community Profile",
        "description": "User profile page for community member showcasing their contributions and discussions in the Databricks community platform.",
        "url": "https://community.databricks.com/t5/user/viewprofilepage/user-id/12345",
        "start_date": "TBD",
        "city": "TBD",
        "source": "tavily"
    }
]

test_hackathons = [
    {
        "name": "HackAI 2025",
        "description": "24-hour hackathon focused on building AI applications. Teams will compete to create innovative solutions using machine learning and AI technologies.",
        "url": "https://hackai2025.devpost.com",
        "start_date": "2025-04-20",
        "city": "New York",
        "source": "devpost"
    },
    {
        "name": "DataCamp Registration Form",
        "description": "Create your free account to access DataCamp's learning platform for data science and analytics courses.",
        "url": "https://datacamp.com/signup/register",
        "start_date": "TBD",
        "city": "TBD",
        "source": "tavily"
    }
]

def test_individual_validation():
    """Test individual event validation."""
    print("🧪 Testing individual GPT validation...")
    
    for i, event in enumerate(test_conferences, 1):
        print(f"\n📋 Conference {i}: {event['name']}")
        is_valid = validate_event_with_gpt(event, "conference")
        status = "✅ VALID" if is_valid else "❌ REJECTED"
        print(f"   Result: {status}")
    
    for i, event in enumerate(test_hackathons, 1):
        print(f"\n🎯 Hackathon {i}: {event['name']}")
        is_valid = validate_event_with_gpt(event, "hackathon")
        status = "✅ VALID" if is_valid else "❌ REJECTED"
        print(f"   Result: {status}")

def test_batch_validation():
    """Test batch validation functionality."""
    print("\n🧪 Testing batch GPT validation...")
    
    print("\n📋 Conference batch validation:")
    valid_conferences, rejected_conferences = validate_events_batch(test_conferences, "conference")
    print(f"   Valid: {len(valid_conferences)}, Rejected: {len(rejected_conferences)}")
    
    print("\n🎯 Hackathon batch validation:")
    valid_hackathons, rejected_hackathons = validate_events_batch(test_hackathons, "hackathon")
    print(f"   Valid: {len(valid_hackathons)}, Rejected: {len(rejected_hackathons)}")

def main():
    """Run all tests."""
    print("🚀 GPT Validation Test Suite")
    print("=" * 50)
    
    # Check if OpenAI API key is available
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️ OPENAI_API_KEY not found - tests will use fallback behavior")
        print("   (All events will be accepted without actual GPT validation)")
    else:
        print("✅ OPENAI_API_KEY found - running actual GPT validation")
    
    test_individual_validation()
    test_batch_validation()
    
    print("\n✅ Test suite completed!")

if __name__ == "__main__":
    main() 