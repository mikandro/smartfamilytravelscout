"""
Lisbon tourism events scraper for Visit Lisboa website.
"""

import logging
import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from app.scrapers.tourism_scraper import BaseTourismScraper

logger = logging.getLogger(__name__)


class LisbonTourismScraper(BaseTourismScraper):
    """Scraper for Lisbon tourism events from visitlisboa.com"""

    BASE_URL = "https://www.visitlisboa.com"
    CITY_NAME = "Lisbon"
    SOURCE_NAME = "tourism_lisbon"

    # Visit Lisboa events page
    EVENTS_URL = "https://www.visitlisboa.com/en/whats-on"

    async def scrape_events(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """
        Scrape events from Visit Lisboa website.

        Args:
            start_date: Start date for event search
            end_date: End date for event search

        Returns:
            List of event dictionaries
        """
        events = []

        try:
            logger.info(f"Scraping Lisbon events from {start_date} to {end_date}")

            # Fetch events page
            html = await self.fetch_html(self.EVENTS_URL, use_playwright=True)
            if not html:
                logger.error("Failed to fetch Lisbon events page")
                return events

            soup = BeautifulSoup(html, 'lxml')

            # Parse event cards
            # Visit Lisboa typically uses article or div elements for events
            event_cards = soup.find_all(['article', 'div'], class_=re.compile(r'event|card|item', re.I))

            logger.info(f"Found {len(event_cards)} potential event cards")

            for card in event_cards:
                try:
                    event_dict = await self._parse_event_card(card, start_date, end_date)
                    if event_dict:
                        events.append(event_dict)
                except Exception as e:
                    logger.warning(f"Error parsing event card: {e}")
                    continue

            logger.info(f"Successfully scraped {len(events)} Lisbon events")

        except Exception as e:
            logger.error(f"Error scraping Lisbon events: {e}", exc_info=True)

        return events

    async def _parse_event_card(
        self,
        card: BeautifulSoup,
        start_date: date,
        end_date: date
    ) -> Optional[Dict[str, Any]]:
        """
        Parse individual event card.

        Args:
            card: BeautifulSoup element representing event card
            start_date: Filter start date
            end_date: Filter end date

        Returns:
            Event dictionary or None if parsing fails or event outside date range
        """
        # Extract title
        title_elem = card.find(['h2', 'h3', 'h4', 'a'], class_=re.compile(r'title|name|heading', re.I))
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
        date_elem = card.find(['time', 'span', 'div'], class_=re.compile(r'date|time|when', re.I))
        if not date_elem:
            date_elem = card.find('time')

        event_date = None
        event_end_date = None

        if date_elem:
            date_text = date_elem.get_text(strip=True)

            # Try to parse date range
            event_date, event_end_date = self.date_parser.parse_date_range(date_text)

            # If range parsing failed, try single date
            if not event_date:
                event_date = self.date_parser.parse_tourism_date(date_text)

        # Skip if no date or outside range
        if not event_date:
            return None

        if event_date < start_date or event_date > end_date:
            return None

        # Extract description
        description = ""
        desc_elem = card.find(['p', 'div'], class_=re.compile(r'description|summary|excerpt', re.I))
        if desc_elem:
            description = desc_elem.get_text(strip=True)

        # Extract price information
        price_range = "varies"
        price_elem = card.find(['span', 'div'], class_=re.compile(r'price|cost|fee', re.I))
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
        )

    async def scrape_event_detail(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Scrape detailed information from event detail page.

        Args:
            url: URL of event detail page

        Returns:
            Dictionary with additional event details or None
        """
        try:
            html = await self.fetch_html(url)
            if not html:
                return None

            soup = BeautifulSoup(html, 'lxml')

            # Extract additional details
            details = {}

            # Try to find venue/location
            venue_elem = soup.find(['div', 'span'], class_=re.compile(r'venue|location|place', re.I))
            if venue_elem:
                details['venue'] = venue_elem.get_text(strip=True)

            # Try to find full description
            desc_elem = soup.find(['div', 'article'], class_=re.compile(r'description|content|body', re.I))
            if desc_elem:
                details['full_description'] = desc_elem.get_text(strip=True)

            return details

        except Exception as e:
            logger.warning(f"Error scraping event detail from {url}: {e}")
            return None
