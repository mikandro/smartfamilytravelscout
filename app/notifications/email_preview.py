"""
Email preview and testing utilities.
Generate HTML previews and send test emails.
"""

import argparse
import asyncio
import logging
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import List

from app.config import get_settings
from app.models.trip_package import TripPackage
from app.notifications.email_sender import create_email_notifier

logger = logging.getLogger(__name__)


def create_sample_deals(count: int = 5) -> List[TripPackage]:
    """
    Create sample trip packages for testing.

    Args:
        count: Number of sample deals to create

    Returns:
        List of TripPackage instances
    """
    destinations = [
        ("Barcelona", 87.5, "Perfect family destination with beautiful beaches, park Güell, and incredible food culture. Kids will love the aquarium and interactive science museum."),
        ("Prague", 92.0, "Charming city with fairy-tale architecture, affordable prices, and family-friendly attractions. The castle tour is a must-do with children!"),
        ("Lisbon", 85.5, "Vibrant coastal city with trams, castles, and amazing seafood. Great weather and very affordable for families."),
        ("Vienna", 78.0, "Cultural hub with stunning palaces, the famous Prater amusement park, and excellent public transportation for families."),
        ("Amsterdam", 81.5, "Canal city with world-class museums, bike-friendly streets, and plenty of parks for kids to play."),
    ]

    deals = []
    base_date = date.today() + timedelta(days=30)

    for i in range(min(count, len(destinations))):
        dest_city, score, reasoning = destinations[i]

        # Create mock TripPackage
        deal = TripPackage()
        deal.id = i + 1
        deal.package_type = "family"
        deal.destination_city = dest_city
        deal.departure_date = base_date + timedelta(days=i * 7)
        deal.return_date = deal.departure_date + timedelta(days=7)
        deal.num_nights = 7
        deal.total_price = Decimal(1200 + (i * 100))
        deal.ai_score = Decimal(score)
        deal.ai_reasoning = reasoning
        deal.flights_json = {}
        deal.accommodation_id = None
        deal.events_json = None
        deal.notified = False

        deals.append(deal)

    return deals


def create_sample_exceptional_deal() -> TripPackage:
    """Create a sample exceptional deal for alert testing."""
    deal = TripPackage()
    deal.id = 999
    deal.package_type = "family"
    deal.destination_city = "Barcelona"
    deal.departure_date = date.today() + timedelta(days=45)
    deal.return_date = deal.departure_date + timedelta(days=7)
    deal.num_nights = 7
    deal.total_price = Decimal(899.99)
    deal.ai_score = Decimal(95.5)
    deal.ai_reasoning = (
        "Outstanding value! This package combines direct flights, beachfront accommodation, "
        "and perfect timing during local festivals. The price is 40% below market average. "
        "Barcelona's family-friendly attractions, excellent weather, and this incredible price "
        "make this an exceptional opportunity."
    )
    deal.flights_json = {}
    deal.accommodation_id = None
    deal.events_json = None
    deal.notified = False

    return deal


def create_sample_parent_escapes(count: int = 5) -> List[TripPackage]:
    """Create sample parent escape packages for testing."""
    destinations = [
        ("Santorini", 94.0, "Incredibly romantic Greek island with stunning sunsets, luxury hotels, and world-class dining. Perfect for couples seeking relaxation."),
        ("Venice", 88.5, "Classic romantic destination with gondola rides, intimate restaurants, and timeless charm. Ideal for anniversaries."),
        ("Paris", 91.0, "The city of love! Charming cafes, the Eiffel Tower, and endless romantic walks along the Seine."),
        ("Dubrovnik", 86.0, "Beautiful coastal city with historic charm, excellent wine, and peaceful beaches. Great for a relaxing couples retreat."),
        ("Porto", 82.5, "Wine region with stunning views, intimate cellars, and a relaxed atmosphere perfect for couples."),
    ]

    escapes = []
    base_date = date.today() + timedelta(days=20)

    for i in range(min(count, len(destinations))):
        dest_city, score, reasoning = destinations[i]

        escape = TripPackage()
        escape.id = 100 + i
        escape.package_type = "parent_escape"
        escape.destination_city = dest_city
        escape.departure_date = base_date + timedelta(days=i * 14)
        escape.return_date = escape.departure_date + timedelta(days=3)
        escape.num_nights = 3
        escape.total_price = Decimal(600 + (i * 75))
        escape.ai_score = Decimal(score)
        escape.ai_reasoning = reasoning
        escape.flights_json = {}
        escape.accommodation_id = None
        escape.events_json = None
        escape.notified = False

        escapes.append(escape)

    return escapes


def save_html_preview(html_content: str, filename: str) -> Path:
    """
    Save HTML content to file for preview.

    Args:
        html_content: HTML content to save
        filename: Output filename

    Returns:
        Path to saved file
    """
    output_dir = Path("email_previews")
    output_dir.mkdir(exist_ok=True)

    output_path = output_dir / filename
    output_path.write_text(html_content, encoding="utf-8")

    return output_path


async def preview_daily_digest():
    """Generate and save preview of daily digest email."""
    print("Generating daily digest preview...")

    notifier = create_email_notifier()
    deals = create_sample_deals(5)

    html_content = notifier.preview_daily_digest(deals)
    output_path = save_html_preview(html_content, "daily_digest_preview.html")

    print(f"✓ Daily digest preview saved to: {output_path}")
    print(f"  Open file://{output_path.absolute()} in your browser to view")


async def preview_deal_alert():
    """Generate and save preview of deal alert email."""
    print("Generating deal alert preview...")

    notifier = create_email_notifier()
    deal = create_sample_exceptional_deal()

    html_content = notifier.preview_deal_alert(deal)
    output_path = save_html_preview(html_content, "deal_alert_preview.html")

    print(f"✓ Deal alert preview saved to: {output_path}")
    print(f"  Open file://{output_path.absolute()} in your browser to view")


async def preview_parent_escape():
    """Generate and save preview of parent escape digest email."""
    print("Generating parent escape digest preview...")

    notifier = create_email_notifier()
    escapes = create_sample_parent_escapes(5)

    html_content = notifier.preview_parent_escape(escapes)
    output_path = save_html_preview(html_content, "parent_escape_preview.html")

    print(f"✓ Parent escape digest preview saved to: {output_path}")
    print(f"  Open file://{output_path.absolute()} in your browser to view")


async def send_test_daily_digest(to_email: str):
    """Send test daily digest email."""
    print(f"Sending test daily digest to {to_email}...")

    settings = get_settings()
    if not settings.smtp_user or not settings.smtp_password:
        print("❌ Error: SMTP credentials not configured in .env file")
        print("   Please set SMTP_USER and SMTP_PASSWORD")
        return

    notifier = create_email_notifier(user_email=to_email)
    deals = create_sample_deals(5)

    success = await notifier.send_daily_digest(deals)

    if success:
        print(f"✓ Test email sent successfully to {to_email}")
    else:
        print("❌ Failed to send test email. Check logs for details.")


async def send_test_deal_alert(to_email: str):
    """Send test deal alert email."""
    print(f"Sending test deal alert to {to_email}...")

    settings = get_settings()
    if not settings.smtp_user or not settings.smtp_password:
        print("❌ Error: SMTP credentials not configured in .env file")
        print("   Please set SMTP_USER and SMTP_PASSWORD")
        return

    notifier = create_email_notifier(user_email=to_email)
    deal = create_sample_exceptional_deal()

    success = await notifier.send_deal_alert(deal)

    if success:
        print(f"✓ Test alert sent successfully to {to_email}")
    else:
        print("❌ Failed to send test alert. Check logs for details.")


async def send_test_parent_escape(to_email: str):
    """Send test parent escape digest email."""
    print(f"Sending test parent escape digest to {to_email}...")

    settings = get_settings()
    if not settings.smtp_user or not settings.smtp_password:
        print("❌ Error: SMTP credentials not configured in .env file")
        print("   Please set SMTP_USER and SMTP_PASSWORD")
        return

    notifier = create_email_notifier(user_email=to_email)
    escapes = create_sample_parent_escapes(5)

    success = await notifier.send_parent_escape_digest(escapes)

    if success:
        print(f"✓ Test email sent successfully to {to_email}")
    else:
        print("❌ Failed to send test email. Check logs for details.")


async def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Email notification system preview and testing tool"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Preview commands
    preview_parser = subparsers.add_parser("preview", help="Generate HTML previews")
    preview_parser.add_argument(
        "template",
        choices=["daily", "alert", "escape", "all"],
        help="Template to preview",
    )

    # Send test commands
    send_parser = subparsers.add_parser("send", help="Send test email")
    send_parser.add_argument(
        "template",
        choices=["daily", "alert", "escape"],
        help="Email type to send",
    )
    send_parser.add_argument("email", help="Recipient email address")

    args = parser.parse_args()

    if args.command == "preview":
        if args.template in ["daily", "all"]:
            await preview_daily_digest()
        if args.template in ["alert", "all"]:
            await preview_deal_alert()
        if args.template in ["escape", "all"]:
            await preview_parent_escape()

        if args.template == "all":
            print("\n✓ All previews generated successfully!")

    elif args.command == "send":
        if args.template == "daily":
            await send_test_daily_digest(args.email)
        elif args.template == "alert":
            await send_test_deal_alert(args.email)
        elif args.template == "escape":
            await send_test_parent_escape(args.email)

    else:
        parser.print_help()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
