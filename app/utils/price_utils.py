"""
Price utility functions for SmartFamilyTravelScout.

Provides functions for parsing, formatting, and calculating prices.
"""

import re
from typing import Dict

# Currency conversion rates to EUR (approximate, for normalization)
CURRENCY_TO_EUR: Dict[str, float] = {
    "EUR": 1.0,
    "€": 1.0,
    "USD": 0.92,
    "$": 0.92,
    "GBP": 1.17,
    "£": 1.17,
    "CHF": 1.05,
    "CZK": 0.041,
    "PLN": 0.23,
    "HUF": 0.0026,
    "DKK": 0.134,
    "SEK": 0.088,
    "NOK": 0.087,
}


def normalize_currency(price: str) -> float:
    """
    Convert various price formats to float (in EUR).

    Supports formats like:
    - €123.45, $150, £100
    - 123.45 EUR, 150 USD
    - 1,234.56, 1.234,56
    - 100 (assumes EUR)

    Args:
        price: Price string in various formats

    Returns:
        Price as float in EUR (0.0 if parsing fails)

    Examples:
        >>> normalize_currency("€123.45")
        123.45
        >>> normalize_currency("$150")
        138.0
        >>> normalize_currency("1,234.56 EUR")
        1234.56
        >>> normalize_currency("invalid")
        0.0
    """
    if not price or not isinstance(price, str):
        return 0.0

    price = price.strip()

    # Extract currency symbol or code
    currency = "EUR"  # Default

    # Check for currency symbols
    for curr_symbol in ["€", "$", "£"]:
        if curr_symbol in price:
            currency = curr_symbol
            price = price.replace(curr_symbol, "").strip()
            break

    # Check for currency codes
    for curr_code in ["EUR", "USD", "GBP", "CHF", "CZK", "PLN", "HUF", "DKK", "SEK", "NOK"]:
        if curr_code in price.upper():
            currency = curr_code
            price = price.upper().replace(curr_code, "").strip()
            break

    # Remove common formatting characters
    price = price.replace(" ", "").replace("\xa0", "")  # Remove spaces and non-breaking spaces

    # Handle different decimal separators
    # European format: 1.234,56 -> 1234.56
    if "," in price and "." in price:
        if price.rindex(",") > price.rindex("."):
            # European format (1.234,56)
            price = price.replace(".", "").replace(",", ".")
        else:
            # US format (1,234.56)
            price = price.replace(",", "")
    elif "," in price:
        # Could be decimal separator or thousands separator
        # If there are digits after comma, treat as decimal
        parts = price.split(",")
        if len(parts) == 2 and len(parts[1]) == 2:
            # Likely decimal (123,45)
            price = price.replace(",", ".")
        else:
            # Likely thousands separator (1,234)
            price = price.replace(",", "")

    # Extract numeric value
    try:
        amount = float(price)
    except ValueError:
        # Try to extract first number
        match = re.search(r"[\d.]+", price)
        if match:
            try:
                amount = float(match.group())
            except ValueError:
                return 0.0
        else:
            return 0.0

    # Convert to EUR if needed
    conversion_rate = CURRENCY_TO_EUR.get(currency, 1.0)
    return round(amount * conversion_rate, 2)


def calculate_per_person(total: float, num_people: int = 4) -> float:
    """
    Calculate per-person price from total price.

    Args:
        total: Total price
        num_people: Number of people (default: 4)

    Returns:
        Price per person (rounded to 2 decimal places)

    Examples:
        >>> calculate_per_person(400.0, 4)
        100.0
        >>> calculate_per_person(350.0, 4)
        87.5
        >>> calculate_per_person(100.0, 0)
        0.0
    """
    if total is None or total < 0:
        return 0.0

    if num_people is None or num_people <= 0:
        return 0.0

    return round(total / num_people, 2)


def format_price(price: float, currency: str = "€") -> str:
    """
    Format price nicely with thousands separator.

    Args:
        price: Price as float
        currency: Currency symbol (default: '€')

    Returns:
        Formatted price string (e.g., "€1,234.56")

    Examples:
        >>> format_price(1234.56)
        '€1,234.56'
        >>> format_price(123.5, '$')
        '$123.50'
        >>> format_price(1000000)
        '€1,000,000.00'
    """
    if price is None:
        price = 0.0

    if currency is None:
        currency = "€"

    # Format with thousands separator and 2 decimal places
    formatted = f"{price:,.2f}"

    return f"{currency}{formatted}"


def price_within_range(price: float, min_price: float | None = None, max_price: float | None = None) -> bool:
    """
    Check if price is within specified range.

    Args:
        price: Price to check
        min_price: Minimum price (inclusive). None means no minimum.
        max_price: Maximum price (inclusive). None means no maximum.

    Returns:
        True if price is within range, False otherwise

    Examples:
        >>> price_within_range(100, 50, 150)
        True
        >>> price_within_range(200, 50, 150)
        False
        >>> price_within_range(100, min_price=50)
        True
        >>> price_within_range(100, max_price=150)
        True
    """
    if price is None:
        return False

    if min_price is not None and price < min_price:
        return False

    if max_price is not None and price > max_price:
        return False

    return True


def calculate_total_price(per_person: float, num_people: int = 4) -> float:
    """
    Calculate total price from per-person price.

    Args:
        per_person: Price per person
        num_people: Number of people (default: 4)

    Returns:
        Total price (rounded to 2 decimal places)

    Examples:
        >>> calculate_total_price(100.0, 4)
        400.0
        >>> calculate_total_price(87.5, 4)
        350.0
    """
    if per_person is None or per_person < 0:
        return 0.0

    if num_people is None or num_people <= 0:
        return 0.0

    return round(per_person * num_people, 2)


def calculate_price_per_night(total: float, nights: int) -> float:
    """
    Calculate price per night.

    Args:
        total: Total price
        nights: Number of nights

    Returns:
        Price per night (rounded to 2 decimal places)

    Examples:
        >>> calculate_price_per_night(700.0, 7)
        100.0
        >>> calculate_price_per_night(350.0, 5)
        70.0
    """
    if total is None or total < 0:
        return 0.0

    if nights is None or nights <= 0:
        return 0.0

    return round(total / nights, 2)


def compare_prices(price1: float, price2: float) -> str:
    """
    Compare two prices and return a human-readable comparison.

    Args:
        price1: First price
        price2: Second price

    Returns:
        Comparison string ('cheaper', 'more expensive', 'same')

    Examples:
        >>> compare_prices(100.0, 150.0)
        'cheaper'
        >>> compare_prices(200.0, 150.0)
        'more expensive'
        >>> compare_prices(100.0, 100.0)
        'same'
    """
    if price1 is None or price2 is None:
        return "unknown"

    if abs(price1 - price2) < 0.01:  # Account for floating point precision
        return "same"
    elif price1 < price2:
        return "cheaper"
    else:
        return "more expensive"


def calculate_price_difference(price1: float, price2: float) -> float:
    """
    Calculate the difference between two prices.

    Args:
        price1: First price
        price2: Second price

    Returns:
        Difference (price1 - price2), rounded to 2 decimal places

    Examples:
        >>> calculate_price_difference(150.0, 100.0)
        50.0
        >>> calculate_price_difference(100.0, 150.0)
        -50.0
    """
    if price1 is None or price2 is None:
        return 0.0

    return round(price1 - price2, 2)


def calculate_price_percentage_difference(price1: float, price2: float) -> float:
    """
    Calculate the percentage difference between two prices.

    Args:
        price1: First price (new price)
        price2: Second price (original price)

    Returns:
        Percentage difference (positive = increase, negative = decrease)

    Examples:
        >>> calculate_price_percentage_difference(150.0, 100.0)
        50.0
        >>> calculate_price_percentage_difference(75.0, 100.0)
        -25.0
    """
    if price1 is None or price2 is None or price2 == 0:
        return 0.0

    difference = price1 - price2
    percentage = (difference / price2) * 100

    return round(percentage, 2)


def parse_price_range(price_range: str) -> tuple[float, float] | None:
    """
    Parse a price range string into min and max values.

    Supports formats like:
    - "€100-€200"
    - "$50 - $150"
    - "100-200"

    Args:
        price_range: Price range string

    Returns:
        Tuple of (min_price, max_price) or None if parsing fails

    Examples:
        >>> parse_price_range("€100-€200")
        (100.0, 200.0)
        >>> parse_price_range("$50 - $150")
        (46.0, 138.0)
        >>> parse_price_range("100-200")
        (100.0, 200.0)
    """
    if not price_range or not isinstance(price_range, str):
        return None

    # Split on dash or hyphen
    parts = re.split(r"[-–—]", price_range)

    if len(parts) != 2:
        return None

    try:
        min_price = normalize_currency(parts[0].strip())
        max_price = normalize_currency(parts[1].strip())

        if min_price > 0 and max_price > 0 and min_price <= max_price:
            return (min_price, max_price)
    except (ValueError, TypeError):
        pass

    return None
