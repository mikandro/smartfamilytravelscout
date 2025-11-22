"""
Kiwi.com API integration for flight searching.

This module provides a comprehensive client for the Kiwi.com Tequila API,
handling flight searches, rate limiting, error handling, and database integration.

API Documentation: https://tequila.kiwi.com/portal/docs/tequila_api
Base URL: https://api.tequila.kiwi.com
Free tier: 100 requests/month
"""

import asyncio
import logging
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional
from urllib.parse import urlencode

import aiohttp
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_async_session_context
from app.exceptions import APIKeyMissingError
from app.models.airport import Airport
from app.models.flight import Flight
from app.utils.rate_limiter import (
    RedisRateLimiter,
    RateLimitExceededError,
    get_kiwi_rate_limiter,
)
from app.utils.retry import api_retry

logger = logging.getLogger(__name__)


class KiwiAPIError(Exception):
    """Base exception for Kiwi API errors."""

    pass


class KiwiClient:
    """
    Client for Kiwi.com Tequila API flight search.

    Handles flight searches from German airports to European destinations,
    with comprehensive rate limiting, error handling, and database integration.

    Examples:
        >>> client = KiwiClient(api_key=os.getenv('KIWI_API_KEY'))
        >>> flights = await client.search_flights('MUC', 'LIS', date(2025, 12, 20), date(2025, 12, 27))
        >>> await client.save_to_database(flights)
        >>> print(f"Found {len(flights)} flights")
    """

    BASE_URL = "https://api.tequila.kiwi.com"
    SEARCH_ENDPOINT = "/v2/search"

    def __init__(
        self,
        api_key: Optional[str] = None,
        rate_limiter: Optional[RedisRateLimiter] = None,
        timeout: int = 30,
    ):
        """
        Initialize Kiwi API client.

        Args:
            api_key: Kiwi API key (defaults to settings.kiwi_api_key)
            rate_limiter: Custom rate limiter instance (optional)
            timeout: Request timeout in seconds (default: 30)
        """
        self.api_key = api_key or settings.kiwi_api_key
        if not self.api_key:
            raise APIKeyMissingError(
                service="Kiwi.com API",
                env_var="KIWI_API_KEY",
                optional=True,
                fallback_info=(
                    "Get a free API key (100 requests/month) at: https://tequila.kiwi.com/portal/login\n\n"
                    "You can also use the default scrapers instead:\n"
                    "  - Skyscanner (playwright-based, no API key)\n"
                    "  - Ryanair (playwright-based, no API key)\n"
                    "  - WizzAir (API-based, no API key)"
                )
            )

        self.rate_limiter = rate_limiter or get_kiwi_rate_limiter()
        self.timeout = timeout
        self.logger = logging.getLogger(f"{__name__}.KiwiClient")

    @api_retry(max_attempts=3, min_wait_seconds=2, max_wait_seconds=10)
    async def _make_request(
        self,
        params: Dict[str, any],
    ) -> Dict:
        """
        Make HTTP request to Kiwi API with automatic retry logic.

        Args:
            params: Query parameters for the API request

        Returns:
            Dict: Parsed JSON response

        Raises:
            RateLimitExceededError: If rate limit is exceeded
            KiwiAPIError: If API returns an error
            aiohttp.ClientError: If network request fails after retries
        """
        # Check rate limit
        if not self.rate_limiter.is_allowed():
            remaining = self.rate_limiter.get_remaining()
            raise RateLimitExceededError(
                f"Monthly rate limit exceeded. {remaining} calls remaining this month."
            )

        url = f"{self.BASE_URL}{self.SEARCH_ENDPOINT}"
        headers = {"apikey": self.api_key}

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            ) as response:
                # Record successful API call
                self.rate_limiter.record_request()

                # Log request details
                query_string = urlencode(params)
                self.logger.info(f"API request: {url}?{query_string}")

                if response.status == 200:
                    data = await response.json()
                    self.logger.info(
                        f"API response: {len(data.get('data', []))} flights found"
                    )
                    return data
                elif response.status == 400:
                    error_msg = await response.text()
                    self.logger.error(f"Bad request (400): {error_msg}")
                    raise KiwiAPIError(f"Bad request: {error_msg}")
                elif response.status == 401:
                    raise KiwiAPIError("Unauthorized: Invalid API key")
                elif response.status == 429:
                    raise RateLimitExceededError("API rate limit exceeded by server")
                else:
                    error_msg = await response.text()
                    self.logger.warning(
                        f"API error (status {response.status}): {error_msg}"
                    )
                    raise KiwiAPIError(
                        f"API request failed with status {response.status}: {error_msg}"
                    )

    async def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        return_date: date,
        adults: int = 2,
        children: int = 2,
        max_stopovers: int = 0,
        currency: str = "EUR",
    ) -> List[Dict]:
        """
        Search for flights between specific airports/cities.

        Args:
            origin: Origin airport IATA code (e.g., 'MUC')
            destination: Destination airport IATA code or city (e.g., 'LIS' or 'London')
            departure_date: Departure date
            return_date: Return date
            adults: Number of adults (default: 2)
            children: Number of children (default: 2)
            max_stopovers: Maximum number of stopovers (default: 0 for direct flights)
            currency: Price currency (default: 'EUR')

        Returns:
            List[Dict]: List of standardized flight offers

        Examples:
            >>> flights = await client.search_flights('MUC', 'LIS', date(2025, 12, 20), date(2025, 12, 27))
            >>> print(f"Found {len(flights)} flights from Munich to Lisbon")
        """
        params = {
            "fly_from": origin,
            "fly_to": destination,
            "date_from": departure_date.strftime("%d/%m/%Y"),
            "date_to": departure_date.strftime("%d/%m/%Y"),
            "return_from": return_date.strftime("%d/%m/%Y"),
            "return_to": return_date.strftime("%d/%m/%Y"),
            "adults": adults,
            "children": children,
            "curr": currency,
            "max_stopovers": max_stopovers,
            "flight_type": "round",
            "one_for_city": 1,  # Return cheapest flight per city
            "limit": 50,  # Maximum results
        }

        self.logger.info(
            f"Searching flights: {origin} → {destination}, "
            f"{departure_date} to {return_date}, "
            f"{adults} adults + {children} children"
        )

        try:
            response = await self._make_request(params)
            flights = self.parse_response(response)
            self.logger.info(f"Found {len(flights)} flights")
            return flights
        except Exception as e:
            self.logger.error(f"Flight search failed: {e}", exc_info=True)
            return []

    async def search_anywhere(
        self,
        origin: str,
        departure_date: date,
        return_date: date,
        adults: int = 2,
        children: int = 2,
        max_stopovers: int = 0,
        currency: str = "EUR",
        limit: int = 50,
    ) -> List[Dict]:
        """
        Search all destinations from origin (flexible destination search).

        Args:
            origin: Origin airport IATA code (e.g., 'MUC')
            departure_date: Departure date
            return_date: Return date
            adults: Number of adults (default: 2)
            children: Number of children (default: 2)
            max_stopovers: Maximum number of stopovers (default: 0 for direct flights)
            currency: Price currency (default: 'EUR')
            limit: Maximum number of results (default: 50)

        Returns:
            List[Dict]: List of standardized flight offers to various destinations

        Examples:
            >>> flights = await client.search_anywhere('MUC', date(2025, 12, 20), date(2025, 12, 27))
            >>> print(f"Found {len(flights)} destinations from Munich")
        """
        params = {
            "fly_from": origin,
            "date_from": departure_date.strftime("%d/%m/%Y"),
            "date_to": departure_date.strftime("%d/%m/%Y"),
            "return_from": return_date.strftime("%d/%m/%Y"),
            "return_to": return_date.strftime("%d/%m/%Y"),
            "adults": adults,
            "children": children,
            "curr": currency,
            "max_stopovers": max_stopovers,
            "flight_type": "round",
            "one_for_city": 1,  # Return cheapest flight per city
            "limit": limit,
        }

        self.logger.info(
            f"Searching flights anywhere from {origin}, "
            f"{departure_date} to {return_date}, "
            f"{adults} adults + {children} children"
        )

        try:
            response = await self._make_request(params)
            flights = self.parse_response(response)
            self.logger.info(f"Found {len(flights)} destinations")
            return flights
        except Exception as e:
            self.logger.error(f"Anywhere search failed: {e}", exc_info=True)
            return []

    def parse_response(self, raw_data: Dict) -> List[Dict]:
        """
        Parse Kiwi API response to standardized FlightOffer format.

        Args:
            raw_data: Raw JSON response from Kiwi API

        Returns:
            List[Dict]: List of standardized flight offers

        Standardized format:
            {
                'origin_airport': 'MUC',
                'destination_airport': 'LIS',
                'origin_city': 'Munich',
                'destination_city': 'Lisbon',
                'airline': 'Ryanair',
                'departure_date': '2025-12-20',
                'departure_time': '14:30',
                'return_date': '2025-12-27',
                'return_time': '18:45',
                'price_per_person': 89.99,
                'total_price': 359.96,
                'direct_flight': True,
                'booking_class': 'Economy',
                'source': 'kiwi',
                'booking_url': 'https://...',
                'scraped_at': '2025-11-15T10:30:00'
            }
        """
        flights = []

        if not raw_data or "data" not in raw_data:
            self.logger.warning("No flight data in API response")
            return flights

        for item in raw_data.get("data", []):
            try:
                # Extract route information
                route = item.get("route", [])
                if not route or len(route) < 2:
                    self.logger.warning("Invalid route data, skipping")
                    continue

                # First leg (outbound)
                outbound = route[0]
                # Last leg (return)
                inbound = route[-1]

                # Parse departure and return times
                departure_dt = datetime.fromtimestamp(outbound.get("dTimeUTC"))
                return_dt = datetime.fromtimestamp(inbound.get("aTimeUTC"))

                # Extract airline (use first leg's airline)
                airline = outbound.get("airline", "Unknown")

                # Calculate price per person (total / 4 people)
                total_price = float(item.get("price", 0))
                price_per_person = total_price / 4

                # Check if direct flight
                direct_flight = len(route) == 2  # Outbound + return only

                # Build booking URL
                booking_token = item.get("booking_token", "")
                deep_link = item.get("deep_link", "")
                booking_url = deep_link if deep_link else f"https://www.kiwi.com/booking?token={booking_token}"

                flight_offer = {
                    "origin_airport": outbound.get("flyFrom", ""),
                    "destination_airport": outbound.get("flyTo", ""),
                    "origin_city": outbound.get("cityFrom", ""),
                    "destination_city": outbound.get("cityTo", ""),
                    "airline": airline,
                    "departure_date": departure_dt.strftime("%Y-%m-%d"),
                    "departure_time": departure_dt.strftime("%H:%M"),
                    "return_date": return_dt.strftime("%Y-%m-%d"),
                    "return_time": return_dt.strftime("%H:%M"),
                    "price_per_person": round(price_per_person, 2),
                    "total_price": round(total_price, 2),
                    "direct_flight": direct_flight,
                    "booking_class": "Economy",  # Kiwi API doesn't specify class
                    "source": "kiwi",
                    "booking_url": booking_url,
                    "scraped_at": datetime.now().isoformat(),
                }

                flights.append(flight_offer)

            except Exception as e:
                self.logger.warning(f"Error parsing flight item: {e}", exc_info=True)
                continue

        return flights

    async def _get_or_create_airport(
        self,
        db: AsyncSession,
        iata_code: str,
        city: str = "",
    ) -> Airport:
        """
        Get airport from database by IATA code, or create if doesn't exist.

        Args:
            db: Database session
            iata_code: Airport IATA code
            city: City name (optional, for creation)

        Returns:
            Airport: Airport model instance
        """
        # Try to find existing airport
        result = await db.execute(
            select(Airport).where(Airport.iata_code == iata_code.upper())
        )
        airport = result.scalar_one_or_none()

        if airport:
            return airport

        # Create new airport with minimal info
        self.logger.info(f"Creating new airport: {iata_code} ({city})")
        airport = Airport(
            iata_code=iata_code.upper(),
            name=f"{city} Airport" if city else f"{iata_code} Airport",
            city=city or iata_code,
            distance_from_home=0,  # Unknown, will be updated later
            driving_time=0,  # Unknown, will be updated later
        )
        db.add(airport)
        await db.flush()  # Get the ID without committing
        return airport

    async def _check_duplicate_flight(
        self,
        db: AsyncSession,
        origin_airport_id: int,
        destination_airport_id: int,
        airline: str,
        departure_date: date,
        departure_time: time,
    ) -> Optional[Flight]:
        """
        Check if a similar flight already exists in the database.

        A duplicate is defined as:
        - Same route (origin + destination)
        - Same airline
        - Same date
        - Similar time (±2 hours)

        Args:
            db: Database session
            origin_airport_id: Origin airport ID
            destination_airport_id: Destination airport ID
            airline: Airline name
            departure_date: Departure date
            departure_time: Departure time

        Returns:
            Optional[Flight]: Existing flight if found, None otherwise
        """
        # Calculate time window (±2 hours)
        time_lower = (
            datetime.combine(departure_date, departure_time) - timedelta(hours=2)
        ).time()
        time_upper = (
            datetime.combine(departure_date, departure_time) + timedelta(hours=2)
        ).time()

        result = await db.execute(
            select(Flight).where(
                and_(
                    Flight.origin_airport_id == origin_airport_id,
                    Flight.destination_airport_id == destination_airport_id,
                    Flight.airline == airline,
                    Flight.departure_date == departure_date,
                    Flight.departure_time >= time_lower,
                    Flight.departure_time <= time_upper,
                )
            )
        )

        return result.scalar_one_or_none()

    async def save_to_database(
        self,
        flights: List[Dict],
        update_if_cheaper: bool = True,
    ) -> Dict[str, int]:
        """
        Save flights to database with duplicate checking.

        Args:
            flights: List of flight offers (from parse_response)
            update_if_cheaper: Update existing flight if new price is cheaper (default: True)

        Returns:
            Dict[str, int]: Statistics about the operation
                {
                    'total': Total flights processed,
                    'inserted': New flights inserted,
                    'updated': Existing flights updated with cheaper prices,
                    'skipped': Flights skipped (duplicates with same/higher price)
                }

        Examples:
            >>> flights = await client.search_flights('MUC', 'LIS', date(2025, 12, 20), date(2025, 12, 27))
            >>> stats = await client.save_to_database(flights)
            >>> print(f"Inserted: {stats['inserted']}, Updated: {stats['updated']}")
        """
        stats = {
            "total": len(flights),
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
        }

        if not flights:
            self.logger.info("No flights to save")
            return stats

        async with get_async_session_context() as db:
            for flight_data in flights:
                try:
                    # Get or create airports
                    origin_airport = await self._get_or_create_airport(
                        db,
                        flight_data["origin_airport"],
                        flight_data["origin_city"],
                    )
                    destination_airport = await self._get_or_create_airport(
                        db,
                        flight_data["destination_airport"],
                        flight_data["destination_city"],
                    )

                    # Parse dates and times
                    departure_date_obj = datetime.strptime(
                        flight_data["departure_date"], "%Y-%m-%d"
                    ).date()
                    departure_time_obj = datetime.strptime(
                        flight_data["departure_time"], "%H:%M"
                    ).time()
                    return_date_obj = datetime.strptime(
                        flight_data["return_date"], "%Y-%m-%d"
                    ).date()
                    return_time_obj = datetime.strptime(
                        flight_data["return_time"], "%H:%M"
                    ).time()

                    # Check for duplicate
                    existing_flight = await self._check_duplicate_flight(
                        db,
                        origin_airport.id,
                        destination_airport.id,
                        flight_data["airline"],
                        departure_date_obj,
                        departure_time_obj,
                    )

                    if existing_flight:
                        # Update if new price is cheaper
                        if (
                            update_if_cheaper
                            and flight_data["price_per_person"] < existing_flight.price_per_person
                        ):
                            self.logger.info(
                                f"Updating flight {existing_flight.id}: "
                                f"€{existing_flight.price_per_person} → €{flight_data['price_per_person']}"
                            )
                            existing_flight.price_per_person = flight_data["price_per_person"]
                            existing_flight.total_price = flight_data["total_price"]
                            existing_flight.booking_url = flight_data["booking_url"]
                            existing_flight.scraped_at = datetime.now()
                            stats["updated"] += 1
                        else:
                            stats["skipped"] += 1
                    else:
                        # Insert new flight
                        new_flight = Flight(
                            origin_airport_id=origin_airport.id,
                            destination_airport_id=destination_airport.id,
                            airline=flight_data["airline"],
                            departure_date=departure_date_obj,
                            departure_time=departure_time_obj,
                            return_date=return_date_obj,
                            return_time=return_time_obj,
                            price_per_person=flight_data["price_per_person"],
                            total_price=flight_data["total_price"],
                            booking_class=flight_data["booking_class"],
                            direct_flight=flight_data["direct_flight"],
                            source=flight_data["source"],
                            booking_url=flight_data["booking_url"],
                            scraped_at=datetime.now(),
                        )
                        db.add(new_flight)
                        stats["inserted"] += 1
                        self.logger.info(
                            f"Inserting new flight: {flight_data['origin_airport']} → "
                            f"{flight_data['destination_airport']} "
                            f"(€{flight_data['price_per_person']}/person)"
                        )

                except Exception as e:
                    self.logger.error(f"Error saving flight: {e}", exc_info=True)
                    continue

            await db.commit()

        self.logger.info(
            f"Database save complete: {stats['inserted']} inserted, "
            f"{stats['updated']} updated, {stats['skipped']} skipped"
        )

        return stats
