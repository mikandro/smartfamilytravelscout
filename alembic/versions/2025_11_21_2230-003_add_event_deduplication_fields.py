"""Add venue and deduplication_hash to events for cross-source deduplication

Revision ID: 003
Revises: a085810eaf1d
Create Date: 2025-11-21 22:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "a085810eaf1d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add venue and deduplication_hash columns to events table."""

    # Add venue column
    op.add_column(
        "events",
        sa.Column(
            "venue",
            sa.String(length=200),
            nullable=True,
            comment="Event venue or location name"
        )
    )

    # Add deduplication_hash column
    op.add_column(
        "events",
        sa.Column(
            "deduplication_hash",
            sa.String(length=64),
            nullable=True,
            comment="Hash for deduplication based on title, venue, and date"
        )
    )

    # Create index on deduplication_hash for fast lookups
    op.create_index(
        op.f("ix_events_deduplication_hash"),
        "events",
        ["deduplication_hash"],
        unique=False
    )


def downgrade() -> None:
    """Remove venue and deduplication_hash columns from events table."""

    # Drop index first
    op.drop_index(op.f("ix_events_deduplication_hash"), table_name="events")

    # Drop columns
    op.drop_column("events", "deduplication_hash")
    op.drop_column("events", "venue")
