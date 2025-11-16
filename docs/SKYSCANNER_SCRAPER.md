# Skyscanner Web Scraper Documentation

## Overview

The Skyscanner Web Scraper is a production-ready, respectful web scraper built with Playwright for browser automation. It extracts flight information from Skyscanner's website without requiring an API key.

## Features

### ✅ Core Functionality
- **Browser Automation**: Uses Playwright for JavaScript-rendered content
- **Flight Data Extraction**: Extracts airline, price, times, stops, and booking URLs
- **Database Integration**: Saves flights to PostgreSQL database
- **Error Handling**: Comprehensive error handling with screenshot capture

### ✅ Respectful Scraping
- **Rate Limiting**: Maximum 10 searches per hour
- **Random Delays**: 3-7 second delays between requests
- **User Agent Rotation**: 6 different real browser user agents
- **robots.txt Compliance**: Respects Skyscanner's robots.txt
- **CAPTCHA Detection**: Detects and aborts on CAPTCHA

### ✅ Robustness
- **Multiple Selectors**: Fallback CSS selectors for layout changes
- **Cookie Consent**: Automatic cookie consent handling
- **Retry Logic**: Automatic retries on network errors (max 2 attempts)
- **Screenshots**: Saves debug screenshots on errors
- **Timeout Handling**: 30-second timeout with graceful fallback

## Installation

### 1. Install Dependencies

```bash
poetry install
```

### 2. Install Playwright Browsers

```bash
poetry run playwright install chromium
```

### 3. Set Up Environment

Create a `.env` file (or use `.env.test` for testing):

```bash
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dbname
REDIS_URL=redis://localhost:6379/0
ANTHROPIC_API_KEY=your-key
SECRET_KEY=your-secret-key
```

## Usage

### Basic Example

```python
import asyncio
from datetime import date, timedelta
from app.scrapers import SkyscannerScraper

async def scrape_flights():
    # Use future dates
    departure = date.today() + timedelta(days=60)
    return_date = departure + timedelta(days=7)

    # Scrape with context manager (auto cleanup)
    async with SkyscannerScraper(headless=True) as scraper:
        flights = await scraper.scrape_route(
            origin="MUC",           # Munich
            destination="LIS",      # Lisbon
            departure_date=departure,
            return_date=return_date
        )

        print(f"Found {len(flights)} flights")

        # Save to database
        await scraper.save_to_database(
            flights=flights,
            origin="MUC",
            destination="LIS",
            departure_date=departure,
            return_date=return_date
        )

asyncio.run(scrape_flights())
```

### One-Way Flight

```python
async with SkyscannerScraper() as scraper:
    flights = await scraper.scrape_route(
        origin="MUC",
        destination="BCN",
        departure_date=date(2025, 12, 20),
        return_date=None  # One-way flight
    )
```

### Error Handling

```python
from app.scrapers import (
    SkyscannerScraper,
    RateLimitExceededError,
    CaptchaDetectedError
)

async with SkyscannerScraper() as scraper:
    try:
        flights = await scraper.scrape_route(...)
    except RateLimitExceededError as e:
        print(f"Rate limit hit: {e}")
        # Wait before retrying
    except CaptchaDetectedError:
        print("CAPTCHA detected, aborting")
        # Screenshot saved in logs/
    except Exception as e:
        print(f"Error: {e}")
```

## API Reference

### `SkyscannerScraper`

#### Constructor

```python
SkyscannerScraper(headless: bool = True, slow_mo: int = 0)
```

**Parameters:**
- `headless` (bool): Run browser in headless mode (default: True)
- `slow_mo` (int): Slow down operations by N milliseconds (default: 0, useful for debugging)

#### Methods

##### `scrape_route()`

```python
async def scrape_route(
    origin: str,
    destination: str,
    departure_date: date,
    return_date: Optional[date] = None
) -> List[Dict]
```

Scrape flights for a specific route.

**Parameters:**
- `origin` (str): Origin airport IATA code (e.g., "MUC")
- `destination` (str): Destination airport IATA code (e.g., "LIS")
- `departure_date` (date): Departure date
- `return_date` (Optional[date]): Return date for round-trip (None for one-way)

**Returns:**
- List of flight dictionaries with structure:
  ```python
  {
      "airline": str,              # e.g., "Lufthansa"
      "price_per_person": float,   # e.g., 150.0
      "total_price": float,        # e.g., 600.0 (for 4 people)
      "departure_time": str,       # e.g., "10:30"
      "arrival_time": str,         # e.g., "12:45"
      "direct_flight": bool,       # True if direct
      "booking_url": str,          # Skyscanner booking link
      "booking_class": str,        # e.g., "Economy"
  }
  ```

**Raises:**
- `RateLimitExceededError`: If 10+ requests made in last hour
- `CaptchaDetectedError`: If CAPTCHA is detected
- `PlaywrightTimeoutError`: If page load times out (30s)

##### `save_to_database()`

```python
async def save_to_database(
    flights: List[Dict],
    origin: str,
    destination: str,
    departure_date: date,
    return_date: Optional[date] = None
)
```

Save scraped flights to database.

**Parameters:**
- `flights`: List of flight dictionaries from `scrape_route()`
- `origin`: Origin airport IATA code
- `destination`: Destination airport IATA code
- `departure_date`: Departure date
- `return_date`: Return date (optional)

**Note:** Requires origin and destination airports to exist in database.

##### `parse_flight_cards()`

```python
async def parse_flight_cards(page: Page) -> List[Dict]
```

Extract flight data from loaded Skyscanner page.

**Parameters:**
- `page`: Playwright Page instance with loaded results

**Returns:**
- List of flight dictionaries

## Rate Limiting

The scraper enforces respectful rate limiting:

- **Maximum**: 10 requests per hour
- **Minimum Delay**: 3-7 seconds between requests
- **Counter Reset**: Hourly

Rate limit status is tracked globally across all scraper instances.

## User Agent Rotation

The scraper rotates between 6 real browser user agents:
- Chrome on Windows
- Chrome on macOS
- Firefox on Windows
- Safari on macOS
- Chrome on Linux
- Edge on Windows

A random user agent is selected for each browser session.

## Error Handling & Debugging

### Screenshot Capture

On errors, the scraper automatically saves screenshots to `logs/`:

```
logs/
├── error_20251116_143052.png
├── timeout_20251116_143105.png
└── captcha_20251116_143120.png
```

### Common Issues

#### CAPTCHA Detected

If you see `CaptchaDetectedError`:
1. Check `logs/captcha_*.png` for verification
2. Wait before retrying (Skyscanner may have flagged your IP)
3. Consider reducing scraping frequency

#### Rate Limit Exceeded

If you see `RateLimitExceededError`:
1. Wait for the cooldown period (shown in error message)
2. Reduce scraping frequency
3. Consider implementing request queuing

#### No Results Found

If `scrape_route()` returns empty list:
1. Check if flights exist for that route/date on Skyscanner
2. Verify airport IATA codes are correct
3. Check logs for selector changes (Skyscanner layout update)

#### Timeout Errors

If you see `PlaywrightTimeoutError`:
1. Check your internet connection
2. Try increasing timeout (edit `scraper_timeout` in config)
3. Check if Skyscanner is accessible

## Testing

### Run Unit Tests

```bash
poetry run pytest tests/unit/test_skyscanner_scraper.py -v
```

**34 unit tests** covering:
- Browser management
- Rate limiting
- URL building
- Price parsing
- Time parsing
- Cookie consent
- CAPTCHA detection
- Screenshot saving
- Flight data extraction
- Database integration

### Run Integration Tests (Slow)

```bash
poetry run pytest tests/integration/test_skyscanner_scraper_integration.py -v -m slow
```

**Note:** Integration tests make real requests to Skyscanner. Use sparingly to avoid rate limits.

### Skip Slow Tests

```bash
poetry run pytest tests/ -v -m "not slow"
```

## Examples

See `examples/skyscanner_example.py` for complete working examples:

```bash
poetry run python examples/skyscanner_example.py
```

Examples include:
1. Basic scrape with database save
2. One-way flight search
3. Multiple routes with comparison
4. Error handling demonstrations

## Architecture

### Data Flow

```
User Request
    ↓
SkyscannerScraper
    ↓
Rate Limit Check → (Pass/Fail)
    ↓
Playwright Browser
    ↓
Navigate to Skyscanner
    ↓
Handle Cookie Consent
    ↓
Wait for Results
    ↓
Detect CAPTCHA → (Yes: Abort / No: Continue)
    ↓
Parse Flight Cards
    ↓
Extract Data (airline, price, times, etc.)
    ↓
Return Flight Dicts
    ↓
Save to Database (optional)
```

### CSS Selector Strategy

The scraper uses **multiple fallback selectors** to handle layout changes:

```python
# Primary selectors (most specific)
'[data-testid="flight-card"]'
'[class*="FlightCard"]'

# Fallback selectors (more generic)
'[class*="flight-card"]'
'li[role="listitem"]'
```

If primary selectors fail, fallbacks are tried automatically.

## Best Practices

### ✅ DO:
- Use context manager (`async with`) for automatic cleanup
- Respect rate limits (10/hour max)
- Handle errors gracefully
- Use future dates (60+ days) for better availability
- Save screenshots enabled for debugging

### ❌ DON'T:
- Scrape in tight loops (add delays)
- Ignore `RateLimitExceededError`
- Use for commercial purposes without permission
- Scrape historical data (not available on Skyscanner)
- Run in production without error monitoring

## Configuration

Scraper settings from `app/config.py`:

```python
scraper_max_retries: int = 3          # Max retry attempts
scraper_timeout: int = 30              # Timeout in seconds
scraper_user_agent: str = "..."       # Default UA (overridden by rotation)
```

Modify in `.env`:

```bash
SCRAPER_MAX_RETRIES=3
SCRAPER_TIMEOUT=30
```

## Troubleshooting

### Browser Won't Start

```bash
# Reinstall Playwright browsers
poetry run playwright install --force chromium
```

### Import Errors

```bash
# Reinstall dependencies
poetry install
```

### Database Connection Errors

Check your `.env` file has correct `DATABASE_URL`.

### Rate Limits Hit Immediately

Reset the global counter (for testing only):

```python
import app.scrapers.skyscanner_scraper as scraper_module
scraper_module._request_count = 0
```

## Legal & Ethical Considerations

### Terms of Service

Skyscanner's Terms of Service prohibit automated scraping. This scraper is for:
- **Educational purposes**
- **Personal use**
- **Research**

**NOT for:**
- Commercial use
- Reselling data
- Competing services

### Respectful Scraping

This scraper implements:
- ✅ Rate limiting
- ✅ User agent rotation
- ✅ robots.txt compliance
- ✅ Delay between requests
- ✅ Error handling to avoid server stress

Always respect website terms and server resources.

## Contributing

When updating the scraper:

1. **Test thoroughly** - Run unit and integration tests
2. **Update selectors** - If Skyscanner changes layout, update CSS selectors
3. **Maintain rate limits** - Don't increase beyond respectful levels
4. **Document changes** - Update this README

## Support

For issues or questions:

1. Check logs in `logs/` directory
2. Review error screenshots
3. Run unit tests to verify setup
4. Check Skyscanner website manually

## Changelog

### v1.0.0 (2025-11-16)
- ✅ Initial implementation
- ✅ Playwright browser automation
- ✅ Rate limiting (10/hour)
- ✅ User agent rotation (6 UAs)
- ✅ Cookie consent handling
- ✅ CAPTCHA detection
- ✅ Screenshot on errors
- ✅ Database integration
- ✅ 34 unit tests (100% pass)
- ✅ Integration tests
- ✅ Comprehensive documentation
- ✅ Example scripts

## License

MIT License - See LICENSE file for details.

---

**Developed for SmartFamilyTravelScout** - An AI-powered family travel deal finder.
