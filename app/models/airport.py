"""
Airport model for storing departure airport information.
"""

from typing import List, Optional

from sqlalchemy import ARRAY, Boolean, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Airport(Base, TimestampMixin):
    """
    Model for storing airport information.
    Includes distance and driving time from Munich home base.
    Extended with OurAirports.com data for comprehensive airport coverage.
    """

    __tablename__ = "airports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    iata_code: Mapped[str] = mapped_column(String(3), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)

    # Location and geography fields (from OurAirports)
    country: Mapped[Optional[str]] = mapped_column(
        String(2), nullable=True, index=True, comment="ISO 3166-1 alpha-2 country code"
    )
    latitude: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 6), nullable=True, comment="Latitude in decimal degrees"
    )
    longitude: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 6), nullable=True, comment="Longitude in decimal degrees"
    )
    timezone: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="IANA timezone identifier (e.g., Europe/Berlin)"
    )
    icao_code: Mapped[Optional[str]] = mapped_column(
        String(4), nullable=True, index=True, comment="4-letter ICAO code"
    )
    airport_type: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True, comment="Airport type: large_airport, medium_airport, etc."
    )

    # Distance and cost fields (for origin airports)
    distance_from_home: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, default=0, comment="Distance in kilometers from Munich home"
    )
    driving_time: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, default=0, comment="Driving time in minutes from Munich home"
    )
    preferred_for: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String), nullable=True, comment="e.g., ['budget', 'direct_flights']"
    )
    parking_cost_per_day: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2), nullable=True, comment="Parking cost in euros per day"
    )
    is_origin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
        comment="Whether this airport can be used as an origin"
    )
    is_destination: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
        comment="Whether this airport can be used as a destination"
    )

    # Relationships
    departing_flights: Mapped[List["Flight"]] = relationship(
        "Flight",
        foreign_keys="Flight.origin_airport_id",
        back_populates="origin_airport",
        cascade="all, delete-orphan",
    )
    arriving_flights: Mapped[List["Flight"]] = relationship(
        "Flight",
        foreign_keys="Flight.destination_airport_id",
        back_populates="destination_airport",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Airport(iata_code='{self.iata_code}', name='{self.name}', city='{self.city}')>"

    @property
    def total_trip_cost(self) -> float:
        """Calculate total additional cost including driving and parking."""
        # Estimate: 0.30 EUR per km for fuel + parking cost for 7 days
        fuel_cost = self.distance_from_home * 0.30 * 2  # Round trip
        parking_cost = (self.parking_cost_per_day or 0) * 7  # Average 7-day trip
        return fuel_cost + parking_cost
