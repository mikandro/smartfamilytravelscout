"""
Unit tests for price_utils module.
"""

import pytest

from app.utils.price_utils import (
    normalize_currency,
    calculate_per_person,
    format_price,
    price_within_range,
    calculate_total_price,
    calculate_price_per_night,
    compare_prices,
    calculate_price_difference,
    calculate_price_percentage_difference,
    parse_price_range,
)


class TestNormalizeCurrency:
    """Tests for normalize_currency function."""

    def test_normalize_currency_euro_symbol(self):
        """Test parsing Euro with symbol."""
        assert normalize_currency("€123.45") == 123.45

    def test_normalize_currency_euro_code(self):
        """Test parsing Euro with code."""
        assert normalize_currency("123.45 EUR") == 123.45

    def test_normalize_currency_usd_symbol(self):
        """Test parsing USD with symbol."""
        result = normalize_currency("$150")
        # USD to EUR conversion (approx 0.92)
        assert 135 < result < 145

    def test_normalize_currency_gbp(self):
        """Test parsing GBP."""
        result = normalize_currency("£100")
        # GBP to EUR conversion (approx 1.17)
        assert 115 < result < 120

    def test_normalize_currency_thousands_separator_us(self):
        """Test parsing US format with thousands separator."""
        assert normalize_currency("€1,234.56") == 1234.56

    def test_normalize_currency_thousands_separator_eu(self):
        """Test parsing European format with thousands separator."""
        assert normalize_currency("€1.234,56") == 1234.56

    def test_normalize_currency_no_symbol(self):
        """Test parsing number without currency symbol (assumes EUR)."""
        assert normalize_currency("123.45") == 123.45

    def test_normalize_currency_decimal_comma(self):
        """Test parsing with comma as decimal separator."""
        assert normalize_currency("123,45 EUR") == 123.45

    def test_normalize_currency_invalid(self):
        """Test parsing invalid price."""
        assert normalize_currency("invalid") == 0.0

    def test_normalize_currency_none(self):
        """Test with None."""
        assert normalize_currency(None) == 0.0

    def test_normalize_currency_empty_string(self):
        """Test with empty string."""
        assert normalize_currency("") == 0.0

    def test_normalize_currency_with_spaces(self):
        """Test parsing with spaces."""
        assert normalize_currency("  €  123.45  ") == 123.45


class TestCalculatePerPerson:
    """Tests for calculate_per_person function."""

    def test_calculate_per_person_basic(self):
        """Test basic per-person calculation."""
        assert calculate_per_person(400.0, 4) == 100.0

    def test_calculate_per_person_decimal(self):
        """Test with decimal result."""
        assert calculate_per_person(350.0, 4) == 87.5

    def test_calculate_per_person_one_person(self):
        """Test with one person."""
        assert calculate_per_person(100.0, 1) == 100.0

    def test_calculate_per_person_zero_people(self):
        """Test with zero people."""
        assert calculate_per_person(100.0, 0) == 0.0

    def test_calculate_per_person_negative_total(self):
        """Test with negative total."""
        assert calculate_per_person(-100.0, 4) == 0.0

    def test_calculate_per_person_none_total(self):
        """Test with None total."""
        assert calculate_per_person(None, 4) == 0.0

    def test_calculate_per_person_none_people(self):
        """Test with None people."""
        assert calculate_per_person(100.0, None) == 0.0


class TestFormatPrice:
    """Tests for format_price function."""

    def test_format_price_basic(self):
        """Test basic price formatting."""
        assert format_price(1234.56) == "€1,234.56"

    def test_format_price_no_decimals(self):
        """Test formatting whole number."""
        assert format_price(1000) == "€1,000.00"

    def test_format_price_large_number(self):
        """Test formatting large number."""
        assert format_price(1000000) == "€1,000,000.00"

    def test_format_price_custom_currency(self):
        """Test with custom currency symbol."""
        assert format_price(123.5, "$") == "$123.50"

    def test_format_price_none(self):
        """Test with None price."""
        assert format_price(None) == "€0.00"

    def test_format_price_none_currency(self):
        """Test with None currency."""
        assert format_price(100.0, None) == "€100.00"


class TestPriceWithinRange:
    """Tests for price_within_range function."""

    def test_price_within_range_true(self):
        """Test price within range."""
        assert price_within_range(100, 50, 150) is True

    def test_price_within_range_false_too_low(self):
        """Test price below range."""
        assert price_within_range(40, 50, 150) is False

    def test_price_within_range_false_too_high(self):
        """Test price above range."""
        assert price_within_range(200, 50, 150) is False

    def test_price_within_range_exact_min(self):
        """Test price exactly at minimum."""
        assert price_within_range(50, 50, 150) is True

    def test_price_within_range_exact_max(self):
        """Test price exactly at maximum."""
        assert price_within_range(150, 50, 150) is True

    def test_price_within_range_no_min(self):
        """Test with no minimum."""
        assert price_within_range(100, None, 150) is True
        assert price_within_range(200, None, 150) is False

    def test_price_within_range_no_max(self):
        """Test with no maximum."""
        assert price_within_range(100, 50, None) is True
        assert price_within_range(40, 50, None) is False

    def test_price_within_range_no_limits(self):
        """Test with no limits."""
        assert price_within_range(100, None, None) is True

    def test_price_within_range_none_price(self):
        """Test with None price."""
        assert price_within_range(None, 50, 150) is False


class TestCalculateTotalPrice:
    """Tests for calculate_total_price function."""

    def test_calculate_total_price_basic(self):
        """Test basic total calculation."""
        assert calculate_total_price(100.0, 4) == 400.0

    def test_calculate_total_price_decimal(self):
        """Test with decimal per-person price."""
        assert calculate_total_price(87.5, 4) == 350.0

    def test_calculate_total_price_one_person(self):
        """Test with one person."""
        assert calculate_total_price(100.0, 1) == 100.0

    def test_calculate_total_price_zero_people(self):
        """Test with zero people."""
        assert calculate_total_price(100.0, 0) == 0.0

    def test_calculate_total_price_negative(self):
        """Test with negative per-person price."""
        assert calculate_total_price(-50.0, 4) == 0.0

    def test_calculate_total_price_none(self):
        """Test with None values."""
        assert calculate_total_price(None, 4) == 0.0
        assert calculate_total_price(100.0, None) == 0.0


class TestCalculatePricePerNight:
    """Tests for calculate_price_per_night function."""

    def test_calculate_price_per_night_basic(self):
        """Test basic per-night calculation."""
        assert calculate_price_per_night(700.0, 7) == 100.0

    def test_calculate_price_per_night_decimal(self):
        """Test with decimal result."""
        assert calculate_price_per_night(350.0, 5) == 70.0

    def test_calculate_price_per_night_one_night(self):
        """Test with one night."""
        assert calculate_price_per_night(100.0, 1) == 100.0

    def test_calculate_price_per_night_zero_nights(self):
        """Test with zero nights."""
        assert calculate_price_per_night(100.0, 0) == 0.0

    def test_calculate_price_per_night_negative_total(self):
        """Test with negative total."""
        assert calculate_price_per_night(-100.0, 7) == 0.0

    def test_calculate_price_per_night_none(self):
        """Test with None values."""
        assert calculate_price_per_night(None, 7) == 0.0
        assert calculate_price_per_night(700.0, None) == 0.0


class TestComparePrices:
    """Tests for compare_prices function."""

    def test_compare_prices_cheaper(self):
        """Test price1 cheaper than price2."""
        assert compare_prices(100.0, 150.0) == "cheaper"

    def test_compare_prices_more_expensive(self):
        """Test price1 more expensive than price2."""
        assert compare_prices(200.0, 150.0) == "more expensive"

    def test_compare_prices_same(self):
        """Test same prices."""
        assert compare_prices(100.0, 100.0) == "same"

    def test_compare_prices_nearly_same(self):
        """Test nearly same prices (within 0.01)."""
        assert compare_prices(100.00, 100.009) == "same"

    def test_compare_prices_none(self):
        """Test with None values."""
        assert compare_prices(None, 100.0) == "unknown"
        assert compare_prices(100.0, None) == "unknown"


class TestCalculatePriceDifference:
    """Tests for calculate_price_difference function."""

    def test_calculate_price_difference_positive(self):
        """Test positive difference."""
        assert calculate_price_difference(150.0, 100.0) == 50.0

    def test_calculate_price_difference_negative(self):
        """Test negative difference."""
        assert calculate_price_difference(100.0, 150.0) == -50.0

    def test_calculate_price_difference_zero(self):
        """Test zero difference."""
        assert calculate_price_difference(100.0, 100.0) == 0.0

    def test_calculate_price_difference_none(self):
        """Test with None values."""
        assert calculate_price_difference(None, 100.0) == 0.0
        assert calculate_price_difference(100.0, None) == 0.0


class TestCalculatePricePercentageDifference:
    """Tests for calculate_price_percentage_difference function."""

    def test_calculate_percentage_difference_increase(self):
        """Test percentage increase."""
        assert calculate_price_percentage_difference(150.0, 100.0) == 50.0

    def test_calculate_percentage_difference_decrease(self):
        """Test percentage decrease."""
        assert calculate_price_percentage_difference(75.0, 100.0) == -25.0

    def test_calculate_percentage_difference_double(self):
        """Test doubling (100% increase)."""
        assert calculate_price_percentage_difference(200.0, 100.0) == 100.0

    def test_calculate_percentage_difference_half(self):
        """Test halving (50% decrease)."""
        assert calculate_price_percentage_difference(50.0, 100.0) == -50.0

    def test_calculate_percentage_difference_zero_original(self):
        """Test with zero original price."""
        assert calculate_price_percentage_difference(100.0, 0.0) == 0.0

    def test_calculate_percentage_difference_none(self):
        """Test with None values."""
        assert calculate_price_percentage_difference(None, 100.0) == 0.0
        assert calculate_price_percentage_difference(100.0, None) == 0.0


class TestParsePriceRange:
    """Tests for parse_price_range function."""

    def test_parse_price_range_euro(self):
        """Test parsing Euro price range."""
        result = parse_price_range("€100-€200")
        assert result == (100.0, 200.0)

    def test_parse_price_range_usd(self):
        """Test parsing USD price range."""
        result = parse_price_range("$50 - $150")
        assert result is not None
        assert result[0] < result[1]

    def test_parse_price_range_no_symbol(self):
        """Test parsing price range without currency."""
        result = parse_price_range("100-200")
        assert result == (100.0, 200.0)

    def test_parse_price_range_with_spaces(self):
        """Test parsing with spaces."""
        result = parse_price_range("€100 - €200")
        assert result == (100.0, 200.0)

    def test_parse_price_range_invalid_format(self):
        """Test parsing invalid format."""
        assert parse_price_range("invalid") is None
        assert parse_price_range("100") is None

    def test_parse_price_range_reverse(self):
        """Test parsing reversed range (max < min)."""
        assert parse_price_range("€200-€100") is None

    def test_parse_price_range_none(self):
        """Test with None."""
        assert parse_price_range(None) is None

    def test_parse_price_range_empty(self):
        """Test with empty string."""
        assert parse_price_range("") is None
