"""D1 database connection for Pyloquent ORM."""

from typing import Any, Dict, List, Optional

from pyloquent.database.connection import Connection
from pyloquent.d1.http_client import D1HttpClient
from pyloquent.exceptions import QueryException
from pyloquent.grammars.grammar import Grammar
from pyloquent.grammars.sqlite_grammar import SQLiteGrammar


class D1Connection(Connection):
    """Cloudflare D1 database connection.

    This connection class supports both:
    1. HTTP API access (for external applications)
    2. Worker bindings (for Cloudflare Workers)

    Example (HTTP API):
        config = {
            'driver': 'd1',
            'api_token': 'your-api-token',
            'account_id': 'your-account-id',
            'database_id': 'your-database-id',
        }
        conn = D1Connection(config)
        await conn.connect()

    Example (Worker Binding):
        config = {
            'driver': 'd1',
            'binding': env.DB,  # D1 binding from Worker environment
        }
        conn = D1Connection(config)
        await conn.connect()
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize the D1 connection.

        Args:
            config: Connection configuration
        """
        super().__init__(config)
        self._http_client: Optional[D1HttpClient] = None
        self._binding: Optional[Any] = None
        self._grammar: Optional[Grammar] = None

    def get_grammar(self) -> Grammar:
        """Get the SQL grammar for this connection.

        D1 uses SQLite syntax, so we use SQLiteGrammar.

        Returns:
            Grammar instance
        """
        if self._grammar is None:
            self._grammar = SQLiteGrammar()
        return self._grammar

    @property
    def grammar(self) -> Grammar:
        """Get the grammar property."""
        return self.get_grammar()

    async def connect(self) -> None:
        """Connect to the D1 database.

        For HTTP API: Creates the HTTP client
        For Worker Binding: Validates the binding
        """
        if "binding" in self.config:
            # Using Worker binding
            self._binding = self.config["binding"]
        else:
            # Using HTTP API
            required_keys = ["api_token", "account_id", "database_id"]
            missing = [k for k in required_keys if k not in self.config]

            if missing:
                raise QueryException(f"D1 HTTP connection missing required config: {missing}")

            self._http_client = D1HttpClient(
                account_id=self.config["account_id"],
                database_id=self.config["database_id"],
                api_token=self.config["api_token"],
                base_url=self.config.get("base_url"),
            )

    async def disconnect(self) -> None:
        """Disconnect from the database.

        For D1, this is a no-op as connections are stateless.
        """
        self._http_client = None
        self._binding = None

    async def execute(self, sql: str, bindings: Optional[List[Any]] = None) -> Any:
        """Execute a SQL statement.

        Args:
            sql: SQL statement
            bindings: Parameter bindings

        Returns:
            Execution result
        """
        if self._binding:
            # Use Worker binding
            return await self._execute_binding(sql, bindings)
        elif self._http_client:
            # Use HTTP API
            result = await self._http_client.execute(sql, bindings)
            return result.get("meta", {}).get("changes", 0)
        else:
            raise QueryException("D1 connection not established")

    async def _execute_binding(self, sql: str, bindings: Optional[List[Any]] = None) -> Any:
        """Execute using Worker binding.

        Args:
            sql: SQL statement
            bindings: Parameter bindings

        Returns:
            Execution result
        """
        try:
            # D1 binding accepts prepared statements
            if bindings:
                stmt = self._binding.prepare(sql)
                result = await stmt.bind(*bindings).all()
            else:
                result = await self._binding.exec(sql)

            # Return affected rows or last inserted ID
            if hasattr(result, "meta"):
                return result.meta.get("changes", 0)
            return 0
        except Exception as e:
            raise QueryException(f"D1 binding execution failed: {e}")

    async def fetch_all(
        self, sql: str, bindings: Optional[List[Any]] = None
    ) -> List[Dict[str, Any]]:
        """Fetch all results from a query.

        Args:
            sql: SQL query
            bindings: Parameter bindings

        Returns:
            List of result rows
        """
        if self._binding:
            # Use Worker binding
            return await self._fetch_all_binding(sql, bindings)
        elif self._http_client:
            # Use HTTP API
            return await self._http_client.query(sql, bindings)
        else:
            raise QueryException("D1 connection not established")

    async def _fetch_all_binding(
        self, sql: str, bindings: Optional[List[Any]] = None
    ) -> List[Dict[str, Any]]:
        """Fetch all using Worker binding.

        Args:
            sql: SQL query
            bindings: Parameter bindings

        Returns:
            List of result rows
        """
        try:
            if bindings:
                stmt = self._binding.prepare(sql)
                result = await stmt.bind(*bindings).all()
            else:
                result = await self._binding.exec(sql)

            return result.results if hasattr(result, "results") else []
        except Exception as e:
            raise QueryException(f"D1 binding query failed: {e}")

    async def fetch_one(
        self, sql: str, bindings: Optional[List[Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Fetch a single result from a query.

        Args:
            sql: SQL query
            bindings: Parameter bindings

        Returns:
            Single result row or None
        """
        results = await self.fetch_all(sql, bindings)
        return results[0] if results else None

    async def begin_transaction(self) -> None:
        """Begin a transaction.

        Note: D1 supports transactions via SQL statements.
        """
        await self.execute("BEGIN TRANSACTION")

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self.execute("COMMIT")

    async def rollback(self) -> None:
        """Rollback the current transaction."""
        await self.execute("ROLLBACK")

    async def transaction(self, callback: callable):
        """Execute a callback within a transaction.

        Args:
            callback: Async function to execute

        Returns:
            Callback result
        """
        await self.begin_transaction()
        try:
            result = await callback()
            await self.commit()
            return result
        except Exception:
            await self.rollback()
            raise
