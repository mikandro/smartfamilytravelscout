# SmartFamilyTravelScout CLI Documentation

Professional command-line interface for the SmartFamilyTravelScout application.

## Installation

After installing dependencies with Poetry:

```bash
poetry install
poetry shell
```

The `scout` command will be available globally within the Poetry shell.

## Available Commands

### Main Pipeline

#### `scout run`

Run the full SmartFamilyTravelScout pipeline including flight scraping, accommodation matching, event discovery, AI analysis, and notifications.

**Options:**
- `--destinations, -d` - Destinations to search (comma-separated IATA codes or 'all'). Default: "all"
- `--dates` - Date range: 'next-3-months', 'next-6-months', or specific dates. Default: "next-3-months"
- `--analyze/--no-analyze` - Run AI analysis on results. Default: True
- `--max-price` - Maximum price per person in EUR

**Examples:**
```bash
# Run with default settings
scout run

# Search specific destinations
scout run --destinations LIS,BCN,PRG --dates next-3-months

# Limit price and skip analysis
scout run --max-price 150 --no-analyze

# Search all destinations for next 6 months
scout run --destinations all --dates next-6-months
```

**Pipeline Steps:**
1. Load origin and destination airports
2. Calculate date ranges based on school holidays
3. Scrape flights from Kiwi, Skyscanner, Ryanair, WizzAir
4. Query available accommodations
5. Generate trip packages by matching flights + accommodations
6. Match events to packages by date and destination
7. Run AI analysis and scoring (optional)
8. Display statistics

---

### View Deals

#### `scout deals`

Show top travel deals based on AI scoring with Rich table formatting.

**Options:**
- `--min-score` - Minimum AI score (0-100). Default: 70
- `--destination, -d` - Filter by destination city
- `--limit, -n` - Number of deals to show. Default: 10
- `--type, -t` - Package type: 'family' or 'parent_escape'
- `--format, -f` - Output format: 'table' or 'json'. Default: 'table'

**Examples:**
```bash
# Show top 10 deals with score >= 70
scout deals

# Show top 20 high-scoring deals
scout deals --min-score 80 --limit 20

# Filter by destination
scout deals --destination lisbon --type family

# JSON output for programmatic use
scout deals --format json

# Family packages only
scout deals --type family --min-score 75
```

**Table Output:**
- Destination city
- Departure and return dates
- Number of nights
- Total price and price per person
- AI score with color coding (green for 80+, yellow otherwise)
- Package type (family/parent_escape)

---

### Configuration Management

#### `scout config show`

Display current configuration without sensitive data.

**Example:**
```bash
scout config show
```

Shows application settings, travel parameters, and feature flags.

#### `scout config get`

Get a specific configuration value.

**Example:**
```bash
scout config get max_flight_price_per_person
scout config get timezone
```

#### `scout config set`

Set a configuration value in .env file.

**Example:**
```bash
scout config set max_flight_price_per_person 250
scout config set enable_ai_scoring true
```

**Note:** Restart the application for changes to take effect.

---

### Scraper Testing

#### `scout test-scraper`

Test individual scrapers with sample queries.

**Arguments:**
- `scraper` - Scraper name: 'kiwi', 'skyscanner', 'ryanair', 'wizzair', 'booking'

**Options:**
- `--origin, -o` - Origin airport IATA code. Default: "MUC"
- `--dest, -d` - Destination airport IATA code. Default: "LIS"
- `--save/--no-save` - Save results to database. Default: False

**Examples:**
```bash
# Test Kiwi scraper
scout test-scraper kiwi --origin MUC --dest LIS

# Test Ryanair and save results
scout test-scraper ryanair --origin VIE --dest BCN --save

# Test Skyscanner
scout test-scraper skyscanner --origin NUE --dest PRG

# Test WizzAir
scout test-scraper wizzair
```

---

### Statistics

#### `scout stats`

Show statistics about scraped data and system usage.

**Options:**
- `--period, -p` - Time period: 'day', 'week', 'month', 'all'. Default: 'week'
- `--scraper, -s` - Filter by scraper source

**Examples:**
```bash
# Show weekly stats
scout stats

# Show monthly stats
scout stats --period month

# Show all-time stats
scout stats --period all

# Filter by scraper
scout stats --scraper kiwi --period month
```

**Displays:**
- Number of flights, accommodations, events, packages
- Number of scraping jobs
- Claude API usage costs

---

### Database Management

#### `scout db init`

Initialize database (create all tables).

**Warning:** Only use in development! In production, use Alembic migrations.

**Example:**
```bash
scout db init
```

Prompts for confirmation before creating tables.

#### `scout db seed`

Seed database with sample data for testing (airports, sample records).

**Example:**
```bash
scout db seed
```

#### `scout db reset`

Reset database (drop all tables and recreate).

**Warning:** This will DELETE ALL DATA!

**Example:**
```bash
scout db reset
```

Requires double confirmation due to destructive nature.

---

### Health Check

#### `scout health`

Check application health status.

**Example:**
```bash
scout health
```

**Checks:**
- Database connection (PostgreSQL)
- Configuration loaded
- Anthropic API key configured
- Kiwi API key configured

Exit code 1 if database connection fails.

---

### Flight Search (Kiwi)

#### `scout kiwi-search`

Search for flights using Kiwi.com API.

**Options:**
- `--origin, -o` - Origin airport IATA code (required)
- `--destination, -d` - Destination airport IATA code (omit for 'anywhere' search)
- `--departure` - Departure date (YYYY-MM-DD). Default: 60 days from today
- `--return` - Return date (YYYY-MM-DD). Default: 7 days after departure
- `--adults` - Number of adults. Default: 2
- `--children` - Number of children. Default: 2
- `--save/--no-save` - Save results to database. Default: True

**Examples:**
```bash
# Search specific route
scout kiwi-search --origin MUC --destination LIS

# Search anywhere from origin
scout kiwi-search --origin MUC

# Custom dates and passengers
scout kiwi-search --origin MUC --destination BCN --departure 2025-12-20 --return 2025-12-27 --adults 2 --children 1

# Don't save to database
scout kiwi-search --origin VIE --destination PRG --no-save
```

#### `scout kiwi-status`

Check Kiwi.com API rate limit status.

**Example:**
```bash
scout kiwi-status
```

Shows API calls used, remaining, and usage percentage.

---

### Worker Management

#### `scout worker`

Start Celery worker for background tasks.

**Example:**
```bash
scout worker
```

#### `scout beat`

Start Celery beat scheduler for periodic tasks.

**Example:**
```bash
scout beat
```

---

## General Options

### Version

```bash
scout --version
scout -v
```

Shows application name and version.

### Help

```bash
scout --help
scout COMMAND --help
```

Show help for any command.

---

## Error Handling

The CLI includes comprehensive error handling:

- **Database errors**: Clear error messages with connection troubleshooting
- **API errors**: Graceful handling of rate limits and authentication issues
- **Validation errors**: User-friendly messages for invalid inputs
- **Debug mode**: Use `DEBUG=true` in .env for detailed stack traces

---

## Rich Formatting Features

The CLI uses Rich library for professional output:

- **Tables**: Formatted data with color-coded columns
- **Progress bars**: Real-time progress tracking for long operations
- **Panels**: Highlighted information boxes
- **Colors**: Syntax highlighting and status indicators
  - Green: Success, healthy status
  - Yellow: Warnings, pending operations
  - Red: Errors, unhealthy status
  - Cyan: Information, data values
  - Magenta: Headers, scores

---

## Environment Variables

Key environment variables (see `.env.example`):

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/scout

# Redis
REDIS_URL=redis://localhost:6379/0

# API Keys
ANTHROPIC_API_KEY=sk-ant-...
KIWI_API_KEY=...

# Configuration
MAX_FLIGHT_PRICE_PER_PERSON=200.0
MAX_ACCOMMODATION_PRICE_PER_NIGHT=150.0
ENABLE_AI_SCORING=true
ENABLE_SCRAPING=true
```

---

## Workflow Examples

### Daily Deal Discovery

```bash
# Morning: Run full pipeline
scout run --destinations all --dates next-3-months

# View top deals
scout deals --min-score 80 --limit 20

# Check system stats
scout stats --period day
```

### Manual Flight Research

```bash
# Test different routes
scout test-scraper kiwi --origin MUC --dest LIS --save
scout test-scraper kiwi --origin MUC --dest BCN --save
scout test-scraper kiwi --origin MUC --dest PRG --save

# View deals
scout deals --min-score 70
```

### Configuration Tuning

```bash
# Check current settings
scout config show

# Adjust price thresholds
scout config set max_flight_price_per_person 250
scout config set max_accommodation_price_per_night 180

# Verify changes
scout config get max_flight_price_per_person
```

### Database Maintenance

```bash
# Initial setup
scout db init
scout db seed

# Check health
scout health

# View stats
scout stats --period all

# Reset if needed (development only)
scout db reset
```

---

## Performance Tips

1. **Use specific destinations** instead of "all" for faster execution
2. **Limit date ranges** to next-3-months for quicker scraping
3. **Skip AI analysis** (`--no-analyze`) when testing scrapers
4. **Filter deals** by destination and type for faster queries
5. **Use JSON output** (`--format json`) for programmatic processing

---

## Troubleshooting

### Database Connection Failed

```bash
# Check database status
scout health

# Verify DATABASE_URL in .env
scout config get database_url

# Test connection
psql $DATABASE_URL -c "SELECT 1"
```

### API Rate Limit Exceeded

```bash
# Check Kiwi status
scout kiwi-status

# Use test-scraper for single queries
scout test-scraper kiwi --origin MUC --dest LIS
```

### No Deals Found

```bash
# Check if data exists
scout stats --period all

# Lower minimum score
scout deals --min-score 50

# Run pipeline first
scout run
```

---

## Advanced Usage

### Chaining Commands

```bash
# Initialize, seed, and run pipeline
scout db init && scout db seed && scout run

# Run pipeline and view top deals
scout run && scout deals --min-score 80
```

### Scripting

```bash
#!/bin/bash
# daily_scout.sh

# Run pipeline
scout run --destinations LIS,BCN,PRG --dates next-3-months

# Export top deals to JSON
scout deals --min-score 80 --limit 50 --format json > deals.json

# Send stats email
scout stats --period day | mail -s "Daily Scout Stats" admin@example.com
```

### Cron Jobs

```bash
# Run daily at 6 AM
0 6 * * * cd /path/to/smartfamilytravelscout && poetry run scout run

# Weekly stats report on Mondays at 9 AM
0 9 * * 1 cd /path/to/smartfamilytravelscout && poetry run scout stats --period week
```

---

## Exit Codes

- `0` - Success
- `1` - Error (database connection, API failure, validation error, etc.)

Use exit codes in scripts:

```bash
if scout health; then
    scout run
else
    echo "Health check failed, skipping run"
fi
```

---

## Support

For issues or questions:

1. Check `scout COMMAND --help`
2. Review environment variables in `.env`
3. Check logs in `logs/` directory
4. Run `scout health` to diagnose system status
5. Enable debug mode: `DEBUG=true scout COMMAND`

---

## Command Summary

| Command | Description |
|---------|-------------|
| `scout run` | Run full pipeline |
| `scout deals` | View top deals |
| `scout config show` | Display configuration |
| `scout config get KEY` | Get config value |
| `scout config set KEY VALUE` | Set config value |
| `scout test-scraper SCRAPER` | Test individual scraper |
| `scout stats` | Show statistics |
| `scout db init` | Initialize database |
| `scout db seed` | Seed database |
| `scout db reset` | Reset database |
| `scout health` | Health check |
| `scout kiwi-search` | Search Kiwi flights |
| `scout kiwi-status` | Kiwi API status |
| `scout worker` | Start Celery worker |
| `scout beat` | Start Celery beat |
| `scout --version` | Show version |
| `scout --help` | Show help |
