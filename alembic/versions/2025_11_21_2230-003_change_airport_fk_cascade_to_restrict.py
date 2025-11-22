"""Change airport foreign keys from CASCADE to RESTRICT

Revision ID: 003
Revises: a085810eaf1d
Create Date: 2025-11-21 22:30:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "a085810eaf1d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema: Change CASCADE to RESTRICT on airport foreign keys."""
    # Drop existing foreign key constraints on flights table
    op.drop_constraint(
        "flights_origin_airport_id_fkey", "flights", type_="foreignkey"
    )
    op.drop_constraint(
        "flights_destination_airport_id_fkey", "flights", type_="foreignkey"
    )

    # Recreate foreign key constraints with RESTRICT
    op.create_foreign_key(
        "flights_origin_airport_id_fkey",
        "flights",
        "airports",
        ["origin_airport_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "flights_destination_airport_id_fkey",
        "flights",
        "airports",
        ["destination_airport_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    """Downgrade database schema: Revert RESTRICT back to CASCADE."""
    # Drop RESTRICT foreign key constraints
    op.drop_constraint(
        "flights_origin_airport_id_fkey", "flights", type_="foreignkey"
    )
    op.drop_constraint(
        "flights_destination_airport_id_fkey", "flights", type_="foreignkey"
    )

    # Recreate foreign key constraints with CASCADE (original behavior)
    op.create_foreign_key(
        "flights_origin_airport_id_fkey",
        "flights",
        "airports",
        ["origin_airport_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "flights_destination_airport_id_fkey",
        "flights",
        "airports",
        ["destination_airport_id"],
        ["id"],
        ondelete="CASCADE",
    )
