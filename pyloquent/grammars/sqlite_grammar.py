"""SQLite grammar implementation."""

from typing import TYPE_CHECKING, Any, List, Tuple

from pyloquent.grammars.grammar import Grammar

if TYPE_CHECKING:
    from pyloquent.query.builder import QueryBuilder


class SQLiteGrammar(Grammar):
    """Grammar for SQLite database."""

    def compile_insert_get_id(
        self, query: "QueryBuilder", values: dict, sequence: str = "id"
    ) -> Tuple[str, List[Any]]:
        """Compile an INSERT query that returns the inserted ID.

        SQLite uses last_insert_rowid() to get the last inserted ID.

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
        """Wrap a value with double quotes.

        Args:
            value: The value to wrap

        Returns:
            Wrapped value with double quotes
        """
        return f'"{value}"'

    def _parameter(self, value: Any) -> str:
        """Get the parameter placeholder.

        SQLite uses ? for parameters.

        Args:
            value: The value to parameterize

        Returns:
            Parameter placeholder string
        """
        return "?"
