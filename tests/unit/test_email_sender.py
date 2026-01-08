"""
Tests for email notification system.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import date, datetime
from pathlib import Path

from app.notifications.email_sender import EmailNotifier, create_email_notifier


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = Mock()
    settings.smtp_host = "smtp.example.com"
    settings.smtp_port = 587
    settings.smtp_user = "user@example.com"
    settings.smtp_password = "password"
    settings.smtp_from_email = "noreply@smarttravel.com"
    settings.smtp_from_name = "Smart Family Travel Scout"
    return settings


@pytest.fixture
def email_notifier(mock_settings):
    """Create EmailNotifier instance with mocked templates."""
    with patch('app.notifications.email_sender.Environment') as mock_env:
        mock_template_env = Mock()
        mock_env.return_value = mock_template_env

        notifier = EmailNotifier(settings=mock_settings, user_email="test@example.com")
        notifier.template_env = mock_template_env

        return notifier


@pytest.fixture
def sample_deal():
    """Create a sample trip package for testing."""
    deal = Mock()
    deal.id = 1
    deal.destination_city = "Barcelona"
    deal.ai_score = 90.0
    deal.total_price = 1500.0
    deal.departure_date = date(2025, 6, 1)
    deal.return_date = date(2025, 6, 7)
    return deal


@pytest.fixture
def sample_deals():
    """Create multiple sample deals."""
    deals = []
    cities = ["Barcelona", "Lisbon", "Prague", "Paris", "Rome"]
    scores = [95.0, 88.0, 82.0, 76.0, 71.0]

    for i, (city, score) in enumerate(zip(cities, scores)):
        deal = Mock()
        deal.id = i + 1
        deal.destination_city = city
        deal.ai_score = score
        deal.total_price = 1200.0 + (i * 100)
        deal.departure_date = date(2025, 6, 1)
        deal.return_date = date(2025, 6, 7)
        deals.append(deal)

    return deals


class TestEmailNotifierInit:
    """Test EmailNotifier initialization."""

    def test_init_with_settings(self, mock_settings):
        """Test initialization with settings."""
        with patch('app.notifications.email_sender.Environment'):
            notifier = EmailNotifier(settings=mock_settings, user_email="test@example.com")

            assert notifier.smtp_host == "smtp.example.com"
            assert notifier.smtp_port == 587
            assert notifier.smtp_user == "user@example.com"
            assert notifier.smtp_password == "password"
            assert notifier.from_email == "noreply@smarttravel.com"
            assert notifier.from_name == "Smart Family Travel Scout"
            assert notifier.user_email == "test@example.com"

    def test_init_creates_template_environment(self, mock_settings):
        """Test that Jinja2 environment is created."""
        with patch('app.notifications.email_sender.Environment') as mock_env:
            EmailNotifier(settings=mock_settings)

            mock_env.assert_called_once()

    def test_init_registers_custom_filters(self, mock_settings):
        """Test that custom template filters are registered."""
        with patch('app.notifications.email_sender.Environment') as mock_env:
            mock_template_env = Mock()
            mock_template_env.filters = {}
            mock_env.return_value = mock_template_env

            EmailNotifier(settings=mock_settings)

            assert "round" in mock_template_env.filters
            assert "format_date" in mock_template_env.filters
            assert "format_price" in mock_template_env.filters


class TestFormatters:
    """Test formatting helper methods."""

    def test_format_date(self, email_notifier):
        """Test date formatting."""
        test_date = date(2025, 6, 15)
        formatted = email_notifier._format_date(test_date)

        assert formatted == "June 15, 2025"

    def test_format_price(self, email_notifier):
        """Test price formatting."""
        price = 1234.56
        formatted = email_notifier._format_price(price)

        assert formatted == "€1234.56"

    def test_format_price_rounds_correctly(self, email_notifier):
        """Test price formatting rounds to 2 decimals."""
        price = 1234.567
        formatted = email_notifier._format_price(price)

        assert formatted == "€1234.57"


class TestSendDailyDigest:
    """Test sending daily digest emails."""

    @pytest.mark.asyncio
    async def test_send_daily_digest_success(self, email_notifier, sample_deals):
        """Test successful daily digest send."""
        # Mock template
        mock_template = Mock()
        mock_template.render.return_value = "<html>Daily Digest</html>"
        email_notifier.template_env.get_template.return_value = mock_template

        # Mock send_email
        email_notifier.send_email = Mock(return_value=True)

        # Execute
        result = await email_notifier.send_daily_digest(sample_deals)

        # Verify
        assert result is True
        email_notifier.send_email.assert_called_once()
        call_args = email_notifier.send_email.call_args
        assert call_args[1]["to_email"] == "test@example.com"
        assert "Daily Travel Deals" in call_args[1]["subject"]

    @pytest.mark.asyncio
    async def test_send_daily_digest_no_deals(self, email_notifier):
        """Test daily digest with no deals."""
        result = await email_notifier.send_daily_digest([])

        assert result is False

    @pytest.mark.asyncio
    async def test_send_daily_digest_no_recipient(self, mock_settings):
        """Test daily digest without recipient email."""
        with patch('app.notifications.email_sender.Environment'):
            notifier = EmailNotifier(settings=mock_settings, user_email=None)

            result = await notifier.send_daily_digest([Mock()])

            assert result is False

    @pytest.mark.asyncio
    async def test_send_daily_digest_sorts_by_score(self, email_notifier, sample_deals):
        """Test that daily digest sorts deals by score."""
        mock_template = Mock()
        mock_template.render.return_value = "<html>Digest</html>"
        email_notifier.template_env.get_template.return_value = mock_template

        email_notifier.send_email = Mock(return_value=True)

        await email_notifier.send_daily_digest(sample_deals)

        # Verify render was called with sorted deals
        render_call = mock_template.render.call_args
        rendered_deals = render_call[1]["deals"]

        # Should be top 5 deals sorted by score
        assert len(rendered_deals) <= 5
        # First deal should have highest score
        assert rendered_deals[0].ai_score >= rendered_deals[-1].ai_score

    @pytest.mark.asyncio
    async def test_send_daily_digest_limits_to_top_5(self, email_notifier):
        """Test daily digest limits to top 5 deals."""
        # Create 10 deals
        many_deals = []
        for i in range(10):
            deal = Mock()
            deal.ai_score = 90.0 - i
            many_deals.append(deal)

        mock_template = Mock()
        mock_template.render.return_value = "<html>Digest</html>"
        email_notifier.template_env.get_template.return_value = mock_template

        email_notifier.send_email = Mock(return_value=True)

        await email_notifier.send_daily_digest(many_deals)

        # Verify only top 5 were rendered
        render_call = mock_template.render.call_args
        rendered_deals = render_call[1]["deals"]
        assert len(rendered_deals) == 5

    @pytest.mark.asyncio
    async def test_send_daily_digest_handles_exception(self, email_notifier, sample_deals):
        """Test daily digest handles exceptions gracefully."""
        email_notifier.template_env.get_template.side_effect = Exception("Template error")

        result = await email_notifier.send_daily_digest(sample_deals)

        assert result is False

    @pytest.mark.asyncio
    async def test_send_daily_digest_custom_recipient(self, email_notifier, sample_deals):
        """Test daily digest with custom recipient."""
        mock_template = Mock()
        mock_template.render.return_value = "<html>Digest</html>"
        email_notifier.template_env.get_template.return_value = mock_template

        email_notifier.send_email = Mock(return_value=True)

        await email_notifier.send_daily_digest(sample_deals, to_email="custom@example.com")

        # Verify custom email was used
        call_args = email_notifier.send_email.call_args
        assert call_args[1]["to_email"] == "custom@example.com"


class TestSendDealAlert:
    """Test sending deal alert emails."""

    @pytest.mark.asyncio
    async def test_send_deal_alert_success(self, email_notifier, sample_deal):
        """Test successful deal alert send."""
        sample_deal.ai_score = 90.0

        mock_template = Mock()
        mock_template.render.return_value = "<html>Deal Alert</html>"
        email_notifier.template_env.get_template.return_value = mock_template

        email_notifier.send_email = Mock(return_value=True)

        result = await email_notifier.send_deal_alert(sample_deal)

        assert result is True
        email_notifier.send_email.assert_called_once()
        call_args = email_notifier.send_email.call_args
        assert "Exceptional Deal Alert" in call_args[1]["subject"]
        assert "Barcelona" in call_args[1]["subject"]

    @pytest.mark.asyncio
    async def test_send_deal_alert_below_threshold(self, email_notifier, sample_deal):
        """Test deal alert with score below threshold."""
        sample_deal.ai_score = 80.0  # Below 85 threshold

        result = await email_notifier.send_deal_alert(sample_deal)

        assert result is False

    @pytest.mark.asyncio
    async def test_send_deal_alert_no_score(self, email_notifier, sample_deal):
        """Test deal alert with no AI score."""
        sample_deal.ai_score = None

        result = await email_notifier.send_deal_alert(sample_deal)

        assert result is False

    @pytest.mark.asyncio
    async def test_send_deal_alert_no_recipient(self, mock_settings, sample_deal):
        """Test deal alert without recipient."""
        with patch('app.notifications.email_sender.Environment'):
            notifier = EmailNotifier(settings=mock_settings, user_email=None)
            sample_deal.ai_score = 90.0

            result = await notifier.send_deal_alert(sample_deal)

            assert result is False

    @pytest.mark.asyncio
    async def test_send_deal_alert_handles_exception(self, email_notifier, sample_deal):
        """Test deal alert handles exceptions."""
        sample_deal.ai_score = 90.0
        email_notifier.template_env.get_template.side_effect = Exception("Template error")

        result = await email_notifier.send_deal_alert(sample_deal)

        assert result is False


class TestSendParentEscapeDigest:
    """Test sending parent escape digest emails."""

    @pytest.mark.asyncio
    async def test_send_parent_escape_success(self, email_notifier, sample_deals):
        """Test successful parent escape digest send."""
        mock_template = Mock()
        mock_template.render.return_value = "<html>Parent Escape</html>"
        email_notifier.template_env.get_template.return_value = mock_template

        email_notifier.send_email = Mock(return_value=True)

        result = await email_notifier.send_parent_escape_digest(sample_deals)

        assert result is True
        email_notifier.send_email.assert_called_once()
        call_args = email_notifier.send_email.call_args
        assert "Parent Escape Digest" in call_args[1]["subject"]

    @pytest.mark.asyncio
    async def test_send_parent_escape_no_getaways(self, email_notifier):
        """Test parent escape with no getaways."""
        result = await email_notifier.send_parent_escape_digest([])

        assert result is False

    @pytest.mark.asyncio
    async def test_send_parent_escape_sorts_by_score(self, email_notifier, sample_deals):
        """Test parent escape sorts getaways by score."""
        mock_template = Mock()
        mock_template.render.return_value = "<html>Escape</html>"
        email_notifier.template_env.get_template.return_value = mock_template

        email_notifier.send_email = Mock(return_value=True)

        await email_notifier.send_parent_escape_digest(sample_deals)

        render_call = mock_template.render.call_args
        rendered_getaways = render_call[1]["getaways"]

        assert len(rendered_getaways) <= 5
        assert rendered_getaways[0].ai_score >= rendered_getaways[-1].ai_score


class TestSendEmail:
    """Test low-level email sending."""

    def test_send_email_success(self, email_notifier):
        """Test successful email send via SMTP."""
        with patch('app.notifications.email_sender.smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            result = email_notifier.send_email(
                to_email="recipient@example.com",
                subject="Test Subject",
                html_body="<html>Test</html>",
            )

            assert result is True
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with("user@example.com", "password")
            mock_server.send_message.assert_called_once()

    def test_send_email_with_text_body(self, email_notifier):
        """Test email send with plain text fallback."""
        with patch('app.notifications.email_sender.smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            result = email_notifier.send_email(
                to_email="recipient@example.com",
                subject="Test Subject",
                html_body="<html>Test</html>",
                text_body="Plain text version",
            )

            assert result is True

    def test_send_email_no_credentials(self, mock_settings):
        """Test email send without SMTP credentials."""
        mock_settings.smtp_user = None
        mock_settings.smtp_password = None

        with patch('app.notifications.email_sender.Environment'):
            notifier = EmailNotifier(settings=mock_settings)

            result = notifier.send_email(
                to_email="test@example.com",
                subject="Test",
                html_body="<html>Test</html>",
            )

            assert result is False

    def test_send_email_authentication_error(self, email_notifier):
        """Test email send with authentication error."""
        with patch('app.notifications.email_sender.smtplib.SMTP') as mock_smtp:
            import smtplib
            mock_server = MagicMock()
            mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Authentication failed")
            mock_smtp.return_value.__enter__.return_value = mock_server

            result = email_notifier.send_email(
                to_email="test@example.com",
                subject="Test",
                html_body="<html>Test</html>",
            )

            assert result is False

    def test_send_email_smtp_exception(self, email_notifier):
        """Test email send with SMTP exception."""
        with patch('app.notifications.email_sender.smtplib.SMTP') as mock_smtp:
            import smtplib
            mock_server = MagicMock()
            mock_server.send_message.side_effect = smtplib.SMTPException("SMTP error")
            mock_smtp.return_value.__enter__.return_value = mock_server

            result = email_notifier.send_email(
                to_email="test@example.com",
                subject="Test",
                html_body="<html>Test</html>",
            )

            assert result is False

    def test_send_email_unexpected_exception(self, email_notifier):
        """Test email send with unexpected exception."""
        with patch('app.notifications.email_sender.smtplib.SMTP') as mock_smtp:
            mock_smtp.side_effect = Exception("Unexpected error")

            result = email_notifier.send_email(
                to_email="test@example.com",
                subject="Test",
                html_body="<html>Test</html>",
            )

            assert result is False


class TestPreviewMethods:
    """Test email preview methods."""

    def test_preview_daily_digest(self, email_notifier, sample_deals):
        """Test daily digest preview generation."""
        mock_template = Mock()
        mock_template.render.return_value = "<html>Preview</html>"
        email_notifier.template_env.get_template.return_value = mock_template

        html = email_notifier.preview_daily_digest(sample_deals)

        assert html == "<html>Preview</html>"
        mock_template.render.assert_called_once()

    def test_preview_daily_digest_error(self, email_notifier, sample_deals):
        """Test daily digest preview handles errors."""
        email_notifier.template_env.get_template.side_effect = Exception("Template error")

        html = email_notifier.preview_daily_digest(sample_deals)

        assert "Error generating preview" in html

    def test_preview_deal_alert(self, email_notifier, sample_deal):
        """Test deal alert preview generation."""
        mock_template = Mock()
        mock_template.render.return_value = "<html>Alert Preview</html>"
        email_notifier.template_env.get_template.return_value = mock_template

        html = email_notifier.preview_deal_alert(sample_deal)

        assert html == "<html>Alert Preview</html>"

    def test_preview_deal_alert_error(self, email_notifier, sample_deal):
        """Test deal alert preview handles errors."""
        email_notifier.template_env.get_template.side_effect = Exception("Template error")

        html = email_notifier.preview_deal_alert(sample_deal)

        assert "Error generating preview" in html

    def test_preview_parent_escape(self, email_notifier, sample_deals):
        """Test parent escape preview generation."""
        mock_template = Mock()
        mock_template.render.return_value = "<html>Escape Preview</html>"
        email_notifier.template_env.get_template.return_value = mock_template

        html = email_notifier.preview_parent_escape(sample_deals)

        assert html == "<html>Escape Preview</html>"

    def test_preview_parent_escape_error(self, email_notifier, sample_deals):
        """Test parent escape preview handles errors."""
        email_notifier.template_env.get_template.side_effect = Exception("Template error")

        html = email_notifier.preview_parent_escape(sample_deals)

        assert "Error generating preview" in html


class TestCreateEmailNotifier:
    """Test factory function."""

    def test_create_email_notifier_with_settings(self, mock_settings):
        """Test creating notifier with provided settings."""
        with patch('app.notifications.email_sender.Environment'):
            notifier = create_email_notifier(settings=mock_settings, user_email="test@example.com")

            assert isinstance(notifier, EmailNotifier)
            assert notifier.user_email == "test@example.com"

    def test_create_email_notifier_default_settings(self):
        """Test creating notifier with default settings."""
        with patch('app.notifications.email_sender.get_settings') as mock_get_settings:
            mock_settings = Mock()
            mock_settings.smtp_host = "smtp.example.com"
            mock_settings.smtp_port = 587
            mock_settings.smtp_user = "user@example.com"
            mock_settings.smtp_password = "password"
            mock_settings.smtp_from_email = "noreply@example.com"
            mock_settings.smtp_from_name = "Test"
            mock_get_settings.return_value = mock_settings

            with patch('app.notifications.email_sender.Environment'):
                notifier = create_email_notifier()

                assert isinstance(notifier, EmailNotifier)
                mock_get_settings.assert_called_once()
