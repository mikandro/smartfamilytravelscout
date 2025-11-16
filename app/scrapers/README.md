# Kiwi.com API Integration

Production-ready integration with Kiwi.com (Tequila API) for flight searching in the SmartFamilyTravelScout application.

## Overview

The Kiwi.com scraper provides a robust, production-ready client for searching flights from German airports to European destinations using the Tequila API. It includes comprehensive rate limiting, error handling, duplicate detection, and database integration.

## Features

### ✅ Complete Implementation

- **KiwiClient Class**: Full async/await implementation with aiohttp
- **Rate Limiting**: File-based tracking (100 calls/month limit)
- **Error Handling**: Retry logic with exponential backoff (max 3 attempts)
- **Database Integration**: Duplicate checking and price updates
- **Standardized Format**: Consistent FlightOffer format across all sources
- **Comprehensive Tests**: 25 unit tests with 100% mock coverage
- **CLI Commands**: Easy-to-use command-line interface

### 🔒 Rate Limiting

The rate limiter tracks API calls per month and prevents exceeding the free tier limit:

- **Limit**: 100 API calls/month (~3 per day)
- **Storage**: File-based tracking (`/tmp/kiwi_api_calls.txt`)
- **Auto-cleanup**: Filters out calls from previous months
- **Warnings**: Alerts when approaching limit

### 🛡️ Error Handling

Robust error handling for production reliability:

- **Network Errors**: Retry with exponential backoff (2s, 4s, 8s)
- **API Errors**: Graceful handling of 400, 401, 429 errors
- **Missing Data**: Validates responses before parsing
- **No Results**: Returns empty list instead of failing

### 💾 Database Integration

Smart duplicate detection and price tracking:

- **Duplicate Detection**: Same route, airline, date (±2 hours)
- **Price Updates**: Automatically updates if cheaper flight found
- **Airport Management**: Auto-creates airports not in database
- **Transaction Safety**: Proper commit/rollback handling

## Installation

### 1. Add Dependencies

Already added to `pyproject.toml`:

```toml
aiohttp = "^3.9.0"
```

Install dependencies:

```bash
poetry install
```

### 2. Configure API Key

Add your Kiwi API key to `.env`:

```bash
KIWI_API_KEY=your_api_key_here
```

Get your API key at: https://tequila.kiwi.com/portal/login

## Usage

### CLI Commands

The easiest way to use the Kiwi scraper is through the CLI:

#### Search Specific Route

```bash
# Search Munich to Lisbon
travelscout kiwi-search --origin MUC --destination LIS

# Custom dates
travelscout kiwi-search --origin MUC --destination BCN \
  --departure 2025-12-20 --return 2025-12-27

# Custom passengers
travelscout kiwi-search --origin MUC --destination LIS \
  --adults 2 --children 3
```

#### Search Anywhere

```bash
# Find deals from Munich to any destination
travelscout kiwi-search --origin MUC
```

#### Check Rate Limit Status

```bash
travelscout kiwi-status
```

### Python API

Use the KiwiClient directly in your code:

```python
import asyncio
from datetime import date, timedelta
from app.scrapers.kiwi_scraper import KiwiClient

async def search_flights():
    # Initialize client
    client = KiwiClient()  # Uses KIWI_API_KEY from env

    # Search specific route
    flights = await client.search_flights(
        origin="MUC",
        destination="LIS",
        departure_date=date.today() + timedelta(days=60),
        return_date=date.today() + timedelta(days=67),
        adults=2,
        children=2,
    )

    # Save to database
    stats = await client.save_to_database(flights)

    print(f"Found {len(flights)} flights")
    print(f"Inserted: {stats['inserted']}, Updated: {stats['updated']}")

asyncio.run(search_flights())
```

### Example Scripts

Run the example scripts to see the scraper in action:

```bash
# Run all examples (uses 2-3 API calls)
python -m app.scrapers.kiwi_example

# Check rate limit without using API calls
python -m app.scrapers.kiwi_example --check-limit

# Search anywhere from MUC
python -m app.scrapers.kiwi_example --anywhere

# Search from multiple airports
python -m app.scrapers.kiwi_example --multiple-airports
```

## API Reference

### KiwiClient

Main client for interacting with Kiwi.com API.

#### `__init__(api_key=None, rate_limiter=None, timeout=30)`

Initialize the Kiwi client.

**Parameters:**
- `api_key` (str, optional): Kiwi API key. Defaults to `settings.kiwi_api_key`
- `rate_limiter` (RateLimiter, optional): Custom rate limiter instance
- `timeout` (int): Request timeout in seconds (default: 30)

#### `async search_flights(origin, destination, departure_date, return_date, ...)`

Search for flights on a specific route.

**Parameters:**
- `origin` (str): Origin airport IATA code (e.g., 'MUC')
- `destination` (str): Destination airport IATA code (e.g., 'LIS')
- `departure_date` (date): Departure date
- `return_date` (date): Return date
- `adults` (int): Number of adults (default: 2)
- `children` (int): Number of children (default: 2)
- `max_stopovers` (int): Maximum stopovers (default: 0)
- `currency` (str): Price currency (default: 'EUR')

**Returns:**
- `List[Dict]`: List of standardized flight offers

#### `async search_anywhere(origin, departure_date, return_date, ...)`

Search for flights to any destination from origin.

**Parameters:**
- `origin` (str): Origin airport IATA code
- `departure_date` (date): Departure date
- `return_date` (date): Return date
- `adults` (int): Number of adults (default: 2)
- `children` (int): Number of children (default: 2)
- `max_stopovers` (int): Maximum stopovers (default: 0)
- `currency` (str): Price currency (default: 'EUR')
- `limit` (int): Maximum results (default: 50)

**Returns:**
- `List[Dict]`: List of standardized flight offers

#### `parse_response(raw_data)`

Parse Kiwi API response to standardized format.

**Parameters:**
- `raw_data` (dict): Raw JSON response from Kiwi API

**Returns:**
- `List[Dict]`: List of standardized flight offers

#### `async save_to_database(flights, update_if_cheaper=True)`

Save flights to database with duplicate checking.

**Parameters:**
- `flights` (List[Dict]): Flight offers from parse_response
- `update_if_cheaper` (bool): Update price if cheaper (default: True)

**Returns:**
- `Dict[str, int]`: Statistics {'total', 'inserted', 'updated', 'skipped'}

### RateLimiter

File-based rate limiter for tracking API calls.

#### `__init__(limit_per_month=100, storage_file="/tmp/kiwi_api_calls.txt")`

Initialize rate limiter.

#### `check_limit() -> bool`

Check if within rate limit.

#### `record_call()`

Record a new API call.

#### `get_remaining_calls() -> int`

Get number of remaining API calls for this month.

#### `reset()`

Reset all API call tracking (for testing).

## Standardized FlightOffer Format

All flight data is returned in this standardized format:

```python
{
    'origin_airport': 'MUC',          # IATA code
    'destination_airport': 'LIS',      # IATA code
    'origin_city': 'Munich',           # City name
    'destination_city': 'Lisbon',      # City name
    'airline': 'Ryanair',              # Airline name
    'departure_date': '2025-12-20',    # ISO format
    'departure_time': '14:30',         # HH:MM format
    'return_date': '2025-12-27',       # ISO format
    'return_time': '18:45',            # HH:MM format
    'price_per_person': 89.99,         # EUR per person
    'total_price': 359.96,             # EUR total (4 people)
    'direct_flight': True,             # Boolean
    'booking_class': 'Economy',        # Class name
    'source': 'kiwi',                  # Data source
    'booking_url': 'https://...',      # Booking link
    'scraped_at': '2025-11-15T10:30:00' # ISO timestamp
}
```

## Testing

Run the comprehensive test suite:

```bash
# Run all Kiwi scraper tests
poetry run pytest tests/unit/test_kiwi_scraper.py -v

# Run with coverage
poetry run pytest tests/unit/test_kiwi_scraper.py --cov=app.scrapers.kiwi_scraper

# Run specific test
poetry run pytest tests/unit/test_kiwi_scraper.py::TestKiwiClient::test_search_flights -v
```

**Test Coverage:**
- ✅ 25 unit tests
- ✅ Rate limiter functionality
- ✅ API request/response handling
- ✅ Response parsing
- ✅ Error handling and retries
- ✅ Database integration
- ✅ Duplicate detection

## Error Handling

### Rate Limit Exceeded

```python
from app.scrapers.kiwi_scraper import RateLimitExceededError

try:
    flights = await client.search_flights(...)
except RateLimitExceededError as e:
    print(f"Rate limit exceeded: {e}")
    # Check remaining calls
    remaining = client.rate_limiter.get_remaining_calls()
    print(f"Remaining calls: {remaining}")
```

### API Errors

```python
from app.scrapers.kiwi_scraper import KiwiAPIError

try:
    flights = await client.search_flights(...)
except KiwiAPIError as e:
    print(f"API error: {e}")
```

### Network Errors

Network errors are automatically retried (max 3 attempts with exponential backoff):

```python
# Automatic retry on network errors
flights = await client.search_flights(...)  # Will retry on failure
```

## Configuration

### Environment Variables

```bash
# Required
KIWI_API_KEY=your_api_key_here

# Optional (from settings)
SCRAPER_MAX_RETRIES=3
SCRAPER_TIMEOUT=30
```

### Custom Rate Limiter

```python
from app.scrapers.kiwi_scraper import KiwiClient, RateLimiter

# Custom rate limiter with different limit
rate_limiter = RateLimiter(
    limit_per_month=50,  # Lower limit
    storage_file="/custom/path/api_calls.txt"
)

client = KiwiClient(rate_limiter=rate_limiter)
```

## Production Deployment

### Rate Limit Management

For production, consider using Redis instead of file-based storage:

```python
# TODO: Implement Redis-based rate limiter
# class RedisRateLimiter:
#     def __init__(self, redis_client, limit_per_month=100):
#         self.redis = redis_client
#         self.limit = limit_per_month
```

### Monitoring

Log all API calls and errors:

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('app.scrapers.kiwi_scraper')
```

### Scheduling

Use Celery for scheduled searches:

```python
from app.tasks.celery_app import celery_app
from app.scrapers.kiwi_scraper import KiwiClient

@celery_app.task
async def scheduled_kiwi_search():
    client = KiwiClient()
    flights = await client.search_anywhere('MUC', ...)
    await client.save_to_database(flights)
```

## Limitations

- **API Rate Limit**: 100 calls/month on free tier
- **Direct Flights Only**: Currently optimized for direct flights (max_stopovers=0)
- **Fixed Passengers**: Default 2 adults + 2 children
- **Single Currency**: EUR only
- **Round Trips Only**: One-way flights not yet supported

## Future Enhancements

- [ ] Redis-based rate limiting for distributed systems
- [ ] One-way flight support
- [ ] Multi-city search
- [ ] Price alerts
- [ ] Historical price tracking
- [ ] Airline preferences
- [ ] Seat class selection (Business, Premium Economy)

## Support

For issues or questions:

1. Check the logs: `tail -f /tmp/kiwi_api_calls.txt`
2. Verify API key: `echo $KIWI_API_KEY`
3. Check rate limit: `travelscout kiwi-status`
4. Run tests: `poetry run pytest tests/unit/test_kiwi_scraper.py`

## References

- **Kiwi API Docs**: https://tequila.kiwi.com/portal/docs/tequila_api
- **API Portal**: https://tequila.kiwi.com/portal/login
- **Support**: support@kiwi.com

---

**Version**: 1.0.0
**Status**: Production Ready ✅
**Last Updated**: November 16, 2025
