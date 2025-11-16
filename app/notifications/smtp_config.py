"""
SMTP configuration presets for common email providers.
Supports Gmail, SendGrid, Mailgun, and custom SMTP servers.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class SMTPConfig:
    """SMTP server configuration."""

    host: str
    port: int
    use_tls: bool = True
    use_ssl: bool = False
    timeout: int = 30

    def __repr__(self) -> str:
        return f"SMTPConfig(host='{self.host}', port={self.port}, use_tls={self.use_tls})"


# Predefined SMTP configurations for popular providers
SMTP_PROVIDERS = {
    "gmail": SMTPConfig(
        host="smtp.gmail.com",
        port=587,
        use_tls=True,
        use_ssl=False,
    ),
    "gmail_ssl": SMTPConfig(
        host="smtp.gmail.com",
        port=465,
        use_tls=False,
        use_ssl=True,
    ),
    "sendgrid": SMTPConfig(
        host="smtp.sendgrid.net",
        port=587,
        use_tls=True,
        use_ssl=False,
    ),
    "mailgun": SMTPConfig(
        host="smtp.mailgun.org",
        port=587,
        use_tls=True,
        use_ssl=False,
    ),
    "mailgun_eu": SMTPConfig(
        host="smtp.eu.mailgun.org",
        port=587,
        use_tls=True,
        use_ssl=False,
    ),
    "outlook": SMTPConfig(
        host="smtp-mail.outlook.com",
        port=587,
        use_tls=True,
        use_ssl=False,
    ),
    "office365": SMTPConfig(
        host="smtp.office365.com",
        port=587,
        use_tls=True,
        use_ssl=False,
    ),
    "yahoo": SMTPConfig(
        host="smtp.mail.yahoo.com",
        port=587,
        use_tls=True,
        use_ssl=False,
    ),
    "amazon_ses_us_east": SMTPConfig(
        host="email-smtp.us-east-1.amazonaws.com",
        port=587,
        use_tls=True,
        use_ssl=False,
    ),
    "amazon_ses_eu_west": SMTPConfig(
        host="email-smtp.eu-west-1.amazonaws.com",
        port=587,
        use_tls=True,
        use_ssl=False,
    ),
}


def get_smtp_config(provider: str) -> Optional[SMTPConfig]:
    """
    Get SMTP configuration for a known provider.

    Args:
        provider: Provider name (gmail, sendgrid, mailgun, etc.)

    Returns:
        SMTPConfig if provider is known, None otherwise

    Example:
        >>> config = get_smtp_config('gmail')
        >>> print(config.host, config.port)
        smtp.gmail.com 587
    """
    return SMTP_PROVIDERS.get(provider.lower())


def create_custom_smtp_config(
    host: str,
    port: int = 587,
    use_tls: bool = True,
    use_ssl: bool = False,
    timeout: int = 30,
) -> SMTPConfig:
    """
    Create custom SMTP configuration.

    Args:
        host: SMTP server hostname
        port: SMTP server port (default: 587)
        use_tls: Use STARTTLS (default: True)
        use_ssl: Use SSL/TLS from start (default: False)
        timeout: Connection timeout in seconds (default: 30)

    Returns:
        SMTPConfig instance

    Example:
        >>> config = create_custom_smtp_config('smtp.example.com', port=465, use_ssl=True)
        >>> print(config)
        SMTPConfig(host='smtp.example.com', port=465, use_tls=False)
    """
    return SMTPConfig(
        host=host,
        port=port,
        use_tls=use_tls,
        use_ssl=use_ssl,
        timeout=timeout,
    )


def get_provider_instructions(provider: str) -> str:
    """
    Get setup instructions for a specific email provider.

    Args:
        provider: Provider name

    Returns:
        Setup instructions as string
    """
    instructions = {
        "gmail": """
        Gmail SMTP Setup:
        1. Enable 2-factor authentication on your Google account
        2. Generate an app-specific password:
           - Go to https://myaccount.google.com/apppasswords
           - Select 'Mail' and your device
           - Copy the generated 16-character password
        3. Use this password (not your regular Gmail password) for smtp_password
        4. Set smtp_user to your full Gmail address (e.g., user@gmail.com)
        """,
        "sendgrid": """
        SendGrid SMTP Setup:
        1. Sign up for SendGrid at https://sendgrid.com
        2. Create an API key:
           - Go to Settings > API Keys
           - Create a new API key with 'Mail Send' permissions
        3. Set smtp_user to 'apikey' (literally the string 'apikey')
        4. Set smtp_password to your API key
        5. Verify your sender email address in SendGrid
        """,
        "mailgun": """
        Mailgun SMTP Setup:
        1. Sign up for Mailgun at https://mailgun.com
        2. Add and verify your domain
        3. Get SMTP credentials:
           - Go to Sending > Domain Settings > SMTP credentials
           - Create SMTP credentials or use default
        4. Set smtp_user to your SMTP username (postmaster@yourdomain.com)
        5. Set smtp_password to your SMTP password
        6. Choose mailgun (US) or mailgun_eu (Europe) based on your region
        """,
        "outlook": """
        Outlook/Hotmail SMTP Setup:
        1. Use your Outlook.com or Hotmail.com email address
        2. Set smtp_user to your full email address
        3. Set smtp_password to your account password
        4. If you have 2FA enabled, generate an app password:
           - Go to Security > Advanced security options
           - Create an app password
        """,
    }

    return instructions.get(provider.lower(), "No specific instructions available for this provider.")


# Email validation helpers
def is_valid_email(email: str) -> bool:
    """
    Basic email validation.

    Args:
        email: Email address to validate

    Returns:
        True if email appears valid, False otherwise
    """
    import re

    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def get_email_domain(email: str) -> Optional[str]:
    """
    Extract domain from email address.

    Args:
        email: Email address

    Returns:
        Domain part of email, or None if invalid

    Example:
        >>> get_email_domain('user@example.com')
        'example.com'
    """
    if "@" in email:
        return email.split("@")[1].lower()
    return None


def suggest_provider_from_email(email: str) -> Optional[str]:
    """
    Suggest SMTP provider based on email domain.

    Args:
        email: Email address

    Returns:
        Suggested provider name, or None if unknown

    Example:
        >>> suggest_provider_from_email('user@gmail.com')
        'gmail'
    """
    domain = get_email_domain(email)
    if not domain:
        return None

    domain_mapping = {
        "gmail.com": "gmail",
        "googlemail.com": "gmail",
        "outlook.com": "outlook",
        "hotmail.com": "outlook",
        "live.com": "outlook",
        "yahoo.com": "yahoo",
        "yahoo.co.uk": "yahoo",
    }

    return domain_mapping.get(domain)
