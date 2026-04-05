"""CLI commands for Pyloquent."""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional

from pyloquent.migrations.creator import MigrationCreator
from pyloquent.migrations.runner import MigrationRunner


class Command(ABC):
    """Base class for CLI commands."""

    @abstractmethod
    async def handle(self, **kwargs) -> None:
        """Handle the command.

        Args:
            **kwargs: Command arguments
        """
        pass


class MakeMigrationCommand(Command):
    """Command to create a new migration file."""

    def __init__(self, migrations_path: str = "migrations"):
        """Initialize the command.

        Args:
            migrations_path: Path to migrations directory
        """
        self.migrations_path = migrations_path

    async def handle(self, name: str, table: Optional[str] = None, create: bool = False) -> None:
        """Handle the command.

        Args:
            name: Migration name
            table: Optional table name
            create: Whether to create a table
        """
        creator = MigrationCreator(self.migrations_path)
        path = await creator.create(name, table=table, create=create)

        print(f"Created migration: {path}")


class MakeModelCommand(Command):
    """Command to create a new model file."""

    def __init__(self, models_path: str = "models", migrations_path: str = "migrations"):
        """Initialize the command.

        Args:
            models_path: Path to models directory
            migrations_path: Path to migrations directory
        """
        self.models_path = Path(models_path)
        self.migrations_path = migrations_path

    async def handle(
        self,
        name: str,
        table: Optional[str] = None,
        create_migration: bool = False,
    ) -> None:
        """Handle the command.

        Args:
            name: Model name
            table: Optional table name
            create_migration: Whether to create a migration
        """
        # Ensure models directory exists
        self.models_path.mkdir(parents=True, exist_ok=True)

        # Create model file
        model_file = self.models_path / f"{name.lower()}.py"
        table_name = table or self._pluralise(name.lower())

        content = self._generate_model_content(name, table_name)
        model_file.write_text(content)

        print(f"Created model: {model_file}")

        # Create migration if requested
        if create_migration:
            migration_creator = MigrationCreator(self.migrations_path)
            migration_name = f"create_{table_name}_table"
            migration_path = await migration_creator.create(
                migration_name, table=table_name, create=True
            )
            print(f"Created migration: {migration_path}")

    def _generate_model_content(self, class_name: str, table: str) -> str:
        """Generate model file content.

        Args:
            class_name: Model class name
            table: Table name

        Returns:
            Model file content
        """
        return f'''"""{class_name} model."""

from typing import Optional
from pyloquent import Model


class {class_name}(Model):
    """{class_name} model."""

    __table__ = "{table}"
    __fillable__ = []

    id: Optional[int] = None
'''

    def _pluralise(self, word: str) -> str:
        """Simple pluralisation.

        Args:
            word: Word to pluralise

        Returns:
            Pluralised word
        """
        if word.endswith("y") and word[-2] not in "aeiou":
            return word[:-1] + "ies"
        elif word.endswith(("s", "x", "z", "ch", "sh")):
            return word + "es"
        return word + "s"


class DatabaseCommand(Command):
    """Base class for database commands."""

    def __init__(self, migrations_path: str = "migrations", config_path: Optional[str] = None):
        """Initialize the command.

        Args:
            migrations_path: Path to migrations directory
            config_path: Path to database configuration file
        """
        self.migrations_path = migrations_path
        self.config_path = config_path

    async def _get_connection(self):
        """Get database connection from config or environment.

        Returns:
            Database connection
        """
        from pyloquent.database.connection import Connection
        from pyloquent.database.sqlite_connection import SQLiteConnection

        # Try to load config
        config = await self._load_config()

        if config:
            driver = config.get("driver", "sqlite")

            if driver == "sqlite":
                return SQLiteConnection(config)
            elif driver == "postgres":
                from pyloquent.database.postgres_connection import PostgresConnection

                return PostgresConnection(config)
            elif driver == "mysql":
                from pyloquent.database.mysql_connection import MySQLConnection

                return MySQLConnection(config)

        # Default to SQLite in-memory
        return SQLiteConnection({"database": ":memory:"})

    async def _load_config(self) -> Optional[Dict[str, Any]]:
        """Load database configuration.

        Returns:
            Configuration dictionary or None
        """
        if not self.config_path:
            return None

        config_file = Path(self.config_path)
        if not config_file.exists():
            return None

        content = config_file.read_text()

        # Try JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try Python file
        if config_file.suffix == ".py":
            import importlib.util

            spec = importlib.util.spec_from_file_location("config", config_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, "DATABASE"):
                    return module.DATABASE

        return None


class MigrateCommand(DatabaseCommand):
    """Command to run migrations."""

    async def handle(self) -> None:
        """Handle the command."""
        connection = await self._get_connection()
        await connection.connect()

        try:
            from pyloquent.schema.builder import SchemaBuilder

            schema = SchemaBuilder(connection)
            runner = MigrationRunner(
                connection=connection,
                migrations_path=self.migrations_path,
                schema=schema,
            )

            migrations = await runner.run()

            if migrations:
                print(f"Ran {len(migrations)} migration(s):")
                for migration in migrations:
                    print(f"  - {migration}")
            else:
                print("Nothing to migrate.")

        finally:
            await connection.disconnect()


class MigrateRollbackCommand(DatabaseCommand):
    """Command to rollback migrations."""

    async def handle(self, steps: int = 1) -> None:
        """Handle the command.

        Args:
            steps: Number of batches to rollback
        """
        connection = await self._get_connection()
        await connection.connect()

        try:
            from pyloquent.schema.builder import SchemaBuilder

            schema = SchemaBuilder(connection)
            runner = MigrationRunner(
                connection=connection,
                migrations_path=self.migrations_path,
                schema=schema,
            )

            migrations = await runner.rollback(steps=steps)

            if migrations:
                print(f"Rolled back {len(migrations)} migration(s):")
                for migration in migrations:
                    print(f"  - {migration}")
            else:
                print("Nothing to rollback.")

        finally:
            await connection.disconnect()


class MigrateStatusCommand(DatabaseCommand):
    """Command to show migration status."""

    async def handle(self) -> None:
        """Handle the command."""
        connection = await self._get_connection()
        await connection.connect()

        try:
            from pyloquent.schema.builder import SchemaBuilder

            schema = SchemaBuilder(connection)
            runner = MigrationRunner(
                connection=connection,
                migrations_path=self.migrations_path,
                schema=schema,
            )

            status = await runner.status()

            print(f"Migration Status")
            print(f"----------------")
            print(f"Ran: {status['ran']}")
            print(f"Pending: {status['pending']}")
            print()

            if status["migrations"]:
                print("Migrations:")
                for migration in status["migrations"]:
                    status_icon = "✓" if migration["ran"] else "✗"
                    print(f"  [{status_icon}] {migration['name']}")

        finally:
            await connection.disconnect()


class MigrateFreshCommand(DatabaseCommand):
    """Command to drop all tables and re-run migrations."""

    async def handle(self) -> None:
        """Handle the command."""
        connection = await self._get_connection()
        await connection.connect()

        try:
            from pyloquent.schema.builder import SchemaBuilder

            schema = SchemaBuilder(connection)
            runner = MigrationRunner(
                connection=connection,
                migrations_path=self.migrations_path,
                schema=schema,
            )

            migrations = await runner.fresh()

            print(f"Ran {len(migrations)} migration(s)")

        finally:
            await connection.disconnect()
