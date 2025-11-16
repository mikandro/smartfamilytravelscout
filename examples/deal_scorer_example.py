"""
Example usage of the DealScorer AI system.

This script demonstrates how to use the DealScorer to analyze trip packages
and filter for good deals using Claude AI.
"""

import asyncio
import os
from datetime import date

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.ai.deal_scorer import create_deal_scorer
from app.models.trip_package import TripPackage


async def main():
    """Example: Score trip packages and find good deals."""

    # Setup (you'll need to configure these for your environment)
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "your-api-key-here")
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/dbname")

    # Create Redis client
    redis_client = Redis.from_url(REDIS_URL, decode_responses=False)

    # Create database session
    engine = create_async_engine(DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Create deal scorer
        # Default: Only analyze packages with flight price < €200/person
        scorer = await create_deal_scorer(
            api_key=ANTHROPIC_API_KEY,
            redis_client=redis_client,
            db_session=session,
            price_threshold_per_person=200.0,  # Only analyze cheap flights
            analyze_all=False,  # Set to True to analyze all packages
        )

        # Example 1: Score a single trip package
        print("\n=== Example 1: Score Single Trip ===")

        # Fetch a trip package from database
        result = await session.execute(
            select(TripPackage)
            .where(TripPackage.package_type == "family")
            .limit(1)
        )
        trip = result.scalar_one_or_none()

        if trip:
            print(f"Analyzing trip: {trip.destination_city} (€{trip.total_price})")

            score_result = await scorer.score_trip(trip)

            if score_result:
                print(f"✓ Score: {score_result['score']}/100")
                print(f"  Recommendation: {score_result['recommendation']}")
                print(f"  Reasoning: {score_result['reasoning']}")
                print(f"  API Cost: ${score_result['_cost']:.4f}")
            else:
                print("✗ Trip filtered out (price above threshold)")
        else:
            print("No trip packages found in database")

        # Example 2: Filter multiple packages for good deals
        print("\n=== Example 2: Filter Good Deals ===")

        # Fetch multiple unscored packages
        result = await session.execute(
            select(TripPackage)
            .where(TripPackage.ai_score.is_(None))
            .limit(10)
        )
        packages = result.scalars().all()

        if packages:
            print(f"Found {len(packages)} unscored packages")

            # Filter for deals with score >= 75
            good_deals = await scorer.filter_good_deals(
                packages,
                min_score=75.0
            )

            print(f"\nFound {len(good_deals)} good deals:")
            for deal in good_deals:
                pkg = deal["package"]
                print(f"\n  • {pkg.destination_city} ({pkg.departure_date} - {pkg.return_date})")
                print(f"    Score: {deal['score']}/100")
                print(f"    Price: €{pkg.total_price} (€{pkg.price_per_person}/person)")
                print(f"    Recommendation: {deal['recommendation']}")
                print(f"    Highlights: {', '.join(deal['highlights'][:3])}")
        else:
            print("No unscored packages found")

        # Example 3: Force analyze an expensive package
        print("\n=== Example 3: Force Analyze (Bypass Threshold) ===")

        # Fetch a more expensive package
        result = await session.execute(
            select(TripPackage)
            .order_by(TripPackage.total_price.desc())
            .limit(1)
        )
        expensive_trip = result.scalar_one_or_none()

        if expensive_trip:
            print(f"Analyzing expensive trip: {expensive_trip.destination_city} "
                  f"(€{expensive_trip.total_price})")

            # Use force_analyze to bypass threshold
            score_result = await scorer.score_trip(
                expensive_trip,
                force_analyze=True
            )

            if score_result:
                print(f"✓ Score: {score_result['score']}/100")
                print(f"  Recommendation: {score_result['recommendation']}")
        else:
            print("No packages found")

        # Example 4: Analyze all mode
        print("\n=== Example 4: Analyze All Mode ===")

        # Create scorer with analyze_all=True
        all_scorer = await create_deal_scorer(
            api_key=ANTHROPIC_API_KEY,
            redis_client=redis_client,
            db_session=session,
            analyze_all=True,  # Analyze regardless of price
        )

        print("Created scorer with analyze_all=True")
        print("This will analyze all packages regardless of flight price")

    await redis_client.close()
    print("\n✓ Done!")


if __name__ == "__main__":
    asyncio.run(main())
