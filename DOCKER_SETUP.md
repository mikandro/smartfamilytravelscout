# Docker Setup Guide

This guide will help you set up and run SmartFamilyTravelScout using Docker Compose.

## Prerequisites

- Docker (version 20.10 or higher)
- Docker Compose (version 2.0 or higher)
- Git

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd smartfamilytravelscout
```

### 2. Configure Environment Variables

A default `.env` file has been created for you with safe defaults. However, you should add your API keys for full functionality:

```bash
# Edit the .env file and add your API keys
nano .env
```

**Required for AI features:**

- `ANTHROPIC_API_KEY`: Get from https://console.anthropic.com/

**Optional (for enhanced scraping):**

- `KIWI_API_KEY`: Flight data from Kiwi.com
- `EVENTBRITE_API_KEY`: Event data from Eventbrite
- Other API keys as listed in `.env.example`

### 3. Start the Services

```bash
# Start all services in detached mode
docker-compose up -d
```

This will:

1. Start PostgreSQL database
2. Start Redis cache/message broker
3. Build and start the FastAPI application
4. Run database migrations automatically
5. Start Celery worker and beat scheduler

### 4. Verify the Setup

Check that all services are running:

```bash
docker-compose ps
```

You should see all services with status "Up" or "healthy".

Check the application health:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "environment": "development",
  "dependencies": {
    "database": "healthy",
    "redis": "healthy"
  }
}
```

### 5. Access the Application

- **Web Dashboard**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## Troubleshooting

### Services Not Starting

**Check logs:**

```bash
docker-compose logs -f
```

**Check specific service logs:**

```bash
docker-compose logs -f app
docker-compose logs -f postgres
docker-compose logs -f redis
```

### Database Connection Issues

The entrypoint script automatically waits for PostgreSQL to be ready and runs migrations. If you encounter issues:

```bash
# Restart the app service
docker-compose restart app

# Check PostgreSQL is running
docker-compose exec postgres pg_isready -U travelscout

# Manually run migrations
docker-compose exec app alembic upgrade head
```

### Redis Connection Issues

```bash
# Check Redis is running
docker-compose exec redis redis-cli ping

# Should return "PONG"
```

### Port Conflicts

If you get "port already in use" errors:

```bash
# Stop existing services
docker-compose down

# Check what's using the ports
lsof -i :8000  # FastAPI
lsof -i :5432  # PostgreSQL
lsof -i :6379  # Redis

# Either stop the conflicting service or modify ports in docker-compose.yml
```

### Missing API Keys

If you see errors about missing API keys:

1. Edit `.env` and add the required API keys
2. Restart the services:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

### Build Issues

If the Docker build fails:

```bash
# Clean rebuild
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

### Permission Issues

If you encounter permission issues with Playwright or logs:

```bash
# Fix permissions
chmod +x entrypoint.sh
docker-compose down
docker-compose up -d --build
```

## Common Commands

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f app
docker-compose logs -f celery-worker
```

### Stop Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes database data)
docker-compose down -v
```

### Restart Services

```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart app
```

### Rebuild After Code Changes

```bash
# Rebuild and restart
docker-compose up -d --build
```

### Access Database

```bash
# PostgreSQL shell
docker-compose exec postgres psql -U travelscout -d travelscout

# Example query
# SELECT * FROM alembic_version;
```

### Access Redis CLI

```bash
docker-compose exec redis redis-cli

# Example commands:
# PING
# KEYS *
# GET some_key
```

### Run Database Migrations

```bash
# Upgrade to latest
docker-compose exec app alembic upgrade head

# Create new migration
docker-compose exec app alembic revision --autogenerate -m "description"

# Downgrade one version
docker-compose exec app alembic downgrade -1
```

### Execute Commands in Container

```bash
# Python shell
docker-compose exec app python

# Run CLI commands
docker-compose exec app python -m app.cli.main health

# Access bash
docker-compose exec app bash
```

## Development Mode

For development with hot-reload:

1. The app service is already configured with `--reload` flag
2. Code changes in `./app` directory will auto-reload
3. For configuration changes, restart the service:
   ```bash
   docker-compose restart app
   ```

## Production Deployment

For production use:

1. **Update `.env` file:**
   - Set `DEBUG=False`
   - Set `ENVIRONMENT=production`
   - Use strong `SECRET_KEY`
   - Configure production SMTP settings

2. **Update `docker-compose.yml`:**
   - Remove `--reload` flag from app command
   - Remove volume mounts for code (except logs)
   - Configure proper restart policies
   - Set resource limits

3. **Use proper database:**
   - Consider external PostgreSQL instance
   - Set up regular backups
   - Configure connection pooling

4. **Security:**
   - Use secrets management (Docker secrets, AWS Secrets Manager)
   - Enable HTTPS/TLS
   - Configure firewall rules
   - Regular security updates

## Architecture

The docker-compose setup includes:

1. **PostgreSQL (postgres)**: Database for storing deals, preferences, and tracking data
2. **Redis (redis)**: Cache and message broker for Celery
3. **FastAPI App (app)**: Main web application and API
4. **Celery Worker (celery-worker)**: Background task processor
5. **Celery Beat (celery-beat)**: Task scheduler

### Service Dependencies

```
postgres, redis
    ↓
   app (waits for postgres/redis to be healthy)
    ↓
celery-worker, celery-beat (wait for app to start)
```

### Automatic Initialization

The `entrypoint.sh` script automatically:

1. Waits for PostgreSQL to be ready
2. Waits for Redis to be ready
3. Runs database migrations with Alembic
4. Starts the application

## Getting Help

- Check the main README.md for general documentation
- Review `.env.example` for all available configuration options
- Check logs with `docker-compose logs -f`
- Create an issue on GitHub if you encounter bugs

## Next Steps

After successful setup:

1. Configure your preferences via the web dashboard
2. Add your departure airports and destination preferences
3. Set up email notifications (optional)
4. Let the system discover deals automatically via Celery Beat
5. Check the dashboard for discovered deals

Enjoy finding amazing family travel deals! 🎉
