"""Base grammar class for SQL compilation."""

from abc import ABC
from typing import TYPE_CHECKING, Any, List, Optional, Tuple

if TYPE_CHECKING:
    from pyloquent.query.builder import QueryBuilder


class Grammar(ABC):
    """Base class for SQL grammar implementations.

    This class handles the compilation of query builder state into
    SQL strings and parameter bindings.
    """

    # Operators that can be used in WHERE clauses
    OPERATORS = [
        "=",
        "<",
        ">",
        "<=",
        ">=",
        "<>",
        "!=",
        "like",
        "not like",
        "ilike",
        "not ilike",
        "in",
        "not in",
        "between",
        "not between",
        "is null",
        "is not null",
    ]

    # Components in the order they should be compiled
    SELECT_COMPONENTS = [
        "aggregate",
        "columns",
        "from",
        "joins",
        "wheres",
        "groups",
        "havings",
        "orders",
        "limit",
        "offset",
    ]

    def __init__(self):
        """Initialize the grammar."""
        self._table_prefix = ""

    def compile_select(self, query: "QueryBuilder") -> Tuple[str, List[Any]]:
        """Compile a SELECT query.

        Args:
            query: The query builder instance

        Returns:
            Tuple of (SQL string, bindings list)
        """
        if query._aggregate_data:
            return self._compile_aggregate(query)

        sql_parts = []
        bindings = []

        # SELECT columns
        columns = self._compile_columns(query)
        if columns:
            sql_parts.append(columns)

        # FROM table
        from_clause = self._compile_from(query)
        sql_parts.append(from_clause)
        bindings.extend(query._bindings.get("from", []))

        # JOINs
        if query._joins:
            joins_sql, joins_bindings = self._compile_joins(query)
            sql_parts.append(joins_sql)
            bindings.extend(joins_bindings)

        # WHEREs
        if query._wheres:
            wheres_sql, wheres_bindings = self._compile_wheres(query)
            sql_parts.append(wheres_sql)
            bindings.extend(wheres_bindings)

        # GROUP BY
        if query._groups:
            sql_parts.append(self._compile_groups(query))

        # HAVINGs
        if query._havings:
            havings_sql, havings_bindings = self._compile_havings(query)
            sql_parts.append(havings_sql)
            bindings.extend(havings_bindings)

        # ORDER BY
        if query._orders:
            sql_parts.append(self._compile_orders(query))

        # LIMIT
        if query._limit is not None:
            sql_parts.append(self._compile_limit(query))

        # OFFSET
        if query._offset is not None:
            sql_parts.append(self._compile_offset(query))

        return " ".join(sql_parts), bindings

    def compile_insert(self, query: "QueryBuilder", values: dict | list) -> Tuple[str, List[Any]]:
        """Compile an INSERT query.

        Args:
            query: The query builder instance
            values: Dictionary or list of dictionaries of column-value pairs

        Returns:
            Tuple of (SQL string, bindings list)
        """
        if isinstance(values, dict):
            values = [values]

        if not values:
            raise ValueError("Cannot insert empty values")

        table = self._wrap_table(query._table)
        columns = list(values[0].keys())

        # Compile columns
        columns_sql = ", ".join(self._wrap_column(col) for col in columns)

        # Compile values placeholders
        rows = []
        bindings = []
        for row in values:
            placeholders = []
            for col in columns:
                placeholders.append(self._parameter(row[col]))
                bindings.append(row[col])
            rows.append(f"({', '.join(placeholders)})")

        values_sql = ", ".join(rows)

        sql = f"INSERT INTO {table} ({columns_sql}) VALUES {values_sql}"

        return sql, bindings

    def compile_insert_get_id(
        self, query: "QueryBuilder", values: dict, sequence: str = "id"
    ) -> Tuple[str, List[Any]]:
        """Compile an INSERT query that returns the inserted ID.

        Args:
            query: The query builder instance
            values: Dictionary of column-value pairs
            sequence: Name of the ID sequence column

        Returns:
            Tuple of (SQL string, bindings list)
        """
        sql, bindings = self.compile_insert(query, values)
        return sql, bindings

    def compile_update(self, query: "QueryBuilder", values: dict) -> Tuple[str, List[Any]]:
        """Compile an UPDATE query.

        Args:
            query: The query builder instance
            values: Dictionary of column-value pairs

        Returns:
            Tuple of (SQL string, bindings list)
        """
        table = self._wrap_table(query._table)

        # Compile SET clauses
        sets = []
        bindings = []
        for column, value in values.items():
            sets.append(f"{self._wrap_column(column)} = {self._parameter(value)}")
            bindings.append(value)

        sets_sql = ", ".join(sets)

        sql_parts = [f"UPDATE {table} SET {sets_sql}"]

        # WHEREs
        if query._wheres:
            wheres_sql, wheres_bindings = self._compile_wheres(query)
            sql_parts.append(wheres_sql)
            bindings.extend(wheres_bindings)

        return " ".join(sql_parts), bindings

    def compile_delete(self, query: "QueryBuilder") -> Tuple[str, List[Any]]:
        """Compile a DELETE query.

        Args:
            query: The query builder instance

        Returns:
            Tuple of (SQL string, bindings list)
        """
        table = self._wrap_table(query._table)

        sql_parts = [f"DELETE FROM {table}"]
        bindings = []

        # WHEREs
        if query._wheres:
            wheres_sql, wheres_bindings = self._compile_wheres(query)
            sql_parts.append(wheres_sql)
            bindings.extend(wheres_bindings)

        return " ".join(sql_parts), bindings

    def _compile_columns(self, query: "QueryBuilder") -> str:
        """Compile the SELECT columns clause.

        Args:
            query: The query builder instance

        Returns:
            SQL columns clause
        """
        if query._distinct:
            select = "SELECT DISTINCT"
        else:
            select = "SELECT"

        if not query._selects:
            return f"{select} *"

        from pyloquent.query.expression import RawExpression

        columns = []
        for column in query._selects:
            if isinstance(column, RawExpression):
                columns.append(column.sql)
            elif isinstance(column, dict):
                # Handle aliased columns: {'column': 'alias'}
                for col, alias in column.items():
                    columns.append(f"{self._wrap_column(col)} AS {self._wrap_column(alias)}")
            else:
                columns.append(self._wrap_column(column))

        return f"{select} {', '.join(columns)}"

    def _compile_from(self, query: "QueryBuilder") -> str:
        """Compile the FROM clause.

        Args:
            query: The query builder instance

        Returns:
            SQL FROM clause
        """
        return f"FROM {self._wrap_table(query._table)}"

    def _compile_joins(self, query: "QueryBuilder") -> Tuple[str, List[Any]]:
        """Compile the JOIN clauses.

        Args:
            query: The query builder instance

        Returns:
            Tuple of (SQL joins clause, bindings list)
        """
        sql_parts = []
        bindings = []

        for join in query._joins:
            join_type = join.type.upper()
            table = self._wrap_table(join.table)

            conditions = []
            for condition in join.conditions:
                first = self._wrap_column(condition.first)
                second = self._wrap_column(condition.second)
                operator = condition.operator
                conditions.append(f"{first} {operator} {second}")

            conditions_sql = " AND ".join(conditions)
            sql_parts.append(f"{join_type} JOIN {table} ON {conditions_sql}")

        return " ".join(sql_parts), bindings

    def _compile_wheres(self, query: "QueryBuilder") -> Tuple[str, List[Any]]:
        """Compile the WHERE clauses.

        Args:
            query: The query builder instance

        Returns:
            Tuple of (SQL WHERE clause, bindings list)
        """
        if not query._wheres:
            return "", []

        sql_parts = []
        bindings = []

        for i, where in enumerate(query._wheres):
            # Determine boolean connector (AND/OR)
            boolean = "AND" if where.boolean == "and" else "OR"

            # First clause doesn't need a boolean connector
            prefix = f" {boolean} " if i > 0 else ""

            if where.type == "nested":
                # Handle nested where groups
                nested_sql, nested_bindings = self._compile_nested_where(where)
                sql_parts.append(f"{prefix}({nested_sql})")
                bindings.extend(nested_bindings)
            elif where.type == "in":
                column = self._wrap_column(where.column)
                placeholders = ", ".join(self._parameter(v) for v in where.value)
                sql_parts.append(f"{prefix}{column} IN ({placeholders})")
                bindings.extend(where.value)
            elif where.type == "not_in":
                column = self._wrap_column(where.column)
                placeholders = ", ".join(self._parameter(v) for v in where.value)
                sql_parts.append(f"{prefix}{column} NOT IN ({placeholders})")
                bindings.extend(where.value)
            elif where.type == "between":
                column = self._wrap_column(where.column)
                placeholders = (
                    f"{self._parameter(where.value[0])} AND {self._parameter(where.value[1])}"
                )
                sql_parts.append(f"{prefix}{column} BETWEEN {placeholders}")
                bindings.extend(where.value)
            elif where.type == "not_between":
                column = self._wrap_column(where.column)
                placeholders = (
                    f"{self._parameter(where.value[0])} AND {self._parameter(where.value[1])}"
                )
                sql_parts.append(f"{prefix}{column} NOT BETWEEN {placeholders}")
                bindings.extend(where.value)
            elif where.type == "null":
                column = self._wrap_column(where.column)
                sql_parts.append(f"{prefix}{column} IS NULL")
            elif where.type == "not_null":
                column = self._wrap_column(where.column)
                sql_parts.append(f"{prefix}{column} IS NOT NULL")
            elif where.type == "raw":
                sql_parts.append(f"{prefix}{where.sql}")
                if where.bindings:
                    bindings.extend(where.bindings)
            else:
                # Basic where clause
                column = self._wrap_column(where.column)
                operator = where.operator
                placeholder = self._parameter(where.value)
                sql_parts.append(f"{prefix}{column} {operator} {placeholder}")
                bindings.append(where.value)

        return "WHERE " + "".join(sql_parts), bindings

    def _compile_nested_where(self, where: Any) -> Tuple[str, List[Any]]:
        """Compile a nested where group.

        Args:
            where: The where clause containing nested query

        Returns:
            Tuple of (SQL clause, bindings list)
        """
        from pyloquent.query.builder import QueryBuilder

        nested_query = QueryBuilder(self)
        nested_query._wheres = where.query._wheres
        nested_query._bindings = where.query._bindings
        return self._compile_wheres(nested_query)

    def _compile_groups(self, query: "QueryBuilder") -> str:
        """Compile the GROUP BY clause.

        Args:
            query: The query builder instance

        Returns:
            SQL GROUP BY clause
        """
        columns = [self._wrap_column(col) for col in query._groups]
        return f"GROUP BY {', '.join(columns)}"

    def _compile_havings(self, query: "QueryBuilder") -> Tuple[str, List[Any]]:
        """Compile the HAVING clauses.

        Args:
            query: The query builder instance

        Returns:
            Tuple of (SQL HAVING clause, bindings list)
        """
        sql_parts = []
        bindings = []

        for i, having in enumerate(query._havings):
            boolean = "AND" if having.boolean == "and" else "OR"
            prefix = f" {boolean} " if i > 0 else ""

            column = self._wrap_column(having.column)
            operator = having.operator
            placeholder = self._parameter(having.value)
            sql_parts.append(f"{prefix}{column} {operator} {placeholder}")
            bindings.append(having.value)

        return "HAVING " + "".join(sql_parts), bindings

    def _compile_orders(self, query: "QueryBuilder") -> str:
        """Compile the ORDER BY clause.

        Args:
            query: The query builder instance

        Returns:
            SQL ORDER BY clause
        """
        orders = []
        for order in query._orders:
            column = self._wrap_column(order.column)
            direction = order.direction.upper()
            orders.append(f"{column} {direction}")

        return f"ORDER BY {', '.join(orders)}"

    def _compile_limit(self, query: "QueryBuilder") -> str:
        """Compile the LIMIT clause.

        Args:
            query: The query builder instance

        Returns:
            SQL LIMIT clause
        """
        return f"LIMIT {query._limit}"

    def _compile_offset(self, query: "QueryBuilder") -> str:
        """Compile the OFFSET clause.

        Args:
            query: The query builder instance

        Returns:
            SQL OFFSET clause
        """
        return f"OFFSET {query._offset}"

    def _compile_aggregate(self, query: "QueryBuilder") -> Tuple[str, List[Any]]:
        """Compile an aggregate query (COUNT, MAX, MIN, etc.).

        Args:
            query: The query builder instance

        Returns:
            Tuple of (SQL string, bindings list)
        """
        aggregate = query._aggregate_data
        func = aggregate.function.upper()
        column = self._wrap_column(aggregate.column)

        sql_parts = [f"SELECT {func}({column}) AS aggregate"]
        bindings = []

        # FROM table
        sql_parts.append(self._compile_from(query))
        bindings.extend(query._bindings.get("from", []))

        # WHEREs
        if query._wheres:
            wheres_sql, wheres_bindings = self._compile_wheres(query)
            sql_parts.append(wheres_sql)
            bindings.extend(wheres_bindings)

        return " ".join(sql_parts), bindings

    def _compile_exists(self, query: "QueryBuilder") -> Tuple[str, List[Any]]:
        """Compile an EXISTS query.

        Args:
            query: The query builder instance

        Returns:
            Tuple of (SQL string, bindings list)
        """
        sql, bindings = self.compile_select(query)
        return f"SELECT EXISTS({sql}) AS exists", bindings

    def _wrap_table(self, table: str) -> str:
        """Wrap a table name with proper delimiters.

        Args:
            table: The table name

        Returns:
            Wrapped table name
        """
        if "." in table:
            # Handle schema.table format
            parts = table.split(".")
            return ".".join(self._wrap_value(part) for part in parts)
        return self._wrap_value(table)

    def _wrap_column(self, column: str) -> str:
        """Wrap a column name with proper delimiters.

        Args:
            column: The column name

        Returns:
            Wrapped column name
        """
        if "." in column and column != "*":
            # Handle table.column format
            parts = column.split(".")
            return ".".join(self._wrap_value(part) for part in parts)
        if column == "*":
            return column
        return self._wrap_value(column)

    def _wrap_value(self, value: str) -> str:
        """Wrap a value (table/column name) with delimiters.

        Args:
            value: The value to wrap

        Returns:
            Wrapped value
        """
        # Base implementation uses double quotes (ANSI SQL)
        # Override in driver-specific grammars
        return f'"{value}"'

    def _parameter(self, value: Any) -> str:
        """Get the parameter placeholder for a value.

        Args:
            value: The value to parameterize

        Returns:
            Parameter placeholder string
        """
        # Base implementation uses ? (positional)
        # Override in driver-specific grammars if needed
        return "?"

    # ========================================================================
    # Schema Compilation
    # ========================================================================

    def compile_create_table(self, blueprint: "Blueprint") -> List[str]:
        """Compile CREATE TABLE statement.

        Args:
            blueprint: Table blueprint

        Returns:
            List of SQL statements
        """
        columns_sql = self._compile_columns_create(blueprint)

        sql = f"CREATE TABLE {self._wrap_table(blueprint.table)} ({columns_sql})"

        statements = [sql]

        # Add index statements
        for index in blueprint.indexes:
            statements.append(self._compile_index(blueprint.table, index))

        # Add foreign key statements
        for fk in blueprint.foreign_keys:
            statements.append(self._compile_foreign_key(blueprint.table, fk))

        return statements

    def compile_alter_table(self, blueprint: "Blueprint") -> List[str]:
        """Compile ALTER TABLE statements.

        Args:
            blueprint: Table blueprint

        Returns:
            List of SQL statements
        """
        statements = []

        for column in blueprint.columns:
            statements.append(
                f"ALTER TABLE {self._wrap_table(blueprint.table)} "
                f"ADD COLUMN {self._compile_column(column)}"
            )

        return statements

    def compile_drop_table(self, table: str) -> str:
        """Compile DROP TABLE statement.

        Args:
            table: Table name

        Returns:
            SQL statement
        """
        return f"DROP TABLE {self._wrap_table(table)}"

    def compile_drop_table_if_exists(self, table: str) -> str:
        """Compile DROP TABLE IF EXISTS statement.

        Args:
            table: Table name

        Returns:
            SQL statement
        """
        return f"DROP TABLE IF EXISTS {self._wrap_table(table)}"

    def compile_rename_table(self, from_table: str, to_table: str) -> str:
        """Compile RENAME TABLE statement.

        Args:
            from_table: Current table name
            to_table: New table name

        Returns:
            SQL statement
        """
        return f"ALTER TABLE {self._wrap_table(from_table)} RENAME TO {self._wrap_table(to_table)}"

    def compile_table_exists(self, table: str) -> Tuple[str, List[Any]]:
        """Compile table existence check.

        Args:
            table: Table name

        Returns:
            Tuple of (SQL, bindings)
        """
        # Default implementation - override in driver-specific grammars
        raise NotImplementedError("compile_table_exists not implemented")

    def compile_column_exists(self, table: str, column: str) -> Tuple[str, List[Any]]:
        """Compile column existence check.

        Args:
            table: Table name
            column: Column name

        Returns:
            Tuple of (SQL, bindings)
        """
        raise NotImplementedError("compile_column_exists not implemented")

    def compile_index_exists(
        self, table: str, columns: List[str], index_type: Optional[str] = None
    ) -> Tuple[str, List[Any]]:
        """Compile index existence check.

        Args:
            table: Table name
            columns: Index columns
            index_type: Type of index

        Returns:
            Tuple of (SQL, bindings)
        """
        raise NotImplementedError("compile_index_exists not implemented")

    def compile_get_tables(self) -> str:
        """Compile query to get all tables.

        Returns:
            SQL statement
        """
        raise NotImplementedError("compile_get_tables not implemented")

    def compile_get_columns(self, table: str) -> Tuple[str, List[Any]]:
        """Compile query to get table columns.

        Args:
            table: Table name

        Returns:
            Tuple of (SQL, bindings)
        """
        raise NotImplementedError("compile_get_columns not implemented")

    def compile_get_indexes(self, table: str) -> Tuple[str, List[Any]]:
        """Compile query to get table indexes.

        Args:
            table: Table name

        Returns:
            Tuple of (SQL, bindings)
        """
        raise NotImplementedError("compile_get_indexes not implemented")

    def compile_get_foreign_keys(self, table: str) -> Tuple[str, List[Any]]:
        """Compile query to get table foreign keys.

        Args:
            table: Table name

        Returns:
            Tuple of (SQL, bindings)
        """
        raise NotImplementedError("compile_get_foreign_keys not implemented")

    def _compile_columns_create(self, blueprint: "Blueprint") -> str:
        """Compile columns for CREATE TABLE.

        Args:
            blueprint: Table blueprint

        Returns:
            Columns SQL
        """
        columns = [self._compile_column(column) for column in blueprint.columns]
        return ", ".join(columns)

    def _compile_column(self, column: "Column") -> str:
        """Compile a single column definition.

        Args:
            column: Column definition

        Returns:
            Column SQL
        """
        sql_parts = [self._wrap_column(column.name)]

        # Type
        type_sql = self._compile_column_type(column)
        sql_parts.append(type_sql)

        # Unsigned
        if column.unsigned:
            sql_parts.append("UNSIGNED")

        # Nullable
        if not column.nullable:
            sql_parts.append("NOT NULL")
        else:
            sql_parts.append("NULL")

        # Default
        if column.default is not None:
            sql_parts.append(f"DEFAULT {self._compile_default_value(column.default)}")

        # Auto increment
        if column.auto_increment:
            sql_parts.append(self._compile_auto_increment())

        return " ".join(sql_parts)

    def _compile_column_type(self, column: "Column") -> str:
        """Compile column type.

        Args:
            column: Column definition

        Returns:
            Type SQL
        """
        type_mapping = {
            "integer": "INTEGER",
            "big_integer": "BIGINT",
            "medium_integer": "MEDIUMINT",
            "small_integer": "SMALLINT",
            "tiny_integer": "TINYINT",
            "float": "FLOAT",
            "double": "DOUBLE",
            "decimal": f"DECIMAL({column.precision}, {column.scale})"
            if column.precision
            else "DECIMAL",
            "char": f"CHAR({column.length or 255})",
            "string": f"VARCHAR({column.length or 255})",
            "text": "TEXT",
            "medium_text": "MEDIUMTEXT",
            "long_text": "LONGTEXT",
            "binary": f"BINARY({column.length})" if column.length else "BLOB",
            "json": "JSON",
            "jsonb": "JSONB",
            "date": "DATE",
            "date_time": f"DATETIME({column.precision})" if column.precision else "DATETIME",
            "date_time_tz": f"TIMESTAMP({column.precision})" if column.precision else "TIMESTAMP",
            "time": f"TIME({column.precision})" if column.precision else "TIME",
            "time_tz": f"TIME({column.precision})" if column.precision else "TIME",
            "timestamp": f"TIMESTAMP({column.precision})" if column.precision else "TIMESTAMP",
            "timestamp_tz": f"TIMESTAMP({column.precision})" if column.precision else "TIMESTAMP",
            "year": "YEAR",
            "uuid": "CHAR(36)",
            "ulid": "CHAR(26)",
            "ip_address": "VARCHAR(45)",
            "mac_address": "VARCHAR(17)",
            "boolean": "BOOLEAN",
            "enum": f"ENUM({', '.join(repr(v) for v in column.allowed)})",
            "set": f"SET({', '.join(repr(v) for v in column.allowed)})",
            "vector": f"VECTOR({column.length})",
        }

        return type_mapping.get(column.type, column.type.upper())

    def _compile_default_value(self, value: Any) -> str:
        """Compile default value.

        Args:
            value: Default value

        Returns:
            Default value SQL
        """
        if value is None:
            return "NULL"
        elif isinstance(value, bool):
            return "1" if value else "0"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, str):
            return repr(value)
        else:
            return repr(str(value))

    def _compile_auto_increment(self) -> str:
        """Compile auto increment clause.

        Returns:
            Auto increment SQL
        """
        return "AUTOINCREMENT"

    def _compile_index(self, table: str, index: "Index") -> str:
        """Compile CREATE INDEX statement.

        Args:
            table: Table name
            index: Index definition

        Returns:
            SQL statement
        """
        index_type = "UNIQUE " if index.unique else ""
        columns = ", ".join(self._wrap_column(col) for col in index.columns)

        return (
            f"CREATE {index_type}INDEX {self._wrap_column(index.name)} "
            f"ON {self._wrap_table(table)} ({columns})"
        )

    def _compile_foreign_key(self, table: str, fk: "ForeignKey") -> str:
        """Compile foreign key constraint.

        Args:
            table: Table name
            fk: Foreign key definition

        Returns:
            SQL statement
        """
        columns = ", ".join(self._wrap_column(col) for col in fk.columns)
        ref_columns = ", ".join(self._wrap_column(col) for col in fk.referenced_columns)

        sql = (
            f"ALTER TABLE {self._wrap_table(table)} "
            f"ADD CONSTRAINT {self._wrap_column(fk.name)} "
            f"FOREIGN KEY ({columns}) "
            f"REFERENCES {self._wrap_table(fk.referenced_table)} ({ref_columns})"
        )

        if fk.on_delete:
            sql += f" ON DELETE {fk.on_delete.upper()}"
        if fk.on_update:
            sql += f" ON UPDATE {fk.on_update.upper()}"

        return sql
