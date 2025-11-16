"""
Configuration management using Pydantic Settings.
Loads environment variables with validation and type checking.
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="SmartFamilyTravelScout", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    environment: str = Field(default="development", description="Environment name")

    # Database
    database_url: PostgresDsn = Field(
        ...,
        description="PostgreSQL connection URL",
    )

    # Redis
    redis_url: RedisDsn = Field(
        ...,
        description="Redis connection URL",
    )

    # Celery
    celery_broker_url: Optional[str] = Field(
        default=None, description="Celery broker URL (defaults to redis_url)"
    )
    celery_result_backend: Optional[str] = Field(
        default=None, description="Celery result backend (defaults to redis_url)"
    )

    # API Keys - Travel Services
    kiwi_api_key: Optional[str] = Field(default=None, description="Kiwi.com API key")
    skyscanner_api_key: Optional[str] = Field(default=None, description="Skyscanner API key")
    amadeus_api_key: Optional[str] = Field(default=None, description="Amadeus API key")
    amadeus_api_secret: Optional[str] = Field(default=None, description="Amadeus API secret")
    eventbrite_api_key: Optional[str] = Field(default=None, description="Eventbrite API key")

    # API Keys - AI Services
    anthropic_api_key: str = Field(..., description="Anthropic Claude API key")

    # Email/SMTP
    smtp_host: str = Field(default="smtp.gmail.com", description="SMTP server host")
    smtp_port: int = Field(default=587, description="SMTP server port")
    smtp_user: Optional[str] = Field(default=None, description="SMTP username")
    smtp_password: Optional[str] = Field(default=None, description="SMTP password")
    smtp_from_email: str = Field(
        default="noreply@smartfamilytravelscout.com", description="From email address"
    )
    smtp_from_name: str = Field(
        default="SmartFamilyTravelScout", description="From name"
    )

    # Scraping Configuration
    scraper_max_retries: int = Field(default=3, description="Maximum scraper retries")
    scraper_timeout: int = Field(default=30, description="Scraper timeout in seconds")
    scraper_user_agent: str = Field(
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        description="User agent for scrapers",
    )

    # Price Thresholds (in EUR)
    max_flight_price_per_person: float = Field(
        default=200.0, description="Maximum flight price per person in EUR"
    )
    max_accommodation_price_per_night: float = Field(
        default=150.0, description="Maximum accommodation price per night in EUR"
    )
    min_deal_score: float = Field(default=7.0, description="Minimum deal score (0-10)")

    # Geographic Settings
    default_departure_airports: str = Field(
        default="VIE,BTS,PRG", description="Default departure airports (comma-separated)"
    )
    default_search_radius_km: int = Field(
        default=500, description="Default search radius in kilometers"
    )

    # Time Settings
    timezone: str = Field(default="Europe/Vienna", description="Default timezone")
    default_trip_duration_days: int = Field(
        default=7, description="Default trip duration in days"
    )
    advance_booking_days: int = Field(
        default=60, description="Advance booking days for searches"
    )

    # Rate Limiting
    rate_limit_per_minute: int = Field(default=60, description="Rate limit per minute")
    rate_limit_per_hour: int = Field(default=1000, description="Rate limit per hour")

    # Cache Settings
    cache_ttl_flights: int = Field(
        default=3600, description="Cache TTL for flights in seconds"
    )
    cache_ttl_accommodations: int = Field(
        default=7200, description="Cache TTL for accommodations in seconds"
    )
    cache_ttl_events: int = Field(
        default=86400, description="Cache TTL for events in seconds"
    )

    # Security
    secret_key: str = Field(..., description="Secret key for signing tokens")
    api_key_header: str = Field(default="X-API-Key", description="API key header name")
    allowed_origins: str = Field(
        default="http://localhost:3000,http://localhost:8000",
        description="Allowed CORS origins (comma-separated)",
    )

    # Feature Flags
    enable_scraping: bool = Field(default=True, description="Enable web scraping")
    enable_ai_scoring: bool = Field(default=True, description="Enable AI scoring")
    enable_notifications: bool = Field(default=True, description="Enable notifications")
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")

    # AWS Configuration (Optional)
    aws_access_key_id: Optional[str] = Field(default=None, description="AWS access key ID")
    aws_secret_access_key: Optional[str] = Field(
        default=None, description="AWS secret access key"
    )
    aws_region: str = Field(default="eu-central-1", description="AWS region")
    aws_s3_bucket: Optional[str] = Field(default=None, description="AWS S3 bucket name")

    # Monitoring (Optional)
    sentry_dsn: Optional[str] = Field(default=None, description="Sentry DSN")
    sentry_environment: str = Field(default="development", description="Sentry environment")
    sentry_traces_sample_rate: float = Field(
        default=0.1, description="Sentry traces sample rate"
    )

    @field_validator("celery_broker_url", mode="before")
    @classmethod
    def set_celery_broker_url(cls, v: Optional[str], info) -> str:
        """Set celery_broker_url to redis_url if not provided."""
        if v is None and "redis_url" in info.data:
            return str(info.data["redis_url"])
        return v or ""

    @field_validator("celery_result_backend", mode="before")
    @classmethod
    def set_celery_result_backend(cls, v: Optional[str], info) -> str:
        """Set celery_result_backend to redis_url if not provided."""
        if v is None and "redis_url" in info.data:
            redis_url = str(info.data["redis_url"])
            # Use database 1 for results
            return redis_url.replace("/0", "/1")
        return v or ""

    def get_departure_airports_list(self) -> List[str]:
        """Get list of departure airports from comma-separated string."""
        return [airport.strip() for airport in self.default_departure_airports.split(",")]

    def get_allowed_origins_list(self) -> List[str]:
        """Get list of allowed origins from comma-separated string."""
        return [origin.strip() for origin in self.allowed_origins.split(",")]

    @property
    def database_url_sync(self) -> str:
        """Get synchronous database URL (for Alembic)."""
        return str(self.database_url).replace("+asyncpg", "")


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Uses lru_cache to avoid re-reading environment variables.
    """
    return Settings()


# Global settings instance
settings = get_settings()
