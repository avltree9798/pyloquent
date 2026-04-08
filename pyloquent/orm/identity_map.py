"""Lightweight identity map for Pyloquent models.

An identity map ensures that, within a given scope, only one Python object
represents each database row.  This prevents duplicate model instances for
the same primary key and makes ``==`` comparisons predictable.

Usage::

    from pyloquent.orm.identity_map import IdentityMap

    # Create a scope (e.g. per request, per test, or per unit-of-work)
    identity_map = IdentityMap()

    # Register models as they are hydrated from the database
    user = identity_map.get_or_register(User, 1, raw_row)

    # Subsequent lookups return the *same* Python object
    same_user = identity_map.get(User, 1)
    assert same_user is user

Context-manager support for scoped sessions::

    async with IdentityMap.session() as imap:
        user = await User.query.with_identity_map(imap).find(1)
"""

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional, Tuple, Type, TypeVar

T = TypeVar("T")

# (ModelClass, primary_key_value) → model instance
_IdentityKey = Tuple[type, Any]


class IdentityMap:
    """Stores model instances keyed by (class, primary_key) pairs.

    All methods are synchronous because the map itself performs no I/O.
    Database access remains fully async through the normal QueryBuilder path.
    """

    def __init__(self) -> None:
        """Initialise an empty identity map."""
        self._store: Dict[_IdentityKey, Any] = {}

    # ------------------------------------------------------------------
    # Core interface
    # ------------------------------------------------------------------

    def get(self, model_class: Type[T], key: Any) -> Optional[T]:
        """Retrieve a cached model instance.

        Args:
            model_class: The model class (e.g. ``User``).
            key: Primary key value (scalar or tuple for composite keys).

        Returns:
            Cached instance, or ``None`` if not present.
        """
        return self._store.get((model_class, self._normalise_key(key)))

    def register(self, model_class: Type[T], key: Any, instance: T) -> T:
        """Store a model instance in the map.

        Args:
            model_class: The model class.
            key: Primary key value.
            instance: Model instance to cache.

        Returns:
            The stored instance (the same object passed in).
        """
        self._store[(model_class, self._normalise_key(key))] = instance
        return instance

    def get_or_register(
        self,
        model_class: Type[T],
        key: Any,
        factory: Any,
    ) -> T:
        """Return an existing cached instance or create and register a new one.

        Args:
            model_class: The model class.
            key: Primary key value.
            factory: Either an already-constructed model instance *or* a
                ``Dict[str, Any]`` of raw database columns used to hydrate
                a new instance.

        Returns:
            The cached or newly created model instance.
        """
        existing = self.get(model_class, key)
        if existing is not None:
            return existing

        if isinstance(factory, dict):
            instance = model_class(**factory)
        else:
            instance = factory

        return self.register(model_class, key, instance)

    def evict(self, model_class: Type[T], key: Any) -> None:
        """Remove an entry from the identity map.

        Args:
            model_class: The model class.
            key: Primary key value.
        """
        self._store.pop((model_class, self._normalise_key(key)), None)

    def clear(self) -> None:
        """Remove all entries from the identity map."""
        self._store.clear()

    def __len__(self) -> int:
        """Return the number of cached entries."""
        return len(self._store)

    def __contains__(self, item: Tuple[type, Any]) -> bool:
        """Support ``(ModelClass, key) in identity_map`` syntax."""
        cls, key = item
        return (cls, self._normalise_key(key)) in self._store

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    @staticmethod
    @asynccontextmanager
    async def session() -> AsyncIterator["IdentityMap"]:
        """Async context manager that yields a fresh, scoped IdentityMap.

        On exit the map is cleared automatically.

        Yields:
            A new :class:`IdentityMap` instance.

        Example::

            async with IdentityMap.session() as imap:
                user = await User.query.with_identity_map(imap).find(1)
        """
        imap = IdentityMap()
        try:
            yield imap
        finally:
            imap.clear()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_key(key: Any) -> Any:
        """Convert mutable composite key dicts to hashable tuples.

        Args:
            key: Scalar or dict primary key.

        Returns:
            Hashable key.
        """
        if isinstance(key, dict):
            return tuple(sorted(key.items()))
        return key
