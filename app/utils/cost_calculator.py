"""
True Cost Calculator for SmartFamilyTravelScout.

Calculates the real total cost of flying from each airport, including:
- Base flight price
- Baggage fees (budget airlines charge extra)
- Parking costs (airport-specific, per day)
- Fuel costs (drive to/from airport)
- Time value (opportunity cost of driving)

Example:
    A €100 flight from FMM might cost more than €150 from MUC when you factor in:
    - 110km drive (€17.60 fuel round trip)
    - €35 parking for 7 days
    - Time cost for 140min driving (€46.67)
"""

import logging
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.config import settings
from app.models.airport import Airport
from app.models.flight import Flight

logger = logging.getLogger(__name__)


class TrueCostCalculator:
    """
    Calculator for determining the true total cost of flights including hidden expenses.

    Cost Components:
    - Base Price: From flight scraper (total_price field)
    - Baggage: Budget airlines charge €30/bag, legacy carriers include it
    - Parking: Airport-dependent, per day
    - Fuel: €0.08/km × distance × 2 (round trip)
    - Time Value: €20/hour × driving time × 2 (round trip)
    """

    # Budget airlines that charge for baggage
    BUDGET_AIRLINES = ['ryanair', 'wizzair', 'easyjet', 'vueling', 'wizz air']

    # Cost constants (in EUR)
    BAGGAGE_COST_BUDGET = 30.0  # Per checked bag on budget airlines
    FUEL_COST_PER_KM = 0.08     # EU average fuel cost per kilometer
    TIME_VALUE_PER_HOUR = 20.0  # Opportunity cost per hour of driving

    def __init__(self, db_session: Session | AsyncSession):
        """
        Initialize the calculator with database access.

        Args:
            db_session: SQLAlchemy database session (sync or async)
        """
        self.db_session = db_session
        self.airports: Dict[str, Airport] = {}
        self._is_async = isinstance(db_session, AsyncSession)

    def load_airports(self) -> Dict[str, Airport]:
        """
        Load airport data from database and cache it.

        Returns:
            Dictionary mapping IATA codes to Airport objects
        """
        if self._is_async:
            raise RuntimeError(
                "Cannot call load_airports() on async session. Use load_airports_async() instead."
            )

        stmt = select(Airport)
        result = self.db_session.execute(stmt)
        airports = result.scalars().all()

        self.airports = {airport.iata_code: airport for airport in airports}
        logger.info(f"Loaded {len(self.airports)} airports from database")

        return self.airports

    async def load_airports_async(self) -> Dict[str, Airport]:
        """
        Load airport data from database asynchronously and cache it.

        Returns:
            Dictionary mapping IATA codes to Airport objects
        """
        if not self._is_async:
            raise RuntimeError(
                "Cannot call load_airports_async() on sync session. Use load_airports() instead."
            )

        stmt = select(Airport)
        result = await self.db_session.execute(stmt)
        airports = result.scalars().all()

        self.airports = {airport.iata_code: airport for airport in airports}
        logger.info(f"Loaded {len(self.airports)} airports from database")

        return self.airports

    def calculate_baggage_cost(self, airline: str, num_bags: int) -> float:
        """
        Calculate baggage fees based on airline type.

        Budget airlines charge per bag, legacy carriers include it.

        Args:
            airline: Airline name (e.g., 'Ryanair', 'Lufthansa')
            num_bags: Number of checked bags

        Returns:
            Total baggage cost in EUR

        Examples:
            >>> calc.calculate_baggage_cost('Ryanair', 2)
            60.0
            >>> calc.calculate_baggage_cost('Lufthansa', 2)
            0.0
        """
        if not airline or num_bags <= 0:
            return 0.0

        # Check if airline is budget (case-insensitive)
        airline_lower = airline.lower().strip()
        is_budget = any(budget in airline_lower for budget in self.BUDGET_AIRLINES)

        if is_budget:
            return num_bags * self.BAGGAGE_COST_BUDGET

        return 0.0  # Legacy carriers include baggage

    def calculate_parking_cost(self, airport_iata: str, num_days: int) -> float:
        """
        Calculate parking cost for the trip duration.

        Args:
            airport_iata: Airport IATA code (e.g., 'MUC', 'FMM')
            num_days: Number of days to park

        Returns:
            Total parking cost in EUR

        Examples:
            >>> calc.calculate_parking_cost('MUC', 7)
            105.0
            >>> calc.calculate_parking_cost('FMM', 7)
            35.0
        """
        if num_days <= 0:
            return 0.0

        airport = self.airports.get(airport_iata)
        if not airport or not airport.parking_cost_per_day:
            logger.warning(f"No parking cost data for airport {airport_iata}")
            return 0.0

        return float(airport.parking_cost_per_day) * num_days

    def calculate_fuel_cost(self, airport_iata: str) -> float:
        """
        Calculate fuel cost for round-trip drive to airport.

        Formula: distance (km) × €0.08/km × 2 (round trip)

        Args:
            airport_iata: Airport IATA code (e.g., 'MUC', 'FMM')

        Returns:
            Total fuel cost in EUR for round trip

        Examples:
            >>> calc.calculate_fuel_cost('FMM')  # 110km from Munich
            17.6
            >>> calc.calculate_fuel_cost('MUC')  # 40km from Munich
            6.4
        """
        airport = self.airports.get(airport_iata)
        if not airport:
            logger.warning(f"No airport data found for {airport_iata}")
            return 0.0

        # Round trip = distance × 2
        round_trip_km = airport.distance_from_home * 2
        return round(round_trip_km * self.FUEL_COST_PER_KM, 2)

    def calculate_time_value(self, airport_iata: str) -> float:
        """
        Calculate opportunity cost of driving time.

        Formula: driving_time (minutes) / 60 × €20/hour × 2 (round trip)

        Args:
            airport_iata: Airport IATA code (e.g., 'MUC', 'FMM')

        Returns:
            Total time cost in EUR for round trip

        Examples:
            >>> calc.calculate_time_value('FMM')  # 140 minutes
            93.33
            >>> calc.calculate_time_value('MUC')  # 45 minutes
            30.0
        """
        airport = self.airports.get(airport_iata)
        if not airport:
            logger.warning(f"No airport data found for {airport_iata}")
            return 0.0

        # Round trip = driving time × 2
        round_trip_minutes = airport.driving_time * 2
        hours = round_trip_minutes / 60.0
        return round(hours * self.TIME_VALUE_PER_HOUR, 2)

    def calculate_total_true_cost(
        self,
        flight: Flight,
        num_bags: int = 2,
        num_days: Optional[int] = None,
    ) -> Dict:
        """
        Calculate complete true cost breakdown for a flight.

        Args:
            flight: Flight object from database
            num_bags: Number of checked bags (default: 2 for family)
            num_days: Trip duration in days (auto-calculated from flight dates if not provided)

        Returns:
            Dictionary with cost breakdown:
            {
                'base_price': 400.00,       # Flight price for 4 people
                'baggage': 60.00,            # 2 bags × €30
                'parking': 35.00,            # 7 days × €5/day
                'fuel': 17.60,               # 110km × €0.08 × 2
                'time_value': 46.67,         # 140min ÷ 60 × €20/hour × 2
                'total_true_cost': 559.27,   # Sum of all costs
                'hidden_costs': 159.27,      # Everything except base price
                'cost_per_person': 139.82,   # Total ÷ 4 people
                'airport_iata': 'FMM',       # Origin airport
                'airline': 'Ryanair'         # Airline name
            }

        Examples:
            >>> breakdown = calc.calculate_total_true_cost(flight, num_bags=2)
            >>> print(f"True cost: €{breakdown['total_true_cost']:.2f}")
            True cost: €559.27
        """
        # Get origin airport IATA code
        if hasattr(flight, 'origin_airport') and flight.origin_airport:
            airport_iata = flight.origin_airport.iata_code
        else:
            # If relationship not loaded, need to fetch it
            logger.warning(f"Flight {flight.id} missing origin_airport relationship")
            airport_iata = None

        # Auto-calculate trip duration from flight dates if not provided
        if num_days is None:
            if flight.duration_days:
                num_days = flight.duration_days
            else:
                num_days = 7  # Default to 7 days if cannot determine
                logger.warning(
                    f"Cannot determine trip duration for flight {flight.id}, using default {num_days} days"
                )

        # Calculate each cost component
        base_price = float(flight.total_price)
        baggage = self.calculate_baggage_cost(flight.airline, num_bags)
        parking = self.calculate_parking_cost(airport_iata, num_days) if airport_iata else 0.0
        fuel = self.calculate_fuel_cost(airport_iata) if airport_iata else 0.0
        time_value = self.calculate_time_value(airport_iata) if airport_iata else 0.0

        # Calculate totals
        hidden_costs = baggage + parking + fuel + time_value
        total_true_cost = base_price + hidden_costs
        cost_per_person = round(total_true_cost / float(settings.family_size), 2)

        return {
            'base_price': round(base_price, 2),
            'baggage': round(baggage, 2),
            'parking': round(parking, 2),
            'fuel': round(fuel, 2),
            'time_value': round(time_value, 2),
            'total_true_cost': round(total_true_cost, 2),
            'hidden_costs': round(hidden_costs, 2),
            'cost_per_person': cost_per_person,
            'airport_iata': airport_iata,
            'airline': flight.airline,
            'num_days': num_days,
            'num_bags': num_bags,
        }

    def calculate_for_all_flights(
        self,
        flights: List[Flight],
        num_bags: int = 2,
        commit: bool = True,
    ) -> List[Dict]:
        """
        Batch calculate true costs for multiple flights (synchronous).

        Updates the flight.true_cost field in the database.

        Args:
            flights: List of Flight objects
            num_bags: Number of checked bags (default: 2)
            commit: Whether to commit changes to database (default: True)

        Returns:
            List of cost breakdown dictionaries

        Examples:
            >>> flights = db.query(Flight).all()
            >>> breakdowns = calc.calculate_for_all_flights(flights)
            >>> print(f"Processed {len(breakdowns)} flights")
        """
        if self._is_async:
            raise RuntimeError(
                "Cannot call calculate_for_all_flights() on async session. "
                "Use calculate_for_all_flights_async() instead."
            )

        breakdowns = []
        updated_count = 0

        for flight in flights:
            try:
                breakdown = self.calculate_total_true_cost(flight, num_bags=num_bags)
                breakdowns.append(breakdown)

                # Update flight record
                flight.true_cost = breakdown['total_true_cost']
                updated_count += 1

            except Exception as e:
                logger.error(f"Error calculating true cost for flight {flight.id}: {e}")
                continue

        if commit and updated_count > 0:
            try:
                self.db_session.commit()
                logger.info(f"Updated true costs for {updated_count} flights")
            except Exception as e:
                self.db_session.rollback()
                logger.error(f"Error committing true cost updates: {e}")
                raise

        return breakdowns

    async def calculate_for_all_flights_async(
        self,
        flights: List[Flight],
        num_bags: int = 2,
        commit: bool = True,
    ) -> List[Dict]:
        """
        Batch calculate true costs for multiple flights (asynchronous).

        Updates the flight.true_cost field in the database.

        Args:
            flights: List of Flight objects
            num_bags: Number of checked bags (default: 2)
            commit: Whether to commit changes to database (default: True)

        Returns:
            List of cost breakdown dictionaries

        Examples:
            >>> flights = (await db.execute(select(Flight))).scalars().all()
            >>> breakdowns = await calc.calculate_for_all_flights_async(flights)
            >>> print(f"Processed {len(breakdowns)} flights")
        """
        if not self._is_async:
            raise RuntimeError(
                "Cannot call calculate_for_all_flights_async() on sync session. "
                "Use calculate_for_all_flights() instead."
            )

        breakdowns = []
        updated_count = 0

        for flight in flights:
            try:
                breakdown = self.calculate_total_true_cost(flight, num_bags=num_bags)
                breakdowns.append(breakdown)

                # Update flight record
                flight.true_cost = breakdown['total_true_cost']
                updated_count += 1

            except Exception as e:
                logger.error(f"Error calculating true cost for flight {flight.id}: {e}")
                continue

        if commit and updated_count > 0:
            try:
                await self.db_session.commit()
                logger.info(f"Updated true costs for {updated_count} flights")
            except Exception as e:
                await self.db_session.rollback()
                logger.error(f"Error committing true cost updates: {e}")
                raise

        return breakdowns

    def print_breakdown(self, breakdown: Dict) -> None:
        """
        Pretty print a cost breakdown for debugging/display.

        Args:
            breakdown: Cost breakdown dictionary from calculate_total_true_cost()

        Examples:
            >>> breakdown = calc.calculate_total_true_cost(flight)
            >>> calc.print_breakdown(breakdown)

            True Cost Breakdown - FMM (Ryanair)
            =====================================
            Base Flight Price:     €400.00
            Baggage (2 bags):       €60.00
            Parking (7 days):       €35.00
            Fuel (round trip):      €17.60
            Time Value:             €46.67
            -------------------------------------
            Hidden Costs:          €159.27
            TOTAL TRUE COST:       €559.27
            Cost per person:       €139.82
        """
        print(f"\nTrue Cost Breakdown - {breakdown['airport_iata']} ({breakdown['airline']})")
        print("=" * 60)
        print(f"Base Flight Price:     €{breakdown['base_price']:>8.2f}")
        print(f"Baggage ({breakdown['num_bags']} bags):       €{breakdown['baggage']:>8.2f}")
        print(f"Parking ({breakdown['num_days']} days):      €{breakdown['parking']:>8.2f}")
        print(f"Fuel (round trip):     €{breakdown['fuel']:>8.2f}")
        print(f"Time Value:            €{breakdown['time_value']:>8.2f}")
        print("-" * 60)
        print(f"Hidden Costs:          €{breakdown['hidden_costs']:>8.2f}")
        print(f"TOTAL TRUE COST:       €{breakdown['total_true_cost']:>8.2f}")
        print(f"Cost per person:       €{breakdown['cost_per_person']:>8.2f}")
        print()
