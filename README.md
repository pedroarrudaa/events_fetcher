# Events Fetcher 🎯

[![GitHub](https://img.shields.io/badge/GitHub-pedroarrudaa%2Fevents_fetcher-blue?logo=github)](https://github.com/pedroarrudaa/events_fetcher)

**Enhanced AI/Tech Events Dashboard** with comprehensive conference and hackathon fetching, Tavily integration, and advanced filtering capabilities for San Francisco and New York events.

## ✨ Features

### 🔍 **Multi-Source Event Discovery**
- **Conference Sources**: Eventbrite, Meetup, Luma, TechMeme, AI/ML Events
- **Hackathon Sources**: DevPost, Major League Hacking, university platforms
- **Tavily AI Search**: Enhanced with Luma-specific queries for SF/NYC events
- **Crawl4AI Integration**: Advanced web scraping with structured data extraction

### 🎯 **Smart Filtering & Validation**
- **Strict Date Filtering**: Only future events (no 30-day grace period)
- **Location Standardization**: Normalizes to "San Francisco" or "New York"
- **Quality Validation**: Removes parsing errors, duplicates, and invalid entries
- **Target Location Filtering**: Focuses on SF Bay Area and NYC events

### 🤖 **AI-Powered Enrichment**
- **GPT-4 Event Enrichment**: Extracts structured data from event pages
- **Parallel Processing**: Efficient concurrent event processing
- **Content Enhancement**: Fills missing dates, descriptions, and details
- **Error Handling**: Robust fallback mechanisms

### 🗄️ **Database Management**
- **SQLite Database**: Efficient storage with proper indexing
- **Bulk Operations**: Optimized save/update operations
- **Automatic Cleanup**: Removes past and invalid events
- **Event Tracking**: Action logging and analytics

## 🚀 Quick Start

### Prerequisites
```bash
# Python 3.8+
python --version

# Node.js 16+ (for frontend)
node --version
```

### Installation
```bash
# Clone repository
git clone https://github.com/pedroarrudaa/events_fetcher.git
cd events_fetcher

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Install Crawl4AI
pip install crawl4ai
crawl4ai-setup

# Install frontend dependencies
cd frontend
npm install
cd ..
```

### Environment Setup
```bash
# Copy environment template
cp .env.example .env

# Add your API keys
echo "OPENAI_API_KEY=your_openai_key_here" >> .env
echo "TAVILY_API_KEY=your_tavily_key_here" >> .env
```

## 🎮 Usage

### Start Backend & Frontend
```bash
# Start backend API (port 8000)
./venv/bin/python -m uvicorn backend:app --reload --host 0.0.0.0 --port 8000

# Start frontend (port 3000)
cd frontend && npm start
```

### Fetch Events
```bash
# Fetch conferences (with limit)
./venv/bin/python run_events_with_crawl4ai.py

# Fetch specific type with limit
./venv/bin/python -c "from event_fetcher import run_event_fetcher; run_event_fetcher('conference', 50)"
./venv/bin/python -c "from event_fetcher import run_event_fetcher; run_event_fetcher('hackathon', 30)"
```

### Database Maintenance
```bash
# Clean past events
./venv/bin/python clean_past_events.py

# View database stats
./venv/bin/python -c "
from database_utils import get_db_manager
db = get_db_manager()
print(db.get_database_stats())
"
```

## 🏗️ Architecture

### Core Components
- **`event_fetcher.py`**: Unified fetching pipeline
- **`event_filters.py`**: Advanced filtering and validation
- **`crawl4ai_integration.py`**: Web scraping with AI extraction
- **`database_utils.py`**: Database operations and management
- **`backend.py`**: FastAPI REST API server
- **`frontend/`**: React dashboard interface

### Data Flow
```
Sources → Raw Events → Filtering → Enrichment → Database → API → Frontend
    ↓         ↓           ↓          ↓         ↓       ↓       ↓
Tavily     Crawl4AI    EventFilter  GPT-4   SQLite  FastAPI React
Luma       DevPost     Date/Loc     Enrich  Bulk    REST    Dashboard
EventBrite Meetup      Validation   Content Save    API     
```

## 🔧 Configuration

### Filter Settings (`event_filters.py`)
```python
@dataclass
class FilterConfig:
    target_locations = ['san francisco', 'sf', 'bay area', 'nyc', 'new york']
    invalid_patterns = [r'^test\s+event', r'^placeholder', ...]
    non_hackathon_keywords = ['summit', 'conference', 'workshop', ...]
```

### Source Configuration (`fetchers/sources/`)
- **Conference Sources**: EventBrite, Luma SF/NYC, Meetup, TechMeme
- **Hackathon Sources**: DevPost, MLH, University platforms
- **Tavily Queries**: Enhanced with Luma-specific searches

## 📊 API Endpoints

### Events API
```bash
# Get all events
GET /events

# Filter by type
GET /events?type=conference
GET /events?type=hackathon

# Filter by location
GET /events?location=San Francisco

# Health check
GET /health
```

### Response Format
```json
{
  "id": "uuid",
  "title": "Event Name",
  "type": "conference|hackathon",
  "location": "San Francisco",
  "start_date": "2025-07-15",
  "end_date": "2025-07-16",
  "url": "https://example.com",
  "status": "enriched"
}
```

## 🎯 Enhanced Features

### 🔍 **Tavily Integration**
- **Luma-Specific Queries**: `lu.ma "AI conference" San Francisco 2025`
- **Enhanced Discovery**: Finds conferences missed by direct scraping
- **Smart Rate Limiting**: Respects API limits with early stopping

### 🧹 **Database Cleanup**
- **Past Event Removal**: Automatically filters events before current date
- **Location Standardization**: Converts all variations to standard format
- **Duplicate Detection**: Removes multiple entries for same event
- **Quality Validation**: Removes parsing errors and invalid entries

### ⚡ **Performance Optimizations**
- **Parallel Processing**: Concurrent event enrichment
- **Bulk Database Operations**: Efficient save/update operations
- **Smart Caching**: Reduces redundant API calls
- **Early Stopping**: Respects rate limits and quotas

## 🛠️ Development

### Project Structure
```
events_fetcher/
├── backend.py              # FastAPI server
├── event_fetcher.py        # Main fetching pipeline
├── event_filters.py        # Filtering and validation
├── database_utils.py       # Database operations
├── crawl4ai_integration.py # Web scraping
├── config.py              # Configuration
├── requirements.txt       # Python dependencies
├── fetchers/
│   ├── sources/           # Event source modules
│   └── enrichers/         # GPT enrichment modules
├── frontend/              # React dashboard
└── venv/                 # Python virtual environment
```

### Key Improvements
- ✅ **Fixed Date Filtering**: Removed 30-day grace period
- ✅ **Enhanced Luma Integration**: Added SF/NYC specific sources
- ✅ **Improved Validation**: Better quality checks and filtering
- ✅ **Database Optimization**: Bulk operations and cleanup utilities
- ✅ **Error Handling**: Robust fallback mechanisms

## 📈 Stats

### Current Database (Clean)
- **9 Valid Conferences**: All future, SF/NYC only
- **14+ Hackathons**: Properly filtered and enriched
- **100% Quality**: No parsing errors or duplicates
- **Standardized Locations**: Consistent "San Francisco"/"New York" format

### Sources Coverage
- **EventBrite**: SF/NYC AI events
- **Luma**: Both direct scraping + Tavily queries
- **Meetup**: Microsoft Reactor, tech groups
- **DevPost**: Major hackathon platform
- **Custom Sources**: TechMeme, AI/ML Events

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Tavily AI**: For enhanced event discovery
- **Crawl4AI**: For advanced web scraping capabilities
- **OpenAI GPT-4**: For intelligent event enrichment
- **Luma**: For comprehensive SF/NYC event coverage

---

**Built with ❤️ for the AI/Tech community in San Francisco and New York** 