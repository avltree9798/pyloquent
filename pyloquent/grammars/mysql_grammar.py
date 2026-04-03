"""MySQL grammar implementation."""

from typing import TYPE_CHECKING, Any, List, Tuple

from pyloquent.grammars.grammar import Grammar

if TYPE_CHECKING:
    from pyloquent.query.builder import QueryBuilder


class MySQLGrammar(Grammar):
    """Grammar for MySQL database."""

    def compile_insert_get_id(
        self, query: "QueryBuilder", values: dict, sequence: str = "id"
    ) -> Tuple[str, List[Any]]:
        """Compile an INSERT query that returns the inserted ID.

        MySQL uses LAST_INSERT_ID() to get the last inserted ID.
        We don't need to modify the SQL - the driver handles this.

        Args:
            query: The query builder instance
            values: Dictionary of column-value pairs
            sequence: Name of the ID sequence column

        Returns:
            Tuple of (SQL string, bindings list)
        """
        sql, bindings = self.compile_insert(query, values)
        return sql, bindings

    def _wrap_value(self, value: str) -> str:
        """Wrap a value with backticks.

        MySQL uses backticks for identifiers.

        Args:
            value: The value to wrap

        Returns:
            Wrapped value with backticks
        """
        return f"`{value}`"

    def _parameter(self, value: Any) -> str:
        """Get the parameter placeholder.

        MySQL uses %s for parameters with aiomysql.

        Args:
            value: The value to parameterize

        Returns:
            Parameter placeholder string
        """
        return "%s"

    def compile_update(self, query: "QueryBuilder", values: dict) -> Tuple[str, List[Any]]:
        """Compile an UPDATE query.

        MySQL supports ORDER BY and LIMIT in UPDATE statements.

        Args:
            query: The query builder instance
            values: Dictionary of column-value pairs

        Returns:
            Tuple of (SQL string, bindings list)
        """
        sql, bindings = super().compile_update(query, values)

        # MySQL supports ORDER BY in UPDATE
        if query._orders:
            sql += " " + self._compile_orders(query)

        # MySQL supports LIMIT in UPDATE
        if query._limit is not None:
            sql += " " + self._compile_limit(query)

        return sql, bindings

    def compile_delete(self, query: "QueryBuilder") -> Tuple[str, List[Any]]:
        """Compile a DELETE query.

        MySQL supports ORDER BY and LIMIT in DELETE statements.

        Args:
            query: The query builder instance

        Returns:
            Tuple of (SQL string, bindings list)
        """
        sql, bindings = super().compile_delete(query)

        # MySQL supports ORDER BY in DELETE
        if query._orders:
            sql += " " + self._compile_orders(query)

        # MySQL supports LIMIT in DELETE
        if query._limit is not None:
            sql += " " + self._compile_limit(query)

        return sql, bindings
