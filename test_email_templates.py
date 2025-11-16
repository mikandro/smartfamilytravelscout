"""
Simple script to test email template rendering without full app dependencies.
"""

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from jinja2 import Environment, FileSystemLoader


class MockTripPackage:
    """Mock TripPackage for testing."""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def price_per_person(self):
        num_people = 4 if self.package_type == "family" else 2
        return float(self.total_price) / num_people

    @property
    def price_per_night(self):
        if self.num_nights > 0:
            return float(self.total_price) / self.num_nights
        return 0.0


def format_date(value):
    """Format date for display."""
    if isinstance(value, date):
        return value.strftime("%B %d, %Y")
    return str(value)


def format_price(value):
    """Format price with currency symbol."""
    return f"€{float(value):.2f}"


def create_sample_deals():
    """Create sample deals for testing."""
    deals = []
    base_date = date.today() + timedelta(days=30)

    destinations = [
        ("Barcelona", 87.5, "Perfect family destination with beautiful beaches, park Güell, and incredible food culture."),
        ("Prague", 92.0, "Charming city with fairy-tale architecture, affordable prices, and family-friendly attractions."),
        ("Lisbon", 85.5, "Vibrant coastal city with trams, castles, and amazing seafood."),
        ("Vienna", 78.0, "Cultural hub with stunning palaces and the famous Prater amusement park."),
        ("Amsterdam", 81.5, "Canal city with world-class museums and bike-friendly streets."),
    ]

    for i, (city, score, reasoning) in enumerate(destinations):
        deal = MockTripPackage(
            id=i + 1,
            package_type="family",
            destination_city=city,
            departure_date=base_date + timedelta(days=i * 7),
            return_date=base_date + timedelta(days=i * 7 + 7),
            num_nights=7,
            total_price=Decimal(1200 + i * 100),
            ai_score=Decimal(score),
            ai_reasoning=reasoning
        )
        deals.append(deal)

    return deals


def create_sample_alert():
    """Create sample exceptional deal."""
    return MockTripPackage(
        id=999,
        package_type="family",
        destination_city="Barcelona",
        departure_date=date.today() + timedelta(days=45),
        return_date=date.today() + timedelta(days=52),
        num_nights=7,
        total_price=Decimal(899.99),
        ai_score=Decimal(95.5),
        ai_reasoning="Outstanding value! This package combines direct flights, beachfront accommodation, and perfect timing during local festivals."
    )


def create_sample_escapes():
    """Create sample parent escapes."""
    escapes = []
    base_date = date.today() + timedelta(days=20)

    destinations = [
        ("Santorini", 94.0, "Incredibly romantic Greek island with stunning sunsets and luxury hotels."),
        ("Venice", 88.5, "Classic romantic destination with gondola rides and intimate restaurants."),
        ("Paris", 91.0, "The city of love! Charming cafes, the Eiffel Tower, and romantic walks."),
    ]

    for i, (city, score, reasoning) in enumerate(destinations):
        escape = MockTripPackage(
            id=100 + i,
            package_type="parent_escape",
            destination_city=city,
            departure_date=base_date + timedelta(days=i * 14),
            return_date=base_date + timedelta(days=i * 14 + 3),
            num_nights=3,
            total_price=Decimal(600 + i * 75),
            ai_score=Decimal(score),
            ai_reasoning=reasoning
        )
        escapes.append(escape)

    return escapes


def test_templates():
    """Test all email templates."""
    print("Testing email templates...")

    # Setup Jinja2
    templates_dir = Path("app/notifications/templates")
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Add custom filters
    env.filters['round'] = lambda x, decimals=0: round(float(x), int(decimals))
    env.filters['format_date'] = format_date
    env.filters['format_price'] = format_price

    # Create output directory
    output_dir = Path("email_previews")
    output_dir.mkdir(exist_ok=True)

    # Test daily digest
    print("  Rendering daily_digest.html...")
    template = env.get_template("daily_digest.html")
    deals = create_sample_deals()
    html = template.render(
        deals=deals,
        date=date.today(),
        total_deals=len(deals),
        summary=f"Found {len(deals)} great family travel deals today! Here are the top {len(deals)}:"
    )
    (output_dir / "daily_digest_preview.html").write_text(html, encoding='utf-8')
    print(f"    ✓ Saved to email_previews/daily_digest_preview.html")

    # Test deal alert
    print("  Rendering deal_alert.html...")
    template = env.get_template("deal_alert.html")
    deal = create_sample_alert()
    html = template.render(deal=deal, date=date.today())
    (output_dir / "deal_alert_preview.html").write_text(html, encoding='utf-8')
    print(f"    ✓ Saved to email_previews/deal_alert_preview.html")

    # Test parent escape
    print("  Rendering parent_escape.html...")
    template = env.get_template("parent_escape.html")
    escapes = create_sample_escapes()
    html = template.render(
        getaways=escapes,
        date=date.today(),
        total_getaways=len(escapes),
        summary=f"Found {len(escapes)} romantic getaways perfect for parents. Here are the top {len(escapes)}:"
    )
    (output_dir / "parent_escape_preview.html").write_text(html, encoding='utf-8')
    print(f"    ✓ Saved to email_previews/parent_escape_preview.html")

    print("\n✓ All templates rendered successfully!")
    print(f"\nOpen the files in email_previews/ to preview:")
    print(f"  - file://{(output_dir / 'daily_digest_preview.html').absolute()}")
    print(f"  - file://{(output_dir / 'deal_alert_preview.html').absolute()}")
    print(f"  - file://{(output_dir / 'parent_escape_preview.html').absolute()}")


if __name__ == "__main__":
    test_templates()
