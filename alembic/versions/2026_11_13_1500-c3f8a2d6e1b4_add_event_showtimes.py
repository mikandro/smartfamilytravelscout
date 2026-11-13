"""Add showtimes to events (for locally scraped, dated events)

Revision ID: c3f8a2d6e1b4
Revises: b7e4c1a9d2f0
Create Date: 2026-11-13 15:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c3f8a2d6e1b4"
down_revision: Union[str, None] = "b7e4c1a9d2f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the showtimes column."""
    op.add_column(
        "events",
        sa.Column(
            "showtimes",
            postgresql.ARRAY(sa.String()),
            nullable=True,
            comment="Start (and end) times on event_date, 'HH:MM' or 'HH:MM-HH:MM'",
        ),
    )


def downgrade() -> None:
    """Remove the showtimes column."""
    op.drop_column("events", "showtimes")
