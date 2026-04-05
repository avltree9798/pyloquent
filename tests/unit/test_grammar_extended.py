"""Extended tests for Grammar – new compilation methods."""

import pytest

from pyloquent.grammars.grammar import Grammar
from pyloquent.grammars.sqlite_grammar import SQLiteGrammar
from pyloquent.query.builder import QueryBuilder
from pyloquent.query.expression import WhereClause


# ---------------------------------------------------------------------------
# Helper: minimal non-SQLite grammar (FOR UPDATE / FOR SHARE passthrough)
# ---------------------------------------------------------------------------

class _PgGrammar(Grammar):
    """Minimal grammar that returns FOR UPDATE / FOR SHARE."""

    def _wrap_value(self, value: str) -> str:
        return f'"{value}"'

    def _parameter(self, value) -> str:
        return "?"


# ---------------------------------------------------------------------------
# compile_increment
# ---------------------------------------------------------------------------

class TestCompileIncrement:
    def test_basic_no_where(self):
        g = SQLiteGrammar()
        b = QueryBuilder(g).from_("posts")
        sql, bindings = g.compile_increment(b, "views", 1, {})
        assert 'UPDATE "posts" SET "views" = "views" + ?' in sql
        assert bindings == [1]
        assert "WHERE" not in sql

    def test_with_where(self):
        g = SQLiteGrammar()
        b = QueryBuilder(g).from_("posts").where("id", 5)
        sql, bindings = g.compile_increment(b, "views", 2, {})
        assert '"views" = "views" + ?' in sql
        assert 'WHERE "id" = ?' in sql
        assert bindings == [2, 5]

    def test_with_extra_columns(self):
        g = SQLiteGrammar()
        b = QueryBuilder(g).from_("posts").where("id", 1)
        sql, bindings = g.compile_increment(b, "views", 1, {"updated_at": "2024-01-01"})
        assert '"updated_at" = ?' in sql
        assert "2024-01-01" in bindings

    def test_decrement_uses_negative_amount(self):
        g = SQLiteGrammar()
        b = QueryBuilder(g).from_("posts")
        sql, bindings = g.compile_increment(b, "stock", -3, {})
        assert '"stock" = "stock" + ?' in sql
        assert bindings == [-3]


# ---------------------------------------------------------------------------
# compile_insert_or_ignore
# ---------------------------------------------------------------------------

class TestCompileInsertOrIgnore:
    def test_sqlite_keyword(self):
        g = SQLiteGrammar()
        b = QueryBuilder(g).from_("tags")
        sql, bindings = g.compile_insert_or_ignore(b, [{"name": "python"}])
        assert sql.startswith("INSERT OR IGNORE INTO")
        assert "python" in bindings

    def test_multiple_rows(self):
        g = SQLiteGrammar()
        b = QueryBuilder(g).from_("tags")
        sql, bindings = g.compile_insert_or_ignore(b, [{"name": "a"}, {"name": "b"}])
        assert sql.count("?") == 2


# ---------------------------------------------------------------------------
# compile_upsert
# ---------------------------------------------------------------------------

class TestCompileUpsert:
    def test_on_conflict_do_update(self):
        g = SQLiteGrammar()
        b = QueryBuilder(g).from_("users")
        sql, bindings = g.compile_upsert(
            b,
            [{"email": "a@b.com", "name": "Alice"}],
            ["email"],
            ["name"],
        )
        assert "ON CONFLICT" in sql
        assert "DO UPDATE SET" in sql
        assert '"name" = excluded."name"' in sql

    def test_multiple_unique_columns(self):
        g = SQLiteGrammar()
        b = QueryBuilder(g).from_("items")
        sql, bindings = g.compile_upsert(
            b,
            [{"a": 1, "b": 2, "c": 3}],
            ["a", "b"],
            ["c"],
        )
        assert '"a"' in sql
        assert '"b"' in sql

    def test_multiple_update_columns(self):
        g = SQLiteGrammar()
        b = QueryBuilder(g).from_("items")
        sql, _ = g.compile_upsert(
            b,
            [{"key": "x", "v1": 1, "v2": 2}],
            ["key"],
            ["v1", "v2"],
        )
        assert '"v1" = excluded."v1"' in sql
        assert '"v2" = excluded."v2"' in sql


# ---------------------------------------------------------------------------
# _compile_lock
# ---------------------------------------------------------------------------

class TestCompileLock:
    def test_for_update_non_sqlite(self):
        g = _PgGrammar()
        b = QueryBuilder(g).from_("users").lock_for_update()
        sql, _ = g.compile_select(b)
        assert "FOR UPDATE" in sql

    def test_for_share_non_sqlite(self):
        g = _PgGrammar()
        b = QueryBuilder(g).from_("users").for_share()
        sql, _ = g.compile_select(b)
        assert "FOR SHARE" in sql

    def test_no_lock_no_clause(self):
        g = _PgGrammar()
        b = QueryBuilder(g).from_("users")
        sql, _ = g.compile_select(b)
        assert "FOR UPDATE" not in sql
        assert "FOR SHARE" not in sql

    def test_sqlite_lock_for_update_is_empty(self):
        g = SQLiteGrammar()
        b = QueryBuilder(g).from_("users").lock_for_update()
        sql, _ = g.compile_select(b)
        assert "FOR UPDATE" not in sql

    def test_sqlite_for_share_is_empty(self):
        g = SQLiteGrammar()
        b = QueryBuilder(g).from_("users").for_share()
        sql, _ = g.compile_select(b)
        assert "FOR SHARE" not in sql


# ---------------------------------------------------------------------------
# WHERE EXISTS / WHERE NOT EXISTS
# ---------------------------------------------------------------------------

class TestWhereExistsCompilation:
    def _make_outer_with_exists(self, type_: str) -> QueryBuilder:
        g = SQLiteGrammar()
        outer = QueryBuilder(g).from_("users")
        inner = QueryBuilder(g).from_("orders").where_raw('"orders"."user_id" = "users"."id"')
        outer._wheres.append(
            WhereClause(column="", boolean="and", type=type_, query=inner)
        )
        return outer

    def test_exists_clause(self):
        outer = self._make_outer_with_exists("exists")
        sql, _ = outer.grammar.compile_select(outer)
        assert "EXISTS (" in sql
        assert "NOT EXISTS" not in sql

    def test_not_exists_clause(self):
        outer = self._make_outer_with_exists("not_exists")
        sql, _ = outer.grammar.compile_select(outer)
        assert "NOT EXISTS (" in sql

    def test_exists_includes_subquery_bindings(self):
        g = SQLiteGrammar()
        outer = QueryBuilder(g).from_("users")
        inner = QueryBuilder(g).from_("orders").where("status", "active")
        outer._wheres.append(
            WhereClause(column="", boolean="and", type="exists", query=inner)
        )
        sql, bindings = g.compile_select(outer)
        assert "active" in bindings

    def test_where_builder_method_adds_type(self):
        g = SQLiteGrammar()
        builder = QueryBuilder(g).from_("users")
        builder.where_exists(lambda q: q.from_("orders"))
        assert builder._wheres[0].type == "exists"

    def test_where_not_exists_builder_method(self):
        g = SQLiteGrammar()
        builder = QueryBuilder(g).from_("users")
        builder.where_not_exists(lambda q: q.from_("orders"))
        assert builder._wheres[0].type == "not_exists"
