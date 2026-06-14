"""CLI commands for Pyloquent."""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional

from pyloquent.migrations.creator import MigrationCreator
from pyloquent.migrations.runner import MigrationRunner


def _import_model(path: str):
    """Import a model class from a dotted or colon-separated path.

    Accepts ``package.module.ClassName`` or ``package.module:ClassName``.

    Args:
        path: Import path to the model class.

    Returns:
        The imported model class.

    Raises:
        ValueError: If the path is malformed.
        ImportError / AttributeError: If the module or class cannot be found.
    """
    import importlib

    if ":" in path:
        module_path, _, attr = path.partition(":")
    else:
        module_path, _, attr = path.rpartition(".")

    if not module_path or not attr:
        raise ValueError(
            f"Invalid model path: {path!r}. Use 'package.module.ClassName' "
            "or 'package.module:ClassName'."
        )

    module = importlib.import_module(module_path)
    return getattr(module, attr)


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

    async def handle(
        self,
        name: str,
        table: Optional[str] = None,
        create: bool = False,
        model: Optional[str] = None,
    ) -> None:
        """Handle the command.

        Args:
            name: Migration name
            table: Optional table name
            create: Whether to create a table
            model: Optional model import path to generate a create migration from
        """
        creator = MigrationCreator(self.migrations_path)

        if model:
            from pyloquent.migrations.generator import generate_create_migration

            model_cls = _import_model(model)
            content = generate_create_migration(model_cls, name)
            path = await creator.create_from_content(name, content)
        else:
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

    async def _get_manager(self):
        """Build and connect a ConnectionManager from config or environment.

        The schema builder resolves its connection through a
        ConnectionManager (``manager.connection()``), so the CLI must construct
        one rather than passing a raw connection. The manager is also
        registered globally via :func:`set_manager` so that any migrations
        referencing models resolve their connection correctly.

        Returns:
            A connected ConnectionManager.
        """
        from pyloquent.database.manager import ConnectionManager, set_manager

        config = await self._load_config()
        if not config:
            # Default to SQLite in-memory.
            config = {"driver": "sqlite", "database": ":memory:"}

        manager = ConnectionManager()
        manager.add_connection("default", config, default=True)
        await manager.connect()
        set_manager(manager)
        return manager

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
        from pyloquent.schema.builder import SchemaBuilder

        manager = await self._get_manager()

        try:
            schema = SchemaBuilder(manager)
            runner = MigrationRunner(
                connection=manager.connection(),
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
            await manager.disconnect()


class MigrateRollbackCommand(DatabaseCommand):
    """Command to rollback migrations."""

    async def handle(self, steps: int = 1) -> None:
        """Handle the command.

        Args:
            steps: Number of batches to rollback
        """
        from pyloquent.schema.builder import SchemaBuilder

        manager = await self._get_manager()

        try:
            schema = SchemaBuilder(manager)
            runner = MigrationRunner(
                connection=manager.connection(),
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
            await manager.disconnect()


class MigrateStatusCommand(DatabaseCommand):
    """Command to show migration status."""

    async def handle(self) -> None:
        """Handle the command."""
        from pyloquent.schema.builder import SchemaBuilder

        manager = await self._get_manager()

        try:
            schema = SchemaBuilder(manager)
            runner = MigrationRunner(
                connection=manager.connection(),
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
            await manager.disconnect()


class MigrateFreshCommand(DatabaseCommand):
    """Command to drop all tables and re-run migrations."""

    async def handle(self) -> None:
        """Handle the command."""
        from pyloquent.schema.builder import SchemaBuilder

        manager = await self._get_manager()

        try:
            schema = SchemaBuilder(manager)
            runner = MigrationRunner(
                connection=manager.connection(),
                migrations_path=self.migrations_path,
                schema=schema,
            )

            migrations = await runner.fresh()

            print(f"Ran {len(migrations)} migration(s)")

        finally:
            await manager.disconnect()


class MigrateDiffCommand(DatabaseCommand):
    """Generate an alter migration by diffing a model against the live DB."""

    async def handle(self, name: str, model: str) -> None:
        """Handle the command.

        Args:
            name: Migration name (e.g. ``update_users_table``).
            model: Import path to the model to diff against the database.
        """
        from pyloquent.migrations.generator import (
            generate_diff_migration,
            get_table_name,
        )
        from pyloquent.schema.builder import SchemaBuilder

        model_cls = _import_model(model)
        table = get_table_name(model_cls)

        manager = await self._get_manager()
        try:
            schema = SchemaBuilder(manager)
            existing = await schema.get_columns(table)
            existing_names = [row["name"] for row in existing]
            content = generate_diff_migration(model_cls, existing_names, name)
        finally:
            await manager.disconnect()

        creator = MigrationCreator(self.migrations_path)
        path = await creator.create_from_content(name, content)
        print(f"Created migration: {path}")
