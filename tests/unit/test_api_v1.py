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


class TestDealsEndpoint:
    """Tests for the deals endpoints."""

    @patch("app.api.routes.v1.deals.AsyncSessionLocal")
    def test_get_deals_empty(self, mock_session_local, test_client):
        """Test GET /api/v1/deals returns empty list when no deals."""
        # Mock database session
        mock_session = AsyncMock()
        mock_session_local.return_value.__aenter__.return_value = mock_session

        # Mock execute returning empty results
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = test_client.get("/api/v1/deals")
        assert response.status_code == 200
        data = response.json()

        assert "deals" in data
        assert isinstance(data["deals"], list)
        assert len(data["deals"]) == 0
        assert data["total_count"] == 0
        assert "filters_applied" in data

    @patch("app.api.routes.v1.deals.AsyncSessionLocal")
    def test_get_deals_with_filters(self, mock_session_local, test_client):
        """Test GET /api/v1/deals with query filters."""
        mock_session = AsyncMock()
        mock_session_local.return_value.__aenter__.return_value = mock_session

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = test_client.get(
            "/api/v1/deals?min_score=70&destination=Barcelona&min_price=500&max_price=2000"
        )
        assert response.status_code == 200
        data = response.json()

        filters = data["filters_applied"]
        assert filters["min_score"] == 70
        assert filters["destination"] == "Barcelona"
        assert filters["min_price"] == 500
        assert filters["max_price"] == 2000

    @patch("app.api.routes.v1.deals.AsyncSessionLocal")
    def test_get_deals_pagination(self, mock_session_local, test_client):
        """Test GET /api/v1/deals with pagination parameters."""
        mock_session = AsyncMock()
        mock_session_local.return_value.__aenter__.return_value = mock_session

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = test_client.get("/api/v1/deals?limit=10&offset=20")
        assert response.status_code == 200
        data = response.json()

        assert data["filters_applied"]["limit"] == 10
        assert data["filters_applied"]["offset"] == 20

    @patch("app.api.routes.v1.deals.AsyncSessionLocal")
    def test_get_deal_by_id_not_found(self, mock_session_local, test_client):
        """Test GET /api/v1/deals/{id} when deal doesn't exist."""
        mock_session = AsyncMock()
        mock_session_local.return_value.__aenter__.return_value = mock_session

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = test_client.get("/api/v1/deals/999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @patch("app.api.routes.v1.deals.AsyncSessionLocal")
    def test_get_top_deals(self, mock_session_local, test_client):
        """Test GET /api/v1/deals/top/{limit}."""
        mock_session = AsyncMock()
        mock_session_local.return_value.__aenter__.return_value = mock_session

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        response = test_client.get("/api/v1/deals/top/10")
        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)


class TestStatsEndpoint:
    """Tests for the statistics endpoints."""

    @patch("app.api.routes.v1.stats.AsyncSessionLocal")
    def test_get_stats(self, mock_session_local, test_client):
        """Test GET /api/v1/stats returns statistics."""
        mock_session = AsyncMock()
        mock_session_local.return_value.__aenter__.return_value = mock_session

        # Mock scalar returns for different queries
        mock_session.scalar = AsyncMock(side_effect=[100, 75, 82.5, 1500.0, 10])

        response = test_client.get("/api/v1/stats")
        assert response.status_code == 200
        data = response.json()

        assert "total_packages" in data
        assert "high_score_packages" in data
        assert "avg_score" in data
        assert "avg_price" in data
        assert "unique_destinations" in data

    @patch("app.api.routes.v1.stats.AsyncSessionLocal")
    def test_get_destination_stats(self, mock_session_local, test_client):
        """Test GET /api/v1/stats/destinations returns destination statistics."""
        mock_session = AsyncMock()
        mock_session_local.return_value.__aenter__.return_value = mock_session

        # Mock destination data
        mock_dest_result = Mock()
        mock_dest_data = [
            Mock(destination_city="Barcelona", count=50, avg_score=85.5),
            Mock(destination_city="Lisbon", count=30, avg_score=78.2),
        ]
        mock_dest_result.all.return_value = mock_dest_data

        mock_session.execute = AsyncMock(return_value=mock_dest_result)
        mock_session.scalar = AsyncMock(return_value=10)

        response = test_client.get("/api/v1/stats/destinations?limit=5")
        assert response.status_code == 200
        data = response.json()

        assert "destinations" in data
        assert "total_destinations" in data
        assert isinstance(data["destinations"], list)


class TestAPIVersioning:
    """Tests for API versioning strategy."""

    def test_v1_prefix_routes_exist(self, test_client):
        """Test that v1 routes are accessible with /api/v1 prefix."""
        # Test version endpoint
        response = test_client.get("/api/v1/version")
        assert response.status_code == 200

        # Test health endpoint
        response = test_client.get("/api/v1/health")
        assert response.status_code in [200, 503]  # May be unhealthy in test env

        # Test deals endpoint
        response = test_client.get("/api/v1/deals")
        assert response.status_code in [200, 500]  # May error without DB

        # Test stats endpoint
        response = test_client.get("/api/v1/stats")
        assert response.status_code in [200, 500]  # May error without DB

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
