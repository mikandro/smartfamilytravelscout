"""
Unit tests for preference-based scoring functionality.
"""

import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.user_preference import UserPreference
from app.models.trip_package import TripPackage
from app.ai.deal_scorer import DealScorer
from app.utils.preference_loader import PreferenceLoader


class TestUserPreference:
    """Test UserPreference model."""

    def test_user_preference_creation(self):
        """Test creating a UserPreference object."""
        pref = UserPreference(
            user_id=1,
            max_flight_price_family=150.0,
            max_flight_price_parents=300.0,
            max_total_budget_family=2000.0,
            preferred_destinations=["Barcelona", "Lisbon"],
            avoid_destinations=["Paris"],
            interests=["beaches", "museums"],
            notification_threshold=75.0,
        )

        assert pref.user_id == 1
        assert pref.max_flight_price_family == 150.0
        assert pref.preferred_destinations == ["Barcelona", "Lisbon"]
        assert pref.avoid_destinations == ["Paris"]
        assert pref.interests == ["beaches", "museums"]

    def test_preferred_destinations_str(self):
        """Test the preferred_destinations_str property."""
        pref = UserPreference(
            user_id=1,
            max_flight_price_family=150.0,
            max_flight_price_parents=300.0,
            max_total_budget_family=2000.0,
            preferred_destinations=["Barcelona", "Lisbon", "Prague"],
        )

        assert pref.preferred_destinations_str == "Barcelona, Lisbon, Prague"

    def test_interests_str(self):
        """Test the interests_str property."""
        pref = UserPreference(
            user_id=1,
            max_flight_price_family=150.0,
            max_flight_price_parents=300.0,
            max_total_budget_family=2000.0,
            interests=["wine", "beaches", "hiking"],
        )

        assert pref.interests_str == "wine, beaches, hiking"

    def test_empty_preferences(self):
        """Test handling of empty preference lists."""
        pref = UserPreference(
            user_id=1,
            max_flight_price_family=150.0,
            max_flight_price_parents=300.0,
            max_total_budget_family=2000.0,
        )

        assert pref.preferred_destinations_str == "None"
        assert pref.interests_str == "None"


class TestPreferenceLoader:
    """Test PreferenceLoader utility."""

    def test_list_available_profiles(self):
        """Test listing available preference profiles."""
        loader = PreferenceLoader()
        profiles = loader.list_available_profiles()

        assert isinstance(profiles, list)
        # Check that some expected profiles exist
        expected_profiles = [
            "family-with-toddlers",
            "budget-conscious",
            "beach-lovers",
            "culture-lovers",
            "adventure-family",
        ]
        for profile in expected_profiles:
            assert profile in profiles

    def test_load_profile_data(self):
        """Test loading profile data from JSON."""
        loader = PreferenceLoader()
        data = loader.load_profile_data("family-with-toddlers")

        assert isinstance(data, dict)
        assert "max_flight_price_family" in data
        assert "max_total_budget_family" in data
        assert "preferred_destinations" in data
        assert data["name"] == "Family with Toddlers"

    def test_load_profile_not_found(self):
        """Test loading a non-existent profile."""
        loader = PreferenceLoader()

        with pytest.raises(FileNotFoundError):
            loader.load_profile_data("non-existent-profile")

    def test_create_user_preference(self):
        """Test creating UserPreference from profile data."""
        loader = PreferenceLoader()
        data = loader.load_profile_data("budget-conscious")

        user_pref = loader.create_user_preference(data)

        assert isinstance(user_pref, UserPreference)
        assert user_pref.max_flight_price_family == 100.0
        assert "Budapest" in user_pref.preferred_destinations
        assert "Zurich" in user_pref.avoid_destinations

    def test_load_profile(self):
        """Test loading complete profile."""
        loader = PreferenceLoader()
        user_pref = loader.load_profile("beach-lovers")

        assert isinstance(user_pref, UserPreference)
        assert user_pref.max_flight_price_family == 180.0
        assert "beaches" in user_pref.interests
        assert "Barcelona" in user_pref.preferred_destinations

    def test_get_profile_description(self):
        """Test getting profile description."""
        loader = PreferenceLoader()
        description = loader.get_profile_description("culture-lovers")

        assert isinstance(description, str)
        assert len(description) > 0
        assert "museum" in description.lower() or "culture" in description.lower()


@pytest.mark.asyncio
class TestPreferenceBasedScoring:
    """Test preference-based scoring with DealScorer."""

    @pytest.fixture
    def mock_claude_client(self):
        """Create a mock Claude client."""
        client = AsyncMock()
        client.analyze = AsyncMock(
            return_value={
                "score": 85,
                "preference_alignment": 9,
                "value_assessment": "Excellent value matching your preferences",
                "family_suitability": 8,
                "timing_quality": 7,
                "recommendation": "book_now",
                "confidence": 90,
                "reasoning": "Perfect match for beach lovers with family-friendly amenities",
                "highlights": ["Great beach location", "Within budget"],
                "concerns": [],
            }
        )
        return client

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.fixture
    def sample_user_preference(self):
        """Create a sample user preference."""
        return UserPreference(
            user_id=1,
            max_flight_price_family=150.0,
            max_flight_price_parents=300.0,
            max_total_budget_family=2000.0,
            preferred_destinations=["Barcelona", "Lisbon"],
            avoid_destinations=["Paris"],
            interests=["beaches", "museums"],
            notification_threshold=75.0,
        )

    @pytest.fixture
    def sample_trip_package(self):
        """Create a sample trip package."""
        package = TripPackage(
            id=1,
            destination_city="Barcelona",
            departure_date=date.today() + timedelta(days=60),
            return_date=date.today() + timedelta(days=67),
            num_nights=7,
            total_price=1500.0,
            price_per_person=375.0,
            package_type="family",
            flights_json={
                "origin_airport": "MUC",
                "destination_airport": "BCN",
                "airline": "Ryanair",
                "price_per_person": 120.0,
                "true_cost": 130.0,
                "direct_flight": True,
            },
        )
        return package

    async def test_score_package_with_preferences(
        self, mock_claude_client, mock_db_session, sample_user_preference, sample_trip_package
    ):
        """Test scoring a package with user preferences."""
        scorer = DealScorer(
            claude_client=mock_claude_client,
            db_session=mock_db_session,
            analyze_all=True,
        )

        result = await scorer.score_package(
            package=sample_trip_package,
            user_prefs=sample_user_preference,
            force_analyze=True,
        )

        assert result is not None
        assert result["score"] == 85
        assert result["preference_alignment"] == 9
        assert result["recommendation"] == "book_now"
        mock_claude_client.analyze.assert_called_once()

    async def test_score_package_exceeds_budget(
        self, mock_claude_client, mock_db_session, sample_user_preference, sample_trip_package
    ):
        """Test that packages exceeding budget are filtered out."""
        # Set package price above user's max budget
        sample_trip_package.total_price = 3000.0

        scorer = DealScorer(
            claude_client=mock_claude_client,
            db_session=mock_db_session,
            analyze_all=False,  # Enable filtering
        )

        result = await scorer.score_package(
            package=sample_trip_package,
            user_prefs=sample_user_preference,
        )

        # Should return None because it exceeds budget
        assert result is None
        mock_claude_client.analyze.assert_not_called()

    async def test_score_package_avoided_destination(
        self, mock_claude_client, mock_db_session, sample_user_preference, sample_trip_package
    ):
        """Test that packages to avoided destinations get low scores."""
        # Set destination to an avoided city
        sample_trip_package.destination_city = "Paris"

        scorer = DealScorer(
            claude_client=mock_claude_client,
            db_session=mock_db_session,
            analyze_all=True,
        )

        result = await scorer.score_package(
            package=sample_trip_package,
            user_prefs=sample_user_preference,
        )

        # Should return a low score for avoided destination
        assert result is not None
        assert result["score"] == 10
        assert result["preference_alignment"] == 0
        assert result["recommendation"] == "skip"
        assert "avoid list" in result["reasoning"].lower()
        # Should not call Claude API for avoided destinations
        mock_claude_client.analyze.assert_not_called()

    async def test_score_package_exceeds_flight_price(
        self, mock_claude_client, mock_db_session, sample_user_preference, sample_trip_package
    ):
        """Test that packages with expensive flights are filtered out."""
        # Set flight price above user's max
        sample_trip_package.flights_json["price_per_person"] = 200.0

        scorer = DealScorer(
            claude_client=mock_claude_client,
            db_session=mock_db_session,
            analyze_all=False,  # Enable filtering
        )

        result = await scorer.score_package(
            package=sample_trip_package,
            user_prefs=sample_user_preference,
        )

        # Should return None because flight price exceeds max
        assert result is None
        mock_claude_client.analyze.assert_not_called()

    async def test_build_prompt_data_with_preferences(
        self, mock_claude_client, mock_db_session, sample_user_preference, sample_trip_package
    ):
        """Test building prompt data with preferences."""
        scorer = DealScorer(
            claude_client=mock_claude_client,
            db_session=mock_db_session,
        )

        # Mock the database query for price history
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = []

        prompt_data = await scorer._build_prompt_data_with_preferences(
            sample_trip_package, sample_user_preference
        )

        # Check that preference data is included
        assert "max_flight_price_family" in prompt_data
        assert prompt_data["max_flight_price_family"] == 150.0
        assert "preferred_destinations" in prompt_data
        assert "Barcelona, Lisbon" in prompt_data["preferred_destinations"]
        assert "avoid_destinations" in prompt_data
        assert "Paris" in prompt_data["avoid_destinations"]
        assert "interests" in prompt_data
        assert "beaches" in prompt_data["interests"]

        # Check that base trip data is also included
        assert prompt_data["city"] == "Barcelona"
        assert prompt_data["num_nights"] == 7
        assert prompt_data["total_cost"] == 1500.0


@pytest.mark.unit
class TestPreferenceProfiles:
    """Test preference profile functionality."""

    def test_all_profiles_are_valid(self):
        """Test that all provided profiles have valid data."""
        loader = PreferenceLoader()
        profiles = loader.list_available_profiles()

        for profile_name in profiles:
            data = loader.load_profile_data(profile_name)

            # Check required fields
            assert "max_flight_price_family" in data
            assert "max_flight_price_parents" in data
            assert "max_total_budget_family" in data

            # Check that values are reasonable
            assert data["max_flight_price_family"] > 0
            assert data["max_flight_price_parents"] > 0
            assert data["max_total_budget_family"] > 0

            # Create UserPreference to ensure it works
            user_pref = loader.create_user_preference(data)
            assert user_pref is not None

    def test_profile_budget_consistency(self):
        """Test that profile budgets are consistent."""
        loader = PreferenceLoader()

        # Budget-conscious should have lowest prices
        budget = loader.load_profile_data("budget-conscious")
        assert budget["max_flight_price_family"] <= 120.0

        # Check that parent escape prices are higher than family prices
        for profile_name in loader.list_available_profiles():
            data = loader.load_profile_data(profile_name)
            assert (
                data["max_flight_price_parents"] >= data["max_flight_price_family"]
            ), f"Profile {profile_name} has inconsistent pricing"
