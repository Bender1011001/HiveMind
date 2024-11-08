from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from .logging_setup import setup_logging

# Set up centralized logging
logger = setup_logging(__name__)

class CacheEntry:
    """Represents a single cache entry with TTL functionality."""

    def __init__(self, value: Any, ttl_minutes: int = 30):
        """Initialize a cache entry with a value and TTL."""
        self.value = value
        self.timestamp = datetime.now()
        self.ttl = timedelta(minutes=ttl_minutes)

    def is_valid(self) -> bool:
        """Check if the cache entry is still valid based on TTL."""
        return datetime.now() - self.timestamp < self.ttl

    def time_until_expiry(self) -> timedelta:
        """Calculate time remaining until entry expires."""
        return self.ttl - (datetime.now() - self.timestamp)

class Cache:
    """In-memory cache implementation with TTL support."""

    def __init__(self):
        """Initialize an empty cache store."""
        logger.info("Initializing cache system")
        self._store: Dict[str, CacheEntry] = {}
        logger.debug("Cache store initialized successfully")

    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve a value from cache if it exists and is valid.
        Returns None if the key doesn't exist or the entry has expired.
        """
        try:
            logger.debug(f"Attempting to retrieve cache entry for key: {key}")
            entry = self._store.get(key)

            if entry:
                if entry.is_valid():
                    time_left = entry.time_until_expiry()
                    logger.info(f"Cache hit for key: {key} (expires in {time_left.total_seconds():.1f} seconds)")
                    return entry.value
                else:
                    # Entry exists but has expired
                    logger.info(f"Cache entry expired for key: {key}")
                    del self._store[key]
                    return None
            else:
                logger.debug(f"Cache miss for key: {key}")
                return None

        except Exception as e:
            logger.error(f"Error retrieving from cache for key {key}: {str(e)}", exc_info=True)
            return None

    def set(self, key: str, value: Any, ttl_minutes: int = 30) -> None:
        """
        Store a value in the cache with a specified TTL.
        Default TTL is 30 minutes.
        """
        try:
            logger.debug(f"Setting cache entry for key: {key} with TTL: {ttl_minutes} minutes")
            self._store[key] = CacheEntry(value, ttl_minutes)
            logger.info(f"Successfully cached value for key: {key} (expires in {ttl_minutes} minutes)")
        except Exception as e:
            logger.error(f"Error setting cache value for key {key}: {str(e)}", exc_info=True)
            raise

    def invalidate(self, key: str) -> None:
        """Remove a specific key from the cache."""
        try:
            logger.debug(f"Attempting to invalidate cache for key: {key}")
            if key in self._store:
                del self._store[key]
                logger.info(f"Successfully invalidated cache for key: {key}")
            else:
                logger.debug(f"No cache entry found to invalidate for key: {key}")
        except Exception as e:
            logger.error(f"Error invalidating cache for key {key}: {str(e)}", exc_info=True)
            raise

    def clear(self) -> None:
        """Clear all entries from the cache."""
        try:
            logger.debug(f"Clearing all cache entries (current size: {len(self._store)})")
            self._store.clear()
            logger.info("Successfully cleared all cache entries")
        except Exception as e:
            logger.error(f"Error clearing cache: {str(e)}", exc_info=True)
            raise

    def cleanup_expired(self) -> None:
        """Remove all expired entries from the cache."""
        try:
            logger.debug("Starting cleanup of expired cache entries")
            initial_size = len(self._store)

            expired_keys = [
                key for key, entry in self._store.items()
                if not entry.is_valid()
            ]

            for key in expired_keys:
                del self._store[key]

            if expired_keys:
                logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
                logger.debug(f"Cache size reduced from {initial_size} to {len(self._store)}")
            else:
                logger.debug("No expired cache entries found during cleanup")

        except Exception as e:
            logger.error(f"Error cleaning up expired cache entries: {str(e)}", exc_info=True)
            raise

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the current cache state."""
        try:
            total_entries = len(self._store)
            valid_entries = sum(1 for entry in self._store.values() if entry.is_valid())
            expired_entries = total_entries - valid_entries

            stats = {
                'total_entries': total_entries,
                'valid_entries': valid_entries,
                'expired_entries': expired_entries,
                'memory_usage_bytes': sum(len(str(entry.value)) for entry in self._store.values())
            }

            logger.debug(f"Cache statistics: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Error calculating cache statistics: {str(e)}", exc_info=True)
            raise
