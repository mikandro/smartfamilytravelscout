"""
Models for the weekend planner: evergreen places, visits and sent plans.

A ``Place`` is somewhere near home the family can go on any weekend (a zoo, a
museum, a lake). It is deliberately separate from ``Event``, which is tied to a
date and a trip destination.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    ARRAY,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

#: Allowed values for ``Place.setting``.
SETTING_INDOOR = "indoor"
SETTING_OUTDOOR = "outdoor"
SETTING_MIXED = "mixed"


class Place(Base, TimestampMixin):
    """An evergreen family destination within day-trip range of home."""

    __tablename__ = "places"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="e.g. 'museum', 'zoo', 'pool', 'playground', 'lake', 'hike'",
    )
    setting: Mapped[str] = mapped_column(
        String(10), nullable=False, index=True, comment="'indoor', 'outdoor' or 'mixed'"
    )

    # Location and travel (travel times are estimates from the home location)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    drive_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True, comment="Estimated one-way drive from home"
    )
    transit_minutes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="One-way by S-Bahn/U-Bahn/tram incl. walk; NULL = car only",
    )
    transit_note: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="e.g. 'S2 to Poing, 10 min walk'"
    )

    # Suitability
    age_min: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    age_max: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Oldest age that still enjoys it; NULL = no limit"
    )
    stroller_friendly: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    duration_hours: Mapped[float] = mapped_column(
        Float, nullable=False, default=2.0, comment="Typical visit length"
    )

    # Practicalities
    cost_family_eur: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Rough entry cost for 2 adults + 2 kids; 0 = free"
    )
    booking_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    months_open: Mapped[Optional[List[int]]] = mapped_column(
        ARRAY(Integer), nullable=True, comment="Months (1-12) it is worth going; NULL = all year"
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Why it works (or what to watch for) with these kids"
    )
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    visits: Mapped[List["PlaceVisit"]] = relationship(
        back_populates="place", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Place(id={self.id}, slug={self.slug!r}, setting={self.setting!r})>"

    def is_open_in(self, month: int) -> bool:
        """Whether the place is in season for the given month (1-12)."""
        return not self.months_open or month in self.months_open

    def suits_ages(self, ages: List[int]) -> bool:
        """Whether every child in ``ages`` falls inside the place's age range."""
        for age in ages:
            if age < self.age_min:
                return False
            if self.age_max is not None and age > self.age_max:
                return False
        return True


class PlaceVisit(Base, TimestampMixin):
    """A record that the family went somewhere, used to keep plans varied."""

    __tablename__ = "place_visits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    place_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("places.id", ondelete="CASCADE"), nullable=False, index=True
    )
    visited_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="1-5")
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    place: Mapped[Place] = relationship(back_populates="visits")

    def __repr__(self) -> str:
        return f"<PlaceVisit(place_id={self.place_id}, visited_on={self.visited_on})>"


class WeekendPlan(Base, TimestampMixin):
    """
    The plan sent for one weekend.

    Stored so the Friday check can tell whether the forecast has changed since
    the Thursday email, and so there is a history of what was suggested.
    """

    __tablename__ = "weekend_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    weekend_start: Mapped[date] = mapped_column(
        Date, nullable=False, unique=True, index=True, comment="The Saturday"
    )
    forecast_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    plan_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<WeekendPlan(weekend_start={self.weekend_start}, sent_at={self.sent_at})>"
