# SmartFamilyTravelScout

AI-powered family travel deal finder that automatically discovers and scores the best travel opportunities for families across Europe.

## Overview

SmartFamilyTravelScout combines web scraping, AI-powered analysis, and intelligent orchestration to help families find amazing travel deals. The system monitors flights, accommodations, and family-friendly events, then uses Claude AI to score and recommend the best travel packages.

### Key Features

- **No API Key Needed to Start**: Use default scrapers (Skyscanner, Ryanair, WizzAir) without configuration! 🚀
- **Intelligent Flight Discovery**: Scrapes multiple airlines (Ryanair, Wizz Air, etc.) and aggregators (Kiwi, Skyscanner)
- **Accommodation Matching**: Finds family-friendly accommodations (Booking.com, Airbnb)
- **Event Integration**: Discovers local family events and activities (Eventbrite)
- **AI-Powered Scoring**: Uses Claude AI to evaluate deal quality and family-friendliness
- **Smart Orchestration**: Celery-based task scheduling for automated deal discovery
- **Price Tracking**: Monitor prices over time and get alerts for the best deals

### 🎯 Quick Start - No Setup Required!

Want to start immediately without any API keys? Use the default scrapers:

```bash
# Install dependencies
poetry install

# Scrape flights using free scrapers (no API key needed!)
poetry run scout scrape --origin MUC --destination BCN

# Use a specific scraper
poetry run scout scrape --origin VIE --destination LIS --scraper skyscanner

# Test individual scrapers
poetry run scout test-scraper ryanair --origin MUC --dest PRG
```

**Default (free) scrapers:**
- ✅ **Skyscanner** - Web scraper (Playwright)
- ✅ **Ryanair** - Web scraper (Playwright)
- ✅ **WizzAir** - API scraper (no auth)

**Optional scrapers (require API keys):**
- Kiwi.com - Requires `KIWI_API_KEY` (100 calls/month free)
- Eventbrite - Requires `EVENTBRITE_API_KEY`

## Technology Stack

- **Backend**: Python 3.11+, FastAPI
- **Database**: PostgreSQL 15 with SQLAlchemy (async)
- **Cache/Queue**: Redis
- **Task Queue**: Celery with Celery Beat
- **Web Scraping**: Playwright, BeautifulSoup4
- **AI**: Anthropic Claude API
- **Data Processing**: Pandas
- **Container**: Docker & Docker Compose
- **Migration**: Alembic

## Project Structure

```
smartfamilytravelscout/
├── app/
│   ├── api/              # FastAPI routes and endpoints
│   ├── scrapers/         # Web scrapers for travel sites
│   ├── ai/               # Claude AI integration
│   ├── models/           # SQLAlchemy database models
│   ├── orchestration/    # Workflow orchestrators
│   ├── services/         # Business logic services
│   ├── notifications/    # Email/push notifications
│   ├── tasks/            # Celery tasks
│   ├── utils/            # Helper utilities
│   ├── cli/              # Command-line interface
│   ├── config.py         # Configuration management
│   └── database.py       # Database connections
├── tests/                # Test suites
├── docs/                 # Documentation
├── alembic/              # Database migrations
├── docker-compose.yml    # Docker services
├── Dockerfile            # Application container
└── pyproject.toml        # Dependencies
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/smartfamilytravelscout.git
   cd smartfamilytravelscout
   ```

2. **Create environment file**
   ```bash
   cp .env.example .env
   ```

3. **Configure environment variables**
   Edit `.env` and add your API keys:
   ```bash
   # Required
   ANTHROPIC_API_KEY=your_anthropic_key_here

   # Optional (for full functionality)
   KIWI_API_KEY=your_kiwi_key
   EVENTBRITE_API_KEY=your_eventbrite_key
   SMTP_USER=your_email@gmail.com
   SMTP_PASSWORD=your_app_password
   ```

4. **Start the application**
   ```bash
   docker-compose up -d
   ```

5. **Check the services**
   - API: http://localhost:8000
   - Health check: http://localhost:8000/health
   - API docs: http://localhost:8000/docs

### Development Setup (Without Docker)

1. **Install Poetry**
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. **Install dependencies**
   ```bash
   poetry install
   ```

3. **Install Playwright browsers**
   ```bash
   poetry run playwright install chromium
   ```

4. **Start PostgreSQL and Redis**
   ```bash
   docker-compose up -d postgres redis
   ```

5. **Run database migrations**
   ```bash
   poetry run alembic upgrade head
   ```

6. **Start the application**
   ```bash
   poetry run uvicorn app.api.main:app --reload
   ```

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection URL | `postgresql+asyncpg://user:pass@localhost:5432/db` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `ANTHROPIC_API_KEY` | Claude AI API key | `sk-ant-...` |
| `SECRET_KEY` | Secret key for signing | `your-secret-key-here` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `KIWI_API_KEY` | Kiwi.com API key | None |
| `EVENTBRITE_API_KEY` | Eventbrite API key | None |
| `SMTP_HOST` | SMTP server host | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP server port | `587` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `DEBUG` | Enable debug mode | `False` |

See `.env.example` for a complete list of available variables.

## Usage

### Using the CLI

```bash
# Search for deals
poetry run travelscout search --from VIE --departure-date 2024-07-15

# Check health
poetry run travelscout health

# Run scrapers manually
poetry run travelscout scrape --scraper kiwi
```

### Using the API

```bash
# Get health status
curl http://localhost:8000/health

# Search for flights
curl -X POST http://localhost:8000/api/v1/search/flights \
  -H "Content-Type: application/json" \
  -d '{"departure": "VIE", "date": "2024-07-15"}'
```

### Scheduled Tasks

Celery Beat automatically runs:
- **Daily**: Full flight scan for configured airports
- **Hourly**: Price updates for tracked deals
- **Weekly**: Event discovery and update

## Database Migrations

```bash
# Create a new migration
poetry run alembic revision --autogenerate -m "description"

# Apply migrations
poetry run alembic upgrade head

# Rollback last migration
poetry run alembic downgrade -1

# View migration history
poetry run alembic history
```

## Testing

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=app --cov-report=html

# Run specific test file
poetry run pytest tests/unit/test_scrapers.py

# Run integration tests
poetry run pytest tests/integration/
```

## Docker Services

| Service | Port | Description |
|---------|------|-------------|
| `app` | 8000 | FastAPI application |
| `postgres` | 5432 | PostgreSQL database |
| `redis` | 6379 | Redis cache & message broker |
| `celery-worker` | - | Celery task worker |
| `celery-beat` | - | Celery scheduler |

### Docker Commands

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f app

# Stop all services
docker-compose down

# Rebuild containers
docker-compose up -d --build

# Access database
docker-compose exec postgres psql -U travelscout -d travelscout

# Access Redis CLI
docker-compose exec redis redis-cli
```

## Monitoring

### Application Logs

```bash
# View all logs
docker-compose logs -f

# View app logs only
docker-compose logs -f app

# View logs directory
ls -la logs/
```

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# Database health
docker-compose exec postgres pg_isready -U travelscout

# Redis health
docker-compose exec redis redis-cli ping
```

## Development

### Code Quality

```bash
# Format code with Black
poetry run black app/

# Lint with Ruff
poetry run ruff check app/

# Type checking with mypy
poetry run mypy app/
```

### Pre-commit Hooks

```bash
# Install pre-commit hooks
poetry run pre-commit install

# Run hooks manually
poetry run pre-commit run --all-files
```

## API Documentation

Once the application is running, visit:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Troubleshooting

### Database Connection Issues

```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# Check PostgreSQL logs
docker-compose logs postgres

# Reset database
docker-compose down -v
docker-compose up -d postgres
poetry run alembic upgrade head
```

### Redis Connection Issues

```bash
# Check if Redis is running
docker-compose ps redis

# Test Redis connection
docker-compose exec redis redis-cli ping
```

### Scraper Issues

```bash
# Install Playwright dependencies
poetry run playwright install-deps

# Test scraper manually
poetry run python -c "from app.scrapers.kiwi_scraper import KiwiScraper; print('OK')"
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License - see LICENSE file for details

## Support

For issues and questions:
- Create an issue on GitHub
- Email: support@smartfamilytravelscout.com

## Roadmap

- [ ] Mobile app integration
- [ ] Multi-currency support
- [ ] ML-based price prediction
- [ ] Social sharing features
- [ ] Travel itinerary builder
- [ ] Budget optimization

## Acknowledgments

- Anthropic Claude AI for intelligent deal scoring
- FastAPI for the excellent web framework
- All the open-source libraries that make this possible
