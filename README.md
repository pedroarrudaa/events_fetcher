# Events Dashboard

A unified platform for discovering and tracking AI conferences and hackathons in San Francisco, New York, and online.

## Features

- 🔍 **Smart Event Discovery**: Automatically discovers AI conferences in SF/NY and hackathons (including online)
- 🤖 **AI-Powered Enrichment**: Uses GPT to extract detailed event information
- 📊 **Advanced Filtering**: Filter by location, type, and upcoming events
- 🗄️ **PostgreSQL Database**: Efficient storage with unified events table
- 🌐 **RESTful API**: FastAPI backend with search, filtering, and statistics
- 🎨 **Modern UI**: React frontend with export functionality and quality metrics
- 📅 **Calendar Ready**: Export events for your calendars (generativeaisf.com, lu.ma/genai-ny)

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
cd frontend && npm install
```

### 2. Set Up Environment
```bash
cp .env.example .env
# Edit .env with your API keys (OpenAI, Tavily, etc.)
```

### 3. Initialize Database
```bash
python events_cli.py init-db
```

### 4. Discover Events

**For AI Conferences in SF & NY:**
```bash
python discover_conferences.py
# Creates: sf_conferences.json, ny_conferences.json
```

**For Hackathons (SF, NY, Online):**
```bash
python discover_hackathons.py
# Creates: sf_hackathons.json, ny_hackathons.json, online_hackathons.json
```

**Or use the CLI for more control:**
```bash
# Discover all events
python events_cli.py discover

# Discover only conferences
python events_cli.py discover --type conference --limit 100

# Discover only hackathons
python events_cli.py discover --type hackathon --limit 50
```

### 5. Start the Application

**Backend API:**
```bash
python events_cli.py serve
# API runs at http://localhost:8000
# Docs at http://localhost:8000/docs
```

**Frontend UI:**
```bash
cd frontend
npm start
# UI runs at http://localhost:3000
```

## Key Scripts

### `discover_conferences.py`
Focused script for discovering AI conferences in San Francisco and New York:
- Filters specifically for AI/ML/GenAI conferences
- Exports separate JSON files for each city
- Ready for calendar upload

### `discover_hackathons.py`
Discovers hackathons including online events:
- Categorizes by location (SF, NY, Online)
- Identifies AI-focused hackathons
- Exports organized JSON files

### `events_cli.py`
Comprehensive CLI for all operations:
- `discover` - Discover new events
- `list` - List events with filters
- `search` - Search by keyword
- `stats` - Database statistics
- `serve` - Run API server
- `record-action` - Track event interactions

## Frontend Features

- **Export Functionality**: Export events as JSON or CSV
- **Smart Filtering**: Filter by type, location, and upcoming only
- **Quality Metrics**: See event quality scores
- **Days Until**: Visual indicators for upcoming events
- **Action Tracking**: Mark events as reached out, interested, applied, or archived

## Architecture

```
├── discover_conferences.py   # SF/NY conference discovery
├── discover_hackathons.py    # Hackathon discovery (including online)
├── events_cli.py            # Main CLI interface
├── event_service.py         # Business logic layer
├── event_repository.py      # Data access layer
├── backend.py              # FastAPI endpoints
├── database_utils.py       # Database models
└── fetchers/
    ├── sources/
    │   └── unified_event_sources.py  # Event discovery
    └── enrichers/
        └── gpt_extractor.py         # AI enrichment
```

## Calendar Integration

After running the discovery scripts, you can upload the JSON files to:
- **San Francisco**: http://generativeaisf.com/
- **New York**: https://lu.ma/genai-ny

The exported files are formatted for easy calendar import with all necessary event details.

## Development

```bash
# Run tests
pytest

# Format code
black .

# Lint
flake8
```

## License

MIT
