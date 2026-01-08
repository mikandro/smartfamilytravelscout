"""
Redis-based flight deduplication cache to avoid redundant expensive comparison operations.

This module provides a caching layer that stores hashes of flight attributes to quickly
identify flights that have already been processed, eliminating the need for repeated
deduplication operations on the same data.

Example:
    >>> from app.utils.flight_cache import FlightDeduplicationCache
    >>> cache = FlightDeduplicationCache(redis_client)
    >>>
    >>> # Check if flight was already processed
    >>> if await cache.is_flight_cached(flight_data):
    >>>     print("Flight already processed")
    >>> else:
    >>>     # Process flight and cache it
    >>>     await cache.cache_flight(flight_data)
"""

import hashlib
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class FlightDeduplicationCache:
    """
    Redis-based cache for flight deduplication.

    This cache stores MD5 hashes of flight attributes (origin, destination, departure date/time,
    airline, and price) to quickly identify flights that have already been seen and processed.

    Benefits:
    - Eliminates redundant expensive comparison operations
    - Reduces CPU consumption during deduplication
    - Improves performance when handling extensive flight datasets

    Cache keys are automatically expired after a configurable TTL (default: 1 hour).

    Attributes:
        redis: Redis client instance
        ttl: Time-to-live for cache entries in seconds (default: 3600 = 1 hour)
        key_prefix: Prefix for all Redis keys (default: "flight:")
    """

    def __init__(
        self,
        redis_client: Redis,
        ttl: int = 3600,
        key_prefix: str = "flight:",
    ):
        """
        Initialize the flight deduplication cache.

        Args:
            redis_client: Redis client for caching
            ttl: Cache TTL in seconds (default: 3600 = 1 hour)
            key_prefix: Prefix for Redis keys (default: "flight:")
        """
        self.redis = redis_client
        self.ttl = ttl
        self.key_prefix = key_prefix

        logger.info(f"Initialized FlightDeduplicationCache with TTL: {ttl}s")

    def _generate_flight_hash(self, flight: Dict[str, Any]) -> str:
        """
        Generate a unique hash for a flight based on its key attributes.

        The hash is computed from:
        - origin airport
        - destination airport
        - departure date
        - departure time
        - airline
        - price (rounded to 2 decimals)

        This creates a unique identifier for each flight that can be used for
        quick duplicate checking.

        Args:
            flight: Flight dictionary with attributes

        Returns:
            MD5 hash string (32 characters)

        Example:
            >>> hash_value = cache._generate_flight_hash({
            ...     "origin_airport": "MUC",
            ...     "destination_airport": "LIS",
            ...     "departure_date": "2025-12-20",
            ...     "departure_time": "08:30",
            ...     "airline": "TAP",
            ...     "price_per_person": 150.50
            ... })
            >>> print(hash_value)  # "a1b2c3d4e5f6..."
        """
        # Extract key attributes
        origin = flight.get("origin_airport", "").upper()
        destination = flight.get("destination_airport", "").upper()
        dep_date = flight.get("departure_date", "")
        dep_time = flight.get("departure_time", "00:00")
        airline = flight.get("airline", "Unknown").upper()

        # Get price (prefer price_per_person, fallback to total_price)
        price = flight.get("price_per_person")
        if price is None:
            total_price = flight.get("total_price", 0)
            price = total_price / 4 if total_price else 0

        # Round price to 2 decimals to avoid minor variations
        price = round(float(price), 2) if price else 0.0

        # Create hash string
        hash_input = f"{origin}_{destination}_{dep_date}_{dep_time}_{airline}_{price}"

        # Generate MD5 hash
        flight_hash = hashlib.md5(hash_input.encode()).hexdigest()

        return flight_hash

    async def is_flight_cached(self, flight: Dict[str, Any]) -> bool:
        """
        Check if a flight has already been processed and cached.

        Args:
            flight: Flight dictionary with attributes

        Returns:
            True if flight exists in cache, False otherwise

        Example:
            >>> if await cache.is_flight_cached(flight_data):
            ...     print("Already processed")
        """
        try:
            flight_hash = self._generate_flight_hash(flight)
            cache_key = f"{self.key_prefix}{flight_hash}"

            exists = await self.redis.exists(cache_key)

            if exists:
                logger.debug(f"Cache HIT for flight hash: {flight_hash}")
            else:
                logger.debug(f"Cache MISS for flight hash: {flight_hash}")

            return bool(exists)

        except Exception as e:
            logger.warning(f"Error checking flight cache: {e}")
            # On error, assume not cached (fail open)
            return False

    async def cache_flight(self, flight: Dict[str, Any]) -> bool:
        """
        Add a flight to the cache with automatic TTL expiration.

        Args:
            flight: Flight dictionary with attributes

        Returns:
            True if successfully cached, False on error

        Example:
            >>> await cache.cache_flight(flight_data)
        """
        try:
            flight_hash = self._generate_flight_hash(flight)
            cache_key = f"{self.key_prefix}{flight_hash}"

            # Store with TTL (value is timestamp for debugging)
            timestamp = datetime.now().isoformat()
            await self.redis.setex(cache_key, self.ttl, timestamp)

            logger.debug(f"Cached flight hash: {flight_hash} (TTL: {self.ttl}s)")

            return True

        except Exception as e:
            logger.warning(f"Error caching flight: {e}")
            return False

    async def cache_multiple_flights(self, flights: list[Dict[str, Any]]) -> int:
        """
        Cache multiple flights in a batch operation.

        This is more efficient than calling cache_flight() in a loop.

        Args:
            flights: List of flight dictionaries

        Returns:
            Number of flights successfully cached

        Example:
            >>> cached_count = await cache.cache_multiple_flights(unique_flights)
            >>> print(f"Cached {cached_count} flights")
        """
        cached_count = 0

        try:
            # Use pipeline for batch operations
            async with self.redis.pipeline() as pipe:
                timestamp = datetime.now().isoformat()

                for flight in flights:
                    try:
                        flight_hash = self._generate_flight_hash(flight)
                        cache_key = f"{self.key_prefix}{flight_hash}"
                        pipe.setex(cache_key, self.ttl, timestamp)
                        cached_count += 1
                    except Exception as e:
                        logger.warning(f"Error adding flight to pipeline: {e}")
                        continue

                # Execute all commands in one go
                await pipe.execute()

            logger.info(f"Cached {cached_count} flights in batch operation")

            return cached_count

        except Exception as e:
            logger.error(f"Error in batch caching: {e}")
            return 0

    async def filter_uncached_flights(self, flights: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
        """
        Filter a list of flights to return only those not in cache.

        This is useful for pre-filtering flights before expensive deduplication operations.

        Args:
            flights: List of flight dictionaries

        Returns:
            List of flights that are not in cache

        Example:
            >>> all_flights = [...]  # 1000 flights
            >>> uncached = await cache.filter_uncached_flights(all_flights)
            >>> print(f"Need to process {len(uncached)} new flights")
        """
        uncached_flights = []

        try:
            # Build list of cache keys
            cache_keys = []
            flight_mapping = {}  # Map cache_key -> flight

            for flight in flights:
                try:
                    flight_hash = self._generate_flight_hash(flight)
                    cache_key = f"{self.key_prefix}{flight_hash}"
                    cache_keys.append(cache_key)
                    flight_mapping[cache_key] = flight
                except Exception as e:
                    logger.warning(f"Error generating hash for flight: {e}")
                    # Include flights with errors in uncached list (fail open)
                    uncached_flights.append(flight)

            # Batch check existence using mget (more efficient than individual exists() calls)
            if cache_keys:
                # Use EXISTS for batch checking
                # Note: Redis doesn't have a direct batch EXISTS, so we use pipeline
                async with self.redis.pipeline() as pipe:
                    for key in cache_keys:
                        pipe.exists(key)

                    results = await pipe.execute()

                    # Filter uncached flights
                    for key, exists in zip(cache_keys, results):
                        if not exists:
                            uncached_flights.append(flight_mapping[key])

            logger.info(
                f"Filtered {len(flights)} flights: {len(uncached_flights)} uncached, "
                f"{len(flights) - len(uncached_flights)} already cached"
            )

            return uncached_flights

        except Exception as e:
            logger.error(f"Error filtering flights: {e}")
            # On error, return all flights (fail open)
            return flights

    async def clear_cache(self) -> int:
        """
        Clear all flight cache entries.

        Use with caution - this will remove all cached flight data.

        Returns:
            Number of keys deleted

        Example:
            >>> deleted = await cache.clear_cache()
            >>> print(f"Cleared {deleted} cached flights")
        """
        try:
            # Find all keys with our prefix
            keys = []
            async for key in self.redis.scan_iter(match=f"{self.key_prefix}*"):
                keys.append(key)

            if keys:
                deleted = await self.redis.delete(*keys)
                logger.info(f"Cleared {deleted} flight cache entries")
                return deleted
            else:
                logger.info("No flight cache entries to clear")
                return 0

        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return 0

    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the flight cache.

        Returns:
            Dictionary with cache statistics:
            - total_keys: Total number of cached flights
            - key_prefix: Cache key prefix

        Example:
            >>> stats = await cache.get_cache_stats()
            >>> print(f"Cached flights: {stats['total_keys']}")
        """
        try:
            # Count keys with our prefix
            total_keys = 0
            async for _ in self.redis.scan_iter(match=f"{self.key_prefix}*"):
                total_keys += 1

            return {
                "total_keys": total_keys,
                "key_prefix": self.key_prefix,
                "ttl": self.ttl,
            }

        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {
                "total_keys": 0,
                "key_prefix": self.key_prefix,
                "ttl": self.ttl,
                "error": str(e),
            }
