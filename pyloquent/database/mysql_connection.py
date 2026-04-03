"""MySQL database connection using aiomysql."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from pyloquent.database.connection import Connection
from pyloquent.exceptions import QueryException

if TYPE_CHECKING:
    from pyloquent.grammars.grammar import Grammar


class MySQLConnection(Connection):
    """MySQL database connection implementation.

    Uses aiomysql for async MySQL support.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize MySQL connection.

        Args:
            config: Configuration dictionary with keys:
                - host: Database host
                - port: Database port (default: 3306)
                - database: Database name
                - user: Username
                - password: Password
                - charset: Character set (default: utf8mb4)
                - autocommit: Whether to autocommit (default: False)
                - min_size: Minimum connection pool size (optional)
                - max_size: Maximum connection pool size (optional)
        """
        super().__init__(config)
        self._host = config.get("host", "localhost")
        self._port = config.get("port", 3306)
        self._database = config.get("database", "")
        self._user = config.get("user", "root")
        self._password = config.get("password", "")
        self._charset = config.get("charset", "utf8mb4")
        self._autocommit = config.get("autocommit", False)
        self._min_size = config.get("min_size", 1)
        self._max_size = config.get("max_size", 10)
        self._pool = None

    async def connect(self) -> None:
        """Establish MySQL connection pool.

        Raises:
            ConnectionError: If connection fails
        """
        import aiomysql

        try:
            self._pool = await aiomysql.create_pool(
                host=self._host,
                port=self._port,
                db=self._database,
                user=self._user,
                password=self._password,
                charset=self._charset,
                autocommit=self._autocommit,
                minsize=self._min_size,
                maxsize=self._max_size,
            )
            self._connected = True
        except Exception as e:
            raise ConnectionError(f"Failed to connect to MySQL database: {e}")

    async def disconnect(self) -> None:
        """Close MySQL connection pool."""
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None
            self._connected = False

    def _convert_bindings(self, bindings: Optional[List[Any]]) -> List[Any]:
        """Convert bindings to aiomysql-compatible format.

        Args:
            bindings: List of bindings

        Returns:
            Converted bindings
        """
        if not bindings:
            return []

        converted = []
        for binding in bindings:
            # aiomysql handles most conversions automatically
            converted.append(binding)
        return converted

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
            # Convert ? placeholders to %s for aiomysql
            converted_sql = sql.replace("?", "%s")
            converted_bindings = self._convert_bindings(bindings)

            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(converted_sql, converted_bindings)

                    if not self._autocommit:
                        await conn.commit()

                    # Return last row id for INSERT, row count for UPDATE/DELETE
                    if converted_sql.strip().upper().startswith("INSERT"):
                        return cur.lastrowid
                    else:
                        return cur.rowcount
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
            # Convert ? placeholders to %s for aiomysql
            converted_sql = sql.replace("?", "%s")
            converted_bindings = self._convert_bindings(bindings)

            async with self._pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(converted_sql, converted_bindings)
                    rows = await cur.fetchall()
                    return [dict(row) for row in rows] if rows else []
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
            # Convert ? placeholders to %s for aiomysql
            converted_sql = sql.replace("?", "%s")
            converted_bindings = self._convert_bindings(bindings)

            async with self._pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(converted_sql, converted_bindings)
                    row = await cur.fetchone()
                    return dict(row) if row else None
        except Exception as e:
            raise QueryException(f"Query execution failed: {e}", sql, bindings)

    def get_grammar(self) -> "Grammar":
        """Get MySQL grammar instance.

        Returns:
            MySQLGrammar instance
        """
        from pyloquent.grammars.mysql_grammar import MySQLGrammar

        return MySQLGrammar()

    async def begin_transaction(self) -> None:
        """Begin a transaction."""
        if not self._pool:
            raise QueryException("Not connected to database")

        async with self._pool.acquire() as conn:
            await conn.begin()

    async def commit(self) -> None:
        """Commit current transaction."""
        if not self._pool:
            raise QueryException("Not connected to database")

        async with self._pool.acquire() as conn:
            await conn.commit()

    async def rollback(self) -> None:
        """Rollback current transaction."""
        if not self._pool:
            raise QueryException("Not connected to database")

        async with self._pool.acquire() as conn:
            await conn.rollback()
