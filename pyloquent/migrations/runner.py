"""Migration runner for executing migrations."""

import importlib.util
import os
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type

from pyloquent.migrations.migration import Migration

if TYPE_CHECKING:
    from pyloquent.database.connection import Connection
    from pyloquent.schema.builder import SchemaBuilder


class MigrationRunner:
    """Runner for executing database migrations.

    This class manages the migration process, including:
    - Running pending migrations
    - Rolling back migrations
    - Tracking migration status

    Example:
        runner = MigrationRunner(connection, migrations_path='migrations')

        # Run all pending migrations
        await runner.run()

        # Rollback last batch
        await runner.rollback()

        # Rollback specific number of migrations
        await runner.rollback(steps=3)
    """

    def __init__(
        self,
        connection: "Connection",
        migrations_path: str = "migrations",
        schema: Optional["SchemaBuilder"] = None,
    ):
        """Initialize the migration runner.

        Args:
            connection: Database connection
            migrations_path: Path to migration files
            schema: Schema builder instance
        """
        self.connection = connection
        self.migrations_path = Path(migrations_path)
        self.schema = schema
        self._migration_table = "migrations"

    async def _ensure_migration_table(self) -> None:
        """Ensure the migrations tracking table exists."""
        # Check if table exists using raw query
        try:
            await self.connection.fetch_all(f"SELECT 1 FROM {self._migration_table} LIMIT 1")
        except Exception:
            # Table doesn't exist, create it
            grammar = self.connection.grammar

            if grammar.__class__.__name__ == "SQLiteGrammar":
                sql = f"""
                    CREATE TABLE {self._migration_table} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        migration VARCHAR(255) NOT NULL,
                        batch INTEGER NOT NULL,
                        executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
            elif grammar.__class__.__name__ == "PostgresGrammar":
                sql = f"""
                    CREATE TABLE {self._migration_table} (
                        id SERIAL PRIMARY KEY,
                        migration VARCHAR(255) NOT NULL,
                        batch INTEGER NOT NULL,
                        executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
            else:  # MySQL
                sql = f"""
                    CREATE TABLE {self._migration_table} (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        migration VARCHAR(255) NOT NULL,
                        batch INTEGER NOT NULL,
                        executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
            await self.connection.execute(sql)

    async def _get_ran_migrations(self) -> List[str]:
        """Get list of already executed migrations.

        Returns:
            List of migration names
        """
        await self._ensure_migration_table()

        try:
            results = await self.connection.fetch_all(
                f"SELECT migration FROM {self._migration_table} ORDER BY executed_at"
            )
            return [row["migration"] for row in results]
        except Exception:
            return []

    async def _get_last_batch_number(self) -> int:
        """Get the last batch number.

        Returns:
            Last batch number (0 if no migrations)
        """
        await self._ensure_migration_table()

        try:
            result = await self.connection.fetch_one(
                f"SELECT MAX(batch) as batch FROM {self._migration_table}"
            )
            return result["batch"] or 0
        except Exception:
            return 0

    async def _get_migrations_in_batch(self, batch: int) -> List[str]:
        """Get migrations in a specific batch.

        Args:
            batch: Batch number

        Returns:
            List of migration names
        """
        await self._ensure_migration_table()

        results = await self.connection.fetch_all(
            f"SELECT migration FROM {self._migration_table} WHERE batch = ? ORDER BY id DESC",
            [batch],
        )
        return [row["migration"] for row in results]

    async def _record_migration(self, migration: str, batch: int) -> None:
        """Record a migration as executed.

        Args:
            migration: Migration name
            batch: Batch number
        """
        await self.connection.execute(
            f"INSERT INTO {self._migration_table} (migration, batch) VALUES (?, ?)",
            [migration, batch],
        )

    async def _remove_migration(self, migration: str) -> None:
        """Remove a migration record.

        Args:
            migration: Migration name
        """
        await self.connection.execute(
            f"DELETE FROM {self._migration_table} WHERE migration = ?",
            [migration],
        )

    def _get_migration_files(self) -> List[Path]:
        """Get all migration files from the migrations directory.

        Returns:
            List of migration file paths
        """
        if not self.migrations_path.exists():
            return []

        files = sorted(self.migrations_path.glob("*.py"))
        return [f for f in files if not f.name.startswith("_")]

    def _load_migration_class(self, file_path: Path) -> Optional[Type[Migration]]:
        """Load a migration class from a file.

        Args:
            file_path: Path to migration file

        Returns:
            Migration class or None
        """
        # Extract migration name from filename
        # Format: YYYY_MM_DD_HHMMSS_migration_name.py
        match = re.match(r"^(\d{4}_\d{2}_\d{2}_\d{6})_(.+)\.py$", file_path.name)
        if not match:
            return None

        timestamp, name = match.groups()

        # Load the module
        spec = importlib.util.spec_from_file_location(f"migration_{timestamp}", file_path)
        if not spec or not spec.loader:
            return None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Find migration class
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, Migration) and attr is not Migration:
                attr.name = f"{timestamp}_{name}"
                return attr

        return None

    async def run(self) -> List[str]:
        """Run all pending migrations.

        Returns:
            List of executed migration names
        """
        ran_migrations = await self._get_ran_migrations()
        migration_files = self._get_migration_files()

        pending = []
        for file_path in migration_files:
            migration_class = self._load_migration_class(file_path)
            if migration_class and migration_class.name not in ran_migrations:
                pending.append((file_path, migration_class))

        if not pending:
            return []

        # Get next batch number
        batch = await self._get_last_batch_number() + 1

        executed = []
        for file_path, migration_class in pending:
            migration = migration_class()
            migration.batch = batch

            # Run the migration
            if self.schema:
                await migration.up(self.schema)
            else:
                # If no schema builder, migration must handle its own DDL
                raise RuntimeError(
                    "Schema builder required for migrations. "
                    "Pass schema parameter to MigrationRunner."
                )

            # Record it
            await self._record_migration(migration.name, batch)
            executed.append(migration.name)

        return executed

    async def rollback(self, steps: int = 1) -> List[str]:
        """Rollback migrations.

        Args:
            steps: Number of batches to rollback (default: 1)

        Returns:
            List of rolled back migration names
        """
        last_batch = await self._get_last_batch_number()
        rolled_back = []

        for _ in range(steps):
            if last_batch <= 0:
                break

            migrations = await self._get_migrations_in_batch(last_batch)

            for migration_name in migrations:
                # Find the migration file
                migration_files = self._get_migration_files()

                for file_path in migration_files:
                    if migration_name in file_path.name:
                        migration_class = self._load_migration_class(file_path)
                        if migration_class:
                            migration = migration_class()

                            # Rollback
                            if self.schema:
                                await migration.down(self.schema)

                            # Remove record
                            await self._remove_migration(migration_name)
                            rolled_back.append(migration_name)

            last_batch -= 1

        return rolled_back

    async def reset(self) -> List[str]:
        """Rollback all migrations.

        Returns:
            List of rolled back migration names
        """
        last_batch = await self._get_last_batch_number()
        return await self.rollback(steps=last_batch)

    async def status(self) -> Dict[str, Any]:
        """Get migration status.

        Returns:
            Dictionary with migration status information
        """
        ran_migrations = await self._get_ran_migrations()
        migration_files = self._get_migration_files()

        all_migrations = []
        for file_path in migration_files:
            migration_class = self._load_migration_class(file_path)
            if migration_class:
                all_migrations.append(
                    {
                        "name": migration_class.name,
                        "ran": migration_class.name in ran_migrations,
                    }
                )

        pending = [m for m in all_migrations if not m["ran"]]

        return {
            "ran": len(ran_migrations),
            "pending": len(pending),
            "migrations": all_migrations,
        }

    async def fresh(self) -> List[str]:
        """Drop all tables and re-run all migrations.

        Returns:
            List of executed migration names
        """
        # Reset all migrations
        await self.reset()

        # Re-run all
        return await self.run()
