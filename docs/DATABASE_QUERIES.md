# Database Query Examples

This document provides example queries for common operations in the SmartFamilyTravelScout database.

## Table of Contents
1. [Airport Queries](#airport-queries)
2. [Flight Queries](#flight-queries)
3. [Accommodation Queries](#accommodation-queries)
4. [Event Queries](#event-queries)
5. [Trip Package Queries](#trip-package-queries)
6. [School Holiday Queries](#school-holiday-queries)
7. [Price History Queries](#price-history-queries)
8. [Complex Queries](#complex-queries)

---

## Airport Queries

### Get all airports sorted by distance from home
```python
from sqlalchemy import select
from app.models import Airport

# Async
async with get_async_session_context() as db:
    result = await db.execute(
        select(Airport).order_by(Airport.distance_from_home)
    )
    airports = result.scalars().all()

# Sync
db = get_sync_session()
airports = db.query(Airport).order_by(Airport.distance_from_home).all()
db.close()
```

### Find budget-friendly airports
```python
from sqlalchemy import select
from app.models import Airport

# Find airports preferred for budget travel
db = get_sync_session()
airports = db.query(Airport).filter(
    Airport.preferred_for.contains(['budget'])
).all()
db.close()
```

### Calculate total trip cost including airport costs
```python
# Using the property defined in the Airport model
airport = db.query(Airport).filter_by(iata_code='FMM').first()
print(f"Total additional cost: €{airport.total_trip_cost:.2f}")
```

---

## Flight Queries

### Find all flights from MUC to Lisbon
```python
from sqlalchemy import select, and_
from app.models import Airport, Flight

db = get_sync_session()

# Get airport IDs
muc = db.query(Airport).filter_by(iata_code='MUC').first()
lis = db.query(Airport).filter_by(iata_code='LIS').first()

# Find flights
flights = db.query(Flight).filter(
    and_(
        Flight.origin_airport_id == muc.id,
        Flight.destination_airport_id == lis.id
    )
).all()

db.close()
```

### Find direct flights under €200 per person
```python
from datetime import date

db = get_sync_session()

flights = db.query(Flight).filter(
    and_(
        Flight.direct_flight == True,
        Flight.price_per_person <= 200.00,
        Flight.departure_date >= date.today()
    )
).order_by(Flight.price_per_person).all()

db.close()
```

### Find flights during school holidays
```python
from sqlalchemy import and_, or_

db = get_sync_session()

# Get Easter Break 2025
holiday = db.query(SchoolHoliday).filter_by(name='Easter Break 2025').first()

flights = db.query(Flight).filter(
    and_(
        Flight.departure_date >= holiday.start_date,
        Flight.departure_date <= holiday.end_date
    )
).all()

db.close()
```

### Get cheapest flights by route
```python
from sqlalchemy import func

db = get_sync_session()

# Group by origin and destination, get minimum price
cheapest_flights = db.query(
    Flight.origin_airport_id,
    Flight.destination_airport_id,
    func.min(Flight.price_per_person).label('min_price')
).group_by(
    Flight.origin_airport_id,
    Flight.destination_airport_id
).all()

db.close()
```

---

## Accommodation Queries

### Find family-friendly accommodations in Lisbon
```python
db = get_sync_session()

accommodations = db.query(Accommodation).filter(
    and_(
        Accommodation.destination_city == 'Lisbon',
        Accommodation.family_friendly == True,
        Accommodation.price_per_night <= 150.00
    )
).order_by(Accommodation.rating.desc()).all()

db.close()
```

### Find accommodations with kitchen
```python
db = get_sync_session()

accommodations = db.query(Accommodation).filter(
    and_(
        Accommodation.destination_city == 'Barcelona',
        Accommodation.has_kitchen == True,
        Accommodation.rating >= 8.0
    )
).all()

db.close()
```

### Get highly-rated accommodations
```python
# Using the is_highly_rated property
db = get_sync_session()

accommodations = db.query(Accommodation).filter(
    Accommodation.destination_city == 'Porto'
).all()

highly_rated = [acc for acc in accommodations if acc.is_highly_rated]
db.close()
```

---

## Event Queries

### Find family events during a specific date range
```python
from datetime import date

db = get_sync_session()

events = db.query(Event).filter(
    and_(
        Event.destination_city == 'Lisbon',
        Event.category == 'family',
        Event.event_date >= date(2025, 8, 1),
        Event.event_date <= date(2025, 8, 15)
    )
).order_by(Event.event_date).all()

db.close()
```

### Find free or cheap events
```python
db = get_sync_session()

events = db.query(Event).filter(
    and_(
        Event.destination_city == 'Barcelona',
        or_(
            Event.price_range == 'free',
            Event.price_range == '<€20'
        )
    )
).all()

db.close()
```

### Find events with high AI relevance score
```python
db = get_sync_session()

events = db.query(Event).filter(
    and_(
        Event.ai_relevance_score >= 8.0,
        Event.category == 'parent_escape'
    )
).order_by(Event.ai_relevance_score.desc()).all()

db.close()
```

---

## Trip Package Queries

### Find trip packages with AI score > 80
```python
db = get_sync_session()

packages = db.query(TripPackage).filter(
    TripPackage.ai_score >= 80.0
).order_by(TripPackage.ai_score.desc()).all()

db.close()
```

### Find family trips within budget
```python
db = get_sync_session()

packages = db.query(TripPackage).filter(
    and_(
        TripPackage.package_type == 'family',
        TripPackage.total_price <= 2000.00
    )
).all()

db.close()
```

### Find unnotified high-score packages
```python
db = get_sync_session()

packages = db.query(TripPackage).filter(
    and_(
        TripPackage.notified == False,
        TripPackage.ai_score >= 70.0
    )
).all()

# Send notifications...

# Mark as notified
for package in packages:
    package.notified = True
db.commit()
db.close()
```

### Get package with accommodation details
```python
from sqlalchemy.orm import joinedload

db = get_sync_session()

package = db.query(TripPackage).options(
    joinedload(TripPackage.accommodation)
).filter_by(id=1).first()

if package.accommodation:
    print(f"Accommodation: {package.accommodation.name}")
    print(f"Price per night: €{package.accommodation.price_per_night}")

db.close()
```

---

## School Holiday Queries

### Get all holidays for 2025
```python
db = get_sync_session()

holidays = db.query(SchoolHoliday).filter(
    SchoolHoliday.year == 2025
).order_by(SchoolHoliday.start_date).all()

db.close()
```

### Check if a date falls within a holiday
```python
from datetime import date

db = get_sync_session()

check_date = date(2025, 8, 15)

# Query
holiday = db.query(SchoolHoliday).filter(
    and_(
        SchoolHoliday.start_date <= check_date,
        SchoolHoliday.end_date >= check_date
    )
).first()

# Or using the model method
holidays = db.query(SchoolHoliday).all()
matching_holiday = next(
    (h for h in holidays if h.contains_date(check_date)),
    None
)

db.close()
```

### Get major holidays only
```python
db = get_sync_session()

major_holidays = db.query(SchoolHoliday).filter(
    SchoolHoliday.holiday_type == 'major'
).all()

# Or using the property
all_holidays = db.query(SchoolHoliday).all()
major = [h for h in all_holidays if h.is_major_holiday]

db.close()
```

---

## Price History Queries

### Get price history for a route
```python
db = get_sync_session()

history = db.query(PriceHistory).filter(
    PriceHistory.route == 'MUC-LIS'
).order_by(PriceHistory.scraped_at.desc()).all()

db.close()
```

### Calculate average price for a route
```python
from sqlalchemy import func

db = get_sync_session()

avg_price = db.query(
    func.avg(PriceHistory.price)
).filter(
    PriceHistory.route == 'MUC-BCN'
).scalar()

print(f"Average price: €{avg_price:.2f}")

db.close()
```

### Find price drops
```python
from datetime import datetime, timedelta
from sqlalchemy import func

db = get_sync_session()

# Get prices from last 7 days
week_ago = datetime.now() - timedelta(days=7)

recent_prices = db.query(
    PriceHistory.route,
    func.min(PriceHistory.price).label('current_price')
).filter(
    PriceHistory.scraped_at >= week_ago
).group_by(PriceHistory.route).all()

# Compare with historical average
for route, current_price in recent_prices:
    historical_avg = db.query(
        func.avg(PriceHistory.price)
    ).filter(
        and_(
            PriceHistory.route == route,
            PriceHistory.scraped_at < week_ago
        )
    ).scalar()

    if historical_avg and current_price < historical_avg * 0.8:  # 20% drop
        print(f"Price drop alert for {route}: €{current_price} (avg: €{historical_avg:.2f})")

db.close()
```

---

## Complex Queries

### Find complete trip packages matching user preferences
```python
from sqlalchemy.orm import joinedload

db = get_sync_session()

# Get user preferences
prefs = db.query(UserPreference).filter_by(user_id=1).first()

# Find packages matching preferences
packages = db.query(TripPackage).options(
    joinedload(TripPackage.accommodation)
).filter(
    and_(
        TripPackage.package_type == 'family',
        TripPackage.total_price <= prefs.max_total_budget_family,
        TripPackage.destination_city.in_(prefs.preferred_destinations),
        TripPackage.ai_score >= prefs.notification_threshold
    )
).order_by(TripPackage.ai_score.desc()).all()

db.close()
```

### Find best deals by combining flight and accommodation data
```python
db = get_sync_session()

# Get flights to Lisbon
lis_airport = db.query(Airport).filter_by(iata_code='LIS').first()

flights = db.query(Flight).filter(
    and_(
        Flight.destination_airport_id == lis_airport.id,
        Flight.price_per_person <= 200.00,
        Flight.departure_date >= date.today()
    )
).all()

# Get accommodations in Lisbon
accommodations = db.query(Accommodation).filter(
    and_(
        Accommodation.destination_city == 'Lisbon',
        Accommodation.family_friendly == True,
        Accommodation.price_per_night <= 100.00
    )
).all()

# Calculate total costs
deals = []
for flight in flights:
    for acc in accommodations:
        if flight.duration_days:
            total_cost = (
                flight.total_price +  # 4 people
                (acc.price_per_night * flight.duration_days)
            )
            if total_cost <= 2000:
                deals.append({
                    'flight': flight,
                    'accommodation': acc,
                    'total_cost': total_cost,
                    'departure': flight.departure_date,
                    'nights': flight.duration_days
                })

# Sort by total cost
deals.sort(key=lambda x: x['total_cost'])

db.close()
```

### Get scraping statistics
```python
from sqlalchemy import func, case

db = get_sync_session()

stats = db.query(
    ScrapingJob.job_type,
    ScrapingJob.source,
    func.count(ScrapingJob.id).label('total_jobs'),
    func.sum(
        case((ScrapingJob.status == 'completed', 1), else_=0)
    ).label('completed'),
    func.sum(
        case((ScrapingJob.status == 'failed', 1), else_=0)
    ).label('failed'),
    func.sum(ScrapingJob.items_scraped).label('total_items'),
    func.avg(
        func.extract('epoch',
            ScrapingJob.completed_at - ScrapingJob.started_at
        )
    ).label('avg_duration_seconds')
).group_by(
    ScrapingJob.job_type,
    ScrapingJob.source
).all()

for stat in stats:
    print(f"{stat.job_type} from {stat.source}:")
    print(f"  Total jobs: {stat.total_jobs}")
    print(f"  Completed: {stat.completed}")
    print(f"  Failed: {stat.failed}")
    print(f"  Items scraped: {stat.total_items}")
    if stat.avg_duration_seconds:
        print(f"  Avg duration: {stat.avg_duration_seconds:.2f}s")

db.close()
```

---

## Async Query Examples

### Async queries with FastAPI dependency
```python
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_async_session
from app.models import Flight, Airport

@app.get("/flights/{origin_code}/{dest_code}")
async def get_flights(
    origin_code: str,
    dest_code: str,
    db: AsyncSession = Depends(get_async_session)
):
    # Get airports
    origin_result = await db.execute(
        select(Airport).where(Airport.iata_code == origin_code)
    )
    origin = origin_result.scalar_one_or_none()

    dest_result = await db.execute(
        select(Airport).where(Airport.iata_code == dest_code)
    )
    dest = dest_result.scalar_one_or_none()

    if not origin or not dest:
        raise HTTPException(status_code=404, detail="Airport not found")

    # Get flights
    flights_result = await db.execute(
        select(Flight).where(
            and_(
                Flight.origin_airport_id == origin.id,
                Flight.destination_airport_id == dest.id
            )
        ).order_by(Flight.price_per_person)
    )
    flights = flights_result.scalars().all()

    return flights
```

---

## Additional Notes

### Using Relationships
```python
# Access related data through relationships
flight = db.query(Flight).first()
print(f"Origin: {flight.origin_airport.name}")
print(f"Destination: {flight.destination_airport.name}")
print(f"Route: {flight.route}")  # Uses @property

# Eager loading to avoid N+1 queries
from sqlalchemy.orm import joinedload

flights = db.query(Flight).options(
    joinedload(Flight.origin_airport),
    joinedload(Flight.destination_airport)
).all()
```

### Working with JSONB fields
```python
# Query JSONB fields
from sqlalchemy.dialects.postgresql import JSONB

# Find packages with specific flight ID in flights_json
packages = db.query(TripPackage).filter(
    TripPackage.flights_json.contains([{'flight_id': 123}])
).all()

# Access JSONB data
package = db.query(TripPackage).first()
flight_ids = package.flights_json.get('flight_ids', [])
```

### Transaction Management
```python
# Sync
db = get_sync_session()
try:
    # Multiple operations
    flight = Flight(...)
    db.add(flight)

    accommodation = Accommodation(...)
    db.add(accommodation)

    # Commit all or nothing
    db.commit()
except Exception as e:
    db.rollback()
    raise
finally:
    db.close()

# Async
async with get_async_session_context() as db:
    # Operations here
    # Auto-commits on success, auto-rolls back on error
    pass
```
