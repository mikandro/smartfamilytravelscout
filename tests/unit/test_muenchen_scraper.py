"""
Unit tests for the muenchen.de event scraper.

Parsing runs against fixtures trimmed from the real site (see
tests/fixtures/muenchen_*.html). No network: ``fetch_html`` is replaced.
"""

from datetime import date, time
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.exceptions import ScraperException
from app.scrapers.muenchen_scraper import (
    CATEGORY_CHRISTMAS_MARKET,
    CATEGORY_FAMILY,
    MuenchenEventsScraper,
    Occurrence,
    group_occurrences,
    has_next_page,
    parse_detail,
    parse_listing,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"
LISTING = (FIXTURES / "muenchen_listing.html").read_text(encoding="utf-8")
DETAIL = (FIXTURES / "muenchen_detail.html").read_text(encoding="utf-8")
BASE = "https://www.muenchen.de"

EMPTY_PAGE = "<html><body><p>Keine Veranstaltungen</p></body></html>"


def listing_page(entries, next_page=False):
    """Build a minimal list page from (title, 'DD.MM.YYYY', 'HH:MM', href) tuples."""
    items = "".join(
        f"""
        <li><div class="m-event-list-item" itemprop="event">
          <time itemprop="endDate" datetime="2026-12-31T12:00:00Z"></time>
          <h3 itemprop="name"><span>{title}</span></h3>
          <p class="m-event-list-item__detail"><time datetime="{day} - {clock}:00">x</time></p>
          <p class="m-event-list-item__detail" itemprop="location">Testbühne</p>
          <a href="{href}">Tickets</a>
        </div></li>"""
        for title, day, clock, href in entries
    )
    pager = '<a href="?page=1"><span>Nächste Seite</span></a>' if next_page else ""
    return f"<html><body><ul>{items}</ul>{pager}</body></html>"


def make_scraper(pages, **kwargs):
    """A scraper whose fetch_html returns ``pages`` in order (no delay)."""
    scraper = MuenchenEventsScraper(request_delay=0, **kwargs)
    scraper.fetch_html = AsyncMock(side_effect=list(pages))
    return scraper


class TestParseListing:
    def test_reads_every_dated_entry_and_skips_the_broken_one(self):
        occurrences = parse_listing(LISTING, BASE)
        assert [o.title for o in occurrences] == [
            "Himmelswerkstatt",
            "Himmelswerkstatt",
            "Oh, wie schön ist Panama",
            "Inside the Suit – Der Mensch im Raumanzug",
            "Pettersson feiert Weihnachten",
        ]

    def test_occurrence_fields(self):
        panama = parse_listing(LISTING, BASE)[2]
        assert panama.venue == "Münchner Theater für Kinder"
        assert panama.day == date(2026, 11, 13)
        assert panama.start_time == time(15, 0)
        assert panama.end_time == time(17, 0)
        assert panama.showtime == "15:00-17:00"
        assert panama.series_end == date(2027, 4, 25)
        assert panama.url.startswith("https://www.muenchenticket.de/event/oh-wie-schoen-ist-panama")

    def test_internal_links_become_absolute(self):
        workshop = parse_listing(LISTING, BASE)[0]
        assert workshop.url == (
            "https://www.muenchen.de/veranstaltungen/kinder/himmelswerkstatt-christkindlmarkt-2026"
        )

    def test_two_showtimes_on_one_day_are_separate_occurrences(self):
        first, second = parse_listing(LISTING, BASE)[:2]
        assert first.day == second.day == date(2026, 11, 26)
        assert {first.showtime, second.showtime} == {"14:30-16:00", "16:30-18:00"}

    def test_page_without_entries_gives_empty_list(self):
        assert parse_listing(EMPTY_PAGE, BASE) == []

    def test_next_page_detection(self):
        assert has_next_page(LISTING) is True
        assert has_next_page(EMPTY_PAGE) is False


class TestParseDetail:
    def test_combines_intro_and_facts(self):
        text = parse_detail(DETAIL)
        assert "Himmelswerkstatt" in text
        assert "Facts:" in text
        assert "Schulkinder von 6 bis 12 Jahren" in text
        assert "Kosten: frei" in text

    def test_is_truncated(self):
        text = parse_detail(DETAIL, max_length=120)
        assert len(text) == 120
        assert text.endswith("…")

    def test_falls_back_to_meta_description(self):
        html = '<html><head><meta name="description" content="Kurz gesagt"></head></html>'
        assert parse_detail(html) == "Kurz gesagt"

    def test_page_without_text_gives_none(self):
        assert parse_detail("<html><body></body></html>") is None


class TestGroupOccurrences:
    def test_same_title_venue_and_day_collapse_with_sorted_showtimes(self):
        events = group_occurrences(
            parse_listing(LISTING, BASE), city="Munich", source="muenchen.de", category="family"
        )
        assert len(events) == 4
        workshop = next(e for e in events if e["title"] == "Himmelswerkstatt")
        assert workshop["showtimes"] == ["14:30-16:00", "16:30-18:00"]
        assert workshop["event_date"] == date(2026, 11, 26)
        assert workshop["end_date"] == date(2026, 12, 13)
        assert workshop["venue"] == "Neues Rathaus"
        assert workshop["destination_city"] == "Munich"
        assert workshop["source"] == "muenchen.de"
        assert workshop["category"] == "family"

    def test_same_show_on_two_days_stays_two_events(self):
        occurrences = [
            Occurrence("Show", "Bühne", date(2026, 11, 14), time(15), None, None, None),
            Occurrence("Show", "Bühne", date(2026, 11, 15), time(15), None, None, None),
        ]
        events = group_occurrences(occurrences, city="Munich", source="s", category="family")
        assert [e["event_date"] for e in events] == [date(2026, 11, 14), date(2026, 11, 15)]
        assert events[0]["showtimes"] == ["15:00"]


class TestListingUrl:
    def test_family_first_page(self):
        url = MuenchenEventsScraper().listing_url(CATEGORY_FAMILY, 0)
        assert url == (
            "https://www.muenchen.de/veranstaltungen/event"
            "?search=1&type=intro&field_category_one_target_id%5B0%5D=27895"
        )

    def test_later_page_and_other_category(self):
        url = MuenchenEventsScraper().listing_url(CATEGORY_CHRISTMAS_MARKET, 3)
        assert "field_category_one_target_id%5B0%5D=28105" in url
        assert url.endswith("&page=3")

    def test_never_uses_the_date_filter_robots_txt_disallows(self):
        assert "date-start" not in MuenchenEventsScraper().listing_url(CATEGORY_FAMILY, 2)

    def test_unknown_category_is_rejected(self):
        with pytest.raises(ValueError, match="concerts"):
            MuenchenEventsScraper(categories=["concerts"])


class TestScrapeEvents:
    SAT, SUN = date(2026, 11, 14), date(2026, 11, 15)

    async def test_keeps_only_events_inside_the_date_range(self):
        scraper = make_scraper([LISTING, DETAIL], categories=[CATEGORY_FAMILY])
        events = await scraper.scrape_events(self.SAT, self.SUN)
        assert sorted(e["title"] for e in events) == [
            "Inside the Suit – Der Mensch im Raumanzug",
            "Pettersson feiert Weihnachten",
        ]

    async def test_stops_paging_once_the_list_is_past_the_end_date(self):
        # The fixture runs to 26 Nov and has a next page, which must not be fetched.
        scraper = make_scraper([LISTING, DETAIL], categories=[CATEGORY_FAMILY])
        await scraper.scrape_events(self.SAT, self.SUN)
        listing_calls = [
            c for c in scraper.fetch_html.call_args_list if "/veranstaltungen/event?" in c.args[0]
        ]
        assert len(listing_calls) == 1

    async def test_follows_pages_until_the_end_date_is_passed(self):
        page0 = listing_page([("Früh", "13.11.2026", "10:00", "https://t.example/1")], True)
        page1 = listing_page([("Samstag", "14.11.2026", "11:00", "https://t.example/2")], True)
        page2 = listing_page([("Montag", "16.11.2026", "11:00", "https://t.example/3")], True)
        scraper = make_scraper([page0, page1, page2], categories=[CATEGORY_FAMILY])
        events = await scraper.scrape_events(self.SAT, self.SUN)
        assert [e["title"] for e in events] == ["Samstag"]
        assert scraper.fetch_html.call_count == 3
        assert scraper.fetch_html.call_args_list[1].args[0].endswith("&page=1")

    async def test_stops_at_the_last_page(self):
        page0 = listing_page([("Samstag", "14.11.2026", "11:00", "https://t.example/2")], False)
        scraper = make_scraper([page0], categories=[CATEGORY_FAMILY])
        assert len(await scraper.scrape_events(self.SAT, self.SUN)) == 1
        assert scraper.fetch_html.call_count == 1

    async def test_page_limit_stops_runaway_paging(self):
        page = listing_page([("Früh", "13.11.2026", "10:00", "https://t.example/1")], True)
        scraper = make_scraper([page] * 50, categories=[CATEGORY_FAMILY])
        await scraper.scrape_events(self.SAT, self.SUN)
        assert scraper.fetch_html.call_count == scraper.MAX_PAGES_PER_CATEGORY

    # The fixture ends on 26 Nov, so a search for that day reads one more page.
    LATER_PAGE = listing_page([("Später", "27.11.2026", "10:00", "https://t.example/9")])

    async def test_description_and_free_price_come_from_own_detail_pages(self):
        scraper = make_scraper([LISTING, self.LATER_PAGE, DETAIL], categories=[CATEGORY_FAMILY])
        events = await scraper.scrape_events(date(2026, 11, 26), date(2026, 11, 26))
        (workshop,) = events
        assert "Schulkinder von 6 bis 12 Jahren" in workshop["description"]
        assert workshop["price_range"] == "free"

    async def test_external_ticket_pages_are_never_fetched(self):
        scraper = make_scraper([LISTING], categories=[CATEGORY_FAMILY])
        events = await scraper.scrape_events(date(2026, 11, 13), date(2026, 11, 13))
        assert [e["title"] for e in events] == ["Oh, wie schön ist Panama"]
        assert events[0]["description"] is None
        fetched = [c.args[0] for c in scraper.fetch_html.call_args_list]
        assert all(url.startswith("https://www.muenchen.de/") for url in fetched)

    async def test_detail_page_is_fetched_once_per_url(self):
        same_link = "/veranstaltungen/kinder/x"
        page = listing_page(
            [("A", "14.11.2026", "10:00", same_link), ("A", "15.11.2026", "10:00", same_link)]
        )
        scraper = make_scraper([page, DETAIL], categories=[CATEGORY_FAMILY])
        events = await scraper.scrape_events(self.SAT, self.SUN)
        assert len(events) == 2
        assert all(e["description"] for e in events)
        assert scraper.fetch_html.call_count == 2

    async def test_failed_detail_page_leaves_event_without_description(self):
        scraper = make_scraper([LISTING, self.LATER_PAGE, None], categories=[CATEGORY_FAMILY])
        events = await scraper.scrape_events(date(2026, 11, 26), date(2026, 11, 26))
        assert events[0]["description"] is None

    async def test_categories_are_scraped_separately_and_labelled(self):
        family = listing_page([("Kasperl", "14.11.2026", "11:00", "https://t.example/k")])
        market = listing_page([("Wintermarkt", "14.11.2026", "12:00", "https://t.example/w")])
        scraper = make_scraper([family, market])
        events = await scraper.scrape_events(self.SAT, self.SUN)
        assert {e["title"]: e["category"] for e in events} == {
            "Kasperl": "family",
            "Wintermarkt": "christmas_market",
        }

    async def test_unreachable_site_raises(self):
        scraper = make_scraper([None], categories=[CATEGORY_FAMILY])
        with pytest.raises(ScraperException, match="could not fetch"):
            await scraper.scrape_events(self.SAT, self.SUN)

    async def test_changed_layout_raises_instead_of_reporting_no_events(self):
        scraper = make_scraper([EMPTY_PAGE], categories=[CATEGORY_FAMILY])
        with pytest.raises(ScraperException, match="layout has probably changed"):
            await scraper.scrape_events(self.SAT, self.SUN)

    async def test_empty_seasonal_category_is_not_an_error(self):
        family = listing_page([("Kasperl", "14.11.2026", "11:00", "https://t.example/k")])
        scraper = make_scraper([family, EMPTY_PAGE])
        events = await scraper.scrape_events(self.SAT, self.SUN)
        assert [e["title"] for e in events] == ["Kasperl"]

    async def test_later_page_failure_keeps_earlier_pages(self):
        page0 = listing_page([("Samstag", "14.11.2026", "11:00", "https://t.example/2")], True)
        scraper = make_scraper([page0, None], categories=[CATEGORY_FAMILY])
        events = await scraper.scrape_events(self.SAT, self.SUN)
        assert [e["title"] for e in events] == ["Samstag"]
