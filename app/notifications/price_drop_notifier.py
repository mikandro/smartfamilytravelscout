"""
Price drop notification system.

Sends email alerts when significant price drops are detected.
"""

import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict, List, Optional
import smtplib

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import Settings

logger = logging.getLogger(__name__)


class PriceDropNotifier:
    """Notification system for price drop alerts."""

    def __init__(self, settings: Settings, user_email: Optional[str] = None):
        """
        Initialize price drop notifier.

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
        self.template_env.filters["format_price"] = self._format_price

    def _format_price(self, value: float) -> str:
        """Format price with proper currency symbol."""
        return f"€{float(value):.2f}"

    async def send_price_drop_alert(
        self,
        drops: List[Dict],
        to_email: Optional[str] = None,
        threshold_percent: float = 10.0,
    ) -> bool:
        """
        Send price drop alert email.

        Args:
            drops: List of price drop dictionaries from PriceHistoryService
            to_email: Recipient email (defaults to user_email)
            threshold_percent: Minimum price drop percentage that triggered this alert

        Returns:
            True if email sent successfully, False otherwise
        """
        if not drops:
            logger.info("No price drops to notify")
            return False

        recipient = to_email or self.user_email
        if not recipient:
            logger.error("No recipient email provided for price drop alert")
            return False

        try:
            # Try to load custom template, fall back to simple HTML
            try:
                template = self.template_env.get_template("price_drop_alert.html")
                html_content = template.render(
                    drops=drops,
                    threshold=threshold_percent,
                    total_drops=len(drops),
                    date=datetime.now(),
                )
            except Exception:
                # Fallback to simple HTML if template not found
                html_content = self._generate_simple_html(drops, threshold_percent)

            subject = f"🎯 Price Drop Alert: {len(drops)} Flight{'s' if len(drops) > 1 else ''} Now Cheaper!"

            return self._send_email(
                to_email=recipient,
                subject=subject,
                html_content=html_content,
            )

        except Exception as e:
            logger.error(f"Failed to send price drop alert: {e}", exc_info=True)
            return False

    def _generate_simple_html(self, drops: List[Dict], threshold: float) -> str:
        """Generate simple HTML email when template is not available."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .container {{
                    background-color: white;
                    border-radius: 10px;
                    padding: 30px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .header {{
                    text-align: center;
                    padding-bottom: 20px;
                    border-bottom: 3px solid #28a745;
                }}
                .header h1 {{
                    color: #28a745;
                    margin: 0;
                    font-size: 28px;
                }}
                .summary {{
                    background-color: #e8f5e9;
                    padding: 15px;
                    border-radius: 5px;
                    margin: 20px 0;
                    text-align: center;
                }}
                .deal {{
                    border-left: 4px solid #28a745;
                    margin: 20px 0;
                    padding: 15px;
                    background-color: #f9f9f9;
                    border-radius: 5px;
                }}
                .deal-header {{
                    font-size: 20px;
                    font-weight: bold;
                    color: #2c3e50;
                    margin-bottom: 10px;
                }}
                .price-info {{
                    display: flex;
                    justify-content: space-between;
                    margin: 10px 0;
                }}
                .price-current {{
                    font-size: 24px;
                    font-weight: bold;
                    color: #28a745;
                }}
                .price-old {{
                    font-size: 18px;
                    color: #999;
                    text-decoration: line-through;
                }}
                .savings {{
                    background-color: #28a745;
                    color: white;
                    padding: 5px 15px;
                    border-radius: 20px;
                    font-weight: bold;
                    display: inline-block;
                    margin-top: 10px;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #ddd;
                    color: #666;
                    font-size: 14px;
                }}
                .source {{
                    display: inline-block;
                    background-color: #007bff;
                    color: white;
                    padding: 3px 10px;
                    border-radius: 3px;
                    font-size: 12px;
                    margin-top: 5px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎯 Price Drop Alert!</h1>
                    <p>We found {len(drops)} significant price drop{'s' if len(drops) > 1 else ''}</p>
                </div>

                <div class="summary">
                    <p><strong>{len(drops)}</strong> flight route{'s have' if len(drops) > 1 else ' has'}
                    dropped by <strong>{threshold}%</strong> or more!</p>
                    <p>Book now to save on your next trip!</p>
                </div>
        """

        for drop in drops:
            html += f"""
                <div class="deal">
                    <div class="deal-header">{drop['route']}</div>
                    <span class="source">{drop['source'].upper()}</span>
                    <div class="price-info">
                        <div>
                            <div class="price-current">€{drop['current_price']:.0f}</div>
                            <div class="price-old">was €{drop['previous_avg_price']:.0f}</div>
                        </div>
                        <div style="text-align: right;">
                            <span class="savings">Save €{drop['drop_amount']:.0f} ({drop['drop_percent']:.1f}%)</span>
                        </div>
                    </div>
                </div>
            """

        html += """
                <div class="footer">
                    <p>This is an automated price alert from SmartFamilyTravelScout.</p>
                    <p>Prices are per person and change frequently. Book soon to lock in these deals!</p>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    def _send_email(self, to_email: str, subject: str, html_content: str) -> bool:
        """
        Send email via SMTP.

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML email content

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = to_email

            # Attach HTML content
            html_part = MIMEText(html_content, "html")
            msg.attach(html_part)

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Price drop alert sent successfully to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}", exc_info=True)
            return False

    def send_price_drop_alert_sync(
        self,
        drops: List[Dict],
        to_email: Optional[str] = None,
        threshold_percent: float = 10.0,
    ) -> bool:
        """
        Send price drop alert email (synchronous version for Celery tasks).

        Args:
            drops: List of price drop dictionaries
            to_email: Recipient email (defaults to user_email)
            threshold_percent: Minimum price drop percentage

        Returns:
            True if email sent successfully, False otherwise
        """
        if not drops:
            logger.info("No price drops to notify")
            return False

        recipient = to_email or self.user_email
        if not recipient:
            logger.error("No recipient email provided for price drop alert")
            return False

        try:
            html_content = self._generate_simple_html(drops, threshold_percent)
            subject = f"🎯 Price Drop Alert: {len(drops)} Flight{'s' if len(drops) > 1 else ''} Now Cheaper!"

            return self._send_email(
                to_email=recipient,
                subject=subject,
                html_content=html_content,
            )

        except Exception as e:
            logger.error(f"Failed to send price drop alert: {e}", exc_info=True)
            return False
