"""Migration creator for generating new migration files."""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional


class MigrationCreator:
    """Creator for generating new migration files.

    Example:
        creator = MigrationCreator('migrations')

        # Create a migration
        path = await creator.create('create_users_table')

        # Create a migration with table specified
        path = await creator.create('add_email_to_users', table='users')
    """

    def __init__(self, migrations_path: str = "migrations"):
        """Initialize the migration creator.

        Args:
            migrations_path: Path to migrations directory
        """
        self.migrations_path = Path(migrations_path)

    async def create(self, name: str, table: Optional[str] = None, create: bool = False) -> Path:
        """Create a new migration file.

        Args:
            name: Migration name (e.g., 'create_users_table')
            table: Optional table name for table-specific migrations
            create: Whether this is a create table migration

        Returns:
            Path to created migration file
        """
        # Ensure migrations directory exists
        self.migrations_path.mkdir(parents=True, exist_ok=True)

        # Generate timestamp
        timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")

        # Create filename
        filename = f"{timestamp}_{name}.py"
        file_path = self.migrations_path / filename

        # Generate migration content
        content = self._get_migration_content(name, table, create)

        # Write file
        file_path.write_text(content)

        return file_path

    def _get_migration_content(
        self, name: str, table: Optional[str] = None, create: bool = False
    ) -> str:
        """Generate migration file content.

        Args:
            name: Migration name
            table: Optional table name
            create: Whether this is a create table migration

        Returns:
            Python code for migration
        """
        class_name = self._to_class_name(name)

        if table and create:
            return self._get_create_table_content(class_name, table)
        elif table:
            return self._get_table_migration_content(class_name, table)
        else:
            return self._get_blank_migration_content(class_name)

    def _to_class_name(self, name: str) -> str:
        """Convert migration name to class name.

        Args:
            name: Migration name (e.g., 'create_users_table')

        Returns:
            Class name (e.g., 'CreateUsersTable')
        """
        # Remove non-alphanumeric characters and split by underscores
        parts = re.split(r"[_\-]", name)
        # Capitalize each part and join
        return "".join(part.capitalize() for part in parts if part)

    def _get_create_table_content(self, class_name: str, table: str) -> str:
        """Get content for a create table migration.

        Args:
            class_name: Migration class name
            table: Table name

        Returns:
            Migration content
        """
        return f'''"""Migration for creating {table} table."""

from pyloquent.migrations import Migration
from pyloquent.schema.builder import SchemaBuilder


class {class_name}(Migration):
    """Create the {table} table."""

    async def up(self, schema: SchemaBuilder) -> None:
        """Run the migration."""
        await schema.create("{table}", lambda table: (
            table.id(),
            table.timestamps()
        ))

    async def down(self, schema: SchemaBuilder) -> None:
        """Reverse the migration."""
        await schema.drop("{table}")
'''

    def _get_table_migration_content(self, class_name: str, table: str) -> str:
        """Get content for a table modification migration.

        Args:
            class_name: Migration class name
            table: Table name

        Returns:
            Migration content
        """
        return f'''"""Migration for modifying {table} table."""

from pyloquent.migrations import Migration
from pyloquent.schema.builder import SchemaBuilder


class {class_name}(Migration):
    """Modify the {table} table."""

    async def up(self, schema: SchemaBuilder) -> None:
        """Run the migration."""
        await schema.table("{table}", lambda table: (
            # Add your columns here
            # table.string('new_column'),
        ))

    async def down(self, schema: SchemaBuilder) -> None:
        """Reverse the migration."""
        await schema.table("{table}", lambda table: (
            # Reverse your changes
            # table.drop_column('new_column'),
        ))
'''

    def _get_blank_migration_content(self, class_name: str) -> str:
        """Get content for a blank migration.

        Args:
            class_name: Migration class name

        Returns:
            Migration content
        """
        return f'''"""Migration."""

from pyloquent.migrations import Migration
from pyloquent.schema.builder import SchemaBuilder


class {class_name}(Migration):
    """Migration."""

    async def up(self, schema: SchemaBuilder) -> None:
        """Run the migration."""
        pass

    async def down(self, schema: SchemaBuilder) -> None:
        """Reverse the migration."""
        pass
'''
