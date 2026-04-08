"""SQLite database connection using aiosqlite."""

import sqlite3
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from pyloquent.database.connection import Connection
from pyloquent.exceptions import QueryException

# Register explicit datetime adapters/converters to avoid the Python 3.12
# deprecation of the built-in default datetime adapter.
sqlite3.register_adapter(datetime, lambda d: d.isoformat())
sqlite3.register_adapter(date, lambda d: d.isoformat())
sqlite3.register_converter("TIMESTAMP", lambda b: datetime.fromisoformat(b.decode()) if b else None)
sqlite3.register_converter("DATETIME", lambda b: datetime.fromisoformat(b.decode()) if b else None)
sqlite3.register_converter("DATE", lambda b: date.fromisoformat(b.decode()) if b else None)

if TYPE_CHECKING:  # pragma: no cover
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
                - timeout: Connection timeout in seconds (default: 5.0)
                - isolation_level: Transaction isolation level (default: None / autocommit)
                - journal_mode: SQLite journal mode — 'wal' recommended for concurrency
                - foreign_keys: Enable FK enforcement (default: True)
        """
        super().__init__(config)
        self._db_path = config.get("database", ":memory:")
        self._timeout = config.get("timeout", 5.0)
        self._isolation_level = config.get("isolation_level", None)
        self._journal_mode = config.get("journal_mode", None)
        self._foreign_keys = config.get("foreign_keys", True)
        self._connection = None
        self._in_transaction = False

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
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            )
            # Return rows as dictionaries
            self._connection.row_factory = aiosqlite.Row
            # Foreign key enforcement
            fk_val = "ON" if self._foreign_keys else "OFF"
            await self._connection.execute(f"PRAGMA foreign_keys = {fk_val}")
            # Journal mode (WAL is recommended for concurrent reads)
            if self._journal_mode:
                await self._connection.execute(f"PRAGMA journal_mode = {self._journal_mode.upper()}")
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
            if not self._in_transaction:
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

    async def execute_many(self, sql: str, rows: List[List[Any]]) -> int:
        """Execute a parameterised statement for multiple rows using aiosqlite executemany.

        This is significantly faster than individual execute() calls for bulk inserts.

        Args:
            sql: SQL statement with ? placeholders
            rows: List of binding lists, one per row

        Returns:
            Total number of rows affected
        """
        if not self._connection:
            from pyloquent.exceptions import QueryException
            raise QueryException("Not connected to database")

        try:
            await self._connection.executemany(sql, rows)
            if not self._in_transaction:
                await self._connection.commit()
            return len(rows)
        except Exception as e:
            from pyloquent.exceptions import QueryException
            raise QueryException(f"Batch insert failed: {e}", sql)

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
        self._in_transaction = True

    async def commit(self) -> None:
        """Commit current transaction."""
        if not self._connection:
            raise QueryException("Not connected to database")
        await self._connection.commit()
        self._in_transaction = False

    async def rollback(self) -> None:
        """Rollback current transaction."""
        if not self._connection:
            raise QueryException("Not connected to database")
        await self._connection.rollback()
        self._in_transaction = False
