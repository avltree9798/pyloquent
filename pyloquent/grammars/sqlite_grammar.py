"""SQLite grammar implementation."""

from typing import TYPE_CHECKING, Any, List, Tuple

from pyloquent.grammars.grammar import Grammar

if TYPE_CHECKING:  # pragma: no cover
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
            value: The value to parameterise

        Returns:
            Parameter placeholder string
        """
        return "?"

    def _compile_lock(self, query: "QueryBuilder") -> str:
        """SQLite does not support row locking — return empty string."""
        return ""

    def compile_upsert(
        self,
        query: "QueryBuilder",
        values: List[dict],
        unique_by: List[str],
        update_columns: List[str],
    ) -> Tuple[str, List[Any]]:
        """SQLite upsert using INSERT OR REPLACE ... ON CONFLICT DO UPDATE.

        SQLite 3.24+ supports the standard ON CONFLICT syntax.
        """
        from pyloquent.grammars.grammar import Grammar
        return Grammar.compile_upsert(self, query, values, unique_by, update_columns)

    def compile_insert_or_ignore(
        self, query: "QueryBuilder", values: List[dict]
    ) -> Tuple[str, List[Any]]:
        """SQLite uses INSERT OR IGNORE INTO syntax."""
        sql, bindings = self.compile_insert(query, values)
        sql = sql.replace("INSERT INTO", "INSERT OR IGNORE INTO", 1)
        return sql, bindings
