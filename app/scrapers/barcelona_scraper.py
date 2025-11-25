"""
Barcelona tourism events scraper for barcelonaturisme.com website.
"""

import logging
import re
from datetime import date
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from app.scrapers.tourism_scraper import BaseTourismScraper

logger = logging.getLogger(__name__)


class BarcelonaTourismScraper(BaseTourismScraper):
    """Scraper for Barcelona tourism events from barcelonaturisme.com"""

    BASE_URL = "https://www.barcelonaturisme.com"
    CITY_NAME = "Barcelona"
    SOURCE_NAME = "tourism_barcelona"

    # Barcelona events page
    EVENTS_URL = "https://www.barcelonaturisme.com/wv3/en/agenda/"

    async def scrape_events(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """
        Scrape events from Barcelona Turisme website.

        Args:
            start_date: Start date for event search
            end_date: End date for event search

        Returns:
            List of event dictionaries
        """
        events = []

        try:
            logger.info(f"Scraping Barcelona events from {start_date} to {end_date}")

            # Barcelona Turisme may use JavaScript for loading events
            html = await self.fetch_html(self.EVENTS_URL, use_playwright=True)
            if not html:
                logger.error(
                    f"Failed to fetch Barcelona events page\n"
                    f"URL: {self.EVENTS_URL}\n"
                    f"Possible causes:\n"
                    f"  - Website is down or blocking requests\n"
                    f"  - Network connectivity issues\n"
                    f"  - Playwright browser not installed\n"
                    f"To fix: Check website availability or run 'poetry run playwright install chromium'"
                )
                return events

            soup = BeautifulSoup(html, 'lxml')

            # Parse event cards
            # Barcelona Turisme typically uses specific event card structure
            event_cards = soup.find_all(['article', 'div', 'li'], class_=re.compile(r'event|card|item|agenda', re.I))

            # Also try finding by specific Barcelona Turisme selectors
            if not event_cards:
                event_cards = soup.find_all(['div'], class_=re.compile(r'resultado|result', re.I))

            logger.info(f"Found {len(event_cards)} potential event cards")

            for card in event_cards:
                try:
                    event_dict = await self._parse_event_card(card, start_date, end_date)
                    if event_dict:
                        events.append(event_dict)
                except Exception as e:
                    logger.warning(f"Error parsing event card: {e}")
                    continue

            # Try to load more events if there's a "load more" button
            await self._handle_load_more(soup, events, start_date, end_date)

            logger.info(f"Successfully scraped {len(events)} Barcelona events")

        except Exception as e:
            logger.error(f"Error scraping Barcelona events: {e}", exc_info=True)

        return events

    async def _parse_event_card(
        self,
        card: BeautifulSoup,
        start_date: date,
        end_date: date
    ) -> Optional[Dict[str, Any]]:
        """
        Parse individual event card from Barcelona Turisme.

        Args:
            card: BeautifulSoup element representing event card
            start_date: Filter start date
            end_date: Filter end date

        Returns:
            Event dictionary or None if parsing fails or event outside date range
        """
        # Extract title
        title_elem = card.find(['h2', 'h3', 'h4', 'a'], class_=re.compile(r'title|name|heading|titulo', re.I))
        if not title_elem:
            title_elem = card.find(['h2', 'h3', 'h4'])

        if not title_elem:
            return None

        title = title_elem.get_text(strip=True)
        if not title or len(title) < 3:
            return None

        # Extract URL
        url_elem = card.find('a', href=True)
        url = url_elem['href'] if url_elem else ""

        # Extract date
        date_elem = card.find(['time', 'span', 'div'], class_=re.compile(r'date|time|when|fecha|data', re.I))
        if not date_elem:
            date_elem = card.find('time')

        event_date = None
        event_end_date = None

        if date_elem:
            # Try datetime attribute first
            if date_elem.has_attr('datetime'):
                date_text = date_elem['datetime']
                event_date = self.date_parser.parse_tourism_date(date_text)

            # Fall back to text content
            if not event_date:
                date_text = date_elem.get_text(strip=True)
                event_date, event_end_date = self.date_parser.parse_date_range(date_text)

                if not event_date:
                    event_date = self.date_parser.parse_tourism_date(date_text)

        # Skip if no date or outside range
        if not event_date:
            return None

        if event_date < start_date or event_date > end_date:
            return None

        # Extract description
        description = ""
        desc_elem = card.find(['p', 'div'], class_=re.compile(r'description|summary|excerpt|descripcion', re.I))
        if desc_elem:
            description = desc_elem.get_text(strip=True)

        # Extract category/tags
        category = None
        tag_elem = card.find(['span', 'div'], class_=re.compile(r'category|tag|tipo', re.I))
        if tag_elem:
            tag_text = tag_elem.get_text(strip=True).lower()
            # Map Spanish/Catalan categories to English
            if any(word in tag_text for word in ['familia', 'family', 'niños', 'nens']):
                category = 'family'
            elif any(word in tag_text for word in ['cultura', 'culture', 'museo', 'museu']):
                category = 'cultural'
            elif any(word in tag_text for word in ['música', 'music', 'concert']):
                category = 'music'
            elif any(word in tag_text for word in ['deporte', 'sport', 'esport']):
                category = 'sports'

        # Extract price information
        price_range = "varies"
        price_elem = card.find(['span', 'div'], class_=re.compile(r'price|cost|fee|precio|preu', re.I))
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            price_range = self.extract_price_range(price_text)
        elif description:
            price_range = self.extract_price_range(description)

        return self.create_event_dict(
            title=title,
            event_date=event_date,
            url=url,
            description=description,
            end_date=event_end_date,
            price_range=price_range,
            category=category,
        )

    async def _handle_load_more(
        self,
        soup: BeautifulSoup,
        events: List[Dict[str, Any]],
        start_date: date,
        end_date: date
    ) -> None:
        """
        Handle 'load more' pagination if present.

        Args:
            soup: BeautifulSoup object of current page
            events: List to append new events to
            start_date: Filter start date
            end_date: Filter end date
        """
        # Look for load more button or pagination
        load_more = soup.find(['button', 'a'], class_=re.compile(r'load.*more|ver.*mas|cargar', re.I))

        if load_more and load_more.has_attr('href'):
            next_url = self.make_absolute_url(load_more['href'])
            try:
                html = await self.fetch_html(next_url, use_playwright=True)
                if html:
                    next_soup = BeautifulSoup(html, 'lxml')
                    event_cards = next_soup.find_all(['article', 'div'], class_=re.compile(r'event|card|item', re.I))

                    for card in event_cards:
                        try:
                            event_dict = await self._parse_event_card(card, start_date, end_date)
                            if event_dict:
                                events.append(event_dict)
                        except Exception as e:
                            logger.warning(f"Error parsing event card from load more: {e}")
            except Exception as e:
                logger.warning(f"Error handling load more: {e}")
