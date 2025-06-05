# Hackathon Mini Pipeline

A simplified, self-contained hackathon data collection pipeline. This is a minimal version designed to be portable and easy to understand.

## Files

- **`main.py`**: Main orchestrator that runs the complete pipeline
- **`logic.py`**: Core functionality (scraping, enrichment, filtering)
- **`render.py`**: HTML and CSV output generation

## Features

✅ **Simple scraping** from multiple sources (Devpost, Hackathon.com, Eventbrite)  
✅ **Optional GPT enrichment** using OpenAI API  
✅ **Smart filtering** by location and date  
✅ **Multiple outputs**: JSON, CSV, and beautiful HTML reports  
✅ **Test database support** (doesn't touch production)  
✅ **Self-contained** - minimal dependencies  

## Usage

### Basic Usage
```bash
# Run with default settings (10 hackathons, enrichment ON)
python main.py

# Fetch 5 hackathons without enrichment
python main.py --limit 5 --no-enrichment

# Save results to test database
python main.py --limit 3 --save-db
```

### Command Line Options

- `--limit N`: Maximum number of hackathons to fetch (default: 10)
- `--no-enrichment`: Skip GPT enrichment to save API credits
- `--save-db`: Save results to test database (safe mode)

## Requirements

```bash
# Install dependencies
pip install requests beautifulsoup4 python-dotenv

# Optional for GPT enrichment
pip install openai

# Optional for database support
pip install sqlalchemy psycopg2-binary
```

## Environment Variables

Create a `.env` file in the project root:

```bash
# Optional: For GPT enrichment
OPENAI_API_KEY=your_openai_api_key_here

# Optional: For database support
DATABASE_URL=your_database_url_here
```

## Output Files

All output files are saved to the `output/` directory:

- **`hackathons_mini.json`**: Raw JSON data
- **`hackathons_mini.csv`**: Spreadsheet format
- **`hackathons_mini.html`**: Beautiful visual report

## Filtering Criteria

The pipeline automatically filters hackathons based on:

- **Location**: San Francisco, New York, Remote/Online events
- **Date**: Future events only
- **Quality**: Basic validation of name and URL

## Architecture

1. **Scraping**: Fetch URLs from multiple sources
2. **Enrichment**: Extract structured data using regex + optional GPT
3. **Filtering**: Apply location, date, and quality filters
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
🏁 Hackathon Mini Pipeline
🎯 Configuration:
   • Limit: 5 hackathons
   • Enrichment: ON
   • Save to DB: OFF

📡 Step 1: Fetching hackathon URLs...
✅ Found 5 hackathon URLs

🧠 Step 2: Enriching with GPT...
✅ Enriched 5 hackathons

🔍 Step 3: Filtering data...
✅ 3 hackathons passed filters

📄 Step 4: Generating outputs...
💾 Saved JSON: output/hackathons_mini.json
🌐 Generated HTML: output/hackathons_mini.html
📊 Generated CSV: output/hackathons_mini.csv

✅ Pipeline completed! Processed 3 hackathons
```

## Migration Ready

This mini pipeline can be easily moved to another project:

1. Copy the entire `automation/hackathon_mini/` folder
2. Install the requirements: `pip install requests beautifulsoup4 python-dotenv`
3. Run: `python main.py`

The pipeline will work independently without the parent project structure. 