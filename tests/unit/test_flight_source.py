"""
Unit tests for the flight source seam.

These test the interface every source satisfies, and the normalisation that
used to be duplicated per-scraper inside the orchestrator's dispatch.
"""

from datetime import date, datetime, time

import pytest

from app.domain.party_size import COUPLE, FAMILY, PartySize
from app.scrapers.flight_source import (
    FLIGHT_SOURCE_ADAPTERS,
    FlightQuery,
    FlightSource,
    InMemoryFlightSource,
    KiwiSource,
    RyanairSource,
    SkyscannerSource,
    WizzAirSource,
    build_flight_sources,
    normalise_offer,
)
from app.scrapers.source_errors import (
    SourceBlocked,
    SourceCredentialsInvalid,
    SourceParseFailed,
    SourceRateLimited,
    SourceUnavailable,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def query():
    return FlightQuery(
        origin="MUC",
        destination="LIS",
        departure_date=date(2025, 12, 20),
        return_date=date(2025, 12, 27),
    )


class TestFlightQuery:
    def test_route_reads_naturally(self, query):
        assert query.route == "MUC-LIS"

    def test_defaults_to_a_family(self, query):
        assert query.party == FAMILY

    def test_is_hashable_and_comparable(self, query):
        same = FlightQuery(
            origin="MUC",
            destination="LIS",
            departure_date=date(2025, 12, 20),
            return_date=date(2025, 12, 27),
        )
        assert query == same


class TestNormalisation:
    """The ~40 lines that were duplicated per scraper in the old dispatch."""

    def test_fills_airports_from_the_query(self, query):
        """Skyscanner does not echo origin/destination."""
        offer = normalise_offer({"price_per_person": 100.0}, source="sky", query=query)
        assert offer["origin_airport"] == "MUC"
        assert offer["destination_airport"] == "LIS"

    def test_renames_origin_and_destination(self, query):
        """Ryanair and WizzAir return `origin`/`destination`."""
        offer = normalise_offer(
            {"origin": "FMM", "destination": "BCN"}, source="ryanair", query=query
        )
        assert offer["origin_airport"] == "FMM"
        assert offer["destination_airport"] == "BCN"
        assert "origin" not in offer

    def test_coerces_date_objects(self, query):
        offer = normalise_offer(
            {"departure_date": date(2025, 12, 20)}, source="x", query=query
        )
        assert offer["departure_date"] == "2025-12-20"

    def test_coerces_time_objects(self, query):
        offer = normalise_offer(
            {"departure_time": time(14, 30)}, source="x", query=query
        )
        assert offer["departure_time"] == "14:30"

    def test_coerces_datetime_objects(self, query):
        offer = normalise_offer(
            {"departure_date": datetime(2025, 12, 20, 14, 30)},
            source="x",
            query=query,
        )
        assert offer["departure_date"] == "2025-12-20"

    def test_promotes_price_to_price_per_person(self, query):
        offer = normalise_offer({"price": 89.99}, source="x", query=query)
        assert offer["price_per_person"] == 89.99

    def test_scales_total_by_party_size(self, query):
        offer = normalise_offer({"price": 100.0}, source="x", query=query)
        assert offer["total_price"] == 400.0  # family of four

    def test_party_size_is_not_hardcoded_to_four(self):
        """The old dispatch hardcoded `* 4`, wrong for a couple."""
        couple_query = FlightQuery(
            origin="MUC",
            destination="LIS",
            departure_date=date(2025, 12, 20),
            party=COUPLE,
        )
        offer = normalise_offer({"price": 100.0}, source="x", query=couple_query)
        assert offer["total_price"] == 200.0

    def test_does_not_overwrite_an_explicit_total(self, query):
        offer = normalise_offer(
            {"price_per_person": 100.0, "total_price": 350.0},
            source="x",
            query=query,
        )
        assert offer["total_price"] == 350.0

    def test_stamps_source_and_scraped_at(self, query):
        offer = normalise_offer({}, source="ryanair", query=query)
        assert offer["source"] == "ryanair"
        assert "scraped_at" in offer

    def test_fixed_airline_is_applied(self, query):
        offer = normalise_offer({}, source="ryanair", query=query, airline="Ryanair")
        assert offer["airline"] == "Ryanair"

    def test_does_not_mutate_the_input(self, query):
        raw = {"price": 50.0}
        normalise_offer(raw, source="x", query=query)
        assert raw == {"price": 50.0}


class TestInMemorySource:
    """The second adapter that makes the seam real rather than hypothetical."""

    async def test_satisfies_the_protocol(self):
        assert isinstance(InMemoryFlightSource(), FlightSource)

    async def test_returns_normalised_offers(self, query):
        source = InMemoryFlightSource(name="fake", offers=[{"price": 50.0}])
        offers = await source.search(query)
        assert offers[0]["source"] == "fake"
        assert offers[0]["origin_airport"] == "MUC"

    async def test_records_the_queries_it_received(self, query):
        source = InMemoryFlightSource()
        await source.search(query)
        assert source.calls == [query]

    async def test_raises_the_configured_error(self, query):
        source = InMemoryFlightSource(error=SourceRateLimited("slow down"))
        with pytest.raises(SourceRateLimited):
            await source.search(query)


class TestErrorTranslation:
    """Each scraper's own exception type becomes one declared error mode."""

    @pytest.mark.parametrize(
        "exc_name,expected",
        [
            ("WizzAirRateLimitError", SourceRateLimited),
            ("RateLimitExceeded", SourceRateLimited),
            ("CaptchaDetected", SourceBlocked),
            ("CaptchaDetectedError", SourceBlocked),
            ("TimeoutError", SourceUnavailable),
            ("KiwiAPIError", SourceUnavailable),
            ("AuthenticationError", SourceCredentialsInvalid),
            ("APIKeyMissingError", SourceCredentialsInvalid),
            ("UnauthorizedError", SourceCredentialsInvalid),
        ],
    )
    def test_maps_by_type_name(self, exc_name, expected):
        source = KiwiSource(client=object())
        exc = type(exc_name, (Exception,), {})("boom")
        assert isinstance(source._translate(exc), expected)

    def test_parse_errors_are_not_retryable(self):
        source = KiwiSource(client=object())
        translated = source._translate(KeyError("price"))
        assert isinstance(translated, SourceParseFailed)
        assert translated.retryable is False

    def test_credentials_failures_are_not_retryable(self):
        """
        A missing or invalid API key will still be invalid next time, so
        retrying burns rate limit and never succeeds. This used to fall
        through to SourceUnavailable, which is retryable.
        """
        source = KiwiSource(client=object())
        exc = type("AuthenticationError", (Exception,), {})("bad key")
        translated = source._translate(exc)
        assert isinstance(translated, SourceCredentialsInvalid)
        assert translated.retryable is False

    def test_credentials_are_checked_before_generic_api_errors(self):
        """Ordering matters: an auth error must not match the APIError rule."""
        source = KiwiSource(client=object())
        exc = type("AuthAPIError", (Exception,), {})("bad key")
        assert isinstance(source._translate(exc), SourceCredentialsInvalid)

    def test_rate_limits_are_retryable(self):
        assert SourceRateLimited("x").retryable is True

    def test_blocked_is_not_retryable(self):
        assert SourceBlocked("captcha").retryable is False

    def test_an_already_declared_error_passes_through(self):
        source = KiwiSource(client=object())
        original = SourceBlocked("captcha", source="kiwi")
        assert source._translate(original) is original

    def test_error_message_names_the_source(self):
        assert "[ryanair]" in str(SourceBlocked("captcha", source="ryanair"))


class TestAdaptersOwnTheirCallShape:
    """Each adapter maps the shared query onto its scraper's own keywords."""

    async def test_kiwi_uses_adults_and_children(self, query):
        captured = {}

        class FakeClient:
            async def search_flights(self, **kwargs):
                captured.update(kwargs)
                return []

        await KiwiSource(client=FakeClient()).search(query)
        assert captured["adults"] == 2
        assert captured["children"] == 2

    async def test_wizzair_uses_adult_count_and_child_count(self, query):
        captured = {}

        class FakeScraper:
            async def search_flights(self, **kwargs):
                captured.update(kwargs)
                return []

        await WizzAirSource(scraper=FakeScraper()).search(query)
        assert captured["adult_count"] == 2
        assert captured["child_count"] == 2

    async def test_skyscanner_owns_its_context_manager(self, query):
        entered = []

        class FakeScraper:
            async def __aenter__(self):
                entered.append("in")
                return self

            async def __aexit__(self, *args):
                entered.append("out")
                return None

            async def scrape_route(self, **kwargs):
                return [{"price": 120.0}]

        offers = await SkyscannerSource(scraper=FakeScraper()).search(query)
        assert entered == ["in", "out"]
        assert offers[0]["source"] == "skyscanner"

    async def test_ryanair_stamps_its_airline(self, query):
        class FakeScraper:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def scrape_route(self, **kwargs):
                return [{"price": 40.0}]

        offers = await RyanairSource(scraper=FakeScraper()).search(query)
        assert offers[0]["airline"] == "Ryanair"

    async def test_scraper_exception_becomes_a_source_error(self, query):
        class Boom(Exception):
            pass

        class FakeClient:
            async def search_flights(self, **kwargs):
                raise Boom("upstream died")

        with pytest.raises(SourceUnavailable):
            await KiwiSource(client=FakeClient()).search(query)


class TestRegistry:
    def test_builds_the_named_sources_in_order(self):
        sources = build_flight_sources(["wizzair", "kiwi"])
        assert [s.name for s in sources] == ["wizzair", "kiwi"]

    def test_unknown_names_are_skipped_not_fatal(self):
        sources = build_flight_sources(["kiwi", "notascraper"])
        assert [s.name for s in sources] == ["kiwi"]

    def test_every_adapter_is_registered_under_its_own_name(self):
        for name, adapter in FLIGHT_SOURCE_ADAPTERS.items():
            assert adapter.name == name

    def test_empty_list_builds_nothing(self):
        assert build_flight_sources([]) == []
