"""Integration tests for schema alteration ops against live SQLite.

SQLite's ALTER TABLE support is version-gated:
  * RENAME COLUMN requires SQLite >= 3.25
  * DROP COLUMN requires SQLite >= 3.35
Tests that need those are skipped on older engines.
"""
from __future__ import annotations

import sqlite3

import pytest

from pyloquent.schema.builder import SchemaBuilder

_VER = sqlite3.sqlite_version_info
_HAS_DROP_COLUMN = _VER >= (3, 35, 0)
_HAS_RENAME_COLUMN = _VER >= (3, 25, 0)


@pytest.mark.asyncio
async def test_add_column(sqlite_db):
    schema = SchemaBuilder(sqlite_db)
    await schema.create("widgets", lambda t: [t.id(), t.string("name")])

    await schema.table("widgets", lambda t: t.string("color").nullable())

    cols = [c["name"] for c in await schema.get_columns("widgets")]
    assert "color" in cols


@pytest.mark.asyncio
async def test_add_index_in_alter(sqlite_db):
    schema = SchemaBuilder(sqlite_db)
    await schema.create("gadgets", lambda t: [t.id(), t.string("sku")])

    await schema.table("gadgets", lambda t: t.index("sku"))

    indexes = [i["name"] for i in await schema.get_indexes("gadgets")]
    assert any("sku" in name for name in indexes)


@pytest.mark.skipif(not _HAS_DROP_COLUMN, reason="SQLite < 3.35 lacks DROP COLUMN")
@pytest.mark.asyncio
async def test_drop_column(sqlite_db):
    schema = SchemaBuilder(sqlite_db)
    await schema.create("doohickeys", lambda t: [t.id(), t.string("name"), t.string("temp")])

    await schema.table("doohickeys", lambda t: t.drop_column("temp"))

    cols = [c["name"] for c in await schema.get_columns("doohickeys")]
    assert "temp" not in cols
    assert "name" in cols


@pytest.mark.skipif(not _HAS_RENAME_COLUMN, reason="SQLite < 3.25 lacks RENAME COLUMN")
@pytest.mark.asyncio
async def test_rename_column(sqlite_db):
    schema = SchemaBuilder(sqlite_db)
    await schema.create("thingamajigs", lambda t: [t.id(), t.string("name")])

    await schema.table("thingamajigs", lambda t: t.rename_column("name", "title"))

    cols = [c["name"] for c in await schema.get_columns("thingamajigs")]
    assert "title" in cols
    assert "name" not in cols


@pytest.mark.asyncio
async def test_drop_index(sqlite_db):
    schema = SchemaBuilder(sqlite_db)
    await schema.create("sprockets", lambda t: [t.id(), t.string("code")])
    await schema.table("sprockets", lambda t: t.index("code"))

    # Confirm it exists, then drop it by its derived name.
    before = [i["name"] for i in await schema.get_indexes("sprockets")]
    assert "sprockets_code_index" in before

    await schema.table("sprockets", lambda t: t.drop_index(["code"]))

    after = [i["name"] for i in await schema.get_indexes("sprockets")]
    assert "sprockets_code_index" not in after


@pytest.mark.asyncio
async def test_drop_primary_raises_on_sqlite(sqlite_db):
    schema = SchemaBuilder(sqlite_db)
    await schema.create("widgets2", lambda t: [t.id(), t.string("name")])

    with pytest.raises(NotImplementedError):
        await schema.table("widgets2", lambda t: t.drop_primary())


# ---------------------------------------------------------------------------
# Raw statement escape hatch — for DDL the Blueprint does not model (e.g.
# PostgreSQL row-level security). Verified here against SQLite.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_statement_executes_raw_ddl(sqlite_db):
    schema = SchemaBuilder(sqlite_db)
    await schema.statement(
        "CREATE TABLE raw_made (id INTEGER PRIMARY KEY, label TEXT)"
    )
    assert await schema.has_table("raw_made")


@pytest.mark.asyncio
async def test_statement_passes_bindings(sqlite_db):
    schema = SchemaBuilder(sqlite_db)
    await schema.create("raw_rows", lambda t: [t.id(), t.string("name")])

    await schema.statement("INSERT INTO raw_rows (name) VALUES (?)", ["Alice"])

    conn = sqlite_db.connection()
    row = await conn.fetch_one("SELECT name FROM raw_rows WHERE name = ?", ["Alice"])
    assert row is not None
    assert row["name"] == "Alice"
