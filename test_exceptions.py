#!/usr/bin/env python3
"""
Test script to verify improved error messages.

This script demonstrates the enhanced exceptions with informative error messages.
Run with: python test_exceptions.py
"""

import sys
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import exceptions directly (standalone module)
import importlib.util
spec = importlib.util.spec_from_file_location("exceptions", "app/exceptions.py")
exceptions = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exceptions)

DatabaseConnectionError = exceptions.DatabaseConnectionError
APIKeyMissingError = exceptions.APIKeyMissingError
ScraperInitializationError = exceptions.ScraperInitializationError
ConfigurationError = exceptions.ConfigurationError
DataValidationError = exceptions.DataValidationError
SMTPConfigurationError = exceptions.SMTPConfigurationError
PlaywrightNotInstalledError = exceptions.PlaywrightNotInstalledError
ScrapingError = exceptions.ScrapingError


def test_database_connection_error():
    """Test DatabaseConnectionError."""
    print("\n" + "="*80)
    print("Testing DatabaseConnectionError")
    print("="*80)
    try:
        raise DatabaseConnectionError(
            connection_type="async (asyncpg)",
            error_details="FATAL: password authentication failed for user 'postgres'"
        )
    except DatabaseConnectionError as e:
        print(str(e))


def test_api_key_missing_error():
    """Test APIKeyMissingError."""
    print("\n" + "="*80)
    print("Testing APIKeyMissingError")
    print("="*80)
    try:
        raise APIKeyMissingError(
            service="Kiwi.com API",
            env_var="KIWI_API_KEY",
            optional=True,
            fallback_info="You can use the default scrapers instead (Skyscanner, Ryanair, WizzAir)"
        )
    except APIKeyMissingError as e:
        print(str(e))


def test_scraper_initialization_error():
    """Test ScraperInitializationError."""
    print("\n" + "="*80)
    print("Testing ScraperInitializationError")
    print("="*80)
    try:
        raise ScraperInitializationError(
            scraper_name="Ryanair",
            component="browser page",
            error_details="Page object failed to initialize after browser startup"
        )
    except ScraperInitializationError as e:
        print(str(e))


def test_playwright_not_installed_error():
    """Test PlaywrightNotInstalledError."""
    print("\n" + "="*80)
    print("Testing PlaywrightNotInstalledError")
    print("="*80)
    try:
        raise PlaywrightNotInstalledError(scraper_name="Airbnb")
    except PlaywrightNotInstalledError as e:
        print(str(e))


def test_scraping_error():
    """Test ScrapingError."""
    print("\n" + "="*80)
    print("Testing ScrapingError")
    print("="*80)
    try:
        raise ScrapingError(
            scraper_name="Skyscanner",
            reason="Request timeout after 30 seconds",
            url="https://www.skyscanner.com/transport/flights/muc/bcn",
            http_status=None,
            timeout=30
        )
    except ScrapingError as e:
        print(str(e))


def test_smtp_configuration_error():
    """Test SMTPConfigurationError."""
    print("\n" + "="*80)
    print("Testing SMTPConfigurationError")
    print("="*80)
    try:
        raise SMTPConfigurationError(
            issue="Authentication failed",
            smtp_details={
                "host": "smtp.gmail.com",
                "port": 587,
                "user": "user@example.com",
                "password": "secret123"
            }
        )
    except SMTPConfigurationError as e:
        print(str(e))


def main():
    """Run all exception tests."""
    print("\n" + "#"*80)
    print("# TESTING IMPROVED ERROR MESSAGES (Issue #57)")
    print("#"*80)

    test_database_connection_error()
    test_api_key_missing_error()
    test_scraper_initialization_error()
    test_playwright_not_installed_error()
    test_scraping_error()
    test_smtp_configuration_error()

    print("\n" + "="*80)
    print("All exception tests completed successfully!")
    print("="*80)
    print("\nNOTE: The above errors demonstrate the improved error messages.")
    print("Users now receive actionable guidance on how to fix issues.")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
