"""Integration tests for QueryBuilder terminator methods: paginate, simple_paginate, cursor, lazy, pluck, find_or_fail, cache methods."""
import pytest
from typing import Optional
from pyloquent import Model
from pyloquent.exceptions import ModelNotFoundException, QueryException
from pyloquent.query.builder import QueryBuilder
from pyloquent.grammars.sqlite_grammar import SQLiteGrammar


class QtUser(Model):
    __table__ = "qt_users"
    __fillable__ = ["name", "score"]
    id: Optional[int] = None
    name: str
    score: Optional[int] = 0


@pytest.fixture
async def qt_tables(sqlite_db):
    conn = sqlite_db.connection()
    await conn.execute("""
        CREATE TABLE qt_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            score INTEGER DEFAULT 0,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    for i in range(10):
        await conn.execute(
            "INSERT INTO qt_users (name, score) VALUES (?, ?)",
            [f"User{i}", i * 10],
        )
    yield


# ---------------------------------------------------------------------------
# paginate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_paginate_returns_correct_structure(sqlite_db, qt_tables):
    result = await QtUser.query.paginate(per_page=3, page=1)
    assert "data" in result
    assert result["total"] == 10
    assert result["per_page"] == 3
    assert result["current_page"] == 1
    assert result["last_page"] == 4
    assert len(result["data"]) == 3


@pytest.mark.asyncio
async def test_paginate_page_2(sqlite_db, qt_tables):
    result = await QtUser.query.paginate(per_page=4, page=2)
    assert result["current_page"] == 2
    assert len(result["data"]) == 4
    assert result["from"] == 5
    assert result["to"] == 8


@pytest.mark.asyncio
async def test_paginate_last_page(sqlite_db, qt_tables):
    result = await QtUser.query.paginate(per_page=3, page=4)
    assert len(result["data"]) == 1
    assert result["to"] == 10


@pytest.mark.asyncio
async def test_paginate_with_columns(sqlite_db, qt_tables):
    result = await QtUser.query.paginate(per_page=5, page=1, columns=["name"])
    assert result["total"] == 10
    assert len(result["data"]) == 5


@pytest.mark.asyncio
async def test_paginate_empty(sqlite_db, qt_tables):
    result = await QtUser.query.where("name", "NONEXISTENT").paginate(per_page=10, page=1)
    assert result["total"] == 0
    assert result["from"] == 0
    assert result["last_page"] == 1


# ---------------------------------------------------------------------------
# simple_paginate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_simple_paginate_has_more(sqlite_db, qt_tables):
    result = await QtUser.query.simple_paginate(per_page=3, page=1)
    assert result["has_more_pages"] is True
    assert len(result["data"]) == 3


@pytest.mark.asyncio
async def test_simple_paginate_last_page(sqlite_db, qt_tables):
    result = await QtUser.query.simple_paginate(per_page=9, page=2)
    assert result["has_more_pages"] is False
    assert len(result["data"]) == 1


@pytest.mark.asyncio
async def test_simple_paginate_with_columns(sqlite_db, qt_tables):
    result = await QtUser.query.simple_paginate(per_page=5, page=1, columns=["name"])
    assert "data" in result
    assert result["per_page"] == 5


# ---------------------------------------------------------------------------
# cursor
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cursor_yields_all(sqlite_db, qt_tables):
    items = []
    async for item in QtUser.query.cursor():
        items.append(item)
    assert len(items) == 10


@pytest.mark.asyncio
async def test_cursor_empty(sqlite_db, qt_tables):
    items = []
    async for item in QtUser.query.where("name", "NOPE").cursor():
        items.append(item)
    assert items == []


# ---------------------------------------------------------------------------
# lazy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_lazy_yields_all(sqlite_db, qt_tables):
    items = []
    async for item in QtUser.query.lazy(chunk_size=3):
        items.append(item)
    assert len(items) == 10


# ---------------------------------------------------------------------------
# pluck
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pluck_returns_column_values(sqlite_db, qt_tables):
    names = await QtUser.query.order_by("id").pluck("name")
    assert names[0] == "User0"
    assert len(names) == 10


# ---------------------------------------------------------------------------
# find_or_fail
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_find_or_fail_found(sqlite_db, qt_tables):
    user = await QtUser.query.find_or_fail(1)
    assert user is not None
    assert user.id == 1


@pytest.mark.asyncio
async def test_find_or_fail_raises(sqlite_db, qt_tables):
    with pytest.raises(ModelNotFoundException):
        await QtUser.query.find_or_fail(9999)


# ---------------------------------------------------------------------------
# first_or_fail raises when no results
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_first_or_fail_raises(sqlite_db, qt_tables):
    with pytest.raises(ModelNotFoundException):
        await QtUser.query.where("name", "NONEXISTENT").first_or_fail()


# ---------------------------------------------------------------------------
# _execute_get without model_class (returns plain Collection of dicts)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_get_no_model_class_returns_dicts(sqlite_db, qt_tables):
    conn = sqlite_db.connection()
    grammar = conn.grammar
    qb = QueryBuilder(grammar, connection=conn).from_("qt_users")
    results = await qb.get()
    assert len(results) == 10
    assert isinstance(results[0], dict)


# ---------------------------------------------------------------------------
# insert bulk
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_insert_bulk(sqlite_db, qt_tables):
    conn = sqlite_db.connection()
    grammar = conn.grammar
    qb = QueryBuilder(grammar, connection=conn).from_("qt_users")
    ok = await qb.insert([{"name": "Bulk1", "score": 1}, {"name": "Bulk2", "score": 2}])
    assert ok is True
    count = await QtUser.query.count()
    assert count == 12


# ---------------------------------------------------------------------------
# cache method (unit, no real cache)
# ---------------------------------------------------------------------------

def test_cache_sets_ttl():
    qb = QueryBuilder(SQLiteGrammar()).from_("users")
    qb.cache(ttl=60)
    assert qb._cache_ttl == 60


def test_cache_forever_sets_none_ttl():
    qb = QueryBuilder(SQLiteGrammar()).from_("users")
    qb.cache_forever()
    assert qb._cache_ttl is None
    assert qb._cache_key is not None


def test_cache_tags_sets_tags():
    qb = QueryBuilder(SQLiteGrammar()).from_("users")
    qb.cache_tags("users", "admins")
    assert qb._cache_tags == ["users", "admins"]
