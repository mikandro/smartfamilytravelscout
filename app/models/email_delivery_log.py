"""
Email delivery log model for tracking notification delivery status.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class EmailDeliveryLog(Base, TimestampMixin):
    """
    Model for tracking email delivery status and history.
    Helps prevent duplicate notifications and provides delivery analytics.
    """

    __tablename__ = "email_delivery_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Email details
    recipient_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Recipient's email address",
    )
    subject: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Email subject line",
    )
    email_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type: 'daily_digest', 'instant_alert', 'parent_escape_digest'",
    )

    # Related entities
    user_preference_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("user_preferences.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User preference that triggered the email",
    )
    trip_package_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("trip_packages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Trip package for instant alerts (if applicable)",
    )

    # Delivery status
    sent_successfully: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether email was sent successfully",
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if delivery failed",
    )

    # Metadata
    num_deals_included: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of deals included in the email (for digests)",
    )

    def __repr__(self) -> str:
        status = "✓" if self.sent_successfully else "✗"
        return (
            f"<EmailDeliveryLog(id={self.id}, type='{self.email_type}', "
            f"to='{self.recipient_email}', status='{status}', "
            f"sent_at={self.created_at})>"
        )

    @property
    def delivery_status(self) -> str:
        """Get human-readable delivery status."""
        return "Delivered" if self.sent_successfully else "Failed"
