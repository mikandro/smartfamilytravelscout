"""
WizzAir flight scraper using their unofficial API.

This scraper calls WizzAir's internal JSON API endpoints directly,
which is more reliable than HTML scraping and doesn't require JavaScript rendering.

API Endpoint: POST https://be.wizzair.com/*/Api/search/search

Note: This uses an unofficial API that may change. If the scraper stops working,
inspect the network traffic on wizzair.com using browser DevTools to find the
updated API endpoint and request format.
"""

import logging
from datetime import date, datetime, time
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.airport import Airport
from app.models.flight import Flight
from app.utils.retry import api_retry

logger = logging.getLogger(__name__)


class WizzAirAPIError(Exception):
    """Raised when WizzAir API returns an error."""

    pass


class WizzAirRateLimitError(Exception):
    """Raised when WizzAir API rate limit is exceeded."""

    pass


class WizzAirScraper:
    """
    Scraper for WizzAir flights using their unofficial API.

    WizzAir is a budget airline with excellent routes to Eastern Europe,
    particularly Moldova (Chisinau).
    """

    # WizzAir API endpoint (the * is a wildcard for API version)
    BASE_URL = "https://be.wizzair.com/*/Api/search/search"

    # User agent to mimic browser requests
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(self, timeout: int = 30) -> None:
        """
        Initialize the WizzAir scraper.

        Args:
            timeout: HTTP request timeout in seconds (default: 30)
        """
        self.timeout = timeout
        self.headers = {
            "User-Agent": self.USER_AGENT,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": "https://wizzair.com",
            "Referer": "https://wizzair.com/",
        }

    def _build_payload(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        return_date: Optional[date],
        adult_count: int = 2,
        child_count: int = 2,
        infant_count: int = 0,
    ) -> Dict[str, Any]:
        """
        Build the API request payload for WizzAir search.

        Args:
            origin: Origin airport IATA code (e.g., 'MUC')
            destination: Destination airport IATA code (e.g., 'CHI')
            departure_date: Departure date
            return_date: Return date (None for one-way)
            adult_count: Number of adults (default: 2)
            child_count: Number of children (default: 2)
            infant_count: Number of infants (default: 0)

        Returns:
            Dict containing the API request payload
        """
        # Build flight list based on whether it's one-way or round-trip
        flight_list = [
            {
                "departureStation": origin.upper(),
                "arrivalStation": destination.upper(),
                "from": departure_date.strftime("%Y-%m-%d"),
                "to": departure_date.strftime("%Y-%m-%d"),
            }
        ]

        # Add return flight if round-trip
        if return_date:
            flight_list.append(
                {
                    "departureStation": destination.upper(),
                    "arrivalStation": origin.upper(),
                    "from": return_date.strftime("%Y-%m-%d"),
                    "to": return_date.strftime("%Y-%m-%d"),
                }
            )

        payload = {
            "flightList": flight_list,
            "adultCount": adult_count,
            "childCount": child_count,
            "infantCount": infant_count,
        }

        return payload

    @api_retry(max_attempts=3, min_wait_seconds=2, max_wait_seconds=10)
    async def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        return_date: Optional[date] = None,
        adult_count: int = 2,
        child_count: int = 2,
    ) -> List[Dict[str, Any]]:
        """
        Search for flights using WizzAir API with automatic retry logic.

        Args:
            origin: Origin airport IATA code (e.g., 'MUC')
            destination: Destination airport IATA code (e.g., 'CHI')
            departure_date: Departure date
            return_date: Return date (None for one-way)
            adult_count: Number of adults (default: 2)
            child_count: Number of children (default: 2)

        Returns:
            List of flight dictionaries with parsed data

        Raises:
            WizzAirAPIError: If API returns an error
            WizzAirRateLimitError: If rate limit is exceeded
            httpx.HTTPError: If network error occurs after retries
        """
        payload = self._build_payload(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            adult_count=adult_count,
            child_count=child_count,
        )

        logger.info(
            f"Searching WizzAir flights: {origin} -> {destination}, "
            f"departure: {departure_date}, return: {return_date}"
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    self.BASE_URL, headers=self.headers, json=payload
                )

                # Check for rate limiting
                if response.status_code == 429:
                    logger.error("WizzAir API rate limit exceeded")
                    raise WizzAirRateLimitError(
                        "Rate limit exceeded. Please wait 60 seconds before retrying."
                    )

                # Check for other HTTP errors
                response.raise_for_status()

                # Parse JSON response
                data = response.json()

                # Log API call success
                logger.info(f"WizzAir API call successful: {response.status_code}")

                # Parse the response
                flights = self._parse_api_response(
                    data, origin, destination, departure_date, return_date
                )

                logger.info(f"Found {len(flights)} flight combinations from WizzAir")
                return flights

            except WizzAirRateLimitError:
                # Re-raise rate limit error without wrapping
                raise
            except httpx.HTTPStatusError as e:
                logger.error(f"WizzAir API HTTP error: {e.response.status_code} - {e}")
                raise WizzAirAPIError(f"API returned error: {e.response.status_code}") from e
            except httpx.RequestError as e:
                logger.error(f"WizzAir API network error: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error calling WizzAir API: {e}", exc_info=True)
                raise WizzAirAPIError(f"Unexpected error: {e}") from e

    def _parse_api_response(
        self,
        data: Dict[str, Any],
        origin: str,
        destination: str,
        departure_date: date,
        return_date: Optional[date],
    ) -> List[Dict[str, Any]]:
        """
        Parse WizzAir API response into standardized flight format.

        WizzAir API returns:
        {
            "outboundFlights": [{
                "price": {"amount": 45.99, "currencyCode": "EUR"},
                "departureDates": "2025-12-20T14:30:00",
                "arrivalDates": "2025-12-20T17:45:00",
                "flightNumber": "W6 1234"
            }],
            "returnFlights": [...]
        }

        Args:
            data: Raw API response data
            origin: Origin airport IATA code
            destination: Destination airport IATA code
            departure_date: Departure date
            return_date: Return date (None for one-way)

        Returns:
            List of flight dictionaries in standardized format
        """
        flights = []

        # Handle empty response
        if not data or "outboundFlights" not in data:
            logger.warning("No flights found in WizzAir API response")
            return flights

        outbound_flights = data.get("outboundFlights", [])
        return_flights = data.get("returnFlights", [])

        # If no outbound flights, return empty
        if not outbound_flights:
            logger.info("No outbound flights available")
            return flights

        # For round-trip flights, combine outbound and return
        if return_date and return_flights:
            for outbound in outbound_flights:
                for return_flight in return_flights:
                    flight_data = self._combine_flights(
                        outbound, return_flight, origin, destination
                    )
                    if flight_data:
                        flights.append(flight_data)
        else:
            # One-way flights
            for outbound in outbound_flights:
                flight_data = self._parse_single_flight(outbound, origin, destination, False)
                if flight_data:
                    flights.append(flight_data)

        return flights

    def _parse_single_flight(
        self,
        flight_data: Dict[str, Any],
        origin: str,
        destination: str,
        is_return: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a single flight from the API response.

        Args:
            flight_data: Flight data from API
            origin: Origin airport IATA code
            destination: Destination airport IATA code
            is_return: Whether this is a return flight

        Returns:
            Dict with parsed flight data, or None if parsing fails
        """
        try:
            # Extract price
            price_data = flight_data.get("price", {})
            price = float(price_data.get("amount", 0))
            currency = price_data.get("currencyCode", "EUR")

            # Extract times (ISO format: 2025-12-20T14:30:00)
            departure_datetime_str = flight_data.get("departureDates", "")
            arrival_datetime_str = flight_data.get("arrivalDates", "")

            if not departure_datetime_str or not arrival_datetime_str:
                logger.warning("Missing departure or arrival time in flight data")
                return None

            # Parse ISO datetime strings
            departure_dt = datetime.fromisoformat(departure_datetime_str.replace("Z", "+00:00"))
            arrival_dt = datetime.fromisoformat(arrival_datetime_str.replace("Z", "+00:00"))

            # Extract flight number
            flight_number = flight_data.get("flightNumber", "Unknown")

            return {
                "origin": origin.upper(),
                "destination": destination.upper(),
                "departure_date": departure_dt.date(),
                "departure_time": departure_dt.time(),
                "arrival_date": arrival_dt.date(),
                "arrival_time": arrival_dt.time(),
                "price": price,
                "currency": currency,
                "flight_number": flight_number,
                "is_return": is_return,
            }

        except (ValueError, KeyError) as e:
            logger.warning(f"Error parsing flight data: {e}", exc_info=True)
            return None

    def _combine_flights(
        self,
        outbound: Dict[str, Any],
        return_flight: Dict[str, Any],
        origin: str,
        destination: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Combine outbound and return flights into a single round-trip offer.

        Args:
            outbound: Outbound flight data
            return_flight: Return flight data
            origin: Origin airport IATA code
            destination: Destination airport IATA code

        Returns:
            Dict with combined flight data in standardized format
        """
        outbound_parsed = self._parse_single_flight(outbound, origin, destination, False)
        return_parsed = self._parse_single_flight(return_flight, destination, origin, True)

        if not outbound_parsed or not return_parsed:
            return None

        # Calculate total price
        total_price = outbound_parsed["price"] + return_parsed["price"]

        return {
            "origin": origin.upper(),
            "destination": destination.upper(),
            "departure_date": outbound_parsed["departure_date"],
            "departure_time": outbound_parsed["departure_time"],
            "return_date": return_parsed["departure_date"],
            "return_time": return_parsed["departure_time"],
            "price": total_price,
            "currency": outbound_parsed["currency"],
            "outbound_flight_number": outbound_parsed["flight_number"],
            "return_flight_number": return_parsed["flight_number"],
        }

    async def save_flights_to_db(
        self,
        db: AsyncSession,
        flights: List[Dict[str, Any]],
        adult_count: int = 2,
        child_count: int = 2,
    ) -> List[Flight]:
        """
        Save parsed flights to the database.

        Args:
            db: Database session
            flights: List of parsed flight dictionaries
            adult_count: Number of adults for price calculation
            child_count: Number of children for price calculation

        Returns:
            List of created Flight objects
        """
        saved_flights = []
        total_passengers = adult_count + child_count

        for flight_data in flights:
            try:
                # Get airport IDs from IATA codes
                origin_airport = await self._get_airport_by_iata(
                    db, flight_data["origin"]
                )
                destination_airport = await self._get_airport_by_iata(
                    db, flight_data["destination"]
                )

                if not origin_airport or not destination_airport:
                    logger.warning(
                        f"Skipping flight: Airport not found "
                        f"({flight_data['origin']} or {flight_data['destination']})"
                    )
                    continue

                # Calculate price per person and total price
                price_per_person = flight_data["price"]
                total_price = price_per_person * total_passengers

                # Create Flight object
                flight = Flight(
                    origin_airport_id=origin_airport.id,
                    destination_airport_id=destination_airport.id,
                    airline="WizzAir",
                    departure_date=flight_data["departure_date"],
                    departure_time=flight_data.get("departure_time"),
                    return_date=flight_data.get("return_date"),
                    return_time=flight_data.get("return_time"),
                    price_per_person=price_per_person,
                    total_price=total_price,
                    booking_class="Economy",  # WizzAir primarily offers economy
                    direct_flight=True,  # WizzAir mostly operates direct flights
                    source="wizzair",
                    booking_url=f"https://wizzair.com/#/booking/select-flight/{flight_data['origin']}/{flight_data['destination']}/{flight_data['departure_date'].strftime('%Y-%m-%d')}",
                )

                db.add(flight)
                saved_flights.append(flight)

                logger.debug(
                    f"Saved WizzAir flight: {flight_data['origin']} -> "
                    f"{flight_data['destination']}, {flight_data['departure_date']}, "
                    f"€{price_per_person:.2f}/person"
                )

            except Exception as e:
                logger.error(f"Error saving flight to database: {e}", exc_info=True)
                continue

        # Commit all flights
        try:
            await db.commit()
            logger.info(f"Successfully saved {len(saved_flights)} WizzAir flights to database")
        except Exception as e:
            await db.rollback()
            logger.error(f"Error committing flights to database: {e}", exc_info=True)
            raise

        return saved_flights

    async def _get_airport_by_iata(
        self, db: AsyncSession, iata_code: str
    ) -> Optional[Airport]:
        """
        Get airport from database by IATA code.

        Args:
            db: Database session
            iata_code: Airport IATA code (e.g., 'MUC')

        Returns:
            Airport object or None if not found
        """
        result = await db.execute(
            select(Airport).where(Airport.iata_code == iata_code.upper())
        )
        return result.scalar_one_or_none()


# Convenience function for CLI/API usage
async def scrape_wizzair_flights(
    db: AsyncSession,
    origin: str,
    destination: str,
    departure_date: date,
    return_date: Optional[date] = None,
    adult_count: int = 2,
    child_count: int = 2,
) -> List[Flight]:
    """
    Convenience function to scrape and save WizzAir flights.

    Args:
        db: Database session
        origin: Origin airport IATA code (e.g., 'MUC')
        destination: Destination airport IATA code (e.g., 'CHI')
        departure_date: Departure date
        return_date: Return date (None for one-way)
        adult_count: Number of adults (default: 2)
        child_count: Number of children (default: 2)

    Returns:
        List of saved Flight objects

    Example:
        >>> from datetime import date
        >>> from app.database import get_async_session_context
        >>> async with get_async_session_context() as db:
        ...     flights = await scrape_wizzair_flights(
        ...         db, 'MUC', 'CHI', date(2025, 12, 20), date(2025, 12, 27)
        ...     )
        ...     print(f"Found {len(flights)} flights")
    """
    scraper = WizzAirScraper()

    # Search for flights
    flight_data = await scraper.search_flights(
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        return_date=return_date,
        adult_count=adult_count,
        child_count=child_count,
    )

    # Save to database
    saved_flights = await scraper.save_flights_to_db(
        db=db,
        flights=flight_data,
        adult_count=adult_count,
        child_count=child_count,
    )

    return saved_flights
