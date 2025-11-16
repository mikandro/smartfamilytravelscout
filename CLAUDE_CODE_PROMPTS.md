# Claude Code Prompts - SmartFamilyTravelScout

This document contains **copy-paste ready prompts** for delegating tasks to Claude Code instances.

**Execution Strategy**:
- ✅ **Green sections** = Can run in parallel
- 🔴 **Red sections** = Must run sequentially
- Each prompt is self-contained and can be copied to a separate Claude Code session

---

## 🔴 PHASE 1: FOUNDATION (Sequential - Run in Order)

### Task 1.1: Project Setup & Infrastructure

**Dependencies**: None
**Estimated Time**: 2 hours
**Can Parallelize**: ❌ No (foundation)

**PROMPT:**
```
Create a production-ready Python project structure for "SmartFamilyTravelScout" - an AI-powered family travel deal finder.

PROJECT REQUIREMENTS:
- Python 3.11+
- Use Poetry for dependency management
- Docker Compose setup with: PostgreSQL 15, Redis, Python app

CORE DEPENDENCIES:
- fastapi (web framework)
- sqlalchemy (ORM)
- alembic (migrations)
- celery (task queue)
- redis (caching)
- playwright (web scraping)
- anthropic (Claude API)
- pandas (data analysis)
- requests (HTTP)
- beautifulsoup4 (HTML parsing)
- python-dotenv (environment)
- pydantic (data validation)
- click or typer (CLI)
- jinja2 (templating)
- rich (pretty CLI output)

FOLDER STRUCTURE:
```
smartfamilytravelscout/
├── app/
│   ├── __init__.py
│   ├── api/              # FastAPI routes
│   │   ├── __init__.py
│   │   └── routes/
│   ├── scrapers/         # All web scrapers
│   │   ├── __init__.py
│   │   ├── base_scraper.py
│   │   ├── kiwi_scraper.py
│   │   ├── skyscanner_scraper.py
│   │   ├── ryanair_scraper.py
│   │   ├── wizzair_scraper.py
│   │   ├── booking_scraper.py
│   │   ├── airbnb_scraper.py
│   │   ├── eventbrite_scraper.py
│   │   └── tourism_scraper.py
│   ├── ai/               # Claude integration
│   │   ├── __init__.py
│   │   ├── claude_client.py
│   │   ├── deal_scorer.py
│   │   ├── itinerary_generator.py
│   │   ├── parent_escape_analyzer.py
│   │   ├── event_scorer.py
│   │   └── prompts/
│   ├── models/           # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── airport.py
│   │   ├── flight.py
│   │   ├── accommodation.py
│   │   ├── event.py
│   │   ├── trip_package.py
│   │   └── user_preference.py
│   ├── orchestration/    # Workflow orchestrators
│   │   ├── __init__.py
│   │   ├── flight_orchestrator.py
│   │   ├── accommodation_matcher.py
│   │   ├── event_matcher.py
│   │   └── main_orchestrator.py
│   ├── services/         # Business logic
│   │   ├── __init__.py
│   │   ├── school_calendar.py
│   │   └── price_tracker.py
│   ├── notifications/    # Email/push notifications
│   │   ├── __init__.py
│   │   └── email_sender.py
│   ├── tasks/            # Celery tasks
│   │   ├── __init__.py
│   │   ├── celery_app.py
│   │   └── scheduled_tasks.py
│   ├── utils/            # Helper functions
│   │   ├── __init__.py
│   │   ├── date_utils.py
│   │   ├── geo_utils.py
│   │   ├── price_utils.py
│   │   ├── cost_calculator.py
│   │   └── retry.py
│   ├── cli/              # Command-line interface
│   │   ├── __init__.py
│   │   └── main.py
│   ├── config.py         # Configuration management
│   └── database.py       # Database connection
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── docs/
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── .gitignore
├── pyproject.toml
├── README.md
└── alembic.ini
```

DELIVERABLES:

1. **pyproject.toml** with all dependencies
2. **docker-compose.yml** with:
   - PostgreSQL 15 (port 5432)
   - Redis (port 6379)
   - Python app container
   - Proper networking and volumes
3. **Dockerfile** for Python app (multi-stage build preferred)
4. **.env.example** with:
   ```
   DATABASE_URL=postgresql://user:password@localhost:5432/travelscout
   REDIS_URL=redis://localhost:6379/0
   ANTHROPIC_API_KEY=your_key_here
   KIWI_API_KEY=your_key_here
   EVENTBRITE_API_KEY=your_key_here
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your_email@gmail.com
   SMTP_PASSWORD=your_password
   ```
5. **app/config.py** - Load environment variables with pydantic BaseSettings
6. **app/database.py** - SQLAlchemy engine and session management
7. **app/__init__.py** - App initialization with logging setup
8. **README.md** with:
   - Project overview
   - Setup instructions (Docker Compose)
   - Running the app
   - Environment variables
9. **.gitignore** for Python, Docker, IDE files
10. **alembic.ini** for database migrations
11. Create all empty __init__.py files for proper package structure

REQUIREMENTS:
- Proper logging configuration (use Python's logging module, JSON format)
- Environment variable validation (fail fast if missing required vars)
- Database connection pooling (SQLAlchemy with pool_size=5)
- Health check endpoint (FastAPI route at /health)
- Use async/await where applicable (FastAPI, database operations)

VERIFICATION STEPS:
1. Run `docker-compose up` - should start without errors
2. Database should be accessible on localhost:5432
3. Redis should be accessible on localhost:6379
4. App should have basic logging output
5. Project structure should match the layout above

Create all these files with proper content, not just placeholders. Include example configurations and best practices.
```

**Expected Output**: Complete project structure ready for development

---

### Task 1.2: Database Schema Implementation

**Dependencies**: Task 1.1
**Estimated Time**: 3 hours
**Can Parallelize**: ❌ No (needed by all data tasks)

**PROMPT:**
```
Implement the complete database schema for SmartFamilyTravelScout using SQLAlchemy and Alembic.

CONTEXT:
This is a family travel deal finder. We need to store flights from multiple sources, accommodations, events, and AI-generated trip packages.

TABLES TO CREATE:

1. **airports**
   - id (PK, serial)
   - iata_code (VARCHAR(3), unique, e.g., 'MUC')
   - name (VARCHAR(100), e.g., 'Munich Airport')
   - city (VARCHAR(50))
   - distance_from_home (INT, km from Munich home)
   - driving_time (INT, minutes)
   - preferred_for (ARRAY[VARCHAR], e.g., ['budget', 'direct_flights'])
   - parking_cost_per_day (DECIMAL, euros)
   - created_at, updated_at

2. **flights**
   - id (PK, serial)
   - origin_airport_id (FK → airports.id)
   - destination_airport_id (FK → airports.id)
   - airline (VARCHAR(50))
   - departure_date (DATE)
   - departure_time (TIME)
   - return_date (DATE)
   - return_time (TIME)
   - price_per_person (DECIMAL)
   - total_price (DECIMAL, for 4 people)
   - booking_class (VARCHAR(20))
   - direct_flight (BOOLEAN)
   - source (VARCHAR(50), e.g., 'kiwi', 'skyscanner', 'ryanair')
   - booking_url (TEXT)
   - true_cost (DECIMAL, nullable, calculated later)
   - scraped_at (TIMESTAMP)
   - created_at, updated_at

3. **accommodations**
   - id (PK, serial)
   - destination_city (VARCHAR(100))
   - name (VARCHAR(200))
   - type (VARCHAR(50), e.g., 'hotel', 'airbnb', 'apartment')
   - bedrooms (INT)
   - price_per_night (DECIMAL)
   - family_friendly (BOOLEAN)
   - has_kitchen (BOOLEAN)
   - has_kids_club (BOOLEAN)
   - rating (DECIMAL, 0-10)
   - review_count (INT)
   - source (VARCHAR(50))
   - url (TEXT)
   - image_url (TEXT)
   - scraped_at (TIMESTAMP)
   - created_at, updated_at

4. **events**
   - id (PK, serial)
   - destination_city (VARCHAR(100))
   - title (VARCHAR(200))
   - event_date (DATE)
   - end_date (DATE, nullable)
   - category (VARCHAR(50), e.g., 'family', 'parent_escape', 'cultural')
   - description (TEXT)
   - price_range (VARCHAR(50), e.g., 'free', '<€20', '€20-50')
   - source (VARCHAR(50))
   - url (TEXT)
   - ai_relevance_score (DECIMAL, nullable, 0-10)
   - scraped_at (TIMESTAMP)
   - created_at, updated_at

5. **trip_packages**
   - id (PK, serial)
   - package_type (VARCHAR(50), 'family' or 'parent_escape')
   - flights_json (JSONB, array of flight IDs)
   - accommodation_id (FK → accommodations.id, nullable)
   - events_json (JSONB, array of event IDs, nullable)
   - total_price (DECIMAL)
   - destination_city (VARCHAR(100))
   - departure_date (DATE)
   - return_date (DATE)
   - num_nights (INT)
   - ai_score (DECIMAL, nullable, 0-100)
   - ai_reasoning (TEXT, nullable)
   - itinerary_json (JSONB, nullable)
   - notified (BOOLEAN, default FALSE)
   - created_at, updated_at

6. **user_preferences**
   - id (PK, serial)
   - user_id (INT, for future multi-user support)
   - max_flight_price_family (DECIMAL, per person)
   - max_flight_price_parents (DECIMAL, per person)
   - max_total_budget_family (DECIMAL)
   - preferred_destinations (ARRAY[VARCHAR])
   - avoid_destinations (ARRAY[VARCHAR])
   - interests (ARRAY[VARCHAR], e.g., ['wine', 'museums', 'beaches'])
   - notification_threshold (DECIMAL, minimum AI score for alerts)
   - parent_escape_frequency (VARCHAR, e.g., 'monthly', 'quarterly')
   - created_at, updated_at

7. **school_holidays**
   - id (PK, serial)
   - name (VARCHAR(100), e.g., 'Easter Break 2025')
   - start_date (DATE)
   - end_date (DATE)
   - year (INT)
   - holiday_type (VARCHAR(50), 'major' or 'long_weekend')
   - region (VARCHAR(50), default 'Bavaria')

8. **price_history**
   - id (PK, serial)
   - route (VARCHAR(10), e.g., 'MUC-LIS')
   - price (DECIMAL)
   - source (VARCHAR(50))
   - scraped_at (TIMESTAMP)
   - created_at

9. **scraping_jobs**
   - id (PK, serial)
   - job_type (VARCHAR(50), e.g., 'flights', 'accommodations')
   - source (VARCHAR(50))
   - status (VARCHAR(20), 'running', 'completed', 'failed')
   - items_scraped (INT)
   - error_message (TEXT, nullable)
   - started_at (TIMESTAMP)
   - completed_at (TIMESTAMP, nullable)

DELIVERABLES:

1. **SQLAlchemy Models** (in app/models/):
   - Create separate file for each model
   - Use proper relationships (ForeignKey, relationship())
   - Add __repr__ methods
   - Add indexes on frequently queried fields (origin_airport_id, destination_city, departure_date, ai_score)

2. **Alembic Migration** (initial schema):
   - Run `alembic init alembic` if not already done
   - Create initial migration with all tables
   - Include indexes in migration

3. **Seed Data Script** (app/utils/seed_data.py):
   - Insert 4 airports:
     * MUC (Munich): distance=20km, driving_time=25min, parking=€15/day
     * FMM (Memmingen): distance=110km, driving_time=70min, parking=€5/day
     * NUE (Nuremberg): distance=170km, driving_time=110min, parking=€10/day
     * SZG (Salzburg): distance=150km, driving_time=90min, parking=€12/day

   - Insert Bavaria school holidays 2025-2026:
     * Easter Break 2025: April 14-25
     * Whitsun Break 2025: June 10-20
     * Summer Holiday 2025: August 1 - September 15
     * Autumn Break 2025: October 27 - November 7
     * Christmas Break 2025: December 22 - January 10, 2026
     * Winter Break 2026: February 16-20
     * Easter Break 2026: March 30 - April 10
     * Whitsun Break 2026: May 26 - June 5

   - Insert default user preferences:
     * max_flight_price_family: €200/person
     * max_total_budget_family: €2000
     * preferred_destinations: ['Lisbon', 'Barcelona', 'Prague', 'Porto']
     * notification_threshold: 70

4. **Database Helper Functions** (app/database.py):
   - get_db() session dependency for FastAPI
   - init_db() to create all tables
   - reset_db() to drop and recreate (for testing)

5. **Example Queries** (in comments or separate file):
   - Find all flights from MUC to Lisbon
   - Get trip packages with score > 80
   - Find events during specific date range

REQUIREMENTS:
- Use proper SQLAlchemy best practices (declarative base, mixins for timestamps)
- Add created_at/updated_at automatically (use events or mixins)
- Proper foreign key constraints with ON DELETE CASCADE where appropriate
- Indexes on: flight origin/destination, trip_packages.ai_score, events.event_date
- JSONB columns for flexible data (flights_json, events_json, itinerary_json)

VERIFICATION STEPS:
1. Run alembic migration successfully
2. Seed data script populates airports and holidays
3. Can query all tables
4. Foreign key relationships work correctly
5. All indexes are created

Implement this completely with production-ready code, not placeholders.
```

**Expected Output**: Complete database schema with migrations and seed data

---

### Task 1.3: Core Utilities & Helpers

**Dependencies**: Task 1.1
**Estimated Time**: 2 hours
**Can Parallelize**: ❌ No (used by all modules)

**PROMPT:**
```
Create core utility functions for SmartFamilyTravelScout that will be used across all modules.

UTILITIES TO BUILD:

1. **Date Utils** (app/utils/date_utils.py):
   ```python
   def is_school_holiday(date: datetime.date, holidays: List[Holiday]) -> bool:
       """Check if date falls within school holidays"""

   def get_upcoming_holidays(months: int = 3) -> List[Holiday]:
       """Get school holidays in next N months"""

   def get_date_ranges_for_holidays(holidays: List[Holiday]) -> List[Tuple[date, date]]:
       """Convert holidays to (start, end) date ranges for searching"""

   def find_long_weekends(year: int) -> List[Tuple[date, date]]:
       """Find 3-4 day weekends (Fri-Mon with public holiday)"""

   def calculate_nights(departure: date, return_date: date) -> int:
       """Calculate number of nights"""

   def date_range(start: date, end: date) -> Iterator[date]:
       """Generate all dates between start and end"""
   ```

2. **Geo Utils** (app/utils/geo_utils.py):
   ```python
   def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
       """Calculate distance in km using Haversine formula"""

   def estimate_driving_time(distance_km: float) -> int:
       """Estimate driving time in minutes (assume 100km/h avg)"""

   def get_city_coordinates(city_name: str) -> Tuple[float, float]:
       """Get lat/lon for city (use hardcoded dict for main cities)"""
   ```

3. **Price Utils** (app/utils/price_utils.py):
   ```python
   def normalize_currency(price: str) -> float:
       """Convert various price formats to float (€123.45, $150, 100EUR)"""

   def calculate_per_person(total: float, num_people: int = 4) -> float:
       """Calculate per-person price"""

   def format_price(price: float, currency: str = '€') -> str:
       """Format price nicely (€1,234.56)"""

   def price_within_range(price: float, min_price: float, max_price: float) -> bool:
       """Check if price is within range"""
   ```

4. **Retry Decorator** (app/utils/retry.py):
   ```python
   def retry_with_backoff(max_attempts: int = 3, backoff_seconds: int = 2):
       """Decorator for retrying functions with exponential backoff"""
       # Retry on network errors, timeouts
       # Exponential backoff: 2s, 4s, 8s, etc.
   ```

5. **Logging Setup** (app/utils/logging_config.py):
   ```python
   def setup_logging(level: str = "INFO"):
       """Configure structured logging (JSON format for production)"""
       # Log to console and file
       # Include: timestamp, level, message, module, function
   ```

6. **String Utils** (app/utils/string_utils.py):
   ```python
   def clean_text(text: str) -> str:
       """Remove extra whitespace, normalize"""

   def extract_numbers(text: str) -> List[float]:
       """Extract all numbers from text"""

   def normalize_city_name(city: str) -> str:
       """Normalize city names (Lisboa → Lisbon, Wien → Vienna)"""
   ```

REQUIREMENTS:
- Full implementations, not stubs
- Comprehensive docstrings with examples
- Type hints for all functions
- Handle edge cases (None values, empty strings, etc.)
- Add unit tests for each utility module in tests/unit/

HARDCODED DATA TO INCLUDE:
- City coordinates (at least 30 European cities)
- City name mappings (local → English names)
- Public holidays Bavaria 2025-2026

VERIFICATION:
- All functions have passing unit tests
- Test edge cases (None, empty, invalid input)
- No external API calls (use hardcoded data)

Create complete, production-ready implementations.
```

**Expected Output**: Comprehensive utility library with tests

---

## ✅ PHASE 2: DATA COLLECTION (Fully Parallel - Run All 8 Simultaneously)

**⚡ All tasks below can run in parallel in separate Claude Code sessions**

### Task 2.1: Kiwi.com Flight Scraper

**Dependencies**: Tasks 1.2, 1.3
**Estimated Time**: 4 hours
**Can Parallelize**: ✅ YES

**PROMPT:**
```
Build a Kiwi.com API integration for flight searching.

CONTEXT:
Kiwi.com (formerly Skypicker) has a free Search API with 100 calls/month. We're building a family travel deal finder that searches flights from 4 German airports (MUC, FMM, NUE, SZG) to European destinations.

API DOCUMENTATION:
- Base URL: https://api.tequila.kiwi.com
- Endpoint: /v2/search
- Free tier: 100 requests/month
- Register at: https://tequila.kiwi.com/portal/login

FEATURES TO IMPLEMENT:

1. **KiwiClient Class** (app/scrapers/kiwi_scraper.py):
   ```python
   class KiwiClient:
       def __init__(self, api_key: str):
           """Initialize with API key from environment"""

       async def search_flights(
           self,
           origin: str,  # IATA code
           destination: str,  # IATA code or city
           departure_date: date,
           return_date: date,
           adults: int = 2,
           children: int = 2
       ) -> List[Dict]:
           """Search for flights, return standardized flight offers"""

       async def search_anywhere(
           self,
           origin: str,
           departure_date: date,
           return_date: date
       ) -> List[Dict]:
           """Search all destinations from origin (destination=None)"""

       def parse_response(self, raw_data: dict) -> List[Dict]:
           """Parse Kiwi API response to standardized FlightOffer format"""

       async def save_to_database(self, flights: List[Dict]):
           """Save flights to database"""
   ```

2. **Standardized FlightOffer Format**:
   ```python
   {
       'origin_airport': 'MUC',
       'destination_airport': 'LIS',
       'origin_city': 'Munich',
       'destination_city': 'Lisbon',
       'airline': 'Ryanair',
       'departure_date': '2025-12-20',
       'departure_time': '14:30',
       'return_date': '2025-12-27',
       'return_time': '18:45',
       'price_per_person': 89.99,
       'total_price': 359.96,  # for 4 people
       'direct_flight': True,
       'booking_class': 'Economy',
       'source': 'kiwi',
       'booking_url': 'https://...',
       'scraped_at': '2025-11-15T10:30:00'
   }
   ```

3. **Rate Limiting**:
   - Track API calls (store in Redis or local file)
   - Limit to 100 calls/month (~3 per day)
   - Raise error if quota exceeded
   - Log each API call with timestamp

4. **Error Handling**:
   - Retry on network errors (max 3 attempts, exponential backoff)
   - Handle API errors gracefully (log and continue)
   - Validate responses before parsing
   - Handle "no flights found" (return empty list)

5. **Database Integration**:
   - Check for duplicate flights before inserting
   - Duplicate = same route, airline, date (±2 hours)
   - Update price if cheaper version found
   - Store in `flights` table with `source='kiwi'`

DELIVERABLES:
- app/scrapers/kiwi_scraper.py with complete implementation
- Rate limiting logic (use Redis counter or simple file-based)
- Comprehensive error handling and logging
- Unit tests (tests/unit/test_kiwi_scraper.py) with mocked API responses
- Example usage script or CLI command to test

REQUIREMENTS:
- Use async/await (aiohttp for HTTP requests)
- Proper logging (log all API calls, errors, successes)
- Type hints throughout
- Docstrings with examples
- Handle edge cases (missing data, invalid responses)

VERIFICATION:
1. Can search MUC → LIS for specific dates
2. Can search "anywhere" from MUC
3. Parses responses correctly to FlightOffer format
4. Saves to database without duplicates
5. Rate limiting works (test by making 4 calls, should warn)
6. Unit tests pass with mocked responses

EXAMPLE USAGE:
```python
client = KiwiClient(api_key=os.getenv('KIWI_API_KEY'))
flights = await client.search_flights('MUC', 'LIS', date(2025, 12, 20), date(2025, 12, 27))
await client.save_to_database(flights)
print(f"Found {len(flights)} flights")
```

Implement completely with production-ready code.
```

**Expected Output**: Working Kiwi.com integration with database storage

---

### Task 2.2: Skyscanner Web Scraper

**Dependencies**: Tasks 1.2, 1.3
**Estimated Time**: 5 hours
**Can Parallelize**: ✅ YES

**PROMPT:**
```
Build a Skyscanner web scraper using Playwright (no API key needed).

CONTEXT:
Skyscanner's API is paid, so we'll scrape their website. We need to be respectful: use delays, rotate user agents, handle errors gracefully.

TARGET: https://www.skyscanner.com/transport/flights/{origin}/{destination}/{departure}/{return}/

SCRAPER REQUIREMENTS:

1. **SkyscannerScraper Class** (app/scrapers/skyscanner_scraper.py):
   ```python
   class SkyscannerScraper:
       def __init__(self):
           """Initialize Playwright browser"""

       async def scrape_route(
           self,
           origin: str,
           destination: str,
           departure_date: date,
           return_date: date
       ) -> List[Dict]:
           """Scrape flights for specific route"""

       async def parse_flight_cards(self, page) -> List[Dict]:
           """Extract flight data from loaded page"""

       def handle_cookie_consent(self, page):
           """Click cookie consent if present"""

       async def save_to_database(self, flights: List[Dict]):
           """Save to database"""
   ```

2. **Scraping Strategy**:
   - Use Playwright in headless mode
   - Navigate to Skyscanner URL
   - Wait for results to load (check for flight cards)
   - Extract: airline, times, price, stops
   - Handle "no results" gracefully
   - Screenshot on errors for debugging

3. **Respectful Scraping**:
   - Random delays between requests (3-7 seconds)
   - Rotate user agents (list of 5+ real browser UAs)
   - Limit to 10 searches per hour
   - Respect robots.txt (Skyscanner allows /transport/flights/)
   - Add delays even within same page (scroll simulation)

4. **Data Extraction**:
   CSS selectors to extract (inspect Skyscanner page):
   - Flight cards: `[data-testid="flight-card"]` or similar
   - Airline: `.airline-name` or extract from logo
   - Price: `[data-testid="price"]` or `.price`
   - Times: departure/arrival times
   - Stops: direct vs 1-2 stops
   - Booking URL: extract link

5. **Error Handling**:
   - Timeout after 30 seconds
   - Retry on network errors (max 2 attempts)
   - Save screenshot on parsing errors
   - Log all failures with details
   - Handle CAPTCHA detection (abort if detected, log warning)

DELIVERABLES:
- app/scrapers/skyscanner_scraper.py
- Playwright browser management (context, page lifecycle)
- CSS selectors with fallbacks (multiple selector strategies)
- User agent rotation logic
- Screenshot saving on errors (save to logs/ directory)
- Unit tests with mocked Playwright page
- Integration test with real page (mark as @pytest.mark.slow)

CHALLENGES TO HANDLE:
- Skyscanner uses JavaScript rendering (Playwright handles this)
- Layout changes (use multiple selector strategies)
- Cookie consent popups (auto-click accept)
- Loading spinners (wait for them to disappear)
- "No results" page (detect and return empty list)

VERIFICATION:
1. Successfully scrapes MUC → LIS flights
2. Extracts at least 5-10 flight options
3. Outputs standardized FlightOffer format
4. Saves to database with source='skyscanner'
5. Handles errors gracefully
6. Respects rate limits

EXAMPLE USAGE:
```python
scraper = SkyscannerScraper()
flights = await scraper.scrape_route('MUC', 'LIS', date(2025, 12, 20), date(2025, 12, 27))
await scraper.save_to_database(flights)
```

IMPORTANT: Scraping can break if Skyscanner changes their HTML. Include fallback selectors and good error messages.

Implement fully with production-ready error handling.
```

**Expected Output**: Working Skyscanner scraper with robust error handling

---

### Task 2.3: Ryanair Direct Scraper

**Dependencies**: Tasks 1.2, 1.3
**Estimated Time**: 5 hours
**Can Parallelize**: ✅ YES

**PROMPT:**
```
Build a Ryanair web scraper using Playwright.

CONTEXT:
Ryanair is a major budget airline flying from MUC and FMM. They don't provide an API, so we scrape their website. Ryanair is strict about scraping, so we must be very respectful.

TARGET: https://www.ryanair.com/

FEATURES TO IMPLEMENT:

1. **RyanairScraper Class** (app/scrapers/ryanair_scraper.py):
   ```python
   class RyanairScraper:
       def __init__(self):
           """Initialize Playwright with specific headers"""

       async def scrape_route(
           self,
           origin: str,
           destination: str,
           departure_date: date,
           return_date: date
       ) -> List[Dict]:
           """Scrape Ryanair flights"""

       async def navigate_search(self, page, origin, dest, out_date, return_date):
           """Fill search form and submit"""

       async def parse_fare_calendar(self, page) -> List[Dict]:
           """Extract prices from fare calendar (cheaper than direct dates)"""

       async def handle_popups(self, page):
           """Close cookie consent, marketing popups"""
   ```

2. **Scraping Flow**:
   ```
   1. Go to ryanair.com
   2. Handle cookie consent (click accept all)
   3. Fill in search form:
      - Origin airport (type and select from dropdown)
      - Destination airport
      - Dates (outbound, return)
      - Passengers (2 adults, 2 children)
   4. Submit search
   5. Wait for results to load
   6. Extract flight cards or fare calendar
   7. Parse prices, times, flight numbers
   ```

3. **Respectful Scraping (Critical for Ryanair)**:
   - Very conservative delays (5-10 seconds between actions)
   - Realistic user behavior (hover, scroll, wait)
   - Limit to 5 searches per day (they track aggressively)
   - Use residential-like headers
   - Don't scrape during peak hours (use 2-6am local time)

4. **Data Extraction**:
   Key elements to extract:
   - Flight price (look for cheapest fare)
   - Departure/arrival times
   - Flight number
   - Direct flight indicator
   - Booking URL (construct from search params)

5. **Special Handling**:
   - Ryanair shows fare calendar (month view) - scrape this for best prices
   - Multiple fare types (Regular, Flexi) - get cheapest
   - Extra fees shown separately (bags, seats) - note but don't include in base price
   - Currency conversion if shown in non-EUR

DELIVERABLES:
- app/scrapers/ryanair_scraper.py
- Popup handler (cookie consent, chat widgets, ads)
- Form filling logic (realistic typing simulation)
- Fare calendar parser
- Rate limiting (max 5/day, stored in Redis or file)
- Error screenshots saved to logs/ryanair/
- Tests with mocked pages

CHALLENGES:
- Ryanair actively blocks scrapers (use stealth mode)
- Frequent layout changes
- Many popups and interruptions
- Fare calendar vs direct date search (calendar is better for price discovery)

STEALTH MODE:
Use playwright-stealth or manual techniques:
- navigator.webdriver = false
- Realistic viewport size (1920x1080)
- Real user agent strings
- Human-like mouse movements
- Random typing delays

VERIFICATION:
1. Can search FMM → Barcelona
2. Extracts prices from fare calendar
3. Handles all popups correctly
4. Doesn't trigger CAPTCHA (test multiple times)
5. Saves to database with source='ryanair'

EXAMPLE OUTPUT:
```python
scraper = RyanairScraper()
flights = await scraper.scrape_route('FMM', 'BCN', date(2025, 12, 20), date(2025, 12, 27))
# Should return 1-3 flight options (outbound + return combinations)
```

IMPORTANT: If you detect CAPTCHA or blocking, abort gracefully and log warning. Don't retry aggressively.

Implement with maximum stealth and respect for their terms.
```

**Expected Output**: Ryanair scraper that avoids detection

---

### Task 2.4: WizzAir Scraper

**Dependencies**: Tasks 1.2, 1.3
**Estimated Time**: 4 hours
**Can Parallelize**: ✅ YES

**PROMPT:**
```
Build a WizzAir flight scraper using their unofficial API.

CONTEXT:
WizzAir is a budget airline with good routes to Eastern Europe (especially Moldova - Chisinau). They don't have an official API, but their website uses JSON endpoints we can call directly.

STRATEGY:
Inspect WizzAir's network requests (browser DevTools) and replicate their API calls. This is more reliable than HTML scraping.

API ENDPOINT (discovered via network tab):
```
POST https://be.wizzair.com/*/Api/search/search
Headers:
  Content-Type: application/json
Payload:
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

IMPLEMENTATION:

1. **WizzAirScraper Class** (app/scrapers/wizzair_scraper.py):
   ```python
   class WizzAirScraper:
       BASE_URL = "https://be.wizzair.com/*/Api/search/search"

       def __init__(self):
           """Initialize HTTP client with headers"""

       async def search_flights(
           self,
           origin: str,
           destination: str,
           departure_date: date,
           return_date: date
       ) -> List[Dict]:
           """Search via API endpoint"""

       def build_payload(self, origin, dest, out_date, ret_date) -> dict:
           """Build API request payload"""

       def parse_api_response(self, response_data: dict) -> List[Dict]:
           """Parse JSON response to FlightOffer format"""
   ```

2. **Headers to Include**:
   ```python
   headers = {
       'User-Agent': 'Mozilla/5.0 ...',
       'Content-Type': 'application/json',
       'Accept': 'application/json',
       'Origin': 'https://wizzair.com',
       'Referer': 'https://wizzair.com/'
   }
   ```

3. **Response Parsing**:
   WizzAir API returns:
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

   Extract:
   - Outbound flight + return flight combinations
   - Total price (sum both directions)
   - Times from ISO timestamps
   - Direct flight (WizzAir mostly operates direct flights)

4. **Error Handling**:
   - API might return 429 (rate limit) - respect it, wait 1 minute
   - Handle "no flights" (empty array in response)
   - Validate JSON structure
   - Log all API calls

DELIVERABLES:
- app/scrapers/wizzair_scraper.py
- Async HTTP client (aiohttp)
- JSON request/response handling
- Conversion to standardized FlightOffer format
- Database saving with source='wizzair'
- Unit tests with mocked API responses

ADVANTAGES OF THIS APPROACH:
✅ Faster than browser scraping
✅ More reliable (JSON doesn't change as much as HTML)
✅ Less likely to be blocked
✅ No JavaScript rendering needed

VERIFICATION:
1. Successfully calls WizzAir API
2. Parses response correctly
3. Finds flights MUC → Chisinau (Moldova)
4. Saves to database
5. Handles errors gracefully

EXAMPLE USAGE:
```python
scraper = WizzAirScraper()
flights = await scraper.search_flights('MUC', 'CHI', date(2025, 12, 20), date(2025, 12, 27))
```

NOTE: If the API endpoint changes, we may need to inspect network traffic again. Include clear instructions for future updates.

Implement with clean async code and good error messages.
```

**Expected Output**: WizzAir API-based scraper

---

### Task 2.5: Booking.com Scraper

**Dependencies**: Tasks 1.2, 1.3
**Estimated Time**: 5 hours
**Can Parallelize**: ✅ YES

**PROMPT:**
```
Build a Booking.com scraper for family-friendly accommodations using Playwright.

CONTEXT:
We need hotels/apartments for families (2 adults, 2 kids ages 3&6) with 2+ bedrooms, preferably with kitchens. Booking.com has the largest inventory.

TARGET URL PATTERN:
```
https://www.booking.com/searchresults.html
?ss={city}
&checkin={YYYY-MM-DD}
&checkout={YYYY-MM-DD}
&group_adults=2
&group_children=2
&age=3
&age=6
&no_rooms=1
```

SCRAPER FEATURES:

1. **BookingClient Class** (app/scrapers/booking_scraper.py):
   ```python
   class BookingClient:
       def __init__(self):
           """Initialize Playwright browser"""

       async def search(
           self,
           city: str,
           check_in: date,
           check_out: date,
           adults: int = 2,
           children_ages: List[int] = [3, 6]
       ) -> List[Dict]:
           """Search for family accommodations"""

       async def parse_property_cards(self, page) -> List[Dict]:
           """Extract property data from search results"""

       def filter_family_friendly(self, properties: List[Dict]) -> List[Dict]:
           """Keep only properties suitable for families"""

       def extract_amenities(self, property_card) -> Dict[str, bool]:
           """Extract: kitchen, kids_club, family_rooms, etc."""
   ```

2. **Scraping Flow**:
   ```
   1. Navigate to Booking.com search URL
   2. Handle cookie consent
   3. Wait for property cards to load
   4. Scroll to load more results (lazy loading)
   5. Extract top 20 properties
   6. For each property:
      - Name, price per night
      - Number of bedrooms
      - Amenities (kitchen, family facilities)
      - Rating and review count
      - URL and image
   ```

3. **Family Filters**:
   Look for properties with:
   - 2+ bedrooms OR "family room"
   - Price < €150/night
   - Keywords: "apartment", "family", "kitchen"
   - Good ratings (>7.5)
   - Available for selected dates

4. **Data Extraction**:
   Key selectors (inspect Booking.com):
   - Property cards: `[data-testid="property-card"]`
   - Name: `.property-name`
   - Price: `[data-testid="price-and-discounted-price"]`
   - Rating: `.review-score-badge`
   - Amenities: Listed in property card or need to click "Show more"

5. **Standardized Output** (Accommodation format):
   ```python
   {
       'destination_city': 'Lisbon',
       'name': 'Family Apartment Central',
       'type': 'apartment',  # or 'hotel'
       'bedrooms': 2,
       'price_per_night': 80.00,
       'family_friendly': True,
       'has_kitchen': True,
       'has_kids_club': False,
       'rating': 8.5,
       'review_count': 234,
       'source': 'booking',
       'url': 'https://booking.com/...',
       'image_url': 'https://...',
       'scraped_at': '2025-11-15T10:00:00'
   }
   ```

6. **Respectful Scraping**:
   - Delays: 4-8 seconds between requests
   - Scroll simulation (realistic behavior)
   - Limit to 1 search per minute
   - User agent rotation
   - Don't overload (max 20 properties per search)

DELIVERABLES:
- app/scrapers/booking_scraper.py
- Playwright browser management
- Property card parser
- Amenity extraction logic
- Family filtering function
- Database saving (accommodations table)
- Screenshots on errors
- Unit tests with mocked pages

CHALLENGES:
- Booking.com uses heavy JavaScript (Playwright handles)
- Lazy loading (scroll to trigger)
- Prices vary by date (scrape what's shown)
- Currency conversion (normalize to EUR)
- Sold out properties (skip them)

VERIFICATION:
1. Searches Lisbon for 7 nights
2. Finds 10-20 properties
3. Correctly identifies apartments vs hotels
4. Extracts amenities (kitchen, bedrooms)
5. Saves to database with source='booking'
6. Filters out non-family options

EXAMPLE USAGE:
```python
client = BookingClient()
properties = await client.search('Lisbon', date(2025, 12, 20), date(2025, 12, 27))
family_friendly = client.filter_family_friendly(properties)
await client.save_to_database(family_friendly)
```

Implement with robust selectors and good fallback strategies.
```

**Expected Output**: Booking.com scraper with family filters

---

### Task 2.6: Airbnb Scraper

**Dependencies**: Tasks 1.2, 1.3
**Estimated Time**: 5 hours
**Can Parallelize**: ✅ YES

**PROMPT:**
```
Build Airbnb data collection using Apify (preferred) or Playwright scraping.

CONTEXT:
Airbnb is great for family apartments with kitchens. Apify has a pre-built Airbnb scraper with a generous free tier (5,000 results/month).

RECOMMENDED APPROACH: Apify Actor

1. **Setup**:
   - Register at apify.com (free account)
   - Get API token
   - Use Airbnb Scraper actor: https://apify.com/dtrungtin/airbnb-scraper

2. **AirbnbClient Class** (app/scrapers/airbnb_scraper.py):
   ```python
   class AirbnbClient:
       def __init__(self, apify_api_key: str):
           """Initialize Apify client"""

       async def search(
           self,
           city: str,
           check_in: date,
           check_out: date,
           adults: int = 2,
           children: int = 2
       ) -> List[Dict]:
           """Search Airbnb via Apify actor"""

       def build_apify_input(self, city, checkin, checkout) -> dict:
           """Build input for Apify actor"""

       def parse_apify_results(self, results: List[dict]) -> List[Dict]:
           """Convert Apify output to our Accommodation format"""

       def filter_family_suitable(self, listings: List[Dict]) -> List[Dict]:
           """Filter for family criteria"""
   ```

3. **Apify Actor Input**:
   ```json
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

4. **Apify Response Parsing**:
   Apify returns JSON with:
   - listing name, URL
   - price per night
   - bedrooms, beds, bathrooms
   - amenities array
   - rating, review count
   - host info
   - images

   Convert to our standardized Accommodation format.

5. **Family Filters**:
   - Type: "Entire place" only
   - Bedrooms >= 2
   - Has kitchen (check amenities array)
   - Family-friendly: check if "suitable for children" in amenities or description
   - Price < €150/night

ALTERNATIVE: Direct Scraping (if Apify doesn't work)

If Apify is unavailable, implement Playwright scraping:
```python
async def scrape_airbnb_direct(
    self,
    city: str,
    check_in: date,
    check_out: date
) -> List[Dict]:
    """Fallback: direct scraping with Playwright"""
    # Navigate to Airbnb search URL
    # Extract listing cards
    # Handle infinite scroll
    # Parse prices, amenities
```

DELIVERABLES:
- app/scrapers/airbnb_scraper.py
- Apify integration (primary method)
- Playwright fallback (optional)
- Amenity parsing logic
- Family filtering
- Database saving (accommodations table, type='airbnb')
- Unit tests with mocked Apify responses
- Cost tracking (log Apify credits used)

APIFY FREE TIER:
- 5,000 results/month
- $5 free credit
- Enough for ~100 searches (50 listings each)

VERIFICATION:
1. Apify actor runs successfully
2. Returns 10-20 Airbnb listings for Lisbon
3. Correctly filters for family criteria (2+ bedrooms, kitchen)
4. Saves to database with type='airbnb'
5. Tracks Apify credits used

EXAMPLE USAGE:
```python
client = AirbnbClient(apify_api_key=os.getenv('APIFY_API_KEY'))
listings = await client.search('Barcelona', date(2025, 12, 20), date(2025, 12, 27))
family_listings = client.filter_family_suitable(listings)
await client.save_to_database(family_listings)
```

BONUS: If time permits, implement caching to avoid re-scraping same dates.

Implement with Apify as primary, Playwright as documented fallback.
```

**Expected Output**: Airbnb integration via Apify or scraping

---

### Task 2.7: EventBrite Scraper

**Dependencies**: Tasks 1.2, 1.3
**Estimated Time**: 3 hours
**Can Parallelize**: ✅ YES

**PROMPT:**
```
Build EventBrite API integration for discovering local events.

CONTEXT:
EventBrite has a free API (1,000 requests/day) that lets us search events by location and date. We want family-friendly events and parent-escape cultural events.

API DOCUMENTATION:
- Docs: https://www.eventbrite.com/platform/api
- Register: https://www.eventbrite.com/platform/api-keys
- Endpoint: https://www.eventbriteapi.com/v3/events/search/

IMPLEMENTATION:

1. **EventBriteClient Class** (app/scrapers/eventbrite_scraper.py):
   ```python
   class EventBriteClient:
       def __init__(self, api_key: str):
           """Initialize with EventBrite private token"""

       async def search_events(
           self,
           city: str,
           start_date: date,
           end_date: date,
           categories: List[str] = None
       ) -> List[Dict]:
           """Search events in city during date range"""

       def categorize_event(self, event: dict) -> str:
           """Categorize as: family | parent_escape | cultural | sports"""

       def parse_event(self, event_data: dict) -> Dict:
           """Convert EventBrite event to our Event format"""
   ```

2. **API Request**:
   ```
   GET /v3/events/search/
   ?location.address={city}
   &start_date.range_start={ISO_date}
   &start_date.range_end={ISO_date}
   &categories={category_ids}
   &expand=venue,category
   ```

3. **Event Categories** (EventBrite IDs):
   - Family: 103 (Family & Education), 115 (Kids & Family)
   - Food & Drink: 110
   - Music: 103
   - Arts: 105
   - Nightlife: 118

   Search with multiple category IDs for comprehensive results.

4. **Standardized Event Format**:
   ```python
   {
       'destination_city': 'Lisbon',
       'title': 'Family Christmas Market',
       'event_date': '2025-12-20',
       'end_date': '2025-12-24',  # nullable
       'category': 'family',  # our categorization
       'description': 'Traditional Christmas market...',
       'price_range': 'free',  # or '<€20', '€20-50', '€50+'
       'source': 'eventbrite',
       'url': 'https://eventbrite.com/e/...',
       'ai_relevance_score': None,  # filled later by AI
       'scraped_at': '2025-11-15T10:00:00'
   }
   ```

5. **Categorization Logic**:
   ```python
   def categorize_event(self, event: dict) -> str:
       title = event['name']['text'].lower()
       desc = event['description']['text'].lower() if event.get('description') else ''

       # Family event indicators
       if any(word in title + desc for word in ['kids', 'children', 'family', 'toddler']):
           return 'family'

       # Parent escape indicators
       if any(word in title + desc for word in ['wine', 'cocktail', 'adults only', 'nightlife']):
           return 'parent_escape'

       # Cultural
       if any(word in title + desc for word in ['museum', 'art', 'exhibition', 'theatre']):
           return 'cultural'

       # Sports
       if any(word in title + desc for word in ['sport', 'match', 'game', 'race']):
           return 'sports'

       return 'cultural'  # default
   ```

6. **Price Range Extraction**:
   - EventBrite provides ticket prices
   - If all tickets free → 'free'
   - If cheapest <€20 → '<€20'
   - If €20-50 → '€20-50'
   - If >€50 → '€50+'

DELIVERABLES:
- app/scrapers/eventbrite_scraper.py
- EventBrite API client
- Event categorization logic
- Price range parser
- Database saving (events table)
- Rate limiting (track calls, warn at 900/day)
- Unit tests with mocked API responses

VERIFICATION:
1. Searches events in Prague for December
2. Finds 20+ events
3. Correctly categorizes events
4. Extracts price ranges
5. Saves to database with source='eventbrite'
6. Handles pagination (if >50 results)

EXAMPLE USAGE:
```python
client = EventBriteClient(api_key=os.getenv('EVENTBRITE_API_KEY'))
events = await client.search_events('Prague', date(2025, 12, 15), date(2025, 12, 25))
# Returns events with basic categorization (AI will refine later)
await client.save_to_database(events)
```

BONUS: Search in radius around city center (EventBrite supports lat/lon + radius).

Implement with clean async code and good categorization heuristics.
```

**Expected Output**: EventBrite API integration with categorization

---

### Task 2.8: Tourism Board Scrapers (OPTIONAL - Lower Priority)

**Dependencies**: Tasks 1.2, 1.3
**Estimated Time**: 4 hours
**Can Parallelize**: ✅ YES

**PROMPT:**
```
Build web scrapers for official tourism board websites to find local events not on EventBrite.

CONTEXT:
Many cities have official tourism websites with festivals, family events, and cultural happenings that aren't on EventBrite. These are often free or unique.

TARGET SITES (Pick 3-5):
1. Lisbon: visitlisboa.com
2. Barcelona: barcelonaturisme.com
3. Prague: prague.eu/en/whats-on
4. Porto: visitporto.travel/events
5. Vienna: wien.info/en/events

IMPLEMENTATION:

1. **TourismScraper Base Class** (app/scrapers/tourism_scraper.py):
   ```python
   class BaseTourismScraper:
       """Base class for tourism board scrapers"""

       async def scrape_events(self, start_date: date, end_date: date) -> List[Dict]:
           """To be implemented by subclasses"""
           raise NotImplementedError

       def parse_event_card(self, card_element) -> Dict:
           """Common parsing logic"""

   class LisbonTourismScraper(BaseTourismScraper):
       BASE_URL = "https://www.visitlisboa.com"

       async def scrape_events(self, start_date, end_date) -> List[Dict]:
           """Scrape Lisbon events"""

   class PragueTourismScraper(BaseTourismScraper):
       BASE_URL = "https://www.prague.eu/en/whats-on"

       async def scrape_events(self, start_date, end_date) -> List[Dict]:
           """Scrape Prague events"""
   ```

2. **Generic Scraping Strategy**:
   - Navigate to events calendar page
   - Filter by date range if possible
   - Extract event cards
   - Parse: title, date, description, location, URL
   - Handle pagination
   - Save to database

3. **Common Patterns**:
   Most tourism sites have:
   - Events calendar/list view
   - Filters for date, category
   - Event cards with: image, title, date, description
   - Detail pages with full info

4. **Parsing Logic**:
   - Extract dates (various formats: "Dec 20, 2025", "20.12.2025", etc.)
   - Categorize based on keywords (same logic as EventBrite)
   - Most events are free or very cheap
   - Images and links

5. **Output Format**:
   Same as EventBrite (Event standardized format).

DELIVERABLES:
- app/scrapers/tourism_scraper.py with base class
- 3-5 city-specific scrapers
- Date parsing helpers (handle multiple formats)
- Database saving (events table, source='tourism_{city}')
- Basic tests

CHALLENGES:
- Each site has different HTML structure
- Multiple languages (EN, local language)
- Different date formats
- Some sites use JavaScript (Playwright needed)

VERIFICATION:
1. Scrapes events from 3+ cities
2. Parses dates correctly
3. Finds events not on EventBrite
4. Saves to database

EXAMPLE USAGE:
```python
lisbon = LisbonTourismScraper()
events = await lisbon.scrape_events(date(2025, 12, 15), date(2025, 12, 25))
```

NOTE: This is lower priority - implement if time allows. Focus on 2-3 cities initially.

Implement basic scrapers with room for expansion.
```

**Expected Output**: Tourism board scrapers for major cities

---

**✅ END OF PHASE 2 - All 8 tasks above can run in parallel**

---

## PHASE 3: DATA PROCESSING ⚙️

### ⚡ Execution: Mixed (Some sequential, some parallel)

---

### Task 3.1: Flight Orchestrator & Deduplication

**Dependencies**: Tasks 2.1, 2.2, 2.3, 2.4
**Estimated Time**: 4 hours
**Can Parallelize**: ❌ No (needs all flight scrapers)

**PROMPT:**
```
Create a FlightOrchestrator that coordinates all flight data sources and deduplicates results.

CONTEXT:
We have 4 flight scrapers (Kiwi, Skyscanner, Ryanair, WizzAir) that may return the same flight. We need to run them all, deduplicate, and save unique flights.

FEATURES TO IMPLEMENT:

1. **FlightOrchestrator Class** (app/orchestration/flight_orchestrator.py):
   ```python
   class FlightOrchestrator:
       def __init__(self):
           """Initialize all scrapers"""
           self.kiwi = KiwiClient()
           self.skyscanner = SkyscannerScraper()
           self.ryanair = RyanairScraper()
           self.wizzair = WizzAirScraper()

       async def scrape_all(
           self,
           origins: List[str],  # ['MUC', 'FMM', 'NUE', 'SZG']
           destinations: List[str],  # ['LIS', 'BCN', 'PRG', ...]
           date_ranges: List[Tuple[date, date]]  # School holiday periods
       ) -> List[Dict]:
           """Run all scrapers in parallel, deduplicate, return flights"""

       async def scrape_source(
           self,
           scraper,
           origin: str,
           destination: str,
           dates: Tuple[date, date]
       ) -> List[Dict]:
           """Scrape single source with error handling"""

       def deduplicate(self, flights: List[Dict]) -> List[Dict]:
           """Remove duplicate flights across sources"""

       async def save_to_database(self, flights: List[Dict]):
           """Batch save flights to database"""
   ```

2. **Parallel Execution Strategy**:
   ```python
   async def scrape_all(self, origins, destinations, date_ranges):
       tasks = []

       for origin in origins:
           for destination in destinations:
               for start, end in date_ranges:
                   # Create task for each scraper
                   tasks.append(self.scrape_source(self.kiwi, origin, destination, (start, end)))
                   tasks.append(self.scrape_source(self.skyscanner, origin, destination, (start, end)))
                   tasks.append(self.scrape_source(self.ryanair, origin, destination, (start, end)))
                   tasks.append(self.scrape_source(self.wizzair, origin, destination, (start, end)))

       # Run all tasks concurrently
       results = await asyncio.gather(*tasks, return_exceptions=True)

       # Filter out errors, flatten results
       all_flights = []
       for result in results:
           if isinstance(result, Exception):
               logger.error(f"Scraper failed: {result}")
               continue
           all_flights.extend(result)

       # Deduplicate
       unique_flights = self.deduplicate(all_flights)
       return unique_flights
   ```

3. **Deduplication Logic**:
   Flights are considered duplicates if:
   - Same origin + destination
   - Same airline
   - Departure date/time within 2 hours
   - Return date/time within 2 hours

   When duplicate found:
   - Keep the one with lowest price
   - Merge booking_url fields (keep all sources for user choice)

   ```python
   def deduplicate(self, flights: List[Dict]) -> List[Dict]:
       # Group by route + airline + approximate time
       grouped = defaultdict(list)

       for flight in flights:
           key = (
               flight['origin_airport'],
               flight['destination_airport'],
               flight['airline'],
               flight['departure_date'],
               # Round departure_time to 2-hour blocks
           )
           grouped[key].append(flight)

       # Keep cheapest from each group, merge URLs
       unique = []
       for group in grouped.values():
           best = min(group, key=lambda f: f['total_price'])
           best['booking_urls'] = [f['booking_url'] for f in group]
           best['sources'] = [f['source'] for f in group]
           unique.append(best)

       return unique
   ```

4. **Error Handling**:
   - If scraper fails, log error but continue with others
   - Track scraping stats (successful/failed per source)
   - Return partial results if some scrapers fail
   - Comprehensive logging

5. **Database Integration**:
   - Batch insert flights (use SQLAlchemy bulk operations)
   - Update existing flights if price changed
   - Track in scraping_jobs table (status, counts, errors)

DELIVERABLES:
- app/orchestration/flight_orchestrator.py
- Async orchestration with asyncio.gather()
- Deduplication algorithm
- Error handling for individual scraper failures
- Database batch operations
- Progress logging with Rich
- Unit tests with mocked scrapers

VERIFICATION:
1. Runs all 4 scrapers in parallel
2. Handles scraper failures gracefully
3. Deduplicates correctly (same flight from multiple sources)
4. Saves ~150-200 unique flights for 4 origins × 10 destinations
5. Logs scraping stats (time, count per source)

EXAMPLE USAGE:
```python
orchestrator = FlightOrchestrator()
flights = await orchestrator.scrape_all(
    origins=['MUC', 'FMM'],
    destinations=['LIS', 'BCN', 'PRG'],
    date_ranges=[(date(2025, 12, 20), date(2025, 12, 27))]
)
print(f"Found {len(flights)} unique flights")
```

Implement with robust async error handling and good logging.
```

**Expected Output**: Flight orchestrator that runs all scrapers and deduplicates

---

### Task 3.2: True Cost Calculator

**Dependencies**: Task 1.2 (airports table)
**Estimated Time**: 3 hours
**Can Parallelize**: ✅ YES (can run parallel with 3.1)

**PROMPT:**
```
Create a TrueCostCalculator that computes the real cost of flying from each airport.

CONTEXT:
A €100 flight from FMM might cost more than €150 from MUC when you factor in: 110km drive, €35 parking for 7 days, €17 fuel. We need to calculate total true cost.

COST COMPONENTS:

1. **Base Price**: From flight scraper
2. **Baggage**: Budget airlines charge extra
   - Budget airlines (Ryanair, WizzAir): €30/bag
   - Legacy carriers (Lufthansa, TAP): €0 (included)
   - Assume 2 checked bags for family of 4
3. **Parking**: Airport-dependent, per day
   - MUC: €15/day
   - FMM: €5/day
   - NUE: €10/day
   - SZG: €12/day
4. **Fuel**: Drive to airport
   - €0.08/km (EU average)
   - Distance from Munich home (in airports table)
   - Round trip (×2)
5. **Time Value**: Opportunity cost of driving
   - €20/hour
   - Driving time (from airports table)
   - Round trip (×2)

IMPLEMENTATION:

1. **TrueCostCalculator Class** (app/utils/cost_calculator.py):
   ```python
   class TrueCostCalculator:
       BUDGET_AIRLINES = ['ryanair', 'wizzair', 'easyjet']
       BAGGAGE_COST_BUDGET = 30.0
       FUEL_COST_PER_KM = 0.08
       TIME_VALUE_PER_HOUR = 20.0

       def __init__(self, db_session):
           """Load airport data from database"""
           self.airports = self.load_airports(db_session)

       def calculate_total_true_cost(
           self,
           flight: Dict,
           num_bags: int = 2,
           num_days: int = None
       ) -> Dict:
           """Calculate complete true cost breakdown"""

       def calculate_baggage_cost(self, airline: str, num_bags: int) -> float:
           """Calculate baggage fees"""

       def calculate_parking_cost(self, airport_iata: str, num_days: int) -> float:
           """Calculate parking cost"""

       def calculate_fuel_cost(self, airport_iata: str) -> float:
           """Calculate fuel cost for round trip drive"""

       def calculate_time_value(self, airport_iata: str) -> float:
           """Calculate time cost for driving"""
   ```

2. **True Cost Breakdown**:
   Return detailed breakdown:
   ```python
   {
       'base_price': 400.00,  # 4 people
       'baggage': 60.00,      # 2 bags × €30
       'parking': 35.00,      # 7 days × €5/day
       'fuel': 17.60,         # 110km × €0.08 × 2
       'time_value': 46.67,   # 140min × €20/hour / 60 × 2
       'total_true_cost': 559.27,
       'hidden_costs': 159.27,  # Everything except base price
       'cost_per_person': 139.82
   }
   ```

3. **Database Integration**:
   - Load airport data on initialization (distance, driving_time, parking_cost)
   - Cache airport data (don't query repeatedly)
   - Update flights table with `true_cost` field

4. **Batch Processing**:
   ```python
   async def calculate_for_all_flights(self, flights: List[Flight]):
       """Batch calculate true costs for all flights"""
       for flight in flights:
           breakdown = self.calculate_total_true_cost(flight)
           flight.true_cost = breakdown['total_true_cost']
           flight.true_cost_breakdown_json = breakdown
       # Commit to database
   ```

DELIVERABLES:
- app/utils/cost_calculator.py
- Complete cost calculation logic
- Database integration (update flights table)
- Batch processing support
- Unit tests with sample flights
- Documentation with examples

VERIFICATION:
1. Correctly identifies budget airlines
2. Calculates all cost components
3. FMM flight shows higher true cost than MUC (due to distance)
4. Breakdown sums correctly
5. Updates database with true_cost

EXAMPLE USAGE:
```python
calculator = TrueCostCalculator(db_session)
flight = {
    'origin_airport': 'FMM',
    'airline': 'Ryanair',
    'total_price': 400.00,
    'departure_date': '2025-12-20',
    'return_date': '2025-12-27'
}
breakdown = calculator.calculate_total_true_cost(flight, num_bags=2)
print(f"True cost: €{breakdown['total_true_cost']:.2f}")
print(f"Hidden costs: €{breakdown['hidden_costs']:.2f}")
```

Implement with clear cost breakdown and good documentation.
```

**Expected Output**: True cost calculator with detailed breakdowns

---

### Task 3.3: Accommodation Matcher

**Dependencies**: Tasks 2.5, 2.6, 3.1
**Estimated Time**: 3 hours
**Can Parallelize**: ❌ No (needs flights from 3.1)

**PROMPT:**
```
Create an AccommodationMatcher that pairs flights with accommodations to generate complete trip packages.

CONTEXT:
We have flights and accommodations separately. Now we need to match them by destination and dates, calculate total trip cost, and create TripPackage objects.

FEATURES TO IMPLEMENT:

1. **AccommodationMatcher Class** (app/orchestration/accommodation_matcher.py):
   ```python
   class AccommodationMatcher:
       def __init__(self, db_session):
           self.db = db_session

       async def generate_trip_packages(
           self,
           max_budget: float = 2000.0,
           min_nights: int = 3,
           max_nights: int = 10
       ) -> List[TripPackage]:
           """Generate all valid trip package combinations"""

       def match_flights_to_accommodations(
           self,
           destination: str
       ) -> List[Tuple[Flight, Accommodation]]:
           """Find all flight + accommodation pairs for destination"""

       def calculate_trip_cost(
           self,
           flight: Flight,
           accommodation: Accommodation,
           num_nights: int
       ) -> Dict:
           """Calculate total trip cost"""

       def create_trip_package(
           self,
           flight: Flight,
           accommodation: Accommodation,
           cost_breakdown: Dict
       ) -> TripPackage:
           """Create TripPackage database object"""
   ```

2. **Matching Logic**:
   ```python
   async def generate_trip_packages(self, max_budget, min_nights, max_nights):
       packages = []

       # Get all unique destinations with flights
       destinations = self.db.query(Flight.destination_city).distinct().all()

       for (dest_city,) in destinations:
           # Get flights to this destination
           flights = self.db.query(Flight).filter(
               Flight.destination_city == dest_city,
               Flight.true_cost.isnot(None)  # Only flights with calculated costs
           ).all()

           # Get accommodations in this city
           accommodations = self.db.query(Accommodation).filter(
               Accommodation.destination_city == dest_city
           ).all()

           # Create all combinations
           for flight in flights:
               num_nights = (flight.return_date - flight.departure_date).days

               # Skip if outside night range
               if not (min_nights <= num_nights <= max_nights):
                   continue

               for accommodation in accommodations:
                   cost = self.calculate_trip_cost(flight, accommodation, num_nights)

                   # Skip if over budget
                   if cost['total'] > max_budget:
                       continue

                   # Create package
                   package = self.create_trip_package(flight, accommodation, cost)
                   packages.append(package)

       return packages
   ```

3. **Cost Calculation**:
   ```python
   def calculate_trip_cost(self, flight, accommodation, num_nights):
       # Flight true cost already includes all flight-related expenses
       flight_cost = flight.true_cost  # For 4 people

       # Accommodation
       accommodation_cost = accommodation.price_per_night * num_nights

       # Food estimate (€100/day for family of 4)
       food_cost = 100.0 * num_nights

       # Optional: Activities budget (€50/day)
       activities_cost = 50.0 * num_nights

       total = flight_cost + accommodation_cost + food_cost + activities_cost

       return {
           'flight_cost': flight_cost,
           'accommodation_cost': accommodation_cost,
           'food_cost': food_cost,
           'activities_cost': activities_cost,
           'total': total,
           'per_person': total / 4.0
       }
   ```

4. **TripPackage Creation**:
   ```python
   def create_trip_package(self, flight, accommodation, cost_breakdown):
       package = TripPackage(
           package_type='family',
           flights_json=[flight.id],  # Store flight IDs
           accommodation_id=accommodation.id,
           events_json=[],  # Will be filled by EventMatcher later
           total_price=cost_breakdown['total'],
           price_breakdown_json=cost_breakdown,
           destination_city=flight.destination_city,
           departure_date=flight.departure_date,
           return_date=flight.return_date,
           num_nights=(flight.return_date - flight.departure_date).days,
           notified=False
       )
       return package
   ```

5. **School Holiday Filtering**:
   ```python
   def filter_by_school_holidays(self, packages: List[TripPackage]) -> List[TripPackage]:
       """Keep only packages during school holidays"""
       school_holidays = self.db.query(SchoolHoliday).all()

       filtered = []
       for package in packages:
           if is_during_holiday(package.departure_date, school_holidays):
               filtered.append(package)

       return filtered
   ```

DELIVERABLES:
- app/orchestration/accommodation_matcher.py
- Matching logic for flights + accommodations
- Cost calculation with breakdown
- TripPackage creation
- School holiday filtering
- Batch database insertion
- Unit tests

VERIFICATION:
1. Generates 50+ trip packages for various destinations
2. All packages within budget (< €2000)
3. Cost breakdowns sum correctly
4. Only includes trips during school holidays
5. Saves packages to database

EXAMPLE USAGE:
```python
matcher = AccommodationMatcher(db_session)
packages = await matcher.generate_trip_packages(max_budget=2000.0)
print(f"Generated {len(packages)} trip packages")

# Filter for specific destination
lisbon_packages = [p for p in packages if p.destination_city == 'Lisbon']
print(f"Lisbon packages: {len(lisbon_packages)}")
```

Implement with efficient database queries and good filtering logic.
```

**Expected Output**: Trip package generator matching flights and accommodations

---

### Task 3.4: Event Matcher

**Dependencies**: Tasks 2.7, 2.8, 3.1
**Estimated Time**: 2 hours
**Can Parallelize**: ✅ YES (parallel with 3.3)

**PROMPT:**
```
Create an EventMatcher that associates events with trip packages.

CONTEXT:
We have events from EventBrite and tourism boards. We need to find which events happen during each trip and add them to the trip package.

FEATURES TO IMPLEMENT:

1. **EventMatcher Class** (app/orchestration/event_matcher.py):
   ```python
   class EventMatcher:
       def __init__(self, db_session):
           self.db = db_session

       async def match_events_to_packages(
           self,
           packages: List[TripPackage]
       ) -> List[TripPackage]:
           """Add matching events to each package"""

       def find_events_for_trip(
           self,
           destination: str,
           start_date: date,
           end_date: date
       ) -> List[Event]:
           """Find events during trip dates"""

       def filter_by_age_appropriateness(
           self,
           events: List[Event],
           kids_ages: List[int] = [3, 6]
       ) -> List[Event]:
           """Filter events suitable for young children"""

       def categorize_for_package_type(
           self,
           events: List[Event],
           package_type: str  # 'family' or 'parent_escape'
       ) -> List[Event]:
           """Keep only relevant events for package type"""
   ```

2. **Matching Logic**:
   ```python
   async def match_events_to_packages(self, packages):
       for package in packages:
           # Find events in destination during trip dates
           events = self.find_events_for_trip(
               package.destination_city,
               package.departure_date,
               package.return_date
           )

           # Filter by package type
           if package.package_type == 'family':
               events = self.filter_by_age_appropriateness(events)
               events = [e for e in events if e.category in ['family', 'cultural']]
           else:  # parent_escape
               events = [e for e in events if e.category in ['parent_escape', 'cultural']]

           # Store event IDs in package
           package.events_json = [e.id for e in events]

       return packages
   ```

3. **Age Appropriateness Filter**:
   ```python
   def filter_by_age_appropriateness(self, events, kids_ages=[3, 6]):
       appropriate = []

       for event in events:
           title_lower = event.title.lower()
           desc_lower = event.description.lower() if event.description else ''

           # Exclude adult-only events
           if any(word in title_lower + desc_lower for word in ['18+', 'adults only', 'nightclub']):
               continue

           # For young kids (3-6), prefer specific types
           if any(word in title_lower + desc_lower for word in ['kids', 'children', 'family', 'playground']):
               appropriate.append(event)
           elif event.category in ['family', 'cultural']:
               appropriate.append(event)

       return appropriate
   ```

4. **Event Scoring Enhancement** (optional):
   ```python
   def rank_events_by_relevance(self, events: List[Event], package: TripPackage) -> List[Event]:
       """Sort events by relevance to trip"""
       # Events with high AI scores first
       # Events on weekends (if trip includes weekend)
       # Free events ranked higher for budget-conscious
       scored = sorted(events, key=lambda e: e.ai_relevance_score or 5, reverse=True)
       return scored[:10]  # Top 10 events
   ```

DELIVERABLES:
- app/orchestration/event_matcher.py
- Event-to-package matching logic
- Age appropriateness filtering
- Category-based filtering (family vs parent escape)
- Database updates (events_json field)
- Unit tests

VERIFICATION:
1. Matches 2-5 events to 80% of trip packages
2. Correctly filters age-inappropriate events
3. Family packages get family events
4. Parent escape packages get adult events
5. Updates packages in database

EXAMPLE USAGE:
```python
matcher = EventMatcher(db_session)
packages = db_session.query(TripPackage).all()
packages_with_events = await matcher.match_events_to_packages(packages)

for package in packages_with_events[:5]:
    print(f"{package.destination_city}: {len(package.events_json)} events")
```

Implement with clear filtering logic and good categorization.
```

**Expected Output**: Event matcher that enriches trip packages

---

## PHASE 4: AI ENGINE 🤖

### 🔴 Execution: Sequential start → Parallel

---

### Task 4.1: Claude API Integration

**Dependencies**: Task 1.1
**Estimated Time**: 2 hours
**Can Parallelize**: ❌ No (foundation for AI tasks)

**PROMPT:**
```
Integrate the Claude API for AI-powered analysis using the official Anthropic SDK.

CONTEXT:
We'll use Claude to score deals, generate itineraries, and make recommendations. Need robust integration with caching, cost tracking, and error handling.

IMPLEMENTATION:

1. **ClaudeClient Class** (app/ai/claude_client.py):
   ```python
   from anthropic import Anthropic
   import json
   import hashlib

   class ClaudeClient:
       def __init__(self, api_key: str, redis_client):
           self.client = Anthropic(api_key=api_key)
           self.redis = redis_client
           self.model = "claude-sonnet-4-5-20250929"
           self.cache_ttl = 86400  # 24 hours

       async def analyze(
           self,
           prompt: str,
           data: Dict,
           response_format: str = 'json',
           use_cache: bool = True
       ) -> Dict:
           """Send prompt to Claude, return parsed response"""

       def _build_cache_key(self, prompt: str, data: Dict) -> str:
           """Generate cache key from prompt + data"""

       def _get_cached_response(self, cache_key: str) -> Optional[Dict]:
           """Check Redis cache"""

       def _cache_response(self, cache_key: str, response: Dict):
           """Store response in Redis"""

       def parse_json_response(self, response_text: str) -> Dict:
           """Extract JSON from Claude's response"""

       def track_cost(self, input_tokens: int, output_tokens: int) -> float:
           """Calculate and log API cost"""
   ```

2. **Cache Strategy**:
   ```python
   async def analyze(self, prompt, data, response_format='json', use_cache=True):
       # Generate cache key
       cache_key = self._build_cache_key(prompt, data)

       # Check cache
       if use_cache:
           cached = self._get_cached_response(cache_key)
           if cached:
               logger.info("Using cached Claude response")
               return cached

       # Call Claude API
       full_prompt = prompt.format(**data)

       message = self.client.messages.create(
           model=self.model,
           max_tokens=2048,
           messages=[{
               "role": "user",
               "content": full_prompt
           }]
       )

       # Parse response
       response_text = message.content[0].text
       if response_format == 'json':
           result = self.parse_json_response(response_text)
       else:
           result = {'text': response_text}

       # Track cost
       cost = self.track_cost(message.usage.input_tokens, message.usage.output_tokens)
       result['_cost'] = cost

       # Cache
       if use_cache:
           self._cache_response(cache_key, result)

       return result
   ```

3. **Cost Tracking**:
   ```python
   def track_cost(self, input_tokens, output_tokens):
       # Claude Sonnet 4.5 pricing (as of 2025)
       input_cost = (input_tokens / 1_000_000) * 3.0  # $3/1M input tokens
       output_cost = (output_tokens / 1_000_000) * 15.0  # $15/1M output tokens
       total_cost = input_cost + output_cost

       # Log to database
       self.db.add(ApiCost(
           service='claude',
           input_tokens=input_tokens,
           output_tokens=output_tokens,
           cost_usd=total_cost,
           timestamp=datetime.now()
       ))

       logger.info(f"Claude API cost: ${total_cost:.4f} ({input_tokens + output_tokens} tokens)")
       return total_cost
   ```

4. **JSON Parsing**:
   ```python
   def parse_json_response(self, response_text):
       """Extract JSON from Claude's response (handles markdown code blocks)"""
       # Claude often wraps JSON in markdown: ```json ... ```
       if '```json' in response_text:
           start = response_text.find('```json') + 7
           end = response_text.rfind('```')
           json_str = response_text[start:end].strip()
       elif '```' in response_text:
           start = response_text.find('```') + 3
           end = response_text.rfind('```')
           json_str = response_text[start:end].strip()
       else:
           json_str = response_text.strip()

       try:
           return json.loads(json_str)
       except json.JSONDecodeError as e:
           logger.error(f"Failed to parse JSON: {e}")
           logger.error(f"Response: {response_text}")
           raise
   ```

5. **Prompt Template Management** (app/ai/prompts/):
   Store prompts as text files:
   - `deal_analysis.txt`
   - `itinerary_generation.txt`
   - `parent_escape_analysis.txt`
   - `event_scoring.txt`

DELIVERABLES:
- app/ai/claude_client.py
- Caching layer with Redis
- Cost tracking (log to database or file)
- JSON response parsing
- Prompt template loading
- Error handling (API failures, rate limits)
- Unit tests with mocked API responses

VERIFICATION:
1. Successfully calls Claude API
2. Caches responses (second call instant)
3. Tracks costs accurately
4. Parses JSON responses correctly
5. Handles API errors gracefully

EXAMPLE USAGE:
```python
client = ClaudeClient(api_key=os.getenv('ANTHROPIC_API_KEY'), redis_client=redis)
response = await client.analyze(
    prompt="Score this deal on 0-100: {deal_details}",
    data={'deal_details': "Flight to Lisbon €400, 4 star hotel €80/night"},
    response_format='json'
)
print(response['score'])
```

Implement with production-grade error handling and caching.
```

**Expected Output**: Robust Claude API integration with caching

---

### Task 4.2: Deal Scorer

**Dependencies**: Task 4.1, 3.3
**Estimated Time**: 4 hours
**Can Parallelize**: ❌ No (needs Claude integration and trip packages)

**PROMPT:**
```
Build an AI-powered deal scoring system using Claude API.

CONTEXT:
We have trip packages with flights, accommodations, and total costs. We need Claude to analyze each package and score it 0-100 based on value, suitability, and timing.

**COMPLETE IMPLEMENTATION SPEC IN /home/user/smartfamilytravelscout/IMPLEMENTATION_SPEC.md - See "Task 4.2" section for full details including prompt templates and scoring criteria.**

KEY REQUIREMENTS:
1. Only analyze packages under price threshold (default: flights <€200/person)
2. Score on 0-100 scale
3. Provide reasoning and recommendation (book_now/wait/skip)
4. Generate deal scores and save to database
5. Option to analyze all flights if user requests

Create app/ai/deal_scorer.py with complete AI integration for deal analysis.
```

**Expected Output**: Deal scorer that uses Claude to evaluate trip packages

---

### Task 4.3: Itinerary Generator

**Dependencies**: Task 4.2
**Estimated Time**: 3 hours
**Can Parallelize**: ✅ YES (can run with 4.4, 4.5)

**PROMPT:**
```
Build an AI itinerary generator for high-scoring trips.

CONTEXT:
For deals scoring >70, generate detailed 3-day family itineraries using Claude.

**COMPLETE IMPLEMENTATION SPEC IN /home/user/smartfamilytravelscout/IMPLEMENTATION_SPEC.md - See "Task 4.3" section for full prompt templates.**

KEY REQUIREMENTS:
1. Generate day-by-day plans (morning/afternoon/evening)
2. Include kid-friendly activities (ages 3&6)
3. Restaurant recommendations
4. Nap time considerations
5. Walking distances from accommodation

Create app/ai/itinerary_generator.py with Claude integration.
```

**Expected Output**: Itinerary generator creating detailed family travel plans

---

### Task 4.4: Parent Escape Analyzer

**Dependencies**: Task 4.1, 3.1
**Estimated Time**: 4 hours
**Can Parallelize**: ✅ YES (parallel with 4.3, 4.5)

**PROMPT:**
```
Build analyzer for romantic getaway opportunities ("Parent Escape Mode").

CONTEXT:
Identify 2-3 night romantic trips for parents: train-accessible from Munich, special events (wine tastings, concerts), spa hotels.

**COMPLETE IMPLEMENTATION SPEC IN /home/user/smartfamilytravelscout/IMPLEMENTATION_SPEC.md - See "Task 4.4" section.**

KEY REQUIREMENTS:
1. Train routes <6h from Munich
2. Focus on: wine regions, spa hotels, cultural events
3. Score on uniqueness of timing
4. Suggest kid-care solutions

Create app/ai/parent_escape_analyzer.py with separate scoring logic.
```

**Expected Output**: Parent escape opportunity analyzer

---

### Task 4.5: Event Relevance Scorer

**Dependencies**: Task 4.1, 2.7
**Estimated Time**: 2 hours
**Can Parallelize**: ✅ YES (parallel with 4.3, 4.4)

**PROMPT:**
```
Use Claude to score event relevance (0-10) for family interests.

CONTEXT:
We have events from EventBrite/tourism boards with basic categorization. Use AI to score how relevant each event is for family travel.

**COMPLETE IMPLEMENTATION SPEC IN /home/user/smartfamilytravelscout/IMPLEMENTATION_SPEC.md - See "Task 4.5" section.**

KEY REQUIREMENTS:
1. Score 0-10 for relevance
2. Check age appropriateness
3. Align with user interests
4. Update events table with ai_relevance_score

Create app/ai/event_scorer.py to batch-score events.
```

**Expected Output**: Event scoring system using AI

---

## PHASE 5: USER INTERFACE 💻

### ⚡ Execution: All Parallel

---

### Task 5.1: CLI Tool

**Dependencies**: Tasks 4.2, 4.3
**Estimated Time**: 4 hours
**Can Parallelize**: ✅ YES

**PROMPT:**
```
Build command-line interface using Click/Typer with Rich formatting.

COMMANDS TO IMPLEMENT:

```bash
# Main pipeline
scout run --destinations all --dates next-3-months

# View deals
scout deals --min-score 70 --destination lisbon

# Configure preferences
scout config set max-budget 2000
scout config show

# Test individual scrapers
scout test-scraper kiwi --origin MUC --dest LIS

# Show statistics
scout stats --period week
scout stats --scraper all

# Database management
scout db init
scout db seed
scout db reset
```

IMPLEMENTATION (app/cli/main.py):
```python
import typer
from rich.console import Console
from rich.table import Table
from rich.progress import track

app = typer.Typer()
console = Console()

@app.command()
def run(
    destinations: str = "all",
    dates: str = "next-3-months",
    analyze: bool = True
):
    """Run full pipeline"""
    console.print("[bold green]Starting SmartFamilyTravelScout...[/bold green]")

    # 1. Scrape flights
    with console.status("[bold yellow]Scraping flights..."):
        # Call flight orchestrator
        pass

    # 2. Scrape accommodations
    # 3. Match packages
    # 4. AI analysis
    # 5. Send notifications

    console.print("[bold green]✓ Pipeline complete![/bold green]")

@app.command()
def deals(
    min_score: int = 70,
    destination: str = None,
    limit: int = 10
):
    """Show top deals"""
    # Query trip_packages table
    packages = query_packages(min_score=min_score, destination=destination)

    # Display as Rich table
    table = Table(title="Top Deals")
    table.add_column("Destination", style="cyan")
    table.add_column("Dates", style="magenta")
    table.add_column("Price", style="green")
    table.add_column("Score", style="yellow")

    for pkg in packages[:limit]:
        table.add_row(
            pkg.destination_city,
            f"{pkg.departure_date} - {pkg.return_date}",
            f"€{pkg.total_price:.0f}",
            f"{pkg.ai_score:.0f}/100"
        )

    console.print(table)
```

DELIVERABLES:
- app/cli/main.py with all commands
- Rich formatting (tables, progress bars, colors)
- Error handling and help text
- Logging integration
- Configuration management

VERIFICATION:
1. scout run executes full pipeline
2. scout deals shows formatted table
3. scout config manages preferences
4. All commands have --help text
5. Errors display nicely

Implement complete CLI with professional UX.
```

**Expected Output**: Full-featured CLI tool with Rich formatting

---

### Task 5.2: Email Notification System

**Dependencies**: Task 4.2
**Estimated Time**: 4 hours
**Can Parallelize**: ✅ YES (parallel with 5.1)

**PROMPT:**
```
Build email notification system with HTML templates.

EMAIL TYPES:

1. **Daily Digest**: Top 5 deals of the day (score >70)
2. **Deal Alert**: Immediate notification for exceptional deals (score >85)
3. **Parent Escape Digest**: Weekly roundup of romantic getaways

IMPLEMENTATION (app/notifications/email_sender.py):
```python
from jinja2 import Environment, FileSystemLoader
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

class EmailNotifier:
    def __init__(self, smtp_config: dict):
        self.smtp_host = smtp_config['host']
        self.smtp_port = smtp_config['port']
        self.smtp_user = smtp_config['user']
        self.smtp_password = smtp_config['password']
        self.from_email = smtp_config['from_email']

        # Jinja2 template environment
        self.template_env = Environment(
            loader=FileSystemLoader('app/notifications/templates')
        )

    async def send_daily_digest(self, deals: List[TripPackage]):
        """Send daily digest email"""
        template = self.template_env.get_template('daily_digest.html')

        html_content = template.render(
            deals=deals,
            date=date.today(),
            summary=f"Found {len(deals)} great deals today!"
        )

        self.send_email(
            to_email=self.get_user_email(),
            subject=f"🌍 Daily Travel Deals - {date.today()}",
            html_body=html_content
        )

    def send_email(self, to_email: str, subject: str, html_body: str):
        """Send HTML email via SMTP"""
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = self.from_email
        msg['To'] = to_email

        html_part = MIMEText(html_body, 'html')
        msg.attach(html_part)

        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            server.login(self.smtp_user, self.smtp_password)
            server.send_message(msg)
```

HTML TEMPLATES (app/notifications/templates/):

1. **daily_digest.html**:
```html
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; }
        .deal-card { border: 1px solid #ddd; padding: 15px; margin: 10px 0; }
        .destination { font-size: 24px; color: #2c3e50; }
        .price { font-size: 20px; color: #27ae60; font-weight: bold; }
        .score { background: #f39c12; color: white; padding: 5px 10px; border-radius: 5px; }
    </style>
</head>
<body>
    <h1>🌍 Your Daily Travel Deals</h1>
    <p>{{ summary }}</p>

    {% for deal in deals %}
    <div class="deal-card">
        <div class="destination">{{ deal.destination_city }}</div>
        <p>{{ deal.departure_date }} - {{ deal.return_date }} ({{ deal.num_nights }} nights)</p>
        <div class="price">€{{ deal.total_price | round(0) }}</div>
        <span class="score">Score: {{ deal.ai_score | round(0) }}/100</span>
        <p>{{ deal.ai_reasoning }}</p>
        <a href="{{ deal.booking_url }}">Book Now</a>
    </div>
    {% endfor %}
</body>
</html>
```

2. **deal_alert.html**: Similar structure for urgent deals

3. **parent_escape.html**: Romantic getaway template

SMTP CONFIGURATION:
Support Gmail, SendGrid, Mailgun:
```python
# Gmail
smtp_config = {
    'host': 'smtp.gmail.com',
    'port': 587,
    'user': 'your_email@gmail.com',
    'password': 'app_password',  # Use app-specific password
    'from_email': 'your_email@gmail.com'
}
```

DELIVERABLES:
- app/notifications/email_sender.py
- HTML email templates (3+ templates)
- SMTP configuration support
- Template rendering with Jinja2
- Error handling (SMTP failures)
- Unsubscribe handling
- Email preview function (for testing)

VERIFICATION:
1. Sends test email successfully
2. HTML renders correctly in Gmail/Outlook
3. Links work properly
4. Images display (if used)
5. Mobile responsive

Implement with beautiful HTML templates and reliable sending.
```

**Expected Output**: Email notification system with HTML templates

---

### Task 5.3: Basic Web Dashboard (Optional - Keep Warm)

**Dependencies**: Task 4.2
**Estimated Time**: 8 hours
**Can Parallelize**: ✅ YES
**Priority**: 🟢 LOW (future enhancement)

**PROMPT:**
```
Build simple FastAPI web dashboard for viewing deals and managing preferences.

PAGES TO BUILD:

1. **Dashboard** (/) - Overview of recent deals
2. **Deals** (/deals) - Filterable list of all packages
3. **Preferences** (/preferences) - Configuration form
4. **Stats** (/stats) - Charts and statistics

IMPLEMENTATION (app/api/routes/main.py):
```python
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/")
async def dashboard(request: Request):
    """Main dashboard"""
    # Get recent deals
    recent_deals = db.query(TripPackage).order_by(
        TripPackage.created_at.desc()
    ).limit(10).all()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "deals": recent_deals,
        "stats": get_stats()
    })

@app.get("/deals")
async def deals_page(
    request: Request,
    min_score: int = 0,
    destination: str = None
):
    """Deals list with filters"""
    query = db.query(TripPackage)

    if min_score:
        query = query.filter(TripPackage.ai_score >= min_score)
    if destination:
        query = query.filter(TripPackage.destination_city == destination)

    deals = query.order_by(TripPackage.ai_score.desc()).all()

    return templates.TemplateResponse("deals.html", {
        "request": request,
        "deals": deals
    })
```

TEMPLATES (use Bootstrap or Tailwind):

```html
<!-- templates/dashboard.html -->
<!DOCTYPE html>
<html>
<head>
    <title>Smart Family Travel Scout</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-dark bg-primary">
        <span class="navbar-brand">Smart Family Travel Scout</span>
    </nav>

    <div class="container mt-4">
        <h1>Recent Deals</h1>

        <div class="row">
            {% for deal in deals %}
            <div class="col-md-6 mb-3">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">{{ deal.destination_city }}</h5>
                        <p class="card-text">
                            {{ deal.departure_date }} - {{ deal.return_date }}<br>
                            <strong>€{{ deal.total_price | round(0) }}</strong><br>
                            Score: {{ deal.ai_score | round(0) }}/100
                        </p>
                        <a href="#" class="btn btn-primary">View Details</a>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
```

FEATURES:
- Responsive design (Bootstrap/Tailwind)
- Filter and sort deals
- View deal details (itinerary, events)
- Edit preferences form
- Basic charts (Chart.js for price trends)

DELIVERABLES:
- FastAPI routes (app/api/routes/)
- HTML templates (templates/)
- Static files (CSS, JS in static/)
- No authentication initially (local only)
- API endpoints for AJAX

VERIFICATION:
1. Runs on http://localhost:8000
2. Displays deals correctly
3. Filters work
4. Mobile responsive
5. Fast page loads

Implement basic dashboard, keep it simple for MVP.
```

**Expected Output**: Simple web dashboard for browsing deals

---

## PHASE 6: ORCHESTRATION & SCHEDULING 🔄

### 🔴 Execution: Sequential

---

### Task 6.1: Celery Task Scheduler

**Dependencies**: ALL previous tasks
**Estimated Time**: 4 hours
**Can Parallelize**: ❌ No (needs all components)

**PROMPT:**
```
Set up Celery for background task scheduling.

SCHEDULED TASKS:

1. **Every 6 hours**: Scrape all flights
2. **Every 12 hours**: Scrape accommodations
3. **Daily at 7am**: Run full analysis and send digest
4. **Weekly Sunday**: Parent escape analysis

IMPLEMENTATION (app/tasks/celery_app.py):
```python
from celery import Celery
from celery.schedules import crontab

celery_app = Celery(
    'travelscout',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

# Celery Beat schedule
celery_app.conf.beat_schedule = {
    'scrape-flights-every-6-hours': {
        'task': 'app.tasks.scheduled_tasks.scrape_all_flights',
        'schedule': crontab(hour='*/6'),
    },
    'scrape-accommodations-every-12-hours': {
        'task': 'app.tasks.scheduled_tasks.scrape_accommodations',
        'schedule': crontab(hour='*/12'),
    },
    'daily-deal-analysis': {
        'task': 'app.tasks.scheduled_tasks.daily_deal_analysis',
        'schedule': crontab(hour=7, minute=0),
    },
    'weekly-parent-escape': {
        'task': 'app.tasks.scheduled_tasks.weekly_parent_escape',
        'schedule': crontab(day_of_week='sunday', hour=10),
    },
}
```

TASKS (app/tasks/scheduled_tasks.py):
```python
from app.tasks.celery_app import celery_app
from app.orchestration.main_orchestrator import MainOrchestrator

@celery_app.task
def scrape_all_flights():
    """Scrape flights from all sources"""
    orchestrator = FlightOrchestrator()
    flights = await orchestrator.scrape_all(
        origins=['MUC', 'FMM', 'NUE', 'SZG'],
        destinations=get_preferred_destinations(),
        date_ranges=get_upcoming_school_holidays()
    )
    logger.info(f"Scraped {len(flights)} flights")
    return len(flights)

@celery_app.task
def daily_deal_analysis():
    """Run full pipeline and send notifications"""
    orchestrator = MainOrchestrator()
    await orchestrator.run_full_pipeline()
```

MONITORING:
Use Flower for Celery monitoring:
```bash
pip install flower
celery -A app.tasks.celery_app flower
# Access at http://localhost:5555
```

DELIVERABLES:
- app/tasks/celery_app.py (Celery config)
- app/tasks/scheduled_tasks.py (all scheduled tasks)
- Beat schedule configuration
- Error handling and retries
- Task monitoring setup
- Documentation for running workers

VERIFICATION:
1. Celery worker starts successfully
2. Beat scheduler triggers tasks
3. Tasks execute without errors
4. Can monitor in Flower
5. Failed tasks retry properly

COMMANDS TO RUN:
```bash
# Start worker
celery -A app.tasks.celery_app worker --loglevel=info

# Start beat scheduler
celery -A app.tasks.celery_app beat --loglevel=info

# Start Flower monitoring
celery -A app.tasks.celery_app flower
```

Implement robust task scheduling with monitoring.
```

**Expected Output**: Complete Celery setup with scheduled tasks

---

### Task 6.2: School Holiday Integration

**Dependencies**: Task 1.2
**Estimated Time**: 2 hours
**Can Parallelize**: ✅ YES (can run with 6.3)

**PROMPT:**
```
Implement school holiday checker and date range generator.

FEATURES (app/services/school_calendar.py):
```python
class SchoolCalendar:
    def __init__(self, db_session):
        self.db = db_session
        self.holidays = self.load_holidays()

    def is_school_holiday(self, date: date) -> bool:
        """Check if date falls within school holidays"""
        for holiday in self.holidays:
            if holiday.start_date <= date <= holiday.end_date:
                return True
        return False

    def get_upcoming_holidays(self, months: int = 3) -> List[SchoolHoliday]:
        """Get holidays in next N months"""
        start = date.today()
        end = start + timedelta(days=30 * months)

        return self.db.query(SchoolHoliday).filter(
            SchoolHoliday.start_date >= start,
            SchoolHoliday.start_date <= end
        ).order_by(SchoolHoliday.start_date).all()

    def get_date_ranges_for_search(self) -> List[Tuple[date, date]]:
        """Get (start, end) pairs for flight searching"""
        holidays = self.get_upcoming_holidays(months=6)

        ranges = []
        for holiday in holidays:
            # Search for trips spanning the holiday
            # Try different durations: 3, 5, 7, 10 nights
            for nights in [3, 5, 7, 10]:
                # Trips starting at holiday start
                ranges.append((holiday.start_date, holiday.start_date + timedelta(days=nights)))

                # Trips ending at holiday end
                ranges.append((holiday.end_date - timedelta(days=nights), holiday.end_date))

        return ranges

    def find_long_weekends(self, year: int) -> List[Tuple[date, date]]:
        """Find 3-4 day weekends with public holidays"""
        # Bavaria public holidays
        public_holidays = self.get_public_holidays(year)

        long_weekends = []
        for ph in public_holidays:
            # If holiday is Friday or Monday, it's a long weekend
            if ph.weekday() == 4:  # Friday
                long_weekends.append((ph, ph + timedelta(days=2)))  # Fri-Sun
            elif ph.weekday() == 0:  # Monday
                long_weekends.append((ph - timedelta(days=2), ph))  # Sat-Mon

        return long_weekends
```

DELIVERABLES:
- app/services/school_calendar.py
- Holiday checker functions
- Date range generator for searches
- Long weekend detector
- Unit tests

VERIFICATION:
1. Correctly identifies Easter 2025 holiday
2. Generates search date ranges for next 6 months
3. Finds long weekends
4. Works with Bavaria calendar

Implement complete calendar service.
```

**Expected Output**: School holiday service with intelligent date range generation

---

### Task 6.3: Price History & Trend Analysis

**Dependencies**: Tasks 1.2, 3.1
**Estimated Time**: 3 hours
**Can Parallelize**: ✅ YES (parallel with 6.2)

**PROMPT:**
```
Track price changes and detect trends.

FEATURES (app/services/price_tracker.py):
```python
class PriceTracker:
    def __init__(self, db_session):
        self.db = db_session

    async def record_prices(self, flights: List[Flight]):
        """Record current prices to history"""
        for flight in flights:
            route = f"{flight.origin_airport}-{flight.destination_airport}"

            history_entry = PriceHistory(
                route=route,
                price=flight.total_price,
                source=flight.source,
                scraped_at=datetime.now()
            )
            self.db.add(history_entry)

        self.db.commit()

    def get_price_history(
        self,
        origin: str,
        destination: str,
        days: int = 30
    ) -> List[PriceHistory]:
        """Get price history for route"""
        route = f"{origin}-{destination}"
        start_date = datetime.now() - timedelta(days=days)

        return self.db.query(PriceHistory).filter(
            PriceHistory.route == route,
            PriceHistory.scraped_at >= start_date
        ).order_by(PriceHistory.scraped_at).all()

    def calculate_statistics(self, origin: str, destination: str) -> Dict:
        """Calculate avg, min, max prices"""
        history = self.get_price_history(origin, destination, days=90)

        if not history:
            return None

        prices = [h.price for h in history]

        return {
            'average': sum(prices) / len(prices),
            'minimum': min(prices),
            'maximum': max(prices),
            'current': history[-1].price if history else None,
            'samples': len(prices)
        }

    def calculate_trend(self, origin: str, destination: str) -> str:
        """Detect if prices are rising, falling, or stable"""
        history = self.get_price_history(origin, destination, days=14)

        if len(history) < 5:
            return 'insufficient_data'

        # Simple trend: compare recent vs older prices
        recent_avg = sum(h.price for h in history[-5:]) / 5
        older_avg = sum(h.price for h in history[:5]) / 5

        change_pct = ((recent_avg - older_avg) / older_avg) * 100

        if change_pct > 10:
            return 'rising'
        elif change_pct < -10:
            return 'falling'
        else:
            return 'stable'

    def detect_price_drops(self, threshold: float = 20.0) -> List[Flight]:
        """Find flights with significant price drops"""
        # Compare current prices to 7-day average
        drops = []

        # Implementation: query recent flights, compare to history
        # If current price is >20% below average, flag it

        return drops
```

DELIVERABLES:
- app/services/price_tracker.py
- Price recording function
- Statistical analysis (avg, min, max)
- Trend detection algorithm
- Price drop alerting
- Unit tests

VERIFICATION:
1. Records prices to history table
2. Calculates correct statistics
3. Detects price trends accurately
4. Finds price drops >20%

Implement price tracking with trend analysis.
```

**Expected Output**: Price tracking and trend analysis service

---

### Task 6.4: Main Orchestration Loop

**Dependencies**: ALL previous tasks
**Estimated Time**: 4 hours
**Can Parallelize**: ❌ No (integrates everything)

**PROMPT:**
```
Build the main orchestrator that runs the complete pipeline.

PIPELINE FLOW:

1. Scrape flights (all sources) → Deduplicate → Calculate true costs
2. Scrape accommodations
3. Scrape events
4. Match flights + accommodations → Generate packages
5. Match events to packages
6. Filter packages by price threshold
7. AI scoring (only for filtered packages)
8. Generate itineraries (for score >70)
9. Send notifications (for score >75)
10. Update dashboard data

IMPLEMENTATION (app/orchestration/main_orchestrator.py):
```python
from rich.progress import Progress

class MainOrchestrator:
    def __init__(self, db_session):
        self.db = db_session
        self.flight_orch = FlightOrchestrator()
        self.accommodation_matcher = AccommodationMatcher(db_session)
        self.event_matcher = EventMatcher(db_session)
        self.deal_scorer = DealScorer(db_session)
        self.itinerary_gen = ItineraryGenerator(db_session)
        self.email_notifier = EmailNotifier(smtp_config)

    async def run_full_pipeline(self, config: Dict = None):
        """Execute complete pipeline"""
        logger.info("Starting full pipeline")

        with Progress() as progress:
            # Phase 1: Data Collection
            task1 = progress.add_task("[cyan]Scraping flights...", total=100)
            flights = await self.run_scraping_phase()
            progress.update(task1, completed=100)

            # Phase 2: Matching
            task2 = progress.add_task("[yellow]Matching packages...", total=100)
            packages = await self.run_matching_phase()
            progress.update(task2, completed=100)

            # Phase 3: AI Analysis
            task3 = progress.add_task("[magenta]AI analysis...", total=100)
            scored_packages = await self.run_analysis_phase(packages)
            progress.update(task3, completed=100)

            # Phase 4: Notifications
            task4 = progress.add_task("[green]Sending notifications...", total=100)
            await self.run_notification_phase(scored_packages)
            progress.update(task4, completed=100)

        logger.info(f"Pipeline complete: {len(scored_packages)} deals found")

    async def run_scraping_phase(self) -> Dict:
        """Phase 1: Scrape all data sources"""
        # Get search parameters
        origins = ['MUC', 'FMM', 'NUE', 'SZG']
        destinations = self.get_preferred_destinations()
        date_ranges = self.get_school_holiday_date_ranges()

        # Scrape flights
        flights = await self.flight_orch.scrape_all(origins, destinations, date_ranges)

        # Calculate true costs
        cost_calc = TrueCostCalculator(self.db)
        await cost_calc.calculate_for_all_flights(flights)

        # Scrape accommodations (parallel)
        booking_scraper = BookingClient()
        airbnb_scraper = AirbnbClient()

        accommodations = []
        for dest in destinations:
            for start, end in date_ranges[:3]:  # Limit to avoid overload
                booking_results = await booking_scraper.search(dest, start, end)
                airbnb_results = await airbnb_scraper.search(dest, start, end)
                accommodations.extend(booking_results + airbnb_results)

        # Scrape events
        event_scraper = EventBriteClient()
        events = []
        for dest in destinations:
            dest_events = await event_scraper.search_events(dest, start, end)
            events.extend(dest_events)

        return {
            'flights': flights,
            'accommodations': accommodations,
            'events': events
        }

    async def run_matching_phase(self) -> List[TripPackage]:
        """Phase 2: Match and create packages"""
        # Generate trip packages
        packages = await self.accommodation_matcher.generate_trip_packages(
            max_budget=2000.0
        )

        # Add events
        packages = await self.event_matcher.match_events_to_packages(packages)

        # Filter by school holidays
        packages = self.filter_by_school_holidays(packages)

        return packages

    async def run_analysis_phase(self, packages: List[TripPackage]) -> List[TripPackage]:
        """Phase 3: AI scoring and itineraries"""
        # Filter cheap packages first (< €200/person for flights)
        cheap_packages = [p for p in packages if (p.total_price / 4) < 200]

        logger.info(f"Analyzing {len(cheap_packages)} packages (out of {len(packages)} total)")

        # Score with AI
        scored = []
        for package in cheap_packages:
            score_result = await self.deal_scorer.score_trip(package)
            package.ai_score = score_result['score']
            package.ai_reasoning = score_result['reasoning']
            scored.append(package)

        # Generate itineraries for high-scoring deals
        high_score = [p for p in scored if p.ai_score >= 70]
        for package in high_score:
            itinerary = await self.itinerary_gen.generate_itinerary(package)
            package.itinerary_json = itinerary

        # Save to database
        self.db.bulk_save_objects(scored)
        self.db.commit()

        return scored

    async def run_notification_phase(self, packages: List[TripPackage]):
        """Phase 4: Send notifications"""
        # Daily digest (score > 70)
        digest_deals = [p for p in packages if p.ai_score >= 70 and not p.notified]
        if digest_deals:
            await self.email_notifier.send_daily_digest(digest_deals[:5])

        # Urgent alerts (score > 85)
        urgent_deals = [p for p in packages if p.ai_score >= 85 and not p.notified]
        for deal in urgent_deals:
            await self.email_notifier.send_deal_alert(deal)

        # Mark as notified
        for package in digest_deals + urgent_deals:
            package.notified = True
        self.db.commit()
```

ERROR HANDLING:
- Graceful degradation (continue if one phase fails)
- Comprehensive logging
- Rollback on database errors
- Email admin on critical failures

DELIVERABLES:
- app/orchestration/main_orchestrator.py
- Complete pipeline implementation
- Error handling at each phase
- Progress tracking with Rich
- Performance logging
- Dry-run mode (skip notifications)

VERIFICATION:
1. Completes full pipeline in <30 min
2. Handles scraper failures gracefully
3. Generates 20+ scored deals
4. Sends email notifications
5. Logs all phases clearly

EXAMPLE USAGE:
```python
orchestrator = MainOrchestrator(db_session)
await orchestrator.run_full_pipeline()
```

Implement robust main orchestrator with complete error handling.
```

**Expected Output**: Complete pipeline orchestrator integrating all components

---

## ✅ EXECUTION SUMMARY

### **Parallel Execution Groups**:

**Group 1 - Foundation** (Sequential):
1. Task 1.1 → 1.2 → 1.3

**Group 2 - Data Collection** (8 tasks in parallel):
2. Tasks 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8 (ALL PARALLEL)

**Group 3 - Processing** (Mixed):
3. Task 3.1 (after Group 2)
4. Task 3.2 (parallel with 3.1)
5. Task 3.3 (after 3.1)
6. Task 3.4 (parallel with 3.3)

**Group 4 - AI Engine** (Sequential → Parallel):
7. Task 4.1 (sequential)
8. Task 4.2 (after 4.1)
9. Tasks 4.3, 4.4, 4.5 (ALL PARALLEL after 4.2)

**Group 5 - UI** (3 tasks in parallel):
10. Tasks 5.1, 5.2, 5.3 (ALL PARALLEL)

**Group 6 - Integration** (Sequential):
11. Tasks 6.2, 6.3 (parallel)
12. Task 6.1 (after all)
13. Task 6.4 (final integration)

---

## 📋 QUICK START CHECKLIST

After implementing all tasks:

```bash
# 1. Setup environment
docker-compose up -d
python -m alembic upgrade head
python -m app.utils.seed_data

# 2. Run first scrape
scout run --destinations all --dates next-3-months

# 3. View deals
scout deals --min-score 70

# 4. Start scheduled tasks
celery -A app.tasks.celery_app worker --loglevel=info
celery -A app.tasks.celery_app beat --loglevel=info

# 5. Access dashboard
# http://localhost:8000
```

---

**🎉 ALL CLAUDE CODE PROMPTS COMPLETE!**

You now have **27 copy-paste ready prompts** organized into 6 phases with clear parallelization instructions.