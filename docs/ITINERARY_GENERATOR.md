# Itinerary Generator

AI-powered itinerary generator for high-scoring family trips, optimized for families with young children (ages 3 & 6).

## Overview

The Itinerary Generator uses Claude API to create detailed 3-day family itineraries for trip packages that score above 70 (configurable threshold). Each itinerary includes:

- **Day-by-day planning** with morning, afternoon, and evening sections
- **Kid-friendly activities** appropriate for ages 3 and 6
- **Nap time considerations** (1-2pm daily for the 3-year-old)
- **Restaurant recommendations** with family amenities (high chairs, kids menu)
- **Walking distances** from accommodation
- **Weather backup plans** for rainy days
- **Practical tips** for traveling with young children
- **Packing essentials** specific to the destination

## Features

### Core Functionality

- ✅ **Smart Threshold Filtering**: Only generates itineraries for high-scoring trips (default: 70+)
- ✅ **Caching**: Reuses existing itineraries to save API costs
- ✅ **Batch Processing**: Generate multiple itineraries in one call
- ✅ **Database Integration**: Automatically saves to `trip_packages.itinerary_json`
- ✅ **Cost Tracking**: Monitors Claude API usage and costs
- ✅ **Error Handling**: Robust validation and error recovery

### Family-Friendly Optimization

The generator is specifically optimized for families with:
- 2 adults
- 2 children (ages 3 & 6)

It accounts for:
- **Nap times**: 1-2pm daily for the 3-year-old
- **Energy levels**: High-energy activities in the morning (9am-12pm)
- **Attention spans**: Maximum 2 major activities per day
- **Rest breaks**: Every 2-3 hours
- **Early bedtime**: Activities end by 7pm

## Usage

### Basic Usage

```python
from redis.asyncio import Redis
from app.ai import ClaudeClient, ItineraryGenerator
from app.database import AsyncSessionLocal

# Initialize clients
redis = Redis.from_url("redis://localhost:6379")
async with AsyncSessionLocal() as db:
    claude_client = ClaudeClient(
        api_key="your-api-key",
        redis_client=redis,
        db_session=db,
    )

    generator = ItineraryGenerator(
        claude_client=claude_client,
        db_session=db,
        min_score_threshold=70.0,
    )

    # Generate itinerary for a trip
    itinerary = await generator.generate_itinerary(
        trip_package=trip,
        save_to_db=True,
    )

    print(itinerary["day_1"]["morning"])
```

### Force Generation for Low-Scoring Trips

```python
# Generate even if score is below threshold
itinerary = await generator.generate_itinerary(
    trip_package=low_score_trip,
    force=True,
    save_to_db=True,
)
```

### Batch Generation

```python
# Generate itineraries for multiple trips
results = await generator.generate_batch(
    trip_packages=[trip1, trip2, trip3],
    save_to_db=True,
    skip_errors=True,
)

for trip_id, itinerary in results.items():
    print(f"Generated itinerary for trip {trip_id}")
```

### Get Summary

```python
# Get a brief text summary
summary = await generator.get_itinerary_summary(trip)
print(summary)
```

## Output Format

The generated itinerary follows this JSON structure:

```json
{
  "day_1": {
    "morning": "Detailed morning plan...",
    "afternoon": "Afternoon plan (accounting for 1-2pm nap)...",
    "evening": "Evening activities and dinner...",
    "breakfast_spot": "Restaurant name and why it's good for families",
    "lunch_spot": "Restaurant with distance from activities",
    "dinner_spot": "Restaurant with high chairs info",
    "weather_backup": "Indoor activities if weather is bad"
  },
  "day_2": { ... },
  "day_3": { ... },
  "tips": [
    "Practical tip 1",
    "Practical tip 2",
    ...
  ],
  "packing_essentials": [
    "Stroller",
    "Sunscreen",
    ...
  ]
}
```

## Configuration

### Threshold Settings

```python
generator = ItineraryGenerator(
    claude_client=claude_client,
    min_score_threshold=75.0,  # Only generate for scores >= 75
)
```

### Prompt Customization

The prompt template is stored in `app/ai/prompts/itinerary_generation.txt` and can be customized to adjust:
- Activity types
- Restaurant criteria
- Timing preferences
- Output format

## Cost Estimation

Based on Claude Sonnet 4.5 pricing:
- **Average cost per itinerary**: ~$0.02-0.04 USD
- **Token usage**: ~1,300 tokens (500 input + 800 output)
- **Caching**: Saves 100% on repeated requests

For 100 high-scoring trips/month: ~$2-4 USD

## Examples

See `examples/itinerary_generator_example.py` for:
1. Basic itinerary generation
2. Batch processing
3. Force generation for low scores
4. JSON export
5. Summary generation

Run examples:
```bash
python examples/itinerary_generator_example.py
```

## Testing

Unit tests are available in `tests/unit/test_itinerary_generator.py`:

```bash
pytest tests/unit/test_itinerary_generator.py -v
```

Tests cover:
- ✅ Basic generation
- ✅ Threshold filtering
- ✅ Force generation
- ✅ Caching behavior
- ✅ Batch processing
- ✅ Validation logic
- ✅ Error handling
- ✅ Database integration

## Integration with Trip Pipeline

The itinerary generator integrates into the main trip analysis pipeline:

```
1. Scrape flights + accommodations
2. Match and create trip packages
3. AI scoring (DealScorer)
4. Filter by score threshold (> 70)
5. → Generate itineraries (ItineraryGenerator) ← YOU ARE HERE
6. Send email notifications
```

Typical workflow:

```python
from app.ai import ItineraryGenerator

# After deal scoring
high_scoring_trips = [trip for trip in trips if trip.ai_score >= 70]

# Generate itineraries
for trip in high_scoring_trips:
    itinerary = await generator.generate_itinerary(
        trip_package=trip,
        save_to_db=True,
    )

    # Itinerary is now available in trip.itinerary_json
```

## Database Schema

Itineraries are stored in the `trip_packages` table:

```sql
-- trip_packages table
itinerary_json JSONB NULL  -- Generated itinerary structure
```

Access via SQLAlchemy:

```python
trip = db.query(TripPackage).filter_by(id=123).first()
itinerary = trip.itinerary_json

# Access specific day
day_1_morning = itinerary["day_1"]["morning"]
```

## Error Handling

The generator handles various error scenarios:

```python
from app.ai.itinerary_generator import ItineraryGenerationError

try:
    itinerary = await generator.generate_itinerary(trip)
except ItineraryGenerationError as e:
    # Handle generation errors
    logger.error(f"Failed to generate itinerary: {e}")
```

Common errors:
- **Below threshold**: Trip score too low (use `force=True` to override)
- **Invalid structure**: Claude returned unexpected format
- **Database error**: Failed to save to database
- **API error**: Claude API call failed

## Best Practices

1. **Use caching**: Don't set `force=True` unless necessary
2. **Batch when possible**: More efficient than individual calls
3. **Monitor costs**: Check `_cost` field in responses
4. **Validate scores**: Only generate for high-scoring trips (70+)
5. **Handle errors gracefully**: Use try/except and `skip_errors=True` in batch mode

## Future Enhancements

Potential improvements for future versions:

- [ ] Multi-language itinerary generation
- [ ] Customizable activity types (cultural, adventure, relaxation)
- [ ] Integration with real-time event APIs
- [ ] Price-conscious restaurant filtering
- [ ] Accessibility options
- [ ] Longer trip durations (5-7 days)
- [ ] Parent escape mode variants
- [ ] PDF export with maps

## Support

For issues or questions:
1. Check example files in `examples/`
2. Review unit tests for usage patterns
3. See main documentation in `IMPLEMENTATION_SPEC.md`
4. Check Claude API logs for debugging

## License

Part of SmartFamilyTravelScout project.
