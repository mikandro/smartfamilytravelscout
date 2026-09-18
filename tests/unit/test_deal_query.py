"""
Unit tests for the deal query seam.

"What counts as a good deal" was implemented eleven times with five different
thresholds, and the "unnotified / recent" guards existed only in the
notification paths -- so a route and a notifier asking the same question got
different answers.
"""

from datetime import datetime, timedelta

import pytest

from app.config import settings
from app.domain.deal_query import (
    EXCELLENT_DEAL_SCORE,
    GOOD_DEAL_SCORE,
    ORDER_BY_DEPARTURE,
    ORDER_BY_PRICE,
    DealCriteria,
    build_deal_query,
    is_excellent_deal,
    is_good_deal,
)
from app.models.trip_package import TripPackage

pytestmark = pytest.mark.unit


def _sql(criteria) -> str:
    return str(build_deal_query(criteria)).lower()


class TestThresholdConstants:
    def test_good_is_seventy(self):
        """The value that was hardcoded in three route modules."""
        assert GOOD_DEAL_SCORE == 70.0

    def test_excellent_is_eighty(self):
        """The value that was hardcoded in the CLI's row styling."""
        assert EXCELLENT_DEAL_SCORE == 80.0

    def test_excellent_is_stricter_than_good(self):
        assert EXCELLENT_DEAL_SCORE > GOOD_DEAL_SCORE


class TestPredicates:
    def test_good_deal_needs_a_score(self):
        assert not is_good_deal(TripPackage(ai_score=None))

    def test_good_deal_at_the_threshold(self):
        assert is_good_deal(TripPackage(ai_score=70.0))

    def test_below_the_threshold(self):
        assert not is_good_deal(TripPackage(ai_score=69.9))

    def test_excellent_deal(self):
        assert is_excellent_deal(TripPackage(ai_score=85.0))
        assert not is_excellent_deal(TripPackage(ai_score=79.0))


class TestCriteriaPresets:
    def test_good_deals_uses_the_good_threshold(self):
        assert DealCriteria.good_deals().min_score == GOOD_DEAL_SCORE

    def test_all_packages_includes_unscored(self):
        """`scout packages` differs from `scout deals` precisely here."""
        assert DealCriteria.all_packages().min_score is None

    def test_digest_uses_the_notification_threshold(self):
        assert (
            DealCriteria.daily_digest().min_score
            == settings.notification_threshold
        )

    def test_digest_only_considers_unnotified_recent_packages(self):
        criteria = DealCriteria.daily_digest()
        assert criteria.unnotified_only is True
        assert criteria.since is not None

    def test_alerts_use_the_stricter_alert_threshold(self):
        assert (
            DealCriteria.immediate_alerts().min_score
            == settings.notification_alert_threshold
        )

    def test_alerts_are_stricter_than_the_digest(self):
        """The two settings keys are deliberately different, not a bug."""
        assert (
            DealCriteria.immediate_alerts().min_score
            >= DealCriteria.daily_digest().min_score
        )


class TestQueryConstruction:
    def test_score_filter_is_applied(self):
        assert "ai_score" in _sql(DealCriteria(min_score=70))

    def test_no_score_filter_when_min_score_is_none(self):
        sql = _sql(DealCriteria(min_score=None))
        assert "ai_score >=" not in sql

    def test_unnotified_filter(self):
        assert "notified" in _sql(DealCriteria(unnotified_only=True))

    def test_since_filter(self):
        sql = _sql(DealCriteria(since=datetime.now() - timedelta(days=1)))
        assert "created_at" in sql

    def test_max_price_filter(self):
        assert "total_price <=" in _sql(DealCriteria(max_price=1500.0))

    def test_destination_filter(self):
        assert "destination_city" in _sql(DealCriteria(destination_city="Lisbon"))

    def test_limit_is_applied(self):
        assert "limit" in _sql(DealCriteria(limit=10))

    def test_orders_by_score_by_default(self):
        sql = _sql(DealCriteria())
        assert "order by" in sql
        assert "ai_score desc" in sql

    def test_can_order_by_price(self):
        assert "total_price asc" in _sql(DealCriteria(order_by=ORDER_BY_PRICE))

    def test_can_order_by_departure(self):
        assert "departure_date asc" in _sql(DealCriteria(order_by=ORDER_BY_DEPARTURE))

    def test_eager_loading_can_be_turned_off_for_counts(self):
        # Should build without error and without the relationship option.
        build_deal_query(DealCriteria(), eager=False)


class TestCriteriaIsAValue:
    def test_is_immutable(self):
        with pytest.raises(Exception):
            DealCriteria().min_score = 10

    def test_equal_criteria_compare_equal(self):
        assert DealCriteria(min_score=70) == DealCriteria(min_score=70)
