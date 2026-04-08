"""PostgreSQL database connection using asyncpg."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from pyloquent.database.connection import Connection
from pyloquent.exceptions import QueryException

if TYPE_CHECKING:
    from pyloquent.grammars.grammar import Grammar


class PostgresConnection(Connection):
    """PostgreSQL database connection implementation.

    Uses asyncpg for async PostgreSQL support.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize PostgreSQL connection.

        Args:
            config: Configuration dictionary with keys:
                - host: Database host
                - port: Database port (default: 5432)
                - database: Database name
                - user: Username
                - password: Password
                - ssl: SSL mode (optional)
                - min_size: Minimum connection pool size (optional)
                - max_size: Maximum connection pool size (optional)
        """
        super().__init__(config)
        self._host = config.get("host", "localhost")
        self._port = config.get("port", 5432)
        self._database = config.get("database", "postgres")
        self._user = config.get("user", "postgres")
        self._password = config.get("password", "")
        self._ssl = config.get("ssl")
        self._min_size = config.get("min_size", 1)
        self._max_size = config.get("max_size", 10)
        self._pool = None

    async def connect(self) -> None:
        """Establish PostgreSQL connection pool.

        Raises:
            ConnectionError: If connection fails
        """
        import asyncpg

        try:
            pool_kwargs: Dict[str, Any] = dict(
                host=self._host,
                port=self._port,
                database=self._database,
                user=self._user,
                password=self._password,
                ssl=self._ssl,
                min_size=self._min_size,
                max_size=self._max_size,
            )
            if self._pool_recycle is not None:
                # asyncpg recycles idle connections after this many seconds
                pool_kwargs["max_inactive_connection_lifetime"] = float(self._pool_recycle)
            self._pool = await asyncpg.create_pool(**pool_kwargs)
            self._connected = True
            self._connected_at = __import__("time").monotonic()
        except Exception as e:
            raise ConnectionError(f"Failed to connect to PostgreSQL database: {e}")

    async def disconnect(self) -> None:
        """Close PostgreSQL connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._connected = False

    def _convert_bindings(self, bindings: Optional[List[Any]]) -> List[Any]:
        """Convert bindings to asyncpg-compatible format.

        Args:
            bindings: List of bindings

        Returns:
            Converted bindings
        """
        if not bindings:
            return []

        converted = []
        for binding in bindings:
            # asyncpg handles most conversions automatically
            converted.append(binding)
        return converted

    async def ping(self) -> bool:
        """Acquire a pool connection and issue ``SELECT 1``."""
        if not self._pool:
            return False
        try:
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception:
            return False

    async def execute(self, sql: str, bindings: Optional[List[Any]] = None) -> Any:
        """Execute a SQL statement.

        Args:
            sql: SQL statement to execute
            bindings: Optional parameter bindings

        Returns:
            Last row ID for INSERT, row count for UPDATE/DELETE
        """
        if not self._pool:
            raise QueryException("Not connected to database")

        try:
            # Convert ? placeholders to $1, $2, etc.
            converted_sql = self._convert_placeholders(sql)
            converted_bindings = self._convert_bindings(bindings)

            async with self._pool.acquire() as conn:
                if converted_sql.strip().upper().startswith("INSERT") and "RETURNING" in converted_sql.upper():
                    # Handle INSERT ... RETURNING
                    row = await conn.fetchrow(converted_sql, *converted_bindings)
                    return row[0] if row else None
                else:
                    result = await conn.execute(converted_sql, *converted_bindings)
                    # Parse result like "INSERT 0 1" or "UPDATE 3"
                    parts = result.split()
                    if parts[0] == "INSERT":
                        return int(parts[-1]) if len(parts) > 2 else None
                    elif parts[0] in ("UPDATE", "DELETE"):
                        return int(parts[-1])
                    return result
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
        if not self._pool:
            raise QueryException("Not connected to database")

        try:
            converted_sql = self._convert_placeholders(sql)
            converted_bindings = self._convert_bindings(bindings)

            async with self._pool.acquire() as conn:
                rows = await conn.fetch(converted_sql, *converted_bindings)
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
        if not self._pool:
            raise QueryException("Not connected to database")

        try:
            converted_sql = self._convert_placeholders(sql)
            converted_bindings = self._convert_bindings(bindings)

            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(converted_sql, *converted_bindings)
                return dict(row) if row else None
        except Exception as e:
            raise QueryException(f"Query execution failed: {e}", sql, bindings)

    def _convert_placeholders(self, sql: str) -> str:
        """Convert ? placeholders to $1, $2, etc. for asyncpg.

        Args:
            sql: SQL with ? placeholders

        Returns:
            SQL with $N placeholders
        """
        import re

        counter = [0]

        def replace(match):
            counter[0] += 1
            return f"${counter[0]}"

        return re.sub(r"\?", replace, sql)

    def get_grammar(self) -> "Grammar":
        """Get PostgreSQL grammar instance.

        Returns:
            PostgresGrammar instance
        """
        from pyloquent.grammars.postgres_grammar import PostgresGrammar

        return PostgresGrammar()

    async def begin_transaction(self) -> None:
        """Begin a transaction."""
        # Transactions are handled automatically by asyncpg
        pass

    async def commit(self) -> None:
        """Commit current transaction."""
        # Transactions are handled automatically by asyncpg
        pass

    async def rollback(self) -> None:
        """Rollback current transaction."""
        # Transactions are handled automatically by asyncpg
        pass
