# WizzAir Flight Scraper

API-based flight scraper for WizzAir, a budget airline with excellent routes to Eastern Europe (especially Moldova - Chisinau).

## Overview

This scraper uses WizzAir's **unofficial JSON API** instead of HTML scraping, making it:
- ✅ **Faster** - No browser rendering needed
- ✅ **More reliable** - JSON structure changes less frequently than HTML
- ✅ **Less likely to be blocked** - Mimics legitimate browser requests
- ✅ **Easier to maintain** - Clean data structures

## Architecture

### Core Components

1. **WizzAirScraper** - Main scraper class
2. **Custom Exceptions** - `WizzAirAPIError`, `WizzAirRateLimitError`
3. **Database Integration** - Async SQLAlchemy for flight storage
4. **Error Handling** - Rate limiting, network errors, validation

### API Endpoint

```
POST https://be.wizzair.com/*/Api/search/search
```

The `*` is a wildcard for the API version (e.g., `12.3.1`).

### Request Format

```json
{
  "flightList": [{
    "departureStation": "MUC",
    "arrivalStation": "CHI",
    "from": "2025-12-20",
    "to": "2025-12-27"
  }],
  "adultCount": 2,
  "childCount": 2,
  "infantCount": 0
}
```

### Response Format

```json
{
  "outboundFlights": [{
    "price": {"amount": 45.99, "currencyCode": "EUR"},
    "departureDates": "2025-12-20T14:30:00",
    "arrivalDates": "2025-12-20T17:45:00",
    "flightNumber": "W6 1234"
  }],
  "returnFlights": [...]
}
```

## Usage

### Basic Usage (API Only)

```python
from datetime import date
from app.scrapers import WizzAirScraper

scraper = WizzAirScraper()

flights = await scraper.search_flights(
    origin="MUC",           # Munich
    destination="CHI",      # Chisinau
    departure_date=date(2025, 12, 20),
    return_date=date(2025, 12, 27),
    adult_count=2,
    child_count=2
)

for flight in flights:
    print(f"{flight['origin']} -> {flight['destination']}")
    print(f"Price: €{flight['price']:.2f}/person")
```

### Save to Database

```python
from app.database import get_async_session_context
from app.scrapers import scrape_wizzair_flights

async with get_async_session_context() as db:
    saved_flights = await scrape_wizzair_flights(
        db=db,
        origin="MUC",
        destination="CHI",
        departure_date=date(2025, 12, 20),
        return_date=date(2025, 12, 27)
    )
    print(f"Saved {len(saved_flights)} flights")
```

### One-Way Flights

```python
flights = await scraper.search_flights(
    origin="VIE",
    destination="CHI",
    departure_date=date(2025, 12, 20),
    return_date=None  # One-way
)
```

## Error Handling

### Rate Limiting

WizzAir may return HTTP 429 if you make too many requests:

```python
from app.scrapers import WizzAirRateLimitError

try:
    flights = await scraper.search_flights(...)
except WizzAirRateLimitError as e:
    print(f"Rate limited: {e}")
    # Wait 60 seconds before retrying
    await asyncio.sleep(60)
```

### Network Errors

```python
import httpx
from app.scrapers import WizzAirAPIError

try:
    flights = await scraper.search_flights(...)
except httpx.RequestError as e:
    print(f"Network error: {e}")
except WizzAirAPIError as e:
    print(f"API error: {e}")
```

## Testing

Run the comprehensive test suite:

```bash
poetry run pytest tests/unit/test_wizzair_scraper.py -v
```

Tests include:
- ✅ Payload building (round-trip, one-way)
- ✅ API response parsing
- ✅ Flight combination logic
- ✅ Error handling (rate limits, network errors)
- ✅ Database integration
- ✅ Airport lookups

## API Headers Required

```python
headers = {
    'User-Agent': 'Mozilla/5.0 ...',
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'Origin': 'https://wizzair.com',
    'Referer': 'https://wizzair.com/'
}
```

## Data Mapping

WizzAir API → Database Schema:

| API Field | Database Field | Notes |
|-----------|----------------|-------|
| `departureDates` | `departure_date`, `departure_time` | ISO datetime split |
| `arrivalDates` | - | Used for validation |
| `price.amount` | `price_per_person` | Per person |
| `price.currencyCode` | - | Assumed EUR |
| `flightNumber` | - | For reference |
| `departureStation` | `origin_airport_id` | Lookup by IATA |
| `arrivalStation` | `destination_airport_id` | Lookup by IATA |

Additional fields set:
- `airline` = "WizzAir"
- `source` = "wizzair"
- `direct_flight` = `true` (WizzAir mostly operates direct)
- `booking_class` = "Economy"
- `total_price` = `price_per_person * (adult_count + child_count)`

## Important Routes

WizzAir has excellent coverage to:

- **Moldova**: Chisinau (CHI)
- **Romania**: Bucharest (BUH), Cluj (CLJ), Iasi (IAS)
- **Bulgaria**: Sofia (SOF), Varna (VAR)
- **Poland**: Warsaw (WAW), Krakow (KRK), Gdansk (GDN)
- **Hungary**: Budapest (BUD)
- **Ukraine**: Kyiv (IEV) [subject to current restrictions]

## Limitations & Notes

### API Limitations

1. **Unofficial API** - May change without notice
2. **Rate Limiting** - Typically ~60 requests/minute
3. **No Seat Selection** - API doesn't provide seat availability
4. **Limited Fare Details** - No breakdown of fees/taxes

### Known Issues

1. **API Version** - The `*` wildcard works but may need updating
2. **Date Format** - Must be ISO format `YYYY-MM-DD`
3. **IATA Codes** - WizzAir uses non-standard codes for some airports (e.g., `CHI` for Chisinau)

## Maintenance

### If the API Stops Working

1. **Inspect Network Traffic**:
   - Open https://wizzair.com in Chrome
   - Open DevTools → Network tab
   - Search for a flight
   - Find the API call to `Api/search/search`
   - Check if endpoint URL changed
   - Verify request payload format

2. **Update the Scraper**:
   - Update `BASE_URL` in `wizzair_scraper.py:56`
   - Update `_build_payload()` if request format changed
   - Update `_parse_api_response()` if response format changed
   - Run tests to verify: `pytest tests/unit/test_wizzair_scraper.py`

3. **Common Changes**:
   - API version number in URL
   - Additional required headers
   - New required fields in payload
   - Renamed fields in response

### Monitoring Recommendations

Set up alerts for:
- HTTP 403 (Forbidden) - IP might be blocked
- HTTP 429 (Rate Limited) - Too many requests
- HTTP 500 (Server Error) - WizzAir API issues
- Empty flight results - API format may have changed

## Performance

**Typical Performance**:
- API call: 500-1500ms
- Parsing: <10ms
- Database save: 50-100ms
- **Total**: ~1-2 seconds per route

**Optimization Tips**:
- Use parallel searches for multiple routes: `asyncio.gather()`
- Cache airport lookups to reduce DB queries
- Batch database inserts for multiple flights
- Implement request rate limiting to avoid 429 errors

## Examples

See `examples/wizzair_scraper_example.py` for complete examples including:
- Simple API search
- Database integration
- One-way flights
- Multiple routes in parallel
- Error handling patterns

## Contributing

When adding features:
1. Add tests in `tests/unit/test_wizzair_scraper.py`
2. Update this README
3. Run full test suite: `poetry run pytest`
4. Check code quality: `poetry run black . && poetry run ruff check .`

## License

Part of SmartFamilyTravelScout project.
