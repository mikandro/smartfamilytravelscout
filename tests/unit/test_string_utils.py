"""
Unit tests for string_utils module.
"""

import pytest

from app.utils.string_utils import (
    clean_text,
    extract_numbers,
    normalize_city_name,
    truncate_text,
    slugify,
    extract_email,
    extract_url,
    capitalize_words,
    remove_html_tags,
    split_camel_case,
    is_valid_email,
    count_words,
    CITY_NAME_MAPPINGS,
)


class TestCleanText:
    """Tests for clean_text function."""

    def test_clean_text_extra_spaces(self):
        """Test removing extra spaces."""
        assert clean_text("  Hello   world  ") == "Hello world"

    def test_clean_text_newlines(self):
        """Test replacing newlines with spaces."""
        assert clean_text("Line1\n\n\nLine2") == "Line1 Line2"

    def test_clean_text_nbsp(self):
        """Test removing non-breaking spaces."""
        assert clean_text("Text\xa0with\xa0nbsp") == "Text with nbsp"

    def test_clean_text_tabs(self):
        """Test replacing tabs."""
        assert clean_text("Text\twith\ttabs") == "Text with tabs"

    def test_clean_text_mixed(self):
        """Test cleaning mixed whitespace."""
        assert clean_text("  Text\n\twith  \xa0 mixed  ") == "Text with mixed"

    def test_clean_text_none(self):
        """Test with None."""
        assert clean_text(None) == ""

    def test_clean_text_empty(self):
        """Test with empty string."""
        assert clean_text("") == ""


class TestExtractNumbers:
    """Tests for extract_numbers function."""

    def test_extract_numbers_basic(self):
        """Test extracting basic numbers."""
        assert extract_numbers("Price: €123.45, Quantity: 10") == [123.45, 10.0]

    def test_extract_numbers_negative(self):
        """Test extracting negative numbers."""
        assert extract_numbers("Temperature: -5.5°C") == [-5.5]

    def test_extract_numbers_no_numbers(self):
        """Test with no numbers."""
        assert extract_numbers("No numbers here") == []

    def test_extract_numbers_decimal_comma(self):
        """Test extracting numbers with comma decimal separator."""
        result = extract_numbers("Price: 123,45")
        assert len(result) == 1
        assert 123.4 <= result[0] <= 123.5

    def test_extract_numbers_thousands_separator(self):
        """Test extracting numbers with thousands separator."""
        result = extract_numbers("Total: 1,234.56")
        assert len(result) == 1
        assert 1234.0 <= result[0] <= 1235.0

    def test_extract_numbers_none(self):
        """Test with None."""
        assert extract_numbers(None) == []

    def test_extract_numbers_empty(self):
        """Test with empty string."""
        assert extract_numbers("") == []


class TestNormalizeCityName:
    """Tests for normalize_city_name function."""

    def test_normalize_city_name_lisbon(self):
        """Test normalizing Lisbon."""
        assert normalize_city_name("Lisboa") == "Lisbon"

    def test_normalize_city_name_vienna(self):
        """Test normalizing Vienna."""
        assert normalize_city_name("Wien") == "Vienna"

    def test_normalize_city_name_munich(self):
        """Test normalizing Munich."""
        assert normalize_city_name("münchen") == "Munich"

    def test_normalize_city_name_no_mapping(self):
        """Test city with no mapping."""
        assert normalize_city_name("Paris") == "Paris"

    def test_normalize_city_name_case_insensitive(self):
        """Test case insensitive matching."""
        assert normalize_city_name("LISBOA") == "Lisbon"

    def test_normalize_city_name_none(self):
        """Test with None."""
        assert normalize_city_name(None) == ""

    def test_normalize_city_name_empty(self):
        """Test with empty string."""
        assert normalize_city_name("") == ""


class TestTruncateText:
    """Tests for truncate_text function."""

    def test_truncate_text_basic(self):
        """Test basic truncation."""
        assert truncate_text("This is a very long text", 10) == "This is..."

    def test_truncate_text_no_truncation_needed(self):
        """Test when text is shorter than max length."""
        assert truncate_text("Short", 10) == "Short"

    def test_truncate_text_custom_suffix(self):
        """Test with custom suffix."""
        assert truncate_text("Long text", 5, suffix=">>") == "Lon>>"

    def test_truncate_text_exact_length(self):
        """Test when text is exactly max length."""
        assert truncate_text("12345", 5) == "12345"

    def test_truncate_text_zero_length(self):
        """Test with zero max length."""
        assert truncate_text("Text", 0) == ""

    def test_truncate_text_none(self):
        """Test with None."""
        assert truncate_text(None) == ""


class TestSlugify:
    """Tests for slugify function."""

    def test_slugify_basic(self):
        """Test basic slugification."""
        assert slugify("Hello World") == "hello-world"

    def test_slugify_german_umlauts(self):
        """Test with German umlauts."""
        assert slugify("München, Germany") == "muenchen-germany"

    def test_slugify_special_characters(self):
        """Test with special characters."""
        assert slugify("  Café & Bar  ") == "cafe-bar"

    def test_slugify_accents(self):
        """Test with accented characters."""
        assert slugify("Café") == "cafe"

    def test_slugify_consecutive_hyphens(self):
        """Test removing consecutive hyphens."""
        assert slugify("Hello    World") == "hello-world"

    def test_slugify_none(self):
        """Test with None."""
        assert slugify(None) == ""

    def test_slugify_empty(self):
        """Test with empty string."""
        assert slugify("") == ""


class TestExtractEmail:
    """Tests for extract_email function."""

    def test_extract_email_basic(self):
        """Test extracting basic email."""
        assert extract_email("Contact: info@example.com") == "info@example.com"

    def test_extract_email_complex(self):
        """Test extracting complex email."""
        assert extract_email("Email: user.name+tag@example.co.uk") == "user.name+tag@example.co.uk"

    def test_extract_email_none_found(self):
        """Test with no email."""
        assert extract_email("No email here") is None

    def test_extract_email_none(self):
        """Test with None."""
        assert extract_email(None) is None


class TestExtractUrl:
    """Tests for extract_url function."""

    def test_extract_url_https(self):
        """Test extracting HTTPS URL."""
        assert extract_url("Visit https://example.com") == "https://example.com"

    def test_extract_url_http(self):
        """Test extracting HTTP URL."""
        assert extract_url("Check http://example.com/path") == "http://example.com/path"

    def test_extract_url_with_params(self):
        """Test extracting URL with query parameters."""
        result = extract_url("Link: https://example.com?param=value")
        assert "https://example.com?param=value" in result

    def test_extract_url_none_found(self):
        """Test with no URL."""
        assert extract_url("No URL here") is None

    def test_extract_url_none(self):
        """Test with None."""
        assert extract_url(None) is None


class TestCapitalizeWords:
    """Tests for capitalize_words function."""

    def test_capitalize_words_basic(self):
        """Test basic capitalization."""
        assert capitalize_words("hello world") == "Hello World"

    def test_capitalize_words_with_exceptions(self):
        """Test with exception words."""
        result = capitalize_words("the cat and the dog", exceptions=["the", "and"])
        assert result == "The Cat and the Dog"

    def test_capitalize_words_first_word_always_capitalized(self):
        """Test that first word is always capitalized."""
        result = capitalize_words("the world", exceptions=["the"])
        assert result == "The World"

    def test_capitalize_words_none(self):
        """Test with None."""
        assert capitalize_words(None) == ""

    def test_capitalize_words_empty(self):
        """Test with empty string."""
        assert capitalize_words("") == ""


class TestRemoveHtmlTags:
    """Tests for remove_html_tags function."""

    def test_remove_html_tags_basic(self):
        """Test removing basic HTML tags."""
        assert remove_html_tags("<p>Hello <b>world</b></p>") == "Hello world"

    def test_remove_html_tags_complex(self):
        """Test removing complex HTML."""
        html = '<div class="container"><p>Text</p></div>'
        assert remove_html_tags(html) == "Text"

    def test_remove_html_tags_no_tags(self):
        """Test with no HTML tags."""
        assert remove_html_tags("No tags") == "No tags"

    def test_remove_html_tags_none(self):
        """Test with None."""
        assert remove_html_tags(None) == ""


class TestSplitCamelCase:
    """Tests for split_camel_case function."""

    def test_split_camel_case_basic(self):
        """Test basic camelCase splitting."""
        assert split_camel_case("helloWorld") == "hello World"

    def test_split_camel_case_pascal(self):
        """Test PascalCase splitting."""
        assert split_camel_case("HelloWorld") == "Hello World"

    def test_split_camel_case_acronym(self):
        """Test with acronyms."""
        assert split_camel_case("XMLParser") == "XML Parser"

    def test_split_camel_case_no_split_needed(self):
        """Test with no camelCase."""
        assert split_camel_case("lowercase") == "lowercase"

    def test_split_camel_case_none(self):
        """Test with None."""
        assert split_camel_case(None) == ""


class TestIsValidEmail:
    """Tests for is_valid_email function."""

    def test_is_valid_email_basic(self):
        """Test valid basic email."""
        assert is_valid_email("test@example.com") is True

    def test_is_valid_email_complex(self):
        """Test valid complex email."""
        assert is_valid_email("user.name+tag@example.co.uk") is True

    def test_is_valid_email_invalid_no_at(self):
        """Test invalid email without @."""
        assert is_valid_email("invalid.email") is False

    def test_is_valid_email_invalid_no_domain(self):
        """Test invalid email without domain."""
        assert is_valid_email("test@") is False

    def test_is_valid_email_invalid_no_tld(self):
        """Test invalid email without TLD."""
        assert is_valid_email("test@example") is False

    def test_is_valid_email_none(self):
        """Test with None."""
        assert is_valid_email(None) is False

    def test_is_valid_email_empty(self):
        """Test with empty string."""
        assert is_valid_email("") is False


class TestCountWords:
    """Tests for count_words function."""

    def test_count_words_basic(self):
        """Test basic word counting."""
        assert count_words("Hello world") == 2

    def test_count_words_single_word(self):
        """Test with single word."""
        assert count_words("One") == 1

    def test_count_words_empty(self):
        """Test with empty string."""
        assert count_words("") == 0

    def test_count_words_extra_spaces(self):
        """Test with extra spaces."""
        assert count_words("  Hello   world  ") == 2

    def test_count_words_none(self):
        """Test with None."""
        assert count_words(None) == 0

    def test_count_words_newlines(self):
        """Test with newlines."""
        assert count_words("Hello\nworld") == 2


class TestCityNameMappings:
    """Tests for CITY_NAME_MAPPINGS data."""

    def test_city_name_mappings_not_empty(self):
        """Test that mappings dictionary is not empty."""
        assert len(CITY_NAME_MAPPINGS) > 0

    def test_city_name_mappings_lowercase_keys(self):
        """Test that all keys are lowercase."""
        for key in CITY_NAME_MAPPINGS.keys():
            assert key == key.lower()

    def test_city_name_mappings_has_common_cities(self):
        """Test that common city mappings exist."""
        common_mappings = [
            ("münchen", "Munich"),
            ("wien", "Vienna"),
            ("lisboa", "Lisbon"),
        ]
        for local, english in common_mappings:
            assert local in CITY_NAME_MAPPINGS
            assert CITY_NAME_MAPPINGS[local] == english
