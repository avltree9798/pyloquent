"""MySQL grammar implementation."""

from typing import TYPE_CHECKING, Any, List, Optional, Tuple

from pyloquent.grammars.grammar import Grammar

if TYPE_CHECKING:  # pragma: no cover
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
            value: The value to parameterise

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

    # ========================================================================
    # Schema Reflection
    # ========================================================================

    def compile_table_exists(self, table: str) -> Tuple[str, List[Any]]:
        """Check if a table exists in MySQL.

        Args:
            table: Table name

        Returns:
            Tuple of (SQL, bindings)
        """
        return (
            "SELECT COUNT(*) AS `exists` FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = %s",
            [table],
        )

    def compile_column_exists(self, table: str, column: str) -> Tuple[str, List[Any]]:
        """Check if a column exists in a MySQL table.

        Args:
            table: Table name
            column: Column name

        Returns:
            Tuple of (SQL, bindings)
        """
        return (
            "SELECT COUNT(*) AS `exists` FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s",
            [table, column],
        )

    def compile_index_exists(
        self, table: str, columns: List[str], index_type: Optional[str] = None
    ) -> Tuple[str, List[Any]]:
        """Check if an index exists on a MySQL table.

        Args:
            table: Table name
            columns: Index columns
            index_type: Type of index

        Returns:
            Tuple of (SQL, bindings)
        """
        return (
            "SELECT COUNT(*) AS `exists` FROM information_schema.statistics "
            "WHERE table_schema = DATABASE() AND table_name = %s",
            [table],
        )

    def compile_get_tables(self) -> str:
        """Get all user-defined tables in the MySQL database.

        Returns:
            SQL statement
        """
        return (
            "SELECT table_name AS name, table_type AS type "
            "FROM information_schema.tables WHERE table_schema = DATABASE() ORDER BY table_name"
        )

    def compile_get_columns(self, table: str) -> Tuple[str, List[Any]]:
        """Get column information for a MySQL table.

        Args:
            table: Table name

        Returns:
            Tuple of (SQL, bindings)
        """
        return (
            "SELECT column_name AS name, data_type AS type, is_nullable, "
            "column_default AS dflt_value, ordinal_position AS cid "
            "FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = %s ORDER BY ordinal_position",
            [table],
        )

    def compile_get_indexes(self, table: str) -> Tuple[str, List[Any]]:
        """Get index information for a MySQL table.

        Args:
            table: Table name

        Returns:
            Tuple of (SQL, bindings)
        """
        return (
            "SELECT index_name AS name, non_unique FROM information_schema.statistics "
            "WHERE table_schema = DATABASE() AND table_name = %s GROUP BY index_name, non_unique",
            [table],
        )

    def compile_get_foreign_keys(self, table: str) -> Tuple[str, List[Any]]:
        """Get foreign key information for a MySQL table.

        Args:
            table: Table name

        Returns:
            Tuple of (SQL, bindings)
        """
        return (
            "SELECT kcu.column_name AS `from`, kcu.referenced_table_name AS `table`, "
            "kcu.referenced_column_name AS `to`, rc.update_rule AS on_update, rc.delete_rule AS on_delete "
            "FROM information_schema.key_column_usage kcu "
            "JOIN information_schema.referential_constraints rc "
            "  ON rc.constraint_name = kcu.constraint_name "
            "WHERE kcu.table_schema = DATABASE() AND kcu.table_name = %s "
            "AND kcu.referenced_table_name IS NOT NULL",
            [table],
        )
