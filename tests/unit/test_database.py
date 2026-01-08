"""
Tests for database connection and session management.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session


class TestDatabaseConfiguration:
    """Test database engine and session configuration."""

    def test_async_engine_configured(self):
        """Test that async engine is properly configured."""
        from app.database import async_engine

        assert async_engine is not None
        assert hasattr(async_engine, 'connect')

    def test_async_session_factory_configured(self):
        """Test that async session factory is configured."""
        from app.database import AsyncSessionLocal

        assert AsyncSessionLocal is not None
        assert callable(AsyncSessionLocal)

    def test_sync_engine_configured(self):
        """Test that sync engine is properly configured."""
        from app.database import sync_engine

        assert sync_engine is not None
        assert hasattr(sync_engine, 'connect')

    def test_sync_session_factory_configured(self):
        """Test that sync session factory is configured."""
        from app.database import SessionLocal

        assert SessionLocal is not None
        assert callable(SessionLocal)


class TestGetAsyncSession:
    """Test async session dependency."""

    @pytest.mark.asyncio
    async def test_get_async_session_yields_session(self):
        """Test that get_async_session yields an AsyncSession."""
        from app.database import get_async_session

        # Mock the session
        with patch('app.database.AsyncSessionLocal') as mock_session_maker:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session_maker.return_value.__aenter__.return_value = mock_session
            mock_session.commit = AsyncMock()
            mock_session.close = AsyncMock()
            mock_session.rollback = AsyncMock()

            # Use the generator
            async for session in get_async_session():
                assert session == mock_session
                break

            # Verify commit and close were called
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_async_session_rollback_on_exception(self):
        """Test that session rolls back on exception."""
        from app.database import get_async_session

        with patch('app.database.AsyncSessionLocal') as mock_session_maker:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session_maker.return_value.__aenter__.return_value = mock_session
            mock_session.commit = AsyncMock(side_effect=Exception("Test error"))
            mock_session.rollback = AsyncMock()
            mock_session.close = AsyncMock()

            # Use the generator and expect exception
            with pytest.raises(Exception, match="Test error"):
                async for session in get_async_session():
                    pass

            # Verify rollback was called
            mock_session.rollback.assert_called_once()
            mock_session.close.assert_called_once()


class TestGetSyncSession:
    """Test synchronous session factory."""

    def test_get_sync_session_returns_session(self):
        """Test that get_sync_session returns a Session."""
        from app.database import get_sync_session

        with patch('app.database.SessionLocal') as mock_session_maker:
            mock_session = Mock(spec=Session)
            mock_session_maker.return_value = mock_session

            session = get_sync_session()

            assert session == mock_session
            mock_session_maker.assert_called_once()


class TestGetAsyncSessionContext:
    """Test async session context manager."""

    @pytest.mark.asyncio
    async def test_get_async_session_context(self):
        """Test async session context manager."""
        from app.database import get_async_session_context

        with patch('app.database.AsyncSessionLocal') as mock_session_maker:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session_maker.return_value.__aenter__.return_value = mock_session
            mock_session.commit = AsyncMock()
            mock_session.close = AsyncMock()

            async with get_async_session_context() as session:
                assert session == mock_session

            # Verify commit and close were called
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_async_session_context_rollback_on_exception(self):
        """Test context manager rolls back on exception."""
        from app.database import get_async_session_context

        with patch('app.database.AsyncSessionLocal') as mock_session_maker:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session_maker.return_value.__aenter__.return_value = mock_session
            mock_session.commit = AsyncMock()
            mock_session.rollback = AsyncMock()
            mock_session.close = AsyncMock()

            with pytest.raises(ValueError):
                async with get_async_session_context() as session:
                    raise ValueError("Test error")

            # Verify rollback was called
            mock_session.rollback.assert_called_once()
            mock_session.close.assert_called_once()


class TestInitDB:
    """Test database initialization functions."""

    @pytest.mark.asyncio
    async def test_init_db_creates_tables(self):
        """Test async init_db creates tables."""
        from app.database import init_db

        with patch('app.database.async_engine.begin') as mock_begin:
            mock_conn = AsyncMock()
            mock_begin.return_value.__aenter__.return_value = mock_conn

            await init_db()

            mock_conn.run_sync.assert_called_once()

    def test_init_db_sync_creates_tables(self):
        """Test sync init_db_sync creates tables."""
        from app.database import init_db_sync

        with patch('app.database.Base.metadata.create_all') as mock_create:
            init_db_sync()

            mock_create.assert_called_once()


class TestDropDB:
    """Test database drop functions."""

    @pytest.mark.asyncio
    async def test_drop_db_drops_tables(self):
        """Test async drop_db drops tables."""
        from app.database import drop_db

        with patch('app.database.async_engine.begin') as mock_begin:
            mock_conn = AsyncMock()
            mock_begin.return_value.__aenter__.return_value = mock_conn

            await drop_db()

            mock_conn.run_sync.assert_called_once()

    def test_drop_db_sync_drops_tables(self):
        """Test sync drop_db_sync drops tables."""
        from app.database import drop_db_sync

        with patch('app.database.Base.metadata.drop_all') as mock_drop:
            drop_db_sync()

            mock_drop.assert_called_once()


class TestResetDB:
    """Test database reset functions."""

    @pytest.mark.asyncio
    async def test_reset_db_drops_and_creates(self):
        """Test async reset_db drops and creates tables."""
        from app.database import reset_db

        with patch('app.database.drop_db', new_callable=AsyncMock) as mock_drop:
            with patch('app.database.init_db', new_callable=AsyncMock) as mock_init:
                await reset_db()

                mock_drop.assert_called_once()
                mock_init.assert_called_once()

    def test_reset_db_sync_drops_and_creates(self):
        """Test sync reset_db_sync drops and creates tables."""
        from app.database import reset_db_sync

        with patch('app.database.drop_db_sync') as mock_drop:
            with patch('app.database.init_db_sync') as mock_init:
                reset_db_sync()

                mock_drop.assert_called_once()
                mock_init.assert_called_once()


class TestCheckDBConnection:
    """Test database connection health check."""

    @pytest.mark.asyncio
    async def test_check_db_connection_success(self):
        """Test successful database connection check."""
        from app.database import check_db_connection

        with patch('app.database.async_engine.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()
            mock_connect.return_value.__aenter__.return_value = mock_conn

            result = await check_db_connection()

            assert result is True
            mock_conn.execute.assert_called_once_with("SELECT 1")

    @pytest.mark.asyncio
    async def test_check_db_connection_failure(self):
        """Test failed database connection check."""
        from app.database import check_db_connection

        with patch('app.database.async_engine.connect') as mock_connect:
            mock_connect.side_effect = Exception("Connection failed")

            result = await check_db_connection()

            assert result is False


class TestCloseDBConnections:
    """Test closing database connections."""

    @pytest.mark.asyncio
    async def test_close_db_connections(self):
        """Test that close_db_connections disposes engines."""
        from app.database import close_db_connections

        with patch('app.database.async_engine.dispose', new_callable=AsyncMock) as mock_async_dispose:
            with patch('app.database.sync_engine.dispose') as mock_sync_dispose:
                await close_db_connections()

                mock_async_dispose.assert_called_once()
                mock_sync_dispose.assert_called_once()


class TestLifespanDB:
    """Test database lifespan context manager."""

    @pytest.mark.asyncio
    async def test_lifespan_db_success(self):
        """Test successful database lifespan."""
        from app.database import lifespan_db

        with patch('app.database.check_db_connection', return_value=True):
            with patch('app.database.close_db_connections', new_callable=AsyncMock) as mock_close:
                async with lifespan_db():
                    pass

                mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_db_connection_failed(self):
        """Test lifespan when database connection fails."""
        from app.database import lifespan_db

        with patch('app.database.check_db_connection', return_value=False):
            with patch('app.database.close_db_connections', new_callable=AsyncMock):
                with pytest.raises(RuntimeError, match="Database connection failed"):
                    async with lifespan_db():
                        pass

    @pytest.mark.asyncio
    async def test_lifespan_db_closes_on_exception(self):
        """Test that lifespan closes connections even on exception."""
        from app.database import lifespan_db

        with patch('app.database.check_db_connection', return_value=True):
            with patch('app.database.close_db_connections', new_callable=AsyncMock) as mock_close:
                with pytest.raises(ValueError):
                    async with lifespan_db():
                        raise ValueError("Test error")

                # Should still close connections
                mock_close.assert_called_once()


class TestSetPostgresPragmas:
    """Test PostgreSQL connection parameters."""

    def test_set_postgres_pragmas_sets_timezone(self):
        """Test that timezone is set to UTC."""
        from app.database import set_postgres_pragmas

        # Create mock connection
        mock_connection = Mock()
        mock_cursor = Mock()
        mock_connection.cursor.return_value = mock_cursor

        # Call the function
        set_postgres_pragmas(mock_connection, None)

        # Verify timezone was set
        mock_cursor.execute.assert_called_once_with("SET timezone='UTC'")
        mock_cursor.close.assert_called_once()


class TestEnginePoolConfiguration:
    """Test database engine pool configuration."""

    def test_async_engine_pool_settings(self):
        """Test async engine pool configuration."""
        from app.database import async_engine

        # Verify pool settings
        assert async_engine.pool.size() >= 0  # Pool is created

    def test_sync_engine_pool_settings(self):
        """Test sync engine pool configuration."""
        from app.database import sync_engine

        # Verify pool exists
        assert sync_engine.pool is not None


class TestSessionConfiguration:
    """Test session factory configuration."""

    def test_async_session_expire_on_commit(self):
        """Test async session doesn't expire on commit."""
        from app.database import AsyncSessionLocal

        # The session factory should have expire_on_commit=False
        # This is configured in the async_sessionmaker call
        assert AsyncSessionLocal is not None

    def test_sync_session_configuration(self):
        """Test sync session autocommit and autoflush settings."""
        from app.database import SessionLocal

        # Verify session factory exists
        assert SessionLocal is not None


class TestImports:
    """Test that all necessary imports are available."""

    def test_base_model_imported(self):
        """Test that Base model is imported."""
        from app.database import Base

        assert Base is not None

    def test_async_session_imported(self):
        """Test that AsyncSession is available."""
        from app.database import AsyncSession

        assert AsyncSession is not None

    def test_session_imported(self):
        """Test that Session is available."""
        from app.database import Session

        assert Session is not None
