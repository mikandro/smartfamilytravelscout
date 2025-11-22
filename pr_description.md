## Summary

This PR addresses issue #57 by implementing comprehensive, informative error messages throughout the application. Users now receive clear explanations of what went wrong, specific remediation instructions, relevant configuration details, and troubleshooting commands.

## Problem

Previously, error messages were generic and unhelpful:
- "Error: Database connection failed" - no guidance on how to fix
- "Error: Invalid API key" - didn't specify which key or where to get it
- "Page not initialized" - no context or troubleshooting steps

This created a poor developer experience and increased support burden.

## Solution

### 1. Created Custom Exceptions Module (`app/exceptions.py`)

Implemented `InformativeException` base class with structured error messaging that includes:
- Clear explanation of what went wrong
- Specific remediation instructions
- Relevant configuration details
- Troubleshooting commands

Specialized exception classes:
- `DatabaseConnectionError` - Database connection failures with setup guidance
- `APIKeyMissingError` - Missing API keys with fallback suggestions
- `ScraperInitializationError` - Scraper initialization issues
- `PlaywrightNotInstalledError` - Playwright setup guidance
- `ScrapingError` - Scraping failures with context (URL, timeout, HTTP status)
- `SMTPConfigurationError` - Email configuration issues
- `ConfigurationError` - General configuration problems
- `DataValidationError` - Data validation failures

### 2. Updated Error Handling Across the Application

**Database (`app/database.py`):**
- Enhanced connection error with masked credentials
- Added detailed logging with troubleshooting steps

**API (`app/api/main.py`):**
- Improved Redis connection errors with configuration details
- Enhanced database startup errors with fix instructions
- Updated global exception handler for better debug context

**Scrapers:**
- `kiwi_scraper.py` - API key error with fallback scraper suggestions
- `eventbrite_scraper.py` - API key error with alternative sources
- `ryanair_scraper.py` - Page initialization error with troubleshooting
- `airbnb_scraper.py` - Playwright installation error with commands
- `barcelona_scraper.py` - Enhanced scraping failure messages

**Email (`app/notifications/email_sender.py`):**
- SMTP authentication errors with Gmail-specific guidance
- Detailed SMTP connection errors with server configuration
- Context-rich error messages with recipient and subject

### 3. Added Test Script (`test_exceptions.py`)

Comprehensive test demonstrating all new exception types and validating error message format.

## Example Improvement

**Before:**
```
ERROR: Database connection failed
```

**After:**
```
================================================================================
ERROR: Database connection failed

DETAILS:
Connection type: async (asyncpg)
Error: FATAL: password authentication failed for user 'postgres'

HOW TO FIX:
1. Ensure PostgreSQL is running
2. Verify DATABASE_URL in your .env file is correct
3. Check network connectivity to the database server
4. Verify database credentials are valid

TROUBLESHOOTING COMMANDS:
  $ docker-compose up -d postgres
  $ docker-compose ps postgres
  $ docker-compose logs postgres
  $ psql $DATABASE_URL -c 'SELECT 1;'
================================================================================
```

## Testing

Run the test script to see all improved error messages:
```bash
python test_exceptions.py
```

## Benefits

✅ Users can self-diagnose and resolve issues independently
✅ Reduced support team workload
✅ Improved developer experience
✅ Clear troubleshooting steps for common problems
✅ Contextual information helps debug faster

## Files Changed

- `app/exceptions.py` - New custom exceptions module
- `app/database.py` - Enhanced database connection errors
- `app/api/main.py` - Improved API startup errors
- `app/scrapers/kiwi_scraper.py` - Better API key errors
- `app/scrapers/eventbrite_scraper.py` - Better API key errors
- `app/scrapers/ryanair_scraper.py` - Page initialization errors
- `app/scrapers/airbnb_scraper.py` - Playwright installation errors
- `app/scrapers/barcelona_scraper.py` - Enhanced scraping errors
- `app/notifications/email_sender.py` - SMTP configuration errors
- `test_exceptions.py` - Test script for validation

Closes #57
