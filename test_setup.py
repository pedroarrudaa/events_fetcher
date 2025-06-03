#!/usr/bin/env python3
"""
Test script to verify the Events Dashboard setup
"""
import requests
import json
import sys

def test_backend():
    """Test if the backend is running and responding correctly."""
    base_url = "http://localhost:8000"
    
    print("🧪 Testing Events Dashboard Backend...")
    print("=" * 50)
    
    # Test 1: Basic connectivity
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        if response.status_code == 200:
            print("✅ Backend is running and accessible")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Backend returned status code: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Could not connect to backend: {e}")
        print("   Make sure to run: python backend.py")
        return False
    
    # Test 2: Health check
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            health_data = response.json()
            print("✅ Health check passed")
            print(f"   Status: {health_data.get('status')}")
            print(f"   Database: {health_data.get('database')}")
            if health_data.get('database') == 'disconnected':
                print("   📝 Note: Using mock data (database not connected)")
        else:
            print(f"❌ Health check failed with status: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Health check failed: {e}")
    
    # Test 3: Events endpoint
    try:
        response = requests.get(f"{base_url}/events", timeout=10)
        if response.status_code == 200:
            events = response.json()
            print(f"✅ Events endpoint working - returned {len(events)} events")
            if events:
                print("   Sample event:")
                sample = events[0]
                print(f"     Title: {sample.get('title')}")
                print(f"     Type: {sample.get('type')}")
                print(f"     Location: {sample.get('location')}")
                print(f"     Status: {sample.get('status')}")
        else:
            print(f"❌ Events endpoint failed with status: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Events endpoint failed: {e}")
    
    # Test 4: Filtering
    try:
        response = requests.get(f"{base_url}/events?type_filter=hackathon&limit=5", timeout=5)
        if response.status_code == 200:
            hackathons = response.json()
            print(f"✅ Filtering works - found {len(hackathons)} hackathons")
        else:
            print(f"❌ Filtering failed with status: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Filtering test failed: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 Backend testing completed!")
    print("\nNext steps:")
    print("1. Go to http://localhost:8000/docs to see the API documentation")
    print("2. Set up the frontend by running:")
    print("   cd frontend && npm install && npm start")
    print("3. Open http://localhost:3000 to see the Events Dashboard")
    
    return True

def test_frontend():
    """Test if the frontend is accessible."""
    frontend_url = "http://localhost:3000"
    
    print("\n🧪 Testing Frontend Accessibility...")
    print("=" * 50)
    
    try:
        response = requests.get(frontend_url, timeout=5)
        if response.status_code == 200:
            print("✅ Frontend is running and accessible")
            print(f"   Available at: {frontend_url}")
        else:
            print(f"❌ Frontend returned status code: {response.status_code}")
    except requests.exceptions.RequestException:
        print("❌ Frontend not accessible")
        print("   To start the frontend:")
        print("   cd frontend && npm install && npm start")

if __name__ == "__main__":
    print("🚀 Events Dashboard Setup Test")
    print("=" * 50)
    
    # Test backend
    backend_ok = test_backend()
    
    # Test frontend if backend is working
    if backend_ok:
        test_frontend()
    
    print("\n📋 Setup Summary:")
    print("- Backend (FastAPI): python backend.py")
    print("- Frontend (React): cd frontend && npm start")
    print("- Dashboard URL: http://localhost:3000")
    print("- API Docs: http://localhost:8000/docs") 