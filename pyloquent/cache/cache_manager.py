"""Cache manager for query caching."""

import hashlib
import json
from typing import Any, Dict, Optional, Type, Union

from pyloquent.cache.stores import CacheStore, FileStore, MemoryStore, RedisStore


class CacheManager:
    """Manager for query result caching.

    This class provides a unified interface for caching query results
    with support for multiple backend stores.

    Example:
        # Using memory store
        cache = CacheManager.store(MemoryStore())

        # Using file store
        cache = CacheManager.store(FileStore("/path/to/cache"))

        # Using Redis
        cache = CacheManager.store(RedisStore(host="localhost", port=6379))

        # Cache a query result
        result = await cache.remember("users:all", 300, lambda: User.all())
    """

    _instance: Optional["CacheManager"] = None
    _store: Optional[CacheStore] = None

    def __init__(self, store: Optional[CacheStore] = None):
        """Initialize the cache manager.

        Args:
            store: Cache store implementation
        """
        if store:
            self._store = store

    @classmethod
    def store(cls, store: Optional[CacheStore] = None) -> "CacheManager":
        """Get or set the cache store.

        Args:
            store: Cache store to use

        Returns:
            CacheManager instance
        """
        if cls._instance is None:
            cls._instance = cls(store)
        elif store is not None:
            cls._instance._store = store

        return cls._instance

    @classmethod
    def get_store(cls) -> Optional[CacheStore]:
        """Get the current cache store.

        Returns:
            Current cache store or None
        """
        if cls._instance is None:
            return None
        return cls._instance._store

    async def get(self, key: str) -> Any:
        """Get an item from the cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        if self._store is None:
            return None

        return await self._store.get(key)

    async def put(self, key: str, value: Any, seconds: Optional[int] = None) -> None:
        """Store an item in the cache.

        Args:
            key: Cache key
            value: Value to cache
            seconds: Time-to-live in seconds
        """
        if self._store is None:
            return

        await self._store.put(key, value, seconds)

    async def forget(self, key: str) -> bool:
        """Remove an item from the cache.

        Args:
            key: Cache key

        Returns:
            True if removed, False if not found
        """
        if self._store is None:
            return False

        return await self._store.forget(key)

    async def flush(self) -> None:
        """Clear all items from the cache."""
        if self._store is None:
            return

        await self._store.flush()

    async def has(self, key: str) -> bool:
        """Check if an item exists in the cache.

        Args:
            key: Cache key

        Returns:
            True if exists
        """
        if self._store is None:
            return False

        return await self._store.has(key)

    async def remember(self, key: str, seconds: Optional[int], callback: callable) -> Any:
        """Get an item from cache or execute callback and store result.

        Args:
            key: Cache key
            seconds: Time-to-live in seconds
            callback: Function to execute if not cached

        Returns:
            Cached or computed value
        """
        # Try to get from cache
        value = await self.get(key)

        if value is not None:
            return value

        # Execute callback
        if asyncio.iscoroutinefunction(callback):
            value = await callback()
        else:
            value = callback()

        # Store in cache
        await self.put(key, value, seconds)

        return value

    async def remember_forever(self, key: str, callback: callable) -> Any:
        """Get an item from cache or execute callback and store forever.

        Args:
            key: Cache key
            callback: Function to execute if not cached

        Returns:
            Cached or computed value
        """
        return await self.remember(key, None, callback)

    async def sear(self, key: str, callback: callable) -> Any:
        """Get an item from cache or execute callback and store forever (alias).

        Args:
            key: Cache key
            callback: Function to execute if not cached

        Returns:
            Cached or computed value
        """
        return await self.remember_forever(key, callback)

    def tags(self, *tags: str) -> "TaggedCacheManager":
        """Get a tagged cache instance.

        Args:
            *tags: Tags to apply

        Returns:
            TaggedCacheManager instance
        """
        return TaggedCacheManager(self, list(tags))

    @staticmethod
    def key(*components: str) -> str:
        """Generate a cache key from components.

        Args:
            *components: Key components

        Returns:
            Cache key string
        """
        return ":".join(str(c) for c in components)

    @staticmethod
    def query_key(sql: str, bindings: list) -> str:
        """Generate a cache key for a query.

        Args:
            sql: SQL string
            bindings: Query bindings

        Returns:
            Cache key string
        """
        data = json.dumps({"sql": sql, "bindings": bindings}, sort_keys=True)
        return hashlib.md5(data.encode()).hexdigest()


# Import asyncio for remember method
import asyncio


class TaggedCacheManager:
    """Cache manager with tag support."""

    def __init__(self, manager: CacheManager, tags: list):
        """Initialize tagged cache manager.

        Args:
            manager: Parent cache manager
            tags: List of tags
        """
        self._manager = manager
        self._tags = tags

    def _tagged_key(self, key: str) -> str:
        """Create a tagged key.

        Args:
            key: Original key

        Returns:
            Tagged key
        """
        tag_string = ":".join(sorted(self._tags))
        return f"tag:{tag_string}:{key}"

    async def get(self, key: str) -> Any:
        """Get an item from the cache."""
        return await self._manager.get(self._tagged_key(key))

    async def put(self, key: str, value: Any, seconds: Optional[int] = None) -> None:
        """Store an item in the cache."""
        await self._manager.put(self._tagged_key(key), value, seconds)

    async def forget(self, key: str) -> bool:
        """Remove an item from the cache."""
        return await self._manager.forget(self._tagged_key(key))

    async def has(self, key: str) -> bool:
        """Check if an item exists in the cache."""
        return await self._manager.has(self._tagged_key(key))

    async def remember(self, key: str, seconds: Optional[int], callback: callable) -> Any:
        """Get an item from cache or execute callback and store result."""
        tagged_key = self._tagged_key(key)

        # Try to get from cache
        value = await self._manager.get(tagged_key)

        if value is not None:
            return value

        # Execute callback
        if asyncio.iscoroutinefunction(callback):
            value = await callback()
        else:
            value = callback()

        # Store in cache
        await self._manager.put(tagged_key, value, seconds)

        return value

    async def flush(self) -> None:
        """Clear all items with these tags."""
        # This would require tracking all keys per tag
        # For now, this is a no-op
        pass
