"""
Unit tests for ItineraryGenerator.

Tests the itinerary generation functionality with mocked Claude API
to avoid actual API calls and ensure predictable testing.
"""

import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock

from app.ai.itinerary_generator import (
    ItineraryGenerator,
    ItineraryGenerationError,
)
from app.models.accommodation import Accommodation
from app.models.trip_package import TripPackage


class TestItineraryGenerator:
    """Test suite for ItineraryGenerator class."""

    @pytest.fixture
    def mock_claude_client(self):
        """Create a mock ClaudeClient."""
        client = AsyncMock()
        client.analyze = AsyncMock()
        return client

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.rollback = AsyncMock()
        return session

    @pytest.fixture
    def sample_accommodation(self):
        """Create a sample Accommodation for testing."""
        return Accommodation(
            id=1,
            destination_city="Lisbon",
            name="Family Apartment in Alfama",
            type="airbnb",
            bedrooms=2,
            price_per_night=85.00,
            family_friendly=True,
            has_kitchen=True,
            rating=9.2,
            source="airbnb",
        )

    @pytest.fixture
    def sample_trip_package(self, sample_accommodation):
        """Create a sample TripPackage for testing."""
        departure = date.today() + timedelta(days=30)
        return_date = departure + timedelta(days=3)

        trip = TripPackage(
            id=1,
            package_type="family",
            flights_json={"outbound": {"price": 400}, "return": {"price": 400}},
            accommodation_id=1,
            events_json={
                "events": [
                    {
                        "title": "Lisbon Oceanarium",
                        "event_date": str(departure + timedelta(days=1)),
                        "category": "family",
                    }
                ]
            },
            destination_city="Lisbon",
            departure_date=departure,
            return_date=return_date,
            num_nights=3,
            total_price=1045.00,
            ai_score=85.5,
            ai_reasoning="Excellent value",
        )
        trip.accommodation = sample_accommodation
        return trip

    @pytest.fixture
    def sample_itinerary_response(self):
        """Create a sample itinerary response from Claude."""
        return {
            "day_1": {
                "morning": "Visit Belém Tower at 9am (15 min walk from accommodation)",
                "afternoon": "Return to accommodation for nap time 1-2pm, then explore Alfama",
                "evening": "Dinner at family-friendly restaurant nearby",
                "breakfast_spot": "Pastelaria Santo António - great pastries, high chairs available",
                "lunch_spot": "Time Out Market - variety of food stalls, family-friendly",
                "dinner_spot": "Cervejaria Ramiro - seafood, kids menu, 10 min walk",
                "weather_backup": "Lisbon Oceanarium - excellent indoor activity",
            },
            "day_2": {
                "morning": "Tram 28 ride at 9:30am",
                "afternoon": "Nap time, then visit local park",
                "evening": "Sunset viewpoint and dinner",
                "breakfast_spot": "Hotel breakfast buffet",
                "lunch_spot": "Café near São Jorge Castle",
                "dinner_spot": "Pizzeria with kids menu",
                "weather_backup": "Children's museum",
            },
            "day_3": {
                "morning": "Beach day at Cascais",
                "afternoon": "Nap on beach, ice cream",
                "evening": "Return to Lisbon, easy dinner",
                "breakfast_spot": "Local bakery",
                "lunch_spot": "Beachfront café in Cascais",
                "dinner_spot": "Casual family restaurant",
                "weather_backup": "Aquarium visit",
            },
            "tips": [
                "Bring stroller for 3-year-old",
                "Download offline maps",
                "Pack sunscreen and hats",
            ],
            "packing_essentials": [
                "Stroller",
                "Sunscreen",
                "Snacks for kids",
                "Portable changing mat",
            ],
            "_cost": 0.0234,
            "_model": "claude-sonnet-4-5-20250929",
            "_tokens": {"input": 500, "output": 800, "total": 1300},
        }

    @pytest.fixture
    def generator(self, mock_claude_client, mock_db_session):
        """Create ItineraryGenerator instance."""
        return ItineraryGenerator(
            claude_client=mock_claude_client,
            db_session=mock_db_session,
            min_score_threshold=70.0,
        )

    def test_initialization(self, generator, mock_claude_client, mock_db_session):
        """Test that ItineraryGenerator initializes correctly."""
        assert generator.claude == mock_claude_client
        assert generator.db_session == mock_db_session
        assert generator.min_score_threshold == 70.0

    async def test_generate_itinerary_success(
        self,
        generator,
        sample_trip_package,
        sample_itinerary_response,
        mock_claude_client,
        mock_db_session,
    ):
        """Test successful itinerary generation."""
        # Setup mock
        mock_claude_client.analyze.return_value = sample_itinerary_response

        # Generate itinerary
        result = await generator.generate_itinerary(
            trip_package=sample_trip_package,
            save_to_db=True,
        )

        # Verify Claude API was called
        mock_claude_client.analyze.assert_called_once()
        call_kwargs = mock_claude_client.analyze.call_args.kwargs

        assert call_kwargs["response_format"] == "json"
        assert call_kwargs["operation"] == "itinerary_generation"
        assert call_kwargs["max_tokens"] == 4096

        # Verify result structure (without metadata)
        assert "day_1" in result
        assert "day_2" in result
        assert "day_3" in result
        assert "tips" in result
        assert "_cost" not in result  # Metadata should be removed

        # Verify database save
        mock_db_session.add.assert_called_once_with(sample_trip_package)
        mock_db_session.commit.assert_called_once()

    async def test_generate_itinerary_below_threshold(
        self, generator, sample_trip_package
    ):
        """Test that generation fails for low-scoring trips without force."""
        sample_trip_package.ai_score = 65.0  # Below threshold of 70

        with pytest.raises(ItineraryGenerationError) as exc_info:
            await generator.generate_itinerary(
                trip_package=sample_trip_package,
                force=False,
            )

        assert "below threshold" in str(exc_info.value).lower()

    async def test_generate_itinerary_force_low_score(
        self,
        generator,
        sample_trip_package,
        sample_itinerary_response,
        mock_claude_client,
    ):
        """Test that force flag allows generation for low-scoring trips."""
        sample_trip_package.ai_score = 65.0
        mock_claude_client.analyze.return_value = sample_itinerary_response

        result = await generator.generate_itinerary(
            trip_package=sample_trip_package,
            force=True,
        )

        assert result is not None
        assert "day_1" in result

    async def test_generate_itinerary_cached(
        self, generator, sample_trip_package, sample_itinerary_response
    ):
        """Test that existing itinerary is returned without regeneration."""
        # Set existing itinerary
        sample_trip_package.itinerary_json = sample_itinerary_response

        result = await generator.generate_itinerary(
            trip_package=sample_trip_package,
            force=False,
        )

        # Should return cached version without calling Claude
        assert result == sample_itinerary_response
        generator.claude.analyze.assert_not_called()

    async def test_generate_batch(
        self,
        generator,
        sample_trip_package,
        sample_itinerary_response,
        mock_claude_client,
    ):
        """Test batch itinerary generation."""
        mock_claude_client.analyze.return_value = sample_itinerary_response

        trips = [sample_trip_package]
        results = await generator.generate_batch(
            trip_packages=trips,
            save_to_db=True,
            skip_errors=True,
        )

        assert len(results) == 1
        assert sample_trip_package.id in results
        assert "day_1" in results[sample_trip_package.id]

    async def test_validate_itinerary_valid(self, generator):
        """Test validation of a valid itinerary."""
        valid_itinerary = {
            "day_1": {
                "morning": "Activity",
                "afternoon": "Activity",
                "evening": "Activity",
                "breakfast_spot": "Restaurant",
                "lunch_spot": "Restaurant",
                "dinner_spot": "Restaurant",
            },
            "day_2": {
                "morning": "Activity",
                "afternoon": "Activity",
                "evening": "Activity",
                "breakfast_spot": "Restaurant",
                "lunch_spot": "Restaurant",
                "dinner_spot": "Restaurant",
            },
            "day_3": {
                "morning": "Activity",
                "afternoon": "Activity",
                "evening": "Activity",
                "breakfast_spot": "Restaurant",
                "lunch_spot": "Restaurant",
                "dinner_spot": "Restaurant",
            },
            "tips": ["Tip 1", "Tip 2"],
        }

        # Should not raise exception
        generator._validate_itinerary(valid_itinerary)

    async def test_validate_itinerary_missing_day(self, generator):
        """Test validation fails for missing day."""
        invalid_itinerary = {
            "day_1": {"morning": "Activity"},
            "day_2": {"morning": "Activity"},
            # Missing day_3
            "tips": [],
        }

        with pytest.raises(ItineraryGenerationError) as exc_info:
            generator._validate_itinerary(invalid_itinerary)

        assert "day_3" in str(exc_info.value).lower()

    async def test_get_accommodation_info(
        self, generator, sample_trip_package, sample_accommodation
    ):
        """Test accommodation info extraction."""
        info = await generator._get_accommodation_info(sample_trip_package)

        assert info["name"] == "Family Apartment in Alfama"
        assert "Lisbon" in info["address"]
        assert info["type"] == "airbnb"

    async def test_get_accommodation_info_missing(self, generator, sample_trip_package):
        """Test accommodation info when accommodation is missing."""
        sample_trip_package.accommodation = None
        sample_trip_package.accommodation_id = None

        info = await generator._get_accommodation_info(sample_trip_package)

        assert "Lisbon" in info["name"]
        assert "city center" in info["address"]

    async def test_get_events_info(self, generator, sample_trip_package):
        """Test events info formatting."""
        events_str = await generator._get_events_info(sample_trip_package)

        assert "Lisbon Oceanarium" in events_str
        assert "family" in events_str

    async def test_get_events_info_empty(self, generator, sample_trip_package):
        """Test events info when no events available."""
        sample_trip_package.events_json = None

        events_str = await generator._get_events_info(sample_trip_package)

        assert "No specific events" in events_str

    async def test_format_dates(self, generator, sample_trip_package):
        """Test date formatting."""
        formatted = generator._format_dates(sample_trip_package)

        assert str(sample_trip_package.departure_date.year) in formatted
        assert str(sample_trip_package.duration_days) in formatted
        assert "to" in formatted

    async def test_get_itinerary_summary(self, generator, sample_trip_package):
        """Test itinerary summary generation."""
        sample_trip_package.itinerary_json = {
            "day_1": {
                "morning": "Visit Belém Tower. Great views from the top."
            },
            "day_2": {"morning": "Tram 28 ride through historic districts."},
            "day_3": {"morning": "Beach day at Cascais."},
        }

        summary = await generator.get_itinerary_summary(sample_trip_package)

        assert "Lisbon" in summary
        assert "Day 1" in summary
        assert "Belém Tower" in summary

    async def test_get_itinerary_summary_no_itinerary(
        self, generator, sample_trip_package
    ):
        """Test summary when no itinerary exists."""
        sample_trip_package.itinerary_json = None

        summary = await generator.get_itinerary_summary(sample_trip_package)

        assert "No itinerary" in summary

    async def test_save_to_database_error(
        self, generator, sample_trip_package, mock_db_session
    ):
        """Test error handling when database save fails."""
        mock_db_session.commit.side_effect = Exception("Database error")

        itinerary = {"day_1": {}}

        with pytest.raises(ItineraryGenerationError) as exc_info:
            await generator._save_to_database(sample_trip_package, itinerary)

        assert "Failed to save" in str(exc_info.value)
        mock_db_session.rollback.assert_called_once()
