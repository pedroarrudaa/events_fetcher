# Hackathon Fetcher

An automated system to fetch and enrich hackathon opportunities from websites like Devpost.

## Features

- 🔍 **Web Scraping**: Uses Firecrawl API to fetch content from JavaScript-heavy sites like Devpost
- 🤖 **AI Enhancement**: Leverages OpenAI GPT-4 mini to extract structured data from raw HTML/markdown
- 📊 **Data Export**: Saves all collected data to CSV format for easy analysis
- 🔄 **Fallback System**: Graceful degradation when AI extraction fails

## Data Fields Extracted

### Core Fields
- `name`: Hackathon name
- `url`: Original URL
- `remote`: Whether it's remote/virtual (true/false)
- `in_person`: Whether it has in-person component (true/false)
- `city`: Location if in-person or hybrid
- `short_description`: Brief description (1-2 sentences)

### Enhanced Fields (via GPT)
- `prizes`: List of prizes/awards
- `sponsors`: List of sponsors
- `judges`: List of judges
- `start_date`, `end_date`: Event dates (YYYY-MM-DD format)
- `registration_deadline`: Registration deadline
- `themes`: List of themes/tracks
- `eligibility`: Who can participate

## Setup

1. **Install Dependencies**:
   ```bash
   cd hackathon_fetcher
   pip install -r requirements.txt
   ```

2. **Configure API Keys**:
   The `.env` file is already created with your API keys. If you need to modify them:
   ```
   FIRECRAWL_API_KEY=your_firecrawl_key
   OPENAI_API_KEY=your_openai_key
   TAVILY_API_KEY=your_tavily_key  # Optional, for future use
   ```

## Usage

### Basic Usage
```bash
python main.py
```

This will:
- Fetch hackathons from 2 pages of Devpost listings
- Process up to 5 hackathons (good for testing)
- Save results to `output/hackathons.csv`

### Customizing Parameters

You can modify the parameters in `main.py`:

```python
fetcher.run(
    max_listings=5,     # Process more listing pages
    max_hackathons=20,  # Process more individual hackathons
    output_filename="my_hackathons.csv"  # Custom filename
)
```

## Project Structure

```
hackathon_fetcher/
├── .env                    # API keys (already configured)
├── main.py                 # Main orchestration script
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── sources/               # Data sources
│   ├── __init__.py
│   └── devpost.py         # Devpost scraper
├── enrichers/             # Data enrichment
│   ├── __init__.py
│   └── gpt_extractor.py   # GPT-based extraction
├── utils/                 # Utilities
│   ├── __init__.py
│   └── firecrawl.py       # Firecrawl API helper
└── output/                # Output directory
    └── hackathons.csv     # Generated CSV files
```

## API Usage Considerations

- **Firecrawl**: Used for fetching JavaScript-heavy content from Devpost
- **OpenAI GPT-4 mini**: Used for structured data extraction (cost-effective option)
- **Rate Limiting**: Built-in delays to respect API limits

## Output Format

The CSV output includes all extracted fields plus metadata:
- `extraction_success`: Whether GPT extraction succeeded
- `extraction_method`: Method used ('gpt-4o-mini' or 'fallback')

## Troubleshooting

### Common Issues

1. **Import Errors**: Make sure you're running from the `hackathon_fetcher` directory
2. **API Key Errors**: Verify your API keys in the `.env` file
3. **No Results**: Devpost's structure may have changed; check the URL patterns in `sources/devpost.py`

### Debugging

Enable verbose output by adding print statements or checking the generated CSV for error messages in failed extractions.

## Future Enhancements

- [ ] Add Tavily API integration for additional enrichment
- [ ] Support for other hackathon platforms (MLH, Eventbrite, etc.)
- [ ] Real-time monitoring for new hackathons
- [ ] Database integration
- [ ] Web interface for data visualization

## License

This project is for educational and research purposes. 