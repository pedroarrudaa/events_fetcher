# Conference Fetcher

A customizable conference data fetcher that uses search queries to find and extract conference information using the Tavily API, web scraping, and OpenAI for data extraction.

## Features

- **Custom Search Queries**: Read search terms from a `queries.txt` file
- **Smart Data Extraction**: Uses OpenAI to extract structured conference data
- **Multiple Export Formats**: Saves data to both CSV and JSON
- **Rate Limiting**: Configurable limits to control API usage and costs
- **Error Handling**: Gracefully handles invalid or empty search results
- **Fallback Support**: Uses both Firecrawl and requests for web scraping

## Quick Start

### 1. Setup Environment Variables

Create a `.env` file with your API keys:

```env
TAVILY_API_KEY=your_tavily_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
FIRECRAWL_API_KEY=your_firecrawl_api_key_here  # Optional
```

### 2. Customize Search Queries

Edit `queries.txt` to include your desired search terms (one per line):

```
AI conference San Francisco 2025
machine learning workshop Europe 2025
NeurIPS 2025 conference
computer vision conference 2025
robotics AI summit 2025
```

### 3. Run the Conference Fetcher

```bash
cd hackathon_fetcher
python conference_fetcher.py
```

## Configuration Options

### Basic Usage

```python
from conference_fetcher import ConferenceFetcher

fetcher = ConferenceFetcher()
fetcher.run(
    limit=6,                    # Total conferences to fetch
    max_results_per_query=2,    # Results per search query (saves API credits)
    queries_file="queries.txt"  # Path to queries file
)
```

### Advanced Usage

```python
# Fetch conferences programmatically
conferences = fetcher.fetch_conferences(limit=10, max_results_per_query=3)

# Save to custom files
fetcher.save_to_csv(conferences, "my_conferences.csv")
fetcher.save_to_json(conferences, "my_conferences.json")

# Generate summary stats
summary = fetcher.generate_summary(conferences)
print(summary)
```

## Output Format

### Conference Data Structure

Each conference includes these fields:

```json
{
  "name": "Conference Name",
  "url": "https://conference-website.com",
  "is_remote": true,
  "city": "San Francisco",
  "start_date": "2025-06-15",
  "end_date": "2025-06-17",
  "topics": ["AI", "Machine Learning", "LLM"],
  "sponsors": ["OpenAI", "Google", "Microsoft"],
  "speakers": ["Dr. Jane Smith", "Prof. John Doe"],
  "price": "$500 - $800",
  "organizer": "AI Conference Organization",
  "fetched_at": "2024-12-19T10:30:00",
  "data_source": "conference_google",
  "extraction_method": "firecrawl",
  "success": true
}
```

### Output Files

- **CSV**: `output/conferences.csv` - Spreadsheet-friendly format
- **JSON**: `output/conferences.json` - Structured data with full details

## Cost Management

### Recommended Settings for Development

```python
fetcher.run(
    limit=6,                 # Small number for testing
    max_results_per_query=2, # Conservative API usage
)
```

### API Usage Per Run

- **Tavily API**: ~10-20 search requests
- **OpenAI API**: ~6-12 completion requests
- **Firecrawl API**: ~6-12 scraping requests (with fallback to free requests)

## Error Handling

The system gracefully handles:

- Missing or invalid `queries.txt` file (falls back to default queries)
- Failed web scraping (tries Firecrawl, then requests)
- OpenAI extraction errors (creates fallback data)
- Network timeouts and API rate limits

## Troubleshooting

### Common Issues

1. **No conferences found**: Check your queries.txt file and API keys
2. **API rate limits**: Reduce `limit` and `max_results_per_query` parameters
3. **Missing dependencies**: Run `pip install -r requirements.txt`

### Debug Mode

To see detailed output, the scripts include extensive logging with emojis for easy scanning:

- 🚀 Starting processes
- ✅ Successful operations
- ❌ Errors and failures
- 💾 File operations
- 🎯 Important milestones

## Customization

### Adding New Search Sources

1. Modify `sources/conference_google.py` to add new search providers
2. Update the `ConferenceGoogleScraper` class with additional methods
3. Extend the data extraction prompts for different website formats

### Custom Data Fields

Modify the OpenAI extraction prompt in `extract_conference_data_with_ai()` to include additional fields as needed.

## Files Overview

- `conference_fetcher.py` - Main orchestration script
- `sources/conference_google.py` - Search and extraction logic
- `queries.txt` - Custom search queries (one per line)
- `output/conferences.csv` - CSV output
- `output/conferences.json` - JSON output
- `utils/firecrawl.py` - Web scraping utilities 