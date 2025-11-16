"""
String utility functions for SmartFamilyTravelScout.

Provides text cleaning, normalization, and parsing functions.
"""

import re
from typing import Dict, List

# City name mappings (local name → English name)
CITY_NAME_MAPPINGS: Dict[str, str] = {
    # German cities
    "münchen": "Munich",
    "muenchen": "Munich",
    "köln": "Cologne",
    "koeln": "Cologne",
    "nürnberg": "Nuremberg",
    "nuernberg": "Nuremberg",
    # Austrian cities
    "wien": "Vienna",
    # Swiss cities
    "zürich": "Zurich",
    "zuerich": "Zurich",
    "genf": "Geneva",
    "genève": "Geneva",
    "bern": "Bern",
    # Italian cities
    "roma": "Rome",
    "milano": "Milan",
    "venezia": "Venice",
    "firenze": "Florence",
    "napoli": "Naples",
    # French cities
    "paris": "Paris",
    "marseille": "Marseille",
    "lyon": "Lyon",
    "nice": "Nice",
    "strasbourg": "Strasbourg",
    # Spanish cities
    "barcelona": "Barcelona",
    "madrid": "Madrid",
    "sevilla": "Seville",
    "zaragoza": "Zaragoza",
    # Portuguese cities
    "lisboa": "Lisbon",
    "porto": "Porto",
    # Czech cities
    "praha": "Prague",
    # Polish cities
    "warszawa": "Warsaw",
    "kraków": "Krakow",
    "krakow": "Krakow",
    # Hungarian cities
    "budapest": "Budapest",
    # Croatian cities
    "zagreb": "Zagreb",
    # Greek cities
    "athína": "Athens",
    "athina": "Athens",
    # Danish cities
    "københavn": "Copenhagen",
    "kobenhavn": "Copenhagen",
    # Swedish cities
    "stockholm": "Stockholm",
    # Norwegian cities
    "oslo": "Oslo",
}


def clean_text(text: str) -> str:
    """
    Remove extra whitespace and normalize text.

    - Removes leading/trailing whitespace
    - Replaces multiple spaces with single space
    - Removes extra newlines
    - Removes non-breaking spaces

    Args:
        text: Text to clean

    Returns:
        Cleaned text

    Examples:
        >>> clean_text("  Hello   world  ")
        'Hello world'
        >>> clean_text("Line1\\n\\n\\nLine2")
        'Line1 Line2'
        >>> clean_text("Text\\xa0with\\xa0nbsp")
        'Text with nbsp'
    """
    if not text or not isinstance(text, str):
        return ""

    # Replace non-breaking spaces
    text = text.replace("\xa0", " ")

    # Replace newlines and tabs with spaces
    text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")

    # Remove multiple spaces
    text = re.sub(r"\s+", " ", text)

    # Strip leading/trailing whitespace
    text = text.strip()

    return text


def extract_numbers(text: str) -> List[float]:
    """
    Extract all numbers from text.

    Supports:
    - Integers: 123
    - Decimals: 123.45
    - Negative numbers: -123
    - Numbers with commas: 1,234.56 or 1.234,56

    Args:
        text: Text to extract numbers from

    Returns:
        List of numbers as floats

    Examples:
        >>> extract_numbers("Price: €123.45, Quantity: 10")
        [123.45, 10.0]
        >>> extract_numbers("Temperature: -5.5°C")
        [-5.5]
        >>> extract_numbers("No numbers here")
        []
    """
    if not text or not isinstance(text, str):
        return []

    numbers = []

    # Pattern for numbers (including decimals and negative)
    # Matches: 123, 123.45, -123, 1,234.56, 1.234,56
    pattern = r"-?\d+(?:[.,]\d+)?"

    matches = re.findall(pattern, text)

    for match in matches:
        # Replace comma with dot for decimal separator
        # Handle both European (1.234,56) and US (1,234.56) formats
        if "," in match and "." in match:
            # Both separators present - determine which is decimal
            if match.rindex(",") > match.rindex("."):
                # European format: 1.234,56
                match = match.replace(".", "").replace(",", ".")
            else:
                # US format: 1,234.56
                match = match.replace(",", "")
        elif "," in match:
            # Only comma - could be thousands or decimal
            parts = match.split(",")
            if len(parts) == 2 and len(parts[1]) <= 2:
                # Likely decimal: 123,45
                match = match.replace(",", ".")
            else:
                # Likely thousands: 1,234
                match = match.replace(",", "")

        try:
            numbers.append(float(match))
        except ValueError:
            continue

    return numbers


def normalize_city_name(city: str) -> str:
    """
    Normalize city names (local → English names).

    Converts local city names to their English equivalents.
    If no mapping exists, returns the capitalized input.

    Args:
        city: City name in any language

    Returns:
        Normalized city name in English

    Examples:
        >>> normalize_city_name("Lisboa")
        'Lisbon'
        >>> normalize_city_name("Wien")
        'Vienna'
        >>> normalize_city_name("münchen")
        'Munich'
        >>> normalize_city_name("Paris")
        'Paris'
    """
    if not city or not isinstance(city, str):
        return ""

    # Clean and lowercase for matching
    city_clean = clean_text(city).lower()

    # Check mapping
    if city_clean in CITY_NAME_MAPPINGS:
        return CITY_NAME_MAPPINGS[city_clean]

    # Return capitalized version if no mapping
    return city.strip().title()


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length (default: 100)
        suffix: Suffix to add when truncating (default: "...")

    Returns:
        Truncated text

    Examples:
        >>> truncate_text("This is a very long text", 10)
        'This is...'
        >>> truncate_text("Short", 10)
        'Short'
    """
    if not text or not isinstance(text, str):
        return ""

    if max_length <= 0:
        return ""

    if len(text) <= max_length:
        return text

    # Account for suffix length
    max_length = max(0, max_length - len(suffix))

    return text[:max_length] + suffix


def slugify(text: str) -> str:
    """
    Convert text to URL-friendly slug.

    - Converts to lowercase
    - Replaces spaces and special characters with hyphens
    - Removes accents
    - Removes consecutive hyphens

    Args:
        text: Text to slugify

    Returns:
        URL-friendly slug

    Examples:
        >>> slugify("Hello World")
        'hello-world'
        >>> slugify("München, Germany")
        'munchen-germany'
        >>> slugify("  Café & Bar  ")
        'cafe-bar'
    """
    if not text or not isinstance(text, str):
        return ""

    # Convert to lowercase
    text = text.lower()

    # Replace German umlauts
    replacements = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    # Remove accents (basic approach)
    # For more comprehensive accent removal, could use unicodedata
    accent_map = {
        "à": "a",
        "á": "a",
        "â": "a",
        "ã": "a",
        "å": "a",
        "è": "e",
        "é": "e",
        "ê": "e",
        "ë": "e",
        "ì": "i",
        "í": "i",
        "î": "i",
        "ï": "i",
        "ò": "o",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ù": "u",
        "ú": "u",
        "û": "u",
        "ç": "c",
        "ñ": "n",
    }
    for old, new in accent_map.items():
        text = text.replace(old, new)

    # Replace non-alphanumeric characters with hyphens
    text = re.sub(r"[^a-z0-9]+", "-", text)

    # Remove leading/trailing hyphens
    text = text.strip("-")

    # Remove consecutive hyphens
    text = re.sub(r"-+", "-", text)

    return text


def extract_email(text: str) -> str | None:
    """
    Extract email address from text.

    Args:
        text: Text to extract email from

    Returns:
        First email address found, or None if none found

    Examples:
        >>> extract_email("Contact: info@example.com")
        'info@example.com'
        >>> extract_email("No email here") is None
        True
    """
    if not text or not isinstance(text, str):
        return None

    # Simple email pattern
    pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    match = re.search(pattern, text)

    return match.group(0) if match else None


def extract_url(text: str) -> str | None:
    """
    Extract URL from text.

    Args:
        text: Text to extract URL from

    Returns:
        First URL found, or None if none found

    Examples:
        >>> extract_url("Visit https://example.com")
        'https://example.com'
        >>> extract_url("No URL here") is None
        True
    """
    if not text or not isinstance(text, str):
        return None

    # Simple URL pattern
    pattern = r"https?://[^\s<>\"{}|\\^`\[\]]+"
    match = re.search(pattern, text)

    return match.group(0) if match else None


def capitalize_words(text: str, exceptions: List[str] | None = None) -> str:
    """
    Capitalize words in text, with exceptions for small words.

    Args:
        text: Text to capitalize
        exceptions: List of words to keep lowercase (e.g., ['and', 'or', 'the'])

    Returns:
        Text with capitalized words

    Examples:
        >>> capitalize_words("hello world")
        'Hello World'
        >>> capitalize_words("the cat and the dog", exceptions=['the', 'and'])
        'The Cat and the Dog'
    """
    if not text or not isinstance(text, str):
        return ""

    if exceptions is None:
        exceptions = []

    words = text.split()
    capitalized = []

    for i, word in enumerate(words):
        if i == 0 or word.lower() not in exceptions:
            # Capitalize first word or non-exception words
            capitalized.append(word.capitalize())
        else:
            capitalized.append(word.lower())

    return " ".join(capitalized)


def remove_html_tags(text: str) -> str:
    """
    Remove HTML tags from text.

    Args:
        text: Text with HTML tags

    Returns:
        Text without HTML tags

    Examples:
        >>> remove_html_tags("<p>Hello <b>world</b></p>")
        'Hello world'
        >>> remove_html_tags("No tags")
        'No tags'
    """
    if not text or not isinstance(text, str):
        return ""

    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Clean up extra whitespace
    return clean_text(text)


def split_camel_case(text: str) -> str:
    """
    Split camelCase or PascalCase text into words.

    Args:
        text: CamelCase text

    Returns:
        Text with spaces between words

    Examples:
        >>> split_camel_case("helloWorld")
        'hello World'
        >>> split_camel_case("XMLParser")
        'XML Parser'
    """
    if not text or not isinstance(text, str):
        return ""

    # Insert space before uppercase letters
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", text)

    return text


def is_valid_email(email: str) -> bool:
    """
    Check if a string is a valid email address.

    Args:
        email: String to check

    Returns:
        True if valid email, False otherwise

    Examples:
        >>> is_valid_email("test@example.com")
        True
        >>> is_valid_email("invalid.email")
        False
    """
    if not email or not isinstance(email, str):
        return False

    pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$"
    return bool(re.match(pattern, email))


def count_words(text: str) -> int:
    """
    Count words in text.

    Args:
        text: Text to count words in

    Returns:
        Number of words

    Examples:
        >>> count_words("Hello world")
        2
        >>> count_words("One")
        1
        >>> count_words("")
        0
    """
    if not text or not isinstance(text, str):
        return 0

    # Clean text first
    text = clean_text(text)

    if not text:
        return 0

    return len(text.split())
