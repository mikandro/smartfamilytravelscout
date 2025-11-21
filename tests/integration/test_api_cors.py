"""
Integration tests for API CORS configuration.

Tests verify that Cross-Origin Resource Sharing (CORS) is properly configured
to allow frontend applications to make API requests.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client for the FastAPI application."""
    from app.api.main import app

    return TestClient(app)


def test_cors_preflight_request(client):
    """Test CORS preflight (OPTIONS) request."""
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )

    # Should allow the request
    assert response.status_code == 200

    # Verify CORS headers are present
    assert "access-control-allow-origin" in response.headers
    assert "access-control-allow-methods" in response.headers
    assert "access-control-allow-headers" in response.headers


def test_cors_simple_request_with_allowed_origin(client):
    """Test CORS with an allowed origin (localhost:3000)."""
    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:3000"},
    )

    # Health check may return 503 if database is not running (that's OK for CORS testing)
    assert response.status_code in [200, 503]

    # Verify CORS header is present with correct origin
    assert "access-control-allow-origin" in response.headers
    # Should allow credentials
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_simple_request_with_another_allowed_origin(client):
    """Test CORS with another allowed origin (localhost:8000)."""
    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:8000"},
    )

    # Health check may return 503 if database is not running (that's OK for CORS testing)
    assert response.status_code in [200, 503]
    assert "access-control-allow-origin" in response.headers


def test_cors_api_root_endpoint(client):
    """Test CORS on /api endpoint."""
    response = client.get(
        "/api",
        headers={"Origin": "http://localhost:3000"},
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers


def test_api_endpoints_accessible(client):
    """Test that key API endpoints are accessible."""
    # Health check
    response = client.get("/health")
    assert response.status_code in [200, 503]  # 503 if dependencies are down

    # API root
    response = client.get("/api")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data


def test_cors_configuration_from_settings():
    """Test that CORS configuration is loaded from settings."""
    from app.config import settings

    # Verify allowed origins are configured
    allowed_origins = settings.get_allowed_origins_list()
    assert isinstance(allowed_origins, list)
    assert len(allowed_origins) > 0

    # Default should include localhost origins for development
    assert any("localhost" in origin for origin in allowed_origins)
