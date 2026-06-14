"""Integration tests for the migration CLI commands.

Regression coverage for the bug where ``pyloquent migrate`` raised
``'SQLiteConnection' object has no attribute 'connection'`` because the CLI
constructed ``SchemaBuilder`` with a raw connection instead of a
ConnectionManager.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from pyloquent.cli.commands import (
    MigrateCommand,
    MigrateRollbackCommand,
    MigrateStatusCommand,
)
from pyloquent.database.sqlite_connection import SQLiteConnection


MIGRATION = textwrap.dedent(
    '''\
    """Create widgets table."""

    from pyloquent.migrations import Migration
    from pyloquent.schema.builder import SchemaBuilder


    class CreateWidgetsTable(Migration):
        async def up(self, schema: SchemaBuilder) -> None:
            await schema.create("widgets", lambda table: [
                table.id(),
                table.string("uid").unique(),
                table.timestamps(),
            ])

        async def down(self, schema: SchemaBuilder) -> None:
            await schema.drop("widgets")
    '''
)


@pytest.fixture
def project(tmp_path: Path):
    """Create a migrations dir, a migration file, and a python config file."""
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "2026_01_01_000000_create_widgets_table.py").write_text(MIGRATION)

    db_path = tmp_path / "cli_test.db"
    config_file = tmp_path / "database_config.py"
    config_file.write_text(
        f'DATABASE = {{"driver": "sqlite", "database": {str(db_path)!r}}}\n'
    )

    return {
        "migrations": str(migrations_dir),
        "config": str(config_file),
        "db": str(db_path),
    }


async def _table_exists(db_path: str, table: str) -> bool:
    conn = SQLiteConnection({"database": db_path})
    await conn.connect()
    try:
        rows = await conn.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            [table],
        )
        return len(rows) > 0
    finally:
        await conn.disconnect()


@pytest.mark.asyncio
async def test_migrate_creates_table(project):
    cmd = MigrateCommand(
        migrations_path=project["migrations"],
        config_path=project["config"],
    )
    # Previously raised: 'SQLiteConnection' object has no attribute 'connection'
    await cmd.handle()

    assert await _table_exists(project["db"], "widgets")


@pytest.mark.asyncio
async def test_migrate_is_idempotent(project):
    cmd = MigrateCommand(
        migrations_path=project["migrations"],
        config_path=project["config"],
    )
    await cmd.handle()
    # Running again must not error and must not re-run the migration.
    await cmd.handle()

    assert await _table_exists(project["db"], "widgets")


@pytest.mark.asyncio
async def test_migrate_status_runs(project, capsys):
    await MigrateCommand(
        migrations_path=project["migrations"],
        config_path=project["config"],
    ).handle()

    await MigrateStatusCommand(
        migrations_path=project["migrations"],
        config_path=project["config"],
    ).handle()

    out = capsys.readouterr().out
    assert "Migration Status" in out
    assert "Ran: 1" in out


@pytest.mark.asyncio
async def test_migrate_rollback(project):
    await MigrateCommand(
        migrations_path=project["migrations"],
        config_path=project["config"],
    ).handle()
    assert await _table_exists(project["db"], "widgets")

    await MigrateRollbackCommand(
        migrations_path=project["migrations"],
        config_path=project["config"],
    ).handle(steps=1)

    assert not await _table_exists(project["db"], "widgets")
