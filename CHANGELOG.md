# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- WebSocket support for real-time deal notifications
- Redis-based rate limiting for API endpoints
- Improved error messaging across scraper failures
- Playwright-stealth support for enhanced web scraping

### Fixed
- Docker Compose project initialization error
- Docker path fixes for container deployment

## [0.1.0] - 2025-01-15

### Added
- Initial release of SmartFamilyTravelScout
- CLI interface with Rich formatting (`scout` command)
  - Health check command
  - Scrape command for flights and accommodations
  - Pipeline runner for full orchestration
  - Deal viewer and statistics commands
- Flight scrapers for multiple sources:
  - Skyscanner web scraper (Playwright-based, no API key required)
  - Ryanair web scraper (Playwright-based, no API key required)
  - WizzAir API scraper (unofficial API, no API key required)
  - Kiwi.com API client (optional, requires API key)
- Accommodation scrapers:
  - Booking.com scraper
  - Airbnb scraper
- Event scrapers:
  - Eventbrite API integration (requires API key)
  - Tourism scrapers for Barcelona, Prague, and Lisbon
- AI-powered features using Claude API:
  - Deal scoring system (0-100 scale) for trip packages
  - Event relevance scoring for family activities
  - Itinerary generator for high-scoring trips
  - Parent escape analyzer for romantic getaway opportunities
- FastAPI web dashboard:
  - REST API endpoints for deals, flights, and accommodations
  - Interactive web interface for browsing travel deals
  - Health monitoring endpoints
- PostgreSQL database with async support:
  - SQLAlchemy ORM models for all entities
  - Alembic migrations for schema management
  - Airport database seeding
  - School holiday calendar (Bavaria)
- Celery background task system:
  - Worker processes for asynchronous scraping
  - Beat scheduler for periodic tasks
  - Redis as message broker
- Email notification system:
  - HTML email templates with Jinja2
  - SMTP integration for deal alerts
  - Email preview functionality
- Docker Compose deployment:
  - PostgreSQL service
  - Redis service
  - FastAPI application
  - Celery worker and beat scheduler
- Comprehensive testing suite:
  - Unit tests with mocking
  - Integration tests with Playwright
  - pytest configuration with coverage reporting
- Cost tracking:
  - API usage monitoring for Claude calls
  - Token usage tracking
  - True cost calculation including parking and travel
- Orchestration system:
  - Flight orchestrator for parallel scraper execution
  - Accommodation matcher for trip package generation
  - Event matcher for activity recommendations
- Configuration management:
  - Pydantic Settings for environment variables
  - Feature flags for optional components
  - SMTP and API key configuration

### Documentation
- README.md with project overview and setup instructions
- CLAUDE.md with development guidelines and architecture details
- API documentation via FastAPI automatic docs
- Example scripts for scrapers and AI features

[Unreleased]: https://github.com/mikandro/smartfamilytravelscout/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/mikandro/smartfamilytravelscout/releases/tag/v0.1.0
