"""
Unit tests for tourism board scrapers.
"""

import os
import pytest
from datetime import date, datetime

# Set test environment variables before importing app modules
os.environ.setdefault('DATABASE_URL', 'postgresql+asyncpg://test:test@localhost/test')
os.environ.setdefault('REDIS_URL', 'redis://localhost:6379/0')
os.environ.setdefault('ANTHROPIC_API_KEY', 'test-key')
os.environ.setdefault('SECRET_KEY', 'test-secret-key')

from app.scrapers.tourism_scraper import TourismDateParser, BaseTourismScraper
from app.scrapers.lisbon_scraper import LisbonTourismScraper
from app.scrapers.prague_scraper import PragueTourismScraper
from app.scrapers.barcelona_scraper import BarcelonaTourismScraper


class TestTourismDateParser:
    """Test the TourismDateParser class."""

    def test_parse_iso_date(self):
        """Test parsing ISO format date."""
        parser = TourismDateParser()
        result = parser.parse_tourism_date("2025-12-20")
        assert result == date(2025, 12, 20)

    def test_parse_european_date(self):
        """Test parsing European format date."""
        parser = TourismDateParser()
        result = parser.parse_tourism_date("20.12.2025")
        assert result == date(2025, 12, 20)

    def test_parse_slash_date(self):
        """Test parsing slash format date."""
        parser = TourismDateParser()
        result = parser.parse_tourism_date("20/12/2025")
        assert result == date(2025, 12, 20)

    def test_parse_month_name_english(self):
        """Test parsing date with English month name."""
        parser = TourismDateParser()
        result = parser.parse_tourism_date("December 20, 2025")
        assert result == date(2025, 12, 20)

    def test_parse_month_name_abbreviated(self):
        """Test parsing date with abbreviated month name."""
        parser = TourismDateParser()
        result = parser.parse_tourism_date("Dec 20, 2025")
        assert result == date(2025, 12, 20)

    def test_parse_month_name_portuguese(self):
        """Test parsing date with Portuguese month name."""
        parser = TourismDateParser()
        result = parser.parse_tourism_date("20 de dezembro 2025")
        assert result == date(2025, 12, 20)

    def test_parse_month_name_spanish(self):
        """Test parsing date with Spanish month name."""
        parser = TourismDateParser()
        result = parser.parse_tourism_date("20 de diciembre 2025")
        assert result == date(2025, 12, 20)

    def test_parse_month_name_czech(self):
        """Test parsing date with Czech month name."""
        parser = TourismDateParser()
        result = parser.parse_tourism_date("20 prosince 2025")
        assert result == date(2025, 12, 20)

    def test_parse_date_without_year(self):
        """Test parsing date without year (should use current year)."""
        parser = TourismDateParser()
        result = parser.parse_tourism_date("December 20", reference_year=2025)
        assert result == date(2025, 12, 20)

    def test_parse_invalid_date(self):
        """Test parsing invalid date string."""
        parser = TourismDateParser()
        result = parser.parse_tourism_date("not a date")
        assert result is None

    def test_parse_empty_string(self):
        """Test parsing empty string."""
        parser = TourismDateParser()
        result = parser.parse_tourism_date("")
        assert result is None

    def test_parse_none(self):
        """Test parsing None."""
        parser = TourismDateParser()
        result = parser.parse_tourism_date(None)
        assert result is None

    def test_parse_date_range_with_dash(self):
        """Test parsing date range with dash."""
        parser = TourismDateParser()
        start, end = parser.parse_date_range("Dec 20 - Dec 25, 2025")
        assert start == date(2025, 12, 20)
        assert end == date(2025, 12, 25)

    def test_parse_date_range_with_to(self):
        """Test parsing date range with 'to'."""
        parser = TourismDateParser()
        start, end = parser.parse_date_range("20.12.2025 to 25.12.2025")
        assert start == date(2025, 12, 20)
        assert end == date(2025, 12, 25)

    def test_parse_single_date_as_range(self):
        """Test parsing single date as range."""
        parser = TourismDateParser()
        start, end = parser.parse_date_range("2025-12-20")
        assert start == date(2025, 12, 20)
        assert end == date(2025, 12, 20)


class TestBaseTourismScraper:
    """Test the BaseTourismScraper class."""

    def test_categorize_event_family(self):
        """Test event categorization - family."""
        scraper = LisbonTourismScraper()
        category = scraper.categorize_event("Family Fun Day", "Activities for children and families")
        assert category == "family"

    def test_categorize_event_cultural(self):
        """Test event categorization - cultural."""
        scraper = LisbonTourismScraper()
        category = scraper.categorize_event("Art Exhibition", "Museum gallery opening")
        assert category == "cultural"

    def test_categorize_event_outdoor(self):
        """Test event categorization - outdoor."""
        scraper = LisbonTourismScraper()
        category = scraper.categorize_event("Park Concert", "Outdoor music in the garden")
        assert category == "outdoor"

    def test_categorize_event_music(self):
        """Test event categorization - music."""
        scraper = LisbonTourismScraper()
        category = scraper.categorize_event("Jazz Concert", "Live music performance")
        assert category == "music"

    def test_categorize_event_default(self):
        """Test event categorization - default to cultural."""
        scraper = LisbonTourismScraper()
        category = scraper.categorize_event("Random Event", "Some description")
        assert category == "cultural"

    def test_extract_price_range_free(self):
        """Test price extraction - free."""
        scraper = LisbonTourismScraper()
        price = scraper.extract_price_range("Free admission for all")
        assert price == "free"

    def test_extract_price_range_free_portuguese(self):
        """Test price extraction - free in Portuguese."""
        scraper = LisbonTourismScraper()
        price = scraper.extract_price_range("Entrada gratuita")
        assert price == "free"

    def test_extract_price_range_cheap(self):
        """Test price extraction - cheap."""
        scraper = LisbonTourismScraper()
        price = scraper.extract_price_range("Tickets €15")
        assert price == "<€20"

    def test_extract_price_range_medium(self):
        """Test price extraction - medium."""
        scraper = LisbonTourismScraper()
        price = scraper.extract_price_range("Price: €35")
        assert price == "€20-50"

    def test_extract_price_range_expensive(self):
        """Test price extraction - expensive."""
        scraper = LisbonTourismScraper()
        price = scraper.extract_price_range("Cost €75 per person")
        assert price == "€50+"

    def test_extract_price_range_no_price(self):
        """Test price extraction - no price info."""
        scraper = LisbonTourismScraper()
        price = scraper.extract_price_range("Join us for fun")
        assert price == "varies"

    def test_make_absolute_url(self):
        """Test converting relative URL to absolute."""
        scraper = LisbonTourismScraper()
        url = scraper.make_absolute_url("/events/concert")
        assert url == "https://www.visitlisboa.com/events/concert"

    def test_make_absolute_url_already_absolute(self):
        """Test absolute URL stays unchanged."""
        scraper = LisbonTourismScraper()
        url = scraper.make_absolute_url("https://example.com/event")
        assert url == "https://example.com/event"

    def test_create_event_dict(self):
        """Test creating standardized event dictionary."""
        scraper = LisbonTourismScraper()
        event = scraper.create_event_dict(
            title="Test Event",
            event_date=date(2025, 12, 20),
            url="/events/test",
            description="Test description",
            price_range="free",
            category="family"
        )

        assert event['destination_city'] == "Lisbon"
        assert event['title'] == "Test Event"
        assert event['event_date'] == date(2025, 12, 20)
        assert event['url'] == "https://www.visitlisboa.com/events/test"
        assert event['description'] == "Test description"
        assert event['price_range'] == "free"
        assert event['category'] == "family"
        assert event['source'] == "tourism_lisbon"


class TestLisbonScraper:
    """Test Lisbon tourism scraper."""

    def test_initialization(self):
        """Test scraper initialization."""
        scraper = LisbonTourismScraper()
        assert scraper.BASE_URL == "https://www.visitlisboa.com"
        assert scraper.CITY_NAME == "Lisbon"
        assert scraper.SOURCE_NAME == "tourism_lisbon"


class TestPragueScraper:
    """Test Prague tourism scraper."""

    def test_initialization(self):
        """Test scraper initialization."""
        scraper = PragueTourismScraper()
        assert scraper.BASE_URL == "https://www.prague.eu"
        assert scraper.CITY_NAME == "Prague"
        assert scraper.SOURCE_NAME == "tourism_prague"


class TestBarcelonaScraper:
    """Test Barcelona tourism scraper."""

    def test_initialization(self):
        """Test scraper initialization."""
        scraper = BarcelonaTourismScraper()
        assert scraper.BASE_URL == "https://www.barcelonaturisme.com"
        assert scraper.CITY_NAME == "Barcelona"
        assert scraper.SOURCE_NAME == "tourism_barcelona"
