"""Unit tests covering uncovered QueryBuilder paths."""
import pytest
from pyloquent.query.builder import QueryBuilder
from pyloquent.grammars.sqlite_grammar import SQLiteGrammar


def qb():
    return QueryBuilder(SQLiteGrammar())


# ---------------------------------------------------------------------------
# table() alias for from_()
# ---------------------------------------------------------------------------

def test_table_alias():
    sql, _ = qb().table("users").to_sql()
    assert '"users"' in sql


# ---------------------------------------------------------------------------
# where_not with negated operators
# ---------------------------------------------------------------------------

def test_where_not_equal():
    sql, bindings = qb().from_("users").where_not("status", "active").to_sql()
    assert "!=" in sql or "<>" in sql
    assert bindings == ["active"]


def test_where_not_greater_than():
    sql, bindings = qb().from_("users").where_not("score", ">", 100).to_sql()
    assert "<=" in sql
    assert bindings == [100]


def test_where_not_less_than():
    sql, bindings = qb().from_("users").where_not("score", "<", 10).to_sql()
    assert ">=" in sql


def test_where_not_two_arg_form():
    sql, bindings = qb().from_("t").where_not("x", 5).to_sql()
    assert "!=" in sql or "<>" in sql
    assert bindings == [5]


# ---------------------------------------------------------------------------
# where with dict (array of wheres)
# ---------------------------------------------------------------------------

def test_where_dict_generates_nested_where():
    sql, bindings = qb().from_("users").where({"name": "Alice", "age": 30}).to_sql()
    assert "name" in sql
    assert "age" in sql
    assert "Alice" in bindings
    assert 30 in bindings


# ---------------------------------------------------------------------------
# _where_nested via where() callback
# ---------------------------------------------------------------------------

def test_where_nested_callback():
    sql, bindings = (
        qb().from_("users")
        .where(lambda q: q.where("a", 1).or_where("b", 2))
        .to_sql()
    )
    assert "(" in sql
    assert 1 in bindings
    assert 2 in bindings


# ---------------------------------------------------------------------------
# cross_join
# ---------------------------------------------------------------------------

def test_cross_join():
    sql, _ = qb().from_("a").cross_join("b").to_sql()
    assert "CROSS JOIN" in sql.upper()


# ---------------------------------------------------------------------------
# right_join
# ---------------------------------------------------------------------------

def test_right_join():
    sql, _ = qb().from_("a").right_join("b", "a.id", "=", "b.a_id").to_sql()
    assert "RIGHT" in sql.upper()


# ---------------------------------------------------------------------------
# without_global_scopes (multiple)
# ---------------------------------------------------------------------------

def test_without_global_scopes_removes_all():
    q = qb().from_("users")
    q.with_global_scope("s1", lambda qb: qb.where("active", 1))
    q.with_global_scope("s2", lambda qb: qb.where("deleted", 0))
    q.without_global_scopes(["s1", "s2"])
    sql, bindings = q.to_sql()
    assert bindings == []


# ---------------------------------------------------------------------------
# reorder
# ---------------------------------------------------------------------------

def test_reorder_clears_orders():
    q = qb().from_("users").order_by("name").reorder()
    sql, _ = q.to_sql()
    assert "ORDER BY" not in sql


def test_reorder_with_new_column():
    q = qb().from_("users").order_by("name").reorder("score", "desc")
    sql, _ = q.to_sql()
    assert "score" in sql.lower()
    assert "desc" in sql.lower()


# ---------------------------------------------------------------------------
# clone
# ---------------------------------------------------------------------------

def test_clone_is_independent():
    q1 = qb().from_("users").where("a", 1)
    q2 = q1.clone()
    q2.where("b", 2)
    sql1, b1 = q1.to_sql()
    sql2, b2 = q2.to_sql()
    assert "b" not in sql1
    assert "b" in sql2


# ---------------------------------------------------------------------------
# or_has / or_doesnt_have / or_where_has
# ---------------------------------------------------------------------------

def test_or_has_produces_sql():
    q = qb().from_("users")
    q.or_has("posts")
    sql, _ = q.to_sql()
    assert sql  # should not throw


def test_or_doesnt_have_produces_sql():
    q = qb().from_("users")
    q.or_doesnt_have("posts")
    sql, _ = q.to_sql()
    assert sql


def test_or_where_has_produces_sql():
    q = qb().from_("users")
    q.or_where_has("posts", lambda sub: sub.where("published", 1))
    sql, _ = q.to_sql()
    assert sql


# ---------------------------------------------------------------------------
# join 3-arg form (implied =)
# ---------------------------------------------------------------------------

def test_join_3_arg_form():
    sql, _ = qb().from_("a").join("b", "a.id", "b.a_id").to_sql()
    assert "JOIN" in sql.upper()
    assert "a_id" in sql


# ---------------------------------------------------------------------------
# where_column 3-arg form
# ---------------------------------------------------------------------------

def test_where_column_3_arg():
    sql, _ = qb().from_("t").where_column("a", "=", "b").to_sql()
    assert '"a"' in sql
    assert '"b"' in sql


def test_where_column_2_arg_implied_eq():
    sql, _ = qb().from_("t").where_column("a", "b").to_sql()
    assert '"a"' in sql
    assert '"b"' in sql


# ---------------------------------------------------------------------------
# with_ eager load (adds to _eager_loads)
# ---------------------------------------------------------------------------

def test_with_adds_eager_loads():
    q = qb().from_("users").with_("posts", "comments")
    assert "posts" in q._eager_loads
    assert "comments" in q._eager_loads


# ---------------------------------------------------------------------------
# Pagination: page/paginate to_sql shape
# ---------------------------------------------------------------------------

def test_paginate_sql_has_limit_offset():
    q = qb().from_("users").limit(10).offset(20)
    sql, _ = q.to_sql()
    assert "LIMIT" in sql.upper()
    assert "OFFSET" in sql.upper()


# ---------------------------------------------------------------------------
# _hydrate_models without model_class returns raw dicts
# ---------------------------------------------------------------------------

def test_hydrate_models_no_model_class():
    q = QueryBuilder(SQLiteGrammar())
    from pyloquent.orm.collection import Collection
    result = q._hydrate_models([{"id": 1, "name": "Alice"}])
    assert isinstance(result, Collection)
    assert result[0] == {"id": 1, "name": "Alice"}


# ---------------------------------------------------------------------------
# where_not with unknown operator falls back to NOT
# ---------------------------------------------------------------------------

def test_where_not_unknown_operator():
    sql, _ = qb().from_("t").where_not("col", "LIKE", "%foo%").to_sql()
    assert "NOT LIKE" in sql.upper()
