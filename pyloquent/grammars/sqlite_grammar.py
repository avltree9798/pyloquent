"""SQLite grammar implementation."""

from typing import TYPE_CHECKING, Any, List, Optional, Tuple

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

    def _compile_auto_increment_column(self, column) -> str:  # noqa: ANN001
        """SQLite's only valid auto-increment form is:

            "id" INTEGER PRIMARY KEY AUTOINCREMENT

        The column **must** be typed exactly `INTEGER` (not BIGINT, not
        UNSIGNED INTEGER) for SQLite to treat it as a ROWID alias. SQLite
        also refuses `NULL` and `DEFAULT` on an AUTOINCREMENT column, so
        this method emits a fixed-form clause regardless of what `unsigned`
        / `nullable` / `default` were set to.
        """
        return f"{self._wrap_column(column.name)} INTEGER PRIMARY KEY AUTOINCREMENT"

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

    # ========================================================================
    # Schema Alteration
    # ========================================================================
    #
    # SQLite's ALTER TABLE is deliberately minimal. It supports ADD COLUMN,
    # RENAME COLUMN (3.25+) and DROP COLUMN (3.35+) — all handled by the base
    # grammar — but cannot drop/modify constraints or rename indexes without a
    # full table rebuild. Those operations raise a clear error.

    def _compile_drop_primary(self, table: str, name: Optional[str] = None) -> str:
        """SQLite cannot drop a primary key via ALTER TABLE."""
        raise NotImplementedError(
            "SQLite cannot drop a primary key via ALTER TABLE. "
            "Recreate the table (create new → copy rows → drop old → rename)."
        )

    def _compile_drop_foreign(self, table: str, name: str) -> str:
        """SQLite cannot drop a foreign key via ALTER TABLE."""
        raise NotImplementedError(
            "SQLite cannot drop a foreign key via ALTER TABLE. "
            "Recreate the table (create new → copy rows → drop old → rename)."
        )

    def _compile_rename_index(self, table: str, from_name: str, to_name: str) -> str:
        """SQLite has no ALTER INDEX ... RENAME."""
        raise NotImplementedError(
            "SQLite cannot rename an index. Drop and recreate it instead."
        )

    # ========================================================================
    # Schema Reflection
    # ========================================================================

    def compile_table_exists(self, table: str) -> Tuple[str, List[Any]]:
        """Check if a table exists in the SQLite database.

        Args:
            table: Table name

        Returns:
            Tuple of (SQL, bindings)
        """
        return (
            "SELECT COUNT(*) AS \"exists\" FROM sqlite_master WHERE type='table' AND name=?",
            [table],
        )

    def compile_column_exists(self, table: str, column: str) -> Tuple[str, List[Any]]:
        """Check if a column exists in a SQLite table using PRAGMA.

        Args:
            table: Table name
            column: Column name

        Returns:
            Tuple of (SQL, bindings)
        """
        return (
            f"SELECT COUNT(*) AS \"exists\" FROM pragma_table_info(?) WHERE name=?",
            [table, column],
        )

    def compile_index_exists(
        self, table: str, columns: List[str], index_type: Optional[str] = None
    ) -> Tuple[str, List[Any]]:
        """Check if an index exists on a SQLite table.

        Args:
            table: Table name
            columns: Index columns
            index_type: Type of index (unused for SQLite)

        Returns:
            Tuple of (SQL, bindings)
        """
        return (
            "SELECT COUNT(*) AS \"exists\" FROM sqlite_master "
            "WHERE type='index' AND tbl_name=?",
            [table],
        )

    def compile_get_tables(self) -> str:
        """Get all user-defined tables in the SQLite database.

        Returns:
            SQL statement
        """
        return (
            "SELECT name, 'table' AS type FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )

    def compile_get_columns(self, table: str) -> Tuple[str, List[Any]]:
        """Get column information for a SQLite table via PRAGMA.

        Args:
            table: Table name

        Returns:
            Tuple of (SQL, bindings)
        """
        return "SELECT cid, name, type, \"notnull\", dflt_value, pk FROM pragma_table_info(?)", [table]

    def compile_get_indexes(self, table: str) -> Tuple[str, List[Any]]:
        """Get index information for a SQLite table via PRAGMA.

        Args:
            table: Table name

        Returns:
            Tuple of (SQL, bindings)
        """
        return "SELECT name, \"unique\", origin, partial FROM pragma_index_list(?)", [table]

    def compile_get_foreign_keys(self, table: str) -> Tuple[str, List[Any]]:
        """Get foreign key information for a SQLite table via PRAGMA.

        Args:
            table: Table name

        Returns:
            Tuple of (SQL, bindings)
        """
        return (
            "SELECT id, seq, \"table\", \"from\", \"to\", on_update, on_delete "
            "FROM pragma_foreign_key_list(?)",
            [table],
        )
