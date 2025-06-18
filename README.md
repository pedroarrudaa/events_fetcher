# Events Dashboard
Platform for discovering hackathons and conferences with GPT enrichment.

## Setup
```bash
pip install -r requirements.txt
# Set: OPENAI_API_KEY, TAVILY_API_KEY, DATABASE_URL
```

## Run Scripts
```bash
# Fetch events
python event_fetcher.py conference 20    # Get 20 conferences
python event_fetcher.py hackathon 30     # Get 30 hackathons

# Start dashboard
python backend.py                        # API (port 5000)
cd frontend && npm install && npm start  # UI (port 3000)

# Legacy: python fetchers/conference_main.py 20
``` 