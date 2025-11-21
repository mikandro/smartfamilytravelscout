"""
AI-powered deal scoring system using Claude API.

This module analyzes trip packages and scores them 0-100 based on value,
suitability, and timing. Only analyzes packages under a configurable price
threshold to optimize API costs.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.claude_client import ClaudeClient
from app.ai.prompt_loader import PromptLoader
from app.config import settings
from app.models.accommodation import Accommodation
from app.models.event import Event
from app.models.flight import Flight
from app.models.price_history import PriceHistory
from app.models.trip_package import TripPackage

logger = logging.getLogger(__name__)


class DealScorer:
    """
    AI-powered deal scoring system using Claude API.

    Analyzes trip packages and provides:
    - Deal score (0-100)
    - Value assessment
    - Family suitability rating
    - Timing quality
    - Recommendation (book_now/wait/skip)
    - Detailed reasoning

    Features:
    - Configurable price threshold filtering (default: €200/person for flights)
    - Optional "analyze all" mode to bypass threshold
    - Historical price context integration
    - Event matching and relevance
    - Cost tracking and caching

    Example:
        >>> scorer = DealScorer(
        ...     claude_client=client,
        ...     db_session=session,
        ...     price_threshold_per_person=200
        ... )
        >>> result = await scorer.score_trip(trip_package)
        >>> print(f"Score: {result['score']}, Recommendation: {result['recommendation']}")
    """

    def __init__(
        self,
        claude_client: ClaudeClient,
        db_session: AsyncSession,
        price_threshold_per_person: float = 200.0,
        analyze_all: bool = False,
    ):
        """
        Initialize the deal scorer.

        Args:
            claude_client: Claude API client instance
            db_session: Database session for querying data
            price_threshold_per_person: Max flight price per person to analyze (default: €200)
            analyze_all: If True, analyze all packages regardless of price (default: False)
        """
        self.claude = claude_client
        self.db = db_session
        self.price_threshold = price_threshold_per_person
        self.analyze_all = analyze_all
        self.prompt_loader = PromptLoader()

        logger.info(
            f"Initialized DealScorer (threshold=€{price_threshold_per_person}/person, "
            f"analyze_all={analyze_all})"
        )

    async def score_trip(
        self,
        trip_package: TripPackage,
        force_analyze: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Score a trip package using Claude AI.

        Args:
            trip_package: The TripPackage to analyze
            force_analyze: If True, bypass price threshold check

        Returns:
            Dictionary with scoring results, or None if filtered out by threshold.
            Result includes:
            - score: Overall deal score (0-100)
            - value_assessment: Text assessment of price value
            - family_suitability: Rating 0-10
            - timing_quality: Rating 0-10
            - recommendation: "book_now", "wait", or "skip"
            - confidence: Confidence level (0-100)
            - reasoning: Explanation text
            - highlights: List of key selling points
            - concerns: List of potential issues

        Raises:
            ValueError: If trip package data is incomplete
        """
        try:
            # Check price threshold (unless analyze_all or force_analyze)
            if not self.analyze_all and not force_analyze:
                flight_price_per_person = self._get_flight_price_per_person(trip_package)
                if flight_price_per_person > self.price_threshold:
                    logger.info(
                        f"Skipping trip {trip_package.id}: flight price "
                        f"€{flight_price_per_person}/person exceeds threshold "
                        f"€{self.price_threshold}"
                    )
                    return None

            # Gather all required data
            prompt_data = await self._build_prompt_data(trip_package)

            # Load prompt template
            prompt = self.prompt_loader.load("deal_analysis")

            # Call Claude API
            logger.info(
                f"Analyzing trip package {trip_package.id} "
                f"({trip_package.destination_city}, €{trip_package.total_price})"
            )

            response = await self.claude.analyze(
                prompt=prompt,
                data=prompt_data,
                response_format="json",
                use_cache=True,
                max_tokens=settings.claude_max_tokens_default,
                operation="deal_scoring",
                temperature=settings.claude_temperature,
            )

            # Validate response structure
            required_fields = [
                "score",
                "value_assessment",
                "family_suitability",
                "timing_quality",
                "recommendation",
                "confidence",
                "reasoning",
            ]
            for field in required_fields:
                if field not in response:
                    logger.warning(
                        f"Missing field '{field}' in Claude response for trip {trip_package.id}"
                    )
                    response[field] = None

            # Update trip package with AI results
            await self._update_trip_package(trip_package, response)

            logger.info(
                f"Scored trip {trip_package.id}: {response['score']}/100 "
                f"({response['recommendation']}, cost=${response.get('_cost', 0):.4f})"
            )

            return response

        except Exception as e:
            logger.error(f"Error scoring trip {trip_package.id}: {e}", exc_info=True)
            raise

    async def filter_good_deals(
        self,
        packages: List[TripPackage],
        min_score: float = 70.0,
    ) -> List[Dict[str, Any]]:
        """
        Score multiple packages and filter for good deals.

        Args:
            packages: List of TripPackage objects to analyze
            min_score: Minimum score threshold (default: 70)

        Returns:
            List of dictionaries with package and scoring info, sorted by score descending.
            Each dict contains:
            - package: The TripPackage object
            - score: The AI score
            - recommendation: The recommendation
            - reasoning: The reasoning text
            - All other fields from score_trip()
        """
        results = []

        for package in packages:
            try:
                score_result = await self.score_trip(package)

                if score_result is None:
                    # Filtered out by price threshold
                    continue

                # Check if meets minimum score
                if score_result.get("score", 0) >= min_score:
                    results.append(
                        {
                            "package": package,
                            **score_result,
                        }
                    )

            except Exception as e:
                logger.error(
                    f"Error scoring package {package.id}: {e}. Skipping.",
                    exc_info=True,
                )
                continue

        # Sort by score descending
        results.sort(key=lambda x: x.get("score", 0), reverse=True)

        logger.info(
            f"Filtered {len(results)} good deals from {len(packages)} packages "
            f"(min_score={min_score})"
        )

        return results

    def _get_flight_price_per_person(self, trip_package: TripPackage) -> float:
        """
        Extract flight price per person from trip package.

        Args:
            trip_package: The trip package

        Returns:
            Flight price per person in EUR

        Raises:
            ValueError: If flight data is missing or invalid
        """
        flights_data = trip_package.flights_json

        if not flights_data:
            raise ValueError(f"Trip package {trip_package.id} has no flight data")

        # Handle different flight data structures
        if isinstance(flights_data, dict):
            # Single flight stored as dict
            price = flights_data.get("price_per_person")
            if price is None:
                raise ValueError(
                    f"Flight data missing price_per_person for trip {trip_package.id}"
                )
            return float(price)

        elif isinstance(flights_data, list) and len(flights_data) > 0:
            # Multiple flights stored as array, use first one
            price = flights_data[0].get("price_per_person")
            if price is None:
                raise ValueError(
                    f"Flight data missing price_per_person for trip {trip_package.id}"
                )
            return float(price)

        else:
            raise ValueError(
                f"Invalid flight data structure for trip {trip_package.id}"
            )

    async def _build_prompt_data(
        self, trip_package: TripPackage
    ) -> Dict[str, Any]:
        """
        Build the data dictionary for the prompt template.

        Args:
            trip_package: The trip package to analyze

        Returns:
            Dictionary with all variables needed for the prompt template
        """
        # Get flight details
        flights_data = trip_package.flights_json
        if isinstance(flights_data, dict):
            flight_info = flights_data
        elif isinstance(flights_data, list) and len(flights_data) > 0:
            flight_info = flights_data[0]
        else:
            flight_info = {}

        # Get accommodation details
        accommodation = trip_package.accommodation
        if accommodation:
            accommodation_name = accommodation.name or "Unknown"
            accommodation_type = accommodation.property_type or "Unknown"
            bedrooms = accommodation.bedrooms or "N/A"
            accommodation_price_per_night = (
                float(accommodation.price_per_night) if accommodation.price_per_night else 0
            )
            accommodation_rating = (
                float(accommodation.rating) if accommodation.rating else "N/A"
            )
            amenities = ", ".join(accommodation.amenities or []) or "Not specified"
        else:
            accommodation_name = "Not specified"
            accommodation_type = "Unknown"
            bedrooms = "N/A"
            accommodation_price_per_night = 0
            accommodation_rating = "N/A"
            amenities = "Not specified"

        # Format flight details for display
        origin = flight_info.get("origin_airport", "N/A")
        destination = flight_info.get("destination_airport", "N/A")
        airline = flight_info.get("airline", "N/A")
        flight_details = f"{origin} → {destination} via {airline}"

        flight_price_per_person = self._get_flight_price_per_person(trip_package)
        true_cost = flight_info.get("true_cost", flight_price_per_person)

        # Get price history context
        price_context = await self._get_price_context(trip_package)

        # Get events
        events_list = await self._get_events_list(trip_package)

        # Calculate cost per person (for family of 4)
        cost_per_person = trip_package.price_per_person

        return {
            "city": trip_package.destination_city,
            "departure_date": trip_package.departure_date.strftime("%Y-%m-%d"),
            "return_date": trip_package.return_date.strftime("%Y-%m-%d"),
            "num_nights": trip_package.num_nights,
            "flight_details": flight_details,
            "flight_price_per_person": flight_price_per_person,
            "true_cost": true_cost,
            "accommodation_name": accommodation_name,
            "accommodation_type": accommodation_type,
            "bedrooms": bedrooms,
            "accommodation_price_per_night": accommodation_price_per_night,
            "accommodation_rating": accommodation_rating,
            "amenities": amenities,
            "total_cost": float(trip_package.total_price),
            "cost_per_person": cost_per_person,
            "price_context": price_context,
            "events_list": events_list,
        }

    async def _get_price_context(self, trip_package: TripPackage) -> str:
        """
        Get historical price context for the route.

        Args:
            trip_package: The trip package

        Returns:
            Formatted string with price context
        """
        try:
            # Get origin and destination from flight data
            flights_data = trip_package.flights_json
            if isinstance(flights_data, dict):
                origin = flights_data.get("origin_airport")
                destination = flights_data.get("destination_airport")
            elif isinstance(flights_data, list) and len(flights_data) > 0:
                origin = flights_data[0].get("origin_airport")
                destination = flights_data[0].get("destination_airport")
            else:
                return "No historical price data available."

            if not origin or not destination:
                return "No historical price data available."

            # Build route string (e.g., "MUC-LIS")
            route = f"{origin}-{destination}"

            # Query price history
            query = select(PriceHistory).where(PriceHistory.route == route)
            result = await self.db.execute(query)
            price_records = result.scalars().all()

            if not price_records:
                return f"No historical price data available for route {route}."

            # Calculate statistics
            prices = [float(record.price) for record in price_records]
            avg_price = sum(prices) / len(prices)
            min_price = min(prices)
            max_price = max(prices)

            current_price = self._get_flight_price_per_person(trip_package)
            percent_diff = ((current_price - avg_price) / avg_price) * 100
            comparison = "above" if percent_diff > 0 else "below"

            return (
                f"Average price for {route}: €{avg_price:.2f}\n"
                f"Lowest seen: €{min_price:.2f}, Highest: €{max_price:.2f}\n"
                f"This price is {abs(percent_diff):.1f}% {comparison} average "
                f"(based on {len(price_records)} historical records)"
            )

        except Exception as e:
            logger.warning(f"Error fetching price context: {e}")
            return "No historical price data available."

    async def _get_events_list(self, trip_package: TripPackage) -> str:
        """
        Get formatted list of events during the trip.

        Args:
            trip_package: The trip package

        Returns:
            Formatted string with events list
        """
        try:
            events_data = trip_package.events_json

            if not events_data:
                return "No events found for these dates."

            # Handle different event data structures
            if isinstance(events_data, list):
                if len(events_data) == 0:
                    return "No events found for these dates."

                # Format event list
                event_lines = []
                for i, event in enumerate(events_data[:10], 1):  # Limit to 10 events
                    if isinstance(event, dict):
                        name = event.get("name", "Unknown Event")
                        date = event.get("date", "Date TBD")
                        category = event.get("category", "")
                        event_lines.append(f"{i}. {name} ({date}) - {category}")
                    else:
                        # Event ID stored, would need to query database
                        event_lines.append(f"{i}. Event ID: {event}")

                return "\n".join(event_lines)

            else:
                return "No events found for these dates."

        except Exception as e:
            logger.warning(f"Error fetching events list: {e}")
            return "No events found for these dates."

    async def _update_trip_package(
        self, trip_package: TripPackage, score_result: Dict[str, Any]
    ) -> None:
        """
        Update trip package with AI scoring results.

        Args:
            trip_package: The trip package to update
            score_result: The scoring results from Claude
        """
        try:
            trip_package.ai_score = score_result.get("score")
            trip_package.ai_reasoning = score_result.get("reasoning")

            # Save to database
            await self.db.commit()
            await self.db.refresh(trip_package)

            logger.debug(f"Updated trip package {trip_package.id} with AI score")

        except Exception as e:
            logger.error(f"Error updating trip package {trip_package.id}: {e}")
            await self.db.rollback()
            raise


async def create_deal_scorer(
    api_key: str,
    redis_client: Redis,
    db_session: AsyncSession,
    price_threshold_per_person: float = 200.0,
    analyze_all: bool = False,
) -> DealScorer:
    """
    Factory function to create a DealScorer instance.

    Args:
        api_key: Anthropic API key
        redis_client: Redis client for caching
        db_session: Database session
        price_threshold_per_person: Max flight price to analyze (default: €200)
        analyze_all: If True, analyze all packages regardless of price

    Returns:
        Configured DealScorer instance
    """
    claude_client = ClaudeClient(
        api_key=api_key,
        redis_client=redis_client,
        db_session=db_session,
    )

    return DealScorer(
        claude_client=claude_client,
        db_session=db_session,
        price_threshold_per_person=price_threshold_per_person,
        analyze_all=analyze_all,
    )
