"""Add accommodation scoring fields

Revision ID: 003
Revises: a085810eaf1d
Create Date: 2025-11-21 22:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "a085810eaf1d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add accommodation scoring fields for price comparison and quality assessment."""

    # Add accommodation_score field
    op.add_column(
        "accommodations",
        sa.Column(
            "accommodation_score",
            sa.Numeric(precision=5, scale=2),
            nullable=True,
            comment="AI-generated accommodation score from 0 to 100",
        ),
    )

    # Add accommodation_score_details field (JSONB)
    op.add_column(
        "accommodations",
        sa.Column(
            "accommodation_score_details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Detailed scoring breakdown (price-quality, family-suitability, etc.)",
        ),
    )

    # Create index on accommodation_score for efficient filtering/sorting
    op.create_index(
        op.f("ix_accommodations_accommodation_score"),
        "accommodations",
        ["accommodation_score"],
        unique=False,
    )


def downgrade() -> None:
    """Remove accommodation scoring fields."""

    # Drop index first
    op.drop_index(
        op.f("ix_accommodations_accommodation_score"), table_name="accommodations"
    )

    # Drop columns
    op.drop_column("accommodations", "accommodation_score_details")
    op.drop_column("accommodations", "accommodation_score")
