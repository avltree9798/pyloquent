"""Integration tests for model-based migration generation CLI commands."""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest
import pytest_asyncio

from pyloquent.cli.commands import MakeMigrationCommand, MigrateDiffCommand
from pyloquent.database.sqlite_connection import SQLiteConnection


MODEL_MODULE = textwrap.dedent(
    '''\
    from typing import Optional
    from pyloquent.orm.model import Model


    class Article(Model):
        __table__ = "articles"
        __fillable__ = ["title", "body", "views"]

        id: Optional[int] = None
        title: str
        body: Optional[str] = None
        views: int = 0
    '''
)


@pytest_asyncio.fixture
def model_project(tmp_path: Path):
    """Write an importable model module and a migrations dir under tmp_path."""
    module_name = "pyloquent_cli_genmodels"
    (tmp_path / f"{module_name}.py").write_text(MODEL_MODULE)
    migrations = tmp_path / "migrations"
    migrations.mkdir()

    sys.path.insert(0, str(tmp_path))
    try:
        yield {
            "model": f"{module_name}:Article",
            "migrations": str(migrations),
            "tmp": tmp_path,
        }
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop(module_name, None)


@pytest.mark.asyncio
async def test_make_migration_from_model(model_project):
    await MakeMigrationCommand(migrations_path=model_project["migrations"]).handle(
        name="create_articles_table",
        model=model_project["model"],
    )

    files = list(Path(model_project["migrations"]).glob("*_create_articles_table.py"))
    assert len(files) == 1
    content = files[0].read_text()
    compile(content, str(files[0]), "exec")
    assert 'schema.create("articles"' in content
    assert "table.id()" in content
    assert 'table.string("title")' in content
    assert 'table.string("body").nullable()' in content
    assert 'table.integer("views").default(0)' in content


@pytest.mark.asyncio
async def test_migrate_diff_from_model(model_project):
    tmp = model_project["tmp"]
    db_path = tmp / "diff.db"

    # Pre-create the table with only a subset of the model's columns.
    conn = SQLiteConnection({"database": str(db_path)})
    await conn.connect()
    await conn.execute(
        "CREATE TABLE articles (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "title TEXT NOT NULL, legacy TEXT)"
    )
    await conn.disconnect()

    config_file = tmp / "database_config.py"
    config_file.write_text(
        f'DATABASE = {{"driver": "sqlite", "database": {str(db_path)!r}}}\n'
    )

    await MigrateDiffCommand(
        migrations_path=model_project["migrations"],
        config_path=str(config_file),
    ).handle(name="update_articles_table", model=model_project["model"])

    files = list(Path(model_project["migrations"]).glob("*_update_articles_table.py"))
    assert len(files) == 1
    content = files[0].read_text()
    compile(content, str(files[0]), "exec")
    # body + views are on the model but missing from the table -> added.
    assert 'table.string("body").nullable()' in content
    assert 'table.integer("views").default(0)' in content
    # legacy is in the DB but not on the model -> dropped.
    assert 'table.drop_column("legacy")' in content
