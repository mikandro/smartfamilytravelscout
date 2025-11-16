"""
API cost tracking model for monitoring AI service usage and costs.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ApiCost(Base, TimestampMixin):
    """
    Track API costs for various services (Claude, OpenAI, etc.).

    This model records token usage and associated costs for API calls
    to enable cost monitoring, budgeting, and optimization.
    """

    __tablename__ = "api_costs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Service information
    service: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="API service name (e.g., 'claude', 'openai')",
    )

    model: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Model name (e.g., 'claude-sonnet-4-5-20250929')",
    )

    # Usage metrics
    input_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of input tokens consumed",
    )

    output_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of output tokens generated",
    )

    # Cost tracking
    cost_usd: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Total cost in USD",
    )

    # Context information
    operation: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Operation type (e.g., 'deal_scoring', 'itinerary_generation')",
    )

    prompt_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="Hash of the prompt for deduplication tracking",
    )

    # Metadata
    cache_hit: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        comment="Whether this was a cache hit (no actual API call)",
    )

    error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if the API call failed",
    )

    # Additional metadata (JSON in string format)
    metadata: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Additional metadata as JSON string",
    )

    # Composite indexes for common queries
    __table_args__ = (
        Index("ix_api_costs_service_created", "service", "created_at"),
        Index("ix_api_costs_operation_created", "operation", "created_at"),
        Index("ix_api_costs_model_created", "model", "created_at"),
    )

    def __repr__(self) -> str:
        """String representation of the ApiCost model."""
        return (
            f"<ApiCost(service={self.service}, "
            f"model={self.model}, "
            f"cost=${self.cost_usd:.4f}, "
            f"tokens={self.input_tokens + self.output_tokens})>"
        )

    @property
    def total_tokens(self) -> int:
        """Calculate total tokens (input + output)."""
        return self.input_tokens + self.output_tokens

    @property
    def cost_per_token(self) -> float:
        """Calculate cost per token."""
        if self.total_tokens == 0:
            return 0.0
        return self.cost_usd / self.total_tokens
