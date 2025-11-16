"""Add ApiCost model for AI service cost tracking

Revision ID: 002
Revises: 001
Create Date: 2025-11-16 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add api_costs table for tracking AI API usage and costs."""

    op.create_table(
        "api_costs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        # Service information
        sa.Column(
            "service",
            sa.String(length=50),
            nullable=False,
            comment="API service name (e.g., 'claude', 'openai')",
        ),
        sa.Column(
            "model",
            sa.String(length=100),
            nullable=True,
            comment="Model name (e.g., 'claude-sonnet-4-5-20250929')",
        ),
        # Usage metrics
        sa.Column(
            "input_tokens",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Number of input tokens consumed",
        ),
        sa.Column(
            "output_tokens",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Number of output tokens generated",
        ),
        # Cost tracking
        sa.Column(
            "cost_usd",
            sa.Float(),
            nullable=False,
            comment="Total cost in USD",
        ),
        # Context information
        sa.Column(
            "operation",
            sa.String(length=100),
            nullable=True,
            comment="Operation type (e.g., 'deal_scoring', 'itinerary_generation')",
        ),
        sa.Column(
            "prompt_hash",
            sa.String(length=64),
            nullable=True,
            comment="Hash of the prompt for deduplication tracking",
        ),
        # Metadata
        sa.Column(
            "cache_hit",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Whether this was a cache hit (no actual API call)",
        ),
        sa.Column(
            "error",
            sa.Text(),
            nullable=True,
            comment="Error message if the API call failed",
        ),
        sa.Column(
            "metadata",
            sa.Text(),
            nullable=True,
            comment="Additional metadata as JSON string",
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for common queries
    op.create_index(
        op.f("ix_api_costs_id"), "api_costs", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_api_costs_service"), "api_costs", ["service"], unique=False
    )
    op.create_index(
        op.f("ix_api_costs_prompt_hash"), "api_costs", ["prompt_hash"], unique=False
    )
    op.create_index(
        op.f("ix_api_costs_created_at"), "api_costs", ["created_at"], unique=False
    )

    # Create composite indexes for common query patterns
    op.create_index(
        "ix_api_costs_service_created", "api_costs", ["service", "created_at"]
    )
    op.create_index(
        "ix_api_costs_operation_created", "api_costs", ["operation", "created_at"]
    )
    op.create_index(
        "ix_api_costs_model_created", "api_costs", ["model", "created_at"]
    )


def downgrade() -> None:
    """Remove api_costs table."""

    # Drop indexes first
    op.drop_index("ix_api_costs_model_created", table_name="api_costs")
    op.drop_index("ix_api_costs_operation_created", table_name="api_costs")
    op.drop_index("ix_api_costs_service_created", table_name="api_costs")
    op.drop_index(op.f("ix_api_costs_created_at"), table_name="api_costs")
    op.drop_index(op.f("ix_api_costs_prompt_hash"), table_name="api_costs")
    op.drop_index(op.f("ix_api_costs_service"), table_name="api_costs")
    op.drop_index(op.f("ix_api_costs_id"), table_name="api_costs")

    # Drop table
    op.drop_table("api_costs")
