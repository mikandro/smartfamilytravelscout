"""
Example integration of email notification system with database.
Shows how to send automated notifications based on trip packages in the database.
"""

import asyncio
import logging
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.trip_package import TripPackage
from app.notifications import create_email_notifier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def send_daily_digest_to_users():
    """
    Send daily digest of top deals to all subscribed users.
    This would typically run as a scheduled Celery task at 8 AM daily.
    """
    logger.info("Starting daily digest job...")

    settings = get_settings()

    # In production, iterate through all subscribed users
    # For now, using a single test user
    user_email = "user@example.com"  # Replace with actual user email

    async for db in get_db():
        try:
            # Query top deals with score > 70, not yet notified
            query = (
                select(TripPackage)
                .filter(
                    TripPackage.ai_score >= 70,
                    TripPackage.package_type == "family",
                    TripPackage.notified == False,
                    TripPackage.departure_date >= date.today(),
                )
                .order_by(TripPackage.ai_score.desc())
                .limit(5)
            )

            result = await db.execute(query)
            deals = result.scalars().all()

            if not deals:
                logger.info("No deals found for daily digest")
                return

            logger.info(f"Found {len(deals)} deals for daily digest")

            # Send email
            notifier = create_email_notifier(user_email=user_email)
            success = await notifier.send_daily_digest(deals)

            if success:
                # Mark deals as notified
                for deal in deals:
                    deal.notified = True
                await db.commit()
                logger.info(f"Daily digest sent successfully to {user_email}")
            else:
                logger.error("Failed to send daily digest")

        except Exception as e:
            logger.error(f"Error in daily digest job: {e}", exc_info=True)
            await db.rollback()


async def send_exceptional_deal_alerts():
    """
    Send immediate alerts for exceptional deals (score >= 85).
    This would typically run every hour to catch new exceptional deals.
    """
    logger.info("Checking for exceptional deals...")

    settings = get_settings()
    user_email = "user@example.com"  # Replace with actual user email

    async for db in get_db():
        try:
            # Query exceptional deals not yet notified
            query = (
                select(TripPackage)
                .filter(
                    TripPackage.ai_score >= 85,
                    TripPackage.notified == False,
                    TripPackage.departure_date >= date.today(),
                )
                .order_by(TripPackage.ai_score.desc())
            )

            result = await db.execute(query)
            exceptional_deals = result.scalars().all()

            if not exceptional_deals:
                logger.info("No exceptional deals found")
                return

            logger.info(f"Found {len(exceptional_deals)} exceptional deals")

            # Send alert for each exceptional deal
            notifier = create_email_notifier(user_email=user_email)

            for deal in exceptional_deals:
                success = await notifier.send_deal_alert(deal)

                if success:
                    deal.notified = True
                    logger.info(
                        f"Alert sent for exceptional deal: {deal.destination_city} "
                        f"(score: {deal.ai_score})"
                    )
                else:
                    logger.error(f"Failed to send alert for deal {deal.id}")

            await db.commit()

        except Exception as e:
            logger.error(f"Error in exceptional deal alerts: {e}", exc_info=True)
            await db.rollback()


async def send_weekly_parent_escape_digest():
    """
    Send weekly digest of romantic getaways.
    This would typically run every Monday at 8 AM.
    """
    logger.info("Starting weekly parent escape digest...")

    settings = get_settings()
    user_email = "user@example.com"  # Replace with actual user email

    async for db in get_db():
        try:
            # Query parent escape packages from the last week
            one_week_ago = date.today() - timedelta(days=7)

            query = (
                select(TripPackage)
                .filter(
                    TripPackage.package_type == "parent_escape",
                    TripPackage.ai_score >= 70,
                    TripPackage.departure_date >= date.today(),
                    TripPackage.created_at >= one_week_ago,
                )
                .order_by(TripPackage.ai_score.desc())
                .limit(5)
            )

            result = await db.execute(query)
            escapes = result.scalars().all()

            if not escapes:
                logger.info("No parent escape packages found for this week")
                return

            logger.info(f"Found {len(escapes)} parent escape packages")

            # Send email
            notifier = create_email_notifier(user_email=user_email)
            success = await notifier.send_parent_escape_digest(escapes)

            if success:
                logger.info(f"Parent escape digest sent successfully to {user_email}")
            else:
                logger.error("Failed to send parent escape digest")

        except Exception as e:
            logger.error(f"Error in parent escape digest: {e}", exc_info=True)


async def send_custom_notification(deal_id: int, user_email: str):
    """
    Send custom notification for a specific deal to a specific user.

    Args:
        deal_id: ID of the trip package
        user_email: User's email address
    """
    logger.info(f"Sending custom notification for deal {deal_id} to {user_email}")

    async for db in get_db():
        try:
            result = await db.execute(
                select(TripPackage).filter(TripPackage.id == deal_id)
            )
            deal = result.scalar_one_or_none()

            if not deal:
                logger.error(f"Deal {deal_id} not found")
                return

            notifier = create_email_notifier(user_email=user_email)

            # Send appropriate email based on score
            if deal.ai_score >= 85:
                success = await notifier.send_deal_alert(deal)
                email_type = "deal alert"
            else:
                success = await notifier.send_daily_digest([deal])
                email_type = "digest"

            if success:
                logger.info(f"Custom {email_type} sent successfully to {user_email}")
            else:
                logger.error(f"Failed to send custom notification")

        except Exception as e:
            logger.error(f"Error sending custom notification: {e}", exc_info=True)


async def main():
    """Run example tasks."""
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python email_integration.py daily         - Send daily digest")
        print("  python email_integration.py alerts        - Send exceptional deal alerts")
        print("  python email_integration.py weekly        - Send weekly parent escape digest")
        print("  python email_integration.py custom <deal_id> <email> - Send custom notification")
        return

    command = sys.argv[1]

    if command == "daily":
        await send_daily_digest_to_users()
    elif command == "alerts":
        await send_exceptional_deal_alerts()
    elif command == "weekly":
        await send_weekly_parent_escape_digest()
    elif command == "custom":
        if len(sys.argv) < 4:
            print("Error: custom command requires deal_id and email")
            print("Usage: python email_integration.py custom <deal_id> <email>")
            return
        deal_id = int(sys.argv[2])
        user_email = sys.argv[3]
        await send_custom_notification(deal_id, user_email)
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    asyncio.run(main())
