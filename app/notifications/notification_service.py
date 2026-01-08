"""
Notification service for managing email notifications to users.
Integrates with deal scoring workflow to trigger notifications.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.email_delivery_log import EmailDeliveryLog
from app.models.trip_package import TripPackage
from app.models.user_preference import UserPreference
from app.notifications.email_sender import EmailNotifier

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service for managing email notifications based on deal scores and user preferences.
    """

    def __init__(self, settings: Settings, email_notifier: EmailNotifier):
        """
        Initialize notification service.

        Args:
            settings: Application settings
            email_notifier: Email notification system
        """
        self.settings = settings
        self.email_notifier = email_notifier

    async def notify_new_deal(
        self,
        trip_package: TripPackage,
        user_preference: UserPreference,
        db_session: AsyncSession,
    ) -> bool:
        """
        Send notification for a newly scored deal if it meets criteria.

        Args:
            trip_package: The trip package that was just scored
            user_preference: User's notification preferences
            db_session: Async database session

        Returns:
            True if notification was sent, False otherwise
        """
        # Check if notifications are enabled globally
        if not self.settings.enable_notifications:
            logger.debug("Notifications globally disabled")
            return False

        # Check if user should receive notifications
        if not user_preference.should_receive_notifications():
            logger.debug(f"User {user_preference.id} has notifications disabled")
            return False

        # Check if already notified
        if trip_package.notified:
            logger.debug(f"Trip package {trip_package.id} already notified")
            return False

        # Check score threshold
        score = float(trip_package.ai_score or 0)
        threshold = float(user_preference.notification_threshold or self.settings.notification_threshold)

        if score < threshold:
            logger.debug(
                f"Trip score {score} below user threshold {threshold}"
            )
            return False

        # Determine notification type based on score
        alert_threshold = self.settings.notification_alert_threshold

        if score >= alert_threshold and user_preference.enable_instant_alerts:
            # Send instant alert for exceptional deals
            success = await self._send_instant_alert(
                trip_package, user_preference, db_session
            )
        elif user_preference.enable_daily_digest:
            # Mark for daily digest (don't send immediately)
            logger.info(
                f"Trip {trip_package.id} marked for daily digest (score: {score})"
            )
            # Daily digest will be sent by scheduled task
            return False
        else:
            logger.debug("No matching notification preference for this deal")
            return False

        return success

    async def _send_instant_alert(
        self,
        trip_package: TripPackage,
        user_preference: UserPreference,
        db_session: AsyncSession,
    ) -> bool:
        """
        Send instant alert email for exceptional deal.

        Args:
            trip_package: The trip package to notify about
            user_preference: User's preferences
            db_session: Database session

        Returns:
            True if sent successfully
        """
        try:
            # Ensure unsubscribe token exists
            if not user_preference.unsubscribe_token:
                user_preference.generate_unsubscribe_token()
                await db_session.commit()

            # Send email
            success = await self.email_notifier.send_deal_alert(
                deal=trip_package,
                to_email=user_preference.email,
                unsubscribe_token=user_preference.unsubscribe_token,
            )

            # Log delivery
            await self._log_delivery(
                email_type="instant_alert",
                recipient_email=user_preference.email,
                subject=f"Exceptional Deal Alert: {trip_package.destination_city}",
                user_preference_id=user_preference.id,
                trip_package_id=trip_package.id,
                sent_successfully=success,
                error_message=None if success else "Failed to send email",
                db_session=db_session,
            )

            # Mark as notified
            if success:
                trip_package.notified = True
                await db_session.commit()
                logger.info(
                    f"Sent instant alert for trip {trip_package.id} to {user_preference.email}"
                )

            return success

        except Exception as e:
            logger.error(f"Error sending instant alert: {e}", exc_info=True)
            await self._log_delivery(
                email_type="instant_alert",
                recipient_email=user_preference.email,
                subject=f"Exceptional Deal Alert: {trip_package.destination_city}",
                user_preference_id=user_preference.id,
                trip_package_id=trip_package.id,
                sent_successfully=False,
                error_message=str(e),
                db_session=db_session,
            )
            return False

    async def send_daily_digest_async(
        self,
        user_preference: UserPreference,
        db_session: AsyncSession,
    ) -> bool:
        """
        Send daily digest email with top deals (async version).

        Args:
            user_preference: User's preferences
            db_session: Async database session

        Returns:
            True if sent successfully
        """
        if not user_preference.should_receive_notifications():
            return False

        if not user_preference.enable_daily_digest:
            return False

        try:
            # Get unnotified deals above threshold
            threshold = float(user_preference.notification_threshold or self.settings.notification_threshold)

            # Query for deals from last 24 hours above threshold
            yesterday = datetime.now() - timedelta(days=1)

            query = (
                select(TripPackage)
                .where(TripPackage.ai_score >= threshold)
                .where(TripPackage.created_at >= yesterday)
                .where(TripPackage.notified == False)
                .order_by(TripPackage.ai_score.desc())
                .limit(10)
            )

            result = await db_session.execute(query)
            deals = list(result.scalars().all())

            if not deals:
                logger.info(f"No deals to send in daily digest for user {user_preference.id}")
                return False

            # Ensure unsubscribe token exists
            if not user_preference.unsubscribe_token:
                user_preference.generate_unsubscribe_token()
                await db_session.commit()

            # Send email
            success = await self.email_notifier.send_daily_digest(
                deals=deals,
                to_email=user_preference.email,
                unsubscribe_token=user_preference.unsubscribe_token,
            )

            # Log delivery
            await self._log_delivery(
                email_type="daily_digest",
                recipient_email=user_preference.email,
                subject=f"Daily Travel Deals - {datetime.now().strftime('%B %d, %Y')}",
                user_preference_id=user_preference.id,
                trip_package_id=None,
                sent_successfully=success,
                error_message=None if success else "Failed to send email",
                num_deals_included=len(deals),
                db_session=db_session,
            )

            # Mark deals as notified
            if success:
                for deal in deals:
                    deal.notified = True
                await db_session.commit()
                logger.info(
                    f"Sent daily digest with {len(deals)} deals to {user_preference.email}"
                )

            return success

        except Exception as e:
            logger.error(f"Error sending daily digest: {e}", exc_info=True)
            await self._log_delivery(
                email_type="daily_digest",
                recipient_email=user_preference.email,
                subject=f"Daily Travel Deals - {datetime.now().strftime('%B %d, %Y')}",
                user_preference_id=user_preference.id,
                trip_package_id=None,
                sent_successfully=False,
                error_message=str(e),
                db_session=db_session,
            )
            return False

    def send_daily_digest_sync(
        self,
        user_preference: UserPreference,
        db_session: Session,
    ) -> bool:
        """
        Send daily digest email with top deals (sync version for Celery).

        Args:
            user_preference: User's preferences
            db_session: Sync database session

        Returns:
            True if sent successfully
        """
        if not user_preference.should_receive_notifications():
            return False

        if not user_preference.enable_daily_digest:
            return False

        try:
            # Get unnotified deals above threshold
            threshold = float(user_preference.notification_threshold or self.settings.notification_threshold)

            # Query for deals from last 24 hours above threshold
            yesterday = datetime.now() - timedelta(days=1)

            deals = (
                db_session.query(TripPackage)
                .filter(TripPackage.ai_score >= threshold)
                .filter(TripPackage.created_at >= yesterday)
                .filter(TripPackage.notified == False)
                .order_by(TripPackage.ai_score.desc())
                .limit(10)
                .all()
            )

            if not deals:
                logger.info(f"No deals to send in daily digest for user {user_preference.id}")
                return False

            # Ensure unsubscribe token exists
            if not user_preference.unsubscribe_token:
                user_preference.generate_unsubscribe_token()
                db_session.commit()

            # Send email (email_notifier methods are already async but we need to run them)
            import asyncio
            success = asyncio.run(
                self.email_notifier.send_daily_digest(
                    deals=deals,
                    to_email=user_preference.email,
                    unsubscribe_token=user_preference.unsubscribe_token,
                )
            )

            # Log delivery
            self._log_delivery_sync(
                email_type="daily_digest",
                recipient_email=user_preference.email,
                subject=f"Daily Travel Deals - {datetime.now().strftime('%B %d, %Y')}",
                user_preference_id=user_preference.id,
                trip_package_id=None,
                sent_successfully=success,
                error_message=None if success else "Failed to send email",
                num_deals_included=len(deals),
                db_session=db_session,
            )

            # Mark deals as notified
            if success:
                for deal in deals:
                    deal.notified = True
                db_session.commit()
                logger.info(
                    f"Sent daily digest with {len(deals)} deals to {user_preference.email}"
                )

            return success

        except Exception as e:
            logger.error(f"Error sending daily digest: {e}", exc_info=True)
            self._log_delivery_sync(
                email_type="daily_digest",
                recipient_email=user_preference.email,
                subject=f"Daily Travel Deals - {datetime.now().strftime('%B %d, %Y')}",
                user_preference_id=user_preference.id,
                trip_package_id=None,
                sent_successfully=False,
                error_message=str(e),
                db_session=db_session,
            )
            return False

    async def _log_delivery(
        self,
        email_type: str,
        recipient_email: str,
        subject: str,
        user_preference_id: Optional[int],
        trip_package_id: Optional[int],
        sent_successfully: bool,
        error_message: Optional[str],
        db_session: AsyncSession,
        num_deals_included: Optional[int] = None,
    ) -> None:
        """
        Log email delivery to database (async).

        Args:
            email_type: Type of email
            recipient_email: Recipient's email
            subject: Email subject
            user_preference_id: User preference ID
            trip_package_id: Trip package ID (if applicable)
            sent_successfully: Whether email was sent successfully
            error_message: Error message if failed
            db_session: Database session
            num_deals_included: Number of deals in digest
        """
        try:
            log = EmailDeliveryLog(
                email_type=email_type,
                recipient_email=recipient_email,
                subject=subject,
                user_preference_id=user_preference_id,
                trip_package_id=trip_package_id,
                sent_successfully=sent_successfully,
                error_message=error_message,
                num_deals_included=num_deals_included,
            )
            db_session.add(log)
            await db_session.commit()
        except Exception as e:
            logger.error(f"Failed to log email delivery: {e}", exc_info=True)

    def _log_delivery_sync(
        self,
        email_type: str,
        recipient_email: str,
        subject: str,
        user_preference_id: Optional[int],
        trip_package_id: Optional[int],
        sent_successfully: bool,
        error_message: Optional[str],
        db_session: Session,
        num_deals_included: Optional[int] = None,
    ) -> None:
        """
        Log email delivery to database (sync version for Celery).

        Args:
            email_type: Type of email
            recipient_email: Recipient's email
            subject: Email subject
            user_preference_id: User preference ID
            trip_package_id: Trip package ID (if applicable)
            sent_successfully: Whether email was sent successfully
            error_message: Error message if failed
            db_session: Database session
            num_deals_included: Number of deals in digest
        """
        try:
            log = EmailDeliveryLog(
                email_type=email_type,
                recipient_email=recipient_email,
                subject=subject,
                user_preference_id=user_preference_id,
                trip_package_id=trip_package_id,
                sent_successfully=sent_successfully,
                error_message=error_message,
                num_deals_included=num_deals_included,
            )
            db_session.add(log)
            db_session.commit()
        except Exception as e:
            logger.error(f"Failed to log email delivery: {e}", exc_info=True)


def create_notification_service(
    settings: Optional[Settings] = None,
) -> NotificationService:
    """
    Factory function to create NotificationService instance.

    Args:
        settings: Application settings (defaults to global settings)

    Returns:
        NotificationService instance
    """
    if settings is None:
        from app.config import get_settings
        settings = get_settings()

    from app.notifications.email_sender import create_email_notifier
    email_notifier = create_email_notifier(settings=settings)

    return NotificationService(settings=settings, email_notifier=email_notifier)
