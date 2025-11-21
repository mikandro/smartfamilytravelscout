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


class TestItineraryStructuralValidation:
    """
    Comprehensive structural validation tests for itineraries.

    Tests from Issue #72: Ensure itinerary structure matches trip duration
    and contains all required sections.
    """

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
        return session

    @pytest.fixture
    def generator(self, mock_claude_client, mock_db_session):
        """Create ItineraryGenerator instance."""
        return ItineraryGenerator(
            claude_client=mock_claude_client,
            db_session=mock_db_session,
            min_score_threshold=70.0,
        )

    async def test_itinerary_has_correct_number_of_days(
        self, generator, mock_claude_client
    ):
        """Test that generated itinerary contains correct number of days matching trip duration."""
        # Create trip package with 3-day duration
        trip = TripPackage(
            id=1,
            package_type="family",
            destination_city="Barcelona",
            departure_date=date.today() + timedelta(days=30),
            return_date=date.today() + timedelta(days=33),
            num_nights=3,
            total_price=1200.00,
            ai_score=80.0,
        )

        # Mock Claude response with 3 days
        mock_itinerary = {
            "day_1": {"morning": "Activity", "afternoon": "Activity", "evening": "Activity",
                     "breakfast_spot": "Café", "lunch_spot": "Restaurant", "dinner_spot": "Bistro"},
            "day_2": {"morning": "Activity", "afternoon": "Activity", "evening": "Activity",
                     "breakfast_spot": "Café", "lunch_spot": "Restaurant", "dinner_spot": "Bistro"},
            "day_3": {"morning": "Activity", "afternoon": "Activity", "evening": "Activity",
                     "breakfast_spot": "Café", "lunch_spot": "Restaurant", "dinner_spot": "Bistro"},
            "tips": ["Tip 1"],
            "_cost": 0.01,
            "_tokens": {"total": 100},
        }
        mock_claude_client.analyze.return_value = mock_itinerary

        result = await generator.generate_itinerary(trip, save_to_db=False)

        # Verify we have exactly 3 days
        day_keys = [k for k in result.keys() if k.startswith("day_")]
        assert len(day_keys) == 3, f"Expected 3 days but got {len(day_keys)}"
        assert "day_1" in result
        assert "day_2" in result
        assert "day_3" in result

    async def test_each_day_contains_all_time_periods(
        self, generator, mock_claude_client
    ):
        """Test that each day has morning, afternoon, and evening activities."""
        trip = TripPackage(
            id=1,
            package_type="family",
            destination_city="Prague",
            departure_date=date.today() + timedelta(days=30),
            return_date=date.today() + timedelta(days=33),
            num_nights=3,
            total_price=900.00,
            ai_score=75.0,
        )

        mock_itinerary = {
            "day_1": {
                "morning": "Visit Old Town Square at 9am",
                "afternoon": "Lunch and nap time, then Charles Bridge",
                "evening": "Dinner at traditional Czech restaurant",
                "breakfast_spot": "Hotel breakfast",
                "lunch_spot": "Local pub",
                "dinner_spot": "Restaurace U Pinkasů",
            },
            "day_2": {
                "morning": "Prague Castle tour",
                "afternoon": "Nap time, then Petřín Tower",
                "evening": "Dinner cruise on Vltava River",
                "breakfast_spot": "Café Louvre",
                "lunch_spot": "Café Imperial",
                "dinner_spot": "Boat restaurant",
            },
            "day_3": {
                "morning": "Zoo Prague visit",
                "afternoon": "Return for rest, then local park",
                "evening": "Easy dinner near accommodation",
                "breakfast_spot": "Bakery",
                "lunch_spot": "Zoo café",
                "dinner_spot": "Pizza place",
            },
            "tips": ["Take tram 22 for easy transport"],
            "_cost": 0.02,
            "_tokens": {"total": 150},
        }
        mock_claude_client.analyze.return_value = mock_itinerary

        result = await generator.generate_itinerary(trip, save_to_db=False)

        # Check each day has all required time periods
        required_periods = ["morning", "afternoon", "evening"]
        for day_num in range(1, 4):
            day_key = f"day_{day_num}"
            assert day_key in result, f"Missing {day_key}"

            for period in required_periods:
                assert period in result[day_key], f"Missing {period} in {day_key}"
                assert len(result[day_key][period]) > 0, f"{period} in {day_key} is empty"

    async def test_each_day_contains_meal_spots(self, generator, mock_claude_client):
        """Test that each day includes breakfast, lunch, and dinner recommendations."""
        trip = TripPackage(
            id=1,
            package_type="family",
            destination_city="Lisbon",
            departure_date=date.today() + timedelta(days=30),
            return_date=date.today() + timedelta(days=33),
            num_nights=3,
            total_price=1000.00,
            ai_score=82.0,
        )

        mock_itinerary = {
            "day_1": {
                "morning": "Belém Tower visit",
                "afternoon": "Nap and Alfama exploration",
                "evening": "Sunset at Miradouro",
                "breakfast_spot": "Pastelaria de Belém - famous for pastéis",
                "lunch_spot": "Time Out Market - variety of options",
                "dinner_spot": "Cervejaria Ramiro - seafood",
                "weather_backup": "Oceanarium",
            },
            "day_2": {
                "morning": "Tram 28 ride",
                "afternoon": "Nap and local park",
                "evening": "Chiado district stroll",
                "breakfast_spot": "Fabrica Coffee Roasters",
                "lunch_spot": "Café A Brasileira",
                "dinner_spot": "Pizzeria with kids menu",
                "weather_backup": "Pavilhão do Conhecimento",
            },
            "day_3": {
                "morning": "Cascais beach day",
                "afternoon": "Beach play and ice cream",
                "evening": "Return to Lisbon",
                "breakfast_spot": "Hotel buffet",
                "lunch_spot": "Beachfront café",
                "dinner_spot": "Casual trattoria",
                "weather_backup": "Shopping at Colombo",
            },
            "tips": ["Bring beach toys"],
            "_cost": 0.025,
            "_tokens": {"total": 200},
        }
        mock_claude_client.analyze.return_value = mock_itinerary

        result = await generator.generate_itinerary(trip, save_to_db=False)

        # Verify all meal spots are present and populated
        meal_types = ["breakfast_spot", "lunch_spot", "dinner_spot"]
        for day_num in range(1, 4):
            day_key = f"day_{day_num}"
            for meal in meal_types:
                assert meal in result[day_key], f"Missing {meal} in {day_key}"
                assert len(result[day_key][meal]) > 5, f"{meal} in {day_key} is too short or empty"


class TestItineraryContentQuality:
    """
    Content quality validation tests for itineraries.

    Tests from Issue #72: Verify activities are meaningful and detailed,
    with proper meal information and quality content.
    """

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
        return session

    @pytest.fixture
    def generator(self, mock_claude_client, mock_db_session):
        """Create ItineraryGenerator instance."""
        return ItineraryGenerator(
            claude_client=mock_claude_client,
            db_session=mock_db_session,
            min_score_threshold=70.0,
        )

    async def test_activities_are_populated_with_details(
        self, generator, mock_claude_client
    ):
        """Test that activities contain meaningful, detailed descriptions."""
        trip = TripPackage(
            id=1,
            package_type="family",
            destination_city="Barcelona",
            departure_date=date.today() + timedelta(days=30),
            return_date=date.today() + timedelta(days=33),
            num_nights=3,
            total_price=1100.00,
            ai_score=85.0,
        )

        mock_itinerary = {
            "day_1": {
                "morning": "Start at Park Güell at 9am (book tickets in advance). Walk through the colorful mosaics and let kids explore the serpentine bench. Great views of Barcelona. Plan 2 hours.",
                "afternoon": "Return to accommodation by 1pm for nap time (crucial for young kids). After rest, head to nearby playground at Plaça del Sol. Ice cream at local gelateria.",
                "evening": "Early dinner at 6pm at El Xampanyet in Born district (tapas, high chairs available, 15 min metro ride). Walk through Gothic Quarter before bedtime.",
                "breakfast_spot": "Brunch & Cake - kid-friendly, amazing pancakes, high chairs",
                "lunch_spot": "Light lunch near Park Güell before nap",
                "dinner_spot": "El Xampanyet - tapas, family atmosphere",
                "weather_backup": "CosmoCaixa science museum - perfect for rainy days",
            },
            "day_2": {
                "morning": "Barcelona Aquarium at 10am (less crowded). Kids love the shark tunnel. Allow 2-3 hours. Bring stroller as lots of walking.",
                "afternoon": "Nap time 1-2:30pm at accommodation. Beach time at Barceloneta (20 min walk). Build sandcastles, paddle in shallow water.",
                "evening": "Beachfront dinner at 6:30pm. Watch sunset. Easy walk back or short taxi.",
                "breakfast_spot": "Milk Bar & Bistro - excellent breakfast, kids portions",
                "lunch_spot": "Aquarium café or nearby Port Vell",
                "dinner_spot": "Pez Vela - beachfront, kids menu, relaxed",
                "weather_backup": "Chocolate Museum - interactive and delicious",
            },
            "day_3": {
                "morning": "Parc de la Ciutadella - rent a boat on the lake (kids love this!). Visit the mammoth statue. Lots of space to run around.",
                "afternoon": "Final nap, then La Rambla for people-watching. Street performers entertain kids. Buy souvenirs.",
                "evening": "Farewell dinner at 6pm near accommodation. Early night for travel tomorrow.",
                "breakfast_spot": "Federal Café - healthy options, smoothies",
                "lunch_spot": "Picnic in the park with takeaway",
                "dinner_spot": "La Fonda - traditional Catalan, budget-friendly",
                "weather_backup": "IKEA Smaland play area if desperate!",
            },
            "tips": [
                "Book Park Güell tickets 3 days ahead",
                "Metro is stroller-friendly with elevators",
                "Bring sun hats and sunscreen",
            ],
            "packing_essentials": ["Lightweight stroller", "Beach toys", "Sunscreen SPF 50"],
            "_cost": 0.03,
            "_tokens": {"total": 250},
        }
        mock_claude_client.analyze.return_value = mock_itinerary

        result = await generator.generate_itinerary(trip, save_to_db=False)

        # Verify activities have substantial content (not just placeholders)
        min_activity_length = 30  # Meaningful activities should be at least 30 chars

        for day_num in range(1, 4):
            day_key = f"day_{day_num}"

            # Check activity descriptions are detailed
            assert len(result[day_key]["morning"]) >= min_activity_length, \
                f"{day_key} morning activity too short"
            assert len(result[day_key]["afternoon"]) >= min_activity_length, \
                f"{day_key} afternoon activity too short"
            assert len(result[day_key]["evening"]) >= min_activity_length, \
                f"{day_key} evening activity too short"

    async def test_breakfast_information_present(
        self, generator, mock_claude_client
    ):
        """Test that breakfast spots are specifically mentioned and detailed."""
        trip = TripPackage(
            id=1,
            package_type="family",
            destination_city="Prague",
            departure_date=date.today() + timedelta(days=30),
            return_date=date.today() + timedelta(days=33),
            num_nights=3,
            total_price=850.00,
            ai_score=78.0,
        )

        mock_itinerary = {
            "day_1": {
                "morning": "Old Town exploration",
                "afternoon": "Charles Bridge walk",
                "evening": "Traditional dinner",
                "breakfast_spot": "Café Savoy - elegant café with pastries and eggs, high chairs available",
                "lunch_spot": "Lokál - Czech pub food",
                "dinner_spot": "U Fleků - historic beer hall",
            },
            "day_2": {
                "morning": "Prague Castle",
                "afternoon": "Petřín Tower",
                "evening": "River cruise",
                "breakfast_spot": "Café Louvre - famous historic café, excellent breakfast buffet",
                "lunch_spot": "Castle area café",
                "dinner_spot": "Cruise dinner",
            },
            "day_3": {
                "morning": "Zoo visit",
                "afternoon": "Local park",
                "evening": "Relaxed dinner",
                "breakfast_spot": "Hotel breakfast buffet - pancakes, fruit, yogurt for kids",
                "lunch_spot": "Zoo restaurant",
                "dinner_spot": "Pizza near hotel",
            },
            "tips": ["Bring Czech crowns for small purchases"],
            "_cost": 0.02,
            "_tokens": {"total": 180},
        }
        mock_claude_client.analyze.return_value = mock_itinerary

        result = await generator.generate_itinerary(trip, save_to_db=False)

        # Verify breakfast information is meaningful
        for day_num in range(1, 4):
            day_key = f"day_{day_num}"
            breakfast = result[day_key]["breakfast_spot"]

            # Check breakfast spots are not empty or generic
            assert len(breakfast) > 10, f"{day_key} breakfast spot too generic"
            # Should contain actual establishment name or description
            assert "-" in breakfast or "breakfast" in breakfast.lower() or "café" in breakfast.lower(), \
                f"{day_key} breakfast spot lacks detail"

    async def test_weather_backup_plans_included(
        self, generator, mock_claude_client
    ):
        """Test that each day includes weather backup plans."""
        trip = TripPackage(
            id=1,
            package_type="family",
            destination_city="Lisbon",
            departure_date=date.today() + timedelta(days=30),
            return_date=date.today() + timedelta(days=33),
            num_nights=3,
            total_price=950.00,
            ai_score=80.0,
        )

        mock_itinerary = {
            "day_1": {
                "morning": "Belém monuments",
                "afternoon": "Alfama walk",
                "evening": "Fado dinner",
                "breakfast_spot": "Pasteis de Belém",
                "lunch_spot": "Time Out Market",
                "dinner_spot": "Fado restaurant",
                "weather_backup": "Lisbon Oceanarium - world-class aquarium, 2-3 hours",
            },
            "day_2": {
                "morning": "Tram 28",
                "afternoon": "São Jorge Castle",
                "evening": "Chiado shopping",
                "breakfast_spot": "Fabrica Coffee",
                "lunch_spot": "Castle café",
                "dinner_spot": "Chiado bistro",
                "weather_backup": "Pavilhão do Conhecimento - science museum with kids area",
            },
            "day_3": {
                "morning": "Cascais beach",
                "afternoon": "Beach play",
                "evening": "Return journey",
                "breakfast_spot": "Hotel",
                "lunch_spot": "Beach café",
                "dinner_spot": "Airport area",
                "weather_backup": "Colombo Shopping Centre - has kids play area and cinema",
            },
            "tips": ["Lisbon Card saves money"],
            "_cost": 0.025,
            "_tokens": {"total": 190},
        }
        mock_claude_client.analyze.return_value = mock_itinerary

        result = await generator.generate_itinerary(trip, save_to_db=False)

        # Verify weather backup plans exist for each day
        for day_num in range(1, 4):
            day_key = f"day_{day_num}"
            assert "weather_backup" in result[day_key], f"Missing weather_backup in {day_key}"
            backup = result[day_key]["weather_backup"]
            assert len(backup) > 10, f"Weather backup for {day_key} too generic"

    async def test_tips_and_packing_essentials_populated(
        self, generator, mock_claude_client
    ):
        """Test that tips and packing essentials are present and useful."""
        trip = TripPackage(
            id=1,
            package_type="family",
            destination_city="Barcelona",
            departure_date=date.today() + timedelta(days=30),
            return_date=date.today() + timedelta(days=33),
            num_nights=3,
            total_price=1150.00,
            ai_score=83.0,
        )

        mock_itinerary = {
            "day_1": {"morning": "Activity", "afternoon": "Activity", "evening": "Activity",
                     "breakfast_spot": "Café", "lunch_spot": "Rest", "dinner_spot": "Tapas"},
            "day_2": {"morning": "Activity", "afternoon": "Activity", "evening": "Activity",
                     "breakfast_spot": "Café", "lunch_spot": "Rest", "dinner_spot": "Tapas"},
            "day_3": {"morning": "Activity", "afternoon": "Activity", "evening": "Activity",
                     "breakfast_spot": "Café", "lunch_spot": "Rest", "dinner_spot": "Tapas"},
            "tips": [
                "Metro T10 ticket is most economical for families",
                "Most restaurants close 3-5pm, plan accordingly",
                "Sagrada Familia needs advance booking",
                "Spanish dinner times are late - eat at 6pm for kids",
            ],
            "packing_essentials": [
                "Lightweight stroller (Barcelona is walkable but tiring)",
                "Sun protection - hats, sunscreen SPF 50+",
                "Reusable water bottles (fountains everywhere)",
                "Small first aid kit",
                "Snacks for hangry moments",
            ],
            "_cost": 0.03,
            "_tokens": {"total": 220},
        }
        mock_claude_client.analyze.return_value = mock_itinerary

        result = await generator.generate_itinerary(trip, save_to_db=False)

        # Verify tips exist and are meaningful
        assert "tips" in result, "Missing tips section"
        assert isinstance(result["tips"], list), "Tips should be a list"
        assert len(result["tips"]) >= 3, "Should have at least 3 tips"
        for tip in result["tips"]:
            assert len(tip) > 10, "Tips should be detailed, not generic"

        # Verify packing essentials
        assert "packing_essentials" in result, "Missing packing essentials"
        assert isinstance(result["packing_essentials"], list), "Packing essentials should be a list"
        assert len(result["packing_essentials"]) >= 3, "Should have at least 3 packing items"


class TestItineraryEventIntegration:
    """
    Integration tests for event inclusion in itineraries.

    Tests from Issue #72: Ensure events from trip package are properly
    integrated into the generated itinerary.
    """

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
        return session

    @pytest.fixture
    def generator(self, mock_claude_client, mock_db_session):
        """Create ItineraryGenerator instance."""
        return ItineraryGenerator(
            claude_client=mock_claude_client,
            db_session=mock_db_session,
            min_score_threshold=70.0,
        )

    async def test_package_events_appear_in_itinerary(
        self, generator, mock_claude_client
    ):
        """Test that events from the trip package are referenced in the itinerary."""
        departure = date.today() + timedelta(days=30)

        # Create trip with specific events
        trip = TripPackage(
            id=1,
            package_type="family",
            destination_city="Lisbon",
            departure_date=departure,
            return_date=departure + timedelta(days=3),
            num_nights=3,
            total_price=1000.00,
            ai_score=85.0,
            events_json={
                "events": [
                    {
                        "title": "Lisbon Oceanarium",
                        "event_date": str(departure + timedelta(days=1)),
                        "category": "family",
                        "description": "Amazing marine life exhibits",
                    },
                    {
                        "title": "Puppet Show at Teatro Maria Matos",
                        "event_date": str(departure + timedelta(days=2)),
                        "category": "kids",
                        "description": "Traditional Portuguese puppet theater",
                    },
                ]
            },
        )

        # Mock itinerary that references the events
        mock_itinerary = {
            "day_1": {
                "morning": "Belém Tower visit at 9am",
                "afternoon": "Nap time, then nearby park",
                "evening": "Dinner in Belém district",
                "breakfast_spot": "Pasteis de Belém",
                "lunch_spot": "Near tower",
                "dinner_spot": "Local tavern",
                "weather_backup": "Lisbon Oceanarium",
            },
            "day_2": {
                "morning": "Visit the Lisbon Oceanarium at 10am - kids will love the shark tunnel and ray pool. Allow 2-3 hours. The oceanarium is one of the best in Europe.",
                "afternoon": "Nap time at accommodation 1-2:30pm. Afternoon at Parque das Nações waterfront.",
                "evening": "Casual dinner at the park",
                "breakfast_spot": "Hotel breakfast",
                "lunch_spot": "Oceanarium café",
                "dinner_spot": "Parque restaurant",
                "weather_backup": "Shopping centre nearby",
            },
            "day_3": {
                "morning": "São Jorge Castle exploration",
                "afternoon": "Attend the Puppet Show at Teatro Maria Matos at 3pm - traditional Portuguese puppets, perfect for ages 3-6. Book tickets in advance.",
                "evening": "Early dinner before flight prep",
                "breakfast_spot": "Local bakery",
                "lunch_spot": "Castle area café",
                "dinner_spot": "Near accommodation",
                "weather_backup": "Museum nearby",
            },
            "tips": ["Book Oceanarium tickets online", "Puppet show is in Portuguese but visual"],
            "packing_essentials": ["Stroller", "Sunscreen"],
            "_cost": 0.025,
            "_tokens": {"total": 200},
        }
        mock_claude_client.analyze.return_value = mock_itinerary

        result = await generator.generate_itinerary(trip, save_to_db=False)

        # Verify event titles appear in the itinerary content
        itinerary_text = str(result).lower()

        assert "oceanarium" in itinerary_text, "Event 'Lisbon Oceanarium' should appear in itinerary"
        assert "puppet" in itinerary_text, "Event 'Puppet Show' should appear in itinerary"

    async def test_events_info_passed_to_claude_prompt(
        self, generator, mock_claude_client
    ):
        """Test that events information is properly passed to Claude API."""
        departure = date.today() + timedelta(days=30)

        trip = TripPackage(
            id=1,
            package_type="family",
            destination_city="Barcelona",
            departure_date=departure,
            return_date=departure + timedelta(days=3),
            num_nights=3,
            total_price=1200.00,
            ai_score=88.0,
            events_json={
                "events": [
                    {
                        "title": "FC Barcelona Match",
                        "event_date": str(departure + timedelta(days=1)),
                        "category": "sports",
                    },
                    {
                        "title": "Magic Fountain Show",
                        "event_date": str(departure + timedelta(days=2)),
                        "category": "entertainment",
                    },
                ]
            },
        )

        mock_itinerary = {
            "day_1": {"morning": "A", "afternoon": "B", "evening": "C",
                     "breakfast_spot": "D", "lunch_spot": "E", "dinner_spot": "F"},
            "day_2": {"morning": "A", "afternoon": "B", "evening": "C",
                     "breakfast_spot": "D", "lunch_spot": "E", "dinner_spot": "F"},
            "day_3": {"morning": "A", "afternoon": "B", "evening": "C",
                     "breakfast_spot": "D", "lunch_spot": "E", "dinner_spot": "F"},
            "tips": ["Tip"],
            "_cost": 0.02,
            "_tokens": {"total": 150},
        }
        mock_claude_client.analyze.return_value = mock_itinerary

        await generator.generate_itinerary(trip, save_to_db=False)

        # Verify Claude was called with event information
        mock_claude_client.analyze.assert_called_once()
        call_kwargs = mock_claude_client.analyze.call_args.kwargs

        prompt_data = call_kwargs["data"]
        assert "events_list" in prompt_data, "Events should be passed to Claude"

        events_text = prompt_data["events_list"]
        assert "FC Barcelona Match" in events_text or "sports" in events_text.lower(), \
            "Event details should be in prompt data"

    async def test_no_events_handling(self, generator, mock_claude_client):
        """Test itinerary generation when no events are available."""
        trip = TripPackage(
            id=1,
            package_type="family",
            destination_city="Prague",
            departure_date=date.today() + timedelta(days=30),
            return_date=date.today() + timedelta(days=33),
            num_nights=3,
            total_price=900.00,
            ai_score=75.0,
            events_json=None,  # No events
        )

        mock_itinerary = {
            "day_1": {
                "morning": "Old Town Square exploration - Astronomical Clock, plenty of cafés",
                "afternoon": "Nap time, then Charles Bridge walk",
                "evening": "Traditional Czech dinner",
                "breakfast_spot": "Café Savoy",
                "lunch_spot": "Lokál pub",
                "dinner_spot": "U Fleků",
                "weather_backup": "National Museum",
            },
            "day_2": {
                "morning": "Prague Castle - arrive early to avoid crowds",
                "afternoon": "Nap, then Petřín Tower and funicular ride",
                "evening": "River cruise dinner",
                "breakfast_spot": "Café Louvre",
                "lunch_spot": "Castle café",
                "dinner_spot": "Dinner cruise",
                "weather_backup": "Toy Museum",
            },
            "day_3": {
                "morning": "Prague Zoo - one of the best in Europe",
                "afternoon": "Final nap, souvenir shopping",
                "evening": "Farewell dinner",
                "breakfast_spot": "Hotel buffet",
                "lunch_spot": "Zoo restaurant",
                "dinner_spot": "Old Town restaurant",
                "weather_backup": "Shopping mall with play area",
            },
            "tips": ["Tram 22 is your friend", "Most places accept cards"],
            "packing_essentials": ["Warm layers", "Comfortable shoes"],
            "_cost": 0.02,
            "_tokens": {"total": 180},
        }
        mock_claude_client.analyze.return_value = mock_itinerary

        # Should succeed even without events
        result = await generator.generate_itinerary(trip, save_to_db=False)

        assert result is not None
        assert "day_1" in result
        assert "day_2" in result
        assert "day_3" in result

        # Verify events_list in prompt indicates no events
        mock_claude_client.analyze.assert_called_once()
        call_kwargs = mock_claude_client.analyze.call_args.kwargs
        events_text = call_kwargs["data"]["events_list"]

        assert "no specific events" in events_text.lower() or "research local" in events_text.lower(), \
            "Should indicate no events found"

    async def test_multiple_events_on_same_day(self, generator, mock_claude_client):
        """Test handling of multiple events scheduled on the same day."""
        departure = date.today() + timedelta(days=30)
        same_day = departure + timedelta(days=1)

        trip = TripPackage(
            id=1,
            package_type="family",
            destination_city="Barcelona",
            departure_date=departure,
            return_date=departure + timedelta(days=3),
            num_nights=3,
            total_price=1300.00,
            ai_score=90.0,
            events_json={
                "events": [
                    {
                        "title": "Morning Market Tour",
                        "event_date": str(same_day),
                        "category": "culture",
                    },
                    {
                        "title": "CosmoCaixa Science Museum",
                        "event_date": str(same_day),
                        "category": "education",
                    },
                    {
                        "title": "Font Màgica Light Show",
                        "event_date": str(same_day),
                        "category": "entertainment",
                    },
                ]
            },
        )

        mock_itinerary = {
            "day_1": {
                "morning": "Beach time",
                "afternoon": "Nap and park",
                "evening": "Dinner",
                "breakfast_spot": "Café",
                "lunch_spot": "Beach bar",
                "dinner_spot": "Tapas",
            },
            "day_2": {
                "morning": "Start with Morning Market Tour at La Boqueria at 9am - colorful stalls, sample fruits",
                "afternoon": "After nap, visit CosmoCaixa Science Museum at 3:30pm - interactive exhibits perfect for kids ages 3-6",
                "evening": "Evening Font Màgica Light Show at Montjuïc at 9pm (kids can nap beforehand) - magical water and light display",
                "breakfast_spot": "Market breakfast",
                "lunch_spot": "Near Boqueria",
                "dinner_spot": "Before light show",
            },
            "day_3": {
                "morning": "Park Güell",
                "afternoon": "Rest time",
                "evening": "Farewell dinner",
                "breakfast_spot": "Local café",
                "lunch_spot": "Park area",
                "dinner_spot": "Gothic Quarter",
            },
            "tips": ["Three events in one day is ambitious with young kids - be flexible"],
            "packing_essentials": ["Stroller", "Snacks"],
            "_cost": 0.03,
            "_tokens": {"total": 250},
        }
        mock_claude_client.analyze.return_value = mock_itinerary

        result = await generator.generate_itinerary(trip, save_to_db=False)

        # Verify all events from same day appear in itinerary
        day_2_content = str(result["day_2"]).lower()

        assert "market" in day_2_content, "Morning Market Tour should be referenced"
        assert "cosmocaixa" in day_2_content or "science" in day_2_content, \
            "Science Museum should be referenced"
        assert "font" in day_2_content or "light show" in day_2_content or "magic" in day_2_content, \
            "Light show should be referenced"
