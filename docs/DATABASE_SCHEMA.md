# SmartFamilyTravelScout Database Schema

Complete database schema documentation for the SmartFamilyTravelScout application.

## Overview

The database is designed to support a family travel deal finder that:
- Tracks multiple departure airports with costs
- Scrapes flights from various sources
- Finds family-friendly accommodations
- Discovers local events and activities
- Generates AI-scored trip packages
- Maintains price history for trend analysis
- Tracks school holidays for optimal trip planning

## Technology Stack

- **Database**: PostgreSQL 14+
- **ORM**: SQLAlchemy 2.0+ with declarative mapping
- **Migrations**: Alembic
- **Async Support**: asyncpg driver for async operations
- **Connection**: psycopg2-binary for sync operations

## Tables

### 1. airports

Stores departure airport information with costs and preferences.

**Columns:**
- `id` (PK): Serial integer
- `iata_code`: 3-letter code (unique), e.g., 'MUC', 'FMM'
- `name`: Airport name
- `city`: City name
- `distance_from_home`: Distance in km from Munich
- `driving_time`: Driving time in minutes
- `preferred_for`: Array of preferences (e.g., ['budget', 'direct_flights'])
- `parking_cost_per_day`: Decimal, euros per day
- `created_at`, `updated_at`: Timestamps

**Indexes:**
- `ix_airports_iata_code` (unique)
- `ix_airports_created_at`

**Sample Data:**
```
MUC: 20km, 25min, €15/day parking
FMM: 110km, 70min, €5/day parking (budget friendly)
NUE: 170km, 110min, €10/day parking
SZG: 150km, 90min, €12/day parking
```

---

### 2. flights

Flight deals from multiple sources (Kiwi, Skyscanner, Ryanair, etc.).

**Columns:**
- `id` (PK): Serial integer
- `origin_airport_id` (FK → airports.id): Departure airport
- `destination_airport_id` (FK → airports.id): Arrival airport
- `airline`: Airline name
- `departure_date`, `departure_time`: Outbound flight
- `return_date`, `return_time`: Return flight (nullable for one-way)
- `price_per_person`: Decimal, EUR per person
- `total_price`: Decimal, EUR for 4 people
- `true_cost`: Decimal, calculated including airport costs
- `booking_class`: E.g., 'Economy', 'Premium Economy'
- `direct_flight`: Boolean
- `source`: Source website/API
- `booking_url`: Link to book
- `scraped_at`: When data was collected
- `created_at`, `updated_at`: Timestamps

**Indexes:**
- `ix_flights_origin_airport_id`
- `ix_flights_destination_airport_id`
- `ix_flights_departure_date`
- `ix_flights_return_date`
- `ix_flights_source`
- `ix_flights_scraped_at`

**Foreign Keys:**
- CASCADE delete when airport is deleted

---

### 3. accommodations

Hotels, Airbnbs, and serviced apartments.

**Columns:**
- `id` (PK): Serial integer
- `destination_city`: City name (indexed)
- `name`: Property name
- `type`: 'hotel', 'airbnb', 'apartment'
- `bedrooms`: Number of bedrooms
- `price_per_night`: Decimal, EUR per night
- `family_friendly`: Boolean
- `has_kitchen`: Boolean
- `has_kids_club`: Boolean
- `rating`: Decimal(3,1), 0-10 scale
- `review_count`: Integer
- `source`: E.g., 'booking.com', 'airbnb'
- `url`: Booking link
- `image_url`: Property image
- `scraped_at`: Collection timestamp
- `created_at`, `updated_at`: Timestamps

**Indexes:**
- `ix_accommodations_destination_city`
- `ix_accommodations_source`
- `ix_accommodations_scraped_at`

---

### 4. events

Local events and activities at destinations.

**Columns:**
- `id` (PK): Serial integer
- `destination_city`: City name (indexed)
- `title`: Event name
- `event_date`: Start date
- `end_date`: End date (nullable, for multi-day events)
- `category`: 'family', 'parent_escape', 'cultural', 'outdoor'
- `description`: Event details
- `price_range`: 'free', '<€20', '€20-50', '€50+'
- `source`: 'eventbrite', 'tripadvisor', 'manual'
- `url`: Event link
- `ai_relevance_score`: Decimal(3,1), AI-scored 0-10
- `scraped_at`: Collection timestamp
- `created_at`, `updated_at`: Timestamps

**Indexes:**
- `ix_events_destination_city`
- `ix_events_event_date`
- `ix_events_category`
- `ix_events_ai_relevance_score`
- `ix_events_scraped_at`

---

### 5. trip_packages

AI-generated complete trip suggestions combining flights, accommodation, and events.

**Columns:**
- `id` (PK): Serial integer
- `package_type`: 'family' or 'parent_escape'
- `flights_json`: JSONB, array of flight IDs or full data
- `accommodation_id` (FK → accommodations.id): Linked accommodation (nullable)
- `events_json`: JSONB, array of event IDs
- `destination_city`: Primary city
- `departure_date`, `return_date`: Trip dates
- `num_nights`: Trip duration
- `total_price`: Decimal, total EUR cost
- `ai_score`: Decimal(5,2), 0-100 score
- `ai_reasoning`: Text explanation from AI
- `itinerary_json`: JSONB, day-by-day suggested itinerary
- `notified`: Boolean, notification sent flag
- `created_at`, `updated_at`: Timestamps

**Indexes:**
- `ix_trip_packages_package_type`
- `ix_trip_packages_destination_city`
- `ix_trip_packages_departure_date`
- `ix_trip_packages_return_date`
- `ix_trip_packages_ai_score` (crucial for finding top deals)

**Foreign Keys:**
- SET NULL when accommodation is deleted

---

### 6. user_preferences

User configuration for deal finding and notifications.

**Columns:**
- `id` (PK): Serial integer
- `user_id`: Integer (for future multi-user support)
- `max_flight_price_family`: Decimal, max EUR per person
- `max_flight_price_parents`: Decimal, max EUR per person
- `max_total_budget_family`: Decimal, max total EUR
- `preferred_destinations`: Array of city names
- `avoid_destinations`: Array of city names to exclude
- `interests`: Array of interests ['wine', 'museums', etc.]
- `notification_threshold`: Decimal, min AI score for alerts
- `parent_escape_frequency`: 'monthly', 'quarterly', 'semi-annual'
- `created_at`, `updated_at`: Timestamps

**Indexes:**
- `ix_user_preferences_user_id`

**Default Values:**
```
max_flight_price_family: €200/person
max_total_budget_family: €2000
preferred_destinations: ['Lisbon', 'Barcelona', 'Prague', 'Porto']
notification_threshold: 70
```

---

### 7. school_holidays

Bavaria school holiday calendar for trip planning.

**Columns:**
- `id` (PK): Serial integer
- `name`: Holiday name, e.g., 'Easter Break 2025'
- `start_date`, `end_date`: Holiday period
- `year`: Calendar year
- `holiday_type`: 'major' or 'long_weekend'
- `region`: Default 'Bavaria'
- `created_at`, `updated_at`: Timestamps

**Indexes:**
- `ix_school_holidays_start_date`
- `ix_school_holidays_end_date`
- `ix_school_holidays_year`

**Seeded Data (2025-2026):**
- Easter Break 2025: Apr 14-25
- Whitsun Break 2025: Jun 10-20
- Summer Holiday 2025: Aug 1 - Sep 15
- Autumn Break 2025: Oct 27 - Nov 7
- Christmas Break 2025/2026: Dec 22 - Jan 10
- Winter Break 2026: Feb 16-20
- Easter Break 2026: Mar 30 - Apr 10
- Whitsun Break 2026: May 26 - Jun 5

---

### 8. price_history

Historical flight prices for trend analysis.

**Columns:**
- `id` (PK): Serial integer
- `route`: Route code, e.g., 'MUC-LIS'
- `price`: Decimal, EUR
- `source`: Data source
- `scraped_at`: Collection timestamp
- `created_at`: Record creation

**Indexes:**
- `ix_price_history_route`
- `ix_price_history_source`
- `ix_price_history_scraped_at`
- `ix_price_history_created_at`

**Usage:**
- Track price trends over time
- Detect price drops
- Calculate historical averages
- Identify good deal thresholds

---

### 9. scraping_jobs

Tracks scraping task execution and status.

**Columns:**
- `id` (PK): Serial integer
- `job_type`: 'flights', 'accommodations', 'events'
- `source`: Source name
- `status`: 'running', 'completed', 'failed'
- `items_scraped`: Count of items collected
- `error_message`: Error details (nullable)
- `started_at`: Job start time
- `completed_at`: Job end time (nullable)

**Indexes:**
- `ix_scraping_jobs_job_type`
- `ix_scraping_jobs_source`
- `ix_scraping_jobs_status`
- `ix_scraping_jobs_started_at`
- `ix_scraping_jobs_completed_at`

**Usage:**
- Monitor scraping health
- Debug failures
- Track performance metrics
- Schedule re-runs

---

## Relationships

### One-to-Many
- `Airport` → `Flight` (as origin)
- `Airport` → `Flight` (as destination)
- `Accommodation` → `TripPackage`

### Cascade Behavior
- Delete airport → CASCADE delete all related flights
- Delete accommodation → SET NULL in trip_packages

---

## JSONB Fields

### trip_packages.flights_json
```json
{
  "outbound_flight_id": 123,
  "return_flight_id": 456,
  "total_flight_cost": 800.00
}
```

### trip_packages.events_json
```json
{
  "event_ids": [10, 15, 20],
  "total_event_cost": 120.00
}
```

### trip_packages.itinerary_json
```json
{
  "day_1": {
    "date": "2025-08-01",
    "activities": ["Arrival", "Check-in", "Dinner at Time Out Market"],
    "events": [10]
  },
  "day_2": {
    "date": "2025-08-02",
    "activities": ["Visit Belém Tower", "Pastéis de Belém", "Beach afternoon"],
    "events": [15]
  }
}
```

---

## Migration Management

### Running Migrations

```bash
# Create new migration
poetry run alembic revision --autogenerate -m "description"

# Apply migrations
poetry run alembic upgrade head

# Rollback one migration
poetry run alembic downgrade -1

# View migration history
poetry run alembic history

# View current revision
poetry run alembic current
```

### Initial Setup

```bash
# Create database (if using Docker)
docker-compose up -d postgres

# Run initial migration
poetry run alembic upgrade head

# Seed data
poetry run python app/utils/seed_data.py
```

---

## Database Functions

### Helper Functions (app/database.py)

**Async:**
- `get_async_session()`: FastAPI dependency
- `get_async_session_context()`: Context manager
- `init_db()`: Create all tables (dev only)
- `drop_db()`: Drop all tables (dev only)
- `reset_db()`: Drop and recreate

**Sync:**
- `get_sync_session()`: Get session for Celery/CLI
- `init_db_sync()`: Create tables (sync)
- `drop_db_sync()`: Drop tables (sync)
- `reset_db_sync()`: Drop and recreate (sync)

**Connection:**
- `check_db_connection()`: Health check
- `close_db_connections()`: Cleanup

---

## Seed Data

Run seeding:
```bash
poetry run python app/utils/seed_data.py
```

Or programmatically:
```python
from app.database import get_sync_session
from app.utils.seed_data import seed_all

db = get_sync_session()
try:
    seed_all(db)
finally:
    db.close()
```

---

## Performance Considerations

### Indexes
All frequently queried fields are indexed:
- Foreign keys
- Date fields
- City names
- Scores
- Status fields

### Query Optimization
- Use `joinedload()` for relationships to avoid N+1 queries
- Use `select()` for async queries
- Filter early, join late
- Use database-level aggregations (COUNT, AVG, etc.)

### Connection Pooling
- Pool size: 5 connections
- Max overflow: 10 connections
- Pool recycle: 1 hour
- Pre-ping enabled for stale connections

---

## Security

### Connection
- Never commit `.env` with real credentials
- Use environment variables for all secrets
- Use SSL for production database connections
- Rotate database passwords regularly

### Queries
- SQLAlchemy protects against SQL injection
- Validate all user inputs
- Use parameterized queries
- Sanitize JSONB inputs

---

## Monitoring

### Metrics to Track
- Query execution time
- Connection pool usage
- Scraping job success rate
- Price update frequency
- AI scoring performance

### Logging
- Log all database errors
- Track slow queries (> 1s)
- Monitor migration status
- Alert on connection failures

---

## Backup and Recovery

### Backup Strategy
```bash
# Full backup
pg_dump -U travelscout travelscout > backup.sql

# Compressed backup
pg_dump -U travelscout travelscout | gzip > backup.sql.gz

# Schema only
pg_dump -U travelscout --schema-only travelscout > schema.sql
```

### Restore
```bash
# Restore from backup
psql -U travelscout travelscout < backup.sql

# From compressed
gunzip -c backup.sql.gz | psql -U travelscout travelscout
```

---

## Example Workflows

### Adding a New Flight Deal
```python
from app.database import get_sync_session
from app.models import Flight, Airport

db = get_sync_session()

# Get airports
muc = db.query(Airport).filter_by(iata_code='MUC').first()
lis = db.query(Airport).filter_by(iata_code='LIS').first()

# Create flight
flight = Flight(
    origin_airport_id=muc.id,
    destination_airport_id=lis.id,
    airline='TAP Air Portugal',
    departure_date=date(2025, 8, 1),
    return_date=date(2025, 8, 8),
    price_per_person=Decimal('180.00'),
    total_price=Decimal('720.00'),
    direct_flight=True,
    source='kiwi'
)

db.add(flight)
db.commit()
db.close()
```

### Finding Best Deals
```python
from app.models import TripPackage, UserPreference

db = get_sync_session()

prefs = db.query(UserPreference).filter_by(user_id=1).first()

packages = db.query(TripPackage).filter(
    and_(
        TripPackage.ai_score >= prefs.notification_threshold,
        TripPackage.total_price <= prefs.max_total_budget_family,
        TripPackage.notified == False
    )
).order_by(TripPackage.ai_score.desc()).limit(10).all()

for pkg in packages:
    send_notification(pkg)
    pkg.notified = True

db.commit()
db.close()
```

---

## Troubleshooting

### Common Issues

**Connection refused:**
```bash
# Check if PostgreSQL is running
docker-compose ps
# or
sudo systemctl status postgresql
```

**Migration conflicts:**
```bash
# Check current state
poetry run alembic current

# View history
poetry run alembic history

# Manual downgrade if needed
poetry run alembic downgrade <revision_id>
```

**Slow queries:**
```sql
-- Enable query logging in PostgreSQL
ALTER DATABASE travelscout SET log_min_duration_statement = 1000;

-- View slow queries
SELECT * FROM pg_stat_statements ORDER BY mean_time DESC;
```

---

## Further Reading

- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [PostgreSQL JSONB](https://www.postgresql.org/docs/current/datatype-json.html)
- [Database Query Examples](./DATABASE_QUERIES.md)
