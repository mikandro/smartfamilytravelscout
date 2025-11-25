"""
Event deduplication utilities for SmartFamilyTravelScout.

This module provides functions for deduplicating events from multiple sources
(Eventbrite, tourism websites) using hash-based matching and fuzzy string matching.
"""

import hashlib
import logging
import re
from datetime import date
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Fuzzy matching threshold (0-1, where 1 is exact match)
FUZZY_MATCH_THRESHOLD = 0.85


def normalize_text(text: str) -> str:
    """
    Normalize text for comparison by removing extra whitespace, punctuation, and converting to lowercase.

    Args:
        text: Text to normalize

    Returns:
        Normalized text string
    """
    if not text:
        return ""

    # Convert to lowercase
    text = text.lower()

    # Remove common punctuation and special characters
    text = re.sub(r'[^\w\s-]', '', text)

    # Normalize whitespace (replace multiple spaces with single space)
    text = re.sub(r'\s+', ' ', text)

    # Strip leading/trailing whitespace
    text = text.strip()

    return text


def extract_venue_from_text(text: str) -> Optional[str]:
    """
    Attempt to extract venue information from event description or URL.

    Common patterns:
    - "at [Venue Name]"
    - "[Venue Name] -"
    - "Location: [Venue Name]"

    Args:
        text: Text to extract venue from (description or URL)

    Returns:
        Extracted venue name or None
    """
    if not text:
        return None

    text = text.strip()

    # Pattern 1: "at [Venue Name]"
    # Stops at common prepositions or punctuation
    match = re.search(r'\bat\s+([A-Z][A-Za-z\s&\'-]+?)(?:\s+(?:on|in|at|during|for|from)|[-,.|]|$)', text)
    if match:
        return match.group(1).strip()

    # Pattern 2: "Location: [Venue Name]"
    match = re.search(r'(?:location|venue|place):\s*([A-Z][A-Za-z\s&\'-]+?)(?:\s*[-,.|]|$)', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Pattern 3: "[Venue Name] -" at the beginning
    match = re.search(r'^([A-Z][A-Za-z\s&\'-]+?)\s*[-–—]', text)
    if match:
        venue = match.group(1).strip()
        # Only return if it looks like a venue (2-50 chars, not just one word)
        if 2 < len(venue) < 50 and ' ' in venue:
            return venue

    return None


def generate_deduplication_hash(
    title: str,
    event_date: date,
    destination_city: str,
    venue: Optional[str] = None
) -> str:
    """
    Generate a hash for event deduplication based on normalized title, venue, date, and city.

    The hash is generated from:
    - Normalized event title
    - Normalized venue (if provided)
    - Event date (ISO format)
    - Destination city (normalized)

    Args:
        title: Event title
        event_date: Event date
        destination_city: City where event takes place
        venue: Optional venue name

    Returns:
        SHA-256 hash string (hex digest)
    """
    # Normalize all text components
    normalized_title = normalize_text(title)
    normalized_city = normalize_text(destination_city)
    normalized_venue = normalize_text(venue) if venue else ""

    # Create hash input string
    hash_input = f"{normalized_title}|{normalized_venue}|{event_date.isoformat()}|{normalized_city}"

    # Generate SHA-256 hash
    hash_obj = hashlib.sha256(hash_input.encode('utf-8'))
    return hash_obj.hexdigest()


def fuzzy_match_titles(title1: str, title2: str) -> float:
    """
    Calculate similarity ratio between two event titles using fuzzy string matching.

    Uses SequenceMatcher for efficient fuzzy comparison.

    Args:
        title1: First event title
        title2: Second event title

    Returns:
        Similarity ratio from 0.0 (no match) to 1.0 (exact match)
    """
    # Normalize titles for comparison
    norm_title1 = normalize_text(title1)
    norm_title2 = normalize_text(title2)

    if not norm_title1 or not norm_title2:
        return 0.0

    # Calculate similarity ratio
    matcher = SequenceMatcher(None, norm_title1, norm_title2)
    return matcher.ratio()


def are_events_similar(
    event1: Dict[str, Any],
    event2: Dict[str, Any],
    fuzzy_threshold: float = FUZZY_MATCH_THRESHOLD
) -> bool:
    """
    Determine if two events are likely duplicates using fuzzy matching.

    Events are considered similar if:
    1. They occur on the same date
    2. They are in the same city
    3. Their titles have a similarity ratio above the threshold

    Args:
        event1: First event dictionary
        event2: Second event dictionary
        fuzzy_threshold: Minimum similarity ratio (0-1) to consider events as duplicates

    Returns:
        True if events are likely duplicates, False otherwise
    """
    # Check if dates match
    date1 = event1.get('event_date')
    date2 = event2.get('event_date')

    if date1 != date2:
        return False

    # Check if cities match
    city1 = normalize_text(event1.get('destination_city', ''))
    city2 = normalize_text(event2.get('destination_city', ''))

    if city1 != city2:
        return False

    # Check title similarity
    title1 = event1.get('title', '')
    title2 = event2.get('title', '')

    similarity = fuzzy_match_titles(title1, title2)

    return similarity >= fuzzy_threshold


def deduplicate_events(
    events: List[Dict[str, Any]],
    use_fuzzy_matching: bool = True
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Deduplicate a list of events using hash-based and fuzzy matching.

    This function:
    1. Generates deduplication hashes for all events
    2. Groups events by hash (exact matches)
    3. Optionally applies fuzzy matching to find similar events
    4. Keeps the event with the most complete information from each group
    5. Merges sources and URLs from duplicate events

    Args:
        events: List of event dictionaries to deduplicate
        use_fuzzy_matching: Whether to use fuzzy matching for similar titles (default: True)

    Returns:
        Tuple of (unique_events, duplicates_removed_count)
    """
    if not events:
        return [], 0

    logger.info(f"Deduplicating {len(events)} events...")

    # Step 1: Generate hashes and group by exact hash matches
    hash_groups = {}
    for event in events:
        # Extract or generate venue
        venue = event.get('venue')
        if not venue and event.get('description'):
            venue = extract_venue_from_text(event['description'])
            event['venue'] = venue  # Store extracted venue

        # Generate hash
        event_hash = generate_deduplication_hash(
            title=event.get('title', ''),
            event_date=event.get('event_date'),
            destination_city=event.get('destination_city', ''),
            venue=venue
        )
        event['deduplication_hash'] = event_hash

        # Group by hash
        if event_hash not in hash_groups:
            hash_groups[event_hash] = []
        hash_groups[event_hash].append(event)

    # Step 2: Keep best event from each hash group and merge metadata
    hash_deduplicated = []
    for hash_key, group in hash_groups.items():
        if len(group) == 1:
            hash_deduplicated.append(group[0])
        else:
            # Merge events with same hash
            best_event = _merge_duplicate_events(group)
            hash_deduplicated.append(best_event)

    # Step 3: Apply fuzzy matching if enabled
    if use_fuzzy_matching:
        unique_events = _apply_fuzzy_deduplication(hash_deduplicated)
    else:
        unique_events = hash_deduplicated

    duplicates_removed = len(events) - len(unique_events)

    logger.info(
        f"Deduplication complete: {len(unique_events)} unique events "
        f"({duplicates_removed} duplicates removed)"
    )

    return unique_events, duplicates_removed


def _merge_duplicate_events(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Merge duplicate events by keeping the most complete information.

    Priority for selecting best event:
    1. Event with most complete description
    2. Event with venue information
    3. Event with URL

    Also merges:
    - Sources (list of all sources)
    - URLs (list of all URLs)

    Args:
        events: List of duplicate events to merge

    Returns:
        Merged event dictionary
    """
    if len(events) == 1:
        return events[0]

    # Select best event based on completeness
    best = max(
        events,
        key=lambda e: (
            len(e.get('description', '') or ''),
            1 if e.get('venue') else 0,
            1 if e.get('url') else 0
        )
    )

    # Collect all sources and URLs
    sources = []
    urls = []

    for event in events:
        source = event.get('source')
        if source and source not in sources:
            sources.append(source)

        url = event.get('url')
        if url and url not in urls:
            urls.append(url)

    # Update best event with merged data
    best = best.copy()  # Don't modify original
    best['sources'] = sources
    best['urls'] = urls
    best['duplicate_count'] = len(events)

    return best


def _apply_fuzzy_deduplication(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Apply fuzzy matching to find and merge similar events that may have slightly different titles.

    Args:
        events: List of events to deduplicate with fuzzy matching

    Returns:
        List of deduplicated events
    """
    if len(events) <= 1:
        return events

    # Track which events have been merged
    merged_indices = set()
    unique_events = []

    for i, event1 in enumerate(events):
        if i in merged_indices:
            continue

        # Find similar events
        similar_group = [event1]
        for j in range(i + 1, len(events)):
            if j in merged_indices:
                continue

            event2 = events[j]
            if are_events_similar(event1, event2):
                similar_group.append(event2)
                merged_indices.add(j)

        # Merge similar events
        if len(similar_group) > 1:
            merged_event = _merge_duplicate_events(similar_group)
            unique_events.append(merged_event)
            logger.debug(
                f"Fuzzy matched {len(similar_group)} events: {event1.get('title')}"
            )
        else:
            unique_events.append(event1)

    return unique_events
