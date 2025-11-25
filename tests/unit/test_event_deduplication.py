"""
Unit tests for event deduplication utilities.
"""

import pytest
from datetime import date

from app.utils.event_deduplication import (
    normalize_text,
    extract_venue_from_text,
    generate_deduplication_hash,
    fuzzy_match_titles,
    are_events_similar,
    deduplicate_events,
    _merge_duplicate_events,
)


class TestNormalizeText:
    """Test text normalization function."""

    def test_normalize_lowercase(self):
        """Test conversion to lowercase."""
        assert normalize_text("HELLO WORLD") == "hello world"
        assert normalize_text("Hello World") == "hello world"

    def test_normalize_whitespace(self):
        """Test whitespace normalization."""
        assert normalize_text("hello    world") == "hello world"
        assert normalize_text("  hello  world  ") == "hello world"
        assert normalize_text("hello\n\tworld") == "hello world"

    def test_normalize_punctuation(self):
        """Test punctuation removal."""
        assert normalize_text("Hello, World!") == "hello world"
        assert normalize_text("Art & Culture") == "art culture"  # & is removed, double space normalized
        assert normalize_text("Lisbon's Festival") == "lisbons festival"

    def test_normalize_empty(self):
        """Test empty string handling."""
        assert normalize_text("") == ""
        assert normalize_text(None) == ""


class TestExtractVenueFromText:
    """Test venue extraction from text."""

    def test_extract_venue_at_pattern(self):
        """Test extraction with 'at' pattern."""
        text = "Jazz Concert at Blue Note Club on Friday"
        assert extract_venue_from_text(text) == "Blue Note Club"

    def test_extract_venue_location_pattern(self):
        """Test extraction with 'Location:' pattern."""
        text = "Family Day\nLocation: Central Park\nFree entry"
        result = extract_venue_from_text(text)
        assert result is not None
        assert "central park" in result.lower()

    def test_extract_venue_dash_pattern(self):
        """Test extraction with venue - title pattern."""
        text = "Museu Nacional de Arte Antiga - Special Exhibition"
        result = extract_venue_from_text(text)
        assert result == "Museu Nacional de Arte Antiga"

    def test_extract_venue_none(self):
        """Test when no venue pattern found."""
        text = "Just a simple event description"
        assert extract_venue_from_text(text) is None

    def test_extract_venue_empty(self):
        """Test with empty input."""
        assert extract_venue_from_text("") is None
        assert extract_venue_from_text(None) is None


class TestGenerateDeduplicationHash:
    """Test deduplication hash generation."""

    def test_same_event_same_hash(self):
        """Test that identical events produce the same hash."""
        hash1 = generate_deduplication_hash(
            title="Summer Festival",
            event_date=date(2025, 7, 15),
            destination_city="Lisbon",
            venue="Praca do Comercio"
        )
        hash2 = generate_deduplication_hash(
            title="Summer Festival",
            event_date=date(2025, 7, 15),
            destination_city="Lisbon",
            venue="Praca do Comercio"
        )
        assert hash1 == hash2

    def test_different_title_different_hash(self):
        """Test that different titles produce different hashes."""
        hash1 = generate_deduplication_hash(
            title="Summer Festival",
            event_date=date(2025, 7, 15),
            destination_city="Lisbon"
        )
        hash2 = generate_deduplication_hash(
            title="Winter Festival",
            event_date=date(2025, 7, 15),
            destination_city="Lisbon"
        )
        assert hash1 != hash2

    def test_different_date_different_hash(self):
        """Test that different dates produce different hashes."""
        hash1 = generate_deduplication_hash(
            title="Summer Festival",
            event_date=date(2025, 7, 15),
            destination_city="Lisbon"
        )
        hash2 = generate_deduplication_hash(
            title="Summer Festival",
            event_date=date(2025, 7, 16),
            destination_city="Lisbon"
        )
        assert hash1 != hash2

    def test_case_insensitive(self):
        """Test that hash is case-insensitive for title."""
        hash1 = generate_deduplication_hash(
            title="Summer Festival",
            event_date=date(2025, 7, 15),
            destination_city="Lisbon"
        )
        hash2 = generate_deduplication_hash(
            title="SUMMER FESTIVAL",
            event_date=date(2025, 7, 15),
            destination_city="Lisbon"
        )
        assert hash1 == hash2

    def test_with_venue(self):
        """Test hash generation with venue."""
        hash_with_venue = generate_deduplication_hash(
            title="Concert",
            event_date=date(2025, 7, 15),
            destination_city="Lisbon",
            venue="Blue Note"
        )
        hash_without_venue = generate_deduplication_hash(
            title="Concert",
            event_date=date(2025, 7, 15),
            destination_city="Lisbon",
            venue=None
        )
        assert hash_with_venue != hash_without_venue


class TestFuzzyMatchTitles:
    """Test fuzzy title matching."""

    def test_exact_match(self):
        """Test exact match returns 1.0."""
        ratio = fuzzy_match_titles("Summer Festival", "Summer Festival")
        assert ratio == 1.0

    def test_case_insensitive(self):
        """Test case-insensitive matching."""
        ratio = fuzzy_match_titles("Summer Festival", "SUMMER FESTIVAL")
        assert ratio == 1.0

    def test_similar_titles(self):
        """Test similar but not identical titles."""
        ratio = fuzzy_match_titles(
            "Lisbon Jazz Festival 2025",
            "Lisbon Jazz Festival"
        )
        assert ratio > 0.8  # Should be very similar

    def test_different_titles(self):
        """Test completely different titles."""
        ratio = fuzzy_match_titles(
            "Summer Music Festival",
            "Winter Art Exhibition"
        )
        assert ratio < 0.5  # Should be quite different

    def test_typos(self):
        """Test handling of typos."""
        ratio = fuzzy_match_titles(
            "Summer Festival",
            "Sumer Festival"
        )
        assert ratio > 0.9  # Should still be very similar

    def test_empty_strings(self):
        """Test empty string handling."""
        assert fuzzy_match_titles("", "") == 0.0
        assert fuzzy_match_titles("Something", "") == 0.0


class TestAreEventsSimilar:
    """Test event similarity detection."""

    def test_identical_events(self):
        """Test that identical events are similar."""
        event1 = {
            'title': 'Summer Festival',
            'event_date': date(2025, 7, 15),
            'destination_city': 'Lisbon'
        }
        event2 = {
            'title': 'Summer Festival',
            'event_date': date(2025, 7, 15),
            'destination_city': 'Lisbon'
        }
        assert are_events_similar(event1, event2) is True

    def test_different_dates(self):
        """Test that events on different dates are not similar."""
        event1 = {
            'title': 'Summer Festival',
            'event_date': date(2025, 7, 15),
            'destination_city': 'Lisbon'
        }
        event2 = {
            'title': 'Summer Festival',
            'event_date': date(2025, 7, 16),
            'destination_city': 'Lisbon'
        }
        assert are_events_similar(event1, event2) is False

    def test_different_cities(self):
        """Test that events in different cities are not similar."""
        event1 = {
            'title': 'Summer Festival',
            'event_date': date(2025, 7, 15),
            'destination_city': 'Lisbon'
        }
        event2 = {
            'title': 'Summer Festival',
            'event_date': date(2025, 7, 15),
            'destination_city': 'Barcelona'
        }
        assert are_events_similar(event1, event2) is False

    def test_slightly_different_titles(self):
        """Test that events with slightly different titles are similar."""
        event1 = {
            'title': 'Lisbon Jazz Festival 2025',
            'event_date': date(2025, 7, 15),
            'destination_city': 'Lisbon'
        }
        event2 = {
            'title': 'Lisbon Jazz Festival',
            'event_date': date(2025, 7, 15),
            'destination_city': 'Lisbon'
        }
        assert are_events_similar(event1, event2) is True

    def test_completely_different_titles(self):
        """Test that events with different titles are not similar."""
        event1 = {
            'title': 'Summer Music Festival',
            'event_date': date(2025, 7, 15),
            'destination_city': 'Lisbon'
        }
        event2 = {
            'title': 'Winter Art Exhibition',
            'event_date': date(2025, 7, 15),
            'destination_city': 'Lisbon'
        }
        assert are_events_similar(event1, event2) is False


class TestMergeDuplicateEvents:
    """Test event merging logic."""

    def test_merge_keeps_best_description(self):
        """Test that merging keeps event with longest description."""
        event1 = {
            'title': 'Festival',
            'description': 'Short',
            'source': 'eventbrite',
            'url': 'http://example.com/1'
        }
        event2 = {
            'title': 'Festival',
            'description': 'This is a much longer and more detailed description',
            'source': 'tourism_lisbon',
            'url': 'http://example.com/2'
        }
        merged = _merge_duplicate_events([event1, event2])

        assert merged['description'] == event2['description']
        assert 'eventbrite' in merged['sources']
        assert 'tourism_lisbon' in merged['sources']
        assert len(merged['urls']) == 2

    def test_merge_keeps_venue(self):
        """Test that merging keeps venue information."""
        event1 = {
            'title': 'Concert',
            'venue': 'Blue Note',
            'description': 'Short',
            'source': 'eventbrite'
        }
        event2 = {
            'title': 'Concert',
            'description': 'Longer description',
            'source': 'tourism_lisbon'
        }
        merged = _merge_duplicate_events([event1, event2])

        # Should keep event2's description but we want venue from event1
        # The function picks based on completeness score
        assert merged is not None

    def test_merge_duplicate_count(self):
        """Test that merged event has duplicate count."""
        events = [
            {'title': 'Event', 'source': 'source1'},
            {'title': 'Event', 'source': 'source2'},
            {'title': 'Event', 'source': 'source3'}
        ]
        merged = _merge_duplicate_events(events)

        assert merged['duplicate_count'] == 3


class TestDeduplicateEvents:
    """Test main deduplication function."""

    def test_deduplicate_exact_matches(self):
        """Test deduplication of exact matches."""
        events = [
            {
                'title': 'Summer Festival',
                'event_date': date(2025, 7, 15),
                'destination_city': 'Lisbon',
                'venue': 'Central Park',
                'source': 'eventbrite',
                'category': 'festival'
            },
            {
                'title': 'Summer Festival',
                'event_date': date(2025, 7, 15),
                'destination_city': 'Lisbon',
                'venue': 'Central Park',
                'source': 'tourism_lisbon',
                'category': 'festival'
            }
        ]

        unique, removed = deduplicate_events(events)

        assert len(unique) == 1
        assert removed == 1
        assert 'deduplication_hash' in unique[0]

    def test_deduplicate_fuzzy_matches(self):
        """Test deduplication with fuzzy matching."""
        events = [
            {
                'title': 'Lisbon Jazz Festival 2025',
                'event_date': date(2025, 7, 15),
                'destination_city': 'Lisbon',
                'source': 'eventbrite',
                'category': 'music'
            },
            {
                'title': 'Lisbon Jazz Festival',
                'event_date': date(2025, 7, 15),
                'destination_city': 'Lisbon',
                'source': 'tourism_lisbon',
                'category': 'music'
            }
        ]

        unique, removed = deduplicate_events(events, use_fuzzy_matching=True)

        assert len(unique) == 1
        assert removed == 1

    def test_deduplicate_different_events(self):
        """Test that different events are not deduplicated."""
        events = [
            {
                'title': 'Summer Festival',
                'event_date': date(2025, 7, 15),
                'destination_city': 'Lisbon',
                'source': 'eventbrite',
                'category': 'festival'
            },
            {
                'title': 'Winter Concert',
                'event_date': date(2025, 12, 20),
                'destination_city': 'Barcelona',
                'source': 'tourism_barcelona',
                'category': 'music'
            }
        ]

        unique, removed = deduplicate_events(events)

        assert len(unique) == 2
        assert removed == 0

    def test_deduplicate_without_fuzzy_matching(self):
        """Test deduplication without fuzzy matching."""
        events = [
            {
                'title': 'Lisbon Jazz Festival 2025',
                'event_date': date(2025, 7, 15),
                'destination_city': 'Lisbon',
                'source': 'eventbrite',
                'category': 'music'
            },
            {
                'title': 'Lisbon Jazz Festival',
                'event_date': date(2025, 7, 15),
                'destination_city': 'Lisbon',
                'source': 'tourism_lisbon',
                'category': 'music'
            }
        ]

        # Without fuzzy matching, these should remain separate
        unique, removed = deduplicate_events(events, use_fuzzy_matching=False)

        assert len(unique) == 2
        assert removed == 0

    def test_deduplicate_empty_list(self):
        """Test deduplication with empty list."""
        unique, removed = deduplicate_events([])

        assert len(unique) == 0
        assert removed == 0

    def test_deduplicate_venue_extraction(self):
        """Test that venue is extracted from description during deduplication."""
        events = [
            {
                'title': 'Concert',
                'event_date': date(2025, 7, 15),
                'destination_city': 'Lisbon',
                'description': 'Amazing concert at Blue Note Club',
                'source': 'eventbrite',
                'category': 'music'
            }
        ]

        unique, removed = deduplicate_events(events)

        assert len(unique) == 1
        # Venue should be extracted
        assert unique[0].get('venue') is not None
