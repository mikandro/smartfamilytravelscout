# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SmartFamilyTravelScout is an AI-powered family travel deal finder that scrapes flights, accommodations, and events from multiple sources, then uses Claude AI to score and recommend the best travel packages for families.

**Tech Stack**: Python 3.11+, FastAPI, PostgreSQL, Redis, Celery, Playwright, SQLAlchemy (async), Anthropic Claude API

## Quick Start (No API Key Needed!)

You can start scraping flights immediately using the default scrapers (Skyscanner, Ryanair, WizzAir) without any API keys:

```bash
# Quick scrape with all free scrapers
poetry run scout scrape --origin MUC --destination BCN

# Use a specific scraper
poetry run scout scrape --origin VIE --destination LIS --scraper skyscanner

# Test individual scrapers
poetry run scout test-scraper ryanair --origin MUC --dest PRG
```

The default scrapers work out of the box - no configuration needed!

<<<<<<< HEAD
## Controlling Scrapers

You can enable or disable specific scrapers both via configuration and at runtime:

### Configuration-based Control (Persistent)

Set environment variables in your `.env` file:

```bash
# Enable/disable specific scrapers (default: all enabled)
USE_KIWI_SCRAPER=false        # Disable Kiwi.com (requires API key anyway)
USE_SKYSCANNER_SCRAPER=true   # Enable Skyscanner (free)
USE_RYANAIR_SCRAPER=true      # Enable Ryanair (free)
USE_WIZZAIR_SCRAPER=false     # Disable WizzAir

# Or use CLI
poetry run scout config set use_wizzair_scraper false
```

### Runtime Control (Temporary)

Override configuration for a single command:

```bash
# Disable specific scrapers for this run only
poetry run scout scrape --origin MUC --destination LIS --disable-scraper wizzair

# Disable multiple scrapers
poetry run scout run --disable-scraper wizzair --disable-scraper ryanair

# Enable a normally-disabled scraper (if you have API key)
poetry run scout scrape --origin MUC --destination BCN --enable-scraper kiwi

# Mix enable and disable
poetry run scout run --enable-scraper kiwi --disable-scraper skyscanner
```

### Check Scraper Status

```bash
# View which scrapers are currently enabled
poetry run scout config show
```

This feature is useful when:
- A scraper is temporarily broken or rate-limited
- You want to test specific scrapers in isolation
- You need to reduce scraping time by using fewer sources
- You want to avoid API costs from premium scrapers
=======
## CLI Command Structure

SmartFamilyTravelScout uses a clear, hierarchical command structure:

**Primary Commands:**
- `scout scrape` - Quick flight searches (supports all scrapers: skyscanner, ryanair, wizzair, kiwi)
- `scout pipeline` - Complete end-to-end travel search pipeline (scrape → match → score → notify)
- `scout deals` - View top AI-scored travel deals (high-value recommendations, score >= 70)
- `scout packages` - View all trip packages (broader results, includes unscored packages)
- `scout stats` - View system statistics and scraping history
- `scout health` - Check application health and configuration

**Deprecated Commands (backward compatibility, will be removed in future versions):**
- `scout run` → Use `scout pipeline` instead
- `scout kiwi-search` → Use `scout scrape --scraper kiwi` instead

**Command Philosophy:**
- `scrape` = quick manual searches for specific routes
- `pipeline` = automated full-stack deal discovery
- `deals` = BEST packages (AI-vetted, high scores)
- `packages` = ALL packages (complete view, includes pending AI analysis)
>>>>>>> origin/main

## Development Commands

### Setup & Installation

```bash
# Install dependencies
poetry install

# Install Playwright browsers
poetry run playwright install chromium

# Start infrastructure (PostgreSQL + Redis)
docker-compose up -d postgres redis

# Run database migrations
poetry run alembic upgrade head

# Seed database with airports and sample data
poetry run scout db seed
```

### Running the Application

```bash
# Start FastAPI server (development)
poetry run uvicorn app.api.main:app --reload

# Start with Docker Compose (all services)
docker-compose up -d

# CLI commands (using 'scout')
poetry run scout health          # Check system health
poetry run scout scrape --origin MUC --destination LIS  # Quick scrape (no API key needed!)
poetry run scout scrape-accommodations --city Barcelona  # Scrape accommodations
poetry run scout pipeline        # Run complete end-to-end pipeline
poetry run scout deals           # View top AI-scored deals (score >= 70)
poetry run scout packages        # View all trip packages
poetry run scout stats           # Show statistics

# Quick start with default (free) scrapers - NO API KEY NEEDED:
poetry run scout scrape --origin MUC --destination BCN
poetry run scout scrape --origin VIE --destination LIS --scraper skyscanner
poetry run scout scrape --origin MUC --destination PRG --scraper kiwi  # Requires KIWI_API_KEY
poetry run scout test-scraper skyscanner --origin MUC --dest PRG

# Accommodation scraping:
poetry run scout scrape-accommodations --city Lisbon
poetry run scout scrape-accommodations --city Barcelona --check-in 2025-07-01 --check-out 2025-07-08
poetry run scout test-scraper booking --dest Barcelona
poetry run scout test-scraper airbnb --dest Lisbon
```

### Testing

```bash
# Run all tests
poetry run pytest

# Run with coverage report
poetry run pytest --cov=app --cov-report=html

# Run specific test file
poetry run pytest tests/unit/test_scrapers.py

# Run only unit tests (fast, mocked)
poetry run pytest -m unit

# Run only integration tests (slow, real browsers)
poetry run pytest -m integration
```

### Database Operations

```bash
# Create a new migration
poetry run alembic revision --autogenerate -m "description"

# Apply migrations
poetry run alembic upgrade head

# Rollback one migration
poetry run alembic downgrade -1

# View migration history
poetry run alembic history

# Reset database (WARNING: deletes all data)
poetry run scout db reset
```

### Celery Workers

```bash
# Start worker
celery -A app.tasks.celery_app worker --loglevel=info

# Start beat scheduler
celery -A app.tasks.celery_app beat --loglevel=info

# Or use CLI shortcuts
poetry run scout worker
poetry run scout beat
```

### Code Quality

```bash
# Format code
poetry run black app/

# Lint code
poetry run ruff check app/

# Type checking
poetry run mypy app/

# Pre-commit hooks (run automatically on git commit)
poetry run pre-commit install          # Install hooks (one-time setup)
poetry run pre-commit run --all-files  # Run manually on all files
poetry run pre-commit run              # Run on staged files only

# Security scanning
poetry run bandit -r app/
```

**Pre-commit Hook Enforcement:**
- All TODOs must reference a GitHub issue: `# TODO(#123): description`
- Code is auto-formatted with Black and Ruff
- Security vulnerabilities are detected with Bandit
- YAML/JSON/TOML files are validated
- Trailing whitespace and line endings are fixed

## Architecture Overview

### Core Components

**Scrapers** (`app/scrapers/`): Web scrapers for multiple data sources

**Default Scrapers (NO API KEY NEEDED):**
- `skyscanner_scraper.py`: Skyscanner web scraper (Playwright) ✓ FREE
- `ryanair_scraper.py`: Ryanair web scraper (Playwright) ✓ FREE
- `wizzair_scraper.py`: WizzAir API scraper (unofficial API) ✓ FREE

**API-Key Scrapers:**
- `kiwi_scraper.py`: Kiwi.com API client (requires KIWI_API_KEY - 100 calls/month free tier)
- `eventbrite_scraper.py`: Eventbrite API client (requires EVENTBRITE_API_KEY)

**Accommodation Scrapers:**
- `booking_scraper.py`: Booking.com scraper (accommodations)
- `airbnb_scraper.py`: Airbnb scraper (accommodations)

**Tourism Scrapers:**
- Tourism scrapers: Barcelona, Prague, Lisbon city events

**Orchestration** (`app/orchestration/`): Coordinates multiple scrapers and data sources
- `flight_orchestrator.py`: Runs all flight scrapers in parallel, deduplicates results, tracks failures
  - **Failure Threshold**: Raises `ScraperFailureThresholdExceeded` if >50% (configurable) of scrapers fail
  - Prevents silent failures that mask critical system issues
- `accommodation_orchestrator.py`: Runs all accommodation scrapers in parallel, deduplicates results
- `accommodation_matcher.py`: Matches accommodations to flights, generates trip packages
- `event_matcher.py`: Matches local events to trip packages

**AI Integration** (`app/ai/`): Claude API integration for intelligent analysis
- `claude_client.py`: Anthropic API client wrapper
- `deal_scorer.py`: Scores trip packages (0-100) based on value, family-friendliness
- `event_scorer.py`: Scores events for family relevance
- `itinerary_generator.py`: Generates day-by-day trip itineraries
- `parent_escape_analyzer.py`: Analyzes destinations for parents-only trips
- `prompt_loader.py`: Loads prompt templates from `app/ai/prompts/`

**Models** (`app/models/`): SQLAlchemy ORM models (all async-capable)
- Core entities: `Airport`, `Flight`, `Accommodation`, `Event`, `TripPackage`
- Supporting: `SchoolHoliday`, `PriceHistory`, `ScrapingJob`, `UserPreference`, `ApiCost`

**Tasks** (`app/tasks/`): Celery background tasks
- `celery_app.py`: Celery configuration and beat schedule
- `scheduled_tasks.py`: Periodic tasks (daily flights, hourly prices, weekly events)

**API** (`app/api/`): FastAPI REST endpoints
- `main.py`: FastAPI app with lifespan management
- `routes/web.py`: Web dashboard routes (HTML/Jinja2)
- `routes/v1/`: API v1 endpoints (JSON REST API)
  - `version.py`: API version information
  - `health.py`: Health check endpoints
  - `deals.py`: Deal listing and details
  - `stats.py`: Statistics endpoints
- **API Versioning**: URL-based versioning (`/api/v1/...`). See `docs/API_VERSIONING.md`

**Notifications** (`app/notifications/`): Email notifications
- `email_sender.py`: SMTP email sender with HTML templates
- `email_preview.py`: Preview emails locally
- `smtp_config.py`: SMTP configuration

### Data Flow

1. **Scraping**: Celery beat triggers scheduled tasks → Orchestrators run scrapers in parallel → Raw data saved to database
2. **Package Generation**: `AccommodationMatcher` combines flights + accommodations → `EventMatcher` adds local events → Trip packages created
3. **AI Scoring**: `DealScorer` evaluates each package using Claude API → Scores and reasoning saved to database
4. **Notifications**: High-scoring packages trigger email notifications to users

### Database Architecture

**Connection Management**:
- Async engine (`asyncpg`) for FastAPI routes
- Sync engine (`psycopg2`) for Celery tasks and CLI
- Both use `app.database` module: `get_async_session()`, `get_sync_session()`, `get_async_session_context()`

**Key Relationships**:
- `Airport` → `Flight` (origin/destination, CASCADE delete)
- `Accommodation` → `TripPackage` (SET NULL delete)
- `TripPackage` stores JSONB for: `flights_json`, `events_json`, `itinerary_json`

**Critical Indexes**: All queries filter by: `ai_score`, `departure_date`, `destination_city`, `source`, `scraped_at`

### AI Prompt System

Prompts are stored as `.txt` files in `app/ai/prompts/`:
- `deal_analysis.txt`: Analyzes trip packages for value and family-friendliness
- `event_scoring.txt`: Scores events for families with kids
- `itinerary_generation.txt`: Creates day-by-day trip plans
- `parent_escape_analysis.txt`: Evaluates parent-only trip potential
- `parent_escape_destination.txt`: Analyzes wine regions for romantic getaways

Use `PromptLoader` to load templates: `load_prompt("deal_analysis")`

### Configuration

All settings use Pydantic Settings in `app/config.py`:
- Required: `DATABASE_URL`, `REDIS_URL`, `ANTHROPIC_API_KEY`, `SECRET_KEY`
- Optional: `KIWI_API_KEY`, `EVENTBRITE_API_KEY`, SMTP config, feature flags
- Scraper settings:
  - `SCRAPER_FAILURE_THRESHOLD` (default: 0.5 = 50%): Maximum allowed scraper failure rate before aborting
  - Set to 0.0 to abort on any failure, 1.0 to never abort
- Access via: `from app.config import settings`

## Important Implementation Details

### Async/Sync Pattern

**Always use async in FastAPI routes**:
```python
from app.database import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession

async def route(db: AsyncSession = Depends(get_async_session)):
    result = await db.execute(select(Flight))
```

**Use sync in Celery tasks and CLI**:
```python
from app.database import get_sync_session

def celery_task():
    db = get_sync_session()
    try:
        flights = db.query(Flight).all()
        db.commit()
    finally:
        db.close()
```

### Scraper Design Pattern

All scrapers follow this pattern:
1. Inherit from base or implement `scrape_flights()` / `scrape_accommodations()`
2. Return list of dicts with standardized fields
3. Handle retries with `@retry` decorator from `app.utils.retry`
4. **Exception Handling**: Log errors and re-raise exceptions (orchestrator handles failure tracking)
   - The `FlightOrchestrator` tracks failures via `asyncio.gather(..., return_exceptions=True)`
   - Raises `ScraperFailureThresholdExceeded` if failure rate exceeds configured threshold
5. Track scraping job status in `scraping_jobs` table

### TODO Policy

All TODO comments must reference a GitHub issue to prevent technical debt accumulation:

**Format:** `# TODO(#123): Brief description of what needs to be done`

**Example:**
```python
# TODO(#59): Implement price update logic
# tracked_flights = get_tracked_flights()
```

**Enforcement:**
- Pre-commit hooks automatically reject TODOs without issue references
- This ensures all incomplete features are tracked and prioritized
- Obsolete TODOs should be removed, not left in code

### Exception Handling

**Custom Exceptions** (`app/exceptions.py`):
- `ScraperFailureThresholdExceeded`: Raised when too many scrapers fail during orchestration
  - Contains failure statistics: `total_scrapers`, `failed_scrapers`, `failure_rate`, `threshold`
  - Signals critical system issues requiring immediate attention
- `ScraperException`: Base exception for scraper-related errors
- Other domain-specific exceptions: `ConfigurationException`, `DatabaseException`, `AIServiceException`

### Cost Tracking

All Claude API calls are tracked in `api_cost` table via `app.utils.cost_calculator`:
```python
from app.utils.cost_calculator import track_api_cost

await track_api_cost(
    service="claude",
    model="claude-3-5-sonnet-20241022",
    input_tokens=1000,
    output_tokens=500
)
```

### True Cost Calculation

Flights have `price_per_person` AND `true_cost` which includes:
- Flight price × 4 people
- Airport parking (days × parking_cost_per_day)
- Driving distance cost
- Formula in `app/utils/cost_calculator.py:calculate_true_cost()`

### School Holiday Integration

Trip searches prioritize school holiday periods from `school_holidays` table:
- Bavaria school calendar seeded via `app/utils/seed_data.py`
- Use `app/utils/date_utils.get_school_holiday_periods()` to get date ranges
- Flights/packages automatically filtered to holiday windows

## Common Development Tasks

### Adding a New Scraper

1. Create `app/scrapers/newsource_scraper.py`
2. Implement `scrape_flights()` or `scrape_accommodations()` returning standardized dicts
3. Add to `FlightOrchestrator` or create new orchestrator
4. Add Celery task in `app/tasks/scheduled_tasks.py`
5. Add test in `tests/unit/test_newsource_scraper.py`

### Adding a New AI Analyzer

1. Create prompt in `app/ai/prompts/new_analyzer.txt`
2. Create analyzer class in `app/ai/new_analyzer.py`
3. Use `ClaudeClient` from `app/ai/claude_client.py`
4. Track costs with `track_api_cost()`
5. Add example in `examples/new_analyzer_example.py`

### Debugging Scrapers

```bash
# Test individual scraper
poetry run scout test-scraper kiwi --origin MUC --dest LIS

# Run scraper example directly
poetry run python examples/kiwi_scraper_example.py

# Check scraping job history
poetry run scout stats --scraper kiwi
```

### Working with Migrations

When modifying models:
1. Make changes to model classes in `app/models/`
2. Generate migration: `poetry run alembic revision --autogenerate -m "description"`
3. Review generated migration in `alembic/versions/`
4. Apply: `poetry run alembic upgrade head`
5. If issues, rollback: `poetry run alembic downgrade -1`

## Testing Guidelines

- **Unit tests** (`tests/unit/`): Mock external services, fast, no browser/network
- **Integration tests** (`tests/integration/`): Real browsers, real network, mark with `@pytest.mark.integration`
- **Fixtures**: Database fixtures in `tests/conftest.py`, data fixtures in `tests/fixtures/`
- Use `pytest-asyncio` for async tests
- Mock scrapers to avoid rate limits: `from unittest.mock import AsyncMock, patch`

## Deployment Notes

### Docker Compose Services

- `postgres`: PostgreSQL 15, port 5432
- `redis`: Redis 7, port 6379
- `app`: FastAPI application, port 8000
- `celery-worker`: Background task worker
- `celery-beat`: Scheduled task scheduler

### Environment Variables

Copy `.env.example` to `.env` and configure:
- `ANTHROPIC_API_KEY`: Required for AI features
- `KIWI_API_KEY`: Optional, for Kiwi.com scraper
- `EVENTBRITE_API_KEY`: Optional, for Eventbrite events
- SMTP settings: For email notifications

### Monitoring

- View logs: `docker-compose logs -f app`
- Check health: `curl http://localhost:8000/health`
- API docs: `http://localhost:8000/docs`
- Celery flower (if enabled): Task monitoring dashboard

## Troubleshooting

**Database connection issues**: Ensure PostgreSQL is running (`docker-compose ps postgres`)

**Playwright errors**: Run `poetry run playwright install chromium` and `poetry run playwright install-deps`

**Celery tasks not running**: Check Redis connection and ensure beat scheduler is running

**API rate limits**: Check `poetry run scout kiwi-status` for Kiwi API limits

**Migration conflicts**: Use `poetry run alembic history` and `poetry run alembic current` to debug
