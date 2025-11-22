"""
Input validators for CLI commands.
Ensures data quality and provides better error messages.
"""

import re
from datetime import date, datetime
from typing import Optional

import typer


def validate_airport_code(value: str) -> str:
    """
    Validate airport IATA code.

    Must be exactly 3 alphabetic characters (case-insensitive).
    Returns uppercase version of the code.

    Args:
        value: Airport code to validate

    Returns:
        Uppercase airport code

    Raises:
        typer.BadParameter: If code is invalid
    """
    if not value:
        raise typer.BadParameter("Airport code cannot be empty")

    # Remove whitespace
    value = value.strip()

    # Check length
    if len(value) != 3:
        raise typer.BadParameter(
            f"Airport code must be exactly 3 characters (got '{value}' with {len(value)} characters)"
        )

    # Check if all alphabetic
    if not value.isalpha():
        raise typer.BadParameter(
            f"Airport code must contain only letters (got '{value}')"
        )

    # Return uppercase version
    return value.upper()


def validate_date_string(value: Optional[str], allow_past: bool = False) -> Optional[str]:
    """
    Validate date string in YYYY-MM-DD format.

    Args:
        value: Date string to validate (can be None)
        allow_past: If False, rejects dates before today

    Returns:
        The validated date string (unchanged) or None if value is None

    Raises:
        typer.BadParameter: If date is invalid or in the past
    """
    if value is None:
        return None

    # Try to parse the date
    try:
        parsed_date = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as e:
        raise typer.BadParameter(
            f"Invalid date format. Expected YYYY-MM-DD (e.g., 2025-12-25), got '{value}'"
        )

    # Check if date is in the past
    if not allow_past and parsed_date < date.today():
        raise typer.BadParameter(
            f"Date cannot be in the past (got {value}, today is {date.today()})"
        )

    return value


def validate_airport_codes_list(value: str) -> str:
    """
    Validate a comma-separated list of airport codes.

    Special value 'all' is allowed.

    Args:
        value: Comma-separated list of airport codes or 'all'

    Returns:
        Validated string (with codes uppercased)

    Raises:
        typer.BadParameter: If any code is invalid
    """
    if value.lower() == "all":
        return "all"

    # Split by comma and validate each code
    codes = [code.strip() for code in value.split(",")]
    validated_codes = []

    for code in codes:
        validated_codes.append(validate_airport_code(code))

    return ",".join(validated_codes)


# Typer callback functions for use with Option/Argument
def airport_code_callback(value: Optional[str]) -> Optional[str]:
    """Callback for validating airport codes in Typer options."""
    if value is None:
        return None
    return validate_airport_code(value)


def date_callback(value: Optional[str]) -> Optional[str]:
    """Callback for validating dates in Typer options."""
    if value is None:
        return None
    return validate_date_string(value, allow_past=False)


def airport_codes_list_callback(value: Optional[str]) -> Optional[str]:
    """Callback for validating airport code lists in Typer options."""
    if value is None:
        return None
    return validate_airport_codes_list(value)
