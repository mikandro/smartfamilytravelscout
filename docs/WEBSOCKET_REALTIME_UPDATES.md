# WebSocket Real-Time Updates

This document describes the WebSocket implementation for real-time scraping job updates in SmartFamilyTravelScout.

## Overview

The WebSocket feature provides real-time updates during scraping operations, eliminating the need for API polling and providing instant feedback to users about:

- Scraping job progress
- Individual scraper status (started, completed, failed)
- Real-time results count
- Error notifications
- Job completion status

## Architecture

### Components

1. **WebSocket Manager** (`app/websocket/manager.py`)
   - Manages WebSocket connections
   - Handles Redis pub/sub for multi-worker coordination
   - Broadcasts events to connected clients

2. **Event Definitions** (`app/websocket/events.py`)
   - `ScrapingEvent`: Data model for all events
   - `ScrapingEventType`: Enum of event types

3. **Progress Tracker** (`app/utils/progress_tracker.py`)
   - Helper functions for emitting events
   - Used by orchestrators and scrapers

4. **WebSocket Routes** (`app/api/routes/websocket.py`)
   - `/ws/scraping/{job_id}`: WebSocket endpoint
   - `/ws/scraping/{job_id}/status`: HTTP polling endpoint (fallback)
   - `/ws/stats`: WebSocket connection statistics

### Event Flow

```
┌─────────────────┐
│ Scraping Job    │
│ Starts          │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│ FlightOrchestra │─────▶│ Progress        │─────▶│ WebSocket       │
│ tor emits event │      │ Tracker         │      │ Manager         │
└─────────────────┘      └─────────────────┘      └────────┬────────┘
                                                            │
                                                            ▼
                                                   ┌─────────────────┐
                                                   │ Redis Pub/Sub   │
                                                   │ (scraping_      │
                                                   │  events)        │
                                                   └────────┬────────┘
                                                            │
                                                            ▼
                                                   ┌─────────────────┐
                                                   │ All connected   │
                                                   │ WebSocket       │
                                                   │ clients receive │
                                                   │ event           │
                                                   └─────────────────┘
```

## Event Types

### Job Events

- **`job_started`**: Scraping job has begun
- **`job_progress`**: Progress update (includes percentage and results count)
- **`job_completed`**: Job finished successfully
- **`job_failed`**: Job failed with error

### Scraper Events

- **`scraper_started`**: Individual scraper (e.g., Skyscanner) started
- **`scraper_completed`**: Individual scraper finished
- **`scraper_failed`**: Individual scraper failed

### Results Events

- **`results_updated`**: Results count updated

## Event Schema

All events follow this JSON structure:

```json
{
  "job_id": 123,
  "event_type": "job_progress",
  "status": "running",
  "progress": 45.5,
  "results_count": 42,
  "message": "Scraping in progress...",
  "metadata": {
    "successful_scrapers": 3,
    "failed_scrapers": 1,
    "total_flights": 42
  },
  "timestamp": "2025-11-21T10:30:00"
}
```

### Fields

- **`job_id`** (int): ID of the scraping job
- **`event_type`** (string): Type of event (see Event Types)
- **`status`** (string): Current job status (`running`, `completed`, `failed`)
- **`progress`** (float, nullable): Progress percentage (0-100)
- **`results_count`** (int): Number of items scraped so far
- **`message`** (string, nullable): Human-readable message
- **`metadata`** (object): Additional event-specific data
- **`timestamp`** (string): ISO 8601 timestamp

## Usage

### WebSocket Endpoint

**Endpoint:** `ws://localhost:8000/ws/scraping/{job_id}`

#### JavaScript Example

```javascript
const jobId = 123;
const ws = new WebSocket(`ws://localhost:8000/ws/scraping/${jobId}`);

ws.onopen = () => {
  console.log('Connected to scraping job', jobId);
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  console.log(`[${data.event_type}] ${data.message}`);
  console.log(`Progress: ${data.progress}%`);
  console.log(`Results: ${data.results_count}`);

  // Update UI
  updateProgressBar(data.progress);
  updateResultsCount(data.results_count);

  // Handle completion
  if (data.event_type === 'job_completed') {
    console.log('Job finished successfully!');
    ws.close();
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('WebSocket closed');
};
```

#### Python Example

```python
import asyncio
import json
import websockets

async def monitor_scraping_job(job_id: int):
    uri = f"ws://localhost:8000/ws/scraping/{job_id}"

    async with websockets.connect(uri) as websocket:
        print(f"Connected to job {job_id}")

        while True:
            message = await websocket.recv()
            event = json.loads(message)

            print(f"[{event['event_type']}] {event['message']}")
            print(f"Progress: {event.get('progress')}%")
            print(f"Results: {event['results_count']}")

            if event['event_type'] in ['job_completed', 'job_failed']:
                break

# Run
asyncio.run(monitor_scraping_job(123))
```

### HTTP Polling Endpoint (Fallback)

If WebSockets are not available, you can use HTTP polling:

**Endpoint:** `GET /ws/scraping/{job_id}/status`

```javascript
async function pollJobStatus(jobId) {
  const response = await fetch(`/ws/scraping/${jobId}/status`);
  const data = await response.json();

  console.log('Job status:', data.status);
  console.log('Items scraped:', data.items_scraped);

  return data;
}

// Poll every 2 seconds
setInterval(() => pollJobStatus(123), 2000);
```

## Integration Guide

### For Developers

#### Emitting Events from Scrapers

Use the helper functions in `app/utils/progress_tracker.py`:

```python
from app.utils.progress_tracker import (
    emit_job_started,
    emit_job_progress,
    emit_job_completed,
    emit_scraper_started,
    emit_scraper_completed,
)

async def my_scraping_function(job_id: int):
    # Emit job started
    await emit_job_started(
        job_id=job_id,
        job_type="flights",
        source="my_scraper",
        message="Starting scrape..."
    )

    # Emit scraper started
    await emit_scraper_started(
        job_id=job_id,
        scraper_name="my_scraper",
        route="MUC→BCN"
    )

    # ... do scraping ...

    # Emit scraper completed
    await emit_scraper_completed(
        job_id=job_id,
        scraper_name="my_scraper",
        route="MUC→BCN",
        results_count=42
    )

    # Emit job completed
    await emit_job_completed(
        job_id=job_id,
        results_count=42,
        message="Scraping complete!"
    )
```

#### Creating a Scraping Job with Real-Time Updates

```python
from app.orchestration.flight_orchestrator import FlightOrchestrator
from app.models.scraping_job import ScrapingJob
from datetime import datetime, date

# Create scraping job
job = ScrapingJob(
    job_type="flights",
    source="orchestrator",
    status="running",
    items_scraped=0,
    started_at=datetime.now()
)
db.add(job)
await db.flush()

# Run orchestrator with job_id for real-time updates
orchestrator = FlightOrchestrator()
flights = await orchestrator.scrape_all(
    origins=['MUC'],
    destinations=['BCN'],
    date_ranges=[(date(2025, 12, 20), date(2025, 12, 27))],
    job_id=job.id  # Pass job_id for real-time updates
)

# Save to database
await orchestrator.save_to_database(
    flights,
    create_job=False,
    job_id=job.id  # Reuse existing job
)
```

## Examples

### Python CLI Client

See `examples/websocket_client_example.py` for a full Python client example:

```bash
python examples/websocket_client_example.py 123
```

### HTML Dashboard

Open `examples/websocket_html_example.html` in a browser for a visual real-time monitor.

### cURL (WebSocket via wscat)

```bash
# Install wscat
npm install -g wscat

# Connect to job
wscat -c ws://localhost:8000/ws/scraping/123
```

## Configuration

### Redis (Required)

WebSocket events use Redis pub/sub for multi-worker coordination. Ensure Redis is configured:

```bash
# .env
REDIS_URL=redis://localhost:6379/0
```

### CORS Settings

For web clients, ensure CORS is configured in `app/config.py`:

```python
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080
```

## Monitoring

### Get WebSocket Statistics

```bash
curl http://localhost:8000/ws/stats
```

Response:
```json
{
  "total_connections": 5,
  "active_jobs": 3,
  "redis_connected": true
}
```

## Troubleshooting

### WebSocket Not Connecting

1. **Check server is running:**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Verify Redis is running:**
   ```bash
   docker-compose ps redis
   ```

3. **Check job exists:**
   ```bash
   curl http://localhost:8000/ws/scraping/123/status
   ```

### No Events Received

1. **Ensure job_id is passed to orchestrator:**
   ```python
   flights = await orchestrator.scrape_all(..., job_id=job.id)
   ```

2. **Check Redis pub/sub:**
   ```bash
   redis-cli
   SUBSCRIBE scraping_events
   ```

3. **Check logs:**
   ```bash
   docker-compose logs -f app
   ```

### Events Not Broadcasting to All Clients

This is expected if Redis is not running. The WebSocket manager uses Redis pub/sub to coordinate multiple workers. Without Redis, events only reach clients connected to the same worker.

**Solution:** Ensure Redis is running and configured.

## Performance Considerations

- **Connection Limits:** Each WebSocket maintains an open connection. Consider connection pooling for high-traffic scenarios.
- **Event Frequency:** Events are sent for each scraper start/complete. For very large jobs (100+ scrapers), consider throttling events.
- **Redis Memory:** Events are ephemeral (not persisted). Redis memory usage is minimal.

## Security

- **Authentication:** Currently no authentication on WebSocket endpoints. Consider adding token-based auth for production.
- **Rate Limiting:** Consider rate limiting WebSocket connections to prevent abuse.
- **Job ID Validation:** Jobs are validated on connection. Invalid job IDs receive an error event.

## Future Enhancements

- [ ] Authentication and authorization
- [ ] Subscription to multiple jobs
- [ ] Event filtering (subscribe to specific event types)
- [ ] Event history (replay missed events)
- [ ] Compression for large events
- [ ] Binary protocol (e.g., MessagePack) for efficiency
