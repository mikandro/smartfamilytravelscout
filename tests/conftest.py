"""
Pytest configuration and shared fixtures for SmartFamilyTravelScout tests.
"""

import pytest
from unittest.mock import Mock, patch
import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import date, datetime, timedelta


# Load test environment variables before any app imports
env_file = Path(__file__).parent.parent / ".env.test"
if env_file.exists():
    load_dotenv(env_file, override=True)
else:
    # Fallback: Set minimal environment variables for testing
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
    os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-at-least-32-characters-long")
    os.environ.setdefault("DEBUG", "False")


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment."""
    yield
    # Cleanup (optional)
    # Remove test environment variables if needed


@pytest.fixture
def temp_logs_dir(tmp_path):
    """Create a temporary logs directory for testing."""
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(exist_ok=True)
    return logs_dir


# Database fixtures for integration tests
@pytest.fixture
async def test_db_session():
    """
    Provide a test database session for integration tests.

    Usage:
        async def test_something(test_db_session):
            # Use test_db_session for database operations
            result = await test_db_session.execute(select(Model))
    """
    from app.database import get_async_session_context

    async with get_async_session_context() as session:
        yield session
        # Rollback any uncommitted changes after test
        await session.rollback()


@pytest.fixture
def sample_airport_data():
    """Provide sample airport data for testing."""
    return {
        "origin": {
            "iata_code": "MUC",
            "name": "Munich Airport",
            "city": "Munich",
            "country": "Germany",
            "distance_from_home": 50,
            "driving_time": 45,
            "parking_cost_per_day": 15.0,
        },
        "destination": {
            "iata_code": "BCN",
            "name": "Barcelona Airport",
            "city": "Barcelona",
            "country": "Spain",
            "distance_from_home": 1200,
            "driving_time": 720,
            "parking_cost_per_day": 0.0,
        },
    }


@pytest.fixture
def sample_flight_data():
    """Provide sample flight data for testing."""
    departure_date = date.today() + timedelta(days=60)
    return_date = departure_date + timedelta(days=7)

    return {
        "airline": "Test Airlines",
        "departure_date": departure_date,
        "return_date": return_date,
        "price_per_person": 150.0,
        "total_price": 600.0,
        "booking_class": "Economy",
        "direct_flight": True,
        "source": "test",
        "booking_url": "https://test.com",
        "scraped_at": datetime.now(),
    }


@pytest.fixture
def sample_accommodation_data():
    """Provide sample accommodation data for testing."""
    return {
        "destination_city": "Barcelona",
        "name": "Test Hotel",
        "accommodation_type": "hotel",
        "price_per_night": 80.0,
        "rating": 4.5,
        "family_friendly": True,
        "source": "test",
        "booking_url": "https://test.com/hotel",
        "scraped_at": datetime.now(),
    }


@pytest.fixture
def sample_event_data():
    """Provide sample event data for testing."""
    event_date = date.today() + timedelta(days=63)

    return {
        "destination_city": "Barcelona",
        "name": "Test Family Event",
        "event_type": "festival",
        "date": event_date,
        "description": "A fun family event",
        "price_per_person": 20.0,
        "family_friendly": True,
        "ai_score": 85,
        "source": "test",
        "scraped_at": datetime.now(),
    }


@pytest.fixture
def sample_trip_package_data():
    """Provide sample trip package data for testing."""
    departure_date = date.today() + timedelta(days=60)
    return_date = departure_date + timedelta(days=7)

    return {
        "package_type": "family",
        "flights_json": [1],
        "accommodation_id": 1,
        "events_json": [],
        "total_price": 1500.0,
        "destination_city": "Barcelona",
        "departure_date": departure_date,
        "return_date": return_date,
        "num_nights": 7,
        "notified": False,
    }


@pytest.fixture
def mock_claude_response():
    """
    Provide a mock Claude API response for testing AI scoring.

    Usage:
        def test_something(mock_claude_response):
            with patch('app.ai.claude_client.ClaudeClient.create') as mock:
                mock.return_value = mock_claude_response
                # Test code here
    """
    mock_response = Mock()
    mock_response.content = [Mock(text="""{
        "score": 85,
        "value_assessment": "Excellent value",
        "family_suitability": "Highly suitable",
        "timing_quality": "Perfect timing",
        "recommendation": "book_now",
        "reasoning": "Great deal"
    }""")]
    mock_response.usage = Mock(input_tokens=1000, output_tokens=500)
    return mock_response


# Markers for test categorization
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "database: mark test as requiring database"
    )
    config.addinivalue_line(
        "markers", "celery: mark test as requiring Celery"
    )
