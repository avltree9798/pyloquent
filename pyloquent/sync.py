"""Synchronous wrappers for Pyloquent's async API.

Pyloquent is async-first by design, but sometimes a sync context is necessary
(scripts, notebooks, CLI tools, test helpers, or frameworks without async support).

:func:`run_sync` is the central utility: it executes any coroutine in a
blocking fashion using the current event loop (or a new one when none exists).

:class:`SyncConnectionManager` and :class:`SyncModel` provide thin sync facades
over their async counterparts.

Example — synchronous script::

    from pyloquent.sync import run_sync, SyncConnectionManager

    manager = SyncConnectionManager({
        'default': {'driver': 'sqlite', 'database': ':memory:'},
    })

    with manager:
        users = manager.table('users').where('active', True).get()
        for user in users:
            print(user)

Example — mixing with async code::

    import asyncio
    from pyloquent.sync import run_sync

    # Run any coroutine synchronously
    user = run_sync(User.find(1))
"""

from __future__ import annotations

import asyncio
import functools
from contextlib import contextmanager
from typing import Any, Coroutine, Generator, TypeVar

T = TypeVar("T")


def run_sync(coro: Coroutine[Any, Any, T]) -> T:
    """Execute a coroutine synchronously and return its result.

    Reuses an already-running event loop when available (e.g. inside Jupyter),
    otherwise creates a new one.

    Args:
        coro: An awaitable coroutine to run.

    Returns:
        The coroutine's return value.

    Raises:
        Exception: Any exception raised by the coroutine is re-raised.

    Example::

        user = run_sync(User.find(1))
        users = run_sync(User.where('active', True).get())
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        # Inside an already-running loop (e.g. Jupyter, uvloop).
        # Use a thread to avoid deadlock.
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()

    return asyncio.run(coro)


def sync(func):
    """Decorator that converts an async function into a synchronous one.

    Args:
        func: An ``async def`` function.

    Returns:
        A synchronous wrapper function.

    Example::

        @sync
        async def get_users():
            return await User.all()

        users = get_users()  # No await needed
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return run_sync(func(*args, **kwargs))
    return wrapper


class SyncConnectionManager:
    """Synchronous facade over :class:`~pyloquent.database.ConnectionManager`.

    Provides a ``with``-statement interface for scripts that cannot use
    ``async with``.

    Args:
        connections: Dict mapping connection names to config dicts.
        default: Name of the default connection (default: ``'default'``).

    Example::

        with SyncConnectionManager({'default': {'driver': 'sqlite', 'database': 'app.db'}}) as mgr:
            rows = mgr.table('users').get()
    """

    def __init__(self, connections: dict[str, Any], default: str = "default") -> None:
        """Initialise the sync manager.

        Args:
            connections: Connection configuration dict.
            default: Default connection name.
        """
        from pyloquent.database.manager import ConnectionManager

        self._manager = ConnectionManager()
        for name, config in connections.items():
            self._manager.add_connection(name, config)
        self._default = default

    def connect(self) -> None:
        """Open all connections synchronously."""
        run_sync(self._manager.connect_all())

    def disconnect(self) -> None:
        """Close all connections synchronously."""
        run_sync(self._manager.disconnect_all())

    def __enter__(self) -> "SyncConnectionManager":
        """Open connections on context entry."""
        self.connect()
        return self

    def __exit__(self, *_: Any) -> None:
        """Close connections on context exit."""
        self.disconnect()

    def table(self, name: str, connection: str | None = None) -> "SyncQueryProxy":
        """Return a synchronous query proxy for the given table.

        Args:
            name: Table name.
            connection: Named connection (uses default if not provided).

        Returns:
            :class:`SyncQueryProxy` instance.
        """
        conn = self._manager.connection(connection)
        builder = conn.table(name)
        return SyncQueryProxy(builder)


class SyncQueryProxy:
    """Wraps a :class:`~pyloquent.query.builder.QueryBuilder` with sync terminators.

    Chaining methods (``where``, ``order_by``, etc.) are forwarded transparently
    and return ``self`` so that calls remain fluent.  Terminal methods (``get``,
    ``first``, ``insert``, etc.) are executed synchronously via :func:`run_sync`.

    Args:
        builder: The underlying async QueryBuilder.
    """

    def __init__(self, builder: Any) -> None:
        """Initialise the sync proxy.

        Args:
            builder: Async QueryBuilder instance.
        """
        self._builder = builder

    # ------------------------------------------------------------------
    # Fluent pass-through (return self for chaining)
    # ------------------------------------------------------------------

    def __getattr__(self, name: str) -> Any:
        """Forward attribute access to the underlying builder.

        Terminal async methods are wrapped with :func:`run_sync`.
        Chainable builder methods are returned as-is so the proxy stays fluent.

        Args:
            name: Attribute or method name.

        Returns:
            Wrapped or direct attribute.
        """
        attr = getattr(self._builder, name)

        if not callable(attr):
            return attr

        @functools.wraps(attr)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = attr(*args, **kwargs)
            import asyncio
            if asyncio.iscoroutine(result):
                return run_sync(result)
            # Chainable builder methods return a QueryBuilder — re-wrap
            from pyloquent.query.builder import QueryBuilder
            if isinstance(result, QueryBuilder):
                self._builder = result
                return self
            return result

        return wrapper

    # ------------------------------------------------------------------
    # Explicit sync terminals for IDE auto-complete convenience
    # ------------------------------------------------------------------

    def get(self) -> Any:
        """Execute the query and return all results synchronously."""
        return run_sync(self._builder.get())

    def first(self) -> Any:
        """Return the first result synchronously."""
        return run_sync(self._builder.first())

    def find(self, id: Any) -> Any:
        """Find a record by primary key synchronously."""
        return run_sync(self._builder.find(id))

    def insert(self, values: Any) -> bool:
        """Insert records synchronously."""
        return run_sync(self._builder.insert(values))

    def update(self, values: Any) -> int:
        """Update records synchronously."""
        return run_sync(self._builder.update(values))

    def delete(self) -> int:
        """Delete records synchronously."""
        return run_sync(self._builder.delete())

    def count(self, column: str = "*") -> int:
        """Return the row count synchronously."""
        return run_sync(self._builder.count(column))

    def exists(self) -> bool:
        """Check if any records exist synchronously."""
        return run_sync(self._builder.exists())

    def pluck(self, column: str) -> list:
        """Get a list of column values synchronously."""
        return run_sync(self._builder.pluck(column))
