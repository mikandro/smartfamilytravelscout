"""
Seed data script for initial database population.
Populates airports, school holidays, and default user preferences.
"""

import logging
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Airport, SchoolHoliday, UserPreference

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


def seed_school_holidays(db: Session, regions: list[str] | None = None) -> None:
    """
    Seed school holidays for German states (2025-2026).

    Args:
        db: Database session
        regions: List of specific regions to seed. If None, seeds all 16 German states.
                 Examples: ["Bavaria"], ["Bavaria", "Berlin"], or None for all.

    Examples:
        # Seed all regions
        seed_school_holidays(db)

        # Seed only Bavaria
        seed_school_holidays(db, regions=["Bavaria"])

        # Seed multiple regions
        seed_school_holidays(db, regions=["Bavaria", "Berlin", "Hamburg"])
    """
    from app.utils.german_school_holidays import GERMAN_HOLIDAYS_2025_2026, get_all_regions

    # If no regions specified, seed all
    if regions is None:
        regions = get_all_regions()

    total_added = 0
    total_skipped = 0

    for region in regions:
        if region not in GERMAN_HOLIDAYS_2025_2026:
            logger.warning(f"Region '{region}' not found in holiday data, skipping")
            continue

        logger.info(f"Seeding holidays for {region}...")
        holidays = GERMAN_HOLIDAYS_2025_2026[region]

        for holiday in holidays:
            # Check if holiday already exists for this region
            existing = (
                db.query(SchoolHoliday)
                .filter_by(
                    name=holiday.name,
                    start_date=holiday.start_date,
                    region=holiday.region
                )
                .first()
            )
            if existing:
                logger.debug(f"Holiday {holiday.name} ({region}) already exists, skipping")
                total_skipped += 1
                continue

            # Create holiday record
            holiday_record = SchoolHoliday(
                name=holiday.name,
                start_date=holiday.start_date,
                end_date=holiday.end_date,
                year=holiday.start_date.year,
                holiday_type=holiday.holiday_type,
                region=holiday.region,
            )
            db.add(holiday_record)
            logger.info(
                f"Created holiday: {holiday.name} ({region}) "
                f"({holiday.start_date} to {holiday.end_date})"
            )
            total_added += 1

    db.commit()
    logger.info(
        f"School holiday seeding completed: {total_added} added, "
        f"{total_skipped} skipped across {len(regions)} region(s)"
    )


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
