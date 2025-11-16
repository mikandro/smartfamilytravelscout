"""
Orchestration module for coordinating multiple scrapers and matchers.

This module provides high-level orchestrators that run multiple scrapers
in parallel, deduplicate results, manage database operations, and match
accommodations and events to trip packages.
"""

from app.orchestration.accommodation_matcher import AccommodationMatcher
from app.orchestration.event_matcher import EventMatcher
from app.orchestration.flight_orchestrator import FlightOrchestrator

__all__ = ["FlightOrchestrator", "AccommodationMatcher", "EventMatcher"]
