#!/usr/bin/env python3
"""
Demo script for ParentEscapeAnalyzer.

This script demonstrates the usage of the parent escape analyzer
to find romantic getaway opportunities for parents.
"""

import asyncio
from datetime import date, timedelta

from app.ai.parent_escape_analyzer import ParentEscapeAnalyzer, TRAIN_DESTINATIONS


def display_train_destinations():
    """Display all configured train destinations."""
    print("\n" + "="*80)
    print("TRAIN-ACCESSIBLE ROMANTIC DESTINATIONS FROM MUNICH")
    print("="*80 + "\n")

    # Group by country
    by_country = {}
    for city, info in TRAIN_DESTINATIONS.items():
        country = info["country"]
        if country not in by_country:
            by_country[country] = []
        by_country[country].append((city, info))

    for country in sorted(by_country.keys()):
        print(f"\n🌍 {country.upper()}")
        print("-" * 80)

        for city, info in sorted(by_country[country], key=lambda x: x[1]["travel_time_hours"]):
            travel_time = info["travel_time_hours"]
            features = ", ".join(info["romantic_features"])

            print(f"  📍 {city:20s} {travel_time:3.1f}h   🍷 {features}")

    print("\n" + "="*80)


def display_analyzer_capabilities():
    """Display what the analyzer can do."""
    print("\n" + "="*80)
    print("PARENT ESCAPE ANALYZER CAPABILITIES")
    print("="*80 + "\n")

    capabilities = [
        "✅ Finds train-accessible romantic destinations (< 6 hours from Munich)",
        "✅ Scores destinations based on romantic appeal, spa hotels, wine regions",
        "✅ Analyzes event timing uniqueness (wine festivals, concerts, etc.)",
        "✅ Suggests childcare solutions for kids (ages 3 & 6)",
        "✅ Creates 2-3 night weekend getaway packages",
        "✅ Filters by budget (default: €1,200 for 2 people)",
        "✅ AI-powered scoring using Claude API",
        "✅ Prioritizes destinations with special events",
    ]

    for capability in capabilities:
        print(f"  {capability}")

    print("\n" + "="*80)


def display_example_destinations():
    """Display some example romantic destinations."""
    print("\n" + "="*80)
    print("EXAMPLE ROMANTIC GETAWAY DESTINATIONS")
    print("="*80 + "\n")

    examples = [
        {
            "city": "Vienna",
            "why": "Imperial culture, opera houses, wine taverns, thermal baths",
            "best_for": "Culture lovers, wine enthusiasts",
            "travel_time": "4.0h",
        },
        {
            "city": "Salzburg",
            "why": "Mozart's birthplace, alpine charm, spa hotels, romantic old town",
            "best_for": "Culture & nature, quick weekend trips",
            "travel_time": "1.5h",
        },
        {
            "city": "Bolzano",
            "why": "South Tyrol wine region, thermal spas, Italian cuisine",
            "best_for": "Wine lovers, spa enthusiasts",
            "travel_time": "4.5h",
        },
        {
            "city": "Baden-Baden",
            "why": "World-famous thermal baths, Black Forest, elegant spa town",
            "best_for": "Relaxation seekers, spa lovers",
            "travel_time": "4.0h",
        },
        {
            "city": "Prague",
            "why": "Romantic architecture, classical concerts, Czech beer culture",
            "best_for": "Culture lovers, architecture enthusiasts",
            "travel_time": "5.5h",
        },
    ]

    for example in examples:
        print(f"🌹 {example['city']} ({example['travel_time']} by train)")
        print(f"   Why: {example['why']}")
        print(f"   Best for: {example['best_for']}")
        print()

    print("="*80)


def display_cost_breakdown_example():
    """Display an example cost breakdown for a romantic getaway."""
    print("\n" + "="*80)
    print("EXAMPLE COST BREAKDOWN: 2-Night Weekend in Vienna")
    print("="*80 + "\n")

    # Vienna example
    train_hours = 4.0
    train_cost = train_hours * 30.0 * 2  # Round trip for 2 people
    accommodation = 150.0 * 2  # €150/night × 2 nights
    food = 80.0 * 2  # €80/day for romantic dining
    activities = 60.0 * 2  # €60/day (museums, concerts, etc.)
    total = train_cost + accommodation + food + activities

    print(f"  🚂 Train (Round trip, 2 people):     €{train_cost:>7.2f}")
    print(f"  🏨 Hotel (2 nights, boutique):      €{accommodation:>7.2f}")
    print(f"  🍽️  Dining (2 days, romantic):       €{food:>7.2f}")
    print(f"  🎭 Activities (museums, concerts):  €{activities:>7.2f}")
    print(f"  {'-'*43}")
    print(f"  💰 TOTAL:                            €{total:>7.2f}")
    print(f"\n  Per person: €{total/2:.2f}")

    print("\n" + "="*80)


def display_usage_example():
    """Display code usage example."""
    print("\n" + "="*80)
    print("USAGE EXAMPLE")
    print("="*80 + "\n")

    code = '''
from app.ai.parent_escape_analyzer import ParentEscapeAnalyzer
from app.ai.claude_client import ClaudeClient
from datetime import date, timedelta

# Initialize analyzer
claude_client = ClaudeClient(api_key="...", redis_client=redis)
analyzer = ParentEscapeAnalyzer(claude_client)

# Find romantic getaways for next 3 months
async with get_async_session_context() as db:
    opportunities = await analyzer.find_escape_opportunities(
        db,
        date_range=(date.today(), date.today() + timedelta(days=90)),
        max_budget=1200.0,
        min_nights=2,
        max_nights=3,
    )

    # Print summary
    await analyzer.print_escape_summary(opportunities, show_top=10)

    # Save to database
    for package in opportunities:
        db.add(package)
    await db.commit()
'''

    print(code)
    print("="*80)


def main():
    """Main demo function."""
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*20 + "PARENT ESCAPE MODE ANALYZER" + " "*31 + "║")
    print("║" + " "*15 + "Romantic Getaways for Parents" + " "*34 + "║")
    print("╚" + "="*78 + "╝")

    display_analyzer_capabilities()
    display_train_destinations()
    display_example_destinations()
    display_cost_breakdown_example()
    display_usage_example()

    print("\n✨ ParentEscapeAnalyzer is ready to help parents find romantic escapes! ✨\n")


if __name__ == "__main__":
    main()
