"""Extended unit tests for QueryBuilder new methods (no DB required)."""

import pytest

from pyloquent.grammars.sqlite_grammar import SQLiteGrammar
from pyloquent.query.builder import QueryBuilder
from pyloquent.query.expression import WhereClause


# ---------------------------------------------------------------------------
# Locking
# ---------------------------------------------------------------------------

class TestLocking:
    def test_lock_for_update(self):
        b = QueryBuilder(SQLiteGrammar()).from_("users").lock_for_update()
        assert b._lock == "for update"

    def test_for_share(self):
        b = QueryBuilder(SQLiteGrammar()).from_("users").for_share()
        assert b._lock == "for share"

    def test_lock_default_is_none(self):
        b = QueryBuilder(SQLiteGrammar()).from_("users")
        assert b._lock is None

    def test_lock_preserved_in_clone(self):
        b = QueryBuilder(SQLiteGrammar()).from_("users").lock_for_update()
        c = b.clone()
        assert c._lock == "for update"

    def test_lock_for_update_returns_self(self):
        b = QueryBuilder(SQLiteGrammar()).from_("users")
        assert b.lock_for_update() is b

    def test_for_share_returns_self(self):
        b = QueryBuilder(SQLiteGrammar()).from_("users")
        assert b.for_share() is b


# ---------------------------------------------------------------------------
# Conditional: when / unless / tap
# ---------------------------------------------------------------------------

class TestWhen:
    def test_truthy_applies_callback(self):
        b = QueryBuilder(SQLiteGrammar()).from_("users")
        result = b.when(True, lambda q: q.where("active", 1))
        assert result is b
        assert len(b._wheres) == 1
        assert b._wheres[0].value == 1

    def test_falsy_skips_callback(self):
        b = QueryBuilder(SQLiteGrammar()).from_("users")
        b.when(False, lambda q: q.where("active", 1))
        assert len(b._wheres) == 0

    def test_falsy_with_default_applies_default(self):
        b = QueryBuilder(SQLiteGrammar()).from_("users")
        b.when(False, lambda q: q.where("active", 1), lambda q: q.where("active", 0))
        assert b._wheres[0].value == 0

    def test_truthy_ignores_default(self):
        b = QueryBuilder(SQLiteGrammar()).from_("users")
        b.when(True, lambda q: q.where("active", 1), lambda q: q.where("active", 0))
        assert b._wheres[0].value == 1

    def test_condition_zero_is_falsy(self):
        b = QueryBuilder(SQLiteGrammar()).from_("users")
        b.when(0, lambda q: q.where("active", 1))
        assert len(b._wheres) == 0

    def test_condition_empty_string_is_falsy(self):
        b = QueryBuilder(SQLiteGrammar()).from_("users")
        b.when("", lambda q: q.where("active", 1))
        assert len(b._wheres) == 0


class TestUnless:
    def test_falsy_applies_callback(self):
        b = QueryBuilder(SQLiteGrammar()).from_("users")
        b.unless(False, lambda q: q.where("active", 1))
        assert len(b._wheres) == 1

    def test_truthy_skips_callback(self):
        b = QueryBuilder(SQLiteGrammar()).from_("users")
        b.unless(True, lambda q: q.where("active", 1))
        assert len(b._wheres) == 0

    def test_truthy_with_default(self):
        b = QueryBuilder(SQLiteGrammar()).from_("users")
        b.unless(True, lambda q: q.where("active", 1), lambda q: q.where("active", 0))
        assert b._wheres[0].value == 0


class TestTap:
    def test_tap_calls_callback_and_returns_self(self):
        seen = []
        b = QueryBuilder(SQLiteGrammar()).from_("orders")
        result = b.tap(lambda q: seen.append(q._table))
        assert result is b
        assert seen == ["orders"]

    def test_tap_does_not_modify_query(self):
        b = QueryBuilder(SQLiteGrammar()).from_("orders")
        b.tap(lambda q: None)
        assert len(b._wheres) == 0


# ---------------------------------------------------------------------------
# WHERE EXISTS / NOT EXISTS (builder side)
# ---------------------------------------------------------------------------

class TestWhereExists:
    def test_where_exists_adds_clause(self):
        b = QueryBuilder(SQLiteGrammar()).from_("users")
        b.where_exists(lambda q: q.from_("orders"))
        assert len(b._wheres) == 1
        assert b._wheres[0].type == "exists"

    def test_where_exists_returns_self(self):
        b = QueryBuilder(SQLiteGrammar()).from_("users")
        result = b.where_exists(lambda q: q.from_("orders"))
        assert result is b

    def test_where_not_exists_adds_clause(self):
        b = QueryBuilder(SQLiteGrammar()).from_("users")
        b.where_not_exists(lambda q: q.from_("orders"))
        assert b._wheres[0].type == "not_exists"

    def test_where_not_exists_returns_self(self):
        b = QueryBuilder(SQLiteGrammar()).from_("users")
        result = b.where_not_exists(lambda q: q.from_("orders"))
        assert result is b

    def test_subquery_receives_fresh_builder(self):
        captured = []
        QueryBuilder(SQLiteGrammar()).from_("users").where_exists(
            lambda q: captured.append(q) or q.from_("x")
        )
        assert len(captured) == 1
        assert isinstance(captured[0], QueryBuilder)


# ---------------------------------------------------------------------------
# to_raw_sql
# ---------------------------------------------------------------------------

class TestToRawSql:
    def test_string_binding_quoted(self):
        b = QueryBuilder(SQLiteGrammar()).from_("users").where("name", "Alice")
        raw = b.to_raw_sql()
        assert "'Alice'" in raw
        assert "?" not in raw

    def test_int_binding_unquoted(self):
        b = QueryBuilder(SQLiteGrammar()).from_("users").where("id", 42)
        raw = b.to_raw_sql()
        assert "42" in raw
        assert "?" not in raw

    def test_bool_true_becomes_1(self):
        b = QueryBuilder(SQLiteGrammar()).from_("users").where("active", True)
        raw = b.to_raw_sql()
        assert "1" in raw

    def test_bool_false_becomes_0(self):
        b = QueryBuilder(SQLiteGrammar()).from_("users").where("active", False)
        raw = b.to_raw_sql()
        assert "0" in raw

    def test_float_binding(self):
        b = QueryBuilder(SQLiteGrammar()).from_("items").where("price", 3.14)
        raw = b.to_raw_sql()
        assert "3.14" in raw

    def test_none_binding_becomes_null(self):
        g = SQLiteGrammar()
        b = QueryBuilder(g).from_("t")
        b._wheres.append(
            WhereClause(column="x", operator="=", value=None, type="basic", boolean="and")
        )
        raw = b.to_raw_sql()
        assert "NULL" in raw

    def test_no_bindings(self):
        b = QueryBuilder(SQLiteGrammar()).from_("users")
        raw = b.to_raw_sql()
        assert "?" not in raw


# ---------------------------------------------------------------------------
# find_many (builder method, no DB)
# ---------------------------------------------------------------------------

class TestFindMany:
    def test_adds_where_in(self):
        # find_many is async+DB; verify the underlying where_in SQL shape it uses
        b = QueryBuilder(SQLiteGrammar()).from_("users").where_in("id", [1, 2, 3])
        sql, bindings = b.to_sql()
        assert "IN" in sql
        assert bindings == [1, 2, 3]


# ---------------------------------------------------------------------------
# Clause-building SQL output
# ---------------------------------------------------------------------------

class TestWhereColumn:
    def test_basic(self):
        b = QueryBuilder(SQLiteGrammar()).from_("orders").where_column("price", ">=", "min_price")
        sql, bindings = b.to_sql()
        assert '"price"' in sql
        assert '"min_price"' in sql
        assert bindings == []


class TestWhereBetween:
    def test_between(self):
        b = QueryBuilder(SQLiteGrammar()).from_("orders").where_between("amount", [10, 100])
        sql, bindings = b.to_sql()
        assert "BETWEEN" in sql
        assert bindings == [10, 100]

    def test_not_between(self):
        b = QueryBuilder(SQLiteGrammar()).from_("orders").where_not_between("amount", [10, 100])
        sql, bindings = b.to_sql()
        assert "NOT BETWEEN" in sql
        assert bindings == [10, 100]


class TestWhereNotIn:
    def test_where_not_in_sql(self):
        b = QueryBuilder(SQLiteGrammar()).from_("users").where_not_in("id", [1, 2])
        sql, bindings = b.to_sql()
        assert "NOT IN" in sql
        assert bindings == [1, 2]


class TestWhereNotNull:
    def test_where_not_null(self):
        b = QueryBuilder(SQLiteGrammar()).from_("users").where_not_null("email")
        sql, _ = b.to_sql()
        assert "IS NOT NULL" in sql


class TestLatestOldest:
    def test_latest(self):
        b = QueryBuilder(SQLiteGrammar()).from_("posts").latest()
        sql, _ = b.to_sql()
        assert "DESC" in sql

    def test_oldest(self):
        b = QueryBuilder(SQLiteGrammar()).from_("posts").oldest()
        sql, _ = b.to_sql()
        assert "ASC" in sql

    def test_latest_custom_column(self):
        b = QueryBuilder(SQLiteGrammar()).from_("posts").latest("published_at")
        sql, _ = b.to_sql()
        assert '"published_at"' in sql


class TestSelectRaw:
    def test_select_raw(self):
        b = QueryBuilder(SQLiteGrammar()).from_("orders").select_raw("COUNT(*) as total")
        sql, _ = b.to_sql()
        assert "COUNT(*) as total" in sql


class TestWhereRaw:
    def test_where_raw(self):
        b = QueryBuilder(SQLiteGrammar()).from_("users").where_raw("id = ?", [99])
        sql, bindings = b.to_sql()
        assert "id = ?" in sql
        assert bindings == [99]


class TestRightJoin:
    def test_right_join_type(self):
        b = (
            QueryBuilder(SQLiteGrammar())
            .from_("users")
            .right_join("posts", "users.id", "=", "posts.user_id")
        )
        assert b._joins[0].type == "right"


class TestAddSelect:
    def test_add_select_appends(self):
        b = QueryBuilder(SQLiteGrammar()).from_("users").select("id").add_select("name")
        assert "name" in b._selects
