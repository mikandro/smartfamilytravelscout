"""add_model_pricing_table

Revision ID: 2924c2c01a59
Revises: a085810eaf1d
Create Date: 2025-11-21 22:19:08.415139+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2924c2c01a59"
down_revision: Union[str, None] = "a085810eaf1d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add model_pricing table for dynamic pricing configuration."""
    op.create_table(
        "model_pricing",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        # Service and model information
        sa.Column(
            "service",
            sa.String(length=50),
            nullable=False,
            comment="API service name (e.g., 'claude', 'openai')",
        ),
        sa.Column(
            "model",
            sa.String(length=100),
            nullable=False,
            comment="Model name (e.g., 'claude-sonnet-4-5-20250929')",
        ),
        # Pricing information (in USD)
        sa.Column(
            "input_cost_per_million",
            sa.Float(),
            nullable=False,
            comment="Cost per 1 million input tokens in USD",
        ),
        sa.Column(
            "output_cost_per_million",
            sa.Float(),
            nullable=False,
            comment="Cost per 1 million output tokens in USD",
        ),
        # Effective date for this pricing
        sa.Column(
            "effective_date",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Date when this pricing becomes effective",
        ),
        # Optional fields
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            server_default="USD",
            comment="Currency code (ISO 4217)",
        ),
        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
            comment="Additional notes about this pricing change",
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
        sa.UniqueConstraint(
            "service",
            "model",
            "effective_date",
            name="uq_model_pricing_service_model_date",
        ),
    )

    # Create indexes for efficient queries
    op.create_index(
        op.f("ix_model_pricing_id"), "model_pricing", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_model_pricing_service"), "model_pricing", ["service"], unique=False
    )
    op.create_index(
        op.f("ix_model_pricing_model"), "model_pricing", ["model"], unique=False
    )
    op.create_index(
        op.f("ix_model_pricing_effective_date"),
        "model_pricing",
        ["effective_date"],
        unique=False,
    )

    # Create composite index for efficient queries
    op.create_index(
        "ix_model_pricing_service_model_date",
        "model_pricing",
        ["service", "model", "effective_date"],
    )


def downgrade() -> None:
    """Remove model_pricing table."""
    # Drop indexes first
    op.drop_index("ix_model_pricing_service_model_date", table_name="model_pricing")
    op.drop_index(
        op.f("ix_model_pricing_effective_date"), table_name="model_pricing"
    )
    op.drop_index(op.f("ix_model_pricing_model"), table_name="model_pricing")
    op.drop_index(op.f("ix_model_pricing_service"), table_name="model_pricing")
    op.drop_index(op.f("ix_model_pricing_id"), table_name="model_pricing")

    # Drop table
    op.drop_table("model_pricing")
