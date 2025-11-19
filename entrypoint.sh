#!/bin/bash
set -e

echo "Starting SmartFamilyTravelScout initialization..."

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL..."
max_retries=30
retry_count=0

while [ $retry_count -lt $max_retries ]; do
    if python -c "
import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import settings

async def check_db():
    try:
        engine = create_async_engine(str(settings.database_url), echo=False)
        async with engine.connect() as conn:
            await conn.execute('SELECT 1')
        await engine.dispose()
        return True
    except Exception as e:
        print(f'Database not ready: {e}', file=sys.stderr)
        return False

result = asyncio.run(check_db())
sys.exit(0 if result else 1)
" 2>/dev/null; then
        echo "PostgreSQL is ready!"
        break
    fi

    retry_count=$((retry_count + 1))
    echo "PostgreSQL is unavailable - attempt $retry_count/$max_retries"
    sleep 2
done

if [ $retry_count -eq $max_retries ]; then
    echo "Error: PostgreSQL did not become ready in time"
    exit 1
fi

# Wait for Redis to be ready
echo "Waiting for Redis..."
retry_count=0

while [ $retry_count -lt $max_retries ]; do
    if python -c "
import redis.asyncio as aioredis
import asyncio
import sys
from app.config import settings

async def check_redis():
    try:
        client = await aioredis.from_url(str(settings.redis_url))
        await client.ping()
        await client.close()
        return True
    except Exception as e:
        print(f'Redis not ready: {e}', file=sys.stderr)
        return False

result = asyncio.run(check_redis())
sys.exit(0 if result else 1)
" 2>/dev/null; then
        echo "Redis is ready!"
        break
    fi

    retry_count=$((retry_count + 1))
    echo "Redis is unavailable - attempt $retry_count/$max_retries"
    sleep 2
done

if [ $retry_count -eq $max_retries ]; then
    echo "Error: Redis did not become ready in time"
    exit 1
fi

# Run database migrations
echo "Running database migrations..."
alembic upgrade head || {
    echo "Warning: Migration failed. This might be expected on first run."
    echo "Attempting to initialize database..."
    alembic revision --autogenerate -m "Initial migration" || echo "Could not create initial migration"
    alembic upgrade head || echo "Could not run initial migration"
}

echo "Initialization complete!"

# Execute the main command
exec "$@"
