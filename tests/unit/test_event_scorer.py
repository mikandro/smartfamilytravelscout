"""
Unit tests for EventScorer.

Tests the AI-powered event relevance scoring with mocked Claude API
to avoid actual API calls during testing.
"""

import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from app.ai.event_scorer import EventScorer, score_events_for_destination
from app.ai.claude_client import ClaudeClient
from app.models.event import Event
from app.models.user_preference import UserPreference


class TestEventScorer:
    """Test suite for EventScorer class."""

    @pytest.fixture
    def mock_claude_client(self):
        """Create a mock ClaudeClient."""
        client = AsyncMock(spec=ClaudeClient)
        return client

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def mock_prompt_loader(self):
        """Create a mock PromptLoader."""
        loader = Mock()
        loader.load.return_value = "Test prompt template: {title} {category}"
        return loader

    @pytest.fixture
    def sample_event(self):
        """Create a sample Event instance."""
        return Event(
            id=1,
            destination_city="Lisbon",
            title="Children's Museum Interactive Exhibit",
            event_date=date(2025, 12, 15),
            category="family",
            description="Interactive science museum for kids ages 3-10",
            price_range="€10-20",
            source="eventbrite",
            url="https://example.com/event",
            ai_relevance_score=None,
        )

    @pytest.fixture
    def sample_user_preferences(self):
        """Create sample UserPreference instance."""
        return UserPreference(
            id=1,
            user_id=1,
            max_flight_price_family=200.0,
            max_flight_price_parents=300.0,
            max_total_budget_family=2000.0,
            interests=["museums", "parks", "cultural events"],
            notification_threshold=70.0,
        )

    @pytest.fixture
    def event_scorer(self, mock_claude_client, mock_db_session, mock_prompt_loader):
        """Create EventScorer instance with mocked dependencies."""
        return EventScorer(
            claude_client=mock_claude_client,
            db_session=mock_db_session,
            prompt_loader=mock_prompt_loader,
        )

    @pytest.fixture
    def mock_scoring_response(self):
        """Create a mock Claude API response for event scoring."""
        return {
            "relevance_score": 8.5,
            "age_appropriate": True,
            "min_age": 3,
            "max_age": 10,
            "category_refined": "family_event",
            "engagement_level": "high",
            "duration_suitable": True,
            "matches_interests": ["museums"],
            "reasoning": "Perfect interactive museum for young children with hands-on exhibits",
            "recommendation": "book",
            "_cost": 0.0042,
            "_model": "claude-sonnet-4-5-20250929",
            "_tokens": {"input": 150, "output": 80, "total": 230},
        }

    def test_initialization(self, event_scorer, mock_claude_client, mock_db_session):
        """Test EventScorer initializes correctly."""
        assert event_scorer.claude == mock_claude_client
        assert event_scorer.db == mock_db_session
        assert event_scorer.prompt_loader is not None

    async def test_score_event_success(
        self,
        event_scorer,
        mock_claude_client,
        sample_event,
        mock_scoring_response,
        mock_db_session,
    ):
        """Test scoring a single event successfully."""
        # Mock Claude API response
        mock_claude_client.analyze.return_value = mock_scoring_response

        # Score the event
        result = await event_scorer.score_event(
            event=sample_event,
            user_interests=["museums", "parks"],
            update_db=True,
        )

        # Verify result
        assert result["relevance_score"] == 8.5
        assert result["age_appropriate"] is True
        assert result["category_refined"] == "family_event"
        assert result["recommendation"] == "book"
        assert "museums" in result["matches_interests"]

        # Verify database update
        assert sample_event.ai_relevance_score == 8.5
        mock_db_session.commit.assert_called_once()

        # Verify Claude API was called correctly
        mock_claude_client.analyze.assert_called_once()
        call_kwargs = mock_claude_client.analyze.call_args.kwargs
        assert call_kwargs["response_format"] == "json"
        assert call_kwargs["operation"] == "event_scoring"
        assert call_kwargs["use_cache"] is True

    async def test_score_event_without_db_update(
        self,
        event_scorer,
        mock_claude_client,
        sample_event,
        mock_scoring_response,
        mock_db_session,
    ):
        """Test scoring event without updating database."""
        mock_claude_client.analyze.return_value = mock_scoring_response

        result = await event_scorer.score_event(
            event=sample_event,
            user_interests=["museums"],
            update_db=False,
        )

        assert result["relevance_score"] == 8.5
        # Database should not be updated
        assert sample_event.ai_relevance_score is None
        mock_db_session.commit.assert_not_called()

    async def test_score_event_with_no_interests(
        self,
        event_scorer,
        mock_claude_client,
        sample_event,
        mock_scoring_response,
    ):
        """Test scoring event with no user interests provided."""
        mock_claude_client.analyze.return_value = mock_scoring_response

        result = await event_scorer.score_event(
            event=sample_event,
            user_interests=None,
            update_db=False,
        )

        assert result["relevance_score"] == 8.5

        # Verify prompt data includes appropriate message for no interests
        call_kwargs = mock_claude_client.analyze.call_args.kwargs
        assert "data" in call_kwargs

    async def test_score_event_failure(
        self,
        event_scorer,
        mock_claude_client,
        sample_event,
        mock_db_session,
    ):
        """Test handling of scoring failure."""
        # Mock API failure
        mock_claude_client.analyze.side_effect = Exception("API error")

        with pytest.raises(Exception, match="API error"):
            await event_scorer.score_event(
                event=sample_event,
                user_interests=["museums"],
            )

        # Verify rollback was called
        mock_db_session.rollback.assert_called_once()

    async def test_score_events_batch_success(
        self,
        event_scorer,
        mock_claude_client,
        mock_scoring_response,
        sample_user_preferences,
    ):
        """Test batch scoring of multiple events."""
        # Create multiple events
        events = [
            Event(
                id=i,
                destination_city="Lisbon",
                title=f"Event {i}",
                event_date=date(2025, 12, 15),
                category="family",
                description=f"Description {i}",
                price_range="€10-20",
                source="eventbrite",
            )
            for i in range(1, 6)
        ]

        # Mock different scores for each event using a list of responses
        mock_responses = [
            {**mock_scoring_response, "relevance_score": 8.5, "_cost": 0.004},
            {**mock_scoring_response, "relevance_score": 6.0, "_cost": 0.004},
            {**mock_scoring_response, "relevance_score": 9.0, "_cost": 0.004},
            {**mock_scoring_response, "relevance_score": 4.5, "_cost": 0.004},
            {**mock_scoring_response, "relevance_score": 7.5, "_cost": 0.004},
        ]
        mock_claude_client.analyze.side_effect = mock_responses

        # Score batch
        results = await event_scorer.score_events_batch(
            events=events,
            user_preferences=sample_user_preferences,
            min_score_threshold=5.0,
        )

        # Verify results
        assert results["total_events"] == 5
        assert results["scored_events"] == 5
        assert results["failed_events"] == 0
        assert results["average_score"] == 7.1  # (8.5 + 6.0 + 9.0 + 4.5 + 7.5) / 5
        assert results["high_relevance_count"] == 3  # Events with score >= 7
        assert len(results["results"]) == 4  # Only events >= 5.0 threshold
        assert results["total_cost"] == 0.02  # 5 * 0.004

        # Verify results are sorted by score (highest first)
        assert results["results"][0]["score"] == 9.0
        assert results["results"][-1]["score"] == 6.0

    async def test_score_events_batch_with_failures(
        self,
        event_scorer,
        mock_claude_client,
        mock_scoring_response,
        sample_user_preferences,
    ):
        """Test batch scoring with some failures."""
        events = [
            Event(
                id=i,
                destination_city="Barcelona",
                title=f"Event {i}",
                event_date=date(2025, 12, 15),
                category="family",
                description=f"Description {i}",
            )
            for i in range(1, 4)
        ]

        # Mock: first success, second fails, third success
        mock_responses = [
            {**mock_scoring_response, "relevance_score": 8.0, "_cost": 0.004},
            Exception("API error"),
            {**mock_scoring_response, "relevance_score": 7.0, "_cost": 0.004},
        ]
        mock_claude_client.analyze.side_effect = mock_responses

        results = await event_scorer.score_events_batch(
            events=events,
            user_preferences=sample_user_preferences,
        )

        # Verify results account for failure
        assert results["total_events"] == 3
        assert results["scored_events"] == 2
        assert results["failed_events"] == 1
        assert results["average_score"] == 7.5  # (8.0 + 7.0) / 2

    async def test_get_top_events(self, event_scorer, mock_db_session):
        """Test retrieving top-scored events for a destination."""
        # Mock database query result
        mock_events = [
            Event(
                id=1,
                title="Event 1",
                destination_city="Porto",
                event_date=date(2025, 12, 15),
                ai_relevance_score=9.0,
            ),
            Event(
                id=2,
                title="Event 2",
                destination_city="Porto",
                event_date=date(2025, 12, 16),
                ai_relevance_score=8.5,
            ),
        ]

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_events
        mock_db_session.execute.return_value = mock_result

        # Get top events
        events = await event_scorer.get_top_events(
            destination_city="Porto",
            min_score=7.0,
            limit=10,
        )

        assert len(events) == 2
        assert events[0].ai_relevance_score == 9.0
        assert events[1].ai_relevance_score == 8.5

    async def test_get_unscored_events(self, event_scorer, mock_db_session):
        """Test retrieving events without scores."""
        mock_events = [
            Event(
                id=3,
                title="Unscored Event",
                destination_city="Madrid",
                event_date=date(2025, 12, 20),
                ai_relevance_score=None,
            ),
        ]

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_events
        mock_db_session.execute.return_value = mock_result

        events = await event_scorer.get_unscored_events(
            destination_city="Madrid",
            limit=50,
        )

        assert len(events) == 1
        assert events[0].ai_relevance_score is None

    def test_format_interests(self, event_scorer):
        """Test formatting of user interests for prompts."""
        # With interests
        formatted = event_scorer._format_interests(["museums", "parks", "beaches"])
        assert formatted == "museums, parks, beaches"

        # No interests
        formatted_empty = event_scorer._format_interests(None)
        assert "general family suitability" in formatted_empty.lower()

        # Empty list
        formatted_empty_list = event_scorer._format_interests([])
        assert "general family suitability" in formatted_empty_list.lower()

    async def test_get_default_user_preferences_exists(
        self, event_scorer, mock_db_session, sample_user_preferences
    ):
        """Test getting default user preferences when they exist."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = sample_user_preferences
        mock_db_session.execute.return_value = mock_result

        prefs = await event_scorer._get_default_user_preferences()

        assert prefs.user_id == 1
        assert prefs.interests == ["museums", "parks", "cultural events"]

    async def test_get_default_user_preferences_creates_default(
        self, event_scorer, mock_db_session
    ):
        """Test creating default preferences when none exist."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        prefs = await event_scorer._get_default_user_preferences()

        # Verify default preferences were created
        assert prefs.user_id == 1
        assert prefs.interests is not None
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()


class TestScoreEventsForDestination:
    """Test suite for score_events_for_destination helper function."""

    async def test_score_events_for_destination_success(self):
        """Test the convenience function for scoring destination events."""
        mock_claude = AsyncMock(spec=ClaudeClient)
        mock_db = AsyncMock()

        # Mock EventScorer methods
        with patch("app.ai.event_scorer.EventScorer") as MockScorer:
            mock_scorer_instance = AsyncMock()
            MockScorer.return_value = mock_scorer_instance

            # Mock unscored events
            mock_events = [
                Event(id=1, title="Event 1", destination_city="Lisbon"),
                Event(id=2, title="Event 2", destination_city="Lisbon"),
            ]
            mock_scorer_instance.get_unscored_events.return_value = mock_events

            # Mock batch scoring results
            mock_scorer_instance.score_events_batch.return_value = {
                "total_events": 2,
                "scored_events": 2,
                "average_score": 7.5,
            }

            # Call function
            results = await score_events_for_destination(
                "Lisbon", mock_claude, mock_db, min_score_threshold=6.0
            )

            # Verify
            assert results["total_events"] == 2
            assert results["scored_events"] == 2
            mock_scorer_instance.get_unscored_events.assert_called_once_with(
                destination_city="Lisbon"
            )
            mock_scorer_instance.score_events_batch.assert_called_once()

    async def test_score_events_for_destination_no_events(self):
        """Test when no unscored events exist."""
        mock_claude = AsyncMock(spec=ClaudeClient)
        mock_db = AsyncMock()

        with patch("app.ai.event_scorer.EventScorer") as MockScorer:
            mock_scorer_instance = AsyncMock()
            MockScorer.return_value = mock_scorer_instance
            mock_scorer_instance.get_unscored_events.return_value = []

            results = await score_events_for_destination(
                "Barcelona", mock_claude, mock_db
            )

            assert results["total_events"] == 0
            assert "No unscored events" in results["message"]
            # Batch scoring should not be called
            mock_scorer_instance.score_events_batch.assert_not_called()
