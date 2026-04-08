"""PostgreSQL grammar implementation."""

from typing import TYPE_CHECKING, Any, List, Optional, Tuple

from pyloquent.grammars.grammar import Grammar

if TYPE_CHECKING:  # pragma: no cover
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
            value: The value to parameterise

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

    # ========================================================================
    # Schema Reflection
    # ========================================================================

    def compile_table_exists(self, table: str) -> Tuple[str, List[Any]]:
        """Check if a table exists in PostgreSQL.

        Args:
            table: Table name

        Returns:
            Tuple of (SQL, bindings)
        """
        return (
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_name = $1) AS \"exists\"",
            [table],
        )

    def compile_column_exists(self, table: str, column: str) -> Tuple[str, List[Any]]:
        """Check if a column exists in a PostgreSQL table.

        Args:
            table: Table name
            column: Column name

        Returns:
            Tuple of (SQL, bindings)
        """
        return (
            "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = $1 AND column_name = $2) AS \"exists\"",
            [table, column],
        )

    def compile_index_exists(
        self, table: str, columns: List[str], index_type: Optional[str] = None
    ) -> Tuple[str, List[Any]]:
        """Check if an index exists on a PostgreSQL table.

        Args:
            table: Table name
            columns: Index columns
            index_type: Type of index

        Returns:
            Tuple of (SQL, bindings)
        """
        return (
            "SELECT EXISTS(SELECT 1 FROM pg_indexes "
            "WHERE tablename = $1) AS \"exists\"",
            [table],
        )

    def compile_get_tables(self) -> str:
        """Get all user-defined tables in the PostgreSQL database.

        Returns:
            SQL statement
        """
        return (
            "SELECT table_name AS name, table_type AS type "
            "FROM information_schema.tables "
            "WHERE table_schema = current_schema() ORDER BY table_name"
        )

    def compile_get_columns(self, table: str) -> Tuple[str, List[Any]]:
        """Get column information for a PostgreSQL table.

        Args:
            table: Table name

        Returns:
            Tuple of (SQL, bindings)
        """
        return (
            "SELECT column_name AS name, data_type AS type, "
            "is_nullable, column_default AS dflt_value, ordinal_position AS cid "
            "FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = $1 ORDER BY ordinal_position",
            [table],
        )

    def compile_get_indexes(self, table: str) -> Tuple[str, List[Any]]:
        """Get index information for a PostgreSQL table.

        Args:
            table: Table name

        Returns:
            Tuple of (SQL, bindings)
        """
        return (
            "SELECT indexname AS name, indexdef FROM pg_indexes WHERE tablename = $1",
            [table],
        )

    def compile_get_foreign_keys(self, table: str) -> Tuple[str, List[Any]]:
        """Get foreign key information for a PostgreSQL table.

        Args:
            table: Table name

        Returns:
            Tuple of (SQL, bindings)
        """
        return (
            "SELECT kcu.column_name AS \"from\", ccu.table_name AS \"table\", "
            "ccu.column_name AS \"to\", rc.update_rule AS on_update, rc.delete_rule AS on_delete "
            "FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "  ON tc.constraint_name = kcu.constraint_name "
            "JOIN information_schema.constraint_column_usage ccu "
            "  ON ccu.constraint_name = tc.constraint_name "
            "JOIN information_schema.referential_constraints rc "
            "  ON rc.constraint_name = tc.constraint_name "
            "WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name = $1",
            [table],
        )
