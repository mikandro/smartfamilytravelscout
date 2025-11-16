"""
Example usage of the Booking.com scraper for family-friendly accommodations.

This script demonstrates how to:
1. Search for family accommodations on Booking.com
2. Filter results for family-friendly properties
3. Save results to the database
4. Display and analyze the results
"""

import asyncio
import logging
from datetime import date, timedelta

from rich.console import Console
from rich.table import Table

from app.scrapers.booking_scraper import BookingClient, search_booking

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)
console = Console()


async def example_basic_search():
    """
    Example 1: Basic search with auto-filtering and database saving.

    This is the simplest way to use the scraper - it automatically filters
    for family-friendly properties and saves them to the database.
    """
    console.print("\n[bold cyan]Example 1: Basic Search[/bold cyan]")
    console.print("Searching for family accommodations in Lisbon...")

    # Define search parameters
    check_in = date(2025, 12, 20)
    check_out = date(2025, 12, 27)

    # Use the convenience function - it handles everything
    properties = await search_booking(
        city="Lisbon",
        check_in=check_in,
        check_out=check_out,
        save_to_db=True,  # Automatically save to database
        limit=20,  # Get up to 20 properties
    )

    console.print(f"\n[green]Found {len(properties)} family-friendly properties[/green]")

    # Display results in a nice table
    display_properties_table(properties[:5])  # Show first 5

    return properties


async def example_advanced_search():
    """
    Example 2: Advanced search with custom parameters and manual filtering.

    This demonstrates more control over the scraping process, including:
    - Custom search parameters
    - Manual filtering with custom criteria
    - Accessing individual properties
    """
    console.print("\n[bold cyan]Example 2: Advanced Search[/bold cyan]")
    console.print("Searching Barcelona with custom parameters...")

    async with BookingClient(headless=True, rate_limit_seconds=4.0) as client:
        # Search with custom parameters
        properties = await client.search(
            city="Barcelona",
            check_in=date(2025, 7, 15),
            check_out=date(2025, 7, 22),
            adults=2,
            children_ages=[3, 6],
            limit=15,
        )

        console.print(f"\nFound {len(properties)} total properties")

        # Apply custom filtering
        family_friendly = client.filter_family_friendly(
            properties,
            min_bedrooms=2,
            max_price=120.0,  # Lower price threshold
            min_rating=8.0,  # Higher rating threshold
        )

        console.print(f"Filtered to {len(family_friendly)} family-friendly properties")

        # Further filter for apartments with kitchens
        apartments_with_kitchen = [
            p for p in family_friendly
            if p.get("type") == "apartment" and p.get("has_kitchen")
        ]

        console.print(f"Found {len(apartments_with_kitchen)} apartments with kitchens")

        # Display top apartments
        display_properties_table(apartments_with_kitchen[:5])

        # Save to database
        if apartments_with_kitchen:
            saved = await client.save_to_database(apartments_with_kitchen)
            console.print(f"\n[green]Saved {saved} properties to database[/green]")

        return apartments_with_kitchen


async def example_multiple_cities():
    """
    Example 3: Search multiple cities in parallel.

    This demonstrates how to efficiently search multiple destinations
    at once using asyncio.gather().
    """
    console.print("\n[bold cyan]Example 3: Multi-City Search[/bold cyan]")
    console.print("Searching multiple cities in parallel...")

    cities = ["Lisbon", "Porto", "Barcelona"]
    check_in = date.today() + timedelta(days=60)
    check_out = check_in + timedelta(days=7)

    async with BookingClient(headless=True) as client:
        # Search all cities in parallel
        search_tasks = [
            client.search(city, check_in, check_out, limit=10)
            for city in cities
        ]

        results = await asyncio.gather(*search_tasks, return_exceptions=True)

        # Process results
        all_properties = []
        for city, properties in zip(cities, results):
            if isinstance(properties, Exception):
                console.print(f"[red]Error searching {city}: {properties}[/red]")
                continue

            # Filter for family-friendly
            family_friendly = client.filter_family_friendly(properties)
            all_properties.extend(family_friendly)

            console.print(
                f"\n[green]{city}:[/green] Found {len(family_friendly)} "
                f"family-friendly properties"
            )

        # Save all properties
        if all_properties:
            saved = await client.save_to_database(all_properties)
            console.print(f"\n[bold green]Total saved: {saved} properties[/bold green]")

        return all_properties


async def example_analyze_results():
    """
    Example 4: Analyze scraped data.

    This demonstrates how to analyze the scraped properties to find
    the best deals and understand pricing trends.
    """
    console.print("\n[bold cyan]Example 4: Data Analysis[/bold cyan]")

    # Search for properties
    properties = await search_booking(
        city="Lisbon",
        check_in=date(2025, 12, 20),
        check_out=date(2025, 12, 27),
        save_to_db=False,  # Don't save yet
        limit=20,
    )

    if not properties:
        console.print("[yellow]No properties found[/yellow]")
        return

    # Calculate statistics
    prices = [p["price_per_night"] for p in properties if p.get("price_per_night")]
    ratings = [p["rating"] for p in properties if p.get("rating")]

    avg_price = sum(prices) / len(prices) if prices else 0
    avg_rating = sum(ratings) / len(ratings) if ratings else 0

    console.print(f"\n[bold]Statistics:[/bold]")
    console.print(f"Total properties: {len(properties)}")
    console.print(f"Average price: €{avg_price:.2f} per night")
    console.print(f"Average rating: {avg_rating:.1f}/10")
    console.print(f"Price range: €{min(prices):.2f} - €{max(prices):.2f}")

    # Find best value properties (high rating, low price)
    scored_properties = []
    for prop in properties:
        if prop.get("rating") and prop.get("price_per_night"):
            # Simple value score: rating / (price / 10)
            value_score = prop["rating"] / (prop["price_per_night"] / 10)
            scored_properties.append((value_score, prop))

    # Sort by value score
    scored_properties.sort(reverse=True, key=lambda x: x[0])

    console.print(f"\n[bold]Top 3 Best Value Properties:[/bold]")
    for score, prop in scored_properties[:3]:
        console.print(
            f"\n  {prop['name']}"
            f"\n  Price: €{prop['price_per_night']}/night"
            f"\n  Rating: {prop['rating']}/10"
            f"\n  Value Score: {score:.2f}"
            f"\n  Type: {prop['type']}"
        )

    return properties


def display_properties_table(properties):
    """Display properties in a formatted Rich table."""
    if not properties:
        console.print("[yellow]No properties to display[/yellow]")
        return

    table = Table(title="Family-Friendly Accommodations", show_header=True)
    table.add_column("Name", style="cyan", width=30)
    table.add_column("Type", style="magenta")
    table.add_column("Bedrooms", justify="center")
    table.add_column("Price/Night", justify="right", style="green")
    table.add_column("Rating", justify="center", style="yellow")
    table.add_column("Kitchen", justify="center")

    for prop in properties:
        name = prop.get("name", "Unknown")[:27] + "..." if len(prop.get("name", "")) > 30 else prop.get("name", "Unknown")
        prop_type = prop.get("type", "N/A")
        bedrooms = str(prop.get("bedrooms", "?"))
        price = f"€{prop.get('price_per_night', 0):.0f}"
        rating = f"{prop.get('rating', 0):.1f}" if prop.get("rating") else "N/A"
        kitchen = "✓" if prop.get("has_kitchen") else "✗"

        table.add_row(name, prop_type, bedrooms, price, rating, kitchen)

    console.print("\n")
    console.print(table)


async def main():
    """Run all examples."""
    console.print("[bold magenta]Booking.com Scraper Examples[/bold magenta]")
    console.print("=" * 60)

    try:
        # Run examples
        await example_basic_search()
        await asyncio.sleep(2)  # Be respectful between searches

        await example_advanced_search()
        await asyncio.sleep(2)

        # Uncomment to run multi-city search (takes longer)
        # await example_multiple_cities()
        # await asyncio.sleep(2)

        await example_analyze_results()

        console.print("\n[bold green]All examples completed successfully![/bold green]")

    except Exception as e:
        logger.error(f"Error running examples: {e}", exc_info=True)
        console.print(f"\n[bold red]Error: {e}[/bold red]")


if __name__ == "__main__":
    # Run the examples
    asyncio.run(main())
