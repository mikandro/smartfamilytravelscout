"""
Model pricing configuration for AI services.

Stores pricing information for different AI models with effective dates,
allowing for historical tracking and easy price updates without code changes.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ModelPricing(Base, TimestampMixin):
    """
    Store pricing information for AI models with effective dates.

    This model enables dynamic pricing configuration without code changes.
    Historical pricing is preserved for accurate cost tracking over time.

    Example:
        >>> pricing = ModelPricing(
        ...     service="claude",
        ...     model="claude-sonnet-4-5-20250929",
        ...     input_cost_per_million=3.0,
        ...     output_cost_per_million=15.0,
        ...     effective_date=datetime(2025, 11, 1)
        ... )
    """

    __tablename__ = "model_pricing"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Service and model information
    service: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="API service name (e.g., 'claude', 'openai')",
    )

    model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Model name (e.g., 'claude-sonnet-4-5-20250929')",
    )

    # Pricing information (in USD)
    input_cost_per_million: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Cost per 1 million input tokens in USD",
    )

    output_cost_per_million: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Cost per 1 million output tokens in USD",
    )

    # Effective date for this pricing
    effective_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Date when this pricing becomes effective",
    )

    # Optional fields
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        server_default="USD",
        comment="Currency code (ISO 4217)",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Additional notes about this pricing change",
    )

    # Composite indexes and constraints
    __table_args__ = (
        # Ensure we can efficiently query the latest pricing for a service/model
        Index("ix_model_pricing_service_model_date", "service", "model", "effective_date"),
        # Prevent duplicate pricing for the same service/model/date
        UniqueConstraint(
            "service",
            "model",
            "effective_date",
            name="uq_model_pricing_service_model_date",
        ),
    )

    def __repr__(self) -> str:
        """String representation of the ModelPricing model."""
        return (
            f"<ModelPricing(service={self.service}, "
            f"model={self.model}, "
            f"input=${self.input_cost_per_million}/M, "
            f"output=${self.output_cost_per_million}/M, "
            f"effective={self.effective_date.date()})>"
        )

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate total cost for given token counts.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Total cost in USD
        """
        input_cost = (input_tokens / 1_000_000) * self.input_cost_per_million
        output_cost = (output_tokens / 1_000_000) * self.output_cost_per_million
        return input_cost + output_cost
