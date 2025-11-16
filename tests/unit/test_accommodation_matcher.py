"""
Unit tests for AccommodationMatcher module.
"""

from datetime import date, datetime
from unittest.mock import AsyncMock, Mock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accommodation import Accommodation
from app.models.airport import Airport
from app.models.flight import Flight
from app.models.school_holiday import SchoolHoliday
from app.models.trip_package import TripPackage
from app.orchestration.accommodation_matcher import AccommodationMatcher


class TestAccommodationMatcher:
    """Tests for AccommodationMatcher initialization and basic methods."""

    @pytest.fixture
    def matcher(self):
        """Create AccommodationMatcher instance."""
        return AccommodationMatcher()

    @pytest.fixture
    def mock_flight(self):
        """Create mock Flight object."""
        flight = Mock(spec=Flight)
        flight.id = 1
        flight.departure_date = date(2025, 12, 20)
        flight.return_date = date(2025, 12, 27)
        flight.true_cost = 559.27

        # Mock airport relationships
        origin = Mock(spec=Airport)
        origin.iata_code = "MUC"
        origin.city = "Munich"

        destination = Mock(spec=Airport)
        destination.iata_code = "LIS"
        destination.city = "Lisbon"

        flight.origin_airport = origin
        flight.destination_airport = destination

        return flight

    @pytest.fixture
    def mock_accommodation(self):
        """Create mock Accommodation object."""
        accommodation = Mock(spec=Accommodation)
        accommodation.id = 1
        accommodation.destination_city = "Lisbon"
        accommodation.name = "Family Apartment"
        accommodation.price_per_night = 80.0
        accommodation.family_friendly = True

        return accommodation

    @pytest.fixture
    def mock_school_holidays(self):
        """Create mock school holidays."""
        holidays = [
            Mock(
                spec=SchoolHoliday,
                name="Christmas Break 2025",
                start_date=date(2025, 12, 20),
                end_date=date(2026, 1, 5),
                holiday_type="major",
            ),
            Mock(
                spec=SchoolHoliday,
                name="Easter Break 2025",
                start_date=date(2025, 4, 14),
                end_date=date(2025, 4, 26),
                holiday_type="major",
            ),
        ]
        return holidays

    def test_init(self, matcher):
        """Test AccommodationMatcher initialization."""
        assert matcher.DAILY_FOOD_COST == 100.0
        assert matcher.DAILY_ACTIVITIES_COST == 50.0


class TestCalculateTripCost:
    """Tests for calculate_trip_cost method."""

    @pytest.fixture
    def matcher(self):
        """Create AccommodationMatcher instance."""
        return AccommodationMatcher()

    @pytest.fixture
    def mock_flight(self):
        """Create mock Flight with true cost."""
        flight = Mock(spec=Flight)
        flight.true_cost = 559.27
        return flight

    @pytest.fixture
    def mock_accommodation(self):
        """Create mock Accommodation."""
        accommodation = Mock(spec=Accommodation)
        accommodation.price_per_night = 80.0
        return accommodation

    def test_calculate_cost_7_nights(self, matcher, mock_flight, mock_accommodation):
        """Test cost calculation for 7-night trip."""
        cost = matcher.calculate_trip_cost(mock_flight, mock_accommodation, 7)

        assert cost["flight_cost"] == 559.27
        assert cost["accommodation_cost"] == 560.0  # 7 × €80
        assert cost["food_cost"] == 700.0  # 7 × €100
        assert cost["activities_cost"] == 350.0  # 7 × €50
        assert cost["total"] == 2169.27
        assert cost["per_person"] == 542.32  # Total ÷ 4

    def test_calculate_cost_3_nights(self, matcher, mock_flight, mock_accommodation):
        """Test cost calculation for 3-night trip."""
        cost = matcher.calculate_trip_cost(mock_flight, mock_accommodation, 3)

        assert cost["flight_cost"] == 559.27
        assert cost["accommodation_cost"] == 240.0  # 3 × €80
        assert cost["food_cost"] == 300.0  # 3 × €100
        assert cost["activities_cost"] == 150.0  # 3 × €50
        assert cost["total"] == 1249.27

    def test_calculate_cost_10_nights(self, matcher, mock_flight, mock_accommodation):
        """Test cost calculation for 10-night trip."""
        cost = matcher.calculate_trip_cost(mock_flight, mock_accommodation, 10)

        assert cost["flight_cost"] == 559.27
        assert cost["accommodation_cost"] == 800.0  # 10 × €80
        assert cost["food_cost"] == 1000.0  # 10 × €100
        assert cost["activities_cost"] == 500.0  # 10 × €50
        assert cost["total"] == 2859.27

    def test_calculate_cost_expensive_accommodation(self, matcher, mock_flight):
        """Test cost calculation with expensive accommodation."""
        expensive_accom = Mock(spec=Accommodation)
        expensive_accom.price_per_night = 200.0

        cost = matcher.calculate_trip_cost(mock_flight, expensive_accom, 7)

        assert cost["accommodation_cost"] == 1400.0  # 7 × €200
        assert cost["total"] == 3209.27

    def test_calculate_cost_budget_accommodation(self, matcher, mock_flight):
        """Test cost calculation with budget accommodation."""
        budget_accom = Mock(spec=Accommodation)
        budget_accom.price_per_night = 40.0

        cost = matcher.calculate_trip_cost(mock_flight, budget_accom, 7)

        assert cost["accommodation_cost"] == 280.0  # 7 × €40
        assert cost["total"] == 1889.27

    def test_calculate_cost_no_true_cost(self, matcher, mock_accommodation):
        """Test cost calculation when flight has no true_cost."""
        flight_no_cost = Mock(spec=Flight)
        flight_no_cost.true_cost = None

        cost = matcher.calculate_trip_cost(flight_no_cost, mock_accommodation, 7)

        assert cost["flight_cost"] == 0.0
        assert cost["total"] == 1610.0  # Without flight cost

    def test_calculate_cost_rounding(self, matcher):
        """Test that costs are properly rounded to 2 decimals."""
        flight = Mock(spec=Flight)
        flight.true_cost = 559.271234

        accommodation = Mock(spec=Accommodation)
        accommodation.price_per_night = 80.555

        cost = matcher.calculate_trip_cost(flight, accommodation, 3)

        # Check all values are rounded to 2 decimals
        assert cost["flight_cost"] == 559.27
        assert cost["accommodation_cost"] == 241.67  # 3 × 80.555 = 241.665
        assert cost["per_person"] == round(cost["total"] / 4, 2)


class TestCreateTripPackage:
    """Tests for create_trip_package method."""

    @pytest.fixture
    def matcher(self):
        """Create AccommodationMatcher instance."""
        return AccommodationMatcher()

    @pytest.fixture
    def mock_flight(self):
        """Create complete mock Flight."""
        flight = Mock(spec=Flight)
        flight.id = 42
        flight.departure_date = date(2025, 12, 20)
        flight.return_date = date(2025, 12, 27)

        destination = Mock(spec=Airport)
        destination.city = "Lisbon"
        flight.destination_airport = destination

        return flight

    @pytest.fixture
    def mock_accommodation(self):
        """Create mock Accommodation."""
        accommodation = Mock(spec=Accommodation)
        accommodation.id = 10
        return accommodation

    @pytest.fixture
    def cost_breakdown(self):
        """Create cost breakdown."""
        return {
            "flight_cost": 559.27,
            "accommodation_cost": 560.0,
            "food_cost": 700.0,
            "activities_cost": 350.0,
            "total": 2169.27,
            "per_person": 542.32,
        }

    def test_create_package_basic(
        self, matcher, mock_flight, mock_accommodation, cost_breakdown
    ):
        """Test basic trip package creation."""
        package = matcher.create_trip_package(
            mock_flight, mock_accommodation, cost_breakdown
        )

        assert isinstance(package, TripPackage)
        assert package.package_type == "family"
        assert package.flights_json == [42]
        assert package.accommodation_id == 10
        assert package.events_json == []
        assert package.total_price == 2169.27
        assert package.destination_city == "Lisbon"
        assert package.departure_date == date(2025, 12, 20)
        assert package.return_date == date(2025, 12, 27)
        assert package.num_nights == 7
        assert package.notified is False

    def test_create_package_3_nights(
        self, matcher, mock_accommodation, cost_breakdown
    ):
        """Test package creation for 3-night trip."""
        flight = Mock(spec=Flight)
        flight.id = 1
        flight.departure_date = date(2025, 4, 14)
        flight.return_date = date(2025, 4, 17)

        destination = Mock(spec=Airport)
        destination.city = "Prague"
        flight.destination_airport = destination

        package = matcher.create_trip_package(
            flight, mock_accommodation, cost_breakdown
        )

        assert package.num_nights == 3
        assert package.destination_city == "Prague"
        assert package.departure_date == date(2025, 4, 14)
        assert package.return_date == date(2025, 4, 17)

    def test_create_package_preserves_cost(
        self, matcher, mock_flight, mock_accommodation
    ):
        """Test that package preserves exact cost from breakdown."""
        cost = {
            "flight_cost": 123.45,
            "accommodation_cost": 678.90,
            "food_cost": 100.0,
            "activities_cost": 50.0,
            "total": 952.35,
            "per_person": 238.09,
        }

        package = matcher.create_trip_package(mock_flight, mock_accommodation, cost)

        assert package.total_price == 952.35


class TestMatchFlightsToAccommodations:
    """Tests for match_flights_to_accommodations method."""

    @pytest.fixture
    def matcher(self):
        """Create AccommodationMatcher instance."""
        return AccommodationMatcher()

    def test_match_single_flight_single_accommodation(self, matcher):
        """Test matching 1 flight with 1 accommodation."""
        flight = Mock(spec=Flight)
        accommodation = Mock(spec=Accommodation)

        pairs = matcher.match_flights_to_accommodations([flight], [accommodation])

        assert len(pairs) == 1
        assert pairs[0] == (flight, accommodation)

    def test_match_multiple_flights_single_accommodation(self, matcher):
        """Test matching multiple flights with 1 accommodation."""
        flights = [Mock(spec=Flight) for _ in range(3)]
        accommodation = Mock(spec=Accommodation)

        pairs = matcher.match_flights_to_accommodations(flights, [accommodation])

        assert len(pairs) == 3
        for i, (flight, accom) in enumerate(pairs):
            assert flight == flights[i]
            assert accom == accommodation

    def test_match_single_flight_multiple_accommodations(self, matcher):
        """Test matching 1 flight with multiple accommodations."""
        flight = Mock(spec=Flight)
        accommodations = [Mock(spec=Accommodation) for _ in range(4)]

        pairs = matcher.match_flights_to_accommodations([flight], accommodations)

        assert len(pairs) == 4
        for i, (f, accom) in enumerate(pairs):
            assert f == flight
            assert accom == accommodations[i]

    def test_match_cartesian_product(self, matcher):
        """Test that matching creates cartesian product."""
        flights = [Mock(spec=Flight) for _ in range(2)]
        accommodations = [Mock(spec=Accommodation) for _ in range(3)]

        pairs = matcher.match_flights_to_accommodations(flights, accommodations)

        # 2 flights × 3 accommodations = 6 combinations
        assert len(pairs) == 6

    def test_match_empty_flights(self, matcher):
        """Test matching with empty flights list."""
        accommodations = [Mock(spec=Accommodation) for _ in range(3)]

        pairs = matcher.match_flights_to_accommodations([], accommodations)

        assert len(pairs) == 0

    def test_match_empty_accommodations(self, matcher):
        """Test matching with empty accommodations list."""
        flights = [Mock(spec=Flight) for _ in range(3)]

        pairs = matcher.match_flights_to_accommodations(flights, [])

        assert len(pairs) == 0

    def test_match_both_empty(self, matcher):
        """Test matching with both lists empty."""
        pairs = matcher.match_flights_to_accommodations([], [])

        assert len(pairs) == 0


class TestIsDuringHoliday:
    """Tests for _is_during_holiday helper method."""

    @pytest.fixture
    def matcher(self):
        """Create AccommodationMatcher instance."""
        return AccommodationMatcher()

    @pytest.fixture
    def holidays(self):
        """Create mock school holidays."""
        return [
            Mock(
                spec=SchoolHoliday,
                start_date=date(2025, 12, 20),
                end_date=date(2026, 1, 5),
            ),
            Mock(
                spec=SchoolHoliday,
                start_date=date(2025, 4, 14),
                end_date=date(2025, 4, 26),
            ),
        ]

    def test_date_during_first_holiday(self, matcher, holidays):
        """Test date during first holiday period."""
        assert matcher._is_during_holiday(date(2025, 12, 25), holidays) is True

    def test_date_during_second_holiday(self, matcher, holidays):
        """Test date during second holiday period."""
        assert matcher._is_during_holiday(date(2025, 4, 20), holidays) is True

    def test_date_on_holiday_start(self, matcher, holidays):
        """Test date on holiday start date."""
        assert matcher._is_during_holiday(date(2025, 12, 20), holidays) is True

    def test_date_on_holiday_end(self, matcher, holidays):
        """Test date on holiday end date."""
        assert matcher._is_during_holiday(date(2026, 1, 5), holidays) is True

    def test_date_before_holidays(self, matcher, holidays):
        """Test date before all holidays."""
        assert matcher._is_during_holiday(date(2025, 3, 1), holidays) is False

    def test_date_after_holidays(self, matcher, holidays):
        """Test date after all holidays."""
        assert matcher._is_during_holiday(date(2026, 2, 1), holidays) is False

    def test_date_between_holidays(self, matcher, holidays):
        """Test date between two holiday periods."""
        assert matcher._is_during_holiday(date(2025, 5, 1), holidays) is False

    def test_empty_holidays_list(self, matcher):
        """Test with empty holidays list."""
        assert matcher._is_during_holiday(date(2025, 12, 25), []) is False


class TestFilterBySchoolHolidays:
    """Tests for filter_by_school_holidays method."""

    @pytest.fixture
    def matcher(self):
        """Create AccommodationMatcher instance."""
        return AccommodationMatcher()

    @pytest.fixture
    async def mock_db(self):
        """Create mock async database session."""
        db = AsyncMock(spec=AsyncSession)
        return db

    @pytest.fixture
    def holidays(self):
        """Create mock school holidays."""
        return [
            Mock(
                spec=SchoolHoliday,
                start_date=date(2025, 12, 20),
                end_date=date(2026, 1, 5),
            ),
        ]

    @pytest.fixture
    def packages(self):
        """Create mock trip packages."""
        # Package during holiday
        package1 = Mock(spec=TripPackage)
        package1.departure_date = date(2025, 12, 22)

        # Package not during holiday
        package2 = Mock(spec=TripPackage)
        package2.departure_date = date(2025, 11, 15)

        # Another package during holiday
        package3 = Mock(spec=TripPackage)
        package3.departure_date = date(2025, 12, 25)

        return [package1, package2, package3]

    @pytest.mark.asyncio
    async def test_filter_keeps_holiday_packages(
        self, matcher, mock_db, holidays, packages
    ):
        """Test that filtering keeps only packages during holidays."""
        # Mock database query to return holidays
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = holidays
        mock_db.execute.return_value = mock_result

        filtered = await matcher.filter_by_school_holidays(mock_db, packages)

        # Should keep packages 1 and 3 (during holidays)
        assert len(filtered) == 2
        assert packages[0] in filtered  # Dec 22
        assert packages[1] not in filtered  # Nov 15
        assert packages[2] in filtered  # Dec 25

    @pytest.mark.asyncio
    async def test_filter_empty_packages(self, matcher, mock_db, holidays):
        """Test filtering with empty packages list."""
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = holidays
        mock_db.execute.return_value = mock_result

        filtered = await matcher.filter_by_school_holidays(mock_db, [])

        assert len(filtered) == 0

    @pytest.mark.asyncio
    async def test_filter_no_holidays_returns_all(self, matcher, mock_db, packages):
        """Test that no holidays returns all packages with warning."""
        # Mock database query to return no holidays
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        with patch("app.orchestration.accommodation_matcher.logger") as mock_logger:
            filtered = await matcher.filter_by_school_holidays(mock_db, packages)

            # Should return all packages when no holidays exist
            assert len(filtered) == 3
            mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_filter_all_packages_during_holidays(
        self, matcher, mock_db, holidays
    ):
        """Test when all packages are during holidays."""
        packages = [
            Mock(spec=TripPackage, departure_date=date(2025, 12, 22)),
            Mock(spec=TripPackage, departure_date=date(2025, 12, 25)),
            Mock(spec=TripPackage, departure_date=date(2025, 12, 30)),
        ]

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = holidays
        mock_db.execute.return_value = mock_result

        filtered = await matcher.filter_by_school_holidays(mock_db, packages)

        assert len(filtered) == 3

    @pytest.mark.asyncio
    async def test_filter_no_packages_during_holidays(
        self, matcher, mock_db, holidays
    ):
        """Test when no packages are during holidays."""
        packages = [
            Mock(spec=TripPackage, departure_date=date(2025, 11, 15)),
            Mock(spec=TripPackage, departure_date=date(2025, 10, 10)),
        ]

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = holidays
        mock_db.execute.return_value = mock_result

        filtered = await matcher.filter_by_school_holidays(mock_db, packages)

        assert len(filtered) == 0


class TestSavePackages:
    """Tests for save_packages method."""

    @pytest.fixture
    def matcher(self):
        """Create AccommodationMatcher instance."""
        return AccommodationMatcher()

    @pytest.fixture
    async def mock_db(self):
        """Create mock async database session."""
        db = AsyncMock(spec=AsyncSession)
        return db

    @pytest.mark.asyncio
    async def test_save_empty_packages(self, matcher, mock_db):
        """Test saving empty packages list."""
        stats = await matcher.save_packages(mock_db, [])

        assert stats["total"] == 0
        assert stats["inserted"] == 0
        assert stats["skipped"] == 0

    @pytest.mark.asyncio
    async def test_save_new_packages(self, matcher, mock_db):
        """Test saving new packages without duplicates."""
        packages = [
            Mock(
                spec=TripPackage,
                departure_date=date(2025, 12, 20),
                return_date=date(2025, 12, 27),
                accommodation_id=1,
                flights_json=[1],
            ),
            Mock(
                spec=TripPackage,
                departure_date=date(2025, 12, 21),
                return_date=date(2025, 12, 28),
                accommodation_id=2,
                flights_json=[2],
            ),
        ]

        # Mock database to return no existing packages
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        stats = await matcher.save_packages(mock_db, packages)

        assert stats["total"] == 2
        assert stats["inserted"] == 2
        assert stats["skipped"] == 0
        assert mock_db.add.call_count == 2
        assert mock_db.commit.call_count == 1

    @pytest.mark.asyncio
    async def test_save_with_duplicates(self, matcher, mock_db):
        """Test saving packages with some duplicates."""
        packages = [
            Mock(
                spec=TripPackage,
                departure_date=date(2025, 12, 20),
                return_date=date(2025, 12, 27),
                accommodation_id=1,
                flights_json=[1],
            ),
            Mock(
                spec=TripPackage,
                departure_date=date(2025, 12, 21),
                return_date=date(2025, 12, 28),
                accommodation_id=2,
                flights_json=[2],
            ),
        ]

        # First package exists, second doesn't
        existing_package = Mock(spec=TripPackage, flights_json=[1])

        mock_results = [existing_package, None]

        async def mock_execute(stmt):
            result = AsyncMock()
            result.scalar_one_or_none.return_value = mock_results.pop(0)
            return result

        mock_db.execute.side_effect = mock_execute

        stats = await matcher.save_packages(mock_db, packages)

        assert stats["total"] == 2
        assert stats["inserted"] == 1
        assert stats["skipped"] == 1
