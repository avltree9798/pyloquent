"""Base database connection class."""

import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:  # pragma: no cover
    from pyloquent.grammars.grammar import Grammar


class Connection(ABC):
    """Abstract base class for database connections.

    This class defines the interface that all database connections must implement.
    Concrete implementations handle the specifics of each database driver.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize the connection with configuration.

        Args:
            config: Dictionary containing connection parameters.
                Additional health-check keys recognised by all drivers:

                - ``pool_pre_ping`` (bool, default ``False``): Execute
                  ``SELECT 1`` before every query and transparently reconnect
                  if the connection is stale.  Equivalent to SQLAlchemy's
                  ``pool_pre_ping``.
                - ``pool_recycle`` (int, default ``None``): Maximum age in
                  seconds before the connection (or pool) is recycled.  For
                  the asyncpg/aiomysql pool drivers this is forwarded as a
                  native pool option; for SQLite it triggers a reconnect on
                  the next query after the threshold is exceeded.
                - ``reconnect_on_error`` (bool, default ``False``): On any
                  query error, attempt a single disconnect/reconnect and
                  retry the original statement once before re-raising.
        """
        self.config = config
        self._grammar: Optional["Grammar"] = None
        self._connected = False
        self._pool_pre_ping: bool = bool(config.get("pool_pre_ping", False))
        self._pool_recycle: Optional[int] = config.get("pool_recycle", None)
        self._reconnect_on_error: bool = bool(config.get("reconnect_on_error", False))
        self._connected_at: Optional[float] = None
        self._pinging: bool = False  # re-entry guard for ensure_connected → ping → fetch_one

    @property
    def grammar(self) -> "Grammar":
        """Get the grammar instance for this connection.

        Returns:
            Grammar instance
        """
        if self._grammar is None:
            self._grammar = self.get_grammar()
        return self._grammar

    @abstractmethod
    async def connect(self) -> None:
        """Establish the database connection.

        Raises:
            ConnectionError: If connection fails
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the database connection."""
        pass

    @abstractmethod
    async def execute(self, sql: str, bindings: Optional[List[Any]] = None) -> Any:
        """Execute a SQL statement.

        Args:
            sql: SQL statement to execute
            bindings: Optional list of parameter bindings

        Returns:
            Execution result (e.g., last insert ID for INSERT, row count for UPDATE/DELETE)

        Raises:
            QueryException: If execution fails
        """
        pass

    async def ping(self) -> bool:
        """Check whether the connection is alive by issuing ``SELECT 1``.

        The default implementation calls ``fetch_one`` with the re-entry guard
        cleared so that it does not recurse back into ``ensure_connected``.
        Subclasses should override this with a lighter-weight mechanism that
        bypasses the normal query path entirely.

        Returns:
            ``True`` if the connection is responsive, ``False`` otherwise.
        """
        try:
            # Temporarily suppress the pre-ping flag so that the fetch_one
            # call used for the health check does not re-enter ensure_connected
            # and cause infinite recursion.
            original = self._pool_pre_ping
            self._pool_pre_ping = False
            try:
                await self.fetch_one("SELECT 1")
            finally:
                self._pool_pre_ping = original
            return True
        except Exception:
            return False

    async def ensure_connected(self) -> None:
        """Re-establish the connection when health-check options indicate it
        may be stale.

        Called automatically by driver ``execute`` / ``fetch_*`` methods when
        ``pool_pre_ping`` or ``pool_recycle`` is enabled.  Safe to call
        manually at any time.
        """
        if not self._connected or self._pinging:
            return

        needs_reconnect = False

        if self._pool_recycle is not None and self._connected_at is not None:
            if time.monotonic() - self._connected_at > self._pool_recycle:
                needs_reconnect = True

        if not needs_reconnect and self._pool_pre_ping:
            self._pinging = True
            try:
                if not await self.ping():
                    needs_reconnect = True
            finally:
                self._pinging = False

        if needs_reconnect:
            await self.disconnect()
            await self.connect()

    async def execute_many(self, sql: str, rows: List[List[Any]]) -> int:
        """Execute a parameterised statement for multiple rows (batch insert).

        The default implementation falls back to executing one row at a time.
        Driver subclasses should override this with native executemany support.

        Args:
            sql: SQL statement with placeholders
            rows: List of binding lists, one per row

        Returns:
            Total number of rows affected
        """
        count = 0
        for row in rows:
            await self.execute(sql, row)
            count += 1
        return count

    @abstractmethod
    async def fetch_all(
        self, sql: str, bindings: Optional[List[Any]] = None
    ) -> List[Dict[str, Any]]:
        """Execute a query and return all results.

        Args:
            sql: SQL SELECT statement
            bindings: Optional list of parameter bindings

        Returns:
            List of dictionaries representing rows

        Raises:
            QueryException: If execution fails
        """
        pass

    @abstractmethod
    async def fetch_one(
        self, sql: str, bindings: Optional[List[Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Execute a query and return the first result.

        Args:
            sql: SQL SELECT statement
            bindings: Optional list of parameter bindings

        Returns:
            Dictionary representing the row, or None if no results

        Raises:
            QueryException: If execution fails
        """
        pass

    @abstractmethod
    def get_grammar(self) -> "Grammar":
        """Get the SQL grammar for this connection type.

        Returns:
            Grammar instance
        """
        pass

    async def begin_transaction(self) -> None:  # pragma: no cover
        """Begin a database transaction.

        Raises:
            QueryException: If transaction fails to start
        """
        await self.execute("BEGIN")  # pragma: no cover

    async def commit(self) -> None:  # pragma: no cover
        """Commit the current transaction.

        Raises:
            QueryException: If commit fails
        """
        await self.execute("COMMIT")  # pragma: no cover

    async def rollback(self) -> None:  # pragma: no cover
        """Rollback the current transaction.

        Raises:
            QueryException: If rollback fails
        """
        await self.execute("ROLLBACK")  # pragma: no cover

    def table(self, name: str) -> "QueryBuilder":
        """Start a query builder for a table.

        Args:
            name: Table name

        Returns:
            QueryBuilder instance
        """
        from pyloquent.query.builder import QueryBuilder

        return QueryBuilder(self.grammar, self).from_(name)

    def is_connected(self) -> bool:
        """Check if the connection is established.

        Returns:
            True if connected
        """
        return self._connected
