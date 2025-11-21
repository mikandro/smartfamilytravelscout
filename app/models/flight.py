"""
Flight model for storing flight deals from various sources.
"""

from datetime import date, datetime, time
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Flight(Base, TimestampMixin):
    """
    SQLAlchemy model for storing flight information from multiple scraper sources.

    Represents flight deals with pricing, schedule, and source information.
    Supports both one-way and round-trip flights with optional return dates.
    Tracks true cost including baggage, parking, and other fees.

    Attributes:
        id: Unique flight ID (auto-increment)
        origin_airport_id: Foreign key to origin Airport
        destination_airport_id: Foreign key to destination Airport
        airline: Airline name (e.g., "Ryanair", "Lufthansa")
        departure_date: Flight departure date
        departure_time: Flight departure time (optional)
        return_date: Return flight date (optional, null for one-way)
        return_time: Return flight time (optional)
        price_per_person: Base price in EUR per person
        total_price: Total price for 4 people in EUR
        true_cost: Total cost including fees, parking, baggage (calculated)
        booking_class: Seat class (e.g., "Economy", "Premium Economy")
        direct_flight: Whether flight is non-stop
        source: Scraper source name ("kiwi", "skyscanner", "ryanair", "wizzair")
        booking_url: Deep link to booking page
        scraped_at: Timestamp when flight was scraped
        origin_airport: Relationship to origin Airport object
        destination_airport: Relationship to destination Airport object

    Examples:
        >>> flight = Flight(
        ...     airline="Ryanair",
        ...     departure_date=date(2025, 6, 15),
        ...     return_date=date(2025, 6, 22),
        ...     price_per_person=89.99,
        ...     total_price=359.96,
        ...     direct_flight=True,
        ...     source="ryanair"
        ... )
    """

    __tablename__ = "flights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Airport relationships
    origin_airport_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("airports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    destination_airport_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("airports.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Flight details
    airline: Mapped[str] = mapped_column(String(50), nullable=False)
    departure_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    departure_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    return_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    return_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)

    # Pricing
    price_per_person: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, comment="Price in EUR per person"
    )
    total_price: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, comment="Total price for 4 people in EUR"
    )
    true_cost: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="True cost including airport costs (calculated later)",
    )

    # Flight characteristics
    booking_class: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="e.g., Economy, Premium Economy"
    )
    direct_flight: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Source information
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True, comment="e.g., kiwi, skyscanner, ryanair"
    )
    booking_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="NOW()", index=True
    )

    # Relationships
    origin_airport: Mapped["Airport"] = relationship(
        "Airport", foreign_keys=[origin_airport_id], back_populates="departing_flights"
    )
    destination_airport: Mapped["Airport"] = relationship(
        "Airport", foreign_keys=[destination_airport_id], back_populates="arriving_flights"
    )

    def __repr__(self) -> str:
        return (
            f"<Flight(id={self.id}, {self.origin_airport.iata_code if self.origin_airport else 'N/A'}"
            f"->{self.destination_airport.iata_code if self.destination_airport else 'N/A'}, "
            f"departure={self.departure_date}, price={self.price_per_person} EUR)>"
        )

    @property
    def route(self) -> str:
        """
        Return route code in IATA format (e.g., 'MUC-LIS').

        Returns:
            str: Origin-Destination airport codes (e.g., "MUC-LIS", "VIE-BCN")
        """
        origin_code = self.origin_airport.iata_code if self.origin_airport else "N/A"
        dest_code = self.destination_airport.iata_code if self.destination_airport else "N/A"
        return f"{origin_code}-{dest_code}"

    @property
    def is_round_trip(self) -> bool:
        """
        Check if this is a round-trip flight.

        Returns:
            bool: True if return_date is set, False for one-way flights
        """
        return self.return_date is not None

    @property
    def duration_days(self) -> Optional[int]:
        """
        Calculate trip duration in days for round-trip flights.

        Returns:
            Optional[int]: Number of days between departure and return,
                          or None for one-way flights
        """
        if self.return_date and self.departure_date:
            return (self.return_date - self.departure_date).days
        return None
