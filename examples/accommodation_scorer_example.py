#!/usr/bin/env python3
"""
Accommodation Scorer Example

This example demonstrates how to use the AccommodationScorer to:
1. Compare accommodations from different booking platforms
2. Calculate price per person per night
3. Score accommodations on price-quality, family-suitability, and overall quality
4. Rank accommodations to find the best options

The scorer evaluates accommodations across multiple dimensions:
- Price-to-quality ratio (value for money)
- Family suitability (family-friendly features, space, amenities)
- Overall quality (rating, review count, credibility)

Usage:
    poetry run python examples/accommodation_scorer_example.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table import Table

from app.ai.accommodation_scorer import AccommodationScorer
from app.database import get_async_session_context
from app.models.accommodation import Accommodation
from sqlalchemy import select

console = Console()


async def main():
    """Run accommodation scoring examples."""

    console.print("\n[bold cyan]🏨 Accommodation Scorer Demo[/bold cyan]\n")

    async with get_async_session_context() as db:
        # Fetch sample accommodations
        console.print("[yellow]Fetching accommodations from database...[/yellow]")
        stmt = select(Accommodation).limit(20)
        result = await db.execute(stmt)
        accommodations = list(result.scalars().all())

        if not accommodations:
            console.print(
                "[red]No accommodations found in database. "
                "Please run scrapers first:[/red]"
            )
            console.print("  poetry run scout scrape --origin MUC --destination BCN")
            return

        console.print(f"[green]Found {len(accommodations)} accommodations[/green]\n")

        # Initialize scorer
        scorer = AccommodationScorer()

        # Score and compare all accommodations
        console.print("[bold]Scoring all accommodations...[/bold]")
        ranked_results = scorer.compare_accommodations(accommodations)

        # Display results in a table
        table = Table(title="🏆 Accommodation Rankings (Top 10)")
        table.add_column("Rank", style="cyan", justify="right")
        table.add_column("Name", style="white", max_width=30)
        table.add_column("City", style="green")
        table.add_column("Source", style="yellow")
        table.add_column("Price/Night", style="magenta", justify="right")
        table.add_column("€/Person", style="blue", justify="right")
        table.add_column("Score", style="bold green", justify="right")
        table.add_column("Value", style="cyan")

        for i, result in enumerate(ranked_results[:10], 1):
            accommodation = result["accommodation"]
            table.add_row(
                str(i),
                accommodation.name[:30],
                accommodation.destination_city,
                accommodation.source,
                f"€{accommodation.price_per_night:.2f}",
                f"€{result['price_per_person_per_night']:.2f}",
                f"{result['overall_score']:.1f}/100",
                result["value_category"],
            )

        console.print(table)

        # Show detailed breakdown for top accommodation
        if ranked_results:
            console.print(
                "\n[bold cyan]📊 Detailed Breakdown - Top Accommodation:[/bold cyan]\n"
            )
            top_result = ranked_results[0]
            top_accommodation = top_result["accommodation"]

            console.print(f"[bold]Name:[/bold] {top_accommodation.name}")
            console.print(f"[bold]City:[/bold] {top_accommodation.destination_city}")
            console.print(f"[bold]Source:[/bold] {top_accommodation.source}")
            console.print(
                f"[bold]Rating:[/bold] {top_accommodation.rating or 'N/A'}/10"
            )
            console.print(
                f"[bold]Reviews:[/bold] {top_accommodation.review_count or 'N/A'}"
            )
            console.print(
                f"[bold]Bedrooms:[/bold] {top_accommodation.bedrooms or 'N/A'}"
            )

            console.print(f"\n[bold cyan]💰 Pricing:[/bold cyan]")
            console.print(
                f"  Price per night: €{top_accommodation.price_per_night:.2f}"
            )
            console.print(
                f"  Price per person per night: "
                f"€{top_result['price_per_person_per_night']:.2f}"
            )
            console.print(
                f"  Estimated capacity: {top_result['estimated_capacity']} persons"
            )

            console.print(f"\n[bold cyan]📈 Scores:[/bold cyan]")
            console.print(
                f"  Overall Score: [bold green]{top_result['overall_score']:.1f}/100[/bold green]"
            )
            console.print(
                f"  Price-Quality Score: {top_result['price_quality_score']:.1f}/100"
            )
            console.print(
                f"  Family Suitability: {top_result['family_suitability_score']:.1f}/100"
            )
            console.print(f"  Quality Score: {top_result['quality_score']:.1f}/100")

            console.print(f"\n[bold cyan]👨‍👩‍👧‍👦 Family Features:[/bold cyan]")
            features = top_result["family_features"]
            console.print(
                f"  Family-friendly: {'✓' if features['family_friendly'] else '✗'}"
            )
            console.print(f"  Kitchen: {'✓' if features['has_kitchen'] else '✗'}")
            console.print(f"  Kids club: {'✓' if features['has_kids_club'] else '✗'}")
            console.print(
                f"  Adequate bedrooms: {'✓' if features['adequate_bedrooms'] else '✗'}"
            )

            console.print(f"\n[bold cyan]💡 Assessment:[/bold cyan]")
            console.print(f"  {top_result['comparison_notes']}")

        # Show value category distribution
        console.print("\n[bold cyan]📊 Value Distribution:[/bold cyan]")
        value_counts = {}
        for result in ranked_results:
            category = result["value_category"]
            value_counts[category] = value_counts.get(category, 0) + 1

        for category in ["excellent", "good", "average", "poor"]:
            count = value_counts.get(category, 0)
            if count > 0:
                percentage = (count / len(ranked_results)) * 100
                console.print(f"  {category.capitalize()}: {count} ({percentage:.1f}%)")

        # Show filtering example
        console.print("\n[bold cyan]🔍 Filtering Example:[/bold cyan]")
        good_accommodations = scorer.filter_by_score(accommodations, min_score=70.0)
        console.print(
            f"  Accommodations with score >= 70: "
            f"[bold green]{len(good_accommodations)}[/bold green] out of {len(accommodations)}"
        )

        console.print("\n[bold green]✨ Demo complete![/bold green]\n")


if __name__ == "__main__":
    asyncio.run(main())
