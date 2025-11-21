"""
Scheduled Celery tasks for automated operations.
"""

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import and_, select

from app.config import settings
from app.database import get_sync_session
from app.models.accommodation import Accommodation
from app.models.event import Event
from app.models.flight import Flight
from app.models.price_history import PriceHistory
from app.models.scraping_job import ScrapingJob
from app.models.trip_package import TripPackage
from app.models.user_preference import UserPreference
from app.notifications.email_sender import create_email_notifier
from app.orchestration.flight_orchestrator import FlightOrchestrator
from app.scrapers.airbnb_scraper import AirbnbScraper
from app.scrapers.barcelona_scraper import BarcelonaScraper
from app.scrapers.booking_scraper import BookingScraper
from app.scrapers.eventbrite_scraper import EventbriteScraper
from app.scrapers.lisbon_scraper import LisbonScraper
from app.scrapers.prague_scraper import PragueScraper
from app.tasks.celery_app import celery_app
from app.utils.date_utils import get_school_holiday_periods

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.scheduled_tasks.daily_flight_search", bind=True)
def daily_flight_search(self):
    """
    Daily task to search for flight deals.

    Runs every day at 6 AM UTC.
    Searches for flights from configured departure airports to popular destinations
    during upcoming school holiday periods.
    """
    logger.info("Starting daily flight search task")

    try:
        # Get departure airports from settings
        origin_airports = settings.get_departure_airports_list()
        logger.info(f"Searching flights from airports: {origin_airports}")

        # Popular family destinations
        destination_airports = ["LIS", "BCN", "PRG", "OPO", "AGP", "PMI", "FAO"]

        # Get upcoming school holiday periods (next 6 months)
        holiday_periods = get_school_holiday_periods(
            start_date=datetime.now().date(),
            end_date=(datetime.now() + timedelta(days=180)).date()
        )

        logger.info(f"Found {len(holiday_periods)} school holiday periods in next 6 months")

        if not holiday_periods:
            logger.warning("No school holidays found, using default date ranges")
            # Fallback: search for weekends in the next 2 months
            start_date = datetime.now().date() + timedelta(days=7)
            holiday_periods = [(start_date, start_date + timedelta(days=7))]

        # Use FlightOrchestrator to scrape all sources
        orchestrator = FlightOrchestrator()

        # Run async scraping in sync context (for Celery)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Scrape all flights
            flights = loop.run_until_complete(
                orchestrator.scrape_all(
                    origins=origin_airports,
                    destinations=destination_airports,
                    date_ranges=holiday_periods
                )
            )

            logger.info(f"Scraped {len(flights)} unique flights")

            # Save to database
            stats = loop.run_until_complete(
                orchestrator.save_to_database(flights, create_job=True)
            )

            logger.info(
                f"Database save complete: {stats['inserted']} inserted, "
                f"{stats['updated']} updated, {stats['skipped']} skipped"
            )

            return {
                "status": "success",
                "origins": origin_airports,
                "destinations": destination_airports,
                "holiday_periods": len(holiday_periods),
                "flights_scraped": len(flights),
                "flights_inserted": stats["inserted"],
                "flights_updated": stats["updated"],
                "task_id": self.request.id
            }

        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Error in daily flight search task: {e}", exc_info=True)
        raise


@celery_app.task(name="app.tasks.scheduled_tasks.update_flight_prices", bind=True)
def update_flight_prices(self):
    """
    Hourly task to update flight prices.

    Runs every hour.
    Re-scrapes recent flights (within last 7 days) to track price changes.
    Saves price history for analysis.
    """
    logger.info("Starting hourly price update task")

    try:
        db = get_sync_session()

        try:
            # Get flights scraped in the last 7 days with departure date in the future
            cutoff_date = datetime.now() - timedelta(days=7)
            future_departure = datetime.now().date()

            flights = db.query(Flight).filter(
                and_(
                    Flight.scraped_at >= cutoff_date,
                    Flight.departure_date >= future_departure
                )
            ).limit(100).all()  # Limit to avoid rate limiting

            logger.info(f"Found {len(flights)} recent flights to update")

            if not flights:
                logger.info("No recent flights to update")
                return {"status": "success", "flights_updated": 0, "task_id": self.request.id}

            # Group flights by route for efficient scraping
            routes = {}
            for flight in flights:
                key = (
                    flight.origin_airport.iata_code if flight.origin_airport else None,
                    flight.destination_airport.iata_code if flight.destination_airport else None,
                    flight.departure_date
                )
                if key[0] and key[1]:
                    if key not in routes:
                        routes[key] = []
                    routes[key].append(flight)

            logger.info(f"Grouped into {len(routes)} unique routes")

            updated_count = 0
            price_changes = 0

            # Re-scrape each route and update prices
            orchestrator = FlightOrchestrator()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                for (origin, destination, dep_date), route_flights in routes.items():
                    # Estimate return date (7 days later as default)
                    return_date = dep_date + timedelta(days=7)

                    try:
                        # Scrape current prices
                        new_flights = loop.run_until_complete(
                            orchestrator.scrape_all(
                                origins=[origin],
                                destinations=[destination],
                                date_ranges=[(dep_date, return_date)]
                            )
                        )

                        # Update prices if found cheaper
                        for old_flight in route_flights:
                            # Find matching flight in new results
                            for new_flight_data in new_flights:
                                if (
                                    new_flight_data.get("airline") == old_flight.airline and
                                    abs(
                                        (datetime.strptime(new_flight_data.get("departure_time", "00:00"), "%H:%M").time().hour if new_flight_data.get("departure_time") else 0) -
                                        (old_flight.departure_time.hour if old_flight.departure_time else 0)
                                    ) <= 2  # Within 2 hours
                                ):
                                    new_price = new_flight_data.get("price_per_person", 0)
                                    old_price = float(old_flight.price_per_person)

                                    # Save price history
                                    price_history = PriceHistory(
                                        flight_id=old_flight.id,
                                        price_per_person=new_price,
                                        total_price=new_price * 4,
                                        recorded_at=datetime.now()
                                    )
                                    db.add(price_history)

                                    # Update flight if price changed
                                    if abs(new_price - old_price) > 0.01:
                                        old_flight.price_per_person = new_price
                                        old_flight.total_price = new_price * 4
                                        old_flight.scraped_at = datetime.now()
                                        price_changes += 1
                                        logger.info(
                                            f"Price changed for {old_flight.airline} "
                                            f"{origin}→{destination}: €{old_price:.2f} → €{new_price:.2f}"
                                        )

                                    updated_count += 1
                                    break

                    except Exception as e:
                        logger.warning(f"Failed to update route {origin}→{destination}: {e}")
                        continue

                db.commit()

            finally:
                loop.close()

            logger.info(
                f"Price update complete: {updated_count} flights updated, "
                f"{price_changes} price changes detected"
            )

            return {
                "status": "success",
                "flights_checked": len(flights),
                "flights_updated": updated_count,
                "price_changes": price_changes,
                "task_id": self.request.id
            }

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error in price update task: {e}", exc_info=True)
        raise


@celery_app.task(name="app.tasks.scheduled_tasks.discover_events", bind=True)
def discover_events(self):
    """
    Weekly task to discover family-friendly events.

    Runs every Sunday at 8 AM UTC.
    Discovers events from Eventbrite and tourism boards (Barcelona, Prague, Lisbon).
    """
    logger.info("Starting weekly event discovery task")

    try:
        db = get_sync_session()

        try:
            # Popular family destinations
            destinations = [
                {"city": "Barcelona", "scraper": BarcelonaScraper()},
                {"city": "Prague", "scraper": PragueScraper()},
                {"city": "Lisbon", "scraper": LisbonScraper()},
            ]

            total_events = 0
            events_by_city = {}

            # Scrape tourism events for each city
            for dest in destinations:
                city = dest["city"]
                scraper = dest["scraper"]

                try:
                    logger.info(f"Scraping events for {city}")

                    # Run async scraper in sync context
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    try:
                        events_data = loop.run_until_complete(scraper.scrape_events())

                        logger.info(f"Found {len(events_data)} events in {city}")

                        # Save events to database
                        saved_count = 0
                        for event_data in events_data:
                            # Check if event already exists
                            existing = db.query(Event).filter(
                                and_(
                                    Event.title == event_data.get("title"),
                                    Event.city == city,
                                    Event.event_date == event_data.get("event_date")
                                )
                            ).first()

                            if not existing:
                                event = Event(
                                    title=event_data.get("title", "Unknown Event"),
                                    description=event_data.get("description", ""),
                                    city=city,
                                    venue=event_data.get("venue", ""),
                                    event_date=event_data.get("event_date"),
                                    end_date=event_data.get("end_date"),
                                    price=event_data.get("price", 0.0),
                                    url=event_data.get("url", ""),
                                    source=event_data.get("source", f"{city.lower()}_tourism"),
                                    category=event_data.get("category", "cultural"),
                                    age_appropriate=event_data.get("age_appropriate", True),
                                )
                                db.add(event)
                                saved_count += 1

                        db.commit()
                        total_events += saved_count
                        events_by_city[city] = saved_count

                        logger.info(f"Saved {saved_count} new events for {city}")

                    finally:
                        loop.close()

                except Exception as e:
                    logger.warning(f"Failed to scrape events for {city}: {e}")
                    continue

            # Scrape Eventbrite if API key is configured
            if settings.eventbrite_api_key:
                try:
                    logger.info("Scraping Eventbrite events")

                    eventbrite = EventbriteScraper()
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    try:
                        # Search for family events in popular destinations
                        for city in ["Barcelona", "Lisbon", "Prague"]:
                            events_data = loop.run_until_complete(
                                eventbrite.search_events(location=city, keywords="family")
                            )

                            logger.info(f"Found {len(events_data)} Eventbrite events in {city}")

                            saved_count = 0
                            for event_data in events_data:
                                # Check if event already exists
                                existing = db.query(Event).filter(
                                    and_(
                                        Event.title == event_data.get("title"),
                                        Event.city == city,
                                        Event.event_date == event_data.get("event_date")
                                    )
                                ).first()

                                if not existing:
                                    event = Event(
                                        title=event_data.get("title", "Unknown Event"),
                                        description=event_data.get("description", ""),
                                        city=city,
                                        venue=event_data.get("venue", ""),
                                        event_date=event_data.get("event_date"),
                                        end_date=event_data.get("end_date"),
                                        price=event_data.get("price", 0.0),
                                        url=event_data.get("url", ""),
                                        source="eventbrite",
                                        category=event_data.get("category", "family"),
                                        age_appropriate=True,
                                    )
                                    db.add(event)
                                    saved_count += 1

                            db.commit()
                            total_events += saved_count

                            if city in events_by_city:
                                events_by_city[city] += saved_count
                            else:
                                events_by_city[city] = saved_count

                            logger.info(f"Saved {saved_count} new Eventbrite events for {city}")

                    finally:
                        loop.close()

                except Exception as e:
                    logger.warning(f"Failed to scrape Eventbrite events: {e}")

            logger.info(f"Event discovery complete: {total_events} total events saved")

            return {
                "status": "success",
                "total_events": total_events,
                "events_by_city": events_by_city,
                "task_id": self.request.id
            }

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error in event discovery task: {e}", exc_info=True)
        raise


@celery_app.task(name="app.tasks.scheduled_tasks.search_accommodations", bind=True)
def search_accommodations(self):
    """
    Daily task to search for accommodations.

    Runs every day at 7 AM UTC.
    Searches for family-friendly accommodations in destinations with upcoming flights.
    """
    logger.info("Starting daily accommodation search task")

    try:
        db = get_sync_session()

        try:
            # Get unique destination cities from flights in the next 6 months
            future_date = datetime.now().date()
            end_date = future_date + timedelta(days=180)

            destinations_query = db.query(Flight.destination_airport_id).filter(
                and_(
                    Flight.departure_date >= future_date,
                    Flight.departure_date <= end_date
                )
            ).distinct()

            # Get actual destination cities
            destinations = []
            for (dest_airport_id,) in destinations_query:
                from app.models.airport import Airport
                airport = db.query(Airport).get(dest_airport_id)
                if airport and airport.city:
                    city = airport.city
                    if city not in destinations:
                        destinations.append(city)

            logger.info(f"Found {len(destinations)} destination cities with flights")

            if not destinations:
                logger.info("No destinations found, using default list")
                destinations = ["Barcelona", "Lisbon", "Prague"]

            total_accommodations = 0
            accommodations_by_city = {}

            # Get upcoming school holiday periods for check-in dates
            holiday_periods = get_school_holiday_periods(
                start_date=future_date,
                end_date=end_date
            )

            if not holiday_periods:
                # Fallback: use next weekend
                next_saturday = future_date + timedelta(days=(5 - future_date.weekday()) % 7)
                holiday_periods = [(next_saturday, next_saturday + timedelta(days=7))]

            # Limit to first 3 periods to avoid excessive scraping
            holiday_periods = holiday_periods[:3]

            logger.info(f"Will search accommodations for {len(holiday_periods)} date periods")

            # Scrape Booking.com for each destination
            booking_scraper = BookingScraper()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                for city in destinations[:5]:  # Limit to 5 cities to avoid excessive load
                    for check_in, check_out in holiday_periods:
                        try:
                            logger.info(f"Scraping accommodations for {city}, {check_in} to {check_out}")

                            # Scrape accommodations
                            accommodations_data = loop.run_until_complete(
                                booking_scraper.search_accommodations(
                                    destination=city,
                                    check_in_date=check_in,
                                    check_out_date=check_out,
                                    adults=2,
                                    children=2
                                )
                            )

                            logger.info(f"Found {len(accommodations_data)} accommodations in {city}")

                            # Save to database
                            saved_count = 0
                            for acc_data in accommodations_data:
                                # Check if accommodation already exists
                                existing = db.query(Accommodation).filter(
                                    and_(
                                        Accommodation.name == acc_data.get("name"),
                                        Accommodation.city == city,
                                        Accommodation.check_in_date == check_in
                                    )
                                ).first()

                                if not existing:
                                    accommodation = Accommodation(
                                        name=acc_data.get("name", "Unknown Property"),
                                        city=city,
                                        address=acc_data.get("address", ""),
                                        check_in_date=check_in,
                                        check_out_date=check_out,
                                        price_per_night=acc_data.get("price_per_night", 0.0),
                                        total_price=acc_data.get("total_price", 0.0),
                                        rating=acc_data.get("rating", 0.0),
                                        num_reviews=acc_data.get("num_reviews", 0),
                                        accommodation_type=acc_data.get("accommodation_type", "hotel"),
                                        num_bedrooms=acc_data.get("num_bedrooms", 1),
                                        max_guests=acc_data.get("max_guests", 4),
                                        amenities=acc_data.get("amenities", []),
                                        url=acc_data.get("url", ""),
                                        source="booking",
                                    )
                                    db.add(accommodation)
                                    saved_count += 1

                            db.commit()
                            total_accommodations += saved_count

                            if city in accommodations_by_city:
                                accommodations_by_city[city] += saved_count
                            else:
                                accommodations_by_city[city] = saved_count

                            logger.info(f"Saved {saved_count} new accommodations for {city}")

                        except Exception as e:
                            logger.warning(f"Failed to scrape accommodations for {city}: {e}")
                            continue

            finally:
                loop.close()

            logger.info(f"Accommodation search complete: {total_accommodations} total accommodations saved")

            return {
                "status": "success",
                "total_accommodations": total_accommodations,
                "accommodations_by_city": accommodations_by_city,
                "destinations_searched": len(destinations[:5]),
                "date_periods": len(holiday_periods),
                "task_id": self.request.id
            }

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error in accommodation search task: {e}", exc_info=True)
        raise


@celery_app.task(name="app.tasks.scheduled_tasks.cleanup_old_data", bind=True)
def cleanup_old_data(self):
    """
    Daily task to clean up old data.

    Runs every day at 2 AM UTC.
    Removes:
    - Flights with past departure dates (older than 7 days)
    - Price history older than 90 days
    - Events that have already occurred (older than 7 days)
    - Failed scraping jobs older than 30 days
    - Trip packages with past departure dates (older than 30 days)
    - Accommodations with past check-in dates (older than 7 days)
    """
    logger.info("Starting daily cleanup task")

    try:
        db = get_sync_session()

        try:
            cleanup_stats = {
                "flights_deleted": 0,
                "price_history_deleted": 0,
                "events_deleted": 0,
                "scraping_jobs_deleted": 0,
                "trip_packages_deleted": 0,
                "accommodations_deleted": 0,
            }

            # 1. Delete old flights (past departure date + 7 days)
            flight_cutoff = datetime.now().date() - timedelta(days=7)
            old_flights = db.query(Flight).filter(
                Flight.departure_date < flight_cutoff
            ).delete(synchronize_session=False)
            cleanup_stats["flights_deleted"] = old_flights
            logger.info(f"Deleted {old_flights} old flights (before {flight_cutoff})")

            # 2. Delete old price history (older than 90 days)
            price_history_cutoff = datetime.now() - timedelta(days=90)
            old_price_history = db.query(PriceHistory).filter(
                PriceHistory.recorded_at < price_history_cutoff
            ).delete(synchronize_session=False)
            cleanup_stats["price_history_deleted"] = old_price_history
            logger.info(f"Deleted {old_price_history} old price history records (before {price_history_cutoff})")

            # 3. Delete old events (past event date + 7 days)
            event_cutoff = datetime.now().date() - timedelta(days=7)
            old_events = db.query(Event).filter(
                Event.event_date < event_cutoff
            ).delete(synchronize_session=False)
            cleanup_stats["events_deleted"] = old_events
            logger.info(f"Deleted {old_events} old events (before {event_cutoff})")

            # 4. Delete old failed scraping jobs (older than 30 days)
            scraping_job_cutoff = datetime.now() - timedelta(days=30)
            old_jobs = db.query(ScrapingJob).filter(
                and_(
                    ScrapingJob.status == "failed",
                    ScrapingJob.started_at < scraping_job_cutoff
                )
            ).delete(synchronize_session=False)
            cleanup_stats["scraping_jobs_deleted"] = old_jobs
            logger.info(f"Deleted {old_jobs} old failed scraping jobs (before {scraping_job_cutoff})")

            # 5. Delete old trip packages (past departure date + 30 days)
            trip_package_cutoff = datetime.now().date() - timedelta(days=30)
            old_packages = db.query(TripPackage).filter(
                TripPackage.departure_date < trip_package_cutoff
            ).delete(synchronize_session=False)
            cleanup_stats["trip_packages_deleted"] = old_packages
            logger.info(f"Deleted {old_packages} old trip packages (before {trip_package_cutoff})")

            # 6. Delete old accommodations (past check-in date + 7 days)
            accommodation_cutoff = datetime.now().date() - timedelta(days=7)
            old_accommodations = db.query(Accommodation).filter(
                Accommodation.check_in_date < accommodation_cutoff
            ).delete(synchronize_session=False)
            cleanup_stats["accommodations_deleted"] = old_accommodations
            logger.info(f"Deleted {old_accommodations} old accommodations (before {accommodation_cutoff})")

            # Commit all deletions
            db.commit()

            total_deleted = sum(cleanup_stats.values())
            logger.info(f"Cleanup complete: {total_deleted} total records deleted")

            return {
                "status": "success",
                "total_deleted": total_deleted,
                "breakdown": cleanup_stats,
                "task_id": self.request.id
            }

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error in cleanup task: {e}", exc_info=True)
        raise


@celery_app.task(name="app.tasks.scheduled_tasks.send_deal_notifications", bind=True)
def send_deal_notifications(self):
    """
    Task to send notifications for new deals.

    Can be triggered manually or scheduled (runs daily at 9 AM UTC).
    Sends email notifications to users about high-scoring trip packages that
    haven't been notified yet.

    Logic:
    1. Query user preferences to get notification threshold
    2. Find trip packages with ai_score >= threshold and notified=False
    3. Send daily digest email with top deals
    4. Send immediate alerts for exceptional deals (score >= 85)
    5. Mark packages as notified
    """
    logger.info("Starting deal notification task")

    try:
        db = get_sync_session()

        try:
            # Get user preferences (default user_id=1 for now)
            user_prefs = db.query(UserPreference).filter(
                UserPreference.user_id == 1
            ).first()

            if not user_prefs:
                # Create default preferences if none exist
                logger.info("No user preferences found, creating default")
                user_prefs = UserPreference(
                    user_id=1,
                    max_flight_price_family=200.0,
                    max_flight_price_parents=300.0,
                    max_total_budget_family=2000.0,
                    notification_threshold=70.0,
                    parent_escape_frequency="quarterly",
                )
                db.add(user_prefs)
                db.commit()

            notification_threshold = float(user_prefs.notification_threshold)
            logger.info(f"Using notification threshold: {notification_threshold}")

            # Find unnotified deals above threshold with future departure dates
            today = datetime.now().date()

            unnotified_deals = db.query(TripPackage).filter(
                and_(
                    TripPackage.notified == False,
                    TripPackage.ai_score >= notification_threshold,
                    TripPackage.departure_date >= today
                )
            ).order_by(TripPackage.ai_score.desc()).all()

            logger.info(f"Found {len(unnotified_deals)} unnotified deals above threshold")

            if not unnotified_deals:
                logger.info("No deals to notify, skipping email send")
                return {
                    "status": "success",
                    "deals_found": 0,
                    "emails_sent": 0,
                    "task_id": self.request.id
                }

            # Check if SMTP is configured
            if not settings.smtp_user or not settings.smtp_password:
                logger.warning(
                    "SMTP not configured, marking deals as notified without sending emails"
                )
                for deal in unnotified_deals:
                    deal.notified = True
                db.commit()

                return {
                    "status": "skipped",
                    "reason": "SMTP not configured",
                    "deals_found": len(unnotified_deals),
                    "deals_marked_notified": len(unnotified_deals),
                    "task_id": self.request.id
                }

            # Initialize email notifier
            # For now, use a default email - in production this would come from user preferences
            user_email = settings.smtp_user  # Fallback to sender email for testing
            email_notifier = create_email_notifier(user_email=user_email)

            emails_sent = 0
            alerts_sent = 0

            # Separate exceptional deals (score >= 85) from good deals
            exceptional_deals = [d for d in unnotified_deals if float(d.ai_score) >= 85]
            good_deals = [d for d in unnotified_deals if float(d.ai_score) < 85]

            # Send immediate alerts for exceptional deals
            for deal in exceptional_deals:
                try:
                    # Run async email in sync context
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    try:
                        success = loop.run_until_complete(
                            email_notifier.send_deal_alert(deal)
                        )

                        if success:
                            alerts_sent += 1
                            emails_sent += 1
                            deal.notified = True
                            logger.info(
                                f"Sent alert for exceptional deal: {deal.destination_city} "
                                f"(score: {deal.ai_score})"
                            )

                    finally:
                        loop.close()

                except Exception as e:
                    logger.warning(f"Failed to send alert for deal {deal.id}: {e}")
                    continue

            # Send daily digest for good deals (if any)
            if good_deals:
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    try:
                        success = loop.run_until_complete(
                            email_notifier.send_daily_digest(good_deals)
                        )

                        if success:
                            emails_sent += 1
                            # Mark all deals in digest as notified
                            for deal in good_deals:
                                deal.notified = True
                            logger.info(f"Sent daily digest with {len(good_deals)} deals")

                    finally:
                        loop.close()

                except Exception as e:
                    logger.warning(f"Failed to send daily digest: {e}")

            # Commit notification status updates
            db.commit()

            logger.info(
                f"Notification task complete: {emails_sent} emails sent "
                f"({alerts_sent} alerts, {1 if good_deals and emails_sent > alerts_sent else 0} digest)"
            )

            return {
                "status": "success",
                "deals_found": len(unnotified_deals),
                "exceptional_deals": len(exceptional_deals),
                "good_deals": len(good_deals),
                "alerts_sent": alerts_sent,
                "digest_sent": 1 if good_deals and emails_sent > alerts_sent else 0,
                "total_emails_sent": emails_sent,
                "task_id": self.request.id
            }

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error in notification task: {e}", exc_info=True)
        raise
