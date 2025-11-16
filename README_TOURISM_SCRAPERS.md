# Tourism Board Event Scrapers

This module provides web scrapers for official tourism board websites to find local events, festivals, and cultural happenings that aren't available on EventBrite.

## Features

- **Multi-city support**: Lisbon, Prague, Barcelona (easily extensible)
- **Multi-language date parsing**: Supports English, Portuguese, Spanish, Czech, and German date formats
- **Smart categorization**: Automatically categorizes events (family, cultural, outdoor, music, sports, etc.)
- **Price extraction**: Identifies free events and estimates price ranges
- **Database integration**: Saves events to PostgreSQL with deduplication
- **Async operations**: Built with asyncio for efficient scraping
- **Playwright support**: Handles JavaScript-heavy websites

## Supported Cities

### Lisbon (Portugal)
- **Source**: [visitlisboa.com](https://www.visitlisboa.com)
- **Scraper**: `LisbonTourismScraper`
- **Source ID**: `tourism_lisbon`

### Prague (Czech Republic)
- **Source**: [prague.eu](https://www.prague.eu/en/whats-on)
- **Scraper**: `PragueTourismScraper`
- **Source ID**: `tourism_prague`

### Barcelona (Spain)
- **Source**: [barcelonaturisme.com](https://www.barcelonaturisme.com)
- **Scraper**: `BarcelonaTourismScraper`
- **Source ID**: `tourism_barcelona`

## Installation

The scrapers are included in the main SmartFamilyTravelScout package. Ensure you have all dependencies installed:

```bash
poetry install
```

Key dependencies:
- `playwright` - For JavaScript-heavy sites
- `beautifulsoup4` - HTML parsing
- `httpx` - Async HTTP client
- `python-dateutil` - Flexible date parsing
- `lxml` - Fast HTML/XML processing

Install Playwright browsers:
```bash
poetry run playwright install chromium
```

## Usage

### Basic Example

```python
import asyncio
from datetime import date, timedelta
from app.scrapers import LisbonTourismScraper

async def scrape_lisbon():
    start_date = date(2025, 12, 15)
    end_date = date(2025, 12, 25)

    async with LisbonTourismScraper() as scraper:
        events = await scraper.scrape_events(start_date, end_date)

    for event in events:
        print(f"{event['title']} on {event['event_date']}")

asyncio.run(scrape_lisbon())
```

### Save to Database

```python
from app.database import get_async_session_context
from app.scrapers import LisbonTourismScraper, save_events_to_db

async def scrape_and_save():
    scraper = LisbonTourismScraper()
    events = await scraper.scrape_events(start_date, end_date)

    async with get_async_session_context() as session:
        saved_count = await save_events_to_db(events, session)
        print(f"Saved {saved_count} events")
```

### Using the Example Script

Scrape all cities:
```bash
python examples/scrape_tourism_events.py
```

Scrape specific city:
```bash
python examples/scrape_tourism_events.py lisbon
python examples/scrape_tourism_events.py prague 60  # 60 days ahead
```

## Architecture

### Base Classes

#### `BaseTourismScraper`
Abstract base class for all tourism scrapers with common functionality:
- HTTP/Playwright fetching
- Date parsing
- Event categorization
- Price extraction
- URL normalization

#### `TourismDateParser`
Enhanced date parser supporting multiple formats and languages:
- ISO dates: `2025-12-20`
- European format: `20.12.2025`
- Month names: `December 20, 2025` (English, Portuguese, Spanish, Czech, German)
- Date ranges: `Dec 20-25, 2025`

### Event Data Structure

Each scraped event has the following fields:

```python
{
    'destination_city': str,      # e.g., 'Lisbon'
    'title': str,                 # Event title
    'event_date': date,           # Start date
    'end_date': date | None,      # End date for multi-day events
    'category': str,              # 'family', 'cultural', 'outdoor', etc.
    'description': str | None,    # Event description
    'price_range': str,           # 'free', '<€20', '€20-50', '€50+', 'varies'
    'source': str,                # e.g., 'tourism_lisbon'
    'url': str,                   # Event URL
}
```

## Date Parsing Examples

The `TourismDateParser` handles various formats:

```python
from app.scrapers import TourismDateParser

parser = TourismDateParser()

# English
parser.parse_tourism_date("December 20, 2025")  # date(2025, 12, 20)
parser.parse_tourism_date("Dec 20, 2025")       # date(2025, 12, 20)

# Portuguese
parser.parse_tourism_date("20 de dezembro 2025")  # date(2025, 12, 20)

# Spanish
parser.parse_tourism_date("20 de diciembre 2025")  # date(2025, 12, 20)

# Czech
parser.parse_tourism_date("20 prosince 2025")      # date(2025, 12, 20)

# Date ranges
start, end = parser.parse_date_range("Dec 20-25, 2025")
# start: date(2025, 12, 20), end: date(2025, 12, 25)
```

## Event Categories

Events are automatically categorized based on keywords:

- **family**: Family-friendly events with activities for children
- **cultural**: Museums, exhibitions, art galleries, cultural events
- **outdoor**: Parks, gardens, nature activities, hiking
- **festival**: Festivals, celebrations, carnivals
- **food**: Food events, gastronomy, restaurants
- **music**: Concerts, performances, music festivals
- **sports**: Sports events, games, competitions

## Extending to New Cities

To add a new city:

1. Create a new scraper class inheriting from `BaseTourismScraper`:

```python
from app.scrapers.tourism_scraper import BaseTourismScraper

class ViennaTourismScraper(BaseTourismScraper):
    BASE_URL = "https://www.wien.info"
    CITY_NAME = "Vienna"
    SOURCE_NAME = "tourism_vienna"
    EVENTS_URL = "https://www.wien.info/en/events"

    async def scrape_events(self, start_date, end_date):
        # Implement scraping logic
        pass
```

2. Add to `app/scrapers/__init__.py`:

```python
from app.scrapers.vienna_scraper import ViennaTourismScraper

__all__ = [..., 'ViennaTourismScraper']
```

## Testing

Run the unit tests:

```bash
poetry run pytest tests/unit/test_tourism_scraper.py -v
```

Test specific functionality:

```bash
# Test date parsing
poetry run pytest tests/unit/test_tourism_scraper.py::TestTourismDateParser -v

# Test event categorization
poetry run pytest tests/unit/test_tourism_scraper.py::TestBaseTourismScraper -v
```

## Common Patterns

### HTML Structures
Tourism websites typically have:
- Event cards in grid/list layout
- Date elements with `time`, `datetime`, or date-specific classes
- Title in `h2`, `h3`, or link elements
- Description in `p` or `div` with description/summary classes
- Price info in dedicated elements or description text

### Pagination
- "Load more" buttons (often requires Playwright)
- Traditional page numbers
- Infinite scroll (requires Playwright)

### JavaScript Rendering
Use `use_playwright=True` for sites that:
- Load events via JavaScript
- Use infinite scroll
- Have dynamic filtering

## Challenges & Solutions

### Challenge: Different HTML structures per site
**Solution**: Use flexible CSS selectors with regex patterns and fallback logic

### Challenge: Multiple date formats
**Solution**: `TourismDateParser` with multi-language support and fallback mechanisms

### Challenge: JavaScript-heavy sites
**Solution**: Playwright integration with automatic browser management

### Challenge: Rate limiting
**Solution**: Built-in delays between requests and exponential backoff on errors

### Challenge: Duplicate events
**Solution**: Database deduplication based on city, title, date, and source

## Performance Considerations

- **Parallel scraping**: Use `asyncio.gather()` to scrape multiple cities simultaneously
- **Request delays**: Default 1 second between requests (configurable)
- **Timeouts**: 30-second default timeout for HTTP/Playwright requests
- **Retries**: 3 automatic retries with exponential backoff
- **Connection pooling**: HTTP sessions are reused across requests

## Limitations

- **Site-specific**: Each scraper is tailored to specific website structure
- **Maintenance**: May require updates if tourism sites change their HTML
- **Coverage**: Only includes events listed on official tourism sites
- **JavaScript**: Some sites may require Playwright, which is slower

## Future Improvements

Potential enhancements:
- [ ] Add more cities (Porto, Vienna, etc.)
- [ ] Image extraction and storage
- [ ] Venue/location geocoding
- [ ] AI-powered relevance scoring
- [ ] Automatic scraper health monitoring
- [ ] Incremental updates (only fetch new events)
- [ ] Multi-language event descriptions

## License

MIT License - Part of SmartFamilyTravelScout project
