"""Schema builder for executing DDL operations."""

from typing import TYPE_CHECKING, Callable, List, Optional

if TYPE_CHECKING:
    from pyloquent.database.manager import ConnectionManager


class SchemaBuilder:
    """Schema builder for database DDL operations.

    This class provides a fluent interface for creating and modifying
    database tables, similar to Laravel's Schema facade.

    Example:
        # Create table
        await Schema.create('users', lambda table: [
            table.id(),
            table.string('name'),
            table.timestamps(),
        ])

        # Modify table
        await Schema.table('users', lambda table: [
            table.string('email').unique(),
        ])

        # Drop table
        await Schema.drop('users')
    """

    def __init__(self, manager: Optional["ConnectionManager"] = None):
        """Initialize schema builder.

        Args:
            manager: Connection manager (uses global if not provided)
        """
        if manager is None:
            from pyloquent.database.manager import get_manager

            manager = get_manager()
        self._manager = manager

    async def create(self, table: str, callback: Callable, temporary: bool = False) -> None:
        """Create a new table.

        Args:
            table: Table name
            callback: Callback that receives Blueprint
            temporary: Whether table is temporary
        """
        from pyloquent.schema.blueprint import Blueprint

        blueprint = Blueprint(table)
        if temporary:
            blueprint.temporary()

        # Execute callback
        columns = callback(blueprint)

        # Handle case where callback returns list of columns
        if columns is not None and not isinstance(columns, list):
            columns = [columns]

        # Get connection and grammar
        conn = self._manager.connection()
        grammar = conn.grammar

        # Compile and execute
        sql = grammar.compile_create_table(blueprint)
        for statement in sql:
            await conn.execute(statement)

    async def create_if_not_exists(self, table: str, callback: Callable) -> None:
        """Create table if it doesn't exist.

        Args:
            table: Table name
            callback: Callback that receives Blueprint
        """
        if not await self.has_table(table):
            await self.create(table, callback)

    async def table(self, table: str, callback: Callable) -> None:
        """Modify an existing table.

        Args:
            table: Table name
            callback: Callback that receives Blueprint
        """
        from pyloquent.schema.blueprint import Blueprint

        blueprint = Blueprint(table)
        callback(blueprint)

        # Get connection and grammar
        conn = self._manager.connection()
        grammar = conn.grammar

        # Compile and execute alterations
        sql = grammar.compile_alter_table(blueprint)
        for statement in sql:
            await conn.execute(statement)

    async def drop(self, table: str) -> None:
        """Drop a table.

        Args:
            table: Table name
        """
        conn = self._manager.connection()
        grammar = conn.grammar

        sql = grammar.compile_drop_table(table)
        await conn.execute(sql)

    async def drop_if_exists(self, table: str) -> None:
        """Drop table if it exists.

        Args:
            table: Table name
        """
        conn = self._manager.connection()
        grammar = conn.grammar

        sql = grammar.compile_drop_table_if_exists(table)
        await conn.execute(sql)

    async def rename(self, from_table: str, to_table: str) -> None:
        """Rename a table.

        Args:
            from_table: Current table name
            to_table: New table name
        """
        conn = self._manager.connection()
        grammar = conn.grammar

        sql = grammar.compile_rename_table(from_table, to_table)
        await conn.execute(sql)

    async def has_table(self, table: str) -> bool:
        """Check if table exists.

        Args:
            table: Table name

        Returns:
            True if table exists
        """
        conn = self._manager.connection()
        grammar = conn.grammar

        sql, bindings = grammar.compile_table_exists(table)
        result = await conn.fetch_one(sql, bindings)
        return result is not None and result.get("exists", False)

    async def has_column(self, table: str, column: str) -> bool:
        """Check if column exists in table.

        Args:
            table: Table name
            column: Column name

        Returns:
            True if column exists
        """
        conn = self._manager.connection()
        grammar = conn.grammar

        sql, bindings = grammar.compile_column_exists(table, column)
        result = await conn.fetch_one(sql, bindings)
        return result is not None and result.get("exists", False)

    async def has_index(
        self, table: str, columns: List[str], index_type: Optional[str] = None
    ) -> bool:
        """Check if index exists on table.

        Args:
            table: Table name
            columns: Column(s) in index
            index_type: Type of index (unique, etc.)

        Returns:
            True if index exists
        """
        conn = self._manager.connection()
        grammar = conn.grammar

        sql, bindings = grammar.compile_index_exists(table, columns, index_type)
        result = await conn.fetch_one(sql, bindings)
        return result is not None and result.get("exists", False)

    async def get_tables(self) -> List[str]:
        """Get list of all tables.

        Returns:
            List of table names
        """
        conn = self._manager.connection()
        grammar = conn.grammar

        sql = grammar.compile_get_tables()
        results = await conn.fetch_all(sql)
        return [row["name"] for row in results]

    async def get_columns(self, table: str) -> List[dict]:
        """Get columns for a table.

        Args:
            table: Table name

        Returns:
            List of column information
        """
        conn = self._manager.connection()
        grammar = conn.grammar

        sql, bindings = grammar.compile_get_columns(table)
        return await conn.fetch_all(sql, bindings)

    async def get_indexes(self, table: str) -> List[dict]:
        """Get indexes for a table.

        Args:
            table: Table name

        Returns:
            List of index information
        """
        conn = self._manager.connection()
        grammar = conn.grammar

        sql, bindings = grammar.compile_get_indexes(table)
        return await conn.fetch_all(sql, bindings)

    async def get_foreign_keys(self, table: str) -> List[dict]:
        """Get foreign keys for a table.

        Args:
            table: Table name

        Returns:
            List of foreign key information
        """
        conn = self._manager.connection()
        grammar = conn.grammar

        sql, bindings = grammar.compile_get_foreign_keys(table)
        return await conn.fetch_all(sql, bindings)


# Global schema builder instance
_schema_builder: Optional[SchemaBuilder] = None


def Schema() -> SchemaBuilder:
    """Get global schema builder instance.

    Returns:
        SchemaBuilder instance
    """
    global _schema_builder
    if _schema_builder is None:
        _schema_builder = SchemaBuilder()
    return _schema_builder
