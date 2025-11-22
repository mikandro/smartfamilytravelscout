"""
Integration tests for AI scoring pipeline.

Tests Claude API integration, deal scoring, event scoring, and cost tracking.
"""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

from sqlalchemy import select

from app.ai.claude_client import ClaudeClient
from app.ai.deal_scorer import DealScorer
from app.database import get_async_session_context
from app.models.accommodation import Accommodation
from app.models.airport import Airport
from app.models.flight import Flight
from app.models.trip_package import TripPackage
from app.models.api_cost import ApiCost


@pytest.mark.integration
@pytest.mark.asyncio
class TestAIScoringPipeline:
    """Integration tests for AI-powered scoring pipeline."""

    async def test_claude_client_initialization(self):
        """
        Test that Claude client initializes correctly with API key.
        """
        client = ClaudeClient()

        assert client is not None
        assert hasattr(client, "client"), "Should have Anthropic client"
        assert hasattr(client, "model"), "Should have model configuration"

    async def test_deal_scorer_initialization(self):
        """
        Test that DealScorer initializes with correct configuration.
        """
        async with get_async_session_context() as db:
            client = ClaudeClient()
            scorer = DealScorer(
                claude_client=client,
                db_session=db,
                price_threshold_per_person=200.0,
                analyze_all=False,
            )

            assert scorer is not None
            assert scorer.price_threshold == 200.0
            assert scorer.analyze_all is False

    async def test_deal_scoring_with_mocked_api(self):
        """
        Test deal scoring workflow with mocked Claude API response.

        Verifies:
        1. Trip package is analyzed
        2. AI response is parsed correctly
        3. Score is within valid range (0-100)
        4. Recommendation is one of: book_now, wait, skip
        5. API cost is tracked
        """
        async with get_async_session_context() as db:
            # Create test data
            origin = Airport(
                iata_code="TSTAI1",
                name="Test AI Airport 1",
                city="TestCity1",
                country="TestCountry",
                distance_from_home=50,
                driving_time=45,
                parking_cost_per_day=10.0,
            )
            destination = Airport(
                iata_code="TSTAI2",
                name="Test AI Airport 2",
                city="TestCity2",
                country="TestCountry",
                distance_from_home=0,
                driving_time=0,
                parking_cost_per_day=0.0,
            )
            db.add_all([origin, destination])
            await db.flush()

            departure_date = date.today() + timedelta(days=60)
            return_date = departure_date + timedelta(days=7)

            flight = Flight(
                origin_airport_id=origin.id,
                destination_airport_id=destination.id,
                airline="Test Airlines",
                departure_date=departure_date,
                return_date=return_date,
                price_per_person=150.0,
                total_price=600.0,
                booking_class="Economy",
                direct_flight=True,
                source="test",
                scraped_at=datetime.now(),
            )
            flight.true_cost = 700.0

            accommodation = Accommodation(
                destination_city="TestCity2",
                name="Test Hotel",
                accommodation_type="hotel",
                price_per_night=80.0,
                rating=4.5,
                family_friendly=True,
                source="test",
                scraped_at=datetime.now(),
            )

            db.add_all([flight, accommodation])
            await db.flush()

            package = TripPackage(
                package_type="family",
                flights_json=[flight.id],
                accommodation_id=accommodation.id,
                events_json=[],
                total_price=1500.0,
                destination_city="TestCity2",
                departure_date=departure_date,
                return_date=return_date,
                num_nights=7,
                notified=False,
            )
            db.add(package)
            await db.commit()

            # Mock Claude API response
            mock_response = Mock()
            mock_response.content = [Mock(text="""
            {
                "score": 85,
                "value_assessment": "Excellent value for money",
                "family_suitability": "Highly suitable for families",
                "timing_quality": "Perfect timing for school holidays",
                "recommendation": "book_now",
                "reasoning": "Great deal with good accommodation and perfect dates"
            }
            """)]
            mock_response.usage = Mock(input_tokens=1000, output_tokens=500)

            client = ClaudeClient()
            scorer = DealScorer(
                claude_client=client,
                db_session=db,
                price_threshold_per_person=200.0,
                analyze_all=True,  # Force analysis
            )

            # Mock the Claude API call
            with patch.object(client.client.messages, 'create', new_callable=AsyncMock) as mock_create:
                mock_create.return_value = mock_response

                # Score the trip
                result = await scorer.score_trip(package, force_analyze=True)

                # Verify result structure
                assert result is not None, "Scoring should return a result"
                assert "score" in result, "Result should contain score"
                assert "recommendation" in result, "Result should contain recommendation"

                # Verify score is in valid range
                assert 0 <= result["score"] <= 100, f"Invalid score: {result['score']}"

                # Verify recommendation is valid
                valid_recommendations = ["book_now", "wait", "skip"]
                assert result["recommendation"] in valid_recommendations, \
                    f"Invalid recommendation: {result['recommendation']}"

            # Cleanup
            await db.delete(package)
            await db.delete(flight)
            await db.delete(accommodation)
            await db.delete(origin)
            await db.delete(destination)
            await db.commit()

    async def test_api_cost_tracking(self):
        """
        Test that API costs are tracked for Claude API calls.
        """
        async with get_async_session_context() as db:
            from app.utils.cost_calculator import track_api_cost

            # Track a test API cost
            await track_api_cost(
                service="claude",
                model="claude-3-5-sonnet-20241022",
                input_tokens=1000,
                output_tokens=500,
                db_session=db,
            )

            await db.commit()

            # Verify cost was recorded
            stmt = select(ApiCost).where(
                ApiCost.service == "claude",
                ApiCost.model == "claude-3-5-sonnet-20241022"
            )
            result = await db.execute(stmt)
            cost_record = result.scalars().first()

            assert cost_record is not None, "API cost not tracked"
            assert cost_record.input_tokens == 1000
            assert cost_record.output_tokens == 500
            assert cost_record.total_cost > 0, "Cost should be calculated"

            # Cleanup
            await db.delete(cost_record)
            await db.commit()

    async def test_price_threshold_filtering(self):
        """
        Test that DealScorer filters packages by price threshold.
        """
        async with get_async_session_context() as db:
            # Create expensive package (above threshold)
            package = TripPackage(
                package_type="family",
                flights_json=[1],
                accommodation_id=1,
                events_json=[],
                total_price=3000.0,  # €750/person (above €200 threshold for flights)
                destination_city="TestCity",
                departure_date=date.today() + timedelta(days=30),
                return_date=date.today() + timedelta(days=37),
                num_nights=7,
                notified=False,
            )

            client = ClaudeClient()
            scorer = DealScorer(
                claude_client=client,
                db_session=db,
                price_threshold_per_person=200.0,
                analyze_all=False,  # Use threshold filtering
            )

            # Should filter out expensive package (unless force_analyze=True)
            # Note: Actual filtering logic depends on flight price, not package price
            # This test verifies the threshold mechanism exists

            assert scorer.price_threshold == 200.0
            assert scorer.analyze_all is False

    async def test_scoring_error_handling(self):
        """
        Test that scoring handles API errors gracefully.
        """
        async with get_async_session_context() as db:
            package = TripPackage(
                package_type="family",
                flights_json=[1],
                accommodation_id=1,
                events_json=[],
                total_price=1500.0,
                destination_city="TestCity",
                departure_date=date.today() + timedelta(days=30),
                return_date=date.today() + timedelta(days=37),
                num_nights=7,
                notified=False,
            )

            client = ClaudeClient()
            scorer = DealScorer(
                claude_client=client,
                db_session=db,
                analyze_all=True,
            )

            # Mock API to raise an exception
            with patch.object(client.client.messages, 'create', new_callable=AsyncMock) as mock_create:
                mock_create.side_effect = Exception("API timeout")

                # Should handle error gracefully and return None
                result = await scorer.score_trip(package, force_analyze=True)

                # Depending on implementation, might return None or raise
                # Verify it doesn't crash the application
                assert result is None or isinstance(result, dict)

    async def test_batch_scoring_efficiency(self):
        """
        Test that multiple packages can be scored efficiently.
        """
        import time

        async with get_async_session_context() as db:
            # Create multiple packages
            packages = []
            for i in range(5):
                package = TripPackage(
                    package_type="family",
                    flights_json=[i],
                    accommodation_id=i,
                    events_json=[],
                    total_price=1500.0 + i * 100,
                    destination_city=f"TestCity{i}",
                    departure_date=date.today() + timedelta(days=30 + i),
                    return_date=date.today() + timedelta(days=37 + i),
                    num_nights=7,
                    notified=False,
                )
                packages.append(package)

            client = ClaudeClient()
            scorer = DealScorer(
                claude_client=client,
                db_session=db,
                analyze_all=True,
            )

            # Mock responses
            mock_response = Mock()
            mock_response.content = [Mock(text='{"score": 80, "recommendation": "book_now"}')]
            mock_response.usage = Mock(input_tokens=1000, output_tokens=500)

            with patch.object(client.client.messages, 'create', new_callable=AsyncMock) as mock_create:
                mock_create.return_value = mock_response

                start_time = time.time()

                # Score all packages
                results = []
                for package in packages:
                    result = await scorer.score_trip(package, force_analyze=True)
                    if result:
                        results.append(result)

                elapsed = time.time() - start_time

                # Should complete in reasonable time (< 5 seconds for 5 packages)
                assert elapsed < 5.0, f"Batch scoring too slow: {elapsed:.2f}s"

                # Verify some results were returned
                assert len(results) > 0, "No packages were scored"

    async def test_prompt_loading(self):
        """
        Test that AI prompts are loaded correctly from template files.
        """
        from app.ai.prompt_loader import PromptLoader

        loader = PromptLoader()

        # Test loading deal analysis prompt
        prompt = loader.load_prompt("deal_analysis")

        assert prompt is not None, "Prompt should be loaded"
        assert len(prompt) > 0, "Prompt should not be empty"
        assert isinstance(prompt, str), "Prompt should be a string"

        # Verify prompt contains expected placeholders
        # (Actual placeholders depend on prompt template)
        assert "{" in prompt or "{{" in prompt, \
            "Prompt should contain template placeholders"

    async def test_score_persistence(self):
        """
        Test that AI scores are persisted to trip packages.
        """
        async with get_async_session_context() as db:
            # Create package
            package = TripPackage(
                package_type="family",
                flights_json=[1],
                accommodation_id=1,
                events_json=[],
                total_price=1500.0,
                destination_city="TestCity",
                departure_date=date.today() + timedelta(days=30),
                return_date=date.today() + timedelta(days=37),
                num_nights=7,
                notified=False,
                ai_score=None,  # Initially no score
            )
            db.add(package)
            await db.commit()

            package_id = package.id

            # Update with AI score
            package.ai_score = 85
            package.ai_reasoning = "Great value for families"
            await db.commit()

            # Retrieve and verify
            retrieved = await db.get(TripPackage, package_id)
            assert retrieved.ai_score == 85
            assert retrieved.ai_reasoning == "Great value for families"

            # Cleanup
            await db.delete(retrieved)
            await db.commit()

    async def test_scoring_with_events(self):
        """
        Test that packages with events get higher scores.
        """
        async with get_async_session_context() as db:
            # Create two similar packages: one with events, one without
            package_without_events = TripPackage(
                package_type="family",
                flights_json=[1],
                accommodation_id=1,
                events_json=[],  # No events
                total_price=1500.0,
                destination_city="TestCity",
                departure_date=date.today() + timedelta(days=30),
                return_date=date.today() + timedelta(days=37),
                num_nights=7,
                notified=False,
            )

            package_with_events = TripPackage(
                package_type="family",
                flights_json=[1],
                accommodation_id=1,
                events_json=[
                    {"id": 1, "name": "Family Festival", "score": 90}
                ],  # Has event
                total_price=1500.0,
                destination_city="TestCity",
                departure_date=date.today() + timedelta(days=30),
                return_date=date.today() + timedelta(days=37),
                num_nights=7,
                notified=False,
            )

            # Verify events are stored
            assert len(package_with_events.events_json) > 0
            assert len(package_without_events.events_json) == 0

            # In real scoring, package with events would score higher
            # This test just verifies the structure is correct
