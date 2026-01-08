"""
Tests for web dashboard routes.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime

from app.api.routes.web import get_stats


class TestGetStats:
    """Test get_stats helper function."""

    @pytest.mark.asyncio
    async def test_get_stats_success(self):
        """Test successful stats retrieval."""
        # Create mock database session
        mock_db = AsyncMock()

        # Mock scalar returns for different queries
        mock_db.scalar = AsyncMock()
        mock_db.scalar.side_effect = [
            10,  # total_packages
            7,   # high_score_packages
            75.5,  # avg_score
            1500.0,  # avg_price
            5,   # unique_destinations
        ]

        # Execute
        stats = await get_stats(mock_db)

        # Verify
        assert stats["total_packages"] == 10
        assert stats["high_score_packages"] == 7
        assert stats["avg_score"] == 75.5
        assert stats["avg_price"] == 1500
        assert stats["unique_destinations"] == 5

    @pytest.mark.asyncio
    async def test_get_stats_with_none_values(self):
        """Test stats when values are None."""
        mock_db = AsyncMock()

        # Mock scalar returns with None values
        mock_db.scalar = AsyncMock()
        mock_db.scalar.side_effect = [None, None, None, None, None]

        # Execute
        stats = await get_stats(mock_db)

        # Verify defaults are used
        assert stats["total_packages"] == 0
        assert stats["high_score_packages"] == 0
        assert stats["avg_score"] == 0
        assert stats["avg_price"] == 0
        assert stats["unique_destinations"] == 0

    @pytest.mark.asyncio
    async def test_get_stats_rounds_correctly(self):
        """Test that stats are rounded correctly."""
        mock_db = AsyncMock()

        mock_db.scalar = AsyncMock()
        mock_db.scalar.side_effect = [
            10,  # total_packages
            7,   # high_score_packages
            75.789,  # avg_score - should round to 75.8
            1599.99,  # avg_price - should round to 1600
            5,   # unique_destinations
        ]

        # Execute
        stats = await get_stats(mock_db)

        # Verify rounding
        assert stats["avg_score"] == 75.8
        assert stats["avg_price"] == 1600

    @pytest.mark.asyncio
    async def test_get_stats_handles_exception(self):
        """Test stats returns defaults on exception."""
        mock_db = AsyncMock()
        mock_db.scalar = AsyncMock(side_effect=Exception("Database error"))

        # Execute
        stats = await get_stats(mock_db)

        # Verify defaults on error
        assert stats["total_packages"] == 0
        assert stats["high_score_packages"] == 0
        assert stats["avg_score"] == 0
        assert stats["avg_price"] == 0
        assert stats["unique_destinations"] == 0


class TestDashboardRoute:
    """Test dashboard route."""

    @pytest.mark.asyncio
    async def test_dashboard_renders_template(self):
        """Test that dashboard route renders template."""
        from app.api.routes.web import dashboard
        from fastapi import Request

        # Create mock request
        mock_request = Mock(spec=Request)

        # Mock database and template
        with patch('app.api.routes.web.AsyncSessionLocal') as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db

            # Mock execute to return deals
            mock_result = AsyncMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_db.execute = AsyncMock(return_value=mock_result)

            # Mock scalar for stats
            mock_db.scalar = AsyncMock(side_effect=[0, 0, None, None, 0])

            # Mock templates
            with patch('app.api.routes.web.templates') as mock_templates:
                mock_templates.TemplateResponse = Mock()

                # Execute
                await dashboard(mock_request)

                # Verify template was called
                mock_templates.TemplateResponse.assert_called_once()
                call_args = mock_templates.TemplateResponse.call_args
                assert call_args[0][0] == "dashboard.html"
                assert "request" in call_args[0][1]
                assert "deals" in call_args[0][1]
                assert "stats" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_dashboard_handles_database_error(self):
        """Test dashboard handles database errors gracefully."""
        from app.api.routes.web import dashboard
        from fastapi import Request

        mock_request = Mock(spec=Request)

        with patch('app.api.routes.web.AsyncSessionLocal') as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db

            # Make execute raise an exception
            mock_db.execute = AsyncMock(side_effect=Exception("DB error"))

            with patch('app.api.routes.web.templates') as mock_templates:
                mock_templates.TemplateResponse = Mock()

                # Execute
                await dashboard(mock_request)

                # Verify template was called with error
                mock_templates.TemplateResponse.assert_called_once()
                call_args = mock_templates.TemplateResponse.call_args
                assert "error" in call_args[0][1]


class TestDealsRoute:
    """Test deals list route."""

    @pytest.mark.asyncio
    async def test_deals_page_no_filters(self):
        """Test deals page without filters."""
        from app.api.routes.web import deals_page
        from fastapi import Request

        mock_request = Mock(spec=Request)

        with patch('app.api.routes.web.AsyncSessionLocal') as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db

            # Mock execute to return deals
            mock_result = AsyncMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_db.execute = AsyncMock(return_value=mock_result)

            with patch('app.api.routes.web.templates') as mock_templates:
                mock_templates.TemplateResponse = Mock()

                # Execute
                await deals_page(mock_request)

                # Verify
                mock_templates.TemplateResponse.assert_called_once()
                call_args = mock_templates.TemplateResponse.call_args
                assert call_args[0][0] == "deals.html"

    @pytest.mark.asyncio
    async def test_deals_page_with_min_score_filter(self):
        """Test deals page with min score filter."""
        from app.api.routes.web import deals_page
        from fastapi import Request

        mock_request = Mock(spec=Request)

        with patch('app.api.routes.web.AsyncSessionLocal') as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db

            mock_result = AsyncMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_db.execute = AsyncMock(return_value=mock_result)

            with patch('app.api.routes.web.templates') as mock_templates:
                mock_templates.TemplateResponse = Mock()

                # Execute with filter
                await deals_page(mock_request, min_score=80)

                # Verify filters were applied
                call_args = mock_templates.TemplateResponse.call_args
                assert call_args[0][1]["filters"]["min_score"] == 80

    @pytest.mark.asyncio
    async def test_deals_page_with_destination_filter(self):
        """Test deals page with destination filter."""
        from app.api.routes.web import deals_page
        from fastapi import Request

        mock_request = Mock(spec=Request)

        with patch('app.api.routes.web.AsyncSessionLocal') as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db

            mock_result = AsyncMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_db.execute = AsyncMock(return_value=mock_result)

            with patch('app.api.routes.web.templates') as mock_templates:
                mock_templates.TemplateResponse = Mock()

                # Execute with destination filter
                await deals_page(mock_request, destination="Barcelona")

                # Verify filters were applied
                call_args = mock_templates.TemplateResponse.call_args
                assert call_args[0][1]["filters"]["destination"] == "Barcelona"

    @pytest.mark.asyncio
    async def test_deals_page_with_price_filters(self):
        """Test deals page with price filters."""
        from app.api.routes.web import deals_page
        from fastapi import Request

        mock_request = Mock(spec=Request)

        with patch('app.api.routes.web.AsyncSessionLocal') as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db

            mock_result = AsyncMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_db.execute = AsyncMock(return_value=mock_result)

            with patch('app.api.routes.web.templates') as mock_templates:
                mock_templates.TemplateResponse = Mock()

                # Execute with price filters
                await deals_page(mock_request, min_price=500, max_price=2000)

                # Verify filters were applied
                call_args = mock_templates.TemplateResponse.call_args
                assert call_args[0][1]["filters"]["min_price"] == 500
                assert call_args[0][1]["filters"]["max_price"] == 2000

    @pytest.mark.asyncio
    async def test_deals_page_handles_error(self):
        """Test deals page handles errors gracefully."""
        from app.api.routes.web import deals_page
        from fastapi import Request

        mock_request = Mock(spec=Request)

        with patch('app.api.routes.web.AsyncSessionLocal') as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db

            # Make execute raise an exception
            mock_db.execute = AsyncMock(side_effect=Exception("DB error"))

            with patch('app.api.routes.web.templates') as mock_templates:
                mock_templates.TemplateResponse = Mock()

                # Execute
                await deals_page(mock_request)

                # Verify error handling
                call_args = mock_templates.TemplateResponse.call_args
                assert "error" in call_args[0][1]


class TestDealDetailsRoute:
    """Test deal details route."""

    @pytest.mark.asyncio
    async def test_deal_details_found(self):
        """Test deal details when deal exists."""
        from app.api.routes.web import deal_details
        from fastapi import Request

        mock_request = Mock(spec=Request)

        with patch('app.api.routes.web.AsyncSessionLocal') as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db

            # Mock deal result
            mock_deal = Mock()
            mock_deal.destination_city = "Barcelona"
            mock_deal.accommodation_id = None

            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = mock_deal
            mock_db.execute = AsyncMock(return_value=mock_result)

            with patch('app.api.routes.web.templates') as mock_templates:
                mock_templates.TemplateResponse = Mock()

                # Execute
                await deal_details(mock_request, package_id=1)

                # Verify
                call_args = mock_templates.TemplateResponse.call_args
                assert call_args[0][0] == "deal_details.html"
                assert "deal" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_deal_details_not_found(self):
        """Test deal details when deal doesn't exist."""
        from app.api.routes.web import deal_details
        from fastapi import Request

        mock_request = Mock(spec=Request)

        with patch('app.api.routes.web.AsyncSessionLocal') as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db

            # Mock no deal found
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute = AsyncMock(return_value=mock_result)

            with patch('app.api.routes.web.templates') as mock_templates:
                mock_templates.TemplateResponse = Mock()

                # Execute
                await deal_details(mock_request, package_id=999)

                # Verify error template
                call_args = mock_templates.TemplateResponse.call_args
                assert call_args[0][0] == "error.html"
                assert "error" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_deal_details_with_accommodation(self):
        """Test deal details with accommodation."""
        from app.api.routes.web import deal_details
        from fastapi import Request

        mock_request = Mock(spec=Request)

        with patch('app.api.routes.web.AsyncSessionLocal') as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db

            # Mock deal with accommodation
            mock_deal = Mock()
            mock_deal.destination_city = "Barcelona"
            mock_deal.accommodation_id = 123

            mock_accommodation = Mock()

            # First execute for deal, second for accommodation
            mock_result1 = AsyncMock()
            mock_result1.scalar_one_or_none.return_value = mock_deal

            mock_result2 = AsyncMock()
            mock_result2.scalar_one_or_none.return_value = mock_accommodation

            mock_db.execute = AsyncMock(side_effect=[mock_result1, mock_result2])

            with patch('app.api.routes.web.templates') as mock_templates:
                mock_templates.TemplateResponse = Mock()

                # Execute
                await deal_details(mock_request, package_id=1)

                # Verify accommodation was fetched
                call_args = mock_templates.TemplateResponse.call_args
                assert "accommodation" in call_args[0][1]


class TestPreferencesRoutes:
    """Test preferences routes."""

    @pytest.mark.asyncio
    async def test_preferences_page_with_existing_prefs(self):
        """Test preferences page with existing preferences."""
        from app.api.routes.web import preferences_page
        from fastapi import Request

        mock_request = Mock(spec=Request)

        with patch('app.api.routes.web.AsyncSessionLocal') as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db

            # Mock existing preferences
            mock_prefs = Mock()
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = mock_prefs
            mock_db.execute = AsyncMock(return_value=mock_result)

            with patch('app.api.routes.web.templates') as mock_templates:
                mock_templates.TemplateResponse = Mock()

                # Execute
                await preferences_page(mock_request)

                # Verify
                call_args = mock_templates.TemplateResponse.call_args
                assert call_args[0][0] == "preferences.html"
                assert call_args[0][1]["preferences"] == mock_prefs

    @pytest.mark.asyncio
    async def test_preferences_page_creates_default(self):
        """Test preferences page creates default preferences."""
        from app.api.routes.web import preferences_page
        from fastapi import Request

        mock_request = Mock(spec=Request)

        with patch('app.api.routes.web.AsyncSessionLocal') as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db

            # Mock no existing preferences
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute = AsyncMock(return_value=mock_result)

            with patch('app.api.routes.web.templates') as mock_templates:
                with patch('app.api.routes.web.UserPreference') as mock_user_pref:
                    mock_templates.TemplateResponse = Mock()

                    # Execute
                    await preferences_page(mock_request)

                    # Verify default preferences were created
                    mock_user_pref.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_preferences_existing(self):
        """Test updating existing preferences."""
        from app.api.routes.web import update_preferences
        from fastapi import Request

        mock_request = Mock(spec=Request)

        with patch('app.api.routes.web.AsyncSessionLocal') as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db

            # Mock existing preferences
            mock_prefs = Mock()
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = mock_prefs
            mock_db.execute = AsyncMock(return_value=mock_result)
            mock_db.commit = AsyncMock()

            with patch('app.api.routes.web.templates') as mock_templates:
                mock_templates.TemplateResponse = Mock()

                # Execute
                await update_preferences(
                    mock_request,
                    max_flight_price_family=800,
                    max_flight_price_parents=600,
                    max_total_budget_family=2000,
                    notification_threshold=70,
                    parent_escape_frequency="monthly",
                )

                # Verify preferences were updated
                assert mock_prefs.max_flight_price_family == 800
                assert mock_prefs.max_flight_price_parents == 600
                mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_preferences_creates_new(self):
        """Test creating new preferences."""
        from app.api.routes.web import update_preferences
        from fastapi import Request

        mock_request = Mock(spec=Request)

        with patch('app.api.routes.web.AsyncSessionLocal') as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db

            # Mock no existing preferences
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute = AsyncMock(return_value=mock_result)
            mock_db.add = Mock()
            mock_db.commit = AsyncMock()

            with patch('app.api.routes.web.templates') as mock_templates:
                with patch('app.api.routes.web.UserPreference') as mock_user_pref:
                    mock_templates.TemplateResponse = Mock()
                    mock_user_pref.return_value = Mock()

                    # Execute
                    await update_preferences(
                        mock_request,
                        max_flight_price_family=800,
                        max_flight_price_parents=600,
                        max_total_budget_family=2000,
                        notification_threshold=70,
                        parent_escape_frequency="monthly",
                    )

                    # Verify new preferences were created
                    mock_user_pref.assert_called_once()
                    mock_db.add.assert_called_once()


class TestStatsRoute:
    """Test statistics route."""

    @pytest.mark.asyncio
    async def test_stats_page_success(self):
        """Test stats page loads successfully."""
        from app.api.routes.web import stats_page
        from fastapi import Request

        mock_request = Mock(spec=Request)

        with patch('app.api.routes.web.AsyncSessionLocal') as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db

            # Mock database queries
            mock_result = AsyncMock()
            mock_result.all.return_value = []
            mock_result.scalars.return_value.all.return_value = []
            mock_db.execute = AsyncMock(return_value=mock_result)
            mock_db.scalar = AsyncMock(side_effect=[0, 0, None, None, 0])

            with patch('app.api.routes.web.templates') as mock_templates:
                mock_templates.TemplateResponse = Mock()

                # Execute
                await stats_page(mock_request)

                # Verify
                call_args = mock_templates.TemplateResponse.call_args
                assert call_args[0][0] == "stats.html"
                assert "stats" in call_args[0][1]
                assert "price_data" in call_args[0][1]
                assert "score_data" in call_args[0][1]
                assert "top_destinations" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_stats_page_handles_error(self):
        """Test stats page handles errors gracefully."""
        from app.api.routes.web import stats_page
        from fastapi import Request

        mock_request = Mock(spec=Request)

        with patch('app.api.routes.web.AsyncSessionLocal') as mock_session:
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db

            # Make execute raise an exception
            mock_db.execute = AsyncMock(side_effect=Exception("DB error"))

            with patch('app.api.routes.web.templates') as mock_templates:
                mock_templates.TemplateResponse = Mock()

                # Execute
                await stats_page(mock_request)

                # Verify error handling
                call_args = mock_templates.TemplateResponse.call_args
                assert "error" in call_args[0][1]
