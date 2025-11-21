"""
Event relevance scorer using Claude AI.

This module provides AI-powered scoring of events for family travel relevance.
Events are scored 0-10 based on age appropriateness, engagement level,
practical considerations, and alignment with user interests.
"""

import logging
from typing import Dict, List, Optional, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.claude_client import ClaudeClient
from app.ai.prompt_loader import PromptLoader
from app.config import settings
from app.models.event import Event
from app.models.user_preference import UserPreference

logger = logging.getLogger(__name__)


class EventScorer:
    """
    AI-powered event relevance scorer for family travel.

    Uses Claude API to analyze events and score them 0-10 for relevance
    to families with young children, considering age appropriateness,
    engagement level, and user interests.

    Example:
        >>> scorer = EventScorer(claude_client, db_session)
        >>> result = await scorer.score_event(event, user_interests=["museums", "parks"])
        >>> print(result["relevance_score"])  # 0-10
        >>>
        >>> # Batch scoring
        >>> results = await scorer.score_events_batch(events, user_prefs)
    """

    def __init__(
        self,
        claude_client: ClaudeClient,
        db_session: AsyncSession,
        prompt_loader: Optional[PromptLoader] = None,
    ):
        """
        Initialize the EventScorer.

        Args:
            claude_client: ClaudeClient instance for API calls
            db_session: Database session for updating events
            prompt_loader: Optional PromptLoader (creates default if not provided)
        """
        self.claude = claude_client
        self.db = db_session
        self.prompt_loader = prompt_loader or PromptLoader()

        logger.info("Initialized EventScorer")

    async def score_event(
        self,
        event: Event,
        user_interests: Optional[List[str]] = None,
        update_db: bool = True,
    ) -> Dict[str, Any]:
        """
        Score a single event for family travel relevance.

        Args:
            event: Event model instance to score
            user_interests: Optional list of user interests (e.g., ["museums", "parks"])
            update_db: Whether to update the event's ai_relevance_score in database

        Returns:
            Dict containing:
                - relevance_score: float (0-10)
                - age_appropriate: bool
                - min_age: int
                - max_age: int or None
                - category_refined: str
                - engagement_level: str (low/medium/high)
                - duration_suitable: bool
                - matches_interests: List[str]
                - reasoning: str
                - recommendation: str (book/consider/skip)
                - _cost: float (API cost in USD)

        Raises:
            Exception: If scoring fails
        """
        try:
            # Load prompt template
            prompt = self.prompt_loader.load("event_scoring")

            # Prepare event details
            event_data = {
                "title": event.title,
                "category": event.category,
                "description": event.description or "No description provided",
                "event_date": str(event.event_date),
                "price_range": event.price_range or "Not specified",
                "destination_city": event.destination_city,
                "user_interests": self._format_interests(user_interests),
            }

            # Call Claude API
            logger.info(
                f"Scoring event: {event.title} ({event.destination_city}) "
                f"- ID: {event.id}"
            )

            result = await self.claude.analyze(
                prompt=prompt,
                data=event_data,
                response_format="json",
                use_cache=True,
                max_tokens=settings.claude_max_tokens_event,
                operation="event_scoring",
                temperature=settings.claude_temperature,
            )

            # Extract relevance score
            relevance_score = result.get("relevance_score", 0.0)

            # Update database if requested
            if update_db:
                event.ai_relevance_score = float(relevance_score)
                await self.db.commit()
                logger.info(
                    f"Updated event {event.id} with relevance score: {relevance_score}"
                )

            logger.info(
                f"Event scored: {event.title} = {relevance_score}/10 "
                f"({result.get('recommendation', 'unknown')})"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to score event {event.id}: {e}")
            await self.db.rollback()
            raise

    async def score_events_batch(
        self,
        events: List[Event],
        user_preferences: Optional[UserPreference] = None,
        update_db: bool = True,
        min_score_threshold: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Score multiple events in batch with progress tracking.

        Args:
            events: List of Event instances to score
            user_preferences: Optional UserPreference instance (fetches default if None)
            update_db: Whether to update events in database
            min_score_threshold: Only return events scoring above this threshold

        Returns:
            Dict containing:
                - total_events: int (total events processed)
                - scored_events: int (successfully scored)
                - failed_events: int (failed to score)
                - average_score: float
                - high_relevance_count: int (score >= 7)
                - results: List[Dict] (scoring results for each event)
                - total_cost: float (total API cost in USD)

        Example:
            >>> results = await scorer.score_events_batch(
            ...     events=lisbon_events,
            ...     min_score_threshold=6.0
            ... )
            >>> print(f"Found {results['high_relevance_count']} highly relevant events")
        """
        try:
            # Get user interests
            if user_preferences is None:
                user_preferences = await self._get_default_user_preferences()

            user_interests = user_preferences.interests or []

            # Track results
            results = []
            failed_count = 0
            total_cost = 0.0
            scores = []

            logger.info(
                f"Starting batch scoring of {len(events)} events with interests: {user_interests}"
            )

            for idx, event in enumerate(events, 1):
                try:
                    # Score the event
                    result = await self.score_event(
                        event=event,
                        user_interests=user_interests,
                        update_db=update_db,
                    )

                    score = result.get("relevance_score", 0.0)

                    # Only include if meets threshold
                    if score >= min_score_threshold:
                        results.append({
                            "event_id": event.id,
                            "title": event.title,
                            "destination": event.destination_city,
                            "date": str(event.event_date),
                            "score": score,
                            "recommendation": result.get("recommendation"),
                            "reasoning": result.get("reasoning"),
                            "category": result.get("category_refined"),
                        })

                    scores.append(score)
                    total_cost += result.get("_cost", 0.0)

                    # Log progress every 10 events
                    if idx % 10 == 0:
                        logger.info(f"Progress: {idx}/{len(events)} events scored")

                except Exception as e:
                    logger.error(f"Failed to score event {event.id}: {e}")
                    failed_count += 1
                    continue

            # Calculate statistics
            avg_score = sum(scores) / len(scores) if scores else 0.0
            high_relevance_count = sum(1 for s in scores if s >= 7.0)

            summary = {
                "total_events": len(events),
                "scored_events": len(scores),
                "failed_events": failed_count,
                "average_score": round(avg_score, 2),
                "high_relevance_count": high_relevance_count,
                "results": sorted(results, key=lambda x: x["score"], reverse=True),
                "total_cost": round(total_cost, 4),
            }

            logger.info(
                f"Batch scoring complete: {summary['scored_events']}/{summary['total_events']} "
                f"events scored successfully. Average score: {summary['average_score']}/10. "
                f"High relevance: {summary['high_relevance_count']}. Cost: ${summary['total_cost']}"
            )

            return summary

        except Exception as e:
            logger.error(f"Batch scoring failed: {e}")
            raise

    async def get_top_events(
        self,
        destination_city: str,
        min_score: float = 7.0,
        limit: int = 10,
    ) -> List[Event]:
        """
        Get top-scored events for a destination.

        Args:
            destination_city: City name to filter by
            min_score: Minimum relevance score (default: 7.0)
            limit: Maximum number of events to return

        Returns:
            List of Event instances sorted by relevance score (highest first)
        """
        try:
            query = (
                select(Event)
                .where(Event.destination_city == destination_city)
                .where(Event.ai_relevance_score >= min_score)
                .order_by(Event.ai_relevance_score.desc())
                .limit(limit)
            )

            result = await self.db.execute(query)
            events = result.scalars().all()

            logger.info(
                f"Found {len(events)} events in {destination_city} "
                f"with score >= {min_score}"
            )

            return list(events)

        except Exception as e:
            logger.error(f"Failed to get top events: {e}")
            raise

    async def get_unscored_events(
        self,
        destination_city: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Event]:
        """
        Get events that haven't been scored yet.

        Args:
            destination_city: Optional city filter
            limit: Optional limit on number of events

        Returns:
            List of Event instances without ai_relevance_score
        """
        try:
            query = select(Event).where(Event.ai_relevance_score.is_(None))

            if destination_city:
                query = query.where(Event.destination_city == destination_city)

            if limit:
                query = query.limit(limit)

            result = await self.db.execute(query)
            events = result.scalars().all()

            logger.info(
                f"Found {len(events)} unscored events"
                + (f" in {destination_city}" if destination_city else "")
            )

            return list(events)

        except Exception as e:
            logger.error(f"Failed to get unscored events: {e}")
            raise

    def _format_interests(self, interests: Optional[List[str]]) -> str:
        """
        Format user interests for the prompt.

        Args:
            interests: List of interest strings

        Returns:
            Formatted string of interests
        """
        if not interests or len(interests) == 0:
            return "No specific interests provided (score based on general family suitability)"

        return ", ".join(interests)

    async def _get_default_user_preferences(self) -> UserPreference:
        """
        Get default user preferences (user_id=1).

        Returns:
            UserPreference instance

        Raises:
            Exception: If no default preferences found
        """
        try:
            query = select(UserPreference).where(UserPreference.user_id == 1)
            result = await self.db.execute(query)
            prefs = result.scalar_one_or_none()

            if not prefs:
                # Create default preferences if none exist
                logger.warning("No user preferences found, creating defaults")
                prefs = UserPreference(
                    user_id=1,
                    max_flight_price_family=200.0,
                    max_flight_price_parents=300.0,
                    max_total_budget_family=2000.0,
                    interests=["museums", "parks", "family activities", "cultural events"],
                    notification_threshold=70.0,
                )
                self.db.add(prefs)
                await self.db.commit()

            return prefs

        except Exception as e:
            logger.error(f"Failed to get user preferences: {e}")
            raise


async def score_events_for_destination(
    destination_city: str,
    claude_client: ClaudeClient,
    db_session: AsyncSession,
    min_score_threshold: float = 5.0,
) -> Dict[str, Any]:
    """
    Convenience function to score all unscored events for a destination.

    Args:
        destination_city: City name to score events for
        claude_client: ClaudeClient instance
        db_session: Database session
        min_score_threshold: Minimum score to include in results

    Returns:
        Batch scoring results dictionary

    Example:
        >>> results = await score_events_for_destination(
        ...     "Lisbon", claude_client, db_session
        ... )
        >>> print(f"Scored {results['scored_events']} events in Lisbon")
    """
    scorer = EventScorer(claude_client, db_session)

    # Get unscored events
    events = await scorer.get_unscored_events(destination_city=destination_city)

    if not events:
        logger.info(f"No unscored events found for {destination_city}")
        return {
            "total_events": 0,
            "scored_events": 0,
            "message": f"No unscored events found for {destination_city}",
        }

    # Score them
    return await scorer.score_events_batch(
        events=events,
        min_score_threshold=min_score_threshold,
    )
