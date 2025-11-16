"""
Price history model for tracking flight price trends.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PriceHistory(Base):
    """
    Model for tracking historical flight prices.
    Used for price trend analysis and deal detection.
    Note: Does not use TimestampMixin to avoid duplicate created_at field.
    """

    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Route information
    route: Mapped[str] = mapped_column(
        String(10), nullable=False, index=True, comment="Route code, e.g., 'MUC-LIS'"
    )

    # Price data
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, comment="Price in EUR")

    # Source information
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True, comment="e.g., 'kiwi', 'skyscanner'"
    )
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # Created timestamp (single field instead of mixin)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="NOW()", index=True
    )

    def __repr__(self) -> str:
        return (
            f"<PriceHistory(id={self.id}, route='{self.route}', "
            f"price={self.price} EUR, source='{self.source}', date={self.scraped_at.date()})>"
        )
