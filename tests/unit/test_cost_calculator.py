"""
Unit tests for TrueCostCalculator module.
"""

from datetime import date
from unittest.mock import Mock, MagicMock

import pytest

from app.models.airport import Airport
from app.models.flight import Flight
from app.utils.cost_calculator import TrueCostCalculator


class TestTrueCostCalculator:
    """Tests for TrueCostCalculator initialization."""

    def test_init_with_sync_session(self):
        """Test initialization with sync session."""
        mock_session = Mock()
        mock_session.__class__.__name__ = "Session"

        calc = TrueCostCalculator(mock_session)

        assert calc.db_session == mock_session
        assert calc.airports == {}
        assert calc._is_async is False

    def test_init_with_async_session(self):
        """Test initialization with async session."""
        from sqlalchemy.ext.asyncio import AsyncSession
        # Create a more realistic mock for AsyncSession
        mock_session = Mock(spec=AsyncSession)

        calc = TrueCostCalculator(mock_session)

        assert calc.db_session == mock_session
        assert calc.airports == {}
        assert calc._is_async is True


class TestCalculateBagageCost:
    """Tests for calculate_baggage_cost method."""

    def setup_method(self):
        """Set up test calculator."""
        self.mock_session = Mock()
        self.calc = TrueCostCalculator(self.mock_session)

    def test_budget_airline_ryanair(self):
        """Test baggage cost for Ryanair (budget)."""
        cost = self.calc.calculate_baggage_cost('Ryanair', 2)
        assert cost == 60.0  # 2 bags × €30

    def test_budget_airline_wizzair(self):
        """Test baggage cost for WizzAir (budget)."""
        cost = self.calc.calculate_baggage_cost('WizzAir', 2)
        assert cost == 60.0

    def test_budget_airline_easyjet(self):
        """Test baggage cost for EasyJet (budget)."""
        cost = self.calc.calculate_baggage_cost('easyJet', 3)
        assert cost == 90.0  # 3 bags × €30

    def test_budget_airline_case_insensitive(self):
        """Test budget airline detection is case-insensitive."""
        cost = self.calc.calculate_baggage_cost('RYANAIR', 2)
        assert cost == 60.0

    def test_budget_airline_with_whitespace(self):
        """Test budget airline with extra whitespace."""
        cost = self.calc.calculate_baggage_cost('  Wizz Air  ', 2)
        assert cost == 60.0

    def test_legacy_airline_lufthansa(self):
        """Test baggage cost for Lufthansa (legacy)."""
        cost = self.calc.calculate_baggage_cost('Lufthansa', 2)
        assert cost == 0.0  # Included in price

    def test_legacy_airline_tap(self):
        """Test baggage cost for TAP (legacy)."""
        cost = self.calc.calculate_baggage_cost('TAP Portugal', 2)
        assert cost == 0.0

    def test_legacy_airline_british_airways(self):
        """Test baggage cost for British Airways (legacy)."""
        cost = self.calc.calculate_baggage_cost('British Airways', 2)
        assert cost == 0.0

    def test_zero_bags(self):
        """Test with zero bags."""
        cost = self.calc.calculate_baggage_cost('Ryanair', 0)
        assert cost == 0.0

    def test_negative_bags(self):
        """Test with negative bags (invalid)."""
        cost = self.calc.calculate_baggage_cost('Ryanair', -1)
        assert cost == 0.0

    def test_empty_airline(self):
        """Test with empty airline name."""
        cost = self.calc.calculate_baggage_cost('', 2)
        assert cost == 0.0

    def test_none_airline(self):
        """Test with None airline."""
        cost = self.calc.calculate_baggage_cost(None, 2)
        assert cost == 0.0


class TestCalculateParkingCost:
    """Tests for calculate_parking_cost method."""

    def setup_method(self):
        """Set up test calculator with mock airports."""
        self.mock_session = Mock()
        self.calc = TrueCostCalculator(self.mock_session)

        # Mock airport data
        self.calc.airports = {
            'MUC': self._create_airport('MUC', parking_cost=15.0),
            'FMM': self._create_airport('FMM', parking_cost=5.0),
            'NUE': self._create_airport('NUE', parking_cost=10.0),
            'SZG': self._create_airport('SZG', parking_cost=12.0),
            'XXX': self._create_airport('XXX', parking_cost=None),
        }

    def _create_airport(self, iata: str, parking_cost: float = None) -> Airport:
        """Helper to create mock airport."""
        airport = Mock(spec=Airport)
        airport.iata_code = iata
        airport.parking_cost_per_day = parking_cost
        return airport

    def test_parking_cost_muc_7_days(self):
        """Test parking cost for MUC (€15/day) for 7 days."""
        cost = self.calc.calculate_parking_cost('MUC', 7)
        assert cost == 105.0  # 7 × €15

    def test_parking_cost_fmm_7_days(self):
        """Test parking cost for FMM (€5/day) for 7 days."""
        cost = self.calc.calculate_parking_cost('FMM', 7)
        assert cost == 35.0  # 7 × €5

    def test_parking_cost_nue_10_days(self):
        """Test parking cost for NUE (€10/day) for 10 days."""
        cost = self.calc.calculate_parking_cost('NUE', 10)
        assert cost == 100.0  # 10 × €10

    def test_parking_cost_szg_3_days(self):
        """Test parking cost for SZG (€12/day) for 3 days."""
        cost = self.calc.calculate_parking_cost('SZG', 3)
        assert cost == 36.0  # 3 × €12

    def test_parking_cost_one_day(self):
        """Test parking cost for 1 day."""
        cost = self.calc.calculate_parking_cost('MUC', 1)
        assert cost == 15.0

    def test_parking_cost_zero_days(self):
        """Test parking cost for 0 days."""
        cost = self.calc.calculate_parking_cost('MUC', 0)
        assert cost == 0.0

    def test_parking_cost_negative_days(self):
        """Test parking cost with negative days (invalid)."""
        cost = self.calc.calculate_parking_cost('MUC', -5)
        assert cost == 0.0

    def test_parking_cost_unknown_airport(self):
        """Test parking cost for unknown airport."""
        cost = self.calc.calculate_parking_cost('ZZZ', 7)
        assert cost == 0.0

    def test_parking_cost_no_parking_data(self):
        """Test parking cost when airport has no parking data."""
        cost = self.calc.calculate_parking_cost('XXX', 7)
        assert cost == 0.0


class TestCalculateFuelCost:
    """Tests for calculate_fuel_cost method."""

    def setup_method(self):
        """Set up test calculator with mock airports."""
        self.mock_session = Mock()
        self.calc = TrueCostCalculator(self.mock_session)

        # Mock airport data with distances
        self.calc.airports = {
            'MUC': self._create_airport('MUC', distance=40),
            'FMM': self._create_airport('FMM', distance=110),
            'NUE': self._create_airport('NUE', distance=170),
            'SZG': self._create_airport('SZG', distance=145),
        }

    def _create_airport(self, iata: str, distance: int) -> Airport:
        """Helper to create mock airport."""
        airport = Mock(spec=Airport)
        airport.iata_code = iata
        airport.distance_from_home = distance
        return airport

    def test_fuel_cost_muc(self):
        """Test fuel cost for MUC (40km)."""
        cost = self.calc.calculate_fuel_cost('MUC')
        # 40km × 2 (round trip) × €0.08/km = €6.40
        assert cost == 6.4

    def test_fuel_cost_fmm(self):
        """Test fuel cost for FMM (110km)."""
        cost = self.calc.calculate_fuel_cost('FMM')
        # 110km × 2 × €0.08 = €17.60
        assert cost == 17.6

    def test_fuel_cost_nue(self):
        """Test fuel cost for NUE (170km)."""
        cost = self.calc.calculate_fuel_cost('NUE')
        # 170km × 2 × €0.08 = €27.20
        assert cost == 27.2

    def test_fuel_cost_szg(self):
        """Test fuel cost for SZG (145km)."""
        cost = self.calc.calculate_fuel_cost('SZG')
        # 145km × 2 × €0.08 = €23.20
        assert cost == 23.2

    def test_fuel_cost_unknown_airport(self):
        """Test fuel cost for unknown airport."""
        cost = self.calc.calculate_fuel_cost('ZZZ')
        assert cost == 0.0


class TestCalculateTimeValue:
    """Tests for calculate_time_value method."""

    def setup_method(self):
        """Set up test calculator with mock airports."""
        self.mock_session = Mock()
        self.calc = TrueCostCalculator(self.mock_session)

        # Mock airport data with driving times
        self.calc.airports = {
            'MUC': self._create_airport('MUC', driving_time=45),
            'FMM': self._create_airport('FMM', driving_time=140),
            'NUE': self._create_airport('NUE', driving_time=120),
            'SZG': self._create_airport('SZG', driving_time=90),
        }

    def _create_airport(self, iata: str, driving_time: int) -> Airport:
        """Helper to create mock airport."""
        airport = Mock(spec=Airport)
        airport.iata_code = iata
        airport.driving_time = driving_time
        return airport

    def test_time_value_muc(self):
        """Test time value for MUC (45 minutes)."""
        cost = self.calc.calculate_time_value('MUC')
        # 45min × 2 (round trip) = 90min = 1.5 hours × €20/hour = €30.00
        assert cost == 30.0

    def test_time_value_fmm(self):
        """Test time value for FMM (140 minutes)."""
        cost = self.calc.calculate_time_value('FMM')
        # 140min × 2 = 280min = 4.67 hours × €20 = €93.33
        assert cost == 93.33

    def test_time_value_nue(self):
        """Test time value for NUE (120 minutes)."""
        cost = self.calc.calculate_time_value('NUE')
        # 120min × 2 = 240min = 4 hours × €20 = €80.00
        assert cost == 80.0

    def test_time_value_szg(self):
        """Test time value for SZG (90 minutes)."""
        cost = self.calc.calculate_time_value('SZG')
        # 90min × 2 = 180min = 3 hours × €20 = €60.00
        assert cost == 60.0

    def test_time_value_unknown_airport(self):
        """Test time value for unknown airport."""
        cost = self.calc.calculate_time_value('ZZZ')
        assert cost == 0.0


class TestCalculateTotalTrueCost:
    """Tests for calculate_total_true_cost method."""

    def setup_method(self):
        """Set up test calculator with comprehensive mock data."""
        self.mock_session = Mock()
        self.calc = TrueCostCalculator(self.mock_session)

        # Set up complete airport data
        self.calc.airports = {
            'MUC': self._create_airport('MUC', distance=40, driving_time=45, parking=15.0),
            'FMM': self._create_airport('FMM', distance=110, driving_time=140, parking=5.0),
            'NUE': self._create_airport('NUE', distance=170, driving_time=120, parking=10.0),
        }

    def _create_airport(
        self, iata: str, distance: int, driving_time: int, parking: float
    ) -> Airport:
        """Helper to create complete mock airport."""
        airport = Mock(spec=Airport)
        airport.iata_code = iata
        airport.distance_from_home = distance
        airport.driving_time = driving_time
        airport.parking_cost_per_day = parking
        return airport

    def _create_flight(
        self,
        airport_iata: str,
        airline: str,
        total_price: float,
        departure_date: date,
        return_date: date,
    ) -> Flight:
        """Helper to create mock flight."""
        flight = Mock(spec=Flight)
        flight.id = 1
        flight.total_price = total_price
        flight.airline = airline
        flight.departure_date = departure_date
        flight.return_date = return_date
        flight.duration_days = (return_date - departure_date).days

        # Mock origin_airport relationship
        flight.origin_airport = self.calc.airports.get(airport_iata)

        return flight

    def test_true_cost_budget_airline_fmm(self):
        """Test complete true cost calculation for budget airline from FMM."""
        # Create Ryanair flight from FMM for €400
        flight = self._create_flight(
            airport_iata='FMM',
            airline='Ryanair',
            total_price=400.0,
            departure_date=date(2025, 12, 20),
            return_date=date(2025, 12, 27),
        )

        breakdown = self.calc.calculate_total_true_cost(flight, num_bags=2)

        # Verify breakdown
        assert breakdown['base_price'] == 400.0
        assert breakdown['baggage'] == 60.0  # 2 bags × €30 (budget airline)
        assert breakdown['parking'] == 35.0  # 7 days × €5/day
        assert breakdown['fuel'] == 17.6    # 110km × 2 × €0.08
        assert breakdown['time_value'] == 93.33  # 140min × 2 / 60 × €20
        assert breakdown['hidden_costs'] == 205.93  # 60 + 35 + 17.6 + 93.33
        assert breakdown['total_true_cost'] == 605.93  # 400 + 205.93
        assert breakdown['cost_per_person'] == 151.48  # 605.93 / 4
        assert breakdown['airport_iata'] == 'FMM'
        assert breakdown['airline'] == 'Ryanair'
        assert breakdown['num_days'] == 7
        assert breakdown['num_bags'] == 2

    def test_true_cost_legacy_airline_muc(self):
        """Test complete true cost calculation for legacy airline from MUC."""
        # Create Lufthansa flight from MUC for €500
        flight = self._create_flight(
            airport_iata='MUC',
            airline='Lufthansa',
            total_price=500.0,
            departure_date=date(2025, 12, 20),
            return_date=date(2025, 12, 27),
        )

        breakdown = self.calc.calculate_total_true_cost(flight, num_bags=2)

        # Verify breakdown
        assert breakdown['base_price'] == 500.0
        assert breakdown['baggage'] == 0.0   # Legacy airline includes baggage
        assert breakdown['parking'] == 105.0  # 7 days × €15/day
        assert breakdown['fuel'] == 6.4      # 40km × 2 × €0.08
        assert breakdown['time_value'] == 30.0  # 45min × 2 / 60 × €20
        assert breakdown['hidden_costs'] == 141.4  # 0 + 105 + 6.4 + 30
        assert breakdown['total_true_cost'] == 641.4  # 500 + 141.4
        assert breakdown['cost_per_person'] == 160.35  # 641.4 / 4

    def test_fmm_cheaper_than_muc_reversed(self):
        """Test scenario: cheaper FMM flight becomes more expensive after true costs."""
        # FMM: €100 base, budget airline
        fmm_flight = self._create_flight(
            airport_iata='FMM',
            airline='Ryanair',
            total_price=100.0,
            departure_date=date(2025, 12, 20),
            return_date=date(2025, 12, 27),
        )

        # MUC: €150 base, legacy airline
        muc_flight = self._create_flight(
            airport_iata='MUC',
            airline='Lufthansa',
            total_price=150.0,
            departure_date=date(2025, 12, 20),
            return_date=date(2025, 12, 27),
        )

        fmm_breakdown = self.calc.calculate_total_true_cost(fmm_flight, num_bags=2)
        muc_breakdown = self.calc.calculate_total_true_cost(muc_flight, num_bags=2)

        # FMM true cost should be higher due to distance + baggage fees
        # FMM: €100 + €60 (bags) + €35 (parking) + €17.6 (fuel) + €93.33 (time) = €305.93
        # MUC: €150 + €0 (bags) + €105 (parking) + €6.4 (fuel) + €30 (time) = €291.4

        assert fmm_breakdown['base_price'] < muc_breakdown['base_price']  # FMM cheaper base
        assert fmm_breakdown['total_true_cost'] > muc_breakdown['total_true_cost']  # FMM more expensive true cost
        assert fmm_breakdown['total_true_cost'] == 305.93
        assert muc_breakdown['total_true_cost'] == 291.4

    def test_custom_num_bags(self):
        """Test with different number of bags."""
        flight = self._create_flight(
            airport_iata='FMM',
            airline='Ryanair',
            total_price=400.0,
            departure_date=date(2025, 12, 20),
            return_date=date(2025, 12, 27),
        )

        # Test with 3 bags
        breakdown = self.calc.calculate_total_true_cost(flight, num_bags=3)
        assert breakdown['baggage'] == 90.0  # 3 bags × €30
        assert breakdown['num_bags'] == 3

    def test_custom_num_days(self):
        """Test with custom trip duration."""
        flight = self._create_flight(
            airport_iata='FMM',
            airline='Ryanair',
            total_price=400.0,
            departure_date=date(2025, 12, 20),
            return_date=date(2025, 12, 27),
        )

        # Override with 10 days
        breakdown = self.calc.calculate_total_true_cost(flight, num_bags=2, num_days=10)
        assert breakdown['parking'] == 50.0  # 10 days × €5/day
        assert breakdown['num_days'] == 10

    def test_flight_without_origin_airport(self):
        """Test flight without origin_airport relationship loaded."""
        flight = Mock(spec=Flight)
        flight.id = 1
        flight.total_price = 400.0
        flight.airline = 'Ryanair'
        flight.departure_date = date(2025, 12, 20)
        flight.return_date = date(2025, 12, 27)
        flight.duration_days = 7
        flight.origin_airport = None  # Not loaded

        breakdown = self.calc.calculate_total_true_cost(flight, num_bags=2)

        # Should still work, but with zero distance-based costs
        assert breakdown['base_price'] == 400.0
        assert breakdown['baggage'] == 60.0  # Still charged for budget airline
        assert breakdown['parking'] == 0.0
        assert breakdown['fuel'] == 0.0
        assert breakdown['time_value'] == 0.0
        assert breakdown['airport_iata'] is None

    def test_flight_without_return_date(self):
        """Test one-way flight (no return date)."""
        flight = Mock(spec=Flight)
        flight.id = 1
        flight.total_price = 200.0
        flight.airline = 'Ryanair'
        flight.departure_date = date(2025, 12, 20)
        flight.return_date = None
        flight.duration_days = None
        flight.origin_airport = self.calc.airports['MUC']

        # Should use default 7 days
        breakdown = self.calc.calculate_total_true_cost(flight, num_bags=2)
        assert breakdown['num_days'] == 7
        assert breakdown['parking'] == 105.0  # 7 days × €15


class TestBatchProcessing:
    """Tests for batch processing methods."""

    def setup_method(self):
        """Set up test calculator with mock data."""
        self.mock_session = Mock()
        self.mock_session.commit = Mock()
        self.mock_session.rollback = Mock()

        self.calc = TrueCostCalculator(self.mock_session)

        # Set up airport data
        self.calc.airports = {
            'MUC': self._create_airport('MUC', distance=40, driving_time=45, parking=15.0),
            'FMM': self._create_airport('FMM', distance=110, driving_time=140, parking=5.0),
        }

    def _create_airport(
        self, iata: str, distance: int, driving_time: int, parking: float
    ) -> Airport:
        """Helper to create mock airport."""
        airport = Mock(spec=Airport)
        airport.iata_code = iata
        airport.distance_from_home = distance
        airport.driving_time = driving_time
        airport.parking_cost_per_day = parking
        return airport

    def _create_flight(
        self, flight_id: int, airport_iata: str, airline: str, total_price: float
    ) -> Flight:
        """Helper to create mock flight."""
        flight = Mock(spec=Flight)
        flight.id = flight_id
        flight.total_price = total_price
        flight.airline = airline
        flight.departure_date = date(2025, 12, 20)
        flight.return_date = date(2025, 12, 27)
        flight.duration_days = 7
        flight.origin_airport = self.calc.airports.get(airport_iata)
        flight.true_cost = None
        return flight

    def test_calculate_for_all_flights(self):
        """Test batch calculation for multiple flights."""
        flights = [
            self._create_flight(1, 'MUC', 'Lufthansa', 500.0),
            self._create_flight(2, 'FMM', 'Ryanair', 400.0),
            self._create_flight(3, 'MUC', 'Ryanair', 300.0),
        ]

        breakdowns = self.calc.calculate_for_all_flights(flights, num_bags=2, commit=False)

        assert len(breakdowns) == 3
        assert flights[0].true_cost == 641.4  # MUC Lufthansa: 500 + 0 + 105 + 6.4 + 30
        assert flights[1].true_cost == 605.93  # FMM Ryanair: 400 + 60 + 35 + 17.6 + 93.33
        assert flights[2].true_cost == 501.4  # MUC Ryanair: 300 + 60 + 105 + 6.4 + 30

    def test_calculate_for_all_flights_with_commit(self):
        """Test batch calculation with database commit."""
        flights = [
            self._create_flight(1, 'MUC', 'Lufthansa', 500.0),
        ]

        self.calc.calculate_for_all_flights(flights, num_bags=2, commit=True)

        # Verify commit was called
        self.mock_session.commit.assert_called_once()

    def test_calculate_for_all_flights_empty_list(self):
        """Test batch calculation with empty flight list."""
        breakdowns = self.calc.calculate_for_all_flights([], num_bags=2)

        assert breakdowns == []
        # Should not commit empty changes
        self.mock_session.commit.assert_not_called()


class TestPrintBreakdown:
    """Tests for print_breakdown method."""

    def test_print_breakdown(self, capsys):
        """Test printing cost breakdown."""
        mock_session = Mock()
        calc = TrueCostCalculator(mock_session)

        breakdown = {
            'airport_iata': 'FMM',
            'airline': 'Ryanair',
            'base_price': 400.0,
            'baggage': 60.0,
            'parking': 35.0,
            'fuel': 17.6,
            'time_value': 93.33,
            'hidden_costs': 205.93,
            'total_true_cost': 605.93,
            'cost_per_person': 151.48,
            'num_bags': 2,
            'num_days': 7,
        }

        calc.print_breakdown(breakdown)

        # Capture and verify output
        captured = capsys.readouterr()
        assert 'FMM' in captured.out
        assert 'Ryanair' in captured.out
        assert '400.00' in captured.out
        assert '60.00' in captured.out
        assert '605.93' in captured.out
