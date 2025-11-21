"""
Seed data script for initial database population.
Populates airports, school holidays, and default user preferences.
"""

import logging
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Airport, ModelPricing, SchoolHoliday, UserPreference

logger = logging.getLogger(__name__)


def seed_airports(db: Session) -> None:
    """
    Seed airport data for Munich area airports.
    Includes distance, driving time, and parking costs.
    """
    airports_data = [
        {
            "iata_code": "MUC",
            "name": "Munich Airport",
            "city": "Munich",
            "distance_from_home": 20,
            "driving_time": 25,
            "preferred_for": ["direct_flights", "international"],
            "parking_cost_per_day": Decimal("15.00"),
            "is_origin": True,
            "is_destination": False,
        },
        {
            "iata_code": "FMM",
            "name": "Memmingen Airport",
            "city": "Memmingen",
            "distance_from_home": 110,
            "driving_time": 70,
            "preferred_for": ["budget", "ryanair"],
            "parking_cost_per_day": Decimal("5.00"),
            "is_origin": True,
            "is_destination": False,
        },
        {
            "iata_code": "NUE",
            "name": "Nuremberg Airport",
            "city": "Nuremberg",
            "distance_from_home": 170,
            "driving_time": 110,
            "preferred_for": ["alternative"],
            "parking_cost_per_day": Decimal("10.00"),
            "is_origin": True,
            "is_destination": False,
        },
        {
            "iata_code": "SZG",
            "name": "Salzburg Airport",
            "city": "Salzburg",
            "distance_from_home": 150,
            "driving_time": 90,
            "preferred_for": ["austria", "scenic"],
            "parking_cost_per_day": Decimal("12.00"),
            "is_origin": True,
            "is_destination": False,
        },
        # Destination airports (popular European cities)
        {
            "iata_code": "LIS",
            "name": "Lisbon Airport",
            "city": "Lisbon",
            "distance_from_home": 0,
            "driving_time": 0,
            "preferred_for": [],
            "parking_cost_per_day": Decimal("0.00"),
            "is_origin": False,
            "is_destination": True,
        },
        {
            "iata_code": "BCN",
            "name": "Barcelona Airport",
            "city": "Barcelona",
            "distance_from_home": 0,
            "driving_time": 0,
            "preferred_for": [],
            "parking_cost_per_day": Decimal("0.00"),
            "is_origin": False,
            "is_destination": True,
        },
        {
            "iata_code": "PRG",
            "name": "Prague Airport",
            "city": "Prague",
            "distance_from_home": 0,
            "driving_time": 0,
            "preferred_for": [],
            "parking_cost_per_day": Decimal("0.00"),
            "is_origin": False,
            "is_destination": True,
        },
        {
            "iata_code": "OPO",
            "name": "Porto Airport",
            "city": "Porto",
            "distance_from_home": 0,
            "driving_time": 0,
            "preferred_for": [],
            "parking_cost_per_day": Decimal("0.00"),
            "is_origin": False,
            "is_destination": True,
        },
    ]

    for airport_data in airports_data:
        # Check if airport already exists
        existing = db.query(Airport).filter_by(iata_code=airport_data["iata_code"]).first()
        if existing:
            logger.info(f"Airport {airport_data['iata_code']} already exists, skipping")
            continue

        airport = Airport(**airport_data)
        db.add(airport)
        logger.info(f"Created airport: {airport_data['iata_code']} - {airport_data['name']}")

    db.commit()
    logger.info("Airport seeding completed")


def seed_school_holidays(db: Session) -> None:
    """
    Seed Bavaria school holidays for 2025-2026.
    Includes major holidays and long weekends.
    """
    holidays_data = [
        # 2025 holidays
        {
            "name": "Easter Break 2025",
            "start_date": date(2025, 4, 14),
            "end_date": date(2025, 4, 25),
            "year": 2025,
            "holiday_type": "major",
            "region": "Bavaria",
        },
        {
            "name": "Whitsun Break 2025",
            "start_date": date(2025, 6, 10),
            "end_date": date(2025, 6, 20),
            "year": 2025,
            "holiday_type": "major",
            "region": "Bavaria",
        },
        {
            "name": "Summer Holiday 2025",
            "start_date": date(2025, 8, 1),
            "end_date": date(2025, 9, 15),
            "year": 2025,
            "holiday_type": "major",
            "region": "Bavaria",
        },
        {
            "name": "Autumn Break 2025",
            "start_date": date(2025, 10, 27),
            "end_date": date(2025, 11, 7),
            "year": 2025,
            "holiday_type": "major",
            "region": "Bavaria",
        },
        {
            "name": "Christmas Break 2025/2026",
            "start_date": date(2025, 12, 22),
            "end_date": date(2026, 1, 10),
            "year": 2025,
            "holiday_type": "major",
            "region": "Bavaria",
        },
        # 2026 holidays
        {
            "name": "Winter Break 2026",
            "start_date": date(2026, 2, 16),
            "end_date": date(2026, 2, 20),
            "year": 2026,
            "holiday_type": "long_weekend",
            "region": "Bavaria",
        },
        {
            "name": "Easter Break 2026",
            "start_date": date(2026, 3, 30),
            "end_date": date(2026, 4, 10),
            "year": 2026,
            "holiday_type": "major",
            "region": "Bavaria",
        },
        {
            "name": "Whitsun Break 2026",
            "start_date": date(2026, 5, 26),
            "end_date": date(2026, 6, 5),
            "year": 2026,
            "holiday_type": "major",
            "region": "Bavaria",
        },
    ]

    for holiday_data in holidays_data:
        # Check if holiday already exists
        existing = (
            db.query(SchoolHoliday)
            .filter_by(name=holiday_data["name"], start_date=holiday_data["start_date"])
            .first()
        )
        if existing:
            logger.info(f"Holiday {holiday_data['name']} already exists, skipping")
            continue

        holiday = SchoolHoliday(**holiday_data)
        db.add(holiday)
        logger.info(
            f"Created holiday: {holiday_data['name']} "
            f"({holiday_data['start_date']} to {holiday_data['end_date']})"
        )

    db.commit()
    logger.info("School holiday seeding completed")


def seed_model_pricing(db: Session) -> None:
    """
    Seed model pricing data for AI services.
    Includes current Claude pricing (as of November 2025).
    """
    pricing_data = [
        {
            "service": "claude",
            "model": "claude-sonnet-4-5-20250929",
            "input_cost_per_million": 3.0,
            "output_cost_per_million": 15.0,
            "effective_date": datetime(2025, 11, 1, 0, 0, 0),
            "currency": "USD",
            "notes": "Claude Sonnet 4.5 pricing as of November 2025",
        },
        {
            "service": "claude",
            "model": "claude-3-5-sonnet-20241022",
            "input_cost_per_million": 3.0,
            "output_cost_per_million": 15.0,
            "effective_date": datetime(2024, 10, 1, 0, 0, 0),
            "currency": "USD",
            "notes": "Claude 3.5 Sonnet pricing (legacy model)",
        },
        {
            "service": "claude",
            "model": "claude-3-opus-20240229",
            "input_cost_per_million": 15.0,
            "output_cost_per_million": 75.0,
            "effective_date": datetime(2024, 3, 1, 0, 0, 0),
            "currency": "USD",
            "notes": "Claude 3 Opus pricing (legacy model)",
        },
        {
            "service": "claude",
            "model": "claude-3-haiku-20240307",
            "input_cost_per_million": 0.25,
            "output_cost_per_million": 1.25,
            "effective_date": datetime(2024, 3, 1, 0, 0, 0),
            "currency": "USD",
            "notes": "Claude 3 Haiku pricing (legacy model)",
        },
    ]

    for pricing in pricing_data:
        # Check if pricing already exists for this service/model/date
        existing = (
            db.query(ModelPricing)
            .filter_by(
                service=pricing["service"],
                model=pricing["model"],
                effective_date=pricing["effective_date"],
            )
            .first()
        )
        if existing:
            logger.info(
                f"Pricing for {pricing['service']}/{pricing['model']} "
                f"(effective {pricing['effective_date'].date()}) already exists, skipping"
            )
            continue

        model_pricing = ModelPricing(**pricing)
        db.add(model_pricing)
        logger.info(
            f"Created pricing: {pricing['service']}/{pricing['model']} - "
            f"${pricing['input_cost_per_million']}/M input, "
            f"${pricing['output_cost_per_million']}/M output "
            f"(effective {pricing['effective_date'].date()})"
        )

    db.commit()
    logger.info("Model pricing seeding completed")


def seed_user_preferences(db: Session) -> None:
    """
    Seed default user preferences.
    Creates a default preference set for user_id=1.
    """
    # Check if preferences already exist for user_id=1
    existing = db.query(UserPreference).filter_by(user_id=1).first()
    if existing:
        logger.info("Default user preferences already exist, skipping")
        return

    preferences = UserPreference(
        user_id=1,
        max_flight_price_family=Decimal("200.00"),
        max_flight_price_parents=Decimal("250.00"),
        max_total_budget_family=Decimal("2000.00"),
        preferred_destinations=["Lisbon", "Barcelona", "Prague", "Porto"],
        avoid_destinations=[],
        interests=["wine", "museums", "beaches", "family_activities"],
        notification_threshold=Decimal("70.00"),
        parent_escape_frequency="quarterly",
    )

    db.add(preferences)
    db.commit()
    logger.info("Default user preferences created successfully")


def seed_all(db: Session) -> None:
    """
    Run all seeding functions.

    Args:
        db: SQLAlchemy database session

    Usage:
        from app.database import get_sync_session
        from app.utils.seed_data import seed_all

        db = get_sync_session()
        try:
            seed_all(db)
        finally:
            db.close()
    """
    logger.info("Starting database seeding...")

    seed_airports(db)
    seed_school_holidays(db)
    seed_model_pricing(db)
    seed_user_preferences(db)

    logger.info("Database seeding completed successfully!")


if __name__ == "__main__":
    """Run seeding when script is executed directly."""
    import sys

    # Add parent directory to path for imports
    sys.path.insert(0, "/home/user/smartfamilytravelscout")

    from app.database import get_sync_session

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    db = get_sync_session()
    try:
        seed_all(db)
    except Exception as e:
        logger.error(f"Error during seeding: {e}")
        db.rollback()
        raise
    finally:
        db.close()
