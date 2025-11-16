# SmartFamilyTravelScout - Implementation Specification

## Executive Summary

**Project**: AI-powered family travel deal finder with multi-airport monitoring and parent escape mode
**Tech Stack**: Python 3.11+, PostgreSQL, Redis, FastAPI, Celery, Playwright, Claude API
**Deployment**: Local development → Cloud (Railway/Render)
**API Strategy**: Free tiers + web scraping fallbacks
**Budget**: ~€30-50/month Claude API (production)

---

## System Architecture

```
┌─────────────────────────────────────────────────┐
│         Data Collection Layer (Scrapers)        │
│  ┌──────────┐ ┌──────────┐ ┌───────────────┐  │
│  │ Flights  │ │ Accomm.  │ │    Events     │  │
│  │ - Kiwi   │ │ - Booking│ │ - EventBrite  │  │
│  │ - Skyscan│ │ - Airbnb │ │ - Tourism     │  │
│  │ - Ryanair│ │          │ │   Boards      │  │
│  │ - WizzAir│ │          │ │               │  │
│  └──────────┘ └──────────┘ └───────────────┘  │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│      Data Processing Layer (Orchestration)      │
│  - Deduplication                                │
│  - Price normalization                          │
│  - True cost calculation                        │
│  - Package matching                             │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│         AI Analysis Layer (Claude)              │
│  - Price threshold filter (€200/person family)  │
│  - Deal scoring (0-100)                         │
│  - Itinerary generation                         │
│  - Parent escape recommendations                │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│          User Interface Layer                   │
│  ┌──────────┐ ┌───────────┐ ┌───────────────┐ │
│  │   CLI    │ │   Email   │ │  Web Dash     │ │
│  │   Tool   │ │   Alerts  │ │  (Later)      │ │
│  └──────────┘ └───────────┘ └───────────────┘ │
└─────────────────────────────────────────────────┘
```

---

## Task Breakdown & Execution Plan

### PHASE 1: FOUNDATION 🏗️
**Execution**: Sequential (each depends on previous)
**Estimated Time**: 6-8 hours total

---

#### **Task 1.1: Project Setup & Infrastructure**
**Priority**: 🔴 CRITICAL
**Parallelizable**: No (foundation)
**Estimated Time**: 2 hours
**Dependencies**: None

**What to Build**:
- Python project with Poetry
- Docker Compose (PostgreSQL 15, Redis, app)
- Environment configuration
- Logging setup
- Basic health check endpoint

**Deliverables**:
- ✅ Project structure with proper folders
- ✅ `docker-compose.yml` with all services
- ✅ `.env.example` with all required variables
- ✅ `pyproject.toml` with dependencies
- ✅ README with setup instructions

**Verification**: `docker-compose up` runs without errors

---

#### **Task 1.2: Database Schema Implementation**
**Priority**: 🔴 CRITICAL
**Parallelizable**: No (needed by all data tasks)
**Estimated Time**: 3 hours
**Dependencies**: Task 1.1

**What to Build**:
- SQLAlchemy models for 9 tables:
  1. `airports` (MUC, FMM, NUE, SZG with distances)
  2. `flights` (all flight data with source tracking)
  3. `accommodations` (hotels, Airbnb)
  4. `events` (local events with AI scores)
  5. `trip_packages` (AI-generated combinations)
  6. `user_preferences` (budget, interests)
  7. `school_holidays` (Bavaria calendar)
  8. `price_history` (trend analysis)
  9. `scraping_jobs` (track scraping runs)

**Deliverables**:
- ✅ SQLAlchemy models with relationships
- ✅ Alembic migrations
- ✅ Seed data script (airports, 2025-2026 school holidays)
- ✅ Database initialization script
- ✅ Helper functions for common queries

**Verification**: Migrations run, seed data loads, tables queryable

---

#### **Task 1.3: Core Utilities & Helpers**
**Priority**: 🟡 HIGH
**Parallelizable**: No (used by all modules)
**Estimated Time**: 2 hours
**Dependencies**: Task 1.1

**What to Build**:
- Date range utilities (school holiday checker)
- Distance/geolocation helpers
- Price normalization functions
- Retry decorators with exponential backoff
- Logging configuration
- Environment variable loader

**Deliverables**:
- ✅ `utils/date_utils.py` (is_school_holiday, get_upcoming_holidays)
- ✅ `utils/geo_utils.py` (calculate_distance, driving_time_estimate)
- ✅ `utils/price_utils.py` (normalize_currency, calculate_per_person)
- ✅ `utils/retry.py` (retry decorator with backoff)
- ✅ Unit tests for all utilities

**Verification**: All utility functions have passing tests

---

### PHASE 2: DATA COLLECTION 📊
**Execution**: ⚡ **FULLY PARALLEL** (all 8 tasks can run simultaneously)
**Estimated Time**: 24-32 hours total (but 4-6 hours wall time if parallel)

---

#### **Task 2.1: Kiwi.com Flight Scraper**
**Priority**: 🔴 CRITICAL
**Parallelizable**: ✅ YES
**Estimated Time**: 4 hours
**Dependencies**: Tasks 1.2, 1.3

**What to Build**:
- Kiwi.com API integration (free tier: 100 calls/month)
- Multi-city search from all 4 airports
- Response parsing to standard format
- Database storage

**Key Features**:
- Search "anywhere" mode (finds all destinations from origin)
- Virtual interlining support
- Self-transfer flagging
- Rate limiting (100 calls/month = ~3/day)

**Deliverables**:
- ✅ `scrapers/kiwi_scraper.py` with `KiwiClient` class
- ✅ Methods: `search_flights()`, `search_anywhere()`, `parse_response()`
- ✅ Outputs standardized `FlightOffer` dict
- ✅ Stores in `flights` table with `source='kiwi'`
- ✅ Unit tests with mocked responses

**Verification**: Fetches 50+ flights from MUC, stores in DB

---

#### **Task 2.2: Skyscanner Web Scraper**
**Priority**: 🟡 HIGH
**Parallelizable**: ✅ YES
**Estimated Time**: 5 hours
**Dependencies**: Tasks 1.2, 1.3

**What to Build**:
- Playwright-based scraper (no API key needed)
- Handles dynamic JavaScript content
- Respectful scraping with delays
- Error handling and retries

**Key Features**:
- Navigate to Skyscanner search page
- Fill in form fields programmatically
- Wait for results to load
- Parse flight cards
- Handle "no results" gracefully

**Deliverables**:
- ✅ `scrapers/skyscanner_scraper.py` with `SkyscannerScraper` class
- ✅ Playwright browser context management
- ✅ Random delays (3-7 seconds) between requests
- ✅ User agent rotation
- ✅ Screenshot on errors for debugging
- ✅ Outputs same `FlightOffer` format

**Verification**: Scrapes MUC→LIS flights, stores in DB

---

#### **Task 2.3: Ryanair Direct Scraper**
**Priority**: 🟡 HIGH
**Parallelizable**: ✅ YES
**Estimated Time**: 5 hours
**Dependencies**: Tasks 1.2, 1.3

**What to Build**:
- Playwright scraper for Ryanair.com
- Cookie consent handling
- Price extraction from fare calendar
- Direct flight filtering

**Key Features**:
- Focus on MUC, FMM routes (Ryanair hubs)
- Extract lowest fares for date ranges
- Handle dynamic pricing popups
- Respectful scraping (2-5 second delays)

**Deliverables**:
- ✅ `scrapers/ryanair_scraper.py` with `RyanairScraper` class
- ✅ CSS selectors with fallbacks
- ✅ Cookie popup handler
- ✅ Fare calendar parser
- ✅ Outputs `FlightOffer` format with `source='ryanair'`

**Verification**: Scrapes 20+ Ryanair flights from FMM

---

#### **Task 2.4: WizzAir Scraper**
**Priority**: 🟢 MEDIUM
**Parallelizable**: ✅ YES
**Estimated Time**: 4 hours
**Dependencies**: Tasks 1.2, 1.3

**What to Build**:
- WizzAir API integration (unofficial/scraping)
- Focus on budget routes to Eastern Europe
- Multi-month search support

**Key Features**:
- WizzAir has unofficial API (network tab inspection)
- JSON responses easier than HTML parsing
- Good for Moldova (CHI) routes

**Deliverables**:
- ✅ `scrapers/wizzair_scraper.py` with `WizzAirScraper` class
- ✅ HTTP requests to unofficial API endpoints
- ✅ JSON response parsing
- ✅ Outputs `FlightOffer` format

**Verification**: Finds flights to Chisinau (Moldova)

---

#### **Task 2.5: Booking.com Scraper**
**Priority**: 🔴 CRITICAL
**Parallelizable**: ✅ YES
**Estimated Time**: 5 hours
**Dependencies**: Tasks 1.2, 1.3

**What to Build**:
- Playwright scraper for Booking.com
- Family-friendly filters (2 adults, 2 children ages 3&6)
- Amenity extraction (kitchen, kids club)
- Price and rating parsing

**Key Features**:
- Search with specific guest configuration
- Filter by: bedrooms (2+), family rooms
- Extract: price, rating, amenities, photos
- Handle pagination (get top 20 results)

**Deliverables**:
- ✅ `scrapers/booking_scraper.py` with `BookingClient` class
- ✅ Methods: `search()`, `parse_property()`, `extract_amenities()`
- ✅ Outputs `Accommodation` dict format
- ✅ Stores in `accommodations` table

**Verification**: Finds 20 family apartments in Lisbon

---

#### **Task 2.6: Airbnb Scraper**
**Priority**: 🟡 HIGH
**Parallelizable**: ✅ YES
**Estimated Time**: 5 hours
**Dependencies**: Tasks 1.2, 1.3

**What to Build**:
- Airbnb scraper using Apify (free tier: 5,000 results/month)
- Alternative: Direct scraping with Playwright
- Focus on "Entire place" with 2+ bedrooms

**Key Features**:
- Apify has pre-built Airbnb scraper
- Free tier sufficient for testing
- Fallback to direct scraping if needed

**Deliverables**:
- ✅ `scrapers/airbnb_scraper.py` with `AirbnbClient` class
- ✅ Apify integration OR Playwright scraper
- ✅ Family filters (bedrooms, amenities)
- ✅ Outputs `Accommodation` format with `type='airbnb'`

**Verification**: Finds 15 Airbnb apartments in Barcelona

---

#### **Task 2.7: EventBrite Scraper**
**Priority**: 🟢 MEDIUM
**Parallelizable**: ✅ YES
**Estimated Time**: 3 hours
**Dependencies**: Tasks 1.2, 1.3

**What to Build**:
- EventBrite API integration (free tier)
- Event search by location and date
- Basic categorization (family/cultural/parent-escape)

**Key Features**:
- Free API key (up to 1,000 requests/day)
- Search radius around city center
- Filter by date range (±7 days from trip dates)

**Deliverables**:
- ✅ `scrapers/eventbrite_scraper.py` with `EventBriteClient` class
- ✅ Methods: `search_events()`, `categorize_event()`
- ✅ Outputs `Event` dict format
- ✅ Stores in `events` table with `ai_relevance_score=NULL`

**Verification**: Finds 30+ events in Prague for December

---

#### **Task 2.8: Tourism Board Scrapers**
**Priority**: 🟢 LOW (can skip for MVP)
**Parallelizable**: ✅ YES
**Estimated Time**: 4 hours
**Dependencies**: Tasks 1.2, 1.3

**What to Build**:
- Scrapers for 5-10 major city tourism websites
- Focus on family-friendly events and festivals
- Multi-language support (EN, DE)

**Target Sites**:
- Lisbon: visitlisboa.com
- Barcelona: barcelonaturisme.com
- Prague: prague.eu
- Porto: visitporto.travel
- Vienna: wien.info

**Deliverables**:
- ✅ `scrapers/tourism_scraper.py` with city-specific parsers
- ✅ Generic scraper base class
- ✅ Event extraction and normalization
- ✅ Stores in `events` table

**Verification**: Finds local festivals not on EventBrite

---

### PHASE 3: DATA PROCESSING ⚙️
**Execution**: Sequential → Parallel
**Estimated Time**: 10-12 hours total

---

#### **Task 3.1: Flight Orchestrator & Deduplication**
**Priority**: 🔴 CRITICAL
**Parallelizable**: No (needs all flight scrapers)
**Estimated Time**: 4 hours
**Dependencies**: Tasks 2.1, 2.2, 2.3, 2.4

**What to Build**:
- Orchestrator that runs all flight scrapers
- Async execution with `asyncio.gather()`
- Deduplication logic across sources
- Database persistence

**Deduplication Logic**:
- Flights are "same" if:
  - Same route (origin + destination)
  - Same date (±2 hours for departure)
  - Same airline
- Keep flight with lowest price
- Merge `booking_url` from all sources

**Deliverables**:
- ✅ `orchestration/flight_orchestrator.py`
- ✅ Class: `FlightOrchestrator`
- ✅ Methods:
  - `async scrape_all(origins, destinations, date_range)`
  - `deduplicate(flights) -> List[Flight]`
  - `save_to_database(flights)`
- ✅ Progress logging and error handling

**Verification**: Scrapes 200+ flights, deduplicates to ~150 unique

---

#### **Task 3.2: True Cost Calculator**
**Priority**: 🟡 HIGH
**Parallelizable**: Can run with 3.1
**Estimated Time**: 3 hours
**Dependencies**: Task 1.2, airport seed data

**What to Build**:
- Calculate real cost of flying from each airport
- Include: baggage, parking, fuel, time value

**Cost Formula**:
```
Base Price (from scraper)
+ Baggage: €30/bag for budget, €0 for legacy carriers
+ Parking: Airport-specific daily rate × days
+ Fuel: €0.08/km × distance_from_home × 2 (round trip)
+ Time Value: €20/hour × (driving_time/60) × 2
= Total True Cost
```

**Deliverables**:
- ✅ `utils/cost_calculator.py`
- ✅ Class: `TrueCostCalculator`
- ✅ Methods:
  - `calculate_baggage_cost(airline, bags=2)`
  - `calculate_parking_cost(airport, days)`
  - `calculate_fuel_cost(airport, distance)`
  - `calculate_time_value(airport, driving_time)`
  - `calculate_total_true_cost(flight) -> dict`
- ✅ Airport-specific cost data

**Verification**: MUC flight €100 → true cost ~€180 (detailed breakdown)

---

#### **Task 3.3: Accommodation Matcher**
**Priority**: 🟡 HIGH
**Parallelizable**: Can run with 3.2
**Estimated Time**: 3 hours
**Dependencies**: Tasks 2.5, 2.6, 3.1

**What to Build**:
- Match flights with accommodations
- Calculate total trip cost
- Generate trip package combinations
- Filter by budget and dates

**Matching Logic**:
```
For each destination with flights:
  1. Find accommodations in city
  2. Calculate nights (from flight dates)
  3. Calculate total cost:
     - Flights (true cost × 4 people)
     - Accommodation (price/night × nights)
     - Food estimate (€100/day × nights)
  4. Create TripPackage if:
     - Total < max_budget
     - Dates align with school holidays
     - 3-10 nights duration
```

**Deliverables**:
- ✅ `orchestration/accommodation_matcher.py`
- ✅ Class: `AccommodationMatcher`
- ✅ Methods:
  - `match_flights_to_accommodations(destination)`
  - `calculate_trip_cost(flight, accommodation)`
  - `generate_trip_packages() -> List[TripPackage]`
- ✅ Stores in `trip_packages` table

**Verification**: Generates 50+ trip packages under €2000

---

#### **Task 3.4: Event Matcher**
**Priority**: 🟢 MEDIUM
**Parallelizable**: ✅ YES (parallel with 3.3)
**Estimated Time**: 2 hours
**Dependencies**: Tasks 2.7, 2.8, 3.1

**What to Build**:
- Match events with trip dates
- Basic relevance filtering
- Associate events with trip packages

**Deliverables**:
- ✅ `orchestration/event_matcher.py`
- ✅ Class: `EventMatcher`
- ✅ Methods:
  - `find_events_for_trip(trip_package)`
  - `filter_by_age_appropriateness(events, kids_ages=[3,6])`
- ✅ Updates `trip_packages.events_json`

**Verification**: 80% of trip packages have 2+ matched events

---

### PHASE 4: AI ENGINE 🤖
**Execution**: Sequential (each builds on previous)
**Estimated Time**: 12-15 hours total

---

#### **Task 4.1: Claude API Integration**
**Priority**: 🔴 CRITICAL
**Parallelizable**: No (foundation for AI tasks)
**Estimated Time**: 2 hours
**Dependencies**: Task 1.1

**What to Build**:
- Claude API client with official SDK
- Prompt template system
- Response parsing and validation
- Cost tracking
- Caching layer (Redis)

**Key Features**:
- Use `anthropic` Python SDK
- Cache responses for 24h (avoid re-analyzing same data)
- Track API costs per request
- Structured output parsing (JSON mode)

**Deliverables**:
- ✅ `ai/claude_client.py`
- ✅ Class: `ClaudeClient`
- ✅ Methods:
  - `analyze(prompt, data, response_format='json')`
  - `get_cached_response(cache_key)`
  - `track_cost(tokens_used)`
- ✅ `ai/prompts/` directory for templates
- ✅ Cost dashboard query (total spent today/month)

**Verification**: Send test prompt, receive JSON response, cache works

---

#### **Task 4.2: Deal Scorer**
**Priority**: 🔴 CRITICAL
**Parallelizable**: No (most important AI feature)
**Estimated Time**: 4 hours
**Dependencies**: Task 4.1, 3.3

**What to Build**:
- AI-powered deal scoring (0-100)
- Price analysis vs. historical data
- Family suitability assessment
- Recommendation engine (book/wait/skip)

**Prompt Template**:
```
Analyze this family trip deal:

TRIP DETAILS:
- Destination: {city}
- Dates: {dates}
- Flights: {flight_details} (True cost: €{true_cost})
- Accommodation: {accommodation_name} ({type}, {bedrooms} bed, €{price}/night)
- Total Cost: €{total_cost} for 4 people

HISTORICAL CONTEXT:
- Average price for this route: €{avg_price}
- Lowest seen: €{lowest_price}
- This is {percentage}% {above/below} average

EVENTS DURING VISIT:
{events_list}

REQUIREMENTS:
1. Overall Deal Score (0-100)
2. Value Assessment (is this genuinely cheap?)
3. Family Suitability (kids ages 3 & 6)
4. Timing Quality (events, weather)
5. Recommendation (book_now/wait/skip)
6. Confidence Level (0-100)
7. Brief reasoning (2-3 sentences)

Output JSON only.
```

**Deliverables**:
- ✅ `ai/deal_scorer.py`
- ✅ Class: `DealScorer`
- ✅ Methods:
  - `score_trip(trip_package) -> dict`
  - `filter_good_deals(packages, threshold=70) -> List`
- ✅ Prompt template in `ai/prompts/deal_analysis.txt`
- ✅ Updates `trip_packages.ai_score` and `ai_reasoning`

**Verification**: Scores 10 trips, saves results to DB

---

#### **Task 4.3: Itinerary Generator**
**Priority**: 🟡 HIGH
**Parallelizable**: Can run with 4.4
**Estimated Time**: 3 hours
**Dependencies**: Task 4.2

**What to Build**:
- Generate 3-day itineraries for top-scored deals
- Include activities, restaurants, logistics
- Family-friendly focus

**Prompt Template**:
```
Create a 3-day family itinerary for:

DESTINATION: {city}
DATES: {dates}
FAMILY: 2 adults, 2 children (ages 3 & 6)
ACCOMMODATION: {accommodation_address}
EVENTS AVAILABLE: {events_list}

REQUIREMENTS:
- Day-by-day plan with morning/afternoon/evening
- Include kid-friendly activities
- Nap time considerations (1-2pm)
- Restaurant recommendations (high chairs, kids menu)
- Walking distances from accommodation
- Backup plans for bad weather

Output as JSON with structure:
{
  "day_1": {"morning": "...", "afternoon": "...", "evening": "..."},
  "day_2": {...},
  "day_3": {...},
  "tips": ["...", "..."]
}
```

**Deliverables**:
- ✅ `ai/itinerary_generator.py`
- ✅ Class: `ItineraryGenerator`
- ✅ Methods:
  - `generate_itinerary(trip_package) -> dict`
- ✅ Stores in `trip_packages.itinerary_json`

**Verification**: Generates detailed 3-day plan for Lisbon trip

---

#### **Task 4.4: Parent Escape Analyzer**
**Priority**: 🟢 MEDIUM
**Parallelizable**: ✅ YES (parallel with 4.3)
**Estimated Time**: 4 hours
**Dependencies**: Task 4.1, 3.1

**What to Build**:
- Separate analyzer for romantic getaways
- Focus on: wine regions, spa hotels, cultural events
- Train-accessible destinations (max 6h from Munich)
- Suggests kid-care solutions

**Search Criteria**:
- 2-3 nights
- Train from Munich (<6h) OR cheap short flight (<1.5h)
- Events: wine tastings, concerts, Michelin restaurants
- Hotels: spa, romantic, boutique

**Deliverables**:
- ✅ `ai/parent_escape_analyzer.py`
- ✅ Class: `ParentEscapeAnalyzer`
- ✅ Methods:
  - `find_escape_opportunities(date_range)`
  - `score_escape(destination, events) -> dict`
- ✅ Separate prompt template
- ✅ Creates `trip_packages` with `type='parent_escape'`

**Verification**: Finds 5+ parent escape options (Vienna, Salzburg, Bolzano, etc.)

---

#### **Task 4.5: Event Relevance Scorer**
**Priority**: 🟢 MEDIUM
**Parallelizable**: ✅ YES (parallel with 4.3, 4.4)
**Estimated Time**: 2 hours
**Dependencies**: Task 4.1, 2.7

**What to Build**:
- Score events for relevance (0-10)
- Categorize: family_event, parent_escape, cultural, skip
- Age appropriateness check

**Deliverables**:
- ✅ `ai/event_scorer.py`
- ✅ Class: `EventScorer`
- ✅ Methods:
  - `score_event(event, user_interests) -> float`
- ✅ Updates `events.ai_relevance_score`

**Verification**: Scores 50 events, filters out 30 irrelevant ones

---

### PHASE 5: USER INTERFACE 💻
**Execution**: Parallel
**Estimated Time**: 10-12 hours total

---

#### **Task 5.1: CLI Tool**
**Priority**: 🔴 CRITICAL
**Parallelizable**: ✅ YES
**Estimated Time**: 4 hours
**Dependencies**: Tasks 4.2, 4.3

**What to Build**:
- Command-line interface with Click or Typer
- Commands for common operations
- Pretty output formatting (Rich library)

**CLI Commands**:
```bash
# Run full pipeline
scout run --destinations all --dates next-3-months

# View deals
scout deals --min-score 70 --destination lisbon

# Configure preferences
scout config set max-budget 2000

# Test scrapers
scout test-scraper kiwi

# Show stats
scout stats --period week
```

**Deliverables**:
- ✅ `cli/main.py` with Click/Typer
- ✅ Commands: `run`, `deals`, `config`, `test-scraper`, `stats`
- ✅ Rich formatting (tables, progress bars)
- ✅ Error handling and help text

**Verification**: Run `scout run`, see pretty output with deals

---

#### **Task 5.2: Email Notification System**
**Priority**: 🔴 CRITICAL
**Parallelizable**: ✅ YES (parallel with 5.1)
**Estimated Time**: 4 hours
**Dependencies**: Task 4.2

**What to Build**:
- Email sender with templates
- Daily digest of top deals
- Immediate alerts for exceptional deals (score >85)
- HTML email formatting

**Email Types**:
1. **Daily Digest**: Top 5 deals of the day
2. **Deal Alert**: Immediate notification for score >85
3. **Parent Escape**: Weekly roundup of romantic getaway options

**Deliverables**:
- ✅ `notifications/email_sender.py`
- ✅ Class: `EmailNotifier`
- ✅ Methods:
  - `send_daily_digest(deals)`
  - `send_deal_alert(trip_package)`
  - `send_parent_escape_digest(escapes)`
- ✅ HTML templates with Jinja2
- ✅ SMTP configuration (Gmail, SendGrid, or Mailgun)

**Verification**: Sends test email with 3 deals, looks good in Gmail

---

#### **Task 5.3: Basic Web Dashboard (Warm)**
**Priority**: 🟢 LOW (future enhancement)
**Parallelizable**: ✅ YES
**Estimated Time**: 8 hours
**Dependencies**: Task 4.2

**What to Build**:
- Simple FastAPI web app
- Pages: Deals, Preferences, Stats
- No authentication (local only initially)
- Bootstrap/Tailwind CSS

**Pages**:
1. **Dashboard**: Overview of recent deals
2. **Deals**: Filterable list with scores
3. **Preferences**: Configure budget, destinations, interests
4. **Stats**: Charts of price trends, scraping stats

**Deliverables**:
- ✅ `api/routes/` (FastAPI routes)
- ✅ `templates/` (Jinja2 HTML templates)
- ✅ `static/` (CSS, JS)
- ✅ Pages: dashboard, deals, preferences, stats
- ✅ Basic charts with Chart.js

**Verification**: Visit http://localhost:8000, see deals table

---

### PHASE 6: ORCHESTRATION & SCHEDULING 🔄
**Execution**: Sequential
**Estimated Time**: 8-10 hours total

---

#### **Task 6.1: Celery Task Scheduler**
**Priority**: 🔴 CRITICAL
**Parallelizable**: No (needs all components)
**Estimated Time**: 4 hours
**Dependencies**: All previous tasks

**What to Build**:
- Celery workers for background tasks
- Scheduled tasks with Celery Beat
- Task monitoring and retry logic

**Scheduled Tasks**:
```python
# Every 6 hours: Scrape flights
@celery.task
def scrape_all_flights():
    orchestrator = FlightOrchestrator()
    orchestrator.scrape_all()

# Every 12 hours: Scrape accommodations
@celery.task
def scrape_accommodations():
    ...

# Daily at 7am: Generate deals and send emails
@celery.task
def daily_deal_analysis():
    ...

# Weekly Sunday: Parent escape analysis
@celery.task
def weekly_parent_escape():
    ...
```

**Deliverables**:
- ✅ `tasks/celery_app.py` (Celery configuration)
- ✅ `tasks/scheduled_tasks.py` (all scheduled tasks)
- ✅ Celery Beat schedule configuration
- ✅ Task monitoring with Flower (optional)

**Verification**: Celery worker runs, tasks execute on schedule

---

#### **Task 6.2: School Holiday Integration**
**Priority**: 🟡 HIGH
**Parallelizable**: Can run with 6.3
**Estimated Time**: 2 hours
**Dependencies**: Task 1.2

**What to Build**:
- School holiday checker service
- Bavaria calendar for 2025-2027
- Long weekend detector
- Major holiday flagging

**Deliverables**:
- ✅ `services/school_calendar.py`
- ✅ Class: `SchoolCalendar`
- ✅ Methods:
  - `is_school_holiday(date) -> bool`
  - `get_upcoming_holidays(months=3) -> List`
  - `get_long_weekends() -> List`
- ✅ Holiday data for 2025-2027

**Verification**: Correctly identifies Easter 2025, Summer 2026

---

#### **Task 6.3: Price History & Trend Analysis**
**Priority**: 🟡 HIGH
**Parallelizable**: ✅ YES (parallel with 6.2)
**Estimated Time**: 3 hours
**Dependencies**: Tasks 1.2, 3.1

**What to Build**:
- Track price changes over time
- Calculate average, min, max prices per route
- Trend detection (prices rising/falling)
- Alert on price drops

**Deliverables**:
- ✅ `services/price_tracker.py`
- ✅ Class: `PriceTracker`
- ✅ Methods:
  - `record_price(flight)`
  - `get_price_history(route, days=30)`
  - `calculate_trend(route) -> str` (rising/falling/stable)
  - `detect_price_drops(threshold=20%) -> List`
- ✅ Stores in `price_history` table

**Verification**: Shows MUC→LIS price trend over 2 weeks

---

#### **Task 6.4: Main Orchestration Loop**
**Priority**: 🔴 CRITICAL
**Parallelizable**: No (integrates everything)
**Estimated Time**: 4 hours
**Dependencies**: ALL previous tasks

**What to Build**:
- Master orchestrator that runs entire pipeline
- Error handling and logging
- Progress tracking
- Performance monitoring

**Pipeline Flow**:
```
1. Scrape flights (all sources) → Deduplicate → Save
2. Scrape accommodations → Save
3. Scrape events → Save
4. Match flights + accommodations → Generate packages
5. Match events to packages
6. Filter packages by price (< threshold)
7. AI scoring (only for filtered packages)
8. Generate itineraries (for score > 70)
9. Send notifications (score > 75)
10. Update dashboard data
```

**Deliverables**:
- ✅ `orchestration/main_orchestrator.py`
- ✅ Class: `MainOrchestrator`
- ✅ Methods:
  - `async run_full_pipeline(config)`
  - `run_scraping_phase()`
  - `run_analysis_phase()`
  - `run_notification_phase()`
- ✅ Comprehensive error handling
- ✅ Progress logging with Rich

**Verification**: Run full pipeline, completes in <30 min, sends emails

---

## Dependency Graph

```
PHASE 1 (Sequential)
├─ 1.1 Project Setup
├─ 1.2 Database Schema (depends on 1.1)
└─ 1.3 Core Utilities (depends on 1.1)

PHASE 2 (Parallel - all can run simultaneously)
├─ 2.1 Kiwi Scraper (depends on 1.2, 1.3)
├─ 2.2 Skyscanner Scraper (depends on 1.2, 1.3)
├─ 2.3 Ryanair Scraper (depends on 1.2, 1.3)
├─ 2.4 WizzAir Scraper (depends on 1.2, 1.3)
├─ 2.5 Booking Scraper (depends on 1.2, 1.3)
├─ 2.6 Airbnb Scraper (depends on 1.2, 1.3)
├─ 2.7 EventBrite Scraper (depends on 1.2, 1.3)
└─ 2.8 Tourism Scrapers (depends on 1.2, 1.3)

PHASE 3 (Mixed)
├─ 3.1 Flight Orchestrator (depends on 2.1-2.4) [Sequential]
├─ 3.2 True Cost Calculator (depends on 1.2) [Parallel with 3.1]
├─ 3.3 Accommodation Matcher (depends on 2.5, 2.6, 3.1)
└─ 3.4 Event Matcher (depends on 2.7, 2.8, 3.1) [Parallel with 3.3]

PHASE 4 (Sequential → Parallel)
├─ 4.1 Claude Integration (depends on 1.1) [Sequential]
├─ 4.2 Deal Scorer (depends on 4.1, 3.3) [Sequential]
├─ 4.3 Itinerary Generator (depends on 4.2) [Parallel]
├─ 4.4 Parent Escape Analyzer (depends on 4.1, 3.1) [Parallel]
└─ 4.5 Event Scorer (depends on 4.1, 2.7) [Parallel]

PHASE 5 (Parallel)
├─ 5.1 CLI Tool (depends on 4.2, 4.3)
├─ 5.2 Email Notifications (depends on 4.2)
└─ 5.3 Web Dashboard (depends on 4.2) [Optional]

PHASE 6 (Sequential)
├─ 6.1 Celery Scheduler (depends on ALL)
├─ 6.2 School Holiday Integration (depends on 1.2)
├─ 6.3 Price Tracker (depends on 1.2, 3.1)
└─ 6.4 Main Orchestrator (depends on ALL)
```

---

## Parallel Execution Groups

### **Group 1: Foundation (Sequential)**
Run these in order:
1. Task 1.1 → Task 1.2 → Task 1.3

### **Group 2: Data Collection (Fully Parallel)**
Start all simultaneously after Group 1:
- Task 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8

### **Group 3: Processing (Mixed)**
Start after Group 2:
- Task 3.1 (wait for 2.1-2.4)
- Task 3.2 (can start immediately after 1.2)
- Task 3.3 (wait for 3.1 + 2.5 + 2.6)
- Task 3.4 (wait for 3.1 + 2.7 + 2.8, parallel with 3.3)

### **Group 4: AI Engine (Sequential Start → Parallel)**
- Task 4.1 (wait for 1.1)
- Task 4.2 (wait for 4.1 + 3.3)
- Then parallel: Task 4.3, 4.4, 4.5

### **Group 5: UI (Fully Parallel)**
Start after 4.2:
- Task 5.1, 5.2, 5.3 (all parallel)

### **Group 6: Integration (Sequential)**
Start after everything:
1. Task 6.2, 6.3 (parallel)
2. Task 6.1
3. Task 6.4

---

## API Keys & Service Registration Checklist

### **Required (Free Tiers)**
- [ ] Kiwi.com API (100 calls/month)
- [ ] EventBrite API (1,000 calls/day)
- [ ] Claude API (Anthropic) - €30-50/month
- [ ] SendGrid/Mailgun (Email - 100 emails/day free)

### **Optional (Can scrape instead)**
- [ ] Apify (Airbnb scraper - 5,000 results/month free)
- [ ] Booking.com Affiliate (requires approval)

### **Not Needed (Direct Scraping)**
- ❌ Skyscanner API (use web scraping)
- ❌ Ryanair API (use web scraping)
- ❌ Airbnb API (use Apify or scraping)

---

## Testing Strategy

Each task should include:
1. **Unit tests** (isolated functionality)
2. **Integration tests** (with dependencies)
3. **Manual verification** (run and inspect output)

Example test structure:
```
tests/
├── unit/
│   ├── test_kiwi_scraper.py (mocked responses)
│   ├── test_cost_calculator.py
│   └── test_deal_scorer.py
├── integration/
│   ├── test_flight_orchestrator.py (real DB)
│   └── test_full_pipeline.py
└── fixtures/
    ├── sample_flights.json
    └── sample_accommodations.json
```

---

## Cost Estimates

### **Development Phase** (3 months)
- Claude API testing: €15-20/month
- Apify free tier: €0
- Email (SendGrid): €0
- **Total**: ~€15-20/month

### **Production Phase**
- Claude API (100 analyses/day): €30-50/month
- Apify Pro (if needed): €20/month
- Email (SendGrid/Mailgun): €10/month
- Hosting (Railway/Render): €0 (free tier initially)
- **Total**: ~€60-80/month

**ROI**: One successful cheap trip saves €500+ ✅

---

## Success Metrics

After implementation, the system should:
- ✅ Scrape 200+ flights every 6 hours
- ✅ Find 50+ accommodations per destination
- ✅ Generate 20+ trip packages daily
- ✅ Score packages with 90%+ accuracy (compared to manual assessment)
- ✅ Send daily digest with top 5 deals
- ✅ Run full pipeline in <30 minutes
- ✅ Cost <€2/day in API fees

---

## Next Steps

1. **Choose execution strategy**:
   - **Option A**: Build sequentially (safer, slower)
   - **Option B**: Parallel where possible (faster, requires coordination)
   - **Option C**: MVP first (Tasks 1.1, 1.2, 2.1, 2.5, 4.1, 4.2, 5.2)

2. **Set up development environment**:
   - Clone repo, run `docker-compose up`
   - Create `.env` file
   - Test database connection

3. **Start Phase 1** (Foundation):
   - Complete Tasks 1.1, 1.2, 1.3
   - Verify with tests

4. **Begin parallel execution of Phase 2** (Data Collection)

---

**Ready to start?** Let me know which phase to begin with, or if you want me to generate specific Claude Code prompts for any tasks!
