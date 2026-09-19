# Monitoring and Metrics Collection

This module provides Prometheus-compatible metrics collection for observing operational health, scraper performance, and API consumption patterns.

## Overview

The monitoring system tracks:
- **Scraper Performance**: Request counts, durations, discovered items, and error rates
- **API Usage**: Request counts and durations for FastAPI endpoints
- **Claude AI Usage**: API calls, token consumption, costs, and response times
- **Database Operations**: Query durations and active connections
- **Trip Packages**: Creation and scoring statistics
- **Notifications**: Delivery success rates by channel

## Quick Start

### Accessing Metrics

The metrics are exposed at the `/metrics` endpoint in Prometheus exposition format:

```bash
curl http://localhost:8000/metrics
```

### Prometheus Configuration

Add this to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'smartfamilytravelscout'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
    scrape_interval: 15s
```

## Available Metrics

### Scraper Metrics

**scraper_requests_total** (Counter)
- Total number of scraper requests
- Labels: `scraper` (kiwi, skyscanner, ryanair, wizzair), `status` (success, failure)

**scraper_duration_seconds** (Histogram)
- Time spent scraping in seconds
- Labels: `scraper`
- Buckets: 0.5s, 1s, 2.5s, 5s, 10s, 30s, 60s, 120s, 300s

**flights_discovered_total** (Counter)
- Total number of flights discovered
- Labels: `scraper`, `origin`, `destination`

**accommodations_discovered_total** (Counter)
- Total number of accommodations discovered
- Labels: `scraper`, `city`

**events_discovered_total** (Counter)
- Total number of events discovered
- Labels: `scraper`, `city`

**scraping_errors_total** (Counter)
- Total number of scraping errors
- Labels: `scraper`, `error_type`

**active_scraping_jobs** (Gauge)
- Number of currently active scraping jobs
- Labels: `scraper`

### API Metrics

**api_requests_total** (Counter)
- Total number of API requests
- Labels: `endpoint`, `method`, `status`

**api_duration_seconds** (Histogram)
- Time spent processing API requests
- Labels: `endpoint`, `method`
- Buckets: 0.01s, 0.025s, 0.05s, 0.1s, 0.25s, 0.5s, 1s, 2.5s, 5s, 10s

### Claude AI Metrics

**claude_api_calls_total** (Counter)
- Total number of Claude API calls
- Labels: `model`, `analyzer`

**claude_api_tokens_total** (Counter)
- Total tokens used in Claude API calls
- Labels: `model`, `token_type` (input, output)

**claude_api_cost_total** (Counter)
- Total cost of Claude API calls in USD
- Labels: `model`

**claude_api_duration_seconds** (Histogram)
- Time spent on Claude API calls
- Labels: `model`, `analyzer`
- Buckets: 0.5s, 1s, 2s, 5s, 10s, 30s, 60s

### Database Metrics

**db_query_duration_seconds** (Histogram)
- Time spent on database queries
- Labels: `operation`
- Buckets: 0.001s to 1s

**db_connections_active** (Gauge)
- Number of active database connections

### Trip Package Metrics

**trip_packages_scored_total** (Counter)
- Total number of trip packages scored
- Labels: `score_range` (0-20, 21-40, 41-60, 61-80, 81-100)

**trip_packages_created_total** (Counter)
- Total number of trip packages created

### Notification Metrics

**notifications_sent_total** (Counter)
- Total number of notifications sent
- Labels: `channel` (email, slack), `status` (success, failure)

## Usage Examples

### Automatic Tracking with Decorators

The `@track_scraper_metrics` decorator automatically tracks scraping operations:

```python
from app.monitoring.decorators import track_scraper_metrics

@track_scraper_metrics('kiwi')
async def scrape_flights(origin, destination, date_from, date_to):
    # Your scraping logic here
    flights = await kiwi_api.search(...)
    return flights
```

This automatically tracks:
- Active jobs (incremented at start, decremented at end)
- Request duration
- Success/failure status
- Discovered items (if result is a list)
- Error types (if exception occurs)

### Manual Metrics Tracking

For more control, you can track metrics manually:

```python
from app.monitoring.metrics import (
    scraper_requests_total,
    scraper_duration_seconds,
    flights_discovered_total,
)
import time

async def custom_scraper(origin, destination):
    start_time = time.time()

    try:
        flights = await scrape_data(origin, destination)

        # Track discovered flights
        flights_discovered_total.labels(
            scraper='custom',
            origin=origin,
            destination=destination
        ).inc(len(flights))

        # Track success
        scraper_requests_total.labels(
            scraper='custom',
            status='success'
        ).inc()

        return flights

    except Exception as e:
        # Track failure
        scraper_requests_total.labels(
            scraper='custom',
            status='failure'
        ).inc()
        raise

    finally:
        # Track duration
        duration = time.time() - start_time
        scraper_duration_seconds.labels(scraper='custom').observe(duration)
```

## Integration Points

### Already Integrated

The following components have metrics tracking enabled:

1. **FlightOrchestrator** (`app/orchestration/flight_orchestrator.py`)
   - Tracks all scraper operations (Kiwi, Skyscanner, Ryanair, WizzAir)
   - Monitors discovered flights, errors, and durations

2. **ClaudeClient** (`app/ai/claude_client.py`)
   - Tracks all Claude API calls
   - Monitors token usage and costs
   - Records response times

3. **FastAPI Metrics Endpoint** (`app/api/main.py`)
   - Exposes `/metrics` endpoint for Prometheus scraping

### Adding Metrics to New Components

To add metrics to a new scraper:

```python
from app.monitoring.decorators import track_scraper_metrics

class MyNewScraper:
    @track_scraper_metrics('mynew')
    async def scrape_flights(self, origin, destination):
        # Your implementation
        pass
```

To track custom events:

```python
from app.monitoring.metrics import trip_packages_created_total

def create_trip_package(flights, accommodations):
    package = TripPackage(...)
    trip_packages_created_total.inc()
    return package
```

## Prometheus Queries

Example queries for alerting and dashboards:

```promql
# Scraper success rate (last 5 minutes)
rate(scraper_requests_total{status="success"}[5m])
/
rate(scraper_requests_total[5m])

# Average scraping duration by scraper
rate(scraper_duration_seconds_sum[5m])
/
rate(scraper_duration_seconds_count[5m])

# Flights discovered per minute
rate(flights_discovered_total[1m])

# Claude API cost per hour
increase(claude_api_cost_total[1h])

# Active scraping jobs
sum(active_scraping_jobs)

# 95th percentile API response time
histogram_quantile(0.95, rate(api_duration_seconds_bucket[5m]))
```

## Grafana Dashboard

Key metrics to visualize:

1. **Scraper Health Panel**: Success rate by scraper (gauge)
2. **Scraping Performance**: Duration histogram by scraper (heatmap)
3. **Discovery Rate**: Flights/accommodations/events discovered over time (graph)
4. **Error Tracking**: Error rate by type (stacked graph)
5. **Claude AI Usage**: Tokens consumed and costs (counter)
6. **Active Jobs**: Current active scraping jobs (gauge)

## Troubleshooting

### Metrics Not Appearing

1. Check that the `/metrics` endpoint is accessible:
   ```bash
   curl http://localhost:8000/metrics
   ```

2. Verify Prometheus is scraping the endpoint:
   ```bash
   curl http://localhost:9090/api/v1/targets
   ```

3. Check application logs for import errors:
   ```bash
   poetry run uvicorn app.api.main:app --log-level debug
   ```

### High Cardinality Warning

If you see high cardinality warnings in Prometheus:
- Review label usage (especially `origin`, `destination`, `city`)
- Consider aggregating less-frequently used routes
- Use recording rules to pre-aggregate metrics

## Performance Impact

The monitoring system has minimal performance impact:
- Metric collection: < 1ms overhead per operation
- Memory usage: ~10KB per unique label combination
- No blocking I/O operations
- Metrics are stored in-memory and scraped by Prometheus

## Future Enhancements

Planned features:
- [ ] Add tracing with OpenTelemetry
- [ ] Implement custom metrics for business KPIs
- [ ] Add alerting rules configuration
- [ ] Create pre-built Grafana dashboard JSON
- [ ] Add metrics for database connection pool
