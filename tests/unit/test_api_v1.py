"""
Unit tests for API v1 endpoints.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, date
from fastapi.testclient import TestClient


@pytest.fixture
def test_client():
    """Create a test client for the FastAPI app."""
    from app.api.main import app
    return TestClient(app)


class TestAPIRoot:
    """Tests for the API root endpoint."""

    def test_api_root(self, test_client):
        """Test that /api returns version information."""
        response = test_client.get("/api")
        assert response.status_code == 200
        data = response.json()

        assert "name" in data
        assert "version" in data
        assert "api_versions" in data
        assert "v1" in data["api_versions"]
        assert data["api_versions"]["v1"]["status"] == "stable"
        assert data["api_versions"]["v1"]["prefix"] == "/api/v1"
        assert "endpoints" in data["api_versions"]["v1"]


class TestVersionEndpoint:
    """Tests for the version endpoint."""

    def test_get_version(self, test_client):
        """Test GET /api/v1/version returns version information."""
        response = test_client.get("/api/v1/version")
        assert response.status_code == 200
        data = response.json()

        assert "api_version" in data
        assert data["api_version"] == "1.0.0"
        assert "app_name" in data
        assert "app_version" in data
        assert "environment" in data
        assert "status" in data
        assert data["status"] == "stable"


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    @patch("app.api.routes.v1.health.check_db_connection")
    @patch("app.api.routes.v1.health.redis_client")
    def test_health_check_healthy(self, mock_redis, mock_db_check, test_client):
        """Test health check when all dependencies are healthy."""
        # Mock healthy dependencies
        mock_db_check.return_value = True
        mock_redis.ping = AsyncMock(return_value=True)

        response = test_client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert "api_version" in data
        assert data["api_version"] == "1.0.0"
        assert "dependencies" in data
        assert data["dependencies"]["database"] == "healthy"
        assert data["dependencies"]["redis"] == "healthy"

    @patch("app.api.routes.v1.health.check_db_connection")
    @patch("app.api.routes.v1.health.redis_client")
    def test_health_check_unhealthy_db(self, mock_redis, mock_db_check, test_client):
        """Test health check when database is unhealthy."""
        # Mock unhealthy database
        mock_db_check.return_value = False
        mock_redis.ping = AsyncMock(return_value=True)

        response = test_client.get("/api/v1/health")
        assert response.status_code == 503
        data = response.json()

        assert data["status"] == "unhealthy"
        assert data["dependencies"]["database"] == "unhealthy"

    @patch("app.api.routes.v1.health.check_db_connection")
    @patch("app.api.routes.v1.health.redis_client", None)
    def test_health_check_no_redis(self, mock_db_check, test_client):
        """Test health check when Redis is not available."""
        mock_db_check.return_value = True

        response = test_client.get("/api/v1/health")
        assert response.status_code == 503
        data = response.json()

        assert data["status"] == "unhealthy"
        assert data["dependencies"]["redis"] == "unhealthy"


class TestAPIVersioning:
    """Tests for API versioning strategy."""

    def test_v1_prefix_routes_exist(self, test_client):
        """Test that v1 routes are accessible with /api/v1 prefix."""
        # Test version endpoint
        response = test_client.get("/api/v1/version")
        assert response.status_code == 200

    @patch("app.api.routes.v1.health.check_db_connection")
    @patch("app.api.routes.v1.health.redis_client")
    def test_v1_health_endpoint_exists(self, mock_redis, mock_db_check, test_client):
        """Test that health endpoint is accessible with /api/v1 prefix."""
        # Mock dependencies for health check
        mock_db_check.return_value = True
        mock_redis.ping = AsyncMock(return_value=True)

        response = test_client.get("/api/v1/health")
        assert response.status_code == 200

    def test_api_root_lists_versions(self, test_client):
        """Test that /api endpoint lists available API versions."""
        response = test_client.get("/api")
        assert response.status_code == 200
        data = response.json()

        assert "api_versions" in data
        assert "v1" in data["api_versions"]
        assert "prefix" in data["api_versions"]["v1"]
        assert "endpoints" in data["api_versions"]["v1"]

        # Check that v1 endpoints are listed
        v1_endpoints = data["api_versions"]["v1"]["endpoints"]
        assert "version" in v1_endpoints
        assert "health" in v1_endpoints
        assert "deals" in v1_endpoints
        assert "stats" in v1_endpoints

    def test_version_endpoint_stability(self, test_client):
        """Test that version endpoint returns consistent structure."""
        response = test_client.get("/api/v1/version")
        assert response.status_code == 200
        data = response.json()

        # Ensure stable fields exist
        required_fields = ["api_version", "app_name", "app_version", "environment", "status"]
        for field in required_fields:
            assert field in data, f"Required field '{field}' missing from version response"


class TestAPIDocumentation:
    """Tests for API documentation endpoints."""

    def test_openapi_schema_available(self, test_client):
        """Test that OpenAPI schema is accessible."""
        response = test_client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()

        assert "openapi" in data
        assert "info" in data
        assert "paths" in data

    def test_docs_endpoint_available(self, test_client):
        """Test that Swagger UI docs are accessible."""
        response = test_client.get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_redoc_endpoint_available(self, test_client):
        """Test that ReDoc documentation is accessible."""
        response = test_client.get("/redoc")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
