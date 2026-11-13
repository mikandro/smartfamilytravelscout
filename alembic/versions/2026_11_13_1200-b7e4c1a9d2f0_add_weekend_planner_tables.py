"""Add weekend planner tables (places, place_visits, weekend_plans)

Revision ID: b7e4c1a9d2f0
Revises: a085810eaf1d
Create Date: 2026-11-13 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b7e4c1a9d2f0"
down_revision: Union[str, None] = "a085810eaf1d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps() -> list:
    return [
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
    ]


def upgrade() -> None:
    """Create the weekend planner tables."""
    op.create_table(
        "places",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "category",
            sa.String(length=50),
            nullable=False,
            comment="e.g. 'museum', 'zoo', 'pool', 'playground', 'lake', 'hike'",
        ),
        sa.Column(
            "setting",
            sa.String(length=10),
            nullable=False,
            comment="'indoor', 'outdoor' or 'mixed'",
        ),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column(
            "drive_minutes",
            sa.Integer(),
            nullable=False,
            comment="Estimated one-way drive from home",
        ),
        sa.Column(
            "transit_minutes",
            sa.Integer(),
            nullable=True,
            comment="One-way by S-Bahn/U-Bahn/tram incl. walk; NULL = car only",
        ),
        sa.Column(
            "transit_note",
            sa.String(length=200),
            nullable=True,
            comment="e.g. 'S2 to Poing, 10 min walk'",
        ),
        sa.Column("age_min", sa.Integer(), nullable=False),
        sa.Column(
            "age_max",
            sa.Integer(),
            nullable=True,
            comment="Oldest age that still enjoys it; NULL = no limit",
        ),
        sa.Column("stroller_friendly", sa.Boolean(), nullable=False),
        sa.Column("duration_hours", sa.Float(), nullable=False, comment="Typical visit length"),
        sa.Column(
            "cost_family_eur",
            sa.Integer(),
            nullable=True,
            comment="Rough entry cost for 2 adults + 2 kids; 0 = free",
        ),
        sa.Column("booking_required", sa.Boolean(), nullable=False),
        sa.Column(
            "months_open",
            postgresql.ARRAY(sa.Integer()),
            nullable=True,
            comment="Months (1-12) it is worth going; NULL = all year",
        ),
        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
            comment="Why it works (or what to watch for) with these kids",
        ),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_places_slug", "places", ["slug"], unique=True)
    op.create_index("ix_places_category", "places", ["category"])
    op.create_index("ix_places_setting", "places", ["setting"])
    op.create_index("ix_places_drive_minutes", "places", ["drive_minutes"])
    op.create_index("ix_places_created_at", "places", ["created_at"])

    op.create_table(
        "place_visits",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("place_id", sa.Integer(), nullable=False),
        sa.Column("visited_on", sa.Date(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True, comment="1-5"),
        sa.Column("comment", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_place_visits_place_id", "place_visits", ["place_id"])
    op.create_index("ix_place_visits_visited_on", "place_visits", ["visited_on"])
    op.create_index("ix_place_visits_created_at", "place_visits", ["created_at"])

    op.create_table(
        "weekend_plans",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("weekend_start", sa.Date(), nullable=False, comment="The Saturday"),
        sa.Column("forecast_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("plan_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_weekend_plans_weekend_start", "weekend_plans", ["weekend_start"], unique=True
    )
    op.create_index("ix_weekend_plans_created_at", "weekend_plans", ["created_at"])


def downgrade() -> None:
    """Drop the weekend planner tables."""
    op.drop_table("weekend_plans")
    op.drop_table("place_visits")
    op.drop_table("places")
