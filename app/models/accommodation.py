"""
Accommodation model for storing hotels, Airbnbs, and apartment rentals.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Accommodation(Base, TimestampMixin):
    """
    Model for storing accommodation options.
    Supports hotels, Airbnbs, and serviced apartments.
    """

    __tablename__ = "accommodations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Location
    destination_city: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, comment="City name, e.g., 'Lisbon', 'Barcelona'"
    )

    # Basic information
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="e.g., 'hotel', 'airbnb', 'apartment'"
    )
    bedrooms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Pricing
    price_per_night: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, comment="Price in EUR per night"
    )

    # Family-friendly features
    family_friendly: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_kitchen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_kids_club: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Reviews and ratings
    rating: Mapped[Optional[float]] = mapped_column(
        Numeric(3, 1), nullable=True, comment="Rating from 0 to 10"
    )
    review_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Source information
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True, comment="e.g., 'booking.com', 'airbnb'"
    )
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="NOW()", index=True
    )

    def __repr__(self) -> str:
        return (
            f"<Accommodation(id={self.id}, name='{self.name}', "
            f"city='{self.destination_city}', price={self.price_per_night} EUR/night)>"
        )

    @property
    def total_cost(self) -> float:
        """Calculate total cost for a 7-night stay."""
        return float(self.price_per_night) * 7

    @property
    def is_highly_rated(self) -> bool:
        """Check if accommodation has high rating (>= 8.0)."""
        if self.rating:
            return float(self.rating) >= 8.0
        return False
