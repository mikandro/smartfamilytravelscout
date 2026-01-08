"""
User preferences model for customizing trip recommendations.
"""

import secrets
from typing import List, Optional

from sqlalchemy import ARRAY, Boolean, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class UserPreference(Base, TimestampMixin):
    """
    Model for storing user preferences and search criteria.
    Supports multi-user in the future.
    """

    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, index=True, comment="For future multi-user support"
    )

    # Budget constraints
    max_flight_price_family: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, comment="Maximum flight price per person for family trips"
    )
    max_flight_price_parents: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, comment="Maximum flight price per person for parent escapes"
    )
    max_total_budget_family: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, comment="Maximum total budget for family trips"
    )

    # Destination preferences
    preferred_destinations: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
        comment="List of preferred cities, e.g., ['Lisbon', 'Barcelona']",
    )
    avoid_destinations: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
        comment="List of cities to avoid",
    )

    # Interest categories
    interests: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
        comment="List of interests, e.g., ['wine', 'museums', 'beaches', 'hiking']",
    )

    # Email and notification settings
    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="User's email address for notifications",
    )
    enable_notifications: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Master switch for all email notifications",
    )
    enable_daily_digest: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Receive daily digest emails with top deals",
    )
    enable_instant_alerts: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Receive instant alerts for exceptional deals",
    )
    enable_parent_escape_digest: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Receive weekly parent escape recommendations",
    )
    notification_threshold: Mapped[float] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=70.0,
        comment="Minimum AI score to trigger notifications",
    )
    unsubscribe_token: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        unique=True,
        index=True,
        comment="Unique token for unsubscribe links",
    )

    # Parent escape settings
    parent_escape_frequency: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="quarterly",
        comment="How often to suggest parent escapes: 'monthly', 'quarterly', 'semi-annual'",
    )

    def __repr__(self) -> str:
        return (
            f"<UserPreference(id={self.id}, user_id={self.user_id}, "
            f"max_flight_price_family={self.max_flight_price_family}, "
            f"notification_threshold={self.notification_threshold})>"
        )

    @property
    def preferred_destinations_str(self) -> str:
        """Get comma-separated string of preferred destinations."""
        if self.preferred_destinations:
            return ", ".join(self.preferred_destinations)
        return "None"

    @property
    def interests_str(self) -> str:
        """Get comma-separated string of interests."""
        if self.interests:
            return ", ".join(self.interests)
        return "None"

    def generate_unsubscribe_token(self) -> str:
        """Generate a unique unsubscribe token."""
        self.unsubscribe_token = secrets.token_urlsafe(32)
        return self.unsubscribe_token

    def should_receive_notifications(self) -> bool:
        """Check if user should receive any notifications."""
        return bool(
            self.enable_notifications
            and self.email
            and (self.enable_daily_digest or self.enable_instant_alerts or self.enable_parent_escape_digest)
        )
