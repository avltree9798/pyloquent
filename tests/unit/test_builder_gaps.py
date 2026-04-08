"""Targeted unit tests for remaining uncovered QueryBuilder paths."""
import pytest
from pyloquent.grammars.sqlite_grammar import SQLiteGrammar
from pyloquent.grammars.postgres_grammar import PostgresGrammar
from pyloquent.query.builder import QueryBuilder
from pyloquent.exceptions import QueryException


def qb():
    return QueryBuilder(SQLiteGrammar())


# ---------------------------------------------------------------------------
# select_raw with bindings (line 177)
# ---------------------------------------------------------------------------

def test_select_raw_with_bindings_updates_bindings():
    q = qb().from_("users").select_raw("COALESCE(name, ?) AS n", ["anon"])
    sql, _ = q.to_sql()
    assert "COALESCE" in sql
    # select bindings are tracked separately in _bindings["select"]
    assert "anon" in q._bindings["select"]


# ---------------------------------------------------------------------------
# distinct(*columns) with columns (line 191)
# ---------------------------------------------------------------------------

def test_distinct_with_explicit_columns():
    q = qb().from_("users").distinct("email", "name")
    assert q._distinct is True
    assert q._distinct_on == ["email", "name"]


# ---------------------------------------------------------------------------
# where: operator=None raises ValueError (line 235)
# ---------------------------------------------------------------------------

def test_where_none_operator_raises():
    with pytest.raises(ValueError):
        qb().from_("users").where("id", None, None)


# ---------------------------------------------------------------------------
# or_where_in (line 348)
# ---------------------------------------------------------------------------

def test_or_where_in():
    q = qb().from_("users").where("x", 1).or_where_in("id", [2, 3])
    sql, bindings = q.to_sql()
    assert "OR" in sql.upper()
    assert 2 in bindings


# ---------------------------------------------------------------------------
# or_where_not_in (line 360)
# ---------------------------------------------------------------------------

def test_or_where_not_in():
    q = qb().from_("users").where("x", 1).or_where_not_in("id", [5, 6])
    sql, bindings = q.to_sql()
    assert "NOT IN" in sql.upper()
    assert 5 in bindings


# ---------------------------------------------------------------------------
# or_where_null (line 435)
# ---------------------------------------------------------------------------

def test_or_where_null():
    q = qb().from_("users").where("x", 1).or_where_null("deleted_at")
    sql, _ = q.to_sql()
    assert "IS NULL" in sql.upper()
    assert "OR" in sql.upper()


# ---------------------------------------------------------------------------
# or_where_not_null (line 446)
# ---------------------------------------------------------------------------

def test_or_where_not_null():
    q = qb().from_("users").where("x", 1).or_where_not_null("email")
    sql, _ = q.to_sql()
    assert "IS NOT NULL" in sql.upper()
    assert "OR" in sql.upper()


# ---------------------------------------------------------------------------
# or_where_raw (line 476)
# ---------------------------------------------------------------------------

def test_or_where_raw():
    q = qb().from_("users").where("x", 1).or_where_raw("y = ?", [99])
    sql, bindings = q.to_sql()
    assert "OR" in sql.upper()
    assert 99 in bindings


# ---------------------------------------------------------------------------
# having 2-argument form (lines 898-899)
# ---------------------------------------------------------------------------

def test_having_2_arg_form():
    q = qb().from_("orders").group_by("user_id").having("total", 100)
    sql, bindings = q.to_sql()
    assert "HAVING" in sql.upper()
    assert 100 in bindings


# ---------------------------------------------------------------------------
# first_or_fail without model_class raises QueryException (line 1418)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_first_or_fail_no_model_class_raises_query_exception():
    from unittest.mock import AsyncMock, MagicMock
    conn = MagicMock()
    conn.fetch_one = AsyncMock(return_value=None)
    conn.fetch_all = AsyncMock(return_value=[])
    q = QueryBuilder(SQLiteGrammar(), connection=conn).from_("things")
    with pytest.raises(QueryException):
        await q.first_or_fail()


# ---------------------------------------------------------------------------
# find_or_fail without model_class raises QueryException (line 1451)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_find_or_fail_no_model_class_raises_query_exception():
    from unittest.mock import AsyncMock, MagicMock
    conn = MagicMock()
    conn.fetch_one = AsyncMock(return_value=None)
    conn.fetch_all = AsyncMock(return_value=[])
    q = QueryBuilder(SQLiteGrammar(), connection=conn).from_("things")
    with pytest.raises(QueryException):
        await q.find_or_fail(999)


# ---------------------------------------------------------------------------
# value: returns None when first() is None (line 1494)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_value_returns_none_when_no_results():
    from unittest.mock import AsyncMock, MagicMock
    conn = MagicMock()
    conn.fetch_one = AsyncMock(return_value=None)
    conn.fetch_all = AsyncMock(return_value=[])
    q = QueryBuilder(SQLiteGrammar(), connection=conn).from_("things")
    result = await q.scalar("name")
    assert result is None


# ---------------------------------------------------------------------------
# value: returns dict key when result is dict (line 1496)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_value_returns_dict_key():
    from unittest.mock import AsyncMock, MagicMock
    conn = MagicMock()
    conn.fetch_one = AsyncMock(return_value={"name": "Alice", "id": 1})
    conn.fetch_all = AsyncMock(return_value=[{"name": "Alice", "id": 1}])
    q = QueryBuilder(SQLiteGrammar(), connection=conn).from_("things")
    result = await q.scalar("name")
    assert result == "Alice"


# ---------------------------------------------------------------------------
# upsert: single string unique_by (line 1699)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upsert_string_unique_by():
    from unittest.mock import AsyncMock, MagicMock
    conn = MagicMock()
    conn.execute = AsyncMock(return_value=1)
    q = QueryBuilder(SQLiteGrammar(), connection=conn).from_("users")
    # unique_by as string instead of list (line 1699)
    result = await q.upsert([{"email": "a@b.com", "name": "A"}], "email")
    assert result >= 0


# ---------------------------------------------------------------------------
# upsert: update_columns=None → auto-derives from values (line 1701)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upsert_auto_update_columns():
    from unittest.mock import AsyncMock, MagicMock
    conn = MagicMock()
    conn.execute = AsyncMock(return_value=1)
    q = QueryBuilder(SQLiteGrammar(), connection=conn).from_("users")
    result = await q.upsert([{"email": "x@y.com", "name": "X"}], ["email"])
    assert result >= 0


# ---------------------------------------------------------------------------
# find_many: no model_class → pk defaults to "id" (line 1741)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_find_many_no_model_class_uses_id():
    from unittest.mock import AsyncMock, MagicMock
    conn = MagicMock()
    conn.fetch_all = AsyncMock(return_value=[{"id": 1}])
    q = QueryBuilder(SQLiteGrammar(), connection=conn).from_("users")
    result = await q.find_many([1, 2])
    assert result is not None


# ---------------------------------------------------------------------------
# PostgresGrammar: aliased select columns (lines 60-61)
# ---------------------------------------------------------------------------

def test_postgres_grammar_aliased_select():
    g = PostgresGrammar()
    q = QueryBuilder(g).from_("users").select({"email": "user_email"})
    sql, _ = g.compile_select(q)
    assert "AS" in sql.upper()
    assert "user_email" in sql


# ---------------------------------------------------------------------------
# belongs_to_many _get_pivot_table_name (lines 83-84) and add_constraints (88)
# ---------------------------------------------------------------------------

def test_belongs_to_many_auto_pivot_name():
    """_get_pivot_table_name produces alphabetically sorted underscore-joined name."""
    from pyloquent.orm.relations.belongs_to_many import BelongsToMany

    class FakeParent:
        __class__ = type("ZModel", (), {})()
        __primary_key__ = "id"
        id = 1

    class FakeRelated:
        __name__ = "AModel"
        __primary_key__ = "id"
        __table__ = "amodels"

        @classmethod
        def _get_default_table_name(cls):
            return "amodels"

    parent = FakeParent()
    parent.__class__.__name__ = "ZModel"

    # Directly call _get_pivot_table_name
    rel = object.__new__(BelongsToMany)
    rel.parent = parent
    rel.related = FakeRelated
    name = rel._get_pivot_table_name()
    assert "_" in name
    parts = name.split("_")
    assert parts == sorted(parts)


# ---------------------------------------------------------------------------
# morph_to _create_query fallback (lines 93-95): no _related_class
# ---------------------------------------------------------------------------

def test_morph_to_create_query_fallback_when_no_related_class():
    """When type_value is empty/missing, _related_class is None and _create_query returns a bare QueryBuilder."""
    from pyloquent.orm.relations.morph_to import MorphTo

    class FakeParent:
        id = 1
        commentable_id = None
        commentable_type = None   # empty → _related_class = None

    parent = FakeParent()
    parent.__class__.__name__ = "FakeParent"

    rel = MorphTo(parent, "commentable")
    # _related_class should be None
    assert rel._related_class is None
    # Accessing query triggers _create_query which returns a bare QueryBuilder
    from pyloquent.query.builder import QueryBuilder
    q = rel._create_query()
    assert isinstance(q, QueryBuilder)
