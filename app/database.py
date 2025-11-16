"""
Database connection and session management using SQLAlchemy.
Supports async operations with asyncpg driver.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import create_engine, event, pool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

# Base class for SQLAlchemy models
Base = declarative_base()

# Async Engine Configuration
async_engine = create_async_engine(
    str(settings.database_url),
    echo=settings.debug,
    pool_pre_ping=True,  # Verify connections before using
    pool_size=5,  # Maximum number of connections in the pool
    max_overflow=10,  # Maximum overflow connections
    pool_recycle=3600,  # Recycle connections after 1 hour
    pool_timeout=30,  # Timeout for getting connection from pool
    connect_args={
        "server_settings": {"application_name": settings.app_name},
        "timeout": 10,
    },
)

# Async Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Sync Engine Configuration (for Alembic migrations)
sync_engine = create_engine(
    settings.database_url_sync,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
    poolclass=pool.QueuePool,
)

# Sync Session Factory
SessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
)


@event.listens_for(pool.Pool, "connect")
def set_postgres_pragmas(dbapi_connection, connection_record):
    """Set PostgreSQL connection parameters."""
    cursor = dbapi_connection.cursor()
    cursor.execute("SET timezone='UTC'")
    cursor.close()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async dependency for FastAPI to get database session.

    Usage:
        @app.get("/items")
        async def read_items(db: AsyncSession = Depends(get_async_session)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_sync_session() -> Session:
    """
    Get synchronous database session.

    Usage (for Celery tasks or CLI):
        db = get_sync_session()
        try:
            # Do work
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    """
    return SessionLocal()


@asynccontextmanager
async def get_async_session_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database session.

    Usage:
        async with get_async_session_context() as db:
            result = await db.execute(select(Item))
            items = result.scalars().all()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize database tables.

    WARNING: This should only be used in development.
    In production, use Alembic migrations instead.
    """
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created successfully")


async def drop_db() -> None:
    """
    Drop all database tables.

    WARNING: This will delete all data! Only use in development/testing.
    """
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    logger.warning("All database tables dropped")


async def check_db_connection() -> bool:
    """
    Check if database connection is healthy.

    Returns:
        bool: True if connection is healthy, False otherwise
    """
    try:
        async with async_engine.connect() as conn:
            await conn.execute("SELECT 1")
        logger.info("Database connection is healthy")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


async def close_db_connections() -> None:
    """Close all database connections and dispose of the engine."""
    await async_engine.dispose()
    sync_engine.dispose()
    logger.info("Database connections closed")


# Context manager for application lifespan
@asynccontextmanager
async def lifespan_db():
    """
    Database lifespan context manager for FastAPI.

    Usage in FastAPI app:
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            async with lifespan_db():
                yield

        app = FastAPI(lifespan=lifespan)
    """
    try:
        # Startup
        logger.info("Initializing database connections")
        if await check_db_connection():
            logger.info("Database is ready")
        else:
            logger.error("Database connection failed during startup")
            raise RuntimeError("Database connection failed")

        yield

    finally:
        # Shutdown
        logger.info("Closing database connections")
        await close_db_connections()
