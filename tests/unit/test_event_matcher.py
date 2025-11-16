"""
Unit tests for EventMatcher.

Tests the event matching logic, age appropriateness filtering,
and categorization with mocked database to avoid actual DB operations.
"""

import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, Mock

from app.orchestration.event_matcher import EventMatcher
from app.models.event import Event
from app.models.trip_package import TripPackage


class TestEventMatcher:
    """Test suite for EventMatcher class."""

    @pytest.fixture
    def mock_db_session(self):
        """Create mock async database session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def event_matcher(self, mock_db_session):
        """Create EventMatcher instance with mocked database session."""
        return EventMatcher(mock_db_session)

    @pytest.fixture
    def sample_events(self):
        """Sample events for testing."""
        return [
            Mock(
                spec=Event,
                id=1,
                destination_city="Lisbon",
                title="Kids Playground Festival",
                description="Fun activities for children aged 3-10",
                category="family",
                event_date=date(2025, 12, 22),
                end_date=None,
                price_range="free",
                ai_relevance_score=Decimal("8.5"),
            ),
            Mock(
                spec=Event,
                id=2,
                destination_city="Lisbon",
                title="Wine Tasting at Sunset",
                description="Adults only wine tasting experience",
                category="parent_escape",
                event_date=date(2025, 12, 23),
                end_date=None,
                price_range="€20-50",
                ai_relevance_score=Decimal("7.0"),
            ),
            Mock(
                spec=Event,
                id=3,
                destination_city="Lisbon",
                title="Historical Walking Tour",
                description="Explore Lisbon's rich history",
                category="cultural",
                event_date=date(2025, 12, 24),
                end_date=None,
                price_range="<€20",
                ai_relevance_score=Decimal("9.0"),
            ),
            Mock(
                spec=Event,
                id=4,
                destination_city="Lisbon",
                title="Nightclub Party 18+",
                description="Adults only nightclub event",
                category="parent_escape",
                event_date=date(2025, 12, 25),
                end_date=None,
                price_range="€50+",
                ai_relevance_score=Decimal("6.0"),
            ),
            Mock(
                spec=Event,
                id=5,
                destination_city="Lisbon",
                title="Family Beach Day",
                description="Beach activities for the whole family",
                category="family",
                event_date=date(2025, 12, 26),
                end_date=date(2025, 12, 27),  # Multi-day event
                price_range="free",
                ai_relevance_score=Decimal("8.0"),
            ),
        ]

    @pytest.fixture
    def sample_packages(self):
        """Sample trip packages for testing."""
        return [
            Mock(
                spec=TripPackage,
                id=1,
                destination_city="Lisbon",
                departure_date=date(2025, 12, 20),
                return_date=date(2025, 12, 27),
                package_type="family",
                events_json=None,
            ),
            Mock(
                spec=TripPackage,
                id=2,
                destination_city="Barcelona",
                departure_date=date(2025, 12, 20),
                return_date=date(2025, 12, 27),
                package_type="parent_escape",
                events_json=None,
            ),
        ]

    def test_initialization(self, event_matcher, mock_db_session):
        """Test that EventMatcher initializes with database session."""
        assert event_matcher.db == mock_db_session

    def test_filter_by_age_appropriateness_excludes_adult_content(
        self, event_matcher, sample_events
    ):
        """Test that adult-only events are excluded for family packages."""
        # Filter the events
        appropriate = event_matcher.filter_by_age_appropriateness(sample_events)

        # Should exclude the nightclub (id=4) and wine tasting (id=2)
        event_ids = [e.id for e in appropriate]
        assert 4 not in event_ids  # Nightclub should be excluded
        assert 2 not in event_ids  # Wine tasting should be excluded
        assert 1 in event_ids  # Kids Playground should be included
        assert 3 in event_ids  # Cultural tour should be included
        assert 5 in event_ids  # Family Beach Day should be included

    def test_filter_by_age_appropriateness_includes_family_keywords(
        self, event_matcher
    ):
        """Test that events with family keywords are included."""
        events = [
            Mock(
                spec=Event,
                id=1,
                title="Puppet Show for Children",
                description="Entertainment for kids",
                category="cultural",
            ),
            Mock(
                spec=Event,
                id=2,
                title="Museum Exhibition",
                description="General exhibition",
                category="cultural",
            ),
        ]

        appropriate = event_matcher.filter_by_age_appropriateness(events)

        # Puppet show should be included (has "children" keyword)
        assert any(e.id == 1 for e in appropriate)

    def test_filter_by_age_appropriateness_with_custom_ages(
        self, event_matcher, sample_events
    ):
        """Test age appropriateness with custom kids ages."""
        # Should work the same regardless of specific ages for basic filtering
        appropriate = event_matcher.filter_by_age_appropriateness(
            sample_events, kids_ages=[5, 8]
        )

        # Should still exclude adult-only content
        event_ids = [e.id for e in appropriate]
        assert 4 not in event_ids  # Nightclub excluded
        assert 2 not in event_ids  # Wine tasting excluded

    def test_categorize_for_package_type_family(self, event_matcher, sample_events):
        """Test categorization for family package type."""
        categorized = event_matcher.categorize_for_package_type(
            sample_events, "family"
        )

        # Should keep only family and cultural events
        categories = [e.category for e in categorized]
        assert "family" in categories
        assert "cultural" in categories
        assert "parent_escape" not in categories

    def test_categorize_for_package_type_parent_escape(
        self, event_matcher, sample_events
    ):
        """Test categorization for parent escape package type."""
        categorized = event_matcher.categorize_for_package_type(
            sample_events, "parent_escape"
        )

        # Should keep only parent_escape and cultural events
        categories = [e.category for e in categorized]
        assert "parent_escape" in categories
        assert "cultural" in categories
        # Family events might still be in the list (depends on sample data)

    def test_categorize_for_package_type_unknown(
        self, event_matcher, sample_events
    ):
        """Test categorization for unknown package type returns all events."""
        categorized = event_matcher.categorize_for_package_type(
            sample_events, "unknown_type"
        )

        # Should return all events for unknown type
        assert len(categorized) == len(sample_events)

    def test_rank_events_by_relevance_sorts_by_ai_score(self, event_matcher):
        """Test that events are sorted by AI relevance score."""
        package = Mock(
            spec=TripPackage,
            departure_date=date(2025, 12, 20),
            return_date=date(2025, 12, 27),
        )

        events = [
            Mock(
                spec=Event,
                id=1,
                event_date=date(2025, 12, 22),
                end_date=None,
                price_range="€20-50",
                ai_relevance_score=Decimal("5.0"),
            ),
            Mock(
                spec=Event,
                id=2,
                event_date=date(2025, 12, 23),
                end_date=None,
                price_range="free",
                ai_relevance_score=Decimal("9.0"),
            ),
            Mock(
                spec=Event,
                id=3,
                event_date=date(2025, 12, 24),
                end_date=None,
                price_range="<€20",
                ai_relevance_score=Decimal("7.5"),
            ),
        ]

        ranked = event_matcher.rank_events_by_relevance(events, package)

        # Should be sorted by AI score (highest first)
        # Event 2 (9.0) should be first, Event 3 (7.5) second, Event 1 (5.0) third
        # But Event 2 also gets bonus for being free
        assert ranked[0].id == 2  # Highest AI score + free
        assert ranked[1].id == 3  # Medium AI score
        assert ranked[2].id == 1  # Lowest AI score

    def test_rank_events_by_relevance_free_events_bonus(self, event_matcher):
        """Test that free events get bonus points in ranking."""
        package = Mock(
            spec=TripPackage,
            departure_date=date(2025, 12, 20),
            return_date=date(2025, 12, 27),
        )

        events = [
            Mock(
                spec=Event,
                id=1,
                event_date=date(2025, 12, 22),
                end_date=None,
                price_range="€50+",
                ai_relevance_score=Decimal("7.0"),
            ),
            Mock(
                spec=Event,
                id=2,
                event_date=date(2025, 12, 23),
                end_date=None,
                price_range="free",
                ai_relevance_score=Decimal("7.0"),  # Same AI score
            ),
        ]

        ranked = event_matcher.rank_events_by_relevance(events, package)

        # Free event should rank higher despite same AI score
        assert ranked[0].id == 2  # Free event
        assert ranked[1].id == 1  # Paid event

    def test_rank_events_by_relevance_limits_to_10(self, event_matcher):
        """Test that ranking returns maximum 10 events."""
        package = Mock(
            spec=TripPackage,
            departure_date=date(2025, 12, 20),
            return_date=date(2025, 12, 27),
        )

        # Create 15 events
        events = [
            Mock(
                spec=Event,
                id=i,
                event_date=date(2025, 12, 22),
                end_date=None,
                price_range="free",
                ai_relevance_score=Decimal(str(10 - i * 0.5)),
            )
            for i in range(15)
        ]

        ranked = event_matcher.rank_events_by_relevance(events, package)

        # Should return only top 10
        assert len(ranked) == 10

    def test_rank_events_by_relevance_handles_none_ai_score(self, event_matcher):
        """Test ranking handles events without AI scores."""
        package = Mock(
            spec=TripPackage,
            departure_date=date(2025, 12, 20),
            return_date=date(2025, 12, 27),
        )

        events = [
            Mock(
                spec=Event,
                id=1,
                event_date=date(2025, 12, 22),
                end_date=None,
                price_range="free",
                ai_relevance_score=None,  # No AI score
            ),
            Mock(
                spec=Event,
                id=2,
                event_date=date(2025, 12, 23),
                end_date=None,
                price_range="€20-50",
                ai_relevance_score=Decimal("8.0"),
            ),
        ]

        ranked = event_matcher.rank_events_by_relevance(events, package)

        # Should handle gracefully (event with score should rank higher)
        assert len(ranked) == 2
        assert ranked[0].id == 2  # Has AI score

    def test_rank_events_by_relevance_empty_list(self, event_matcher):
        """Test ranking with empty event list."""
        package = Mock(spec=TripPackage)
        ranked = event_matcher.rank_events_by_relevance([], package)
        assert len(ranked) == 0

    @pytest.mark.asyncio
    async def test_find_events_for_trip_single_day_events(
        self, event_matcher, mock_db_session
    ):
        """Test finding single-day events during trip dates."""
        # Mock database query result
        mock_result = MagicMock()
        mock_events = [
            Mock(
                spec=Event,
                id=1,
                destination_city="Lisbon",
                event_date=date(2025, 12, 22),
                end_date=None,
            ),
            Mock(
                spec=Event,
                id=2,
                destination_city="Lisbon",
                event_date=date(2025, 12, 25),
                end_date=None,
            ),
        ]

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_events
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        # Find events
        events = await event_matcher.find_events_for_trip(
            destination="Lisbon",
            start_date=date(2025, 12, 20),
            end_date=date(2025, 12, 27),
        )

        # Should return the mocked events
        assert len(events) == 2
        assert events[0].id == 1
        assert events[1].id == 2
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_events_for_trip_multi_day_events(
        self, event_matcher, mock_db_session
    ):
        """Test finding multi-day events that overlap with trip."""
        # Mock database query result
        mock_result = MagicMock()
        mock_events = [
            Mock(
                spec=Event,
                id=1,
                destination_city="Barcelona",
                event_date=date(2025, 12, 18),  # Starts before trip
                end_date=date(2025, 12, 22),  # Ends during trip
            ),
        ]

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_events
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        # Find events
        events = await event_matcher.find_events_for_trip(
            destination="Barcelona",
            start_date=date(2025, 12, 20),
            end_date=date(2025, 12, 27),
        )

        # Should return the multi-day event
        assert len(events) == 1
        assert events[0].id == 1

    @pytest.mark.asyncio
    async def test_match_events_to_packages_family(
        self, event_matcher, mock_db_session, sample_packages, sample_events
    ):
        """Test matching events to family package."""
        # Get family package
        family_package = sample_packages[0]

        # Mock database query result
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = sample_events
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        # Match events
        packages = await event_matcher.match_events_to_packages([family_package])

        # Should have events assigned
        assert packages[0].events_json is not None
        assert isinstance(packages[0].events_json, list)
        assert len(packages[0].events_json) > 0

        # Should only contain family and cultural events (not adult-only)
        # Event IDs 1, 3, 5 should be included (family/cultural, age-appropriate)
        # Events 2, 4 should be excluded (adult-only)
        for event_id in packages[0].events_json:
            assert event_id in [1, 3, 5]

    @pytest.mark.asyncio
    async def test_match_events_to_packages_parent_escape(
        self, event_matcher, mock_db_session, sample_packages, sample_events
    ):
        """Test matching events to parent escape package."""
        # Get parent escape package
        parent_package = sample_packages[1]
        parent_package.destination_city = "Lisbon"  # Match sample events

        # Mock database query result
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = sample_events
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        # Match events
        packages = await event_matcher.match_events_to_packages([parent_package])

        # Should have events assigned
        assert packages[0].events_json is not None
        assert isinstance(packages[0].events_json, list)

        # Should contain parent_escape and cultural events
        # Events 2, 3, 4 should potentially be included (parent_escape/cultural)
        # Events 1, 5 should be excluded (family category)
        for event_id in packages[0].events_json:
            # Get the corresponding event
            event = next(e for e in sample_events if e.id == event_id)
            assert event.category in ["parent_escape", "cultural"]

    @pytest.mark.asyncio
    async def test_match_events_to_packages_no_events(
        self, event_matcher, mock_db_session, sample_packages
    ):
        """Test matching when no events are found."""
        # Mock database query returning empty result
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        # Match events
        packages = await event_matcher.match_events_to_packages(sample_packages)

        # Should have empty events list
        for package in packages:
            assert package.events_json == []

    @pytest.mark.asyncio
    async def test_match_events_to_packages_multiple_packages(
        self, event_matcher, mock_db_session, sample_packages, sample_events
    ):
        """Test matching events to multiple packages."""
        # Mock database query result
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = sample_events
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        # Both packages should get events assigned
        packages = await event_matcher.match_events_to_packages(sample_packages)

        # Each package should be processed
        assert len(packages) == 2
        # Database should be queried for each package
        assert mock_db_session.execute.call_count == 2
