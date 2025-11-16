# True Cost Calculator

## Overview

The **TrueCostCalculator** computes the real total cost of flying from each airport by including all hidden expenses that budget comparisons often miss.

### The Problem

A €100 flight from Memmingen (FMM) might actually cost MORE than a €150 flight from Munich (MUC) when you factor in:

- **110km drive** to FMM vs 40km to MUC
- **Parking costs**: €5/day at FMM vs €15/day at MUC (7 days = €35 vs €105)
- **Fuel costs**: €17.60 for FMM vs €6.40 for MUC (round trip)
- **Time value**: 140 minutes driving to FMM vs 45 minutes to MUC
- **Baggage fees**: €60 for Ryanair vs €0 for Lufthansa (2 bags for family of 4)

### The Solution

The TrueCostCalculator provides a complete cost breakdown that includes:

1. **Base Price**: Flight price from scraper
2. **Baggage Fees**: €30/bag for budget airlines, €0 for legacy carriers
3. **Parking**: Airport-specific daily rates
4. **Fuel**: €0.08/km × distance × 2 (round trip)
5. **Time Value**: €20/hour × driving time × 2 (opportunity cost)

## Installation

The calculator is already integrated into the SmartFamilyTravelScout app:

```python
from app.utils.cost_calculator import TrueCostCalculator
from app.database import get_sync_session
```

## Quick Start

### Basic Usage (Synchronous)

```python
from app.utils.cost_calculator import TrueCostCalculator
from app.database import get_sync_session
from app.models.flight import Flight
from sqlalchemy import select

# Get database session
db = get_sync_session()

# Initialize calculator
calc = TrueCostCalculator(db)

# Load airport data (do this once)
calc.load_airports()

# Get a flight
flight = db.execute(
    select(Flight).where(Flight.id == 123)
).scalar_one()

# Calculate true cost
breakdown = calc.calculate_total_true_cost(flight, num_bags=2)

# Display results
calc.print_breakdown(breakdown)
```

### Async Usage

```python
from app.utils.cost_calculator import TrueCostCalculator
from app.database import get_async_session_context
from app.models.flight import Flight
from sqlalchemy import select

async def calculate_costs():
    async with get_async_session_context() as db:
        # Initialize calculator
        calc = TrueCostCalculator(db)

        # Load airport data
        await calc.load_airports_async()

        # Get flights
        result = await db.execute(select(Flight).limit(10))
        flights = result.scalars().all()

        # Batch calculate
        breakdowns = await calc.calculate_for_all_flights_async(
            flights,
            num_bags=2,
            commit=True
        )

        return breakdowns
```

## Cost Breakdown Example

```python
breakdown = calc.calculate_total_true_cost(flight, num_bags=2)
```

Returns:

```python
{
    'base_price': 400.00,        # Flight price for 4 people
    'baggage': 60.00,            # 2 bags × €30 (Ryanair)
    'parking': 35.00,            # 7 days × €5/day (FMM)
    'fuel': 17.60,               # 110km × 2 × €0.08/km
    'time_value': 93.33,         # 140min × 2 ÷ 60 × €20/hour
    'total_true_cost': 605.93,   # Sum of all costs
    'hidden_costs': 205.93,      # Everything except base price
    'cost_per_person': 151.48,   # Total ÷ 4 people
    'airport_iata': 'FMM',
    'airline': 'Ryanair',
    'num_days': 7,
    'num_bags': 2
}
```

## Detailed Examples

### Example 1: Budget Airline vs Legacy Carrier

```python
# Ryanair from FMM: €100 base price
fmm_flight = db.execute(
    select(Flight)
    .where(Flight.airline == 'Ryanair')
    .where(Flight.origin_airport.has(iata_code='FMM'))
).scalar_one()

# Lufthansa from MUC: €150 base price
muc_flight = db.execute(
    select(Flight)
    .where(Flight.airline == 'Lufthansa')
    .where(Flight.origin_airport.has(iata_code='MUC'))
).scalar_one()

# Calculate both
fmm_breakdown = calc.calculate_total_true_cost(fmm_flight, num_bags=2)
muc_breakdown = calc.calculate_total_true_cost(muc_flight, num_bags=2)

# Compare
print(f"FMM base: €{fmm_breakdown['base_price']}")
print(f"FMM true cost: €{fmm_breakdown['total_true_cost']}")
print(f"FMM hidden costs: €{fmm_breakdown['hidden_costs']}")
print()
print(f"MUC base: €{muc_breakdown['base_price']}")
print(f"MUC true cost: €{muc_breakdown['total_true_cost']}")
print(f"MUC hidden costs: €{muc_breakdown['hidden_costs']}")
```

**Output:**
```
FMM base: €100.00
FMM true cost: €305.93
FMM hidden costs: €205.93

MUC base: €150.00
MUC true cost: €291.40
MUC hidden costs: €141.40
```

**Result**: Despite FMM being €50 cheaper on paper, MUC is actually €14.53 cheaper when accounting for all costs!

### Example 2: Batch Update All Flights

```python
from sqlalchemy import select

# Get all flights
result = db.execute(select(Flight))
flights = result.scalars().all()

# Calculate true costs for all and update database
breakdowns = calc.calculate_for_all_flights(
    flights,
    num_bags=2,
    commit=True
)

print(f"Updated {len(breakdowns)} flights with true costs")

# Now you can query flights by true_cost
cheapest_true_cost = db.execute(
    select(Flight)
    .where(Flight.true_cost.isnot(None))
    .order_by(Flight.true_cost.asc())
    .limit(5)
).scalars().all()

for flight in cheapest_true_cost:
    print(f"{flight.route}: €{flight.true_cost:.2f}")
```

### Example 3: Custom Parameters

```python
# Calculate with 3 bags instead of 2
breakdown = calc.calculate_total_true_cost(
    flight,
    num_bags=3,
    num_days=10  # Override auto-detected trip duration
)

print(f"Baggage cost for 3 bags: €{breakdown['baggage']}")
print(f"Parking for 10 days: €{breakdown['parking']}")
```

## Cost Constants

The calculator uses these default values (configurable in the class):

```python
TrueCostCalculator.BUDGET_AIRLINES = [
    'ryanair', 'wizzair', 'easyjet', 'vueling', 'wizz air'
]

TrueCostCalculator.BAGGAGE_COST_BUDGET = 30.0  # €30 per bag
TrueCostCalculator.FUEL_COST_PER_KM = 0.08     # €0.08 per km
TrueCostCalculator.TIME_VALUE_PER_HOUR = 20.0  # €20 per hour
```

### Airport-Specific Data

Stored in the database `airports` table:

| Airport | IATA | Distance | Driving Time | Parking/Day |
|---------|------|----------|--------------|-------------|
| Munich  | MUC  | 40 km    | 45 min       | €15         |
| Memmingen | FMM | 110 km  | 140 min      | €5          |
| Nuremberg | NUE | 170 km  | 120 min      | €10         |
| Salzburg | SZG | 145 km   | 90 min       | €12         |

## API Reference

### TrueCostCalculator

#### `__init__(db_session: Session | AsyncSession)`

Initialize the calculator with a database session.

```python
calc = TrueCostCalculator(db_session)
```

#### `load_airports() -> Dict[str, Airport]`

Load and cache airport data from database (synchronous).

```python
airports = calc.load_airports()
```

#### `load_airports_async() -> Dict[str, Airport]`

Load and cache airport data from database (asynchronous).

```python
airports = await calc.load_airports_async()
```

#### `calculate_baggage_cost(airline: str, num_bags: int) -> float`

Calculate baggage fees based on airline type.

- **Budget airlines**: €30 per bag
- **Legacy carriers**: €0 (included)

```python
cost = calc.calculate_baggage_cost('Ryanair', 2)  # €60.00
cost = calc.calculate_baggage_cost('Lufthansa', 2)  # €0.00
```

#### `calculate_parking_cost(airport_iata: str, num_days: int) -> float`

Calculate parking cost for trip duration.

```python
cost = calc.calculate_parking_cost('MUC', 7)  # €105.00 (7 × €15)
```

#### `calculate_fuel_cost(airport_iata: str) -> float`

Calculate fuel cost for round-trip drive.

Formula: `distance_km × 2 × €0.08`

```python
cost = calc.calculate_fuel_cost('FMM')  # €17.60 (110km × 2 × €0.08)
```

#### `calculate_time_value(airport_iata: str) -> float`

Calculate opportunity cost of driving time.

Formula: `(driving_minutes × 2 / 60) × €20`

```python
cost = calc.calculate_time_value('FMM')  # €93.33 (140min × 2 / 60 × €20)
```

#### `calculate_total_true_cost(flight: Flight, num_bags: int = 2, num_days: int = None) -> Dict`

Calculate complete true cost breakdown.

**Parameters:**
- `flight`: Flight object from database
- `num_bags`: Number of checked bags (default: 2)
- `num_days`: Trip duration (auto-calculated from flight dates if None)

**Returns:** Dictionary with complete cost breakdown

```python
breakdown = calc.calculate_total_true_cost(flight, num_bags=2)
```

#### `calculate_for_all_flights(flights: List[Flight], num_bags: int = 2, commit: bool = True) -> List[Dict]`

Batch calculate true costs for multiple flights (synchronous).

Updates `flight.true_cost` field in database.

```python
breakdowns = calc.calculate_for_all_flights(flights, num_bags=2, commit=True)
```

#### `calculate_for_all_flights_async(flights: List[Flight], num_bags: int = 2, commit: bool = True) -> List[Dict]`

Batch calculate true costs for multiple flights (asynchronous).

```python
breakdowns = await calc.calculate_for_all_flights_async(flights, num_bags=2, commit=True)
```

#### `print_breakdown(breakdown: Dict) -> None`

Pretty print a cost breakdown for debugging/display.

```python
calc.print_breakdown(breakdown)
```

## Integration with Scrapers

### Updating Scraped Flights

After scraping new flights, automatically calculate true costs:

```python
from app.scrapers.ryanair_scraper import RyanairScraper
from app.utils.cost_calculator import TrueCostCalculator

# Scrape flights
scraper = RyanairScraper(db_session)
flights = await scraper.scrape_flights(...)

# Calculate true costs
calc = TrueCostCalculator(db_session)
await calc.load_airports_async()
await calc.calculate_for_all_flights_async(flights, commit=True)
```

### CLI Usage

Create a CLI command to update all flights:

```python
import asyncio
from app.database import get_async_session_context
from app.utils.cost_calculator import TrueCostCalculator
from app.models.flight import Flight
from sqlalchemy import select

async def update_all_true_costs():
    """Update true costs for all flights in database."""
    async with get_async_session_context() as db:
        calc = TrueCostCalculator(db)
        await calc.load_airports_async()

        # Get all flights
        result = await db.execute(select(Flight))
        flights = result.scalars().all()

        # Update
        breakdowns = await calc.calculate_for_all_flights_async(
            flights,
            num_bags=2,
            commit=True
        )

        print(f"✓ Updated {len(breakdowns)} flights")

        # Show statistics
        avg_hidden_cost = sum(b['hidden_costs'] for b in breakdowns) / len(breakdowns)
        print(f"Average hidden costs: €{avg_hidden_cost:.2f}")

if __name__ == "__main__":
    asyncio.run(update_all_true_costs())
```

## Testing

Run the test suite:

```bash
# Run all cost calculator tests
pytest tests/unit/test_cost_calculator.py -v

# Run specific test class
pytest tests/unit/test_cost_calculator.py::TestCalculateBagageCost -v

# Run with coverage
pytest tests/unit/test_cost_calculator.py --cov=app.utils.cost_calculator
```

## Database Schema

The calculator uses these database fields:

### `airports` table
- `iata_code` (str): Airport code
- `distance_from_home` (int): Distance in km from Munich
- `driving_time` (int): Driving time in minutes
- `parking_cost_per_day` (float): Daily parking cost in EUR

### `flights` table
- `total_price` (float): Base flight price for 4 people
- `airline` (str): Airline name
- `departure_date` (date): Departure date
- `return_date` (date): Return date
- `origin_airport_id` (int): Foreign key to airports
- `true_cost` (float): **Calculated true cost** (populated by calculator)

## Performance Considerations

### Caching

The calculator caches airport data after loading:

```python
calc = TrueCostCalculator(db)
calc.load_airports()  # Load once

# Use many times without additional DB queries
for flight in flights:
    breakdown = calc.calculate_total_true_cost(flight)
```

### Batch Processing

Use batch methods for better performance:

```python
# ✗ Slow: Individual commits
for flight in flights:
    breakdown = calc.calculate_total_true_cost(flight)
    flight.true_cost = breakdown['total_true_cost']
    db.commit()

# ✓ Fast: Single commit
breakdowns = calc.calculate_for_all_flights(flights, commit=True)
```

## FAQ

### Q: Why is time valued at €20/hour?

This is the opportunity cost of driving. Instead of spending 4+ hours driving to/from a distant airport, you could be working, relaxing, or doing something valuable.

### Q: Can I customize the cost constants?

Yes! Modify the class constants:

```python
calc = TrueCostCalculator(db)
calc.FUEL_COST_PER_KM = 0.10  # Increase fuel cost
calc.TIME_VALUE_PER_HOUR = 25.0  # Increase time value
```

### Q: What if I don't have checked bags?

Set `num_bags=0`:

```python
breakdown = calc.calculate_total_true_cost(flight, num_bags=0)
```

### Q: How accurate are these calculations?

The calculations use reasonable EU averages:
- **Fuel**: €0.08/km is based on average EU fuel prices and car efficiency
- **Time**: €20/hour is a conservative estimate of opportunity cost
- **Baggage**: €30/bag is typical for budget airlines in 2025
- **Parking**: Actual airport rates from official sources

### Q: Can I use this for one-way flights?

Yes, but you need to specify `num_days` since it can't be auto-calculated:

```python
breakdown = calc.calculate_total_true_cost(
    one_way_flight,
    num_bags=2,
    num_days=7  # Assume 7 days
)
```

## Troubleshooting

### Error: "Cannot call load_airports() on async session"

Use the correct method for your session type:

```python
# Sync session
calc.load_airports()

# Async session
await calc.load_airports_async()
```

### Warning: "No parking cost data for airport XXX"

The airport is missing `parking_cost_per_day` in the database. Update the airport data:

```python
airport = db.query(Airport).filter_by(iata_code='XXX').first()
airport.parking_cost_per_day = 10.0
db.commit()
```

### Missing origin_airport relationship

Ensure you're loading the relationship:

```python
from sqlalchemy.orm import joinedload

flight = db.execute(
    select(Flight)
    .options(joinedload(Flight.origin_airport))
    .where(Flight.id == 123)
).scalar_one()
```

## License

Part of SmartFamilyTravelScout project. See main project LICENSE.
