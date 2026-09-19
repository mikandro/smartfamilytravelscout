"""
Prometheus metrics collectors for monitoring system performance and health.
"""

from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, REGISTRY

# Use the default registry
metrics_registry = REGISTRY

# Scraper metrics
scraper_requests_total = Counter(
    "scraper_requests_total",
    "Total number of scraper requests",
    ["scraper", "status"],
    registry=metrics_registry,
)

scraper_duration_seconds = Histogram(
    "scraper_duration_seconds",
    "Time spent scraping in seconds",
    ["scraper"],
    registry=metrics_registry,
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, float("inf")),
)

flights_discovered_total = Counter(
    "flights_discovered_total",
    "Total number of flights discovered",
    ["scraper", "origin", "destination"],
    registry=metrics_registry,
)

accommodations_discovered_total = Counter(
    "accommodations_discovered_total",
    "Total number of accommodations discovered",
    ["scraper", "city"],
    registry=metrics_registry,
)

events_discovered_total = Counter(
    "events_discovered_total",
    "Total number of events discovered",
    ["scraper", "city"],
    registry=metrics_registry,
)

# API metrics
api_requests_total = Counter(
    "api_requests_total",
    "Total number of API requests",
    ["endpoint", "method", "status"],
    registry=metrics_registry,
)

api_duration_seconds = Histogram(
    "api_duration_seconds",
    "Time spent processing API requests in seconds",
    ["endpoint", "method"],
    registry=metrics_registry,
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float("inf")),
)

# Error tracking
scraping_errors_total = Counter(
    "scraping_errors_total",
    "Total number of scraping errors",
    ["scraper", "error_type"],
    registry=metrics_registry,
)

# Active jobs
active_scraping_jobs = Gauge(
    "active_scraping_jobs",
    "Number of currently active scraping jobs",
    ["scraper"],
    registry=metrics_registry,
)

# Claude AI metrics
claude_api_calls_total = Counter(
    "claude_api_calls_total",
    "Total number of Claude API calls",
    ["model", "analyzer"],
    registry=metrics_registry,
)

claude_api_tokens_total = Counter(
    "claude_api_tokens_total",
    "Total number of tokens used in Claude API calls",
    ["model", "token_type"],
    registry=metrics_registry,
)

claude_api_cost_total = Counter(
    "claude_api_cost_total",
    "Total cost of Claude API calls in USD",
    ["model"],
    registry=metrics_registry,
)

claude_api_duration_seconds = Histogram(
    "claude_api_duration_seconds",
    "Time spent on Claude API calls in seconds",
    ["model", "analyzer"],
    registry=metrics_registry,
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, float("inf")),
)

# Database metrics
db_query_duration_seconds = Histogram(
    "db_query_duration_seconds",
    "Time spent on database queries in seconds",
    ["operation"],
    registry=metrics_registry,
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, float("inf")),
)

db_connections_active = Gauge(
    "db_connections_active",
    "Number of active database connections",
    registry=metrics_registry,
)

# Trip package metrics
trip_packages_scored_total = Counter(
    "trip_packages_scored_total",
    "Total number of trip packages scored",
    ["score_range"],
    registry=metrics_registry,
)

trip_packages_created_total = Counter(
    "trip_packages_created_total",
    "Total number of trip packages created",
    registry=metrics_registry,
)

# Notification metrics
notifications_sent_total = Counter(
    "notifications_sent_total",
    "Total number of notifications sent",
    ["channel", "status"],
    registry=metrics_registry,
)
