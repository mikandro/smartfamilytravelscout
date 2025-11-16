"""
Example usage of Claude API integration.

This script demonstrates how to use the ClaudeClient for various
AI-powered travel analysis tasks.

Usage:
    python examples/claude_integration_example.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import ClaudeClient, load_prompt
from app.config import settings
from app.database import AsyncSessionLocal


async def example_deal_analysis():
    """Example: Analyze a travel deal using Claude."""
    print("\n" + "=" * 60)
    print("EXAMPLE 1: Travel Deal Analysis")
    print("=" * 60)

    # Setup
    redis = Redis.from_url(str(settings.redis_url))

    async with AsyncSessionLocal() as db:
        # Initialize Claude client
        client = ClaudeClient(
            api_key=settings.anthropic_api_key,
            redis_client=redis,
            db_session=db,
        )

        # Load the deal analysis prompt template
        try:
            prompt = load_prompt("deal_analysis")
        except FileNotFoundError:
            # Fallback if prompt template doesn't exist
            prompt = """
Analyze this travel deal and provide a score from 0-100:

{deal_details}

Return JSON with: score, price_rating, highlights, concerns, recommendation
            """.strip()

        # Sample deal data
        deal_details = """
Flight: Vienna (VIE) to Lisbon (LIS)
Price: €145 per person (round trip)
Dates: December 20-27, 2025
Airline: TAP Air Portugal (direct flight)
Hotel: 4-star family hotel in city center
Hotel Price: €95 per night (family room for 4)
Included: Breakfast, free WiFi, kids stay free
Total for family of 4: €1,245 (flights + 7 nights)
        """.strip()

        # Analyze the deal
        print("\nAnalyzing deal...")
        print(f"Deal: Vienna to Lisbon, €1,245 for family of 4\n")

        result = await client.analyze(
            prompt=prompt,
            data={"deal_details": deal_details},
            response_format="json",
            operation="deal_scoring",
        )

        # Display results
        print(f"✓ Deal Score: {result.get('score', 'N/A')}/100")
        print(f"✓ Price Rating: {result.get('price_rating', 'N/A')}")
        print(f"✓ API Cost: ${result['_cost']:.4f}")
        print(f"✓ Tokens Used: {result['_tokens']['total']}")

        if "highlights" in result:
            print(f"\nHighlights:")
            for highlight in result["highlights"]:
                print(f"  • {highlight}")

        if "recommendation" in result:
            print(f"\nRecommendation: {result['recommendation']}")

    await redis.close()


async def example_event_scoring():
    """Example: Score a family event using Claude."""
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Family Event Scoring")
    print("=" * 60)

    redis = Redis.from_url(str(settings.redis_url))

    async with AsyncSessionLocal() as db:
        client = ClaudeClient(
            api_key=settings.anthropic_api_key,
            redis_client=redis,
            db_session=db,
        )

        # Sample event data
        event_details = """
Event: Christmas Markets Tour
Location: Vienna, Austria
Date: December 15-24, 2025
Duration: 2-3 hours
Price: €25 per adult, kids under 12 free
Description: Guided walking tour through Vienna's magical Christmas markets,
including tasting traditional treats, hot chocolate for kids, and visits to
5 different markets. Family-friendly pace with breaks.
Accessibility: Stroller-friendly routes
        """.strip()

        prompt = """
Score this event for family-friendliness (0-100):

{event_details}

Return JSON with: family_score, age_range (min/max/ideal), pros, cons, tips_for_parents, recommendation
        """.strip()

        print("\nScoring event...")
        print("Event: Christmas Markets Tour\n")

        result = await client.analyze(
            prompt=prompt,
            data={"event_details": event_details},
            response_format="json",
            operation="event_scoring",
        )

        print(f"✓ Family Score: {result.get('family_score', 'N/A')}/100")

        if "age_range" in result:
            age = result["age_range"]
            print(
                f"✓ Age Range: {age.get('min', 'N/A')}-{age.get('max', 'any')} "
                f"(ideal: {age.get('ideal', 'N/A')})"
            )

        print(f"✓ API Cost: ${result['_cost']:.4f}")

        if "pros" in result:
            print(f"\nPros:")
            for pro in result["pros"][:3]:  # Show first 3
                print(f"  • {pro}")

        if "tips_for_parents" in result:
            print(f"\nTips for Parents:")
            for tip in result["tips_for_parents"][:2]:  # Show first 2
                print(f"  • {tip}")

    await redis.close()


async def example_caching():
    """Example: Demonstrate response caching."""
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Response Caching")
    print("=" * 60)

    redis = Redis.from_url(str(settings.redis_url))

    async with AsyncSessionLocal() as db:
        client = ClaudeClient(
            api_key=settings.anthropic_api_key,
            redis_client=redis,
            db_session=db,
        )

        prompt = "Rate this destination for families: {destination}"
        data = {"destination": "Barcelona, Spain"}

        # First call - will hit API
        print("\n1st call (API)...")
        import time

        start = time.time()
        result1 = await client.analyze(
            prompt=prompt,
            data=data,
            response_format="text",
            operation="destination_rating",
        )
        time1 = time.time() - start

        print(f"✓ Time: {time1:.2f}s")
        print(f"✓ Cost: ${result1['_cost']:.4f}")

        # Second call - should use cache
        print("\n2nd call (cached)...")
        start = time.time()
        result2 = await client.analyze(
            prompt=prompt,
            data=data,
            response_format="text",
            operation="destination_rating",
        )
        time2 = time.time() - start

        print(f"✓ Time: {time2:.2f}s (should be much faster!)")
        print(f"✓ Cost: ${result2['_cost']:.4f} (same as first call)")
        print(f"✓ Speedup: {time1/time2:.1f}x faster")

        # Get cache stats
        stats = await client.get_cache_stats()
        print(f"\nCache Stats:")
        print(f"  • Cached responses: {stats['cached_responses']}")
        print(f"  • Cache TTL: {stats['cache_ttl']}s ({stats['cache_ttl']/3600:.1f}h)")

    await redis.close()


async def example_custom_analysis():
    """Example: Custom analysis with inline prompt."""
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Custom Analysis")
    print("=" * 60)

    redis = Redis.from_url(str(settings.redis_url))

    async with AsyncSessionLocal() as db:
        client = ClaudeClient(
            api_key=settings.anthropic_api_key,
            redis_client=redis,
            db_session=db,
        )

        # Custom prompt for parent escape analysis
        prompt = """
You are analyzing a hotel for "parent escape" opportunities - times when
parents can relax while kids are safely entertained.

Hotel: {hotel_name}
Features: {features}

Rate the hotel's parent escape potential (0-10) and explain why.
Return JSON with: score, kids_activities, parent_relaxation, recommendation
        """.strip()

        data = {
            "hotel_name": "Family Resort Algarve",
            "features": """
- Kids club (ages 4-12) open 9am-5pm daily
- Supervised beach activities
- Children's pool with waterslides
- Evening kids disco (7-9pm)
- Spa with adults-only area
- Beachfront restaurant with kids menu
- Babysitting service available
- All-inclusive option
            """.strip(),
        }

        print("\nAnalyzing parent escape potential...")

        result = await client.analyze(
            prompt=prompt,
            data=data,
            response_format="json",
            operation="parent_escape_analysis",
            max_tokens=1024,
        )

        print(f"\n✓ Parent Escape Score: {result.get('score', 'N/A')}/10")
        print(f"✓ Recommendation: {result.get('recommendation', 'N/A')}")
        print(f"✓ API Cost: ${result['_cost']:.4f}")
        print(f"✓ Tokens: {result['_tokens']['total']}")

    await redis.close()


async def example_error_handling():
    """Example: Error handling and cost tracking."""
    print("\n" + "=" * 60)
    print("EXAMPLE 5: Error Handling")
    print("=" * 60)

    redis = Redis.from_url(str(settings.redis_url))

    async with AsyncSessionLocal() as db:
        client = ClaudeClient(
            api_key=settings.anthropic_api_key,
            redis_client=redis,
            db_session=db,
        )

        try:
            # This will fail to parse as JSON
            prompt = "Just write a casual sentence about {topic}"
            data = {"topic": "family travel"}

            print("\nTrying to parse text response as JSON (will fail)...")

            result = await client.analyze(
                prompt=prompt,
                data=data,
                response_format="json",  # Requesting JSON but won't get it
                operation="error_test",
            )

        except Exception as e:
            print(f"\n✗ Error caught: {type(e).__name__}")
            print(f"  Message: {str(e)[:100]}...")
            print("\n✓ Error handling working correctly!")

    await redis.close()


async def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("CLAUDE API INTEGRATION EXAMPLES")
    print("=" * 60)
    print(f"Model: {ClaudeClient().model}")
    print(f"Cache TTL: 24 hours")
    print("=" * 60)

    try:
        # Run examples
        await example_deal_analysis()
        await example_event_scoring()
        await example_caching()
        await example_custom_analysis()
        await example_error_handling()

        print("\n" + "=" * 60)
        print("ALL EXAMPLES COMPLETED SUCCESSFULLY!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Example failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    # Check for API key
    if not hasattr(settings, "anthropic_api_key") or not settings.anthropic_api_key:
        print("ERROR: ANTHROPIC_API_KEY not found in environment")
        print("Please set ANTHROPIC_API_KEY in your .env file")
        sys.exit(1)

    # Run examples
    asyncio.run(main())
