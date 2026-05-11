"""Regression tests for `QueryBuilder.order_by_raw`.

Before 0.3.4 there was no way to express dialect-specific ORDER BY clauses
like `NULLS FIRST/LAST`, `COALESCE(...)`, or computed expressions. Users
had to fall back to a raw `connection.execute(...)` call, defeating the
point of the builder.
"""
from __future__ import annotations

from typing import Optional

import pytest

from pyloquent import ConnectionManager, Model
from pyloquent.database.manager import set_manager


class _Item(Model):
    __table__ = "items"
    __fillable__ = ("name", "priority", "ends_at")

    id: Optional[int] = None
    name: str = ""
    priority: int = 0
    ends_at: Optional[str] = None


@pytest.fixture
async def items():
    mgr = ConnectionManager()
    mgr.add_connection("default", {"driver": "sqlite", "database": ":memory:"}, default=True)
    await mgr.connect()
    set_manager(mgr)
    conn = mgr.connection()
    await conn.execute(
        "CREATE TABLE items ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  name TEXT NOT NULL,"
        "  priority INTEGER NOT NULL DEFAULT 0,"
        "  ends_at TEXT"
        ")"
    )
    # Seed: a couple of rows with NULL `ends_at`.
    await _Item.create({"name": "ongoing", "priority": 1, "ends_at": None})
    await _Item.create({"name": "old", "priority": 2, "ends_at": "2023-01-01"})
    await _Item.create({"name": "newer", "priority": 3, "ends_at": "2024-01-01"})
    try:
        yield
    finally:
        await mgr.disconnect()


class TestOrderByRaw:
    async def test_order_by_raw_compiles_into_select(self, items) -> None:
        """The builder emits the raw SQL literally inside ORDER BY."""
        sql = (
            _Item.query.order_by_raw("COALESCE(ends_at, '9999-12-31') DESC")
            .to_raw_sql()
        )
        # The raw fragment must end up verbatim in the SQL.
        assert "ORDER BY COALESCE(ends_at, '9999-12-31') DESC" in sql

    async def test_order_by_raw_executes_against_sqlite(self, items) -> None:
        rows = (
            await _Item.query
            .order_by_raw("COALESCE(ends_at, '9999-12-31') DESC")
            .get()
        )
        # `ongoing` (NULL → 9999) comes first; then `newer` (2024); then `old` (2023).
        assert [r.name for r in rows] == ["ongoing", "newer", "old"]

    async def test_order_by_raw_supports_bindings(self, items) -> None:
        """Like `where_raw`, the raw expression can carry parameters."""
        rows = (
            await _Item.query
            .order_by_raw("CASE WHEN priority = ? THEN 0 ELSE 1 END", [2])
            .order_by("priority", "asc")
            .get()
        )
        # priority=2 is pinned first, then the rest in ascending priority.
        assert rows[0].priority == 2

    async def test_order_by_raw_composes_with_order_by(self, items) -> None:
        """Multiple ORDER BY clauses, mixing raw and column, preserve order."""
        sql = (
            _Item.query
            .order_by_raw("ends_at IS NULL DESC")
            .order_by("priority", "asc")
            .to_raw_sql()
        )
        assert "ORDER BY ends_at IS NULL DESC, " in sql
        assert "priority" in sql
