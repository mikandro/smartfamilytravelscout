"""add_composite_indexes_for_performance

Revision ID: 9b2c6de58e84
Revises: a085810eaf1d
Create Date: 2025-11-21 22:21:36.878475+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9b2c6de58e84"
down_revision: Union[str, None] = "a085810eaf1d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add composite indexes for improved query performance."""
    # Composite index for flight route queries (origin + destination + date)
    # Improves queries like: WHERE origin_airport_id = ? AND destination_airport_id = ? AND departure_date = ?
    op.create_index(
        "ix_flights_route_date",
        "flights",
        ["origin_airport_id", "destination_airport_id", "departure_date"],
        unique=False,
    )

    # Composite index for trip package scoring queries (ai_score DESC + departure_date)
    # Improves queries like: ORDER BY ai_score DESC WHERE departure_date >= ?
    op.create_index(
        "ix_trip_packages_score_date",
        "trip_packages",
        [sa.text("ai_score DESC"), "departure_date"],
        unique=False,
    )


def downgrade() -> None:
    """Remove composite indexes."""
    op.drop_index("ix_trip_packages_score_date", table_name="trip_packages")
    op.drop_index("ix_flights_route_date", table_name="flights")
