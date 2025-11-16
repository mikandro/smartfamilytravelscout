"""
Unsubscribe handling for email notifications.
Provides functionality to manage user email preferences and unsubscribe requests.
"""

import hashlib
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class UnsubscribeToken:
    """Generate and verify unsubscribe tokens."""

    def __init__(self, secret_key: str):
        """
        Initialize unsubscribe token generator.

        Args:
            secret_key: Secret key for signing tokens
        """
        self.secret_key = secret_key

    def generate_token(self, email: str) -> str:
        """
        Generate unsubscribe token for an email address.

        Args:
            email: User's email address

        Returns:
            Unsubscribe token (hash)

        Example:
            >>> token_gen = UnsubscribeToken('secret')
            >>> token = token_gen.generate_token('user@example.com')
        """
        # Combine email with secret key and hash
        data = f"{email.lower()}:{self.secret_key}"
        token = hashlib.sha256(data.encode()).hexdigest()
        return token

    def verify_token(self, email: str, token: str) -> bool:
        """
        Verify that a token matches an email address.

        Args:
            email: User's email address
            token: Token to verify

        Returns:
            True if token is valid for email, False otherwise
        """
        expected_token = self.generate_token(email)
        return token == expected_token

    def generate_unsubscribe_url(
        self, email: str, base_url: str = "https://smartfamilytravelscout.com"
    ) -> str:
        """
        Generate complete unsubscribe URL for an email.

        Args:
            email: User's email address
            base_url: Base URL of the application

        Returns:
            Complete unsubscribe URL

        Example:
            >>> url = token_gen.generate_unsubscribe_url('user@example.com')
            >>> print(url)
            https://smartfamilytravelscout.com/unsubscribe?email=user@example.com&token=abc123...
        """
        token = self.generate_token(email)
        return f"{base_url}/unsubscribe?email={email}&token={token}"


class EmailPreferences:
    """
    Manage email notification preferences for users.

    In a real application, this would interact with a database table
    storing user preferences.
    """

    PREFERENCE_TYPES = {
        "daily_digest": "Daily travel deal digest",
        "deal_alerts": "Exceptional deal alerts (score ≥ 85)",
        "parent_escape": "Weekly parent escape digest",
        "all": "All email notifications",
    }

    def __init__(self):
        """Initialize email preferences manager."""
        # In production, this would use a database
        self._preferences = {}

    def get_preferences(self, email: str) -> dict:
        """
        Get email preferences for a user.

        Args:
            email: User's email address

        Returns:
            Dictionary of preferences

        Example:
            >>> prefs = email_prefs.get_preferences('user@example.com')
            >>> print(prefs['daily_digest'])
            True
        """
        default_preferences = {
            "daily_digest": True,
            "deal_alerts": True,
            "parent_escape": True,
            "unsubscribed_at": None,
        }

        return self._preferences.get(email.lower(), default_preferences)

    def update_preference(
        self, email: str, preference_type: str, enabled: bool
    ) -> bool:
        """
        Update a specific email preference.

        Args:
            email: User's email address
            preference_type: Type of preference to update
            enabled: Whether to enable or disable

        Returns:
            True if update was successful

        Example:
            >>> email_prefs.update_preference('user@example.com', 'daily_digest', False)
            True
        """
        if preference_type not in self.PREFERENCE_TYPES and preference_type != "all":
            logger.error(f"Invalid preference type: {preference_type}")
            return False

        email = email.lower()
        current_prefs = self.get_preferences(email)

        if preference_type == "all":
            # Update all preferences
            for pref in self.PREFERENCE_TYPES:
                if pref != "all":
                    current_prefs[pref] = enabled
        else:
            current_prefs[preference_type] = enabled

        self._preferences[email] = current_prefs

        logger.info(f"Updated preference {preference_type}={enabled} for {email}")
        return True

    def unsubscribe(self, email: str) -> bool:
        """
        Unsubscribe user from all emails.

        Args:
            email: User's email address

        Returns:
            True if unsubscribe was successful

        Example:
            >>> email_prefs.unsubscribe('user@example.com')
            True
        """
        email = email.lower()
        current_prefs = self.get_preferences(email)

        # Disable all email types
        for pref in self.PREFERENCE_TYPES:
            if pref != "all":
                current_prefs[pref] = False

        current_prefs["unsubscribed_at"] = datetime.utcnow().isoformat()

        self._preferences[email] = current_prefs

        logger.info(f"Unsubscribed user: {email}")
        return True

    def resubscribe(self, email: str) -> bool:
        """
        Resubscribe user to all emails.

        Args:
            email: User's email address

        Returns:
            True if resubscribe was successful
        """
        email = email.lower()
        current_prefs = self.get_preferences(email)

        # Enable all email types
        for pref in self.PREFERENCE_TYPES:
            if pref != "all":
                current_prefs[pref] = True

        current_prefs["unsubscribed_at"] = None

        self._preferences[email] = current_prefs

        logger.info(f"Resubscribed user: {email}")
        return True

    def is_subscribed(self, email: str, preference_type: str = "all") -> bool:
        """
        Check if user is subscribed to a specific email type.

        Args:
            email: User's email address
            preference_type: Type of email to check (default: 'all')

        Returns:
            True if user is subscribed

        Example:
            >>> if email_prefs.is_subscribed('user@example.com', 'daily_digest'):
            ...     send_daily_digest()
        """
        prefs = self.get_preferences(email.lower())

        if preference_type == "all":
            # Check if subscribed to any email type
            return any(prefs.get(pref, False) for pref in self.PREFERENCE_TYPES if pref != "all")

        return prefs.get(preference_type, False)


def create_unsubscribe_handler(secret_key: str) -> UnsubscribeToken:
    """
    Factory function to create unsubscribe token handler.

    Args:
        secret_key: Application secret key

    Returns:
        UnsubscribeToken instance

    Example:
        >>> from app.config import get_settings
        >>> settings = get_settings()
        >>> handler = create_unsubscribe_handler(settings.secret_key)
    """
    return UnsubscribeToken(secret_key)


# Global preferences manager instance
email_preferences = EmailPreferences()
