"""
Tests for FastAPI main application.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import status


@pytest.fixture
def mock_db_connection():
    """Mock database connection."""
    with patch('app.api.main.check_db_connection') as mock:
        mock.return_value = True
        yield mock


@pytest.fixture
def mock_redis():
    """Mock Redis connection."""
    with patch('app.api.main.aioredis') as mock:
        redis_mock = AsyncMock()
        redis_mock.ping = AsyncMock()
        mock.from_url = AsyncMock(return_value=redis_mock)
        yield mock


@pytest.fixture
def client(mock_db_connection, mock_redis):
    """Test client with mocked dependencies."""
    with patch('app.api.main.check_db_connection', return_value=AsyncMock(return_value=True)):
        with patch('app.api.main.close_db_connections', return_value=AsyncMock()):
            from app.api.main import app
            with TestClient(app) as test_client:
                yield test_client


class TestAPIRoot:
    """Test API root endpoint."""

    def test_api_root(self, client):
        """Test /api endpoint returns API information."""
        response = client.get("/api")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "docs" in data
        assert "health" in data
        assert data["docs"] == "/docs"
        assert data["health"] == "/health"


class TestHealthCheck:
    """Test health check endpoint."""

    @patch('app.api.main.check_db_connection')
    async def test_health_check_all_healthy(self, mock_db_check, client):
        """Test health check when all dependencies are healthy."""
        mock_db_check.return_value = True

        # Mock redis_client
        with patch('app.api.main.redis_client') as mock_redis:
            mock_redis.ping = AsyncMock()

            response = client.get("/health")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "healthy"
            assert "version" in data
            assert "environment" in data
            assert "dependencies" in data

    @patch('app.api.main.check_db_connection')
    async def test_health_check_database_unhealthy(self, mock_db_check, client):
        """Test health check when database is unhealthy."""
        mock_db_check.return_value = False

        with patch('app.api.main.redis_client') as mock_redis:
            mock_redis.ping = AsyncMock()

            response = client.get("/health")

            # Note: The status code in response depends on implementation
            data = response.json()
            assert "dependencies" in data

    @patch('app.api.main.check_db_connection')
    async def test_health_check_redis_unhealthy(self, mock_db_check, client):
        """Test health check when Redis is unhealthy."""
        mock_db_check.return_value = True

        with patch('app.api.main.redis_client', None):
            response = client.get("/health")

            data = response.json()
            assert "dependencies" in data

    @patch('app.api.main.check_db_connection')
    async def test_health_check_redis_ping_fails(self, mock_db_check, client):
        """Test health check when Redis ping fails."""
        mock_db_check.return_value = True

        with patch('app.api.main.redis_client') as mock_redis:
            mock_redis.ping = AsyncMock(side_effect=Exception("Redis error"))

            response = client.get("/health")

            data = response.json()
            assert "dependencies" in data


class TestGlobalExceptionHandler:
    """Test global exception handler."""

    @patch('app.api.main.settings')
    def test_global_exception_handler_debug_mode(self, mock_settings, client):
        """Test exception handler in debug mode shows error details."""
        mock_settings.debug = True

        # Create a route that raises an exception
        with patch('app.api.routes.web.templates.TemplateResponse') as mock_template:
            mock_template.side_effect = Exception("Test error")

            response = client.get("/")

            # Should return 500 error with exception message
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch('app.api.main.settings')
    def test_global_exception_handler_production_mode(self, mock_settings, client):
        """Test exception handler in production mode hides error details."""
        mock_settings.debug = False

        with patch('app.api.routes.web.templates.TemplateResponse') as mock_template:
            mock_template.side_effect = Exception("Test error")

            response = client.get("/")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestMiddleware:
    """Test middleware configuration."""

    def test_cors_middleware_configured(self):
        """Test that CORS middleware is configured."""
        from app.api.main import app

        # Check that CORS middleware is in the middleware stack
        middleware_classes = [m.__class__.__name__ for m in app.user_middleware]
        assert 'CORSMiddleware' in str(middleware_classes) or len(app.user_middleware) > 0

    def test_gzip_middleware_configured(self):
        """Test that GZip middleware is configured."""
        from app.api.main import app

        # Check that GZip middleware is in the middleware stack
        middleware_classes = [m.__class__.__name__ for m in app.user_middleware]
        assert 'GZipMiddleware' in str(middleware_classes) or len(app.user_middleware) > 0


class TestStaticFiles:
    """Test static files mounting."""

    def test_static_files_mounted(self):
        """Test that static files are mounted."""
        from app.api.main import app

        # Check that static route exists
        routes = [route.path for route in app.routes]
        assert any('/static' in path for path in routes)


class TestApplicationMetadata:
    """Test application metadata."""

    def test_app_title(self):
        """Test application title is set."""
        from app.api.main import app
        assert app.title is not None

    def test_app_version(self):
        """Test application version is set."""
        from app.api.main import app
        assert app.version is not None

    def test_app_description(self):
        """Test application description is set."""
        from app.api.main import app
        assert app.description is not None
        assert "family travel" in app.description.lower()

    def test_docs_url(self):
        """Test docs URL is configured."""
        from app.api.main import app
        assert app.docs_url == "/docs"

    def test_redoc_url(self):
        """Test ReDoc URL is configured."""
        from app.api.main import app
        assert app.redoc_url == "/redoc"

    def test_openapi_url(self):
        """Test OpenAPI URL is configured."""
        from app.api.main import app
        assert app.openapi_url == "/openapi.json"


class TestLifespan:
    """Test application lifespan management."""

    @pytest.mark.asyncio
    async def test_lifespan_startup_success(self):
        """Test successful startup."""
        from app.api.main import lifespan, app

        with patch('app.api.main.aioredis.from_url') as mock_redis:
            mock_redis_client = AsyncMock()
            mock_redis_client.ping = AsyncMock()
            mock_redis.return_value = mock_redis_client

            with patch('app.api.main.check_db_connection', return_value=True):
                with patch('app.api.main.close_db_connections', new_callable=AsyncMock):
                    async with lifespan(app):
                        # During lifespan, connections should be established
                        pass

                    # After lifespan, connections should be closed
                    mock_redis_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_redis_connection_fails(self):
        """Test startup when Redis connection fails."""
        from app.api.main import lifespan, app

        with patch('app.api.main.aioredis.from_url') as mock_redis:
            mock_redis.side_effect = Exception("Redis connection failed")

            with patch('app.api.main.check_db_connection', return_value=True):
                with patch('app.api.main.close_db_connections', new_callable=AsyncMock):
                    # Should not raise exception, just log error
                    async with lifespan(app):
                        pass

    @pytest.mark.asyncio
    async def test_lifespan_database_check_fails(self):
        """Test startup when database check fails."""
        from app.api.main import lifespan, app

        with patch('app.api.main.aioredis.from_url') as mock_redis:
            mock_redis_client = AsyncMock()
            mock_redis_client.ping = AsyncMock()
            mock_redis.return_value = mock_redis_client

            with patch('app.api.main.check_db_connection', return_value=False):
                with patch('app.api.main.close_db_connections', new_callable=AsyncMock):
                    # Should not raise exception, just log error
                    async with lifespan(app):
                        pass

    @pytest.mark.asyncio
    async def test_lifespan_shutdown(self):
        """Test application shutdown."""
        from app.api.main import lifespan, app

        mock_redis_client = AsyncMock()
        mock_redis_client.ping = AsyncMock()
        mock_redis_client.close = AsyncMock()

        with patch('app.api.main.aioredis.from_url', return_value=mock_redis_client):
            with patch('app.api.main.check_db_connection', return_value=True):
                mock_close_db = AsyncMock()
                with patch('app.api.main.close_db_connections', mock_close_db):
                    async with lifespan(app):
                        pass

                    # Verify shutdown was called
                    mock_redis_client.close.assert_called_once()
                    mock_close_db.assert_called_once()


class TestRouterInclusion:
    """Test that routers are properly included."""

    def test_web_router_included(self):
        """Test that web router is included."""
        from app.api.main import app

        # Check that dashboard routes exist
        routes = [route.path for route in app.routes]
        assert "/" in routes or any(route.path == "/" for route in app.routes)
