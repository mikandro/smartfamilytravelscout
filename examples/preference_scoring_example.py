"""
Example: Using preference-based scoring for personalized recommendations.

This example demonstrates how to use user preferences to get personalized
travel deal recommendations that match specific interests and budget constraints.
"""

import asyncio
import logging
from datetime import date, timedelta

from sqlalchemy import select

from app.ai.deal_scorer import create_deal_scorer
from app.config import settings
from app.database import get_async_session_context
from app.models.trip_package import TripPackage
from app.models.user_preference import UserPreference
from app.utils.preference_loader import PreferenceLoader

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def example_load_preference_profile():
    """Example: Load a preference profile and save to database."""
    logger.info("=" * 60)
    logger.info("Example 1: Loading a preference profile")
    logger.info("=" * 60)

    loader = PreferenceLoader()

    # List available profiles
    profiles = loader.list_available_profiles()
    logger.info(f"Available profiles: {', '.join(profiles)}")

    # Load the 'family-with-toddlers' profile
    profile_name = "family-with-toddlers"
    logger.info(f"\nLoading profile: {profile_name}")

    user_pref = loader.load_profile(profile_name)

    logger.info(f"Max flight price (family): €{user_pref.max_flight_price_family}")
    logger.info(f"Max total budget (family): €{user_pref.max_total_budget_family}")
    logger.info(f"Preferred destinations: {user_pref.preferred_destinations_str}")
    logger.info(f"Avoid destinations: {user_pref.avoid_destinations or 'None'}")
    logger.info(f"Interests: {user_pref.interests_str}")

    # Save to database
    async with get_async_session_context() as db:
        saved_pref = await loader.save_profile_to_db_async(profile_name, db, user_id=1)
        logger.info(f"\n✓ Saved preferences to database (ID: {saved_pref.id})")

    return saved_pref


async def example_score_with_preferences():
    """Example: Score trip packages using user preferences."""
    logger.info("\n" + "=" * 60)
    logger.info("Example 2: Scoring packages with user preferences")
    logger.info("=" * 60)

    async with get_async_session_context() as db:
        # Get user preferences
        result = await db.execute(
            select(UserPreference).where(UserPreference.user_id == 1)
        )
        user_prefs = result.scalar_one_or_none()

        if not user_prefs:
            logger.warning("No user preferences found. Run example 1 first.")
            return

        logger.info(f"Using preferences for user {user_prefs.user_id}")
        logger.info(f"Budget limit: €{user_prefs.max_total_budget_family}")

        # Get some trip packages to score
        query = (
            select(TripPackage)
            .where(TripPackage.departure_date >= date.today())
            .limit(5)
        )
        result = await db.execute(query)
        packages = result.scalars().all()

        if not packages:
            logger.warning("No trip packages found in database.")
            logger.info("Generate some packages first using the main pipeline.")
            return

        logger.info(f"\nFound {len(packages)} packages to score\n")

        # Create deal scorer
        from redis.asyncio import Redis

        redis_client = Redis.from_url(settings.redis_url, decode_responses=True)

        try:
            scorer = await create_deal_scorer(
                api_key=settings.anthropic_api_key,
                redis_client=redis_client,
                db_session=db,
                analyze_all=True,  # Analyze all for demonstration
            )

            # Score each package with preferences
            for i, package in enumerate(packages, 1):
                logger.info(f"Package {i}: {package.destination_city}")
                logger.info(
                    f"  Dates: {package.departure_date} to {package.return_date}"
                )
                logger.info(f"  Total price: €{package.total_price}")

                # Score with preferences
                result = await scorer.score_package(
                    package=package, user_prefs=user_prefs, force_analyze=True
                )

                if result is None:
                    logger.info("  ⊘ Filtered out (exceeds budget or constraints)")
                else:
                    logger.info(f"  Score: {result['score']}/100")
                    logger.info(
                        f"  Preference Alignment: {result.get('preference_alignment', 'N/A')}/10"
                    )
                    logger.info(f"  Recommendation: {result['recommendation']}")
                    logger.info(f"  Reasoning: {result['reasoning']}")

                logger.info("")

        finally:
            await redis_client.close()


async def example_compare_profiles():
    """Example: Compare how different profiles score the same package."""
    logger.info("\n" + "=" * 60)
    logger.info("Example 3: Comparing different preference profiles")
    logger.info("=" * 60)

    loader = PreferenceLoader()

    # Load different profiles
    profiles_to_compare = [
        "family-with-toddlers",
        "budget-conscious",
        "beach-lovers",
        "culture-lovers",
    ]

    async with get_async_session_context() as db:
        # Get one trip package
        query = (
            select(TripPackage)
            .where(TripPackage.destination_city == "Barcelona")
            .limit(1)
        )
        result = await db.execute(query)
        package = result.scalar_one_or_none()

        if not package:
            logger.warning("No Barcelona package found for comparison.")
            return

        logger.info(f"Comparing profiles for: {package.destination_city}")
        logger.info(f"Package price: €{package.total_price}")
        logger.info(f"Departure: {package.departure_date}\n")

        from redis.asyncio import Redis

        redis_client = Redis.from_url(settings.redis_url, decode_responses=True)

        try:
            scorer = await create_deal_scorer(
                api_key=settings.anthropic_api_key,
                redis_client=redis_client,
                db_session=db,
                analyze_all=True,
            )

            for profile_name in profiles_to_compare:
                try:
                    user_pref = loader.load_profile(profile_name)
                    logger.info(f"Profile: {profile_name}")

                    result = await scorer.score_package(
                        package=package, user_prefs=user_pref, force_analyze=True
                    )

                    if result is None:
                        logger.info("  ⊘ Would be filtered out")
                    else:
                        logger.info(f"  Score: {result['score']}/100")
                        logger.info(
                            f"  Preference Alignment: {result.get('preference_alignment', 'N/A')}/10"
                        )
                        logger.info(f"  Recommendation: {result['recommendation']}")

                    logger.info("")

                except Exception as e:
                    logger.error(f"  Error: {e}\n")

        finally:
            await redis_client.close()


async def example_filter_by_preferences():
    """Example: Filter packages based on user preferences."""
    logger.info("\n" + "=" * 60)
    logger.info("Example 4: Filtering packages by preferences")
    logger.info("=" * 60)

    async with get_async_session_context() as db:
        # Load beach-lovers profile
        loader = PreferenceLoader()
        user_pref = loader.load_profile("beach-lovers")

        logger.info("Using 'beach-lovers' profile")
        logger.info(f"Max budget: €{user_pref.max_total_budget_family}")
        logger.info(
            f"Preferred destinations: {user_pref.preferred_destinations_str}\n"
        )

        # Query packages within budget
        query = (
            select(TripPackage)
            .where(TripPackage.departure_date >= date.today())
            .where(
                TripPackage.total_price
                <= float(user_pref.max_total_budget_family)
            )
        )

        # Filter out avoided destinations
        if user_pref.avoid_destinations:
            for avoid_dest in user_pref.avoid_destinations:
                query = query.where(
                    ~TripPackage.destination_city.ilike(f"%{avoid_dest}%")
                )

        result = await db.execute(query)
        filtered_packages = result.scalars().all()

        logger.info(f"Found {len(filtered_packages)} packages within preferences:")

        for package in filtered_packages[:10]:  # Show first 10
            logger.info(
                f"  • {package.destination_city}: €{package.total_price} "
                f"({package.departure_date})"
            )


async def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("PREFERENCE-BASED SCORING EXAMPLES")
    print("=" * 60 + "\n")

    try:
        # Example 1: Load a preference profile
        await example_load_preference_profile()

        # Example 2: Score packages with preferences
        await example_score_with_preferences()

        # Example 3: Compare different profiles
        await example_compare_profiles()

        # Example 4: Filter by preferences
        await example_filter_by_preferences()

        print("\n" + "=" * 60)
        print("All examples completed!")
        print("=" * 60 + "\n")

    except Exception as e:
        logger.error(f"Error running examples: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
