"""
Pytest configuration and shared fixtures for SmartFamilyTravelScout tests.
"""

import pytest
from unittest.mock import Mock, patch
import os
from pathlib import Path
from dotenv import load_dotenv


# Load test environment variables before any app imports
env_file = Path(__file__).parent.parent / ".env.test"
if env_file.exists():
    load_dotenv(env_file, override=True)
else:
    # Fallback: Set minimal environment variables for testing
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
    os.environ.setdefault("SECRET_KEY", "test-secret-key")
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
