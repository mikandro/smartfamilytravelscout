"""
Prague tourism events scraper for prague.eu website.
"""

import logging
import re
from datetime import date
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from app.scrapers.tourism_scraper import BaseTourismScraper

logger = logging.getLogger(__name__)


class PragueTourismScraper(BaseTourismScraper):
    """Scraper for Prague tourism events from prague.eu"""

    BASE_URL = "https://www.prague.eu"
    CITY_NAME = "Prague"
    SOURCE_NAME = "tourism_prague"

    # Prague events page
    EVENTS_URL = "https://www.prague.eu/en/whats-on"

    async def scrape_events(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """
        Scrape events from Prague.eu website.

        Args:
            start_date: Start date for event search
            end_date: End date for event search

        Returns:
            List of event dictionaries
        """
        events = []

        try:
            logger.info(f"Scraping Prague events from {start_date} to {end_date}")

            # Try to build URL with date filters if API supports it
            params = {
                'date_from': start_date.strftime('%Y-%m-%d'),
                'date_to': end_date.strftime('%Y-%m-%d'),
            }
            url_with_params = f"{self.EVENTS_URL}?{urlencode(params)}"

            # Fetch events page - Prague.eu may use JavaScript
            html = await self.fetch_html(url_with_params, use_playwright=True)
            if not html:
                logger.warning("Failed to fetch with date params, trying base URL")
                html = await self.fetch_html(self.EVENTS_URL, use_playwright=True)

            if not html:
                logger.error("Failed to fetch Prague events page")
                return events

            soup = BeautifulSoup(html, 'lxml')

            # Parse event cards
            # Prague.eu typically uses specific event card structure
            event_cards = soup.find_all(['article', 'div', 'li'], class_=re.compile(r'event|card|item|listing', re.I))

            # Also try finding by data attributes
            if not event_cards:
                event_cards = soup.find_all(['div', 'article'], attrs={'data-event-id': True})

            logger.info(f"Found {len(event_cards)} potential event cards")

            for card in event_cards:
                try:
                    event_dict = await self._parse_event_card(card, start_date, end_date)
                    if event_dict:
                        events.append(event_dict)
                except Exception as e:
                    logger.warning(f"Error parsing event card: {e}")
                    continue

            # Try pagination if available
            page_num = 2
            max_pages = 5  # Limit to prevent infinite loops

            while page_num <= max_pages:
                next_url = await self._find_next_page(soup)
                if not next_url:
                    break

                logger.info(f"Fetching page {page_num}")
                html = await self.fetch_html(next_url, use_playwright=True)
                if not html:
                    break

                soup = BeautifulSoup(html, 'lxml')
                event_cards = soup.find_all(['article', 'div', 'li'], class_=re.compile(r'event|card|item', re.I))

                for card in event_cards:
                    try:
                        event_dict = await self._parse_event_card(card, start_date, end_date)
                        if event_dict:
                            events.append(event_dict)
                    except Exception as e:
                        logger.warning(f"Error parsing event card on page {page_num}: {e}")
                        continue

                page_num += 1

            logger.info(f"Successfully scraped {len(events)} Prague events")

        except Exception as e:
            logger.error(f"Error scraping Prague events: {e}", exc_info=True)

        return events

    async def _parse_event_card(
        self,
        card: BeautifulSoup,
        start_date: date,
        end_date: date
    ) -> Optional[Dict[str, Any]]:
        """
        Parse individual event card from Prague.eu.

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
            title_elem = card.find(['h2', 'h3', 'h4', 'a'])

        if not title_elem:
            return None

        title = title_elem.get_text(strip=True)
        if not title or len(title) < 3:
            return None

        # Extract URL
        url_elem = card.find('a', href=True)
        url = url_elem['href'] if url_elem else ""

        # Extract date
        date_elem = card.find(['time', 'span', 'div'], class_=re.compile(r'date|time|when|datum', re.I))
        if not date_elem:
            date_elem = card.find('time', attrs={'datetime': True})

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
        desc_elem = card.find(['p', 'div'], class_=re.compile(r'description|summary|excerpt|perex', re.I))
        if desc_elem:
            description = desc_elem.get_text(strip=True)

        # Extract price information
        price_range = "varies"
        price_elem = card.find(['span', 'div'], class_=re.compile(r'price|cost|fee|cena', re.I))
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

    async def _find_next_page(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Find next page URL for pagination.

        Args:
            soup: BeautifulSoup object of current page

        Returns:
            URL of next page or None if not found
        """
        # Look for pagination elements
        next_link = soup.find('a', class_=re.compile(r'next|další', re.I))
        if next_link and next_link.has_attr('href'):
            return self.make_absolute_url(next_link['href'])

        # Look for numbered pagination
        pagination = soup.find(['nav', 'div'], class_=re.compile(r'pagination|paging', re.I))
        if pagination:
            links = pagination.find_all('a', href=True)
            for link in links:
                if 'next' in link.get_text(strip=True).lower():
                    return self.make_absolute_url(link['href'])

        return None
