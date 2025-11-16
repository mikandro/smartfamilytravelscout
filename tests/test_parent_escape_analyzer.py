"""
Tests for ParentEscapeAnalyzer.

This module tests the parent escape analyzer functionality including:
- Finding romantic destinations accessible by train from Munich
- Scoring destinations based on events and romantic appeal
- Generating trip packages for 2-3 night getaways
"""

import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.ai.parent_escape_analyzer import ParentEscapeAnalyzer, TRAIN_DESTINATIONS
from app.ai.claude_client import ClaudeClient
from app.models.accommodation import Accommodation
from app.models.event import Event
from app.models.trip_package import TripPackage


@pytest.fixture
def mock_claude_client():
    """Create a mock Claude client for testing."""
    client = MagicMock(spec=ClaudeClient)
    client.analyze = AsyncMock(return_value={
        "escape_score": 85,
        "romantic_appeal": 9,
        "accessibility_score": 8,
        "event_timing_score": 9,
        "weekend_suitability": 8,
        "highlights": [
            "World-class wine region",
            "Beautiful thermal spas",
            "Charming boutique hotels"
        ],
        "recommended_experiences": [
            {
                "activity": "Wine tasting in South Tyrol vineyards",
                "type": "wine",
                "special_timing": "Harvest season - September/October"
            },
            {
                "activity": "Thermal spa treatment at historic baths",
                "type": "spa",
                "special_timing": "anytime"
            }
        ],
        "childcare_suggestions": [
            "Professional babysitting service available in Munich",
            "Ask grandparents or family members to help",
            "Consider trusted au pair or nanny"
        ],
        "best_time_to_go": "Late September for wine harvest season",
        "recommendation": "Bolzano is an excellent romantic getaway combining world-class wines, thermal spas, and Italian culture, all accessible in under 5 hours by train.",
        "_cost": 0.15,
        "_model": "claude-sonnet-4-5-20250929",
        "_tokens": {"input": 850, "output": 420, "total": 1270}
    })
    return client


@pytest.fixture
def analyzer(mock_claude_client):
    """Create ParentEscapeAnalyzer instance with mock client."""
    return ParentEscapeAnalyzer(claude_client=mock_claude_client)


@pytest.fixture
def sample_accommodation():
    """Create a sample romantic accommodation."""
    return Accommodation(
        id=1,
        destination_city="Bolzano",
        name="Grand Hotel Terme di Comano",
        type="hotel",
        bedrooms=1,
        price_per_night=120.0,
        family_friendly=False,
        has_kitchen=False,
        has_kids_club=False,
        rating=8.5,
        review_count=250,
        source="booking.com",
        url="https://booking.com/hotel/123",
    )


@pytest.fixture
def sample_event():
    """Create a sample romantic event."""
    event_date = date.today() + timedelta(days=30)
    return Event(
        id=1,
        destination_city="Bolzano",
        title="South Tyrol Wine Festival",
        event_date=event_date,
        end_date=event_date + timedelta(days=2),
        category="wine",
        description="Annual wine tasting festival featuring local wineries",
        price_range="€20-50",
        source="eventbrite",
        url="https://eventbrite.com/event/123",
        ai_relevance_score=9.5,
    )


class TestTrainDestinations:
    """Test train destination data and configuration."""

    def test_train_destinations_exist(self):
        """Test that train destinations are configured."""
        assert len(TRAIN_DESTINATIONS) > 0
        assert "Vienna" in TRAIN_DESTINATIONS
        assert "Salzburg" in TRAIN_DESTINATIONS

    def test_train_destinations_have_required_fields(self):
        """Test that all destinations have required information."""
        for city, info in TRAIN_DESTINATIONS.items():
            assert "travel_time_hours" in info
            assert "country" in info
            assert "romantic_features" in info
            assert isinstance(info["travel_time_hours"], float)
            assert isinstance(info["romantic_features"], list)

    def test_travel_times_reasonable(self):
        """Test that most destinations are under 6 hours."""
        under_6h = [
            city for city, info in TRAIN_DESTINATIONS.items()
            if info["travel_time_hours"] <= 6.0
        ]
        # At least 80% should be under 6 hours
        assert len(under_6h) >= len(TRAIN_DESTINATIONS) * 0.8


class TestParentEscapeAnalyzer:
    """Test ParentEscapeAnalyzer class."""

    def test_analyzer_initialization(self, mock_claude_client):
        """Test analyzer initializes correctly."""
        analyzer = ParentEscapeAnalyzer(claude_client=mock_claude_client)
        assert analyzer.claude == mock_claude_client
        assert analyzer.DAILY_FOOD_COST == 80.0
        assert analyzer.DAILY_ACTIVITIES_COST == 60.0

    @pytest.mark.asyncio
    async def test_score_escape(self, analyzer, sample_accommodation, sample_event):
        """Test scoring of a romantic escape destination."""
        destination_info = TRAIN_DESTINATIONS["Bolzano"]

        result = await analyzer.score_escape(
            destination="Bolzano",
            destination_info=destination_info,
            accommodation=sample_accommodation,
            events=[sample_event],
            duration_nights=2,
            total_cost=650.0,
        )

        # Verify Claude client was called
        analyzer.claude.analyze.assert_called_once()

        # Check result structure
        assert "escape_score" in result
        assert "romantic_appeal" in result
        assert "event_timing_score" in result
        assert "recommended_experiences" in result
        assert "childcare_suggestions" in result

        # Check score is in valid range
        assert 0 <= result["escape_score"] <= 100
        assert 0 <= result["romantic_appeal"] <= 10

    def test_build_destination_summary(
        self, analyzer, sample_accommodation
    ):
        """Test building destination summary text."""
        destination_info = TRAIN_DESTINATIONS["Bolzano"]

        summary = analyzer._build_destination_summary(
            destination="Bolzano",
            destination_info=destination_info,
            accommodation=sample_accommodation,
            total_cost=650.0,
        )

        assert "Bolzano" in summary
        assert "Italy" in summary
        assert "Grand Hotel Terme di Comano" in summary
        assert "€650.00" in summary
        assert "4.5h" in summary

    def test_build_events_summary(self, analyzer, sample_event):
        """Test building events summary text."""
        # Test with events
        summary = analyzer._build_events_summary([sample_event])
        assert "South Tyrol Wine Festival" in summary
        assert "wine" in summary

        # Test without events
        empty_summary = analyzer._build_events_summary([])
        assert "No special events" in empty_summary

    @pytest.mark.asyncio
    async def test_find_romantic_accommodations(self, analyzer):
        """Test finding romantic accommodations in a city."""
        # Mock database session
        mock_db = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        accommodations = await analyzer._find_romantic_accommodations(
            mock_db, "Vienna"
        )

        # Verify query was executed
        mock_db.execute.assert_called_once()
        assert isinstance(accommodations, list)

    @pytest.mark.asyncio
    async def test_find_romantic_events(self, analyzer):
        """Test finding romantic events in a city."""
        # Mock database session
        mock_db = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        date_range = (date.today(), date.today() + timedelta(days=90))
        events = await analyzer._find_romantic_events(
            mock_db, "Vienna", date_range
        )

        # Verify query was executed
        mock_db.execute.assert_called_once()
        assert isinstance(events, list)

    @pytest.mark.asyncio
    async def test_build_package(
        self, analyzer, sample_accommodation, sample_event
    ):
        """Test building a trip package."""
        city_info = TRAIN_DESTINATIONS["Salzburg"]
        departure_date = date.today() + timedelta(days=30)
        return_date = departure_date + timedelta(days=2)

        package = await analyzer._build_package(
            city="Salzburg",
            city_info=city_info,
            accommodation=sample_accommodation,
            events=[sample_event],
            departure_date=departure_date,
            return_date=return_date,
            num_nights=2,
            max_budget=1200.0,
        )

        # Verify package was created
        assert package is not None
        assert isinstance(package, TripPackage)
        assert package.package_type == "parent_escape"
        assert package.destination_city == "Salzburg"
        assert package.num_nights == 2
        assert package.total_price <= 1200.0
        assert package.ai_score == 85  # From mock

    @pytest.mark.asyncio
    async def test_build_package_over_budget(
        self, analyzer, sample_accommodation, sample_event
    ):
        """Test that packages over budget are not created."""
        city_info = TRAIN_DESTINATIONS["Salzburg"]
        departure_date = date.today() + timedelta(days=30)
        return_date = departure_date + timedelta(days=2)

        # Set very low budget
        package = await analyzer._build_package(
            city="Salzburg",
            city_info=city_info,
            accommodation=sample_accommodation,
            events=[sample_event],
            departure_date=departure_date,
            return_date=return_date,
            num_nights=2,
            max_budget=100.0,  # Too low
        )

        # Package should be None (over budget)
        assert package is None

    @pytest.mark.asyncio
    async def test_print_escape_summary(self, analyzer, capsys):
        """Test printing escape opportunity summary."""
        # Create sample packages
        packages = [
            TripPackage(
                package_type="parent_escape",
                flights_json={"travel_method": "train"},
                accommodation_id=1,
                events_json=[],
                destination_city="Vienna",
                departure_date=date.today() + timedelta(days=30),
                return_date=date.today() + timedelta(days=32),
                num_nights=2,
                total_price=800.0,
                ai_score=90,
                ai_reasoning="Excellent romantic getaway",
                itinerary_json={
                    "highlights": ["Opera house", "Wine tasting"]
                },
            ),
            TripPackage(
                package_type="parent_escape",
                flights_json={"travel_method": "train"},
                accommodation_id=2,
                events_json=[],
                destination_city="Salzburg",
                departure_date=date.today() + timedelta(days=45),
                return_date=date.today() + timedelta(days=47),
                num_nights=2,
                total_price=650.0,
                ai_score=85,
                ai_reasoning="Charming spa town",
                itinerary_json={
                    "highlights": ["Thermal baths", "Old town"]
                },
            ),
        ]

        await analyzer.print_escape_summary(packages, show_top=10)
        # Test passes if no exceptions raised


class TestIntegration:
    """Integration tests for the full analyzer workflow."""

    @pytest.mark.asyncio
    async def test_cost_calculation_reasonable(self, analyzer):
        """Test that cost calculations are in reasonable ranges."""
        city_info = TRAIN_DESTINATIONS["Vienna"]

        # Calculate for 2 nights
        nights = 2
        accommodation_cost = 120.0 * nights
        train_cost = city_info["travel_time_hours"] * 30.0 * 2
        food_cost = analyzer.DAILY_FOOD_COST * nights
        activities_cost = analyzer.DAILY_ACTIVITIES_COST * nights

        total = train_cost + accommodation_cost + food_cost + activities_cost

        # Vienna 2-night trip should be 500-1000 EUR
        assert 500 <= total <= 1000

    def test_romantic_features_valid(self):
        """Test that all romantic features are from valid set."""
        valid_features = {"wine", "spa", "culture", "mountains", "dining"}

        for city, info in TRAIN_DESTINATIONS.items():
            features = info["romantic_features"]
            for feature in features:
                assert feature in valid_features, (
                    f"Invalid feature '{feature}' for {city}"
                )
