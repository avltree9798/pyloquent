"""Base database connection class."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from pyloquent.grammars.grammar import Grammar


class Connection(ABC):
    """Abstract base class for database connections.

    This class defines the interface that all database connections must implement.
    Concrete implementations handle the specifics of each database driver.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize the connection with configuration.

        Args:
            config: Dictionary containing connection parameters
        """
        self.config = config
        self._grammar: Optional["Grammar"] = None
        self._connected = False

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

    async def begin_transaction(self) -> None:
        """Begin a database transaction.

        Raises:
            QueryException: If transaction fails to start
        """
        await self.execute("BEGIN")

    async def commit(self) -> None:
        """Commit the current transaction.

        Raises:
            QueryException: If commit fails
        """
        await self.execute("COMMIT")

    async def rollback(self) -> None:
        """Rollback the current transaction.

        Raises:
            QueryException: If rollback fails
        """
        await self.execute("ROLLBACK")

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
