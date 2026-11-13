"""
Scraper for the muenchen.de event calendar (official Munich city portal).

Used by the weekend planner for things that only happen on particular days:
children's theatre, family events, Christmas markets.

How the site works (checked November 2026):

- Each category has a date-sorted, server-rendered list at
  ``/veranstaltungen/event?search=1&type=intro&field_category_one_target_id[0]=<id>&page=N``
  with 30 entries per page. Every entry is ONE occurrence of an event (one
  showtime), marked up as a schema.org Event.
- Entries link either to a muenchen.de detail page (which has a description
  and usually age, price and booking facts) or straight to an external ticket
  shop. Only muenchen.de detail pages are fetched; other sites are not touched.
- robots.txt allows these paths. It disallows URLs containing ``&date-start=``,
  so the calendar's date filter is deliberately not used: the scraper pages
  through the list until it has passed the end date.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlencode, urlparse

from bs4 import BeautifulSoup

from app.config import settings
from app.exceptions import ScraperException
from app.scrapers.tourism_scraper import BaseTourismScraper

logger = logging.getLogger(__name__)

#: muenchen.de category ids -> the category stored on our Event rows.
CATEGORY_FAMILY = "family"
CATEGORY_CHRISTMAS_MARKET = "christmas_market"

MUENCHEN_CATEGORIES: Dict[str, int] = {
    CATEGORY_FAMILY: 27895,  # "Familie / Kinder"
    CATEGORY_CHRISTMAS_MARKET: 28105,  # "Weihnachtsmarkt / Christkindlmarkt"
}

_OCCURRENCE_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})\s*-\s*(\d{2}):(\d{2})")
_FREE_RE = re.compile(r"\b(kostenlos|kostenfrei|eintritt frei|kosten:\s*frei)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Occurrence:
    """One list entry: a single showtime of an event."""

    title: str
    venue: Optional[str]
    day: date
    start_time: Optional[time]
    end_time: Optional[time]
    series_end: Optional[date]
    url: Optional[str]

    @property
    def showtime(self) -> Optional[str]:
        """``"15:00-17:00"``, ``"15:00"`` or None when no time is given."""
        if self.start_time is None:
            return None
        text = self.start_time.strftime("%H:%M")
        if self.end_time is not None and self.end_time != self.start_time:
            text += "-" + self.end_time.strftime("%H:%M")
        return text


def _clean(text: Optional[str]) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _parse_occurrence_time(value: Optional[str]) -> Tuple[Optional[date], Optional[time]]:
    """Parse the list's ``"14.11.2026 - 15:00:00"`` timestamps."""
    match = _OCCURRENCE_RE.search(value or "")
    if not match:
        return None, None
    day, month, year, hour, minute = (int(part) for part in match.groups())
    try:
        return date(year, month, day), time(hour, minute)
    except ValueError:
        return None, None


def _parse_iso_date(value: Optional[str]) -> Optional[date]:
    try:
        return datetime.fromisoformat((value or "").replace("Z", "+00:00")).date()
    except ValueError:
        return None


def parse_listing(html: str, base_url: str) -> List[Occurrence]:
    """
    Extract every occurrence from one calendar list page.

    Entries without a title or a parseable day are skipped.
    """
    soup = BeautifulSoup(html, "lxml")
    occurrences: List[Occurrence] = []

    for item in soup.select("div.m-event-list-item"):
        name_tag = item.select_one("[itemprop=name]")
        title = _clean(name_tag.get_text(" ")) if name_tag else ""
        times = item.select(".m-event-list-item__detail time")
        day, start_time = _parse_occurrence_time(times[0].get("datetime") if times else None)
        if not title or day is None:
            continue
        _, end_time = _parse_occurrence_time(times[1].get("datetime") if len(times) > 1 else None)

        location = item.select_one("[itemprop=location]")
        series_end_tag = item.select_one("[itemprop=endDate]")
        link = item.select_one("a[href]")
        href = link.get("href") if link else None
        if href and href.startswith("/"):
            href = base_url.rstrip("/") + href

        occurrences.append(
            Occurrence(
                title=title,
                venue=_clean(location.get_text(" ")) or None if location else None,
                day=day,
                start_time=start_time,
                end_time=end_time,
                series_end=(
                    _parse_iso_date(series_end_tag.get("datetime")) if series_end_tag else None
                ),
                url=href,
            )
        )

    return occurrences


def has_next_page(html: str) -> bool:
    """Whether the list page links to a following page."""
    soup = BeautifulSoup(html, "lxml")
    return any("Nächste Seite" in link.get_text() for link in soup.select("a[href]"))


def parse_detail(html: str, max_length: int = 900) -> Optional[str]:
    """
    Pull the intro text and the key facts box from a muenchen.de detail page.

    The facts box is where age range, cost and registration are stated, e.g.
    ``Alter: Schulkinder von 6 bis 12 Jahren``.
    """
    soup = BeautifulSoup(html, "lxml")
    intro = [_clean(p.get_text(" ")) for p in soup.select(".m-intro-horizontal__content p")]
    facts = [_clean(li.get_text(" ")) for li in soup.select(".m-callout__content li")]

    parts = [part for part in intro if part]
    if facts:
        parts.append("Facts: " + "; ".join(fact for fact in facts if fact))
    if not parts:
        meta = soup.select_one("meta[name=description]")
        parts = [_clean(meta.get("content"))] if meta and meta.get("content") else []

    text = " ".join(parts).strip()
    if not text:
        return None
    if len(text) > max_length:
        text = text[: max_length - 1].rstrip() + "…"
    return text


def group_occurrences(
    occurrences: Sequence[Occurrence],
    *,
    city: str,
    source: str,
    category: str,
) -> List[Dict[str, Any]]:
    """
    Collapse occurrences into one event dict per (title, venue, day).

    A puppet show with performances at 14:00 and 16:00 becomes one event with
    ``showtimes == ["14:00-15:00", "16:00-17:00"]``.
    """
    grouped: Dict[Tuple[str, str, date], Dict[str, Any]] = {}

    for occurrence in occurrences:
        key = (occurrence.title.lower(), (occurrence.venue or "").lower(), occurrence.day)
        event = grouped.get(key)
        if event is None:
            event = {
                "destination_city": city,
                "title": occurrence.title,
                "venue": occurrence.venue,
                "event_date": occurrence.day,
                "end_date": occurrence.series_end,
                "category": category,
                "description": None,
                "price_range": "varies",
                "source": source,
                "url": occurrence.url,
                "showtimes": [],
            }
            grouped[key] = event
        if occurrence.showtime and occurrence.showtime not in event["showtimes"]:
            event["showtimes"].append(occurrence.showtime)
        if event["url"] is None and occurrence.url:
            event["url"] = occurrence.url

    events = list(grouped.values())
    for event in events:
        event["showtimes"].sort()
    return events


class MuenchenEventsScraper(BaseTourismScraper):
    """Scraper for family events and Christmas markets on muenchen.de."""

    BASE_URL = "https://www.muenchen.de"
    LISTING_PATH = "/veranstaltungen/event"
    CITY_NAME = "Munich"
    SOURCE_NAME = "muenchen.de"

    REQUEST_DELAY = 2.0  # seconds between requests; this is a public city site
    MAX_PAGES_PER_CATEGORY = 12
    MAX_DETAIL_PAGES = 25

    def __init__(
        self,
        city_name: Optional[str] = None,
        categories: Optional[Sequence[str]] = None,
        request_delay: Optional[float] = None,
    ):
        """
        Args:
            city_name: Value stored in ``Event.destination_city`` (default "Munich").
            categories: Keys of ``MUENCHEN_CATEGORIES`` to scrape (default: all).
            request_delay: Seconds to wait between requests (default 2).
        """
        super().__init__()
        if city_name:
            self.CITY_NAME = city_name
        self.categories = list(categories) if categories else list(MUENCHEN_CATEGORIES)
        unknown = [name for name in self.categories if name not in MUENCHEN_CATEGORIES]
        if unknown:
            raise ValueError(f"Unknown muenchen.de categories: {', '.join(unknown)}")
        if request_delay is not None:
            self.REQUEST_DELAY = request_delay
        self._requests_made = 0

    async def _get_http_session(self):
        """HTTP session using the configured scraper user agent."""
        session = await super()._get_http_session()
        session.headers["User-Agent"] = settings.scraper_user_agent
        session.headers["Accept-Language"] = "de-DE,de;q=0.9,en;q=0.5"
        return session

    def listing_url(self, category: str, page: int) -> str:
        """URL of one page of a category's date-sorted list."""
        query = [
            ("search", "1"),
            ("type", "intro"),
            ("field_category_one_target_id[0]", str(MUENCHEN_CATEGORIES[category])),
        ]
        if page:
            query.append(("page", str(page)))
        return f"{self.BASE_URL}{self.LISTING_PATH}?{urlencode(query)}"

    async def _polite_fetch(self, url: str) -> Optional[str]:
        """Fetch a page, waiting ``REQUEST_DELAY`` between consecutive requests."""
        if self._requests_made and self.REQUEST_DELAY > 0:
            await asyncio.sleep(self.REQUEST_DELAY)
        self._requests_made += 1
        return await self.fetch_html(url)

    async def _scrape_category(
        self, category: str, start_date: date, end_date: date
    ) -> List[Occurrence]:
        """Page through one category until the list has passed ``end_date``."""
        collected: List[Occurrence] = []

        for page in range(self.MAX_PAGES_PER_CATEGORY):
            url = self.listing_url(category, page)
            html = await self._polite_fetch(url)
            if html is None:
                if page == 0:
                    raise ScraperException(f"muenchen.de: could not fetch the {category} list")
                logger.warning(
                    "muenchen.de: page %d of %s failed; using earlier pages", page, category
                )
                break

            occurrences = parse_listing(html, self.BASE_URL)
            if not occurrences:
                if page == 0 and category == CATEGORY_FAMILY:
                    # The family list always has entries, so an empty first
                    # page means the markup changed and the parser is blind.
                    raise ScraperException(
                        "muenchen.de: no entries recognised in the family list "
                        "(the page layout has probably changed)"
                    )
                if page == 0:
                    # Seasonal categories can be legitimately empty
                    # (Christmas markets in June).
                    logger.info("muenchen.de: no %s entries listed", category)
                break

            collected.extend(o for o in occurrences if start_date <= o.day <= end_date)

            if max(o.day for o in occurrences) > end_date or not has_next_page(html):
                break
        else:
            logger.warning(
                "muenchen.de: stopped %s after %d pages without reaching %s",
                category,
                self.MAX_PAGES_PER_CATEGORY,
                end_date,
            )

        return collected

    async def _add_descriptions(self, events: List[Dict[str, Any]]) -> None:
        """Fetch muenchen.de detail pages (once per URL) and attach descriptions."""
        descriptions: Dict[str, Optional[str]] = {}
        own_host = urlparse(self.BASE_URL).netloc

        for event in events:
            url = event.get("url")
            if not url or urlparse(url).netloc != own_host:
                continue
            if url not in descriptions:
                if len(descriptions) >= self.MAX_DETAIL_PAGES:
                    continue
                html = await self._polite_fetch(url)
                descriptions[url] = parse_detail(html) if html else None
            description = descriptions[url]
            if description:
                event["description"] = description
                if _FREE_RE.search(description):
                    event["price_range"] = "free"

    async def scrape_events(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """
        Scrape events taking place between ``start_date`` and ``end_date``.

        Returns:
            One dict per (title, venue, day) with the standard event fields
            plus ``venue`` and ``showtimes``.

        Raises:
            ScraperException: If the first page of the family list cannot be
                fetched or contains no recognisable entries (the site layout
                has probably changed).
        """
        events: List[Dict[str, Any]] = []

        for category in self.categories:
            occurrences = await self._scrape_category(category, start_date, end_date)
            events.extend(
                group_occurrences(
                    occurrences, city=self.CITY_NAME, source=self.SOURCE_NAME, category=category
                )
            )
            logger.info(
                "muenchen.de: %d %s occurrences between %s and %s",
                len(occurrences),
                category,
                start_date,
                end_date,
            )

        await self._add_descriptions(events)
        logger.info("muenchen.de: %d events after grouping", len(events))
        return events
