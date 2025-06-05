# Conference Mini Pipeline

A simplified, self-contained AI/ML conference data collection pipeline. This is a minimal version designed to be portable and easy to understand.

## Files

- **`main.py`**: Main orchestrator that runs the complete pipeline
- **`logic.py`**: Core functionality (scraping, enrichment, filtering)
- **`render.py`**: HTML and CSV output generation

## Features

✅ **Multi-source scraping** (Tavily search, known conference sites, fallback URLs)  
✅ **Optional GPT enrichment** using OpenAI API  
✅ **Smart filtering** by location, date, and AI/ML relevance  
✅ **Multiple outputs**: JSON, CSV, and beautiful HTML reports  
✅ **Test database support** (doesn't touch production)  
✅ **Self-contained** - minimal dependencies  

## Usage

### Basic Usage
```bash
# Run with default settings (10 conferences, enrichment ON)
python main.py

# Fetch 5 conferences without enrichment
python main.py --limit 5 --no-enrichment

# Save results to test database
python main.py --limit 3 --save-db
```

### Command Line Options

- `--limit N`: Maximum number of conferences to fetch (default: 10)
- `--no-enrichment`: Skip GPT enrichment to save API credits
- `--save-db`: Save results to test database (safe mode)

## Requirements

```bash
# Install dependencies
pip install requests beautifulsoup4 python-dotenv

# Optional for Tavily search
pip install tavily-python

# Optional for GPT enrichment
pip install openai

# Optional for database support
pip install sqlalchemy psycopg2-binary
```

## Environment Variables

Create a `.env` file in the project root:

```bash
# Optional: For Tavily search (enhanced discovery)
TAVILY_API_KEY=your_tavily_api_key_here

# Optional: For GPT enrichment
OPENAI_API_KEY=your_openai_api_key_here

# Optional: For database support
DATABASE_URL=your_database_url_here
```

## Output Files

All output files are saved to the `output/` directory:

- **`conferences_mini.json`**: Raw JSON data
- **`conferences_mini.csv`**: Spreadsheet format
- **`conferences_mini.html`**: Beautiful visual report

## Filtering Criteria

The pipeline automatically filters conferences based on:

- **Location**: San Francisco, New York, Boston, Seattle, Austin, Denver, Remote/Online events
- **Relevance**: AI, ML, Deep Learning, Computer Vision, NLP, Data Science, MLOps topics
- **Date**: Future events only
- **Quality**: Basic validation of name, URL, and content

## Data Sources

1. **Tavily Search**: AI-powered web search (if API key provided)
2. **Known Conference Sites**: Eventbrite, Conf-Finder, AllConferences
3. **High-Quality Fallbacks**: NVIDIA GTC, OpenAI DevDay, Google I/O, Apple WWDC, etc.

## Architecture

1. **Scraping**: Fetch URLs from multiple sources with intelligent fallbacks
2. **Enrichment**: Extract structured data using regex + optional GPT
3. **Filtering**: Apply location, date, relevance, and quality filters
4. **Output**: Generate JSON, CSV, and HTML reports
5. **Database**: Optionally save to test database

## Portability

This folder is designed to be self-contained and portable:

- ✅ No dependencies on parent project folders
- ✅ Reuses existing database models from `database_utils.py`
- ✅ Uses test database to avoid production conflicts
- ✅ Minimal external dependencies
- ✅ Clean, readable code structure

## Example Output

```bash
🏁 Conference Mini Pipeline
🎯 Configuration:
   • Limit: 5 conferences
   • Enrichment: ON
   • Save to DB: OFF

📡 Step 1: Fetching conference URLs...
✅ Tavily search enabled
🔍 Searching: AI conference San Francisco 2025
🌐 Scraping: https://www.eventbrite.com/d/online/ai-conference/
✅ Found 8 conference URLs

🧠 Step 2: Enriching with GPT...
🧠 Enriching 1/8: https://www.nvidia.com/gtc/...
✅ Enriched 8 conferences

🔍 Step 3: Filtering data...
✅ 5 conferences passed filters

📄 Step 4: Generating outputs...
💾 Saved JSON: output/conferences_mini.json
🌐 Generated HTML: output/conferences_mini.html
📊 Generated CSV: output/conferences_mini.csv

✅ Pipeline completed! Processed 5 conferences
```

## Sample Conference Data

```json
{
  "name": "NVIDIA GTC 2025",
  "url": "https://www.nvidia.com/gtc/",
  "start_date": "2025-03-17",
  "end_date": "2025-03-20",
  "location": "San Francisco, CA",
  "remote": false,
  "description": "The premier AI conference featuring the latest in GPU computing, AI, and machine learning technologies.",
  "themes": ["Artificial Intelligence", "Machine Learning", "Computer Vision"],
  "registration_url": "https://www.nvidia.com/gtc/register/",
  "registration_deadline": "2025-02-15",
  "source": "mini"
}
```

## Migration Ready

This mini pipeline can be easily moved to another project:

1. Copy the entire `automation/conference_mini/` folder
2. Install the requirements: `pip install requests beautifulsoup4 python-dotenv`
3. Optionally add API keys to `.env` file
4. Run: `python main.py`

The pipeline will work independently without the parent project structure.

## API Credits Usage

- **Tavily**: ~$0.01 per search query (3 queries by default)
- **OpenAI GPT**: ~$0.002 per conference enrichment
- **Total cost for 10 conferences**: ~$0.05 (very economical)

## Troubleshooting

### No conferences found
- Check internet connection
- Verify API keys in `.env` file
- Try running with `--no-enrichment` flag

### Database errors
- Ensure `DATABASE_URL` is set correctly
- Only use `--save-db` flag in test mode
- Check database permissions

### Slow performance
- Reduce `--limit` parameter
- Use `--no-enrichment` to skip GPT calls
- Check internet connection speed 