"""Add OurAirports fields to airports

Revision ID: 003
Revises: a085810eaf1d
Create Date: 2025-11-21 22:34:00.000000+00:00

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
    """Upgrade database schema."""
    # Add new fields from OurAirports dataset
    op.add_column(
        "airports",
        sa.Column(
            "country",
            sa.String(length=2),
            nullable=True,
            comment="ISO 3166-1 alpha-2 country code",
        ),
    )
    op.add_column(
        "airports",
        sa.Column(
            "latitude",
            sa.Numeric(precision=10, scale=6),
            nullable=True,
            comment="Latitude in decimal degrees",
        ),
    )
    op.add_column(
        "airports",
        sa.Column(
            "longitude",
            sa.Numeric(precision=10, scale=6),
            nullable=True,
            comment="Longitude in decimal degrees",
        ),
    )
    op.add_column(
        "airports",
        sa.Column(
            "timezone",
            sa.String(length=50),
            nullable=True,
            comment="IANA timezone identifier (e.g., Europe/Berlin)",
        ),
    )
    op.add_column(
        "airports",
        sa.Column(
            "icao_code",
            sa.String(length=4),
            nullable=True,
            comment="4-letter ICAO code",
        ),
    )
    op.add_column(
        "airports",
        sa.Column(
            "airport_type",
            sa.String(length=30),
            nullable=True,
            comment="Airport type: large_airport, medium_airport, etc.",
        ),
    )

    # Create indexes for new fields
    op.create_index(
        op.f("ix_airports_country"),
        "airports",
        ["country"],
        unique=False,
    )
    op.create_index(
        op.f("ix_airports_icao_code"),
        "airports",
        ["icao_code"],
        unique=False,
    )

    # Alter existing fields to be nullable (for imported airports)
    op.alter_column(
        "airports",
        "distance_from_home",
        existing_type=sa.INTEGER(),
        nullable=True,
        server_default="0",
        comment="Distance in kilometers from Munich home",
    )
    op.alter_column(
        "airports",
        "driving_time",
        existing_type=sa.INTEGER(),
        nullable=True,
        server_default="0",
        comment="Driving time in minutes from Munich home",
    )

    # Increase string field lengths for international airport names
    op.alter_column(
        "airports",
        "name",
        existing_type=sa.String(length=100),
        type_=sa.String(length=200),
        existing_nullable=False,
    )
    op.alter_column(
        "airports",
        "city",
        existing_type=sa.String(length=50),
        type_=sa.String(length=100),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade database schema."""
    # Restore field lengths
    op.alter_column(
        "airports",
        "city",
        existing_type=sa.String(length=100),
        type_=sa.String(length=50),
        existing_nullable=False,
    )
    op.alter_column(
        "airports",
        "name",
        existing_type=sa.String(length=200),
        type_=sa.String(length=100),
        existing_nullable=False,
    )

    # Restore nullable constraints
    op.alter_column(
        "airports",
        "driving_time",
        existing_type=sa.INTEGER(),
        nullable=False,
        server_default=None,
        comment="Driving time in minutes from Munich home",
    )
    op.alter_column(
        "airports",
        "distance_from_home",
        existing_type=sa.INTEGER(),
        nullable=False,
        server_default=None,
        comment="Distance in kilometers from Munich home",
    )

    # Drop indexes
    op.drop_index(op.f("ix_airports_icao_code"), table_name="airports")
    op.drop_index(op.f("ix_airports_country"), table_name="airports")

    # Drop new columns
    op.drop_column("airports", "airport_type")
    op.drop_column("airports", "icao_code")
    op.drop_column("airports", "timezone")
    op.drop_column("airports", "longitude")
    op.drop_column("airports", "latitude")
    op.drop_column("airports", "country")
