"""Unit tests targeting uncovered lines across core modules."""

from __future__ import annotations

import asyncio
from typing import Any, Optional
from unittest.mock import patch

import pytest

from pyloquent.grammars.mysql_grammar import MySQLGrammar
from pyloquent.grammars.postgres_grammar import PostgresGrammar
from pyloquent.grammars.sqlite_grammar import SQLiteGrammar
from pyloquent.orm.hybrid_property import hybrid_property
from pyloquent.orm.identity_map import IdentityMap
from pyloquent.orm.type_decorator import (
    CommaSeparatedType,
    JSONType,
    TypeDecorator,
    get_type,
)
from pyloquent.query.builder import QueryBuilder
from pyloquent.query.expression import OrderClause, RawExpression


# ---------------------------------------------------------------------------
# type_decorator — uncovered paths
# ---------------------------------------------------------------------------

class _DummyDecorator(TypeDecorator):
    impl = "TEXT"


def test_get_type_with_instance():
    """get_type(instance) → returns the same instance (line 69)."""
    inst = JSONType()
    result = get_type(inst)
    assert result is inst


def test_get_type_with_subclass():
    """get_type(SubClass) → instantiates and returns it (line 72)."""
    result = get_type(_DummyDecorator)
    assert isinstance(result, _DummyDecorator)


def test_get_type_unknown_string():
    """get_type('unknown_xyz') → returns None via registry miss (line 67)."""
    result = get_type("unknown_xyz_not_registered")
    assert result is None


def test_get_type_returns_none_for_non_decorator():
    """get_type with a non-string, non-TypeDecorator object → None (line 72)."""
    result = get_type(42)
    assert result is None


def test_base_decorator_passthrough():
    """Base TypeDecorator.process_bind_param and process_result_value are passthroughs (lines 102, 116)."""
    d = _DummyDecorator()
    assert d.process_bind_param("hello") == "hello"
    assert d.process_result_value(42) == 42


def test_json_type_none_bind():
    """JSONType.process_bind_param(None) → None (line 143)."""
    j = JSONType()
    assert j.process_bind_param(None) is None


def test_json_type_none_result():
    """JSONType.process_result_value(None) → None (line 160)."""
    j = JSONType()
    assert j.process_result_value(None) is None


def test_json_type_dict_result():
    """JSONType.process_result_value on already-dict value returns it (line 164)."""
    j = JSONType()
    d = {"x": 1}
    assert j.process_result_value(d) is d


def test_comma_separated_none_bind():
    """CommaSeparatedType.process_bind_param(None) → None (line 183)."""
    c = CommaSeparatedType()
    assert c.process_bind_param(None) is None


def test_comma_separated_non_list_bind():
    """CommaSeparatedType.process_bind_param with a plain string returns it (line 186)."""
    c = CommaSeparatedType()
    assert c.process_bind_param("already,csv") == "already,csv"


def test_comma_separated_none_result():
    """CommaSeparatedType.process_result_value(None) → None (line 199)."""
    c = CommaSeparatedType()
    assert c.process_result_value(None) is None


def test_comma_separated_non_string_result():
    """CommaSeparatedType.process_result_value with a list returns it as-is (line 202)."""
    c = CommaSeparatedType()
    existing = ["a", "b"]
    assert c.process_result_value(existing) is existing


# ---------------------------------------------------------------------------
# grammar — line 291 (_compile_ctes called directly with empty ctes)
# ---------------------------------------------------------------------------

def test_compile_ctes_empty():
    """_compile_ctes returns ('', []) when query has no CTEs (line 291)."""
    g = SQLiteGrammar()
    qb = QueryBuilder(g).from_("users")
    # Call directly — compile_select skips the call when ctes is empty
    sql, bindings = g._compile_ctes(qb)
    assert sql == ""
    assert bindings == []


# ---------------------------------------------------------------------------
# grammar — line 341 (window expression fallback order_by item)
# ---------------------------------------------------------------------------

def test_compile_window_non_order_clause():
    """compile_window_expression with a raw-string order_by item hits str() fallback (line 341)."""
    g = SQLiteGrammar()

    class _RawOrder:
        """Non-OrderClause order item — falls to str() branch."""
        def __str__(self):
            return "score DESC"

    sql, _ = g.compile_window_expression(
        function="ROW_NUMBER",
        args=[],
        partition_by=None,
        order_by=[_RawOrder()],
        frame=None,
        alias="rn",
    )
    assert "score DESC" in sql


# ---------------------------------------------------------------------------
# sqlite_grammar — line 128 (compile_index_exists)
# ---------------------------------------------------------------------------

def test_sqlite_compile_index_exists():
    """compile_index_exists returns correct SQL (line 128)."""
    g = SQLiteGrammar()
    sql, bindings = g.compile_index_exists("users", ["email"])
    assert "sqlite_master" in sql
    assert bindings == ["users"]


# ---------------------------------------------------------------------------
# mysql_grammar — schema reflection methods (lines 119, 135, 154, 166, 180, 197, 212)
# ---------------------------------------------------------------------------

def test_mysql_compile_table_exists():
    sql, b = MySQLGrammar().compile_table_exists("users")
    assert "information_schema" in sql
    assert b == ["users"]


def test_mysql_compile_column_exists():
    sql, b = MySQLGrammar().compile_column_exists("users", "email")
    assert "information_schema" in sql
    assert b == ["users", "email"]


def test_mysql_compile_index_exists():
    sql, b = MySQLGrammar().compile_index_exists("users", ["email"])
    assert "statistics" in sql
    assert b == ["users"]


def test_mysql_compile_get_tables():
    sql = MySQLGrammar().compile_get_tables()
    assert "information_schema" in sql


def test_mysql_compile_get_columns():
    sql, b = MySQLGrammar().compile_get_columns("users")
    assert "information_schema" in sql
    assert b == ["users"]


def test_mysql_compile_get_indexes():
    sql, b = MySQLGrammar().compile_get_indexes("users")
    assert "statistics" in sql
    assert b == ["users"]


def test_mysql_compile_get_foreign_keys():
    sql, b = MySQLGrammar().compile_get_foreign_keys("users")
    assert "key_column_usage" in sql
    assert b == ["users"]


# ---------------------------------------------------------------------------
# postgres_grammar — schema reflection methods (lines 150, 169, 181)
# ---------------------------------------------------------------------------

def test_postgres_compile_column_exists():
    sql, b = PostgresGrammar().compile_column_exists("users", "email")
    assert "information_schema" in sql
    assert b == ["users", "email"]


def test_postgres_compile_index_exists():
    sql, b = PostgresGrammar().compile_index_exists("users", ["email"])
    assert "pg_indexes" in sql
    assert b == ["users"]


def test_postgres_compile_get_tables():
    sql = PostgresGrammar().compile_get_tables()
    assert "information_schema" in sql


# ---------------------------------------------------------------------------
# hybrid_property — line 86 (regular function expression, not classmethod)
# ---------------------------------------------------------------------------

def test_hybrid_property_regular_function_expression():
    """expression() with a plain function (not classmethod) stores it directly (line 86)."""
    hp = hybrid_property(lambda self: self)

    def expr_fn(cls):
        return RawExpression("1 + 1")

    returned = hp.expression(expr_fn)
    assert returned is hp
    assert hp._expr is expr_fn


# ---------------------------------------------------------------------------
# identity_map — line 102 (get_or_register with model instance, not dict)
# ---------------------------------------------------------------------------

def test_identity_map_get_or_register_with_instance():
    """get_or_register accepts a pre-built model instance (line 102)."""
    imap = IdentityMap()

    class _FakeModel:
        pass

    instance = _FakeModel()
    result = imap.get_or_register(_FakeModel, 1, instance)
    assert result is instance
    assert imap.get(_FakeModel, 1) is instance


# ---------------------------------------------------------------------------
# builder — line 939 (select_window with OrderClause object in order_by)
# ---------------------------------------------------------------------------

def test_select_window_with_order_clause_object():
    """select_window with an OrderClause object in order_by uses the OC branch (line 939)."""
    g = SQLiteGrammar()
    oc = OrderClause(column="score", direction="desc")
    sql, _ = (
        QueryBuilder(g)
        .from_("users")
        .select_window("ROW_NUMBER", order_by=[oc], alias="rn")
        .to_sql()
    )
    assert "ROW_NUMBER" in sql
    assert "score" in sql


# ---------------------------------------------------------------------------
# builder — line 2457 (_cast_row with no model_class)
# ---------------------------------------------------------------------------

def test_cast_row_no_model_class():
    """_cast_row returns the row unchanged when no model_class is set (line 2457)."""
    qb = QueryBuilder(SQLiteGrammar())
    row = {"a": 1, "b": "hello"}
    result = qb._cast_row(row)
    assert result is row


# ---------------------------------------------------------------------------
# builder — _cast_row when model has no __casts__
# ---------------------------------------------------------------------------

def test_cast_row_no_casts():
    """_cast_row returns the row unchanged when model has no __casts__ (early return)."""
    from pyloquent.orm.model import Model

    class NoCastModel(Model):
        __table__ = "nc"
        __timestamps__ = False
        id: Optional[int] = None

    qb = QueryBuilder(SQLiteGrammar(), model_class=NoCastModel)
    row = {"id": 1}
    result = qb._cast_row(row)
    assert result == row


# ---------------------------------------------------------------------------
# sync — run_sync inside a running event loop (lines 72-75)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_sync_inside_running_loop():
    """run_sync uses ThreadPoolExecutor when called from a running loop (lines 72-75)."""
    from pyloquent.sync import run_sync

    async def _coro():
        return 42

    result = run_sync(_coro())
    assert result == 42


# ---------------------------------------------------------------------------
# sync — SyncQueryProxy.__getattr__ async path (line 210) + plain return (line 216)
# ---------------------------------------------------------------------------

def test_sync_proxy_getattr_async_method():
    """Calling an async QB method not in the explicit list goes through __getattr__
    and returns run_sync(result) (line 210)."""
    from pyloquent.sync import SyncConnectionManager, run_sync

    with SyncConnectionManager({"default": {"driver": "sqlite", "database": ":memory:"}}) as mgr:
        conn = mgr._manager.connection()
        run_sync(conn.execute("CREATE TABLE _async_t (id INTEGER PRIMARY KEY, v INTEGER)"))
        run_sync(conn.execute("INSERT INTO _async_t VALUES (1, 10)"))
        run_sync(conn.execute("INSERT INTO _async_t VALUES (2, 20)"))

        proxy = mgr.table("_async_t")
        # max() is async on QueryBuilder and not explicitly defined on SyncQueryProxy
        result = proxy.max("v")
        assert result == 20


def test_sync_proxy_getattr_non_qb_return():
    """A QB method that returns a plain value (not coroutine, not QB) hits line 216."""
    from pyloquent.sync import SyncConnectionManager
    from pyloquent.grammars.sqlite_grammar import SQLiteGrammar

    with SyncConnectionManager({"default": {"driver": "sqlite", "database": ":memory:"}}) as mgr:
        proxy = mgr.table("_nonqb")
        # to_sql() returns a (str, list) tuple — not a coroutine or QueryBuilder
        sql_result = proxy.to_sql()
        assert isinstance(sql_result, tuple)
