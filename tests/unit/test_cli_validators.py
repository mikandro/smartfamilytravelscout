"""
Unit tests for CLI input validators.
"""

import pytest
from datetime import date, timedelta
import typer

from app.cli.validators import (
    validate_airport_code,
    validate_date_string,
    validate_airport_codes_list,
)


class TestAirportCodeValidator:
    """Tests for airport code validation."""

    def test_valid_uppercase_code(self):
        """Test that valid uppercase codes are accepted."""
        assert validate_airport_code("MUC") == "MUC"
        assert validate_airport_code("BCN") == "BCN"
        assert validate_airport_code("LIS") == "LIS"

    def test_valid_lowercase_code(self):
        """Test that lowercase codes are converted to uppercase."""
        assert validate_airport_code("muc") == "MUC"
        assert validate_airport_code("bcn") == "BCN"
        assert validate_airport_code("lis") == "LIS"

    def test_valid_mixed_case_code(self):
        """Test that mixed case codes are converted to uppercase."""
        assert validate_airport_code("MuC") == "MUC"
        assert validate_airport_code("bCn") == "BCN"

    def test_code_with_whitespace(self):
        """Test that codes with leading/trailing whitespace are accepted."""
        assert validate_airport_code(" MUC ") == "MUC"
        assert validate_airport_code("  BCN  ") == "BCN"

    def test_empty_code(self):
        """Test that empty codes are rejected."""
        with pytest.raises(typer.BadParameter, match="cannot be empty"):
            validate_airport_code("")

    def test_code_too_short(self):
        """Test that codes with less than 3 characters are rejected."""
        with pytest.raises(typer.BadParameter, match="exactly 3 characters"):
            validate_airport_code("AB")
        with pytest.raises(typer.BadParameter, match="exactly 3 characters"):
            validate_airport_code("A")

    def test_code_too_long(self):
        """Test that codes with more than 3 characters are rejected."""
        with pytest.raises(typer.BadParameter, match="exactly 3 characters"):
            validate_airport_code("MUCC")
        with pytest.raises(typer.BadParameter, match="exactly 3 characters"):
            validate_airport_code("INVALID")

    def test_code_with_numbers(self):
        """Test that codes with numbers are rejected."""
        with pytest.raises(typer.BadParameter, match="only letters"):
            validate_airport_code("M1C")
        with pytest.raises(typer.BadParameter, match="only letters"):
            validate_airport_code("123")

    def test_code_with_special_characters(self):
        """Test that codes with special characters are rejected."""
        with pytest.raises(typer.BadParameter, match="only letters"):
            validate_airport_code("M@C")
        with pytest.raises(typer.BadParameter, match="only letters"):
            validate_airport_code("M-C")
        with pytest.raises(typer.BadParameter, match="only letters"):
            validate_airport_code("M_C")


class TestDateValidator:
    """Tests for date validation."""

    def test_valid_future_date(self):
        """Test that valid future dates are accepted."""
        future_date = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")
        assert validate_date_string(future_date) == future_date

    def test_today_is_accepted(self):
        """Test that today's date is accepted."""
        today = date.today().strftime("%Y-%m-%d")
        assert validate_date_string(today) == today

    def test_none_date(self):
        """Test that None is accepted (optional dates)."""
        assert validate_date_string(None) is None

    def test_past_date_rejected(self):
        """Test that past dates are rejected by default."""
        past_date = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        with pytest.raises(typer.BadParameter, match="cannot be in the past"):
            validate_date_string(past_date)

    def test_past_date_allowed_with_flag(self):
        """Test that past dates can be allowed with allow_past flag."""
        past_date = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        assert validate_date_string(past_date, allow_past=True) == past_date

    def test_invalid_format_slash_separator(self):
        """Test that dates with slash separators are rejected."""
        with pytest.raises(typer.BadParameter, match="Invalid date format"):
            validate_date_string("12/25/2025")

    def test_invalid_format_dot_separator(self):
        """Test that dates with dot separators are rejected."""
        with pytest.raises(typer.BadParameter, match="Invalid date format"):
            validate_date_string("25.12.2025")

    def test_invalid_format_wrong_order(self):
        """Test that dates in wrong order are rejected."""
        with pytest.raises(typer.BadParameter, match="Invalid date format"):
            validate_date_string("25-12-2025")  # DD-MM-YYYY instead of YYYY-MM-DD

    def test_invalid_date_values(self):
        """Test that invalid date values are rejected."""
        with pytest.raises(typer.BadParameter, match="Invalid date format"):
            validate_date_string("2025-13-01")  # Invalid month
        with pytest.raises(typer.BadParameter, match="Invalid date format"):
            validate_date_string("2025-02-30")  # Invalid day

    def test_invalid_format_text(self):
        """Test that text instead of date is rejected."""
        with pytest.raises(typer.BadParameter, match="Invalid date format"):
            validate_date_string("tomorrow")
        with pytest.raises(typer.BadParameter, match="Invalid date format"):
            validate_date_string("invalid")


class TestAirportCodesListValidator:
    """Tests for comma-separated airport codes list validation."""

    def test_valid_single_code(self):
        """Test that a single valid code is accepted."""
        assert validate_airport_codes_list("MUC") == "MUC"

    def test_valid_multiple_codes(self):
        """Test that multiple valid codes are accepted."""
        assert validate_airport_codes_list("MUC,BCN,LIS") == "MUC,BCN,LIS"

    def test_codes_with_whitespace(self):
        """Test that codes with whitespace are handled correctly."""
        assert validate_airport_codes_list("MUC, BCN, LIS") == "MUC,BCN,LIS"
        assert validate_airport_codes_list(" MUC , BCN , LIS ") == "MUC,BCN,LIS"

    def test_lowercase_codes_converted(self):
        """Test that lowercase codes are converted to uppercase."""
        assert validate_airport_codes_list("muc,bcn,lis") == "MUC,BCN,LIS"

    def test_all_keyword(self):
        """Test that 'all' keyword is accepted."""
        assert validate_airport_codes_list("all") == "all"
        assert validate_airport_codes_list("ALL") == "all"
        assert validate_airport_codes_list("All") == "all"

    def test_invalid_code_in_list(self):
        """Test that invalid codes in list are rejected."""
        with pytest.raises(typer.BadParameter, match="exactly 3 characters"):
            validate_airport_codes_list("MUC,INVALID,BCN")

    def test_empty_code_in_list(self):
        """Test that empty codes in list are handled."""
        # This will fail because after splitting by comma, we get an empty string
        with pytest.raises(typer.BadParameter, match="cannot be empty"):
            validate_airport_codes_list("MUC,,BCN")

    def test_code_with_numbers_in_list(self):
        """Test that codes with numbers in list are rejected."""
        with pytest.raises(typer.BadParameter, match="only letters"):
            validate_airport_codes_list("MUC,B1N,LIS")
