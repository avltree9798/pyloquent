"""Integration/unit tests for remaining QueryBuilder method coverage."""
import pytest
from typing import Optional
from pyloquent import Model
from pyloquent.exceptions import QueryException
from pyloquent.query.builder import QueryBuilder
from pyloquent.grammars.sqlite_grammar import SQLiteGrammar


class ExUser(Model):
    __table__ = "ex_users"
    __fillable__ = ["name", "score", "active"]
    id: Optional[int] = None
    name: str
    score: Optional[int] = 0
    active: Optional[bool] = True


@pytest.fixture
async def ex_tables(sqlite_db):
    conn = sqlite_db.connection()
    await conn.execute("""
        CREATE TABLE ex_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            score INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    for i in range(5):
        await conn.execute("INSERT INTO ex_users (name, score) VALUES (?, ?)", [f"U{i}", i * 5])
    yield


# ---------------------------------------------------------------------------
# take / skip aliases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_take_alias_for_limit(sqlite_db, ex_tables):
    results = await ExUser.query.take(2).get()
    assert len(results) == 2


@pytest.mark.asyncio
async def test_skip_alias_for_offset(sqlite_db, ex_tables):
    all_results = await ExUser.query.order_by("id").get()
    skipped = await ExUser.query.order_by("id").skip(2).limit(100).get()
    assert len(skipped) == len(all_results) - 2


# ---------------------------------------------------------------------------
# for_page
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_for_page(sqlite_db, ex_tables):
    results = await ExUser.query.for_page(2, 2).get()
    assert len(results) == 2


def test_for_page_raises_on_page_zero():
    qb = QueryBuilder(SQLiteGrammar()).from_("users")
    with pytest.raises(ValueError):
        qb.for_page(0)


def test_limit_raises_on_negative():
    qb = QueryBuilder(SQLiteGrammar()).from_("users")
    with pytest.raises(ValueError):
        qb.limit(-1)


def test_offset_raises_on_negative():
    qb = QueryBuilder(SQLiteGrammar()).from_("users")
    with pytest.raises(ValueError):
        qb.offset(-1)


# ---------------------------------------------------------------------------
# or_having
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_or_having(sqlite_db, ex_tables):
    results = await (
        ExUser.query.select_raw("name, COUNT(*) as cnt")
        .group_by("name")
        .having("cnt", ">=", 1)
        .or_having("score", ">", 0)
        .get()
    )
    assert len(results) >= 1


# ---------------------------------------------------------------------------
# increment / decrement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_increment(sqlite_db, ex_tables):
    u = await ExUser.create({"name": "Inc", "score": 10})
    await ExUser.query.where("id", u.id).increment("score", 5)
    refreshed = await ExUser.find(u.id)
    assert refreshed.score == 15


@pytest.mark.asyncio
async def test_decrement(sqlite_db, ex_tables):
    u = await ExUser.create({"name": "Dec", "score": 20})
    await ExUser.query.where("id", u.id).decrement("score", 3)
    refreshed = await ExUser.find(u.id)
    assert refreshed.score == 17


@pytest.mark.asyncio
async def test_increment_with_extra_columns(sqlite_db, ex_tables):
    u = await ExUser.create({"name": "IncEx", "score": 0})
    await ExUser.query.where("id", u.id).increment("score", 1, extra={"name": "Updated"})
    refreshed = await ExUser.find(u.id)
    assert refreshed.score == 1
    assert refreshed.name == "Updated"


# ---------------------------------------------------------------------------
# update_all / delete_all
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_all(sqlite_db, ex_tables):
    count = await ExUser.query.update_all({"active": False})
    assert count >= 5


@pytest.mark.asyncio
async def test_delete_all(sqlite_db, ex_tables):
    await ExUser.query.update_all({"active": False})
    deleted = await ExUser.query.delete_all()
    remaining = await ExUser.query.count()
    assert remaining == 0


# ---------------------------------------------------------------------------
# update raises without WHERE
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_raises_without_where(sqlite_db, ex_tables):
    conn = sqlite_db.connection()
    grammar = conn.grammar
    qb = QueryBuilder(grammar, connection=conn).from_("ex_users")
    with pytest.raises(QueryException):
        await qb.update({"name": "DANGER"})


# ---------------------------------------------------------------------------
# delete raises without WHERE
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_raises_without_where(sqlite_db, ex_tables):
    conn = sqlite_db.connection()
    grammar = conn.grammar
    qb = QueryBuilder(grammar, connection=conn).from_("ex_users")
    with pytest.raises(QueryException):
        await qb.delete()


# ---------------------------------------------------------------------------
# each (callback-based iteration)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_each_sync_callback(sqlite_db, ex_tables):
    names = []
    await ExUser.query.each(lambda u: names.append(u.name), chunk_size=2)
    assert len(names) == 5


@pytest.mark.asyncio
async def test_each_async_callback(sqlite_db, ex_tables):
    names = []

    async def collect(u):
        names.append(u.name)

    await ExUser.query.each(collect, chunk_size=3)
    assert len(names) == 5


# ---------------------------------------------------------------------------
# chunk
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chunk_yields_all(sqlite_db, ex_tables):
    total = []
    async for chunk in ExUser.query.chunk(2):
        total.extend(chunk)
    assert len(total) == 5


# ---------------------------------------------------------------------------
# lock_for_update / for_share / to_raw_sql (unit - no connection needed)
# ---------------------------------------------------------------------------

def test_lock_for_update_sql():
    qb = QueryBuilder(SQLiteGrammar()).from_("users").where("id", 1)
    qb.lock_for_update()
    sql, _ = qb.to_sql()
    assert sql  # doesn't crash; lock may be ignored in SQLite


def test_for_share_sql():
    qb = QueryBuilder(SQLiteGrammar()).from_("users").where("id", 1)
    qb.for_share()
    sql, _ = qb.to_sql()
    assert sql


def test_to_raw_sql():
    qb = QueryBuilder(SQLiteGrammar()).from_("users").where("name", "Alice")
    raw = qb.to_raw_sql()
    assert "Alice" in raw
    assert "?" not in raw


# ---------------------------------------------------------------------------
# add_select
# ---------------------------------------------------------------------------

def test_add_select_appends():
    qb = QueryBuilder(SQLiteGrammar()).from_("users").select("name")
    qb.add_select("email")
    sql, _ = qb.to_sql()
    assert "name" in sql
    assert "email" in sql


# ---------------------------------------------------------------------------
# insert_or_ignore
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_insert_or_ignore(sqlite_db, ex_tables):
    conn = sqlite_db.connection()
    grammar = conn.grammar
    qb = QueryBuilder(grammar, connection=conn).from_("ex_users")
    result = await qb.insert_or_ignore({"name": "Ignore", "score": 99})
    assert result is True
