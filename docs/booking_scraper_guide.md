# Booking.com Scraper Guide

## Overview

The Booking.com scraper is a sophisticated web scraping tool built with Playwright that searches for family-friendly accommodations on Booking.com. It's specifically designed to find properties suitable for families with 2 adults and 2 children (ages 3 & 6).

## Features

### Core Functionality
- ✅ **Automated Search**: Navigate to Booking.com with family-specific search parameters
- ✅ **Smart Parsing**: Extract property data from search results using robust selectors
- ✅ **Family Filtering**: Automatically filter properties by bedrooms, price, rating, and amenities
- ✅ **Amenity Detection**: Identify kitchens, kids clubs, and family facilities
- ✅ **Database Integration**: Save properties directly to PostgreSQL database
- ✅ **Respectful Scraping**: Built-in rate limiting, delays, and user agent rotation

### Technical Features
- ✅ **Playwright Browser Automation**: Handles JavaScript-heavy sites
- ✅ **Cookie Consent Handling**: Automatically accepts cookie banners
- ✅ **Lazy Loading Support**: Scrolls to load more properties
- ✅ **Error Screenshots**: Saves debugging screenshots on failures
- ✅ **Async/Await**: Fully asynchronous for better performance
- ✅ **Context Manager**: Clean resource management with `async with`

## Installation

### Prerequisites

1. Python 3.11+
2. Poetry (package manager)
3. PostgreSQL database

### Setup

```bash
# Install dependencies
poetry install

# Install Playwright browsers
poetry run playwright install chromium

# Set up environment variables (copy from .env.example)
cp .env.example .env
# Edit .env with your database credentials
```

## Quick Start

### Basic Usage

```python
import asyncio
from datetime import date
from app.scrapers.booking_scraper import search_booking

async def main():
    # Simple search with auto-save to database
    properties = await search_booking(
        city="Lisbon",
        check_in=date(2025, 12, 20),
        check_out=date(2025, 12, 27),
        save_to_db=True
    )

    print(f"Found {len(properties)} family-friendly properties")

asyncio.run(main())
```

### Advanced Usage

```python
import asyncio
from datetime import date
from app.scrapers.booking_scraper import BookingClient

async def main():
    # Create client with custom settings
    async with BookingClient(
        headless=True,
        rate_limit_seconds=5.0
    ) as client:
        # Search with custom parameters
        properties = await client.search(
            city="Barcelona",
            check_in=date(2025, 7, 15),
            check_out=date(2025, 7, 22),
            adults=2,
            children_ages=[3, 6],
            limit=20
        )

        # Apply custom filtering
        family_friendly = client.filter_family_friendly(
            properties,
            min_bedrooms=2,
            max_price=120.0,
            min_rating=8.0
        )

        # Save to database
        saved_count = await client.save_to_database(family_friendly)
        print(f"Saved {saved_count} properties")

asyncio.run(main())
```

## API Reference

### `BookingClient`

Main class for scraping Booking.com.

#### Constructor

```python
BookingClient(
    headless: bool = True,
    screenshots_dir: Optional[Path] = None,
    rate_limit_seconds: float = 5.0
)
```

**Parameters:**
- `headless` (bool): Run browser in headless mode (default: True)
- `screenshots_dir` (Path): Directory for error screenshots (default: "screenshots")
- `rate_limit_seconds` (float): Minimum seconds between requests (default: 5.0)

#### Methods

##### `search()`

Search for accommodations with family parameters.

```python
async def search(
    city: str,
    check_in: date,
    check_out: date,
    adults: int = 2,
    children_ages: Optional[List[int]] = None,
    limit: int = 20
) -> List[Dict[str, Any]]
```

**Parameters:**
- `city` (str): Destination city name (e.g., "Lisbon", "Barcelona")
- `check_in` (date): Check-in date
- `check_out` (date): Check-out date
- `adults` (int): Number of adults (default: 2)
- `children_ages` (List[int]): Ages of children (default: [3, 6])
- `limit` (int): Maximum properties to return (default: 20)

**Returns:** List of property dictionaries

**Example:**
```python
properties = await client.search(
    city="Lisbon",
    check_in=date(2025, 12, 20),
    check_out=date(2025, 12, 27),
    limit=15
)
```

##### `filter_family_friendly()`

Filter properties for family suitability.

```python
def filter_family_friendly(
    properties: List[Dict[str, Any]],
    min_bedrooms: int = 2,
    max_price: float = 150.0,
    min_rating: float = 7.5
) -> List[Dict[str, Any]]
```

**Parameters:**
- `properties` (List[Dict]): Properties to filter
- `min_bedrooms` (int): Minimum bedrooms required (default: 2)
- `max_price` (float): Maximum price per night in EUR (default: 150.0)
- `min_rating` (float): Minimum rating score (default: 7.5)

**Returns:** Filtered list of properties

**Example:**
```python
family_properties = client.filter_family_friendly(
    properties,
    min_bedrooms=3,
    max_price=120.0,
    min_rating=8.0
)
```

##### `save_to_database()`

Save properties to the database.

```python
async def save_to_database(
    properties: List[Dict[str, Any]],
    session: Optional[AsyncSession] = None
) -> int
```

**Parameters:**
- `properties` (List[Dict]): Properties to save
- `session` (AsyncSession): Optional database session

**Returns:** Number of properties saved

**Example:**
```python
saved_count = await client.save_to_database(properties)
print(f"Saved {saved_count} properties")
```

##### `parse_property_cards()`

Extract property data from search result cards.

```python
async def parse_property_cards(
    page: Page,
    limit: int = 20
) -> List[Dict[str, Any]]
```

**Parameters:**
- `page` (Page): Playwright page with search results
- `limit` (int): Maximum properties to parse

**Returns:** List of property dictionaries

##### `extract_amenities()`

Extract amenity flags from property card.

```python
async def extract_amenities(
    property_card
) -> Dict[str, bool]
```

**Returns:** Dictionary with amenity flags:
- `has_kitchen` (bool): Has kitchen/kitchenette
- `has_kids_club` (bool): Has kids club or children's facilities

### Convenience Functions

##### `search_booking()`

Quick search function with auto-filtering and database saving.

```python
async def search_booking(
    city: str,
    check_in: date,
    check_out: date,
    save_to_db: bool = True,
    **kwargs
) -> List[Dict[str, Any]]
```

**Parameters:**
- `city` (str): Destination city
- `check_in` (date): Check-in date
- `check_out` (date): Check-out date
- `save_to_db` (bool): Auto-save to database (default: True)
- `**kwargs`: Additional arguments for `BookingClient.search()`

**Example:**
```python
properties = await search_booking(
    "Porto",
    date(2025, 8, 1),
    date(2025, 8, 8)
)
```

## Property Data Structure

Each scraped property is returned as a dictionary with the following structure:

```python
{
    "destination_city": "Lisbon",         # Search city
    "name": "Family Apartment Central",   # Property name
    "type": "apartment",                  # "apartment" or "hotel"
    "bedrooms": 2,                        # Number of bedrooms (may be None)
    "price_per_night": 80.00,            # Price in EUR
    "family_friendly": True,              # Auto-set by filter
    "has_kitchen": True,                  # Has kitchen/kitchenette
    "has_kids_club": False,               # Has kids club
    "rating": 8.5,                        # Rating 0-10 (may be None)
    "review_count": 234,                  # Number of reviews (may be None)
    "source": "booking",                  # Always "booking"
    "url": "https://booking.com/...",    # Property URL
    "image_url": "https://...",          # Main image URL
    "scraped_at": "2025-11-15T10:00:00" # ISO format timestamp
}
```

## Filtering Logic

The `filter_family_friendly()` method applies multiple criteria:

### Hard Filters (properties are excluded if they fail):
1. **Price**: Must have a price AND be ≤ max_price
2. **Rating**: If rating exists, must be ≥ min_rating
3. **Bedrooms**: If bedroom count is known, must be ≥ min_bedrooms

### Scoring System (for ranking):
Properties get points for family-friendly features:
- Apartment type: +1 point
- Has kitchen: +2 points
- Has min_bedrooms or more: +2 points
- Rating ≥ 8.5: +1 point

Properties with score ≥ 1 or with known bedroom count are kept.

## Respectful Scraping

The scraper implements several best practices:

### Rate Limiting
- Configurable delays between requests (default: 5-8 seconds)
- Random delays to appear more human-like
- Recommended: 1 search per minute maximum

### User Agent Rotation
- Rotates between 5 different user agents
- Includes Chrome, Firefox, and Safari
- Updates automatically for each session

### Realistic Behavior
- Scrolls gradually to trigger lazy loading
- Accepts cookie consent like a human
- Random delays between actions
- Respects server responses

### Resource Limits
- Default limit of 20 properties per search
- Can be adjusted but stay reasonable
- Screenshots saved on errors for debugging

## Database Schema

Properties are saved to the `accommodations` table:

```sql
CREATE TABLE accommodations (
    id SERIAL PRIMARY KEY,
    destination_city VARCHAR(100) NOT NULL,
    name VARCHAR(200) NOT NULL,
    type VARCHAR(50) NOT NULL,
    bedrooms INTEGER,
    price_per_night NUMERIC(10, 2) NOT NULL,
    family_friendly BOOLEAN NOT NULL DEFAULT false,
    has_kitchen BOOLEAN NOT NULL DEFAULT false,
    has_kids_club BOOLEAN NOT NULL DEFAULT false,
    rating NUMERIC(3, 1),
    review_count INTEGER,
    source VARCHAR(50) NOT NULL,
    url TEXT,
    image_url TEXT,
    scraped_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## Error Handling

### Screenshots
On errors, the scraper automatically saves screenshots to `screenshots/`:
- `timeout_no_results_YYYYMMDD_HHMMSS.png` - Results didn't load
- `parse_error_YYYYMMDD_HHMMSS.png` - Error parsing properties
- `search_error_YYYYMMDD_HHMMSS.png` - General search error

### Logging
The scraper uses Python's logging module:
- `INFO`: Normal operations and progress
- `DEBUG`: Detailed parsing information
- `WARNING`: Non-critical issues
- `ERROR`: Failures and exceptions

### Common Issues

**Issue**: Cookie consent not handled
- **Solution**: Scraper automatically tries multiple selectors
- **Check**: Screenshots for banner appearance

**Issue**: No properties found
- **Solution**: Check if city name is correct
- **Check**: Try different dates (some cities have limited availability)

**Issue**: Playwright timeout
- **Solution**: Increase timeout in code
- **Check**: Network connection stability

**Issue**: Database connection error
- **Solution**: Verify DATABASE_URL in .env
- **Check**: PostgreSQL is running

## Testing

### Run Unit Tests

```bash
# Run all scraper tests
DATABASE_URL=postgresql+asyncpg://test:test@localhost:5432/test \
REDIS_URL=redis://localhost:6379/0 \
ANTHROPIC_API_KEY=test_key \
SECRET_KEY=test_secret \
poetry run pytest tests/unit/test_booking_scraper.py -v

# Run specific test
poetry run pytest tests/unit/test_booking_scraper.py::TestBookingClient::test_filter_family_friendly -v

# Run with coverage
poetry run pytest tests/unit/test_booking_scraper.py --cov=app.scrapers.booking_scraper
```

### Test Coverage

The test suite includes 25+ tests covering:
- URL construction
- Cookie consent handling
- Property parsing
- Price/rating/bedroom extraction
- Amenity detection
- Family-friendly filtering
- Database operations
- Error handling

## Examples

See `examples/booking_scraper_example.py` for complete working examples:

1. **Basic Search**: Simple search with auto-save
2. **Advanced Search**: Custom filtering and parameters
3. **Multi-City Search**: Parallel searches for multiple destinations
4. **Data Analysis**: Analyze results and find best deals

Run examples:
```bash
poetry run python examples/booking_scraper_example.py
```

## Best Practices

### Do's ✅
- Use reasonable rate limits (5+ seconds)
- Limit results to what you need (20-30 max)
- Run during off-peak hours
- Check robots.txt compliance
- Save screenshots for debugging
- Use headless mode in production

### Don'ts ❌
- Don't scrape aggressively (respect rate limits)
- Don't make concurrent requests to same site
- Don't ignore errors (check screenshots)
- Don't scrape without delays
- Don't bypass security measures

## Troubleshooting

### Enable Debug Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
```

### Disable Headless Mode

```python
client = BookingClient(headless=False)
# Watch the browser in action
```

### Increase Timeouts

```python
# In booking_scraper.py, modify:
await page.goto(url, wait_until="domcontentloaded", timeout=60000)  # 60s instead of 30s
```

## Future Enhancements

Planned improvements:
- [ ] Proxy support for distributed scraping
- [ ] More detailed property information (detailed scraping)
- [ ] Price history tracking
- [ ] Availability calendar scraping
- [ ] Multi-language support
- [ ] Captcha handling
- [ ] Room type detection

## License

MIT License - See LICENSE file for details

## Support

For issues, questions, or contributions:
- GitHub Issues: [Create an issue](#)
- Documentation: See this guide
- Examples: Check `examples/booking_scraper_example.py`
