"""
Event model for storing family activities and parent escape opportunities.
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Event(Base, TimestampMixin):
    """
    Model for storing events and activities at destinations.
    Includes family activities and parent escape opportunities.
    """

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Location
    destination_city: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, comment="City name, e.g., 'Lisbon', 'Barcelona'"
    )

    # Event details
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True, comment="For multi-day events"
    )

    # Categorization
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="e.g., 'family', 'parent_escape', 'cultural', 'outdoor'",
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Pricing
    price_range: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="e.g., 'free', '<€20', '€20-50', '€50+'"
    )

    # Source information
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="e.g., 'eventbrite', 'tripadvisor', 'manual'"
    )
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # AI scoring
    ai_relevance_score: Mapped[Optional[float]] = mapped_column(
        Numeric(3, 1),
        nullable=True,
        index=True,
        comment="AI-generated relevance score from 0 to 10",
    )

    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="NOW()", index=True
    )

    def __repr__(self) -> str:
        return (
            f"<Event(id={self.id}, title='{self.title}', "
            f"city='{self.destination_city}', date={self.event_date}, category='{self.category}')>"
        )

    @property
    def is_multi_day(self) -> bool:
        """Check if event spans multiple days."""
        return self.end_date is not None and self.end_date > self.event_date

    @property
    def duration_days(self) -> int:
        """Calculate event duration in days."""
        if self.end_date:
            return (self.end_date - self.event_date).days + 1
        return 1
