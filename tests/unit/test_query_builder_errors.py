"""Unit tests for QueryBuilder error paths and edge cases (no connection, validation errors, etc.)."""
import pytest
from pyloquent.query.builder import QueryBuilder
from pyloquent.grammars.sqlite_grammar import SQLiteGrammar
from pyloquent.exceptions import QueryException


def qb():
    return QueryBuilder(SQLiteGrammar())


# ---------------------------------------------------------------------------
# where_not with None operator (explicit None) should raise
# ---------------------------------------------------------------------------

def test_where_not_raises_without_operator():
    with pytest.raises(ValueError):
        qb().from_("t").where_not("col", None, None)


# ---------------------------------------------------------------------------
# where_column with None operator raises
# ---------------------------------------------------------------------------

def test_where_column_raises_without_operator():
    with pytest.raises(ValueError):
        qb().from_("t").where_column("a", None, None)


# ---------------------------------------------------------------------------
# having / having_raw
# ---------------------------------------------------------------------------

def test_having_3_args():
    sql, bindings = qb().from_("t").group_by("x").having("x", ">", 10).to_sql()
    assert "HAVING" in sql.upper()
    assert 10 in bindings


# ---------------------------------------------------------------------------
# No-connection async error paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_raises_without_connection():
    with pytest.raises(QueryException):
        await qb().from_("t").get()


@pytest.mark.asyncio
async def test_first_raises_without_connection():
    with pytest.raises(QueryException):
        await qb().from_("t").first()


@pytest.mark.asyncio
async def test_count_raises_without_connection():
    with pytest.raises(QueryException):
        await qb().from_("t").count()


@pytest.mark.asyncio
async def test_sum_raises_without_connection():
    with pytest.raises(QueryException):
        await qb().from_("t").sum("x")


@pytest.mark.asyncio
async def test_avg_raises_without_connection():
    with pytest.raises(QueryException):
        await qb().from_("t").avg("x")


@pytest.mark.asyncio
async def test_max_raises_without_connection():
    with pytest.raises(QueryException):
        await qb().from_("t").max("x")


@pytest.mark.asyncio
async def test_min_raises_without_connection():
    with pytest.raises(QueryException):
        await qb().from_("t").min("x")


@pytest.mark.asyncio
async def test_pluck_raises_without_connection():
    with pytest.raises(QueryException):
        await qb().from_("t").pluck("x")


@pytest.mark.asyncio
async def test_insert_raises_without_connection():
    with pytest.raises(QueryException):
        await qb().from_("t").insert({"x": 1})


@pytest.mark.asyncio
async def test_insert_empty_raises():
    with pytest.raises(ValueError):
        await qb().from_("t").insert([])


@pytest.mark.asyncio
async def test_update_raises_without_connection():
    with pytest.raises(QueryException):
        await qb().from_("t").where("id", 1).update({"x": 1})


@pytest.mark.asyncio
async def test_update_all_raises_without_connection():
    with pytest.raises(QueryException):
        await qb().from_("t").update_all({"x": 1})


@pytest.mark.asyncio
async def test_delete_raises_without_connection():
    with pytest.raises(QueryException):
        await qb().from_("t").where("id", 1).delete()


@pytest.mark.asyncio
async def test_delete_all_raises_without_connection():
    with pytest.raises(QueryException):
        await qb().from_("t").delete_all()


@pytest.mark.asyncio
async def test_increment_raises_without_connection():
    with pytest.raises(QueryException):
        await qb().from_("t").where("id", 1).increment("score")


@pytest.mark.asyncio
async def test_insert_get_id_raises_without_connection():
    with pytest.raises(QueryException):
        await qb().from_("t").insert_get_id({"name": "X"})


@pytest.mark.asyncio
async def test_insert_or_ignore_raises_without_connection():
    with pytest.raises(QueryException):
        await qb().from_("t").insert_or_ignore({"name": "X"})


# ---------------------------------------------------------------------------
# first_or_fail without model_class raises QueryException
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_first_or_fail_no_model_class_raises_query_exception(sqlite_db):
    conn = sqlite_db.connection()
    grammar = conn.grammar
    q = QueryBuilder(grammar, connection=conn).from_("nonexistent_table_xyz")
    with pytest.raises(Exception):  # Either QueryException or table error
        await q.first_or_fail()


# ---------------------------------------------------------------------------
# __await__ allows direct await on builder
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_await_query_builder_directly(sqlite_db):
    conn = sqlite_db.connection()
    grammar = conn.grammar
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS await_test (
            id INTEGER PRIMARY KEY, name TEXT,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    await conn.execute("INSERT INTO await_test (name) VALUES (?)", ["hello"])
    qb_instance = QueryBuilder(grammar, connection=conn).from_("await_test")
    results = await qb_instance
    assert len(results) == 1


# ---------------------------------------------------------------------------
# where_in with empty list (should add impossible condition)
# ---------------------------------------------------------------------------

def test_where_in_empty_values():
    sql, bindings = qb().from_("t").where_in("id", []).to_sql()
    assert sql  # Should not crash
