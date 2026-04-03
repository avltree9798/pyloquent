"""Cache store implementations."""

import hashlib
import json
import pickle
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Union


class CacheStore(ABC):
    """Abstract base class for cache stores."""

    @abstractmethod
    async def get(self, key: str) -> Any:
        """Get an item from the cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        pass

    @abstractmethod
    async def put(self, key: str, value: Any, seconds: Optional[int] = None) -> None:
        """Store an item in the cache.

        Args:
            key: Cache key
            value: Value to cache
            seconds: Time-to-live in seconds
        """
        pass

    @abstractmethod
    async def forget(self, key: str) -> bool:
        """Remove an item from the cache.

        Args:
            key: Cache key

        Returns:
            True if removed, False if not found
        """
        pass

    @abstractmethod
    async def flush(self) -> None:
        """Clear all items from the cache."""
        pass

    @abstractmethod
    async def has(self, key: str) -> bool:
        """Check if an item exists in the cache.

        Args:
            key: Cache key

        Returns:
            True if exists
        """
        pass


class MemoryStore(CacheStore):
    """In-memory cache store."""

    def __init__(self):
        """Initialize the memory store."""
        self._storage: Dict[str, Dict[str, Any]] = {}

    async def get(self, key: str) -> Any:
        """Get an item from the cache."""
        if key not in self._storage:
            return None

        item = self._storage[key]

        # Check expiration
        if item["expires_at"] is not None:
            if datetime.now() > item["expires_at"]:
                await self.forget(key)
                return None

        return item["value"]

    async def put(self, key: str, value: Any, seconds: Optional[int] = None) -> None:
        """Store an item in the cache."""
        expires_at = None
        if seconds is not None:
            expires_at = datetime.now() + timedelta(seconds=seconds)

        self._storage[key] = {
            "value": value,
            "expires_at": expires_at,
        }

    async def forget(self, key: str) -> bool:
        """Remove an item from the cache."""
        if key in self._storage:
            del self._storage[key]
            return True
        return False

    async def flush(self) -> None:
        """Clear all items from the cache."""
        self._storage.clear()

    async def has(self, key: str) -> bool:
        """Check if an item exists in the cache."""
        if key not in self._storage:
            return False

        item = self._storage[key]

        # Check expiration
        if item["expires_at"] is not None:
            if datetime.now() > item["expires_at"]:
                await self.forget(key)
                return False

        return True


class FileStore(CacheStore):
    """File-based cache store."""

    def __init__(self, path: str = "cache"):
        """Initialize the file store.

        Args:
            path: Directory path for cache files
        """
        self._path = Path(path)
        self._path.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, key: str) -> Path:
        """Get the file path for a cache key.

        Args:
            key: Cache key

        Returns:
            File path
        """
        # Hash the key to create a safe filename
        hashed = hashlib.md5(key.encode()).hexdigest()
        return self._path / f"{hashed}.cache"

    async def get(self, key: str) -> Any:
        """Get an item from the cache."""
        file_path = self._get_file_path(key)

        if not file_path.exists():
            return None

        try:
            with open(file_path, "rb") as f:
                data = pickle.load(f)

            # Check expiration
            if data["expires_at"] is not None:
                if datetime.now() > data["expires_at"]:
                    await self.forget(key)
                    return None

            return data["value"]
        except (pickle.PickleError, IOError, KeyError):
            return None

    async def put(self, key: str, value: Any, seconds: Optional[int] = None) -> None:
        """Store an item in the cache."""
        file_path = self._get_file_path(key)

        expires_at = None
        if seconds is not None:
            expires_at = datetime.now() + timedelta(seconds=seconds)

        data = {
            "value": value,
            "expires_at": expires_at,
        }

        with open(file_path, "wb") as f:
            pickle.dump(data, f)

    async def forget(self, key: str) -> bool:
        """Remove an item from the cache."""
        file_path = self._get_file_path(key)

        if file_path.exists():
            file_path.unlink()
            return True
        return False

    async def flush(self) -> None:
        """Clear all items from the cache."""
        for file_path in self._path.glob("*.cache"):
            file_path.unlink()

    async def has(self, key: str) -> bool:
        """Check if an item exists in the cache."""
        file_path = self._get_file_path(key)

        if not file_path.exists():
            return False

        try:
            with open(file_path, "rb") as f:
                data = pickle.load(f)

            # Check expiration
            if data["expires_at"] is not None:
                if datetime.now() > data["expires_at"]:
                    await self.forget(key)
                    return False

            return True
        except (pickle.PickleError, IOError, KeyError):
            return False


class RedisStore(CacheStore):
    """Redis cache store."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        prefix: str = "pyloquent:",
    ):
        """Initialize the Redis store.

        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            password: Redis password
            prefix: Key prefix
        """
        self._host = host
        self._port = port
        self._db = db
        self._password = password
        self._prefix = prefix
        self._redis: Any = None

    async def _get_redis(self) -> Any:
        """Get or create Redis connection."""
        if self._redis is None:
            try:
                import redis.asyncio as aioredis

                self._redis = aioredis.Redis(
                    host=self._host,
                    port=self._port,
                    db=self._db,
                    password=self._password,
                    decode_responses=False,
                )
            except ImportError:
                raise ImportError(
                    "Redis support requires 'redis' package. Install with: pip install redis"
                )

        return self._redis

    def _make_key(self, key: str) -> str:
        """Add prefix to key.

        Args:
            key: Original key

        Returns:
            Prefixed key
        """
        return f"{self._prefix}{key}"

    async def get(self, key: str) -> Any:
        """Get an item from the cache."""
        redis = await self._get_redis()
        prefixed_key = self._make_key(key)

        data = await redis.get(prefixed_key)

        if data is None:
            return None

        try:
            return pickle.loads(data)
        except pickle.PickleError:
            return None

    async def put(self, key: str, value: Any, seconds: Optional[int] = None) -> None:
        """Store an item in the cache."""
        redis = await self._get_redis()
        prefixed_key = self._make_key(key)

        data = pickle.dumps(value)

        if seconds is not None:
            await redis.setex(prefixed_key, seconds, data)
        else:
            await redis.set(prefixed_key, data)

    async def forget(self, key: str) -> bool:
        """Remove an item from the cache."""
        redis = await self._get_redis()
        prefixed_key = self._make_key(key)

        result = await redis.delete(prefixed_key)
        return result > 0

    async def flush(self) -> None:
        """Clear all items from the cache."""
        redis = await self._get_redis()

        # Only clear keys with our prefix
        pattern = f"{self._prefix}*"
        cursor = 0

        while True:
            cursor, keys = await redis.scan(cursor, match=pattern, count=100)
            if keys:
                await redis.delete(*keys)
            if cursor == 0:
                break

    async def has(self, key: str) -> bool:
        """Check if an item exists in the cache."""
        redis = await self._get_redis()
        prefixed_key = self._make_key(key)

        result = await redis.exists(prefixed_key)
        return result > 0


class TaggedCache(CacheStore):
    """Cache store with tagging support."""

    def __init__(self, store: CacheStore, tags: list):
        """Initialize tagged cache.

        Args:
            store: Underlying cache store
            tags: List of tags
        """
        self._store = store
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
        return await self._store.get(self._tagged_key(key))

    async def put(self, key: str, value: Any, seconds: Optional[int] = None) -> None:
        """Store an item in the cache."""
        await self._store.put(self._tagged_key(key), value, seconds)

    async def forget(self, key: str) -> bool:
        """Remove an item from the cache."""
        return await self._store.forget(self._tagged_key(key))

    async def flush(self) -> None:
        """Clear all items with these tags."""
        # This is a simplified implementation
        # A full implementation would track all keys per tag
        pass

    async def has(self, key: str) -> bool:
        """Check if an item exists in the cache."""
        return await self._store.has(self._tagged_key(key))

    async def flush_tag(self, tag: str) -> None:
        """Flush all items with a specific tag.

        Args:
            tag: Tag to flush
        """
        # This would require tracking all keys per tag
        # Implementation depends on the underlying store
        pass
