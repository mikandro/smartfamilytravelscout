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
from app.ai.judgement import JudgementSchema, MalformedJudgement
from app.ai.prompt_loader import PromptLoader

#: What a deal-scoring response must contain.
DEAL_SCHEMA = JudgementSchema(
    required=(
        "score",
        "value_assessment",
        "family_suitability",
        "timing_quality",
        "recommendation",
        "confidence",
        "reasoning",
    ),
    optional=("highlights", "concerns"),
    defaults={"highlights": [], "concerns": []},
)
from app.domain.package_components import (
    describe_flight,
    load_flights,
    read_flight_components,
)
from app.models.accommodation import Accommodation
from app.models.event import Event
from app.models.flight import Flight
from app.models.price_history import PriceHistory
from app.models.trip_package import TripPackage
from app.models.user_preference import UserPreference

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
                flight_price_per_person = await self._get_flight_price_per_person(
                    trip_package
                )
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
                max_tokens=2048,
                operation="deal_scoring",
            )

            # Validate against the declared schema. This used to set every
            # missing field to None and carry on, which produced packages with
            # a null score and no error anywhere -- indistinguishable from a
            # package Claude had genuinely declined to score.
            response = DEAL_SCHEMA.validate(response, "deal_scoring")

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

    async def score_package(
        self,
        package: TripPackage,
        user_prefs: UserPreference,
        force_analyze: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Score a trip package using Claude AI with user preferences.

        This function incorporates user-specific preferences (budget, interests,
        preferred/avoided destinations) into the scoring process to provide
        personalized recommendations.

        Args:
            package: The TripPackage to analyze
            user_prefs: User preference settings to consider
            force_analyze: If True, bypass price threshold check

        Returns:
            Dictionary with scoring results, or None if filtered out by threshold.
            Result includes:
            - score: Overall deal score (0-100), adjusted for preferences
            - preference_alignment: How well it matches user preferences (0-10)
            - value_assessment: Text assessment of price value
            - family_suitability: Rating 0-10
            - timing_quality: Rating 0-10
            - recommendation: "book_now", "wait", or "skip"
            - confidence: Confidence level (0-100)
            - reasoning: Explanation text including preference matching
            - highlights: List of key selling points
            - concerns: List of potential issues

        Raises:
            ValueError: If trip package data is incomplete

        Example:
            >>> user_prefs = await db.get(UserPreference, 1)
            >>> result = await scorer.score_package(package, user_prefs)
            >>> if result and result['preference_alignment'] >= 8:
            >>>     print(f"Great match! Score: {result['score']}")
        """
        try:
            # Check price threshold against user preferences
            if not self.analyze_all and not force_analyze:
                flight_price_per_person = self._get_flight_price_per_person(package)

                # Use user's max flight price preference
                max_price = float(user_prefs.max_flight_price_family)

                if flight_price_per_person > max_price:
                    logger.info(
                        f"Skipping trip {package.id}: flight price "
                        f"€{flight_price_per_person}/person exceeds user's max "
                        f"€{max_price}"
                    )
                    return None

                # Also check total budget
                if float(package.total_price) > float(user_prefs.max_total_budget_family):
                    logger.info(
                        f"Skipping trip {package.id}: total price "
                        f"€{package.total_price} exceeds user's max budget "
                        f"€{user_prefs.max_total_budget_family}"
                    )
                    return None

            # Check if destination is in avoid list
            if user_prefs.avoid_destinations:
                destination_lower = package.destination_city.lower()
                avoid_list_lower = [d.lower() for d in user_prefs.avoid_destinations]
                if any(avoid in destination_lower for avoid in avoid_list_lower):
                    logger.info(
                        f"Skipping trip {package.id}: destination {package.destination_city} "
                        f"is in user's avoid list"
                    )
                    # Return a low score instead of None to show why it was rejected
                    return {
                        "score": 10,
                        "preference_alignment": 0,
                        "value_assessment": "Destination is in your avoid list",
                        "family_suitability": 0,
                        "timing_quality": 0,
                        "recommendation": "skip",
                        "confidence": 100,
                        "reasoning": f"{package.destination_city} is in your avoid destinations list",
                        "highlights": [],
                        "concerns": ["Destination is in avoid list"],
                    }

            # Gather all required data with user preferences
            prompt_data = await self._build_prompt_data_with_preferences(
                package, user_prefs
            )

            # Load preference-aware prompt template
            prompt = self.prompt_loader.load("deal_analysis_with_preferences")

            # Call Claude API
            logger.info(
                f"Analyzing trip package {package.id} with user preferences "
                f"({package.destination_city}, €{package.total_price})"
            )

            response = await self.claude.analyze(
                prompt=prompt,
                data=prompt_data,
                response_format="json",
                use_cache=True,
                max_tokens=2048,
                operation="deal_scoring_with_preferences",
            )

            # Validate response structure
            required_fields = [
                "score",
                "value_assessment",
                "preference_alignment",
                "family_suitability",
                "timing_quality",
                "recommendation",
                "confidence",
                "reasoning",
            ]
            for field in required_fields:
                if field not in response:
                    logger.warning(
                        f"Missing field '{field}' in Claude response for trip {package.id}"
                    )
                    response[field] = None

            # Update trip package with AI results
            await self._update_trip_package(package, response)

            logger.info(
                f"Scored trip {package.id} with preferences: {response['score']}/100 "
                f"(preference_alignment={response.get('preference_alignment', 'N/A')}, "
                f"{response['recommendation']}, cost=${response.get('_cost', 0):.4f})"
            )

            return response

        except Exception as e:
            logger.error(
                f"Error scoring trip {package.id} with preferences: {e}",
                exc_info=True,
            )
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

    async def _get_flight_price_per_person(self, trip_package: TripPackage) -> float:
        """
        Resolve the flight price per person for a trip package.

        Reads the travel components through the package-components seam and
        resolves referenced ``Flight`` rows, so every historical shape of
        ``flights_json`` is handled in one place.

        Args:
            trip_package: The trip package

        Returns:
            Flight price per person in EUR

        Raises:
            ValueError: If the package claims to be flight-backed but no price
                can be resolved from its ids or its legacy snapshot.
        """
        components = read_flight_components(trip_package.flights_json)

        # Flight-backed package: resolve the referenced Flight row. This used to
        # call .get() on whatever sat in flights_json, which raised
        # AttributeError on the list[int] the main pipeline writes.
        flights = await load_flights(components, self.db)
        if flights:
            price = flights[0].price_per_person
            if price is not None:
                return float(price)

        # Legacy row with the flight fields embedded in the JSON.
        if components.snapshot:
            price = components.snapshot.get("price_per_person")
            if price is not None:
                return float(price)

        # Non-flight travel (parent escape) has no per-person flight price;
        # fall back to the package's own per-person figure, which knows that
        # an escape package is for two people rather than four.
        if not components.is_flight:
            return float(trip_package.price_per_person)

        raise ValueError(
            f"Trip package {trip_package.id} has no resolvable flight price "
            f"(travel_method={components.travel_method}, "
            f"flight_ids={list(components.flight_ids)})"
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
        # Resolve the travel components once, through the seam.
        components = read_flight_components(trip_package.flights_json)
        flights = await load_flights(components, self.db)
        primary_flight = flights[0] if flights else None

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
        flight_details = describe_flight(primary_flight, components)

        flight_price_per_person = await self._get_flight_price_per_person(trip_package)

        # Prefer the true cost on the resolved Flight row; fall back to a legacy
        # embedded snapshot, then to the plain per-person price.
        if primary_flight is not None and primary_flight.true_cost is not None:
            true_cost = float(primary_flight.true_cost)
        else:
            true_cost = float(
                components.snapshot.get("true_cost", flight_price_per_person)
            )

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

    async def _build_prompt_data_with_preferences(
        self, package: TripPackage, user_prefs: UserPreference
    ) -> Dict[str, Any]:
        """
        Build the data dictionary for the preference-aware prompt template.

        Args:
            package: The trip package to analyze
            user_prefs: User preference settings

        Returns:
            Dictionary with all variables needed for the preference-aware prompt template
        """
        # Start with base prompt data
        prompt_data = await self._build_prompt_data(package)

        # Add user preference data
        prompt_data.update(
            {
                "max_flight_price_family": float(user_prefs.max_flight_price_family),
                "max_total_budget_family": float(user_prefs.max_total_budget_family),
                "notification_threshold": float(user_prefs.notification_threshold),
                "preferred_destinations": (
                    user_prefs.preferred_destinations_str
                    if user_prefs.preferred_destinations
                    else "No specific preferences"
                ),
                "avoid_destinations": (
                    ", ".join(user_prefs.avoid_destinations)
                    if user_prefs.avoid_destinations
                    else "None"
                ),
                "interests": (
                    user_prefs.interests_str if user_prefs.interests else "Not specified"
                ),
                "travel_purpose": (
                    "Family trip with children"
                    if package.package_type == "family"
                    else "Parent escape (adults only)"
                ),
            }
        )

        return prompt_data

    async def _get_price_context(self, trip_package: TripPackage) -> str:
        """
        Get historical price context for the route.

        Args:
            trip_package: The trip package

        Returns:
            Formatted string with price context
        """
        try:
            # Resolve origin and destination through the components seam.
            components = read_flight_components(trip_package.flights_json)
            flights = await load_flights(components, self.db)

            if flights:
                origin = getattr(flights[0].origin_airport, "iata_code", None)
                destination = getattr(
                    flights[0].destination_airport, "iata_code", None
                )
            else:
                origin = components.snapshot.get("origin_airport")
                destination = components.snapshot.get("destination_airport")

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
