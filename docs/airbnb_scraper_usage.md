# Airbnb Scraper Usage Guide

This guide explains how to use the AirbnbClient to collect family-friendly Airbnb listings.

## Overview

The `AirbnbClient` provides two methods for scraping Airbnb data:

1. **Apify Integration (Primary)**: Uses Apify's pre-built Airbnb Scraper actor
2. **Playwright Fallback**: Direct web scraping when Apify is unavailable

## Setup

### 1. Register for Apify (Recommended)

1. Sign up at [apify.com](https://apify.com) (free account)
2. Get your API token from Settings > Integrations
3. Add to your `.env` file:

```bash
APIFY_API_KEY=your_apify_api_key_here
```

### 2. Install Dependencies

```bash
poetry install
# or
pip install apify-client playwright
```

### 3. Apify Free Tier Limits

- **5,000 results/month**
- **$5 free credit**
- Enough for ~100 searches (50 listings each)

## Basic Usage

### Simple Search

```python
from datetime import date
from app.scrapers.airbnb_scraper import AirbnbClient

# Initialize client
client = AirbnbClient()  # Uses APIFY_API_KEY from settings

# Search for listings
listings = await client.search(
    city="Lisbon, Portugal",
    check_in=date(2025, 12, 20),
    check_out=date(2025, 12, 27),
    adults=2,
    children=2,
    max_listings=20
)

print(f"Found {len(listings)} listings")
```

### Search with Family Filtering

```python
# Search and filter for family-suitable accommodations
all_listings = await client.search(
    city="Barcelona, Spain",
    check_in=date(2025, 12, 20),
    check_out=date(2025, 12, 27)
)

# Filter for family criteria
family_listings = client.filter_family_suitable(all_listings)

print(f"Family-suitable: {len(family_listings)} of {len(all_listings)}")
```

### Save to Database

```python
# Search and save to database
listings = await client.search(
    city="Porto, Portugal",
    check_in=date(2025, 12, 20),
    check_out=date(2025, 12, 27)
)

# Filter for family
family_listings = client.filter_family_suitable(listings)

# Save to database
saved_count = await client.save_to_database(family_listings)
print(f"Saved {saved_count} accommodations to database")
```

### Complete Example

```python
import asyncio
import os
from datetime import date
from app.scrapers.airbnb_scraper import AirbnbClient


async def search_airbnb_for_family():
    """Complete example: Search, filter, and save."""

    # Initialize client
    client = AirbnbClient(apify_api_key=os.getenv('APIFY_API_KEY'))

    # Search parameters
    city = "Lisbon, Portugal"
    check_in = date(2025, 12, 20)
    check_out = date(2025, 12, 27)

    try:
        # Search Airbnb
        print(f"Searching Airbnb in {city}...")
        listings = await client.search(
            city=city,
            check_in=check_in,
            check_out=check_out,
            adults=2,
            children=2,
            max_listings=50
        )

        print(f"Found {len(listings)} total listings")

        # Filter for family-suitable
        family_listings = client.filter_family_suitable(listings)
        print(f"Family-suitable: {len(family_listings)} listings")

        # Show some results
        for listing in family_listings[:5]:
            print(f"\n{listing['name']}")
            print(f"  Bedrooms: {listing['bedrooms']}")
            print(f"  Price: €{listing['price_per_night']}/night")
            print(f"  Rating: {listing.get('rating', 'N/A')}")
            print(f"  URL: {listing['url']}")

        # Save to database
        saved_count = await client.save_to_database(family_listings)
        print(f"\nSaved {saved_count} new accommodations to database")

        # Check credits used
        credits = client.get_credits_used()
        print(f"Apify credits used: {credits:.4f}")

    except Exception as e:
        print(f"Error: {e}")


# Run the example
if __name__ == "__main__":
    asyncio.run(search_airbnb_for_family())
```

## Family-Friendly Criteria

The `filter_family_suitable()` method filters listings based on:

- **Bedrooms**: Minimum 2 bedrooms
- **Kitchen**: Must have a kitchen
- **Price**: Maximum €150/night
- **Property Type**: "Entire place" only (set in search)

## Apify Actor Input

The client automatically builds the Apify input:

```python
{
    "locationQuery": "Lisbon, Portugal",
    "checkIn": "2025-12-20",
    "checkOut": "2025-12-27",
    "currency": "EUR",
    "adults": 2,
    "children": 2,
    "propertyType": ["Entire place"],
    "minBedrooms": 2,
    "amenities": ["Kitchen"],
    "maxListings": 20,
    "includeReviews": false
}
```

## Playwright Fallback

If Apify is unavailable or fails, the client automatically falls back to Playwright scraping:

```python
# Apify will be tried first, then Playwright if it fails
client = AirbnbClient()
listings = await client.search(...)  # Automatically uses fallback if needed
```

To force Playwright (without Apify):

```python
# Don't provide API key
client = AirbnbClient(apify_api_key=None)
listings = await client.search(...)  # Uses Playwright
```

## Database Schema

Listings are saved to the `accommodations` table:

| Column | Type | Description |
|--------|------|-------------|
| name | String | Listing name |
| type | String | "apartment" for Airbnb |
| destination_city | String | City name |
| bedrooms | Integer | Number of bedrooms |
| price_per_night | Numeric | Price in EUR |
| family_friendly | Boolean | Family-friendly indicator |
| has_kitchen | Boolean | Has kitchen |
| rating | Numeric | Rating (0-5) |
| review_count | Integer | Number of reviews |
| source | String | "airbnb" |
| url | String | Airbnb listing URL |
| image_url | String | Primary image URL |
| scraped_at | DateTime | Scrape timestamp |

## Cost Tracking

Track Apify credits used:

```python
client = AirbnbClient()

# Perform searches
await client.search(...)
await client.search(...)

# Check total credits used
total_credits = client.get_credits_used()
print(f"Total Apify credits used: {total_credits:.4f}")
```

## Error Handling

The client handles errors gracefully:

```python
try:
    listings = await client.search(
        city="Invalid City",
        check_in=date(2025, 12, 20),
        check_out=date(2025, 12, 27)
    )
except Exception as e:
    print(f"Search failed: {e}")
    # Falls back to Playwright automatically
```

## Best Practices

1. **Cache Results**: Avoid re-scraping same dates
2. **Batch Searches**: Search multiple cities in one session
3. **Monitor Credits**: Check `get_credits_used()` regularly
4. **Filter Early**: Use Apify filters to reduce results
5. **Save Incrementally**: Save to database after each city

## CLI Integration

Create a CLI command for searching:

```python
# In app/cli/main.py
import typer
from datetime import date
from app.scrapers.airbnb_scraper import AirbnbClient

app = typer.Typer()

@app.command()
def search_airbnb(
    city: str,
    check_in: str,
    check_out: str,
    max_listings: int = 20
):
    """Search Airbnb for family-friendly listings."""
    import asyncio

    async def run():
        client = AirbnbClient()
        listings = await client.search(
            city=city,
            check_in=date.fromisoformat(check_in),
            check_out=date.fromisoformat(check_out),
            max_listings=max_listings
        )

        family_listings = client.filter_family_suitable(listings)
        await client.save_to_database(family_listings)

        print(f"Found and saved {len(family_listings)} family-friendly listings")

    asyncio.run(run())
```

Usage:

```bash
poetry run scout search-airbnb "Lisbon, Portugal" 2025-12-20 2025-12-27
```

## Troubleshooting

### Apify Not Working

1. Check API key in `.env`
2. Verify Apify account has credits
3. Check actor ID is correct: `dtrungtin/airbnb-scraper`

### Playwright Fails

1. Install Playwright browsers: `playwright install chromium`
2. Check internet connection
3. Verify Airbnb is accessible

### No Results

1. Try broader search (increase `max_listings`)
2. Relax filters (check `MIN_BEDROOMS`, `MAX_PRICE_PER_NIGHT`)
3. Verify city name format: "City, Country"

## References

- [Apify Airbnb Scraper](https://apify.com/dtrungtin/airbnb-scraper)
- [Apify Python Client](https://docs.apify.com/api/client/python/)
- [Playwright Python](https://playwright.dev/python/)
