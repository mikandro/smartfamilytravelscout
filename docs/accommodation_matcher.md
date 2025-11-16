# AccommodationMatcher Documentation

## Overview

The `AccommodationMatcher` is a core orchestration component that pairs flights with accommodations to generate complete trip packages. It calculates comprehensive trip costs, filters by budget and school holidays, and creates `TripPackage` database records ready for AI scoring.

## Features

- **Smart Matching**: Automatically pairs flights with accommodations in the same destination city
- **Comprehensive Cost Calculation**: Includes flights, accommodation, food, and activities
- **Budget Filtering**: Only generates packages within specified budget constraints
- **Duration Filtering**: Filters trips by minimum/maximum night requirements
- **School Holiday Filtering**: Ensures trips align with Bavaria school calendar
- **Batch Processing**: Efficient database operations with progress tracking
- **Rich Console Output**: Beautiful progress bars and summary tables

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    AccommodationMatcher                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Query flights with true_cost calculated                    │
│     ↓                                                           │
│  2. Group by destination city                                  │
│     ↓                                                           │
│  3. Match with accommodations in same city                     │
│     ↓                                                           │
│  4. Calculate total trip costs                                 │
│     - Flight true cost (incl. baggage, parking, fuel, time)    │
│     - Accommodation (price_per_night × nights)                 │
│     - Food estimate (€100/day for family of 4)                 │
│     - Activities budget (€50/day)                              │
│     ↓                                                           │
│  5. Filter by budget and trip duration                         │
│     ↓                                                           │
│  6. Filter by school holidays (optional)                       │
│     ↓                                                           │
│  7. Create TripPackage database records                        │
│     ↓                                                           │
│  8. Save to database (batch operations)                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Cost Breakdown

### Flight True Cost
The flight's `true_cost` field already includes all flight-related expenses:
- Base flight price (for 4 people)
- Baggage fees (€30/bag for budget airlines)
- Airport parking costs (varies by airport)
- Fuel costs for driving to airport (€0.08/km × distance × 2)
- Time value of driving (€20/hour × driving time × 2)

### Accommodation Cost
```python
accommodation_cost = price_per_night × num_nights
```

### Food Cost
Estimated at €100/day for a family of 4:
```python
food_cost = 100.0 × num_nights
```

### Activities Cost
Budgeted at €50/day for family activities:
```python
activities_cost = 50.0 × num_nights
```

### Total Trip Cost
```python
total = flight_true_cost + accommodation_cost + food_cost + activities_cost
```

## Usage

### Basic Usage

```python
import asyncio
from app.database import get_async_session_context
from app.orchestration.accommodation_matcher import AccommodationMatcher

async def generate_packages():
    matcher = AccommodationMatcher()

    async with get_async_session_context() as db:
        packages = await matcher.generate_trip_packages(
            db,
            max_budget=2000.0,
            min_nights=3,
            max_nights=10,
            filter_holidays=True
        )

        print(f"Generated {len(packages)} trip packages")

        # Save to database
        stats = await matcher.save_packages(db, packages)
        print(f"Saved {stats['inserted']} packages")

asyncio.run(generate_packages())
```

### Custom Budget Constraints

```python
# Budget trips (< €1500)
budget_packages = await matcher.generate_trip_packages(
    db,
    max_budget=1500.0,
    min_nights=3,
    max_nights=7
)

# Luxury trips (€2000-€3000)
all_packages = await matcher.generate_trip_packages(
    db,
    max_budget=3000.0,
    min_nights=5,
    max_nights=10
)
luxury_packages = [p for p in all_packages if p.total_price >= 2000]
```

### Weekend Getaways

```python
# 3-4 night trips only
weekend_packages = await matcher.generate_trip_packages(
    db,
    max_budget=1500.0,
    min_nights=3,
    max_nights=4
)
```

### Destination-Specific Packages

```python
# Generate all packages
all_packages = await matcher.generate_trip_packages(db)

# Filter by destination
lisbon_packages = [p for p in all_packages if p.destination_city == "Lisbon"]
prague_packages = [p for p in all_packages if p.destination_city == "Prague"]
```

### Cost Breakdown Analysis

```python
# Calculate detailed costs
cost = matcher.calculate_trip_cost(flight, accommodation, num_nights)

print(f"Flight cost:        €{cost['flight_cost']:.2f}")
print(f"Accommodation cost: €{cost['accommodation_cost']:.2f}")
print(f"Food cost:          €{cost['food_cost']:.2f}")
print(f"Activities cost:    €{cost['activities_cost']:.2f}")
print(f"Total:              €{cost['total']:.2f}")
print(f"Per person:         €{cost['per_person']:.2f}")
```

## API Reference

### `AccommodationMatcher`

#### `__init__()`
Initialize the matcher.

```python
matcher = AccommodationMatcher()
```

#### `generate_trip_packages(db, max_budget, min_nights, max_nights, filter_holidays)`
Generate all valid trip package combinations.

**Parameters:**
- `db` (AsyncSession): Database session
- `max_budget` (float): Maximum total trip budget in EUR (default: 2000.0)
- `min_nights` (int): Minimum trip duration (default: 3)
- `max_nights` (int): Maximum trip duration (default: 10)
- `filter_holidays` (bool): Filter by school holidays (default: True)

**Returns:** List of TripPackage objects

**Example:**
```python
packages = await matcher.generate_trip_packages(
    db, max_budget=2500.0, min_nights=5, max_nights=7
)
```

#### `calculate_trip_cost(flight, accommodation, num_nights)`
Calculate total trip cost with detailed breakdown.

**Parameters:**
- `flight` (Flight): Flight object with true_cost calculated
- `accommodation` (Accommodation): Accommodation object
- `num_nights` (int): Number of nights

**Returns:** Dictionary with cost breakdown

**Example:**
```python
cost = matcher.calculate_trip_cost(flight, accommodation, 7)
# Returns: {'flight_cost': 559.27, 'accommodation_cost': 560.0, ...}
```

#### `create_trip_package(flight, accommodation, cost_breakdown)`
Create TripPackage database object.

**Parameters:**
- `flight` (Flight): Flight object
- `accommodation` (Accommodation): Accommodation object
- `cost_breakdown` (Dict): Cost breakdown from calculate_trip_cost()

**Returns:** TripPackage object

**Example:**
```python
package = matcher.create_trip_package(flight, accommodation, cost)
db.add(package)
await db.commit()
```

#### `filter_by_school_holidays(db, packages)`
Filter packages to only include trips during school holidays.

**Parameters:**
- `db` (AsyncSession): Database session
- `packages` (List[TripPackage]): Packages to filter

**Returns:** Filtered list of TripPackage objects

**Example:**
```python
filtered = await matcher.filter_by_school_holidays(db, packages)
```

#### `save_packages(db, packages)`
Batch save trip packages to database.

**Parameters:**
- `db` (AsyncSession): Database session
- `packages` (List[TripPackage]): Packages to save

**Returns:** Dictionary with statistics: `{'total', 'inserted', 'skipped'}`

**Example:**
```python
stats = await matcher.save_packages(db, packages)
print(f"Inserted {stats['inserted']}, Skipped {stats['skipped']}")
```

#### `print_package_summary(db, packages)`
Print a Rich table summary of packages.

**Parameters:**
- `db` (AsyncSession): Database session
- `packages` (List[TripPackage]): Packages to display

**Example:**
```python
await matcher.print_package_summary(db, packages)
```

## Database Schema

### TripPackage Model

```python
class TripPackage:
    id: int
    package_type: str              # 'family' or 'parent_escape'
    flights_json: List[int]         # Array of flight IDs
    accommodation_id: int           # FK to accommodations
    events_json: List[int]          # Array of event IDs (empty initially)
    destination_city: str           # e.g., 'Lisbon', 'Prague'
    departure_date: date
    return_date: date
    num_nights: int
    total_price: float              # Total package price
    ai_score: float                 # AI-generated score (filled later)
    ai_reasoning: str               # AI explanation (filled later)
    notified: bool                  # User notification status
```

## Performance

### Efficiency
- **Parallel Queries**: Uses SQLAlchemy's `selectinload()` to avoid N+1 queries
- **Batch Operations**: Commits database changes in batches (50 packages)
- **Progress Tracking**: Real-time progress bars using Rich
- **Smart Filtering**: Filters in-memory to minimize database queries

### Expected Output
For a typical dataset:
- **10 destination cities**
- **50 flights** with true costs calculated
- **30 accommodations** across destinations
- **5 flights per city** (average)
- **3 accommodations per city** (average)

Expected packages: **150-200 total** (after budget and holiday filtering)

## Integration

### Pipeline Position

```
1. FlightOrchestrator        → Scrape & deduplicate flights
2. TrueCostCalculator        → Calculate flight true costs
3. AccommodationScraper      → Scrape accommodations
4. AccommodationMatcher      → Generate trip packages ⭐ YOU ARE HERE
5. EventMatcher              → Add events to packages
6. AIScorer                  → Score packages with Claude
7. NotificationService       → Notify user of best deals
```

### Integration Example

```python
from app.orchestration.flight_orchestrator import FlightOrchestrator
from app.orchestration.accommodation_matcher import AccommodationMatcher
from app.utils.cost_calculator import TrueCostCalculator

async def full_pipeline():
    async with get_async_session_context() as db:
        # 1. Scrape flights
        orchestrator = FlightOrchestrator()
        flights = await orchestrator.scrape_all(
            origins=['MUC', 'FMM'],
            destinations=['LIS', 'BCN', 'PRG'],
            date_ranges=[(date(2025, 12, 20), date(2025, 12, 27))]
        )
        await orchestrator.save_to_database(flights)

        # 2. Calculate true costs
        calculator = TrueCostCalculator(db)
        await calculator.load_airports_async()

        flight_objects = (await db.execute(select(Flight))).scalars().all()
        await calculator.calculate_for_all_flights_async(flight_objects)

        # 3. Generate trip packages
        matcher = AccommodationMatcher()
        packages = await matcher.generate_trip_packages(db, max_budget=2000.0)
        await matcher.save_packages(db, packages)

        print(f"Pipeline complete: {len(packages)} packages generated")
```

## Testing

Run the comprehensive unit tests:

```bash
pytest tests/unit/test_accommodation_matcher.py -v
```

Test coverage includes:
- ✅ Cost calculations (multiple scenarios)
- ✅ Package creation
- ✅ Flight-accommodation matching
- ✅ School holiday filtering
- ✅ Budget filtering
- ✅ Database operations
- ✅ Edge cases (empty data, missing costs, etc.)

## Examples

See `examples/accommodation_matcher_example.py` for comprehensive usage examples including:
1. Basic package generation
2. Custom budget constraints
3. Destination-specific filtering
4. Cost breakdown analysis
5. Weekend getaway packages

Run examples:
```bash
python examples/accommodation_matcher_example.py
```

## Troubleshooting

### "No packages generated"
**Cause**: No flights with calculated true costs, or no matching accommodations

**Solution**:
```python
# Check flights with true costs
flights = await db.execute(select(Flight).where(Flight.true_cost.isnot(None)))
print(f"Flights with true cost: {len(flights.scalars().all())}")

# Check accommodations
accommodations = await db.execute(select(Accommodation))
print(f"Total accommodations: {len(accommodations.scalars().all())}")
```

### "All packages filtered out by holidays"
**Cause**: No flights during school holiday periods

**Solution**:
```python
# Disable holiday filtering temporarily
packages = await matcher.generate_trip_packages(
    db, filter_holidays=False
)
```

### "Packages over budget"
**Cause**: Budget too low for available options

**Solution**:
```python
# Increase budget or reduce trip duration
packages = await matcher.generate_trip_packages(
    db,
    max_budget=3000.0,  # Increase budget
    max_nights=7        # Reduce max nights
)
```

## Future Enhancements

- [ ] Add support for multi-city trips
- [ ] Include flight + hotel bundle discounts
- [ ] Support for apartment vs hotel preferences
- [ ] Dynamic food/activity cost estimation based on destination
- [ ] Integration with real-time pricing updates
- [ ] Support for flexible date ranges (±3 days)

## See Also

- [TrueCostCalculator Documentation](./true_cost_calculator.md)
- [FlightOrchestrator Documentation](./flight_orchestrator.md)
- [Database Schema](./DATABASE_SCHEMA.md)
