"""
Email notification system for SmartFamilyTravelScout.
"""

from app.notifications.email_sender import EmailNotifier, create_email_notifier
from app.notifications.smtp_config import (
    SMTPConfig,
    get_smtp_config,
    create_custom_smtp_config,
    get_provider_instructions,
    suggest_provider_from_email,
)

__all__ = [
    "EmailNotifier",
    "create_email_notifier",
    "SMTPConfig",
    "get_smtp_config",
    "create_custom_smtp_config",
    "get_provider_instructions",
    "suggest_provider_from_email",
]
