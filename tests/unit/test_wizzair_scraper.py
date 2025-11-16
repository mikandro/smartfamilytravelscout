"""
Unit tests for WizzAir scraper.

Tests the WizzAir API scraper with mocked HTTP responses.
"""

import json
from datetime import date, datetime, time
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.airport import Airport
from app.models.flight import Flight
from app.scrapers.wizzair_scraper import (
    WizzAirAPIError,
    WizzAirRateLimitError,
    WizzAirScraper,
    scrape_wizzair_flights,
)


@pytest.fixture
def scraper() -> WizzAirScraper:
    """Create a WizzAir scraper instance."""
    return WizzAirScraper(timeout=30)


@pytest.fixture
def sample_api_response_roundtrip() -> Dict[str, Any]:
    """Sample WizzAir API response for round-trip flight."""
    return {
        "outboundFlights": [
            {
                "price": {"amount": 45.99, "currencyCode": "EUR"},
                "departureDates": "2025-12-20T14:30:00",
                "arrivalDates": "2025-12-20T17:45:00",
                "flightNumber": "W6 1234",
            },
            {
                "price": {"amount": 89.99, "currencyCode": "EUR"},
                "departureDates": "2025-12-20T08:00:00",
                "arrivalDates": "2025-12-20T11:15:00",
                "flightNumber": "W6 5678",
            },
        ],
        "returnFlights": [
            {
                "price": {"amount": 52.50, "currencyCode": "EUR"},
                "departureDates": "2025-12-27T18:00:00",
                "arrivalDates": "2025-12-27T21:15:00",
                "flightNumber": "W6 4321",
            }
        ],
    }


@pytest.fixture
def sample_api_response_oneway() -> Dict[str, Any]:
    """Sample WizzAir API response for one-way flight."""
    return {
        "outboundFlights": [
            {
                "price": {"amount": 45.99, "currencyCode": "EUR"},
                "departureDates": "2025-12-20T14:30:00",
                "arrivalDates": "2025-12-20T17:45:00",
                "flightNumber": "W6 1234",
            }
        ],
        "returnFlights": [],
    }


@pytest.fixture
def sample_api_response_empty() -> Dict[str, Any]:
    """Sample WizzAir API response with no flights."""
    return {"outboundFlights": [], "returnFlights": []}


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock database session."""
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def mock_airports() -> Dict[str, Airport]:
    """Create mock airport objects."""
    return {
        "MUC": Airport(
            id=1,
            iata_code="MUC",
            name="Munich Airport",
            city="Munich",
            distance_from_home=50,
            driving_time=45,
            parking_cost_per_day=15.0,
        ),
        "CHI": Airport(
            id=2,
            iata_code="CHI",
            name="Chisinau International Airport",
            city="Chisinau",
            distance_from_home=2000,
            driving_time=0,
            parking_cost_per_day=0.0,
        ),
    }


class TestWizzAirScraper:
    """Test suite for WizzAirScraper class."""

    def test_init(self, scraper: WizzAirScraper) -> None:
        """Test scraper initialization."""
        assert scraper.timeout == 30
        assert "User-Agent" in scraper.headers
        assert "Content-Type" in scraper.headers
        assert scraper.headers["Content-Type"] == "application/json"

    def test_build_payload_roundtrip(self, scraper: WizzAirScraper) -> None:
        """Test building API payload for round-trip flight."""
        payload = scraper._build_payload(
            origin="MUC",
            destination="CHI",
            departure_date=date(2025, 12, 20),
            return_date=date(2025, 12, 27),
            adult_count=2,
            child_count=2,
        )

        assert payload["adultCount"] == 2
        assert payload["childCount"] == 2
        assert payload["infantCount"] == 0
        assert len(payload["flightList"]) == 2

        # Check outbound flight
        outbound = payload["flightList"][0]
        assert outbound["departureStation"] == "MUC"
        assert outbound["arrivalStation"] == "CHI"
        assert outbound["from"] == "2025-12-20"
        assert outbound["to"] == "2025-12-20"

        # Check return flight
        return_flight = payload["flightList"][1]
        assert return_flight["departureStation"] == "CHI"
        assert return_flight["arrivalStation"] == "MUC"
        assert return_flight["from"] == "2025-12-27"
        assert return_flight["to"] == "2025-12-27"

    def test_build_payload_oneway(self, scraper: WizzAirScraper) -> None:
        """Test building API payload for one-way flight."""
        payload = scraper._build_payload(
            origin="MUC",
            destination="CHI",
            departure_date=date(2025, 12, 20),
            return_date=None,
            adult_count=2,
            child_count=2,
        )

        assert len(payload["flightList"]) == 1
        assert payload["flightList"][0]["departureStation"] == "MUC"
        assert payload["flightList"][0]["arrivalStation"] == "CHI"

    def test_parse_single_flight(self, scraper: WizzAirScraper) -> None:
        """Test parsing a single flight from API response."""
        flight_data = {
            "price": {"amount": 45.99, "currencyCode": "EUR"},
            "departureDates": "2025-12-20T14:30:00",
            "arrivalDates": "2025-12-20T17:45:00",
            "flightNumber": "W6 1234",
        }

        result = scraper._parse_single_flight(flight_data, "MUC", "CHI", False)

        assert result is not None
        assert result["origin"] == "MUC"
        assert result["destination"] == "CHI"
        assert result["price"] == 45.99
        assert result["currency"] == "EUR"
        assert result["flight_number"] == "W6 1234"
        assert result["departure_date"] == date(2025, 12, 20)
        assert result["departure_time"] == time(14, 30, 0)
        assert result["arrival_date"] == date(2025, 12, 20)
        assert result["arrival_time"] == time(17, 45, 0)
        assert result["is_return"] is False

    def test_parse_single_flight_invalid_data(self, scraper: WizzAirScraper) -> None:
        """Test parsing flight with invalid data returns None."""
        flight_data = {
            "price": {"amount": 45.99},
            # Missing dates and flight number
        }

        result = scraper._parse_single_flight(flight_data, "MUC", "CHI", False)
        assert result is None

    def test_combine_flights(
        self, scraper: WizzAirScraper, sample_api_response_roundtrip: Dict[str, Any]
    ) -> None:
        """Test combining outbound and return flights."""
        outbound = sample_api_response_roundtrip["outboundFlights"][0]
        return_flight = sample_api_response_roundtrip["returnFlights"][0]

        result = scraper._combine_flights(outbound, return_flight, "MUC", "CHI")

        assert result is not None
        assert result["origin"] == "MUC"
        assert result["destination"] == "CHI"
        assert result["departure_date"] == date(2025, 12, 20)
        assert result["return_date"] == date(2025, 12, 27)
        assert result["price"] == 45.99 + 52.50  # Combined price
        assert result["currency"] == "EUR"
        assert "outbound_flight_number" in result
        assert "return_flight_number" in result

    def test_parse_api_response_roundtrip(
        self, scraper: WizzAirScraper, sample_api_response_roundtrip: Dict[str, Any]
    ) -> None:
        """Test parsing round-trip API response."""
        flights = scraper._parse_api_response(
            sample_api_response_roundtrip,
            "MUC",
            "CHI",
            date(2025, 12, 20),
            date(2025, 12, 27),
        )

        # Should have 2 outbound * 1 return = 2 combinations
        assert len(flights) == 2

        # Check first combination
        flight = flights[0]
        assert flight["origin"] == "MUC"
        assert flight["destination"] == "CHI"
        assert flight["departure_date"] == date(2025, 12, 20)
        assert flight["return_date"] == date(2025, 12, 27)
        assert flight["price"] == 45.99 + 52.50

    def test_parse_api_response_oneway(
        self, scraper: WizzAirScraper, sample_api_response_oneway: Dict[str, Any]
    ) -> None:
        """Test parsing one-way API response."""
        flights = scraper._parse_api_response(
            sample_api_response_oneway, "MUC", "CHI", date(2025, 12, 20), None
        )

        assert len(flights) == 1
        flight = flights[0]
        assert flight["origin"] == "MUC"
        assert flight["destination"] == "CHI"
        assert "return_date" not in flight or flight.get("return_date") is None

    def test_parse_api_response_empty(
        self, scraper: WizzAirScraper, sample_api_response_empty: Dict[str, Any]
    ) -> None:
        """Test parsing empty API response."""
        flights = scraper._parse_api_response(
            sample_api_response_empty, "MUC", "CHI", date(2025, 12, 20), None
        )

        assert len(flights) == 0

    @pytest.mark.asyncio
    async def test_search_flights_success(
        self, scraper: WizzAirScraper, sample_api_response_roundtrip: Dict[str, Any]
    ) -> None:
        """Test successful flight search."""
        # Mock httpx response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_api_response_roundtrip
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.post", return_value=mock_response):
            flights = await scraper.search_flights(
                origin="MUC",
                destination="CHI",
                departure_date=date(2025, 12, 20),
                return_date=date(2025, 12, 27),
            )

            assert len(flights) == 2
            assert all("origin" in f for f in flights)
            assert all("destination" in f for f in flights)

    @pytest.mark.asyncio
    async def test_search_flights_rate_limit(self, scraper: WizzAirScraper) -> None:
        """Test handling of rate limit error."""
        # Mock httpx response with 429 status
        mock_response = MagicMock()
        mock_response.status_code = 429

        with patch("httpx.AsyncClient.post", return_value=mock_response):
            with pytest.raises(WizzAirRateLimitError):
                await scraper.search_flights(
                    origin="MUC",
                    destination="CHI",
                    departure_date=date(2025, 12, 20),
                    return_date=date(2025, 12, 27),
                )

    @pytest.mark.asyncio
    async def test_search_flights_http_error(self, scraper: WizzAirScraper) -> None:
        """Test handling of HTTP error."""
        # Mock httpx to raise HTTPStatusError
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error", request=MagicMock(), response=mock_response
        )

        with patch("httpx.AsyncClient.post", return_value=mock_response):
            with pytest.raises(WizzAirAPIError):
                await scraper.search_flights(
                    origin="MUC",
                    destination="CHI",
                    departure_date=date(2025, 12, 20),
                    return_date=date(2025, 12, 27),
                )

    @pytest.mark.asyncio
    async def test_search_flights_network_error(self, scraper: WizzAirScraper) -> None:
        """Test handling of network error."""
        with patch(
            "httpx.AsyncClient.post",
            side_effect=httpx.RequestError("Network error", request=MagicMock()),
        ):
            with pytest.raises(httpx.RequestError):
                await scraper.search_flights(
                    origin="MUC",
                    destination="CHI",
                    departure_date=date(2025, 12, 20),
                    return_date=date(2025, 12, 27),
                )

    @pytest.mark.asyncio
    async def test_get_airport_by_iata(
        self, scraper: WizzAirScraper, mock_db_session: AsyncMock, mock_airports: Dict[str, Airport]
    ) -> None:
        """Test getting airport by IATA code."""
        # Mock database query result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_airports["MUC"]
        mock_db_session.execute.return_value = mock_result

        airport = await scraper._get_airport_by_iata(mock_db_session, "MUC")

        assert airport is not None
        assert airport.iata_code == "MUC"
        assert airport.name == "Munich Airport"

    @pytest.mark.asyncio
    async def test_get_airport_by_iata_not_found(
        self, scraper: WizzAirScraper, mock_db_session: AsyncMock
    ) -> None:
        """Test getting non-existent airport."""
        # Mock database query result (not found)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        airport = await scraper._get_airport_by_iata(mock_db_session, "XXX")

        assert airport is None

    @pytest.mark.asyncio
    async def test_save_flights_to_db(
        self,
        scraper: WizzAirScraper,
        mock_db_session: AsyncMock,
        mock_airports: Dict[str, Airport],
    ) -> None:
        """Test saving flights to database."""
        # Mock airport queries
        async def mock_get_airport(db: AsyncSession, iata: str) -> Airport:
            return mock_airports.get(iata.upper())

        with patch.object(scraper, "_get_airport_by_iata", side_effect=mock_get_airport):
            flight_data = [
                {
                    "origin": "MUC",
                    "destination": "CHI",
                    "departure_date": date(2025, 12, 20),
                    "departure_time": time(14, 30),
                    "return_date": date(2025, 12, 27),
                    "return_time": time(18, 0),
                    "price": 98.49,
                    "currency": "EUR",
                }
            ]

            saved_flights = await scraper.save_flights_to_db(
                db=mock_db_session, flights=flight_data, adult_count=2, child_count=2
            )

            assert len(saved_flights) == 1
            assert mock_db_session.add.called
            assert mock_db_session.commit.called

            # Check flight properties
            flight = saved_flights[0]
            assert flight.airline == "WizzAir"
            assert flight.source == "wizzair"
            assert flight.direct_flight is True
            assert flight.price_per_person == 98.49
            assert flight.total_price == 98.49 * 4  # 2 adults + 2 children

    @pytest.mark.asyncio
    async def test_save_flights_airport_not_found(
        self, scraper: WizzAirScraper, mock_db_session: AsyncMock
    ) -> None:
        """Test saving flights when airport not found in database."""
        # Mock airport not found
        with patch.object(scraper, "_get_airport_by_iata", return_value=None):
            flight_data = [
                {
                    "origin": "XXX",
                    "destination": "YYY",
                    "departure_date": date(2025, 12, 20),
                    "price": 100.0,
                    "currency": "EUR",
                }
            ]

            saved_flights = await scraper.save_flights_to_db(
                db=mock_db_session, flights=flight_data
            )

            # Should skip flights with unknown airports
            assert len(saved_flights) == 0
            assert not mock_db_session.add.called

    @pytest.mark.asyncio
    async def test_scrape_wizzair_flights_convenience_function(
        self, mock_db_session: AsyncMock, sample_api_response_roundtrip: Dict[str, Any]
    ) -> None:
        """Test the convenience function for scraping flights."""
        # Mock the scraper methods
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_api_response_roundtrip
        mock_response.raise_for_status = MagicMock()

        mock_airport = Airport(
            id=1,
            iata_code="MUC",
            name="Munich",
            city="Munich",
            distance_from_home=50,
            driving_time=45,
        )

        with patch("httpx.AsyncClient.post", return_value=mock_response), patch(
            "app.scrapers.wizzair_scraper.WizzAirScraper._get_airport_by_iata",
            return_value=mock_airport,
        ):
            flights = await scrape_wizzair_flights(
                db=mock_db_session,
                origin="MUC",
                destination="CHI",
                departure_date=date(2025, 12, 20),
                return_date=date(2025, 12, 27),
            )

            assert mock_db_session.commit.called
