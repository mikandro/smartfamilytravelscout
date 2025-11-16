# Ryanair Web Scraper

A sophisticated, stealth-focused web scraper for Ryanair flights using Playwright.

## ⚠️ Important Warnings

**Ryanair actively blocks automated scrapers.** This scraper implements maximum stealth and respectful practices:

- ✅ **Rate limiting**: Maximum 5 searches per day
- ✅ **Realistic behavior**: Human-like delays, mouse movements, typing
- ✅ **Stealth mode**: Multiple anti-detection techniques
- ✅ **Conservative delays**: 5-10 seconds between actions
- ✅ **CAPTCHA detection**: Gracefully aborts when CAPTCHA appears
- ✅ **Off-peak hours**: Recommended usage 2-6 AM local time

**Use responsibly and at your own risk.**

## Features

### Core Functionality

1. **Stealth Mode**
   - Playwright with stealth plugin
   - Navigator.webdriver spoofing
   - Realistic viewport and user agents
   - Human-like behavior simulation
   - Random delays and scrolling

2. **Popup Handling**
   - Cookie consent dialogs
   - Chat widgets
   - Marketing popups
   - Ad overlays

3. **Form Navigation**
   - Airport selection with autocomplete
   - Date picker navigation
   - Passenger selection (2 adults, 2 children)
   - Realistic typing simulation

4. **Price Discovery**
   - Fare calendar parsing
   - Multiple fare types (Regular, Flexi)
   - Cheapest price extraction
   - Flight details (times, flight numbers)

5. **Rate Limiting**
   - 5 searches per day maximum
   - File-based tracking
   - Automatic daily reset
   - Clear error messages

6. **Error Handling**
   - Screenshot logging on errors
   - CAPTCHA detection
   - Graceful failure
   - Detailed logging

## Installation

### Prerequisites

```bash
# Install Python dependencies (already in pyproject.toml)
poetry install

# Install playwright-stealth (additional package)
pip install playwright-stealth

# Install Playwright browsers
playwright install chromium
```

### Directory Setup

The scraper automatically creates necessary directories:

```
logs/
└── ryanair/          # Error screenshots saved here
    ├── 20231116_143022_captcha_detected.png
    ├── 20231116_143045_error_search_submit.png
    └── ...
```

## Usage

### Basic Usage

```python
import asyncio
from datetime import date
from app.scrapers.ryanair_scraper import RyanairScraper

async def scrape_flights():
    scraper = RyanairScraper()

    try:
        flights = await scraper.scrape_route(
            origin="FMM",              # Memmingen
            destination="BCN",         # Barcelona
            departure_date=date(2025, 12, 20),
            return_date=date(2025, 12, 27),
        )

        for flight in flights:
            print(f"€{flight['price']} - {flight['departure_time']}")

    finally:
        await scraper.close()

asyncio.run(scrape_flights())
```

### With Database Integration

```python
from app.database import SessionLocal
from app.scrapers.ryanair_db_helper import scrape_and_save_route

async def scrape_and_save():
    async with SessionLocal() as db:
        flights = await scrape_and_save_route(
            db=db,
            origin="FMM",
            destination="BCN",
            departure_date=date(2025, 12, 20),
            return_date=date(2025, 12, 27),
        )

        print(f"Saved {len(flights)} flights to database")
```

### Error Handling

```python
from app.scrapers.ryanair_scraper import (
    RyanairScraper,
    RateLimitExceeded,
    CaptchaDetected,
)

async def safe_scrape():
    scraper = RyanairScraper()

    try:
        flights = await scraper.scrape_route(...)

    except RateLimitExceeded as e:
        print(f"Rate limit exceeded: {e}")
        print("Try again tomorrow")

    except CaptchaDetected as e:
        print(f"CAPTCHA detected: {e}")
        print("Scraper working correctly - avoiding detection")

    except Exception as e:
        print(f"Unexpected error: {e}")

    finally:
        await scraper.close()
```

### Context Manager

```python
async def scrape_with_context():
    async with RyanairScraper() as scraper:
        flights = await scraper.scrape_route(...)
        # Browser closes automatically
```

## API Reference

### RyanairScraper

#### `__init__(log_dir: str = "./logs/ryanair")`

Initialize scraper with optional log directory.

**Parameters:**
- `log_dir`: Directory for error screenshots (default: `./logs/ryanair`)

#### `async scrape_route(origin, destination, departure_date, return_date) -> List[Dict]`

Main scraping method.

**Parameters:**
- `origin` (str): Origin airport IATA code (e.g., "FMM", "MUC")
- `destination` (str): Destination airport IATA code (e.g., "BCN", "PMI")
- `departure_date` (date): Outbound flight date
- `return_date` (date): Return flight date

**Returns:**
- List of flight dictionaries with keys:
  - `price` (float): Price per person in EUR
  - `currency` (str): Currency code ("EUR")
  - `departure_time` (str): Departure time ("HH:MM")
  - `arrival_time` (str): Arrival time ("HH:MM")
  - `flight_number` (str): Flight number
  - `direct` (bool): Direct flight indicator
  - `booking_class` (str): Fare type ("Regular", "Flexi")
  - `booking_url` (str): Constructed booking URL
  - `origin` (str): Origin airport code
  - `destination` (str): Destination airport code
  - `departure_date` (date): Departure date
  - `return_date` (date): Return date
  - `source` (str): Always "ryanair"
  - `scraped_at` (datetime): Scrape timestamp

**Raises:**
- `RateLimitExceeded`: Daily limit exceeded
- `CaptchaDetected`: CAPTCHA encountered
- `Exception`: Other scraping errors

#### `async close()`

Close browser and cleanup.

### Helper Functions

#### `scrape_and_save_route(db, origin, destination, departure_date, return_date)`

Convenience function that scrapes and saves to database.

## Scraped Data Structure

```python
{
    "price": 49.99,
    "currency": "EUR",
    "departure_time": "08:30",
    "arrival_time": "10:45",
    "flight_number": "FR1234",
    "direct": True,
    "booking_class": "Regular",
    "booking_url": "https://www.ryanair.com/gb/en/trip/flights/...",
    "origin": "FMM",
    "destination": "BCN",
    "departure_date": date(2025, 12, 20),
    "return_date": date(2025, 12, 27),
    "source": "ryanair",
    "scraped_at": datetime(2025, 11, 16, 14, 30, 0)
}
```

## Rate Limiting

Rate limit data is stored in `/tmp/ryanair_rate_limit.json`:

```json
{
    "date": "2025-11-16",
    "count": 3
}
```

- Maximum: 5 searches per day
- Resets automatically at midnight
- Shared across all scraper instances
- File-based (no Redis required)

To manually reset:

```bash
rm /tmp/ryanair_rate_limit.json
```

## Stealth Techniques

The scraper implements multiple anti-detection measures:

### 1. Browser Configuration

```python
args=[
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    # ... more stealth args
]
```

### 2. Navigator Spoofing

```javascript
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined
});
```

### 3. Realistic Behavior

- Random delays (1-3 seconds)
- Human-like typing (50-150ms per character)
- Random scrolling
- Mouse movements
- Hover effects

### 4. Residential Headers

- Realistic user agents
- Browser-appropriate headers
- Proper timezone and locale
- Geolocation (Munich coordinates)

## Screenshots

The scraper saves screenshots in various scenarios:

- `initial_page.png` - Homepage loaded
- `success_results.png` - Results page
- `error_*.png` - Error conditions
- `captcha_detected.png` - CAPTCHA detected
- `no_flights_found.png` - No results

Screenshots include timestamp: `20231116_143022_error_name.png`

## Troubleshooting

### CAPTCHA Detected

**Cause:** Ryanair detected automated activity

**Solutions:**
1. Wait 24 hours before trying again
2. Use during off-peak hours (2-6 AM)
3. Don't exceed rate limit
4. Don't run multiple instances

### Rate Limit Exceeded

**Cause:** 5 searches per day limit reached

**Solutions:**
1. Wait until tomorrow (automatic reset)
2. Manually reset: `rm /tmp/ryanair_rate_limit.json`
3. Use database to avoid re-scraping same routes

### No Flights Found

**Causes:**
1. No flights available for route/date
2. Page structure changed (Ryanair updates)
3. Scraper blocked

**Solutions:**
1. Check route availability on Ryanair.com manually
2. Try different dates
3. Check error screenshots in `logs/ryanair/`
4. Update selectors if page structure changed

### Timeout Errors

**Causes:**
1. Slow internet connection
2. Ryanair site slow
3. CAPTCHA appeared

**Solutions:**
1. Increase timeout in scraper code
2. Try again later
3. Check screenshots for CAPTCHA

## Best Practices

1. **Timing**
   - Run during 2-6 AM local time
   - Avoid peak hours (evenings, weekends)
   - Space out searches (not all at once)

2. **Rate Limiting**
   - Respect the 5/day limit
   - Don't try to circumvent it
   - Use database to cache results

3. **Error Handling**
   - Always use try/except
   - Check for CaptchaDetected
   - Close browser in finally block

4. **Monitoring**
   - Check error screenshots
   - Review logs regularly
   - Monitor success rate

5. **Maintenance**
   - Update selectors if Ryanair changes layout
   - Test regularly
   - Keep playwright-stealth updated

## Examples

See `examples/ryanair_scraper_example.py` for comprehensive examples:

```bash
python examples/ryanair_scraper_example.py
```

Examples include:
1. Basic scraping
2. Multiple routes
3. Database integration
4. Error handling
5. Rate limit checking

## Testing

Run unit tests:

```bash
pytest tests/unit/test_ryanair_scraper.py -v
```

Run integration tests (requires network):

```bash
pytest tests/unit/test_ryanair_scraper.py::TestRyanairScraperIntegration -v
```

**Note:** Integration tests are skipped by default to avoid triggering CAPTCHA during CI/CD.

## Maintenance

### Updating Selectors

If Ryanair changes their page structure, update selectors in:

1. `navigate_search()` - Search form selectors
2. `handle_popups()` - Popup selectors
3. `parse_fare_calendar()` - Results page selectors

Check error screenshots to identify new selectors.

### Updating User Agents

Update `USER_AGENTS` list in `RyanairScraper` class with current browser versions.

## Legal and Ethical Considerations

- ⚠️ **Terms of Service**: Scraping may violate Ryanair's ToS
- ⚠️ **Rate Limiting**: Always respect rate limits
- ⚠️ **Personal Use**: Intended for personal use only
- ⚠️ **No Commercial Use**: Not for commercial scraping operations

**Use at your own risk. The authors are not responsible for any misuse.**

## Contributing

When contributing updates:

1. Test thoroughly to avoid detection
2. Document selector changes
3. Update tests
4. Check screenshots work
5. Verify rate limiting

## Support

For issues:

1. Check error screenshots in `logs/ryanair/`
2. Review logs with logging level DEBUG
3. Verify rate limit status
4. Test with example script first

## Changelog

### v1.0.0 (2025-11-16)
- Initial release
- Stealth mode implementation
- Rate limiting (5/day)
- CAPTCHA detection
- Comprehensive error handling
- Database integration
- Example scripts
- Unit tests

## License

MIT License - See LICENSE file for details.
