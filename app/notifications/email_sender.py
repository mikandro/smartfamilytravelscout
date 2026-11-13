"""
Email notification system with HTML templates.
Supports daily digests, deal alerts, and parent escape notifications.
"""

import logging
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import Settings
from app.exceptions import SMTPConfigurationError
from app.models.trip_package import TripPackage

logger = logging.getLogger(__name__)


class EmailNotifier:
    """Email notification system with HTML template support."""

    def __init__(self, settings: Settings, user_email: Optional[str] = None):
        """
        Initialize email notifier.

        Args:
            settings: Application settings with SMTP configuration
            user_email: Default recipient email address
        """
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_user = settings.smtp_user
        self.smtp_password = settings.smtp_password
        self.from_email = settings.smtp_from_email
        self.from_name = settings.smtp_from_name
        self.user_email = user_email

        # Setup Jinja2 template environment
        templates_dir = Path(__file__).parent / "templates"
        templates_dir.mkdir(exist_ok=True)

        self.template_env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Register custom filters
        self.template_env.filters["round"] = lambda x, decimals=0: round(float(x), int(decimals))
        self.template_env.filters["format_date"] = self._format_date
        self.template_env.filters["format_price"] = self._format_price

    def _format_date(self, value: date) -> str:
        """Format date for display."""
        return value.strftime("%B %d, %Y")

    def _format_price(self, value: float) -> str:
        """Format price with proper currency symbol."""
        return f"€{float(value):.2f}"

    async def send_daily_digest(
        self, deals: List[TripPackage], to_email: Optional[str] = None, unsubscribe_token: Optional[str] = None
    ) -> bool:
        """
        Send daily digest email with top deals.

        Args:
            deals: List of trip packages (score > 70)
            to_email: Recipient email (defaults to user_email)
            unsubscribe_token: User's unsubscribe token for the email footer

        Returns:
            True if email sent successfully, False otherwise
        """
        if not deals:
            logger.info("No deals to send in daily digest")
            return False

        recipient = to_email or self.user_email
        if not recipient:
            logger.error("No recipient email provided for daily digest")
            return False

        try:
            template = self.template_env.get_template("daily_digest.html")

            # Sort deals by score descending and take top 5
            top_deals = sorted(deals, key=lambda d: float(d.ai_score or 0), reverse=True)[:5]

            html_content = template.render(
                deals=top_deals,
                date=date.today(),
                total_deals=len(deals),
                summary=f"Found {len(deals)} great family travel deals today! Here are the top {len(top_deals)}:",
                unsubscribe_token=unsubscribe_token,
            )

            subject = f"🌍 Daily Travel Deals - {date.today().strftime('%B %d, %Y')}"

            return self.send_email(
                to_email=recipient,
                subject=subject,
                html_body=html_content,
            )
        except Exception as e:
            logger.error(f"Failed to send daily digest: {e}", exc_info=True)
            return False

    async def send_deal_alert(
        self, deal: TripPackage, to_email: Optional[str] = None, unsubscribe_token: Optional[str] = None
    ) -> bool:
        """
        Send immediate alert for exceptional deal.

        Args:
            deal: Trip package with score > 85
            to_email: Recipient email (defaults to user_email)
            unsubscribe_token: User's unsubscribe token for the email footer

        Returns:
            True if email sent successfully, False otherwise
        """
        recipient = to_email or self.user_email
        if not recipient:
            logger.error("No recipient email provided for deal alert")
            return False

        if not deal.ai_score or float(deal.ai_score) < 85:
            logger.warning(
                f"Deal score {deal.ai_score} is below alert threshold "
                f"({settings.notification_alert_threshold})"
            )
            return False

        try:
            template = self.template_env.get_template("deal_alert.html")

            html_content = template.render(
                deal=deal,
                date=date.today(),
                unsubscribe_token=unsubscribe_token,
            )

            subject = f"🚨 Exceptional Deal Alert: {deal.destination_city} - {deal.ai_score:.0f}/100!"

            return self.send_email(
                to_email=recipient,
                subject=subject,
                html_body=html_content,
            )
        except Exception as e:
            logger.error(f"Failed to send deal alert: {e}", exc_info=True)
            return False

    async def send_parent_escape_digest(
        self, getaways: List[TripPackage], to_email: Optional[str] = None, unsubscribe_token: Optional[str] = None
    ) -> bool:
        """
        Send weekly digest of romantic getaways for parents.

        Args:
            getaways: List of parent escape trip packages
            to_email: Recipient email (defaults to user_email)
            unsubscribe_token: User's unsubscribe token for the email footer

        Returns:
            True if email sent successfully, False otherwise
        """
        if not getaways:
            logger.info("No parent escape deals to send")
            return False

        recipient = to_email or self.user_email
        if not recipient:
            logger.error("No recipient email provided for parent escape digest")
            return False

        try:
            template = self.template_env.get_template("parent_escape.html")

            # Sort by score and take top 5
            top_getaways = sorted(
                getaways, key=lambda g: float(g.ai_score or 0), reverse=True
            )[:5]

            html_content = template.render(
                getaways=top_getaways,
                date=date.today(),
                total_getaways=len(getaways),
                summary=f"Found {len(getaways)} romantic getaways perfect for parents. Here are the top {len(top_getaways)}:",
                unsubscribe_token=unsubscribe_token,
            )

            subject = f"💑 Weekly Parent Escape Digest - {date.today().strftime('%B %d, %Y')}"

            return self.send_email(
                to_email=recipient,
                subject=subject,
                html_body=html_content,
            )
        except Exception as e:
            logger.error(f"Failed to send parent escape digest: {e}", exc_info=True)
            return False

    def _weekend_label(self, plan: Any) -> str:
        """e.g. ``Sat 14 – Sun 15 November`` (or a single day on a Sunday)."""
        days = plan.days
        if len(days) == 1:
            return days[0].strftime("%A %d %B")
        return f"{days[0].strftime('%a %d')} – {days[-1].strftime('%a %d %B')}"

    def render_weekend_plan(self, plan: Any, is_update: bool = False) -> str:
        """
        Render the weekend plan email as HTML.

        Args:
            plan: ``app.weekend.planner.WeekendPlanResult``
            is_update: True for the "forecast changed" follow-up
        """
        template = self.template_env.get_template("weekend_plan.html")
        return template.render(
            plan=plan,
            is_update=is_update,
            weekend_label=self._weekend_label(plan),
            verdict_icons={"outdoor": "☀️", "mixed": "⛅", "indoor": "🌧️"},
        )

    def render_weekend_plan_text(self, plan: Any, is_update: bool = False) -> str:
        """Plain-text version of the weekend plan (email fallback and CLI)."""
        lines = [f"Weekend plan: {self._weekend_label(plan)}"]
        if is_update:
            lines.append("The forecast changed, so this is an updated plan.")
        if plan.summary:
            lines += ["", plan.summary]
        if plan.forecast:
            lines.append("")
            lines += [f"  {day.summary()}" for day in plan.forecast]
        for kind, option in plan.ordered_options:
            label = "If it's dry" if kind == "outdoor" else "If it's wet"
            day = f" (best on {option.best_day_text})" if option.best_day_text else ""
            lines += ["", f"{label}{day}: {option.name}"]
            if option.why:
                lines.append(f"  {option.why}")
            if option.tips:
                lines.append(f"  Tip: {option.tips}")
            lines.append(f"  {option.travel_text}")
            extras = f"  about {option.duration_hours:g} h, {option.cost_text}"
            if option.booking_required:
                extras += ", book ahead"
            lines.append(extras)
            if option.url:
                lines.append(f"  {option.url}")
        if plan.events:
            lines += ["", "Only this weekend (from muenchen.de, check the link first):"]
            for event in plan.events:
                venue = f" at {event.venue}" if event.venue else ""
                lines.append(f"  - {event.title}{venue}: {event.when_text}")
                if event.why:
                    lines.append(f"    {event.why}")
                if event.age_note:
                    lines.append(f"    Ages: {event.age_note}")
                if not event.vetted:
                    lines.append("    Not checked for age fit.")
                if event.url:
                    lines.append(f"    {event.url}")
        if plan.alternates:
            lines += ["", "Also good this weekend:"]
            lines += [f"  - {option.name} ({option.drive_minutes} min drive)" for option in plan.alternates]
        for warning in plan.warnings:
            lines += ["", f"Note: {warning}"]
        return "\n".join(lines)

    async def send_weekend_plan(
        self, plan: Any, to_email: Optional[str] = None, is_update: bool = False
    ) -> bool:
        """
        Send the weekend plan email.

        Args:
            plan: ``app.weekend.planner.WeekendPlanResult``
            to_email: Recipient email (defaults to user_email)
            is_update: True for the "forecast changed" follow-up

        Returns:
            True if email sent successfully, False otherwise
        """
        recipient = to_email or self.user_email
        if not recipient:
            logger.error("No recipient email provided for weekend plan")
            return False

        try:
            prefix = "🔄 Forecast changed" if is_update else "🗓️ Weekend plan"
            subject = f"{prefix}: {self._weekend_label(plan)}"
            return self.send_email(
                to_email=recipient,
                subject=subject,
                html_body=self.render_weekend_plan(plan, is_update=is_update),
                text_body=self.render_weekend_plan_text(plan, is_update=is_update),
            )
        except Exception as e:
            logger.error(f"Failed to send weekend plan: {e}", exc_info=True)
            return False

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
    ) -> bool:
        """
        Send HTML email via SMTP.

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_body: HTML content
            text_body: Plain text fallback (optional)

        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.smtp_user or not self.smtp_password:
            logger.warning("SMTP credentials not configured, skipping email send")
            return False

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = to_email

            # Add plain text fallback if provided
            if text_body:
                text_part = MIMEText(text_body, "plain", "utf-8")
                msg.attach(text_part)

            # Add HTML content
            html_part = MIMEText(html_body, "html", "utf-8")
            msg.attach(html_part)

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
                server.set_debuglevel(0)
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Email sent successfully to {to_email}: {subject}")
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(
                f"SMTP authentication failed: {e}\n"
                f"Server: {self.smtp_host}:{self.smtp_port}\n"
                f"User: {self.smtp_user}\n"
                f"To fix:\n"
                f"  1. Verify SMTP_USER and SMTP_PASSWORD in .env\n"
                f"  2. For Gmail, use app-specific password (not your regular password)\n"
                f"  3. Ensure 2FA is enabled for app-specific passwords\n"
                f"  4. Check if 'Less secure app access' needs to be enabled",
                exc_info=True
            )
            return False
        except smtplib.SMTPException as e:
            logger.error(
                f"SMTP error while sending email to {to_email}: {e}\n"
                f"Server: {self.smtp_host}:{self.smtp_port}\n"
                f"Subject: {subject}\n"
                f"To fix:\n"
                f"  1. Verify SMTP server is reachable\n"
                f"  2. Check firewall settings\n"
                f"  3. Verify SMTP_HOST and SMTP_PORT in .env",
                exc_info=True
            )
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error sending email to {to_email}: {e}\n"
                f"Subject: {subject}\n"
                f"Check SMTP configuration in .env file",
                exc_info=True
            )
            return False

    def preview_daily_digest(self, deals: List[TripPackage]) -> str:
        """
        Generate HTML preview of daily digest email (for testing).

        Args:
            deals: List of trip packages

        Returns:
            HTML content as string
        """
        try:
            template = self.template_env.get_template("daily_digest.html")
            top_deals = sorted(deals, key=lambda d: float(d.ai_score or 0), reverse=True)[:5]

            return template.render(
                deals=top_deals,
                date=date.today(),
                total_deals=len(deals),
                summary=f"Found {len(deals)} great family travel deals today! Here are the top {len(top_deals)}:",
            )
        except Exception as e:
            logger.error(f"Failed to preview daily digest: {e}", exc_info=True)
            return f"<html><body><h1>Error generating preview</h1><p>{e}</p></body></html>"

    def preview_deal_alert(self, deal: TripPackage) -> str:
        """
        Generate HTML preview of deal alert email (for testing).

        Args:
            deal: Trip package

        Returns:
            HTML content as string
        """
        try:
            template = self.template_env.get_template("deal_alert.html")
            return template.render(deal=deal, date=date.today())
        except Exception as e:
            logger.error(f"Failed to preview deal alert: {e}", exc_info=True)
            return f"<html><body><h1>Error generating preview</h1><p>{e}</p></body></html>"

    def preview_parent_escape(self, getaways: List[TripPackage]) -> str:
        """
        Generate HTML preview of parent escape digest (for testing).

        Args:
            getaways: List of parent escape packages

        Returns:
            HTML content as string
        """
        try:
            template = self.template_env.get_template("parent_escape.html")
            top_getaways = sorted(
                getaways, key=lambda g: float(g.ai_score or 0), reverse=True
            )[:5]

            return template.render(
                getaways=top_getaways,
                date=date.today(),
                total_getaways=len(getaways),
                summary=f"Found {len(getaways)} romantic getaways perfect for parents. Here are the top {len(top_getaways)}:",
            )
        except Exception as e:
            logger.error(f"Failed to preview parent escape: {e}", exc_info=True)
            return f"<html><body><h1>Error generating preview</h1><p>{e}</p></body></html>"


def create_email_notifier(
    settings: Optional[Settings] = None, user_email: Optional[str] = None
) -> EmailNotifier:
    """
    Factory function to create EmailNotifier instance.

    Args:
        settings: Application settings (defaults to global settings)
        user_email: Default recipient email

    Returns:
        EmailNotifier instance
    """
    if settings is None:
        from app.config import get_settings

        settings = get_settings()

    return EmailNotifier(settings=settings, user_email=user_email)
