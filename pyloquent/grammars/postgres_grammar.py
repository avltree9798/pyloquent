"""PostgreSQL grammar implementation."""

from typing import TYPE_CHECKING, Any, List, Tuple

from pyloquent.grammars.grammar import Grammar

if TYPE_CHECKING:
    from pyloquent.query.builder import QueryBuilder


class PostgresGrammar(Grammar):
    """Grammar for PostgreSQL database."""

    def compile_insert_get_id(
        self, query: "QueryBuilder", values: dict, sequence: str = "id"
    ) -> Tuple[str, List[Any]]:
        """Compile an INSERT query that returns the inserted ID.

        PostgreSQL uses RETURNING clause to get the inserted ID.

        Args:
            query: The query builder instance
            values: Dictionary of column-value pairs
            sequence: Name of the ID sequence column

        Returns:
            Tuple of (SQL string, bindings list)
        """
        sql, bindings = self.compile_insert(query, values)
        returning = self._wrap_column(sequence)
        sql = f"{sql} RETURNING {returning}"
        return sql, bindings

    def _compile_columns(self, query: "QueryBuilder") -> str:
        """Compile the SELECT columns clause.

        PostgreSQL supports DISTINCT ON.

        Args:
            query: The query builder instance

        Returns:
            SQL columns clause
        """
        if hasattr(query, "_distinct_on") and query._distinct_on:
            distinct_columns = ", ".join(self._wrap_column(col) for col in query._distinct_on)
            select = f"SELECT DISTINCT ON ({distinct_columns})"
        elif query._distinct:
            select = "SELECT DISTINCT"
        else:
            select = "SELECT"

        if not query._selects:
            return f"{select} *"

        columns = []
        for column in query._selects:
            if isinstance(column, dict):
                # Handle aliased columns: {'column': 'alias'}
                for col, alias in column.items():
                    columns.append(f"{self._wrap_column(col)} AS {self._wrap_column(alias)}")
            else:
                columns.append(self._wrap_column(column))

        return f"{select} {', '.join(columns)}"

    def _compile_update(self, query: "QueryBuilder", values: dict) -> Tuple[str, List[Any]]:
        """Compile an UPDATE query.

        Args:
            query: The query builder instance
            values: Dictionary of column-value pairs

        Returns:
            Tuple of (SQL string, bindings list)
        """
        return super().compile_update(query, values)

    def _wrap_value(self, value: str) -> str:
        """Wrap a value with double quotes.

        Args:
            value: The value to wrap

        Returns:
            Wrapped value with double quotes
        """
        return f'"{value}"'

    def _parameter(self, value: Any) -> str:
        """Get the parameter placeholder.

        PostgreSQL uses $1, $2, etc. for parameters.
        For simplicity, we use positional parameters and let asyncpg handle it.

        Args:
            value: The value to parameterize

        Returns:
            Parameter placeholder string
        """
        # asyncpg handles the conversion of ? to $1, $2, etc.
        return "?"

    def supports_returning(self) -> bool:
        """Check if this grammar supports RETURNING clause.

        Returns:
            True if RETURNING is supported
        """
        return True

    def supports_ilike(self) -> bool:
        """Check if this grammar supports ILIKE operator.

        Returns:
            True if ILIKE is supported
        """
        return True
