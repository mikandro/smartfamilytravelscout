"""
Scheduled Celery tasks for automated operations.
"""

import logging
from datetime import datetime, timedelta

from app.tasks.celery_app import celery_app
from app.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.scheduled_tasks.daily_flight_search", bind=True)
def daily_flight_search(self):
    """
    Daily task to search for flight deals.

    Runs every day at 6 AM UTC.
    Searches for flights from configured departure airports.
    """
    logger.info("Starting daily flight search task")

    try:
        # Get departure airports from settings
        airports = settings.get_departure_airports_list()
        logger.info(f"Searching flights from airports: {airports}")

        # Calculate search dates (advance booking window)
        start_date = datetime.now() + timedelta(days=7)
        end_date = start_date + timedelta(days=settings.advance_booking_days)

        logger.info(f"Search period: {start_date.date()} to {end_date.date()}")

        # TODO: Implement actual flight search logic
        # Example:
        # for airport in airports:
        #     search_flights_from_airport.delay(airport, start_date, end_date)

        logger.info("Daily flight search task completed successfully")
        return {"status": "success", "airports": airports, "task_id": self.request.id}

    except Exception as e:
        logger.error(f"Error in daily flight search task: {e}", exc_info=True)
        raise


@celery_app.task(name="app.tasks.scheduled_tasks.update_flight_prices", bind=True)
def update_flight_prices(self):
    """
    Hourly task to update flight prices.

    Runs every hour.
    Updates prices for tracked flights.
    """
    logger.info("Starting hourly price update task")

    try:
        # TODO: Implement price update logic
        # Example:
        # tracked_flights = get_tracked_flights()
        # for flight in tracked_flights:
        #     update_flight_price.delay(flight.id)

        logger.info("Hourly price update task completed successfully")
        return {"status": "success", "task_id": self.request.id}

    except Exception as e:
        logger.error(f"Error in price update task: {e}", exc_info=True)
        raise


@celery_app.task(name="app.tasks.scheduled_tasks.discover_events", bind=True)
def discover_events(self):
    """
    Weekly task to discover family-friendly events.

    Runs every Sunday at 8 AM UTC.
    Discovers events from Eventbrite and other sources.
    """
    logger.info("Starting weekly event discovery task")

    try:
        # TODO: Implement event discovery logic
        # Example:
        # destinations = get_popular_destinations()
        # for destination in destinations:
        #     scrape_eventbrite.delay(destination)

        logger.info("Weekly event discovery task completed successfully")
        return {"status": "success", "task_id": self.request.id}

    except Exception as e:
        logger.error(f"Error in event discovery task: {e}", exc_info=True)
        raise


@celery_app.task(name="app.tasks.scheduled_tasks.search_accommodations", bind=True)
def search_accommodations(self):
    """
    Daily task to search for accommodations.

    Runs every day at 7 AM UTC.
    Searches for family-friendly accommodations in destinations with upcoming flights.
    Uses AccommodationOrchestrator to coordinate multiple sources (Booking.com, Airbnb).
    """
    logger.info("Starting daily accommodation search task")

    try:
        import asyncio
        from datetime import date, timedelta
        from sqlalchemy import and_
        from app.orchestration.accommodation_orchestrator import AccommodationOrchestrator
        from app.database import get_sync_session
        from app.models.airport import Airport
        from app.models.flight import Flight
        from app.utils.date_utils import get_school_holiday_periods

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
                airport = db.query(Airport).get(dest_airport_id)
                if airport and airport.city:
                    city = airport.city
                    if city not in destinations:
                        destinations.append(city)

            logger.info(f"Found {len(destinations)} destination cities with flights")

            if not destinations:
                logger.info("No destinations found, using default list")
                destinations = ["Barcelona", "Lisbon", "Prague"]

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

            # Run async orchestrator in sync context
            async def run_search():
                orchestrator = AccommodationOrchestrator()
                total_accommodations = 0
                accommodations_by_city = {}

                # Limit to 5 cities to avoid excessive load
                for city in destinations[:5]:
                    city_total = 0
                    for check_in, check_out in holiday_periods:
                        try:
                            logger.info(f"Searching accommodations for {city}, {check_in} to {check_out}")
                            accommodations = await orchestrator.search_all_sources(
                                city=city,
                                check_in=check_in,
                                check_out=check_out,
                                adults=2,
                                children=2,
                            )

                            # Save to database
                            if accommodations:
                                stats = await orchestrator.save_to_database(accommodations)
                                period_total = stats["inserted"] + stats["updated"]
                                city_total += period_total
                                total_accommodations += period_total
                                logger.info(
                                    f"Saved {stats['inserted']} new and updated {stats['updated']} "
                                    f"accommodations for {city} ({check_in} to {check_out})"
                                )

                        except Exception as e:
                            logger.error(f"Error searching accommodations for {city}: {e}", exc_info=True)
                            continue

                    accommodations_by_city[city] = city_total

                return total_accommodations, accommodations_by_city

            total, accommodations_by_city = asyncio.run(run_search())

            logger.info(f"Daily accommodation search task completed successfully. Total: {total} accommodations")
            return {
                "status": "success",
                "task_id": self.request.id,
                "total_accommodations": total,
                "accommodations_by_city": accommodations_by_city,
                "destinations_searched": len(destinations[:5]),
                "date_periods": len(holiday_periods),
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
    Removes expired deals, old price data, etc.
    """
    logger.info("Starting daily cleanup task")

    try:
        # Calculate cutoff date (e.g., 30 days old)
        cutoff_date = datetime.now() - timedelta(days=30)
        logger.info(f"Cleaning up data older than: {cutoff_date.date()}")

        # TODO: Implement cleanup logic
        # Example:
        # delete_old_flights(cutoff_date)
        # delete_old_price_history(cutoff_date)
        # delete_expired_deals()

        logger.info("Daily cleanup task completed successfully")
        return {"status": "success", "cutoff_date": cutoff_date.isoformat(), "task_id": self.request.id}

    except Exception as e:
        logger.error(f"Error in cleanup task: {e}", exc_info=True)
        raise


@celery_app.task(name="app.tasks.scheduled_tasks.send_daily_digest", bind=True)
def send_daily_digest(self):
    """
    Daily task to send digest emails to all users with notifications enabled.

    Runs every day at 8 AM UTC.
    Sends top deals from last 24 hours to users.
    """
    logger.info("Starting daily digest task")

    try:
        from app.database import get_sync_session
        from app.models.user_preference import UserPreference
        from app.notifications.notification_service import create_notification_service

        db = get_sync_session()
        notification_service = create_notification_service()

        try:
            # Get all users with notifications enabled
            users = (
                db.query(UserPreference)
                .filter(UserPreference.enable_notifications == True)
                .filter(UserPreference.enable_daily_digest == True)
                .filter(UserPreference.email.isnot(None))
                .all()
            )

            logger.info(f"Sending daily digest to {len(users)} users")

            success_count = 0
            failed_count = 0

            for user in users:
                try:
                    if notification_service.send_daily_digest_sync(user, db):
                        success_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    logger.error(f"Error sending digest to user {user.id}: {e}", exc_info=True)
                    failed_count += 1

            logger.info(
                f"Daily digest task completed: {success_count} sent, {failed_count} failed"
            )
            return {
                "status": "success",
                "sent": success_count,
                "failed": failed_count,
                "task_id": self.request.id,
            }

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error in daily digest task: {e}", exc_info=True)
        raise


@celery_app.task(name="app.tasks.scheduled_tasks.send_deal_notifications", bind=True)
def send_deal_notifications(self):
    """
    Task to send notifications for new deals.

    Can be triggered manually or scheduled.
    Sends email notifications to users about new deals.
    This is primarily for instant alerts when exceptional deals are found.
    """
    logger.info("Starting deal notification task")

    try:
        from app.database import get_sync_session
        from app.models.trip_package import TripPackage
        from app.models.user_preference import UserPreference
        from app.notifications.notification_service import create_notification_service

        db = get_sync_session()
        notification_service = create_notification_service()

        try:
            # Get all users with instant alerts enabled
            users = (
                db.query(UserPreference)
                .filter(UserPreference.enable_notifications == True)
                .filter(UserPreference.enable_instant_alerts == True)
                .filter(UserPreference.email.isnot(None))
                .all()
            )

            if not users:
                logger.info("No users with instant alerts enabled")
                return {"status": "success", "sent": 0, "task_id": self.request.id}

            # Get unnotified high-score deals
            alert_threshold = settings.notification_alert_threshold
            deals = (
                db.query(TripPackage)
                .filter(TripPackage.ai_score >= alert_threshold)
                .filter(TripPackage.notified == False)
                .order_by(TripPackage.ai_score.desc())
                .limit(10)
                .all()
            )

            if not deals:
                logger.info("No new exceptional deals to notify about")
                return {"status": "success", "sent": 0, "task_id": self.request.id}

            logger.info(
                f"Found {len(deals)} exceptional deals for {len(users)} users"
            )

            notifications_sent = 0

            for deal in deals:
                for user in users:
                    # Check user's threshold
                    user_threshold = float(user.notification_threshold or settings.notification_threshold)
                    if float(deal.ai_score) >= user_threshold:
                        try:
                            # Send instant alert (sync version)
                            import asyncio
                            from app.notifications.email_sender import create_email_notifier

                            email_notifier = create_email_notifier()

                            success = asyncio.run(
                                email_notifier.send_deal_alert(
                                    deal=deal,
                                    to_email=user.email,
                                )
                            )

                            if success:
                                notifications_sent += 1
                                # Mark as notified after first successful notification
                                deal.notified = True
                                db.commit()
                                logger.info(f"Sent alert for deal {deal.id} to user {user.id}")

                        except Exception as e:
                            logger.error(
                                f"Error sending alert to user {user.id} for deal {deal.id}: {e}",
                                exc_info=True,
                            )

            logger.info(f"Deal notification task completed: {notifications_sent} alerts sent")
            return {
                "status": "success",
                "sent": notifications_sent,
                "deals_processed": len(deals),
                "task_id": self.request.id,
            }

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error in notification task: {e}", exc_info=True)
        raise
