# Integration Tests

This directory contains comprehensive integration tests for SmartFamilyTravelScout's critical workflows.

## Overview

Integration tests validate that multiple components work together correctly across the entire system. Unlike unit tests that test individual components in isolation, these tests verify end-to-end functionality with real database operations, multiple module interactions, and complete workflows.

## Test Coverage

### 1. End-to-End Flight Search (`test_flight_search_end_to_end.py`)
Tests the complete flight search workflow from search initiation to database persistence:
- FlightOrchestrator initialization and execution
- Multiple scraper coordination
- Flight deduplication across sources
- Database persistence with relationships
- ScrapingJob tracking
- Error handling and recovery
- Concurrent scraper execution

**Key Scenarios:**
- Complete flight search with multiple scrapers
- Duplicate flight detection and merging
- Graceful error handling when scrapers fail
- Parallel execution verification

### 2. Package Generation Pipeline (`test_package_generation_pipeline.py`)
Tests the complete trip package generation flow:
- Flight retrieval with true cost calculations
- Accommodation matching by destination city
- Trip package assembly with cost breakdown
- Event matching and integration
- School holiday filtering
- Duplicate package prevention

**Key Scenarios:**
- Complete package generation (flights → accommodations → events)
- Accurate cost calculation including all components
- School holiday period filtering
- Prevention of duplicate packages

### 3. Database Operations (`test_database_operations.py`)
Tests database relationships, integrity, and performance:
- CASCADE DELETE on Airport → Flight relationship
- SET NULL on Accommodation → TripPackage relationship
- Eager loading with `selectinload()`
- Transaction rollback on errors
- Index usage and query performance
- Concurrent update handling
- Bulk insert operations
- JSONB field operations

**Key Scenarios:**
- Foreign key constraints and cascading deletes
- Transaction integrity and rollback
- Query optimization with indexes
- Bulk operations efficiency
- JSONB array manipulation

### 4. Celery Task Execution (`test_celery_tasks.py`)
Tests background task execution and orchestration:
- Task registration with Celery
- Individual task execution (daily flights, price updates, events, etc.)
- Task failure handling and logging
- Retry mechanisms
- Async execution capabilities
- Task chaining and workflows
- Result serialization and storage

**Key Scenarios:**
- All scheduled tasks execute successfully
- Task failures are logged and handled
- Tasks can be chained together
- Results are properly stored

### 5. AI Scoring Pipeline (`test_ai_scoring_pipeline.py`)
Tests Claude API integration and AI-powered analysis:
- Claude client initialization
- DealScorer configuration
- Trip package scoring with mocked API
- API cost tracking
- Price threshold filtering
- Error handling for API failures
- Batch scoring efficiency
- Prompt template loading
- Score persistence to database

**Key Scenarios:**
- Complete scoring workflow with mocked Claude API
- API costs are tracked in database
- Scoring respects price thresholds
- API errors handled gracefully
- Multiple packages scored efficiently

### 6. Notification Workflow (`test_notification_workflow.py`)
Tests email notification system:
- Email sender initialization
- Email content generation
- High-score package detection
- Notification deduplication
- SMTP error handling
- HTML email formatting
- Batch notification sending
- User preference filtering
- Retry mechanisms

**Key Scenarios:**
- Notifications triggered for high-scoring packages
- Same package not notified twice
- Email generation with proper formatting
- User preferences respected
- Failed notifications can be retried

## Running Integration Tests

### Prerequisites

1. **Database Setup:**
   ```bash
   # Start PostgreSQL (via Docker Compose or locally)
   docker-compose up -d postgres

   # Run migrations
   poetry run alembic upgrade head

   # Seed test data (optional)
   poetry run scout db seed
   ```

2. **Environment Variables:**
   Ensure `.env.test` exists with test configuration, or set:
   ```bash
   export DATABASE_URL="postgresql+asyncpg://test:test@localhost:5432/test"
   export REDIS_URL="redis://localhost:6379/0"
   export ANTHROPIC_API_KEY="test-key"
   ```

### Running All Integration Tests

```bash
# Run all integration tests
poetry run pytest tests/integration/ -v

# Run with coverage report
poetry run pytest tests/integration/ --cov=app --cov-report=html

# Run only integration tests (using marker)
poetry run pytest -m integration -v
```

### Running Specific Test Files

```bash
# Test flight search workflow
poetry run pytest tests/integration/test_flight_search_end_to_end.py -v

# Test package generation
poetry run pytest tests/integration/test_package_generation_pipeline.py -v

# Test database operations
poetry run pytest tests/integration/test_database_operations.py -v

# Test Celery tasks
poetry run pytest tests/integration/test_celery_tasks.py -v

# Test AI scoring
poetry run pytest tests/integration/test_ai_scoring_pipeline.py -v

# Test notifications
poetry run pytest tests/integration/test_notification_workflow.py -v
```

### Running Specific Test Classes or Methods

```bash
# Run a specific test class
poetry run pytest tests/integration/test_flight_search_end_to_end.py::TestFlightSearchEndToEnd -v

# Run a specific test method
poetry run pytest tests/integration/test_database_operations.py::TestDatabaseOperations::test_airport_flight_cascade_delete -v
```

### Filtering Tests

```bash
# Skip slow tests
poetry run pytest tests/integration/ -m "not slow" -v

# Run only database-related tests
poetry run pytest tests/integration/ -m database -v

# Run tests with specific keyword
poetry run pytest tests/integration/ -k "scoring" -v
```

## Test Configuration

### Pytest Markers

Tests use the following markers for categorization:

- `@pytest.mark.integration` - Integration test (requires multiple components)
- `@pytest.mark.slow` - Slow test (may be skipped in quick runs)
- `@pytest.mark.database` - Requires database access
- `@pytest.mark.celery` - Requires Celery worker

### Fixtures

Common fixtures are defined in `tests/conftest.py`:

- `test_db_session` - Async database session with automatic cleanup
- `sample_airport_data` - Sample airport data for tests
- `sample_flight_data` - Sample flight data for tests
- `sample_accommodation_data` - Sample accommodation data
- `sample_event_data` - Sample event data
- `sample_trip_package_data` - Sample trip package data
- `mock_claude_response` - Mocked Claude API response

## Best Practices

### Writing Integration Tests

1. **Test Real Interactions:** Integration tests should test actual component interactions, not mocked versions
2. **Database Cleanup:** Always clean up test data after tests complete
3. **Use Fixtures:** Leverage shared fixtures for common test data
4. **Test Error Paths:** Test both success and failure scenarios
5. **Independence:** Tests should be independent and runnable in any order
6. **Descriptive Names:** Use clear, descriptive test method names

### Example Test Structure

```python
@pytest.mark.integration
@pytest.mark.asyncio
class TestMyWorkflow:
    """Integration tests for my workflow."""

    async def test_complete_workflow(self):
        """
        Test complete workflow from start to finish.

        Verifies:
        1. Step 1 completes successfully
        2. Data is persisted correctly
        3. Relationships are maintained
        4. Results are as expected
        """
        # Setup
        async with get_async_session_context() as db:
            # Create test data
            ...

        # Execute
        result = await my_workflow()

        # Verify
        assert result is not None
        assert result.status == "success"

        # Cleanup
        async with get_async_session_context() as db:
            # Delete test data
            ...
```

## Troubleshooting

### Database Connection Issues

```bash
# Check database is running
docker-compose ps postgres

# View database logs
docker-compose logs postgres

# Restart database
docker-compose restart postgres
```

### Test Failures

```bash
# Run with verbose output
poetry run pytest tests/integration/ -vv

# Run with print statements
poetry run pytest tests/integration/ -s

# Run with detailed traceback
poetry run pytest tests/integration/ --tb=long
```

### Performance Issues

```bash
# Run tests in parallel (requires pytest-xdist)
poetry run pytest tests/integration/ -n auto

# Profile slow tests
poetry run pytest tests/integration/ --durations=10
```

## CI/CD Integration

These integration tests are designed to run in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
test:
  runs-on: ubuntu-latest
  services:
    postgres:
      image: postgres:15
      env:
        POSTGRES_PASSWORD: test
        POSTGRES_DB: test
      options: >-
        --health-cmd pg_isready
        --health-interval 10s
        --health-timeout 5s
        --health-retries 5
  steps:
    - uses: actions/checkout@v2
    - name: Install dependencies
      run: poetry install
    - name: Run migrations
      run: poetry run alembic upgrade head
    - name: Run integration tests
      run: poetry run pytest tests/integration/ -v
```

## Contributing

When adding new features, please add corresponding integration tests:

1. Create a new test file or add to existing file
2. Use appropriate pytest markers
3. Include docstrings describing what is tested
4. Clean up test data after execution
5. Ensure tests pass locally before committing

## Maintenance

These tests should be updated when:

- New features are added to the system
- Critical workflows are modified
- Database schema changes
- API integrations change
- Bug fixes require new test coverage

## Additional Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [SQLAlchemy Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Celery Testing Documentation](https://docs.celeryq.dev/en/stable/userguide/testing.html)
- [Project README](../../README.md)
- [CLAUDE.md](../../CLAUDE.md) - Project development guide
