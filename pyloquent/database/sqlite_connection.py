"""SQLite database connection using aiosqlite."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from pyloquent.database.connection import Connection
from pyloquent.exceptions import QueryException

if TYPE_CHECKING:
    from pyloquent.grammars.grammar import Grammar


class SQLiteConnection(Connection):
    """SQLite database connection implementation.

    Uses aiosqlite for async SQLite support.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize SQLite connection.

        Args:
            config: Configuration dictionary with keys:
                - database: Path to database file or ':memory:'
                - timeout: Connection timeout (optional)
                - isolation_level: Transaction isolation level (optional)
        """
        super().__init__(config)
        self._db_path = config.get("database", ":memory:")
        self._timeout = config.get("timeout", 5.0)
        self._isolation_level = config.get("isolation_level", None)
        self._connection = None

    async def connect(self) -> None:
        """Establish SQLite connection.

        Raises:
            ConnectionError: If connection fails
        """
        import aiosqlite

        try:
            self._connection = await aiosqlite.connect(
                self._db_path,
                timeout=self._timeout,
                isolation_level=self._isolation_level,
            )
            # Enable foreign keys
            await self._connection.execute("PRAGMA foreign_keys = ON")
            # Return rows as dictionaries
            self._connection.row_factory = aiosqlite.Row
            self._connected = True
        except Exception as e:
            raise ConnectionError(f"Failed to connect to SQLite database: {e}")

    async def disconnect(self) -> None:
        """Close SQLite connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            self._connected = False

    async def execute(self, sql: str, bindings: Optional[List[Any]] = None) -> Any:
        """Execute a SQL statement.

        Args:
            sql: SQL statement to execute
            bindings: Optional parameter bindings

        Returns:
            Last row ID for INSERT, row count for UPDATE/DELETE
        """
        if not self._connection:
            raise QueryException("Not connected to database")

        try:
            cursor = await self._connection.execute(sql, bindings or [])
            await self._connection.commit()

            # Return last row id for INSERT, row count for UPDATE/DELETE
            if sql.strip().upper().startswith("INSERT"):
                return cursor.lastrowid
            else:
                return cursor.rowcount
        except Exception as e:
            raise QueryException(f"Query execution failed: {e}", sql, bindings)

    async def fetch_all(
        self, sql: str, bindings: Optional[List[Any]] = None
    ) -> List[Dict[str, Any]]:
        """Execute a query and return all results.

        Args:
            sql: SQL SELECT statement
            bindings: Optional parameter bindings

        Returns:
            List of dictionaries representing rows
        """
        if not self._connection:
            raise QueryException("Not connected to database")

        try:
            cursor = await self._connection.execute(sql, bindings or [])
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            raise QueryException(f"Query execution failed: {e}", sql, bindings)

    async def fetch_one(
        self, sql: str, bindings: Optional[List[Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Execute a query and return the first result.

        Args:
            sql: SQL SELECT statement
            bindings: Optional parameter bindings

        Returns:
            Dictionary representing the row, or None if no results
        """
        if not self._connection:
            raise QueryException("Not connected to database")

        try:
            cursor = await self._connection.execute(sql, bindings or [])
            row = await cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            raise QueryException(f"Query execution failed: {e}", sql, bindings)

    def get_grammar(self) -> "Grammar":
        """Get SQLite grammar instance.

        Returns:
            SQLiteGrammar instance
        """
        from pyloquent.grammars.sqlite_grammar import SQLiteGrammar

        return SQLiteGrammar()

    async def begin_transaction(self) -> None:
        """Begin a transaction."""
        if not self._connection:
            raise QueryException("Not connected to database")
        await self._connection.execute("BEGIN")

    async def commit(self) -> None:
        """Commit current transaction."""
        if not self._connection:
            raise QueryException("Not connected to database")
        await self._connection.commit()

    async def rollback(self) -> None:
        """Rollback current transaction."""
        if not self._connection:
            raise QueryException("Not connected to database")
        await self._connection.rollback()
