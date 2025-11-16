"""initial schema with all tables

Revision ID: 001
Revises:
Create Date: 2025-11-16 08:05:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables with proper indexes and constraints."""

    # Create airports table
    op.create_table(
        'airports',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('iata_code', sa.String(length=3), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('city', sa.String(length=50), nullable=False),
        sa.Column('distance_from_home', sa.Integer(), nullable=False, comment='Distance in kilometers from Munich home'),
        sa.Column('driving_time', sa.Integer(), nullable=False, comment='Driving time in minutes from Munich home'),
        sa.Column('preferred_for', postgresql.ARRAY(sa.String()), nullable=True, comment="e.g., ['budget', 'direct_flights']"),
        sa.Column('parking_cost_per_day', sa.Numeric(precision=10, scale=2), nullable=True, comment='Parking cost in euros per day'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_airports_created_at'), 'airports', ['created_at'], unique=False)
    op.create_index(op.f('ix_airports_iata_code'), 'airports', ['iata_code'], unique=True)

    # Create accommodations table
    op.create_table(
        'accommodations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('destination_city', sa.String(length=100), nullable=False, comment="City name, e.g., 'Lisbon', 'Barcelona'"),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False, comment="e.g., 'hotel', 'airbnb', 'apartment'"),
        sa.Column('bedrooms', sa.Integer(), nullable=True),
        sa.Column('price_per_night', sa.Numeric(precision=10, scale=2), nullable=False, comment='Price in EUR per night'),
        sa.Column('family_friendly', sa.Boolean(), nullable=False),
        sa.Column('has_kitchen', sa.Boolean(), nullable=False),
        sa.Column('has_kids_club', sa.Boolean(), nullable=False),
        sa.Column('rating', sa.Numeric(precision=3, scale=1), nullable=True, comment='Rating from 0 to 10'),
        sa.Column('review_count', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(length=50), nullable=False, comment="e.g., 'booking.com', 'airbnb'"),
        sa.Column('url', sa.Text(), nullable=True),
        sa.Column('image_url', sa.Text(), nullable=True),
        sa.Column('scraped_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_accommodations_created_at'), 'accommodations', ['created_at'], unique=False)
    op.create_index(op.f('ix_accommodations_destination_city'), 'accommodations', ['destination_city'], unique=False)
    op.create_index(op.f('ix_accommodations_scraped_at'), 'accommodations', ['scraped_at'], unique=False)
    op.create_index(op.f('ix_accommodations_source'), 'accommodations', ['source'], unique=False)

    # Create events table
    op.create_table(
        'events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('destination_city', sa.String(length=100), nullable=False, comment="City name, e.g., 'Lisbon', 'Barcelona'"),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('event_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True, comment='For multi-day events'),
        sa.Column('category', sa.String(length=50), nullable=False, comment="e.g., 'family', 'parent_escape', 'cultural', 'outdoor'"),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price_range', sa.String(length=50), nullable=True, comment="e.g., 'free', '<€20', '€20-50', '€50+'"),
        sa.Column('source', sa.String(length=50), nullable=False, comment="e.g., 'eventbrite', 'tripadvisor', 'manual'"),
        sa.Column('url', sa.Text(), nullable=True),
        sa.Column('ai_relevance_score', sa.Numeric(precision=3, scale=1), nullable=True, comment='AI-generated relevance score from 0 to 10'),
        sa.Column('scraped_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_events_ai_relevance_score'), 'events', ['ai_relevance_score'], unique=False)
    op.create_index(op.f('ix_events_category'), 'events', ['category'], unique=False)
    op.create_index(op.f('ix_events_created_at'), 'events', ['created_at'], unique=False)
    op.create_index(op.f('ix_events_destination_city'), 'events', ['destination_city'], unique=False)
    op.create_index(op.f('ix_events_event_date'), 'events', ['event_date'], unique=False)
    op.create_index(op.f('ix_events_scraped_at'), 'events', ['scraped_at'], unique=False)

    # Create school_holidays table
    op.create_table(
        'school_holidays',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False, comment="e.g., 'Easter Break 2025', 'Summer Holiday 2025'"),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('holiday_type', sa.String(length=50), nullable=False, comment="'major' for long holidays, 'long_weekend' for short breaks"),
        sa.Column('region', sa.String(length=50), nullable=False, comment='School region'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_school_holidays_created_at'), 'school_holidays', ['created_at'], unique=False)
    op.create_index(op.f('ix_school_holidays_end_date'), 'school_holidays', ['end_date'], unique=False)
    op.create_index(op.f('ix_school_holidays_start_date'), 'school_holidays', ['start_date'], unique=False)
    op.create_index(op.f('ix_school_holidays_year'), 'school_holidays', ['year'], unique=False)

    # Create user_preferences table
    op.create_table(
        'user_preferences',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False, comment='For future multi-user support'),
        sa.Column('max_flight_price_family', sa.Numeric(precision=10, scale=2), nullable=False, comment='Maximum flight price per person for family trips'),
        sa.Column('max_flight_price_parents', sa.Numeric(precision=10, scale=2), nullable=False, comment='Maximum flight price per person for parent escapes'),
        sa.Column('max_total_budget_family', sa.Numeric(precision=10, scale=2), nullable=False, comment='Maximum total budget for family trips'),
        sa.Column('preferred_destinations', postgresql.ARRAY(sa.String()), nullable=True, comment="List of preferred cities, e.g., ['Lisbon', 'Barcelona']"),
        sa.Column('avoid_destinations', postgresql.ARRAY(sa.String()), nullable=True, comment='List of cities to avoid'),
        sa.Column('interests', postgresql.ARRAY(sa.String()), nullable=True, comment="List of interests, e.g., ['wine', 'museums', 'beaches', 'hiking']"),
        sa.Column('notification_threshold', sa.Numeric(precision=5, scale=2), nullable=False, comment='Minimum AI score to trigger notifications'),
        sa.Column('parent_escape_frequency', sa.String(length=20), nullable=False, comment="How often to suggest parent escapes: 'monthly', 'quarterly', 'semi-annual'"),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_preferences_created_at'), 'user_preferences', ['created_at'], unique=False)
    op.create_index(op.f('ix_user_preferences_user_id'), 'user_preferences', ['user_id'], unique=False)

    # Create price_history table
    op.create_table(
        'price_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('route', sa.String(length=10), nullable=False, comment="Route code, e.g., 'MUC-LIS'"),
        sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=False, comment='Price in EUR'),
        sa.Column('source', sa.String(length=50), nullable=False, comment="e.g., 'kiwi', 'skyscanner'"),
        sa.Column('scraped_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_price_history_created_at'), 'price_history', ['created_at'], unique=False)
    op.create_index(op.f('ix_price_history_route'), 'price_history', ['route'], unique=False)
    op.create_index(op.f('ix_price_history_scraped_at'), 'price_history', ['scraped_at'], unique=False)
    op.create_index(op.f('ix_price_history_source'), 'price_history', ['source'], unique=False)

    # Create scraping_jobs table
    op.create_table(
        'scraping_jobs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('job_type', sa.String(length=50), nullable=False, comment="e.g., 'flights', 'accommodations', 'events'"),
        sa.Column('source', sa.String(length=50), nullable=False, comment='Source website or API'),
        sa.Column('status', sa.String(length=20), nullable=False, comment="'running', 'completed', 'failed'"),
        sa.Column('items_scraped', sa.Integer(), nullable=False, comment='Number of items successfully scraped'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scraping_jobs_completed_at'), 'scraping_jobs', ['completed_at'], unique=False)
    op.create_index(op.f('ix_scraping_jobs_job_type'), 'scraping_jobs', ['job_type'], unique=False)
    op.create_index(op.f('ix_scraping_jobs_source'), 'scraping_jobs', ['source'], unique=False)
    op.create_index(op.f('ix_scraping_jobs_started_at'), 'scraping_jobs', ['started_at'], unique=False)
    op.create_index(op.f('ix_scraping_jobs_status'), 'scraping_jobs', ['status'], unique=False)

    # Create flights table (depends on airports)
    op.create_table(
        'flights',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('origin_airport_id', sa.Integer(), nullable=False),
        sa.Column('destination_airport_id', sa.Integer(), nullable=False),
        sa.Column('airline', sa.String(length=50), nullable=False),
        sa.Column('departure_date', sa.Date(), nullable=False),
        sa.Column('departure_time', sa.Time(), nullable=True),
        sa.Column('return_date', sa.Date(), nullable=True),
        sa.Column('return_time', sa.Time(), nullable=True),
        sa.Column('price_per_person', sa.Numeric(precision=10, scale=2), nullable=False, comment='Price in EUR per person'),
        sa.Column('total_price', sa.Numeric(precision=10, scale=2), nullable=False, comment='Total price for 4 people in EUR'),
        sa.Column('true_cost', sa.Numeric(precision=10, scale=2), nullable=True, comment='True cost including airport costs (calculated later)'),
        sa.Column('booking_class', sa.String(length=20), nullable=True, comment='e.g., Economy, Premium Economy'),
        sa.Column('direct_flight', sa.Boolean(), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False, comment="e.g., kiwi, skyscanner, ryanair"),
        sa.Column('booking_url', sa.Text(), nullable=True),
        sa.Column('scraped_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['destination_airport_id'], ['airports.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['origin_airport_id'], ['airports.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_flights_created_at'), 'flights', ['created_at'], unique=False)
    op.create_index(op.f('ix_flights_departure_date'), 'flights', ['departure_date'], unique=False)
    op.create_index(op.f('ix_flights_destination_airport_id'), 'flights', ['destination_airport_id'], unique=False)
    op.create_index(op.f('ix_flights_origin_airport_id'), 'flights', ['origin_airport_id'], unique=False)
    op.create_index(op.f('ix_flights_return_date'), 'flights', ['return_date'], unique=False)
    op.create_index(op.f('ix_flights_scraped_at'), 'flights', ['scraped_at'], unique=False)
    op.create_index(op.f('ix_flights_source'), 'flights', ['source'], unique=False)

    # Create trip_packages table (depends on accommodations)
    op.create_table(
        'trip_packages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('package_type', sa.String(length=50), nullable=False, comment="'family' or 'parent_escape'"),
        sa.Column('flights_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment='Array of flight IDs or full flight data'),
        sa.Column('accommodation_id', sa.Integer(), nullable=True),
        sa.Column('events_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Array of event IDs or full event data'),
        sa.Column('destination_city', sa.String(length=100), nullable=False, comment='Primary destination city'),
        sa.Column('departure_date', sa.Date(), nullable=False),
        sa.Column('return_date', sa.Date(), nullable=False),
        sa.Column('num_nights', sa.Integer(), nullable=False),
        sa.Column('total_price', sa.Numeric(precision=10, scale=2), nullable=False, comment='Total package price in EUR'),
        sa.Column('ai_score', sa.Numeric(precision=5, scale=2), nullable=True, comment='AI-generated score from 0 to 100'),
        sa.Column('ai_reasoning', sa.Text(), nullable=True, comment='AI explanation for the score and package recommendation'),
        sa.Column('itinerary_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Day-by-day itinerary suggested by AI'),
        sa.Column('notified', sa.Boolean(), nullable=False, comment='Whether user has been notified'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['accommodation_id'], ['accommodations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_trip_packages_ai_score'), 'trip_packages', ['ai_score'], unique=False)
    op.create_index(op.f('ix_trip_packages_created_at'), 'trip_packages', ['created_at'], unique=False)
    op.create_index(op.f('ix_trip_packages_departure_date'), 'trip_packages', ['departure_date'], unique=False)
    op.create_index(op.f('ix_trip_packages_destination_city'), 'trip_packages', ['destination_city'], unique=False)
    op.create_index(op.f('ix_trip_packages_package_type'), 'trip_packages', ['package_type'], unique=False)
    op.create_index(op.f('ix_trip_packages_return_date'), 'trip_packages', ['return_date'], unique=False)


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table('trip_packages')
    op.drop_table('flights')
    op.drop_table('scraping_jobs')
    op.drop_table('price_history')
    op.drop_table('user_preferences')
    op.drop_table('school_holidays')
    op.drop_table('events')
    op.drop_table('accommodations')
    op.drop_table('airports')
