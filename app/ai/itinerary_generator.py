"""
AI-powered itinerary generator for high-scoring family trips.

This module generates detailed 3-day family itineraries using Claude API,
optimized for families with young children (ages 3 & 6).
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.claude_client import ClaudeClient
from app.ai.prompt_loader import load_prompt
from app.models.accommodation import Accommodation
from app.models.event import Event
from app.models.trip_package import TripPackage

logger = logging.getLogger(__name__)


class ItineraryGenerationError(Exception):
    """Custom exception for itinerary generation errors."""

    pass


class ItineraryGenerator:
    """
    Generate detailed 3-day family itineraries for high-scoring trips.

    Features:
    - Day-by-day planning (morning/afternoon/evening)
    - Kid-friendly activities for ages 3 & 6
    - Nap time considerations (1-2pm daily)
    - Restaurant recommendations with family amenities
    - Walking distances from accommodation
    - Weather backup plans

    Example:
        >>> generator = ItineraryGenerator(claude_client=claude, db_session=session)
        >>> itinerary = await generator.generate_itinerary(
        ...     trip_package=trip,
        ...     save_to_db=True
        ... )
        >>> print(itinerary["day_1"]["morning"])
    """

    def __init__(
        self,
        claude_client: ClaudeClient,
        db_session: Optional[AsyncSession] = None,
        min_score_threshold: float = 70.0,
    ):
        """
        Initialize the itinerary generator.

        Args:
            claude_client: Configured ClaudeClient instance
            db_session: Optional database session for saving results
            min_score_threshold: Minimum AI score to generate itineraries (default: 70)
        """
        self.claude = claude_client
        self.db_session = db_session
        self.min_score_threshold = min_score_threshold

        logger.info(
            f"Initialized ItineraryGenerator with score threshold: {min_score_threshold}"
        )

    async def generate_itinerary(
        self,
        trip_package: TripPackage,
        save_to_db: bool = True,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate a detailed 3-day itinerary for a trip package.

        Args:
            trip_package: TripPackage instance with trip details
            save_to_db: Whether to save the itinerary to database (default: True)
            force: Generate even if score is below threshold (default: False)

        Returns:
            Dictionary with itinerary structure:
            {
                "day_1": {
                    "morning": "...",
                    "afternoon": "...",
                    "evening": "...",
                    "breakfast_spot": "...",
                    "lunch_spot": "...",
                    "dinner_spot": "...",
                    "weather_backup": "..."
                },
                "day_2": {...},
                "day_3": {...},
                "tips": [...],
                "packing_essentials": [...]
            }

        Raises:
            ItineraryGenerationError: If generation fails or trip doesn't meet criteria
        """
        # Validate trip package
        if not force and (
            trip_package.ai_score is None
            or float(trip_package.ai_score) < self.min_score_threshold
        ):
            raise ItineraryGenerationError(
                f"Trip score ({trip_package.ai_score}) is below threshold "
                f"({self.min_score_threshold}). Use force=True to override."
            )

        # Check if itinerary already exists
        if trip_package.itinerary_json and not force:
            logger.info(
                f"Trip package {trip_package.id} already has itinerary. "
                f"Returning cached version."
            )
            return trip_package.itinerary_json

        logger.info(
            f"Generating itinerary for trip {trip_package.id} "
            f"(destination: {trip_package.destination_city}, "
            f"dates: {trip_package.departure_date} to {trip_package.return_date}, "
            f"score: {trip_package.ai_score})"
        )

        try:
            # Load accommodation details
            accommodation_info = await self._get_accommodation_info(trip_package)

            # Load events info
            events_info = await self._get_events_info(trip_package)

            # Format dates
            dates = self._format_dates(trip_package)

            # Load and format prompt
            prompt = load_prompt("itinerary_generation")

            prompt_data = {
                "city": trip_package.destination_city,
                "dates": dates,
                "accommodation_name": accommodation_info["name"],
                "accommodation_address": accommodation_info["address"],
                "accommodation_type": accommodation_info["type"],
                "events_list": events_info,
            }

            # Call Claude API
            logger.info(
                f"Calling Claude API to generate itinerary for {trip_package.destination_city}"
            )

            response = await self.claude.analyze(
                prompt=prompt,
                data=prompt_data,
                response_format="json",
                use_cache=True,
                max_tokens=4096,  # Larger token limit for detailed itineraries
                operation="itinerary_generation",
                temperature=0.7,  # Slightly lower for more consistent formatting
            )

            # Extract itinerary (without metadata)
            itinerary = {
                k: v for k, v in response.items() if not k.startswith("_")
            }

            # Validate itinerary structure
            self._validate_itinerary(itinerary)

            # Log cost and token usage
            logger.info(
                f"Itinerary generated successfully. "
                f"Cost: ${response['_cost']:.4f}, "
                f"Tokens: {response['_tokens']['total']}"
            )

            # Save to database if requested
            if save_to_db and self.db_session:
                await self._save_to_database(trip_package, itinerary)

            return itinerary

        except Exception as e:
            logger.error(f"Failed to generate itinerary for trip {trip_package.id}: {e}")
            raise ItineraryGenerationError(
                f"Itinerary generation failed: {e}"
            ) from e

    async def generate_batch(
        self,
        trip_packages: List[TripPackage],
        save_to_db: bool = True,
        skip_errors: bool = True,
    ) -> Dict[int, Dict[str, Any]]:
        """
        Generate itineraries for multiple trip packages.

        Args:
            trip_packages: List of TripPackage instances
            save_to_db: Whether to save itineraries to database
            skip_errors: Continue on errors (default: True)

        Returns:
            Dictionary mapping trip package IDs to itineraries
        """
        results = {}
        errors = {}

        for trip in trip_packages:
            try:
                itinerary = await self.generate_itinerary(
                    trip_package=trip,
                    save_to_db=save_to_db,
                )
                results[trip.id] = itinerary
                logger.info(f"Generated itinerary for trip {trip.id}")
            except Exception as e:
                errors[trip.id] = str(e)
                if skip_errors:
                    logger.warning(
                        f"Skipping trip {trip.id} due to error: {e}"
                    )
                else:
                    raise

        logger.info(
            f"Batch generation complete. "
            f"Successful: {len(results)}, Failed: {len(errors)}"
        )

        if errors:
            logger.warning(f"Failed trips: {errors}")

        return results

    async def _get_accommodation_info(
        self, trip_package: TripPackage
    ) -> Dict[str, str]:
        """
        Extract accommodation information for the prompt.

        Args:
            trip_package: TripPackage instance

        Returns:
            Dictionary with accommodation details
        """
        if trip_package.accommodation:
            # Use relationship if available
            acc = trip_package.accommodation
            return {
                "name": acc.name,
                "address": f"{acc.destination_city} city center",  # Generic address
                "type": acc.type,
            }
        else:
            # Fallback to generic accommodation
            return {
                "name": f"Family Accommodation in {trip_package.destination_city}",
                "address": f"{trip_package.destination_city} city center",
                "type": "hotel/apartment",
            }

    async def _get_events_info(self, trip_package: TripPackage) -> str:
        """
        Format events information for the prompt.

        Args:
            trip_package: TripPackage instance

        Returns:
            Formatted string of events
        """
        if not trip_package.events_json or not trip_package.events_json.get("events"):
            return "No specific events found during this period. Research local attractions."

        events = trip_package.events_json.get("events", [])

        # Format events for prompt
        event_lines = []
        for event in events[:10]:  # Limit to top 10 events
            if isinstance(event, dict):
                title = event.get("title", "Unknown Event")
                date = event.get("event_date", "")
                category = event.get("category", "")
                event_lines.append(f"- {title} ({category}) on {date}")
            elif isinstance(event, int):
                # Event ID only - would need to fetch from DB
                event_lines.append(f"- Event ID: {event}")

        if not event_lines:
            return "No specific events found during this period. Research local attractions."

        return "\n".join(event_lines)

    def _format_dates(self, trip_package: TripPackage) -> str:
        """
        Format trip dates for the prompt.

        Args:
            trip_package: TripPackage instance

        Returns:
            Formatted date string
        """
        return (
            f"{trip_package.departure_date.strftime('%B %d, %Y')} to "
            f"{trip_package.return_date.strftime('%B %d, %Y')} "
            f"({trip_package.duration_days} days)"
        )

    def _validate_itinerary(self, itinerary: Dict[str, Any]) -> None:
        """
        Validate that the itinerary has the expected structure.

        Args:
            itinerary: Generated itinerary dictionary

        Raises:
            ItineraryGenerationError: If validation fails
        """
        # Check for required day keys
        required_days = ["day_1", "day_2", "day_3"]
        for day in required_days:
            if day not in itinerary:
                raise ItineraryGenerationError(
                    f"Missing required day: {day}"
                )

            # Check for required sections in each day
            required_sections = [
                "morning",
                "afternoon",
                "evening",
                "breakfast_spot",
                "lunch_spot",
                "dinner_spot",
            ]
            for section in required_sections:
                if section not in itinerary[day]:
                    logger.warning(
                        f"Missing section '{section}' in {day}. "
                        f"Itinerary may be incomplete."
                    )

        # Check for tips
        if "tips" not in itinerary:
            logger.warning("Itinerary missing 'tips' section")

        logger.info("Itinerary structure validation passed")

    async def _save_to_database(
        self, trip_package: TripPackage, itinerary: Dict[str, Any]
    ) -> None:
        """
        Save the generated itinerary to the database.

        Args:
            trip_package: TripPackage instance to update
            itinerary: Generated itinerary dictionary
        """
        if not self.db_session:
            logger.warning("No database session available. Skipping save.")
            return

        try:
            trip_package.itinerary_json = itinerary

            self.db_session.add(trip_package)
            await self.db_session.commit()
            await self.db_session.refresh(trip_package)

            logger.info(
                f"Saved itinerary to database for trip package {trip_package.id}"
            )
        except Exception as e:
            logger.error(f"Failed to save itinerary to database: {e}")
            await self.db_session.rollback()
            raise ItineraryGenerationError(
                f"Failed to save itinerary: {e}"
            ) from e

    async def get_itinerary_summary(self, trip_package: TripPackage) -> str:
        """
        Get a brief text summary of the itinerary.

        Args:
            trip_package: TripPackage with generated itinerary

        Returns:
            Brief text summary of the itinerary
        """
        if not trip_package.itinerary_json:
            return "No itinerary generated yet."

        itinerary = trip_package.itinerary_json

        # Extract highlights from each day
        summary_lines = [
            f"3-Day Family Itinerary for {trip_package.destination_city}",
            f"Dates: {self._format_dates(trip_package)}",
            "",
        ]

        for day_num in range(1, 4):
            day_key = f"day_{day_num}"
            if day_key in itinerary:
                day_data = itinerary[day_key]
                summary_lines.append(f"Day {day_num}:")

                # Extract first sentence from morning plan
                morning = day_data.get("morning", "")
                if morning:
                    first_sentence = morning.split(".")[0]
                    summary_lines.append(f"  Morning: {first_sentence}")

        return "\n".join(summary_lines)
