"""Tests for SQL grammar compilation."""

import pytest

from pyloquent.grammars import MySQLGrammar, PostgresGrammar, SQLiteGrammar
from pyloquent.query.builder import QueryBuilder


class TestSQLiteGrammar:
    """Test SQLite grammar compilation."""

    def test_simple_select(self):
        """Test basic SELECT compilation."""
        grammar = SQLiteGrammar()
        builder = QueryBuilder(grammar).from_("users")
        sql, bindings = builder.to_sql()

        assert sql == 'SELECT * FROM "users"'
        assert bindings == []

    def test_select_columns(self):
        """Test SELECT with specific columns."""
        grammar = SQLiteGrammar()
        builder = QueryBuilder(grammar).from_("users").select("id", "name", "email")
        sql, bindings = builder.to_sql()

        assert sql == 'SELECT "id", "name", "email" FROM "users"'
        assert bindings == []

    def test_where_basic(self):
        """Test basic WHERE clause."""
        grammar = SQLiteGrammar()
        builder = QueryBuilder(grammar).from_("users").where("id", 1)
        sql, bindings = builder.to_sql()

        assert sql == 'SELECT * FROM "users" WHERE "id" = ?'
        assert bindings == [1]

    def test_where_with_operator(self):
        """Test WHERE with explicit operator."""
        grammar = SQLiteGrammar()
        builder = QueryBuilder(grammar).from_("users").where("age", ">", 18)
        sql, bindings = builder.to_sql()

        assert sql == 'SELECT * FROM "users" WHERE "age" > ?'
        assert bindings == [18]

    def test_multiple_wheres(self):
        """Test multiple WHERE clauses."""
        grammar = SQLiteGrammar()
        builder = QueryBuilder(grammar).from_("users").where("age", ">", 18).where("active", True)
        sql, bindings = builder.to_sql()

        assert sql == 'SELECT * FROM "users" WHERE "age" > ? AND "active" = ?'
        assert bindings == [18, True]

    def test_where_in(self):
        """Test WHERE IN clause."""
        grammar = SQLiteGrammar()
        builder = QueryBuilder(grammar).from_("users").where_in("id", [1, 2, 3])
        sql, bindings = builder.to_sql()

        assert sql == 'SELECT * FROM "users" WHERE "id" IN (?, ?, ?)'
        assert bindings == [1, 2, 3]

    def test_where_null(self):
        """Test WHERE NULL clause."""
        grammar = SQLiteGrammar()
        builder = QueryBuilder(grammar).from_("users").where_null("deleted_at")
        sql, bindings = builder.to_sql()

        assert sql == 'SELECT * FROM "users" WHERE "deleted_at" IS NULL'
        assert bindings == []

    def test_order_by(self):
        """Test ORDER BY clause."""
        grammar = SQLiteGrammar()
        builder = QueryBuilder(grammar).from_("users").order_by("name", "asc")
        sql, bindings = builder.to_sql()

        assert sql == 'SELECT * FROM "users" ORDER BY "name" ASC'
        assert bindings == []

    def test_limit_and_offset(self):
        """Test LIMIT and OFFSET."""
        grammar = SQLiteGrammar()
        builder = QueryBuilder(grammar).from_("users").limit(10).offset(20)
        sql, bindings = builder.to_sql()

        assert sql == 'SELECT * FROM "users" LIMIT 10 OFFSET 20'
        assert bindings == []

    def test_join(self):
        """Test JOIN clause."""
        grammar = SQLiteGrammar()
        builder = (
            QueryBuilder(grammar).from_("users").join("posts", "users.id", "=", "posts.user_id")
        )
        sql, bindings = builder.to_sql()

        assert 'JOIN "posts" ON "users"."id" = "posts"."user_id"' in sql

    def test_left_join(self):
        """Test LEFT JOIN clause."""
        grammar = SQLiteGrammar()
        builder = (
            QueryBuilder(grammar)
            .from_("users")
            .left_join("posts", "users.id", "=", "posts.user_id")
        )
        sql, bindings = builder.to_sql()

        assert 'LEFT JOIN "posts" ON "users"."id" = "posts"."user_id"' in sql

    def test_group_by(self):
        """Test GROUP BY clause."""
        grammar = SQLiteGrammar()
        builder = QueryBuilder(grammar).from_("users").group_by("department")
        sql, bindings = builder.to_sql()

        assert 'GROUP BY "department"' in sql

    def test_having(self):
        """Test HAVING clause."""
        grammar = SQLiteGrammar()
        builder = (
            QueryBuilder(grammar).from_("users").group_by("department").having("COUNT(*)", ">", 5)
        )
        sql, bindings = builder.to_sql()

        assert 'HAVING "COUNT(*)" > ?' in sql
        assert bindings == [5]


class TestMySQLGrammar:
    """Test MySQL grammar compilation."""

    def test_wrap_value(self):
        """Test that MySQL uses backticks."""
        grammar = MySQLGrammar()
        wrapped = grammar._wrap_value("users")

        assert wrapped == "`users`"

    def test_parameter(self):
        """Test that MySQL uses %s for parameters."""
        grammar = MySQLGrammar()
        param = grammar._parameter("value")

        assert param == "%s"


class TestPostgresGrammar:
    """Test PostgreSQL grammar compilation."""

    def test_wrap_value(self):
        """Test that PostgreSQL uses double quotes."""
        grammar = PostgresGrammar()
        wrapped = grammar._wrap_value("users")

        assert wrapped == '"users"'

    def test_parameter(self):
        """Test PostgreSQL parameter placeholder."""
        grammar = PostgresGrammar()
        param = grammar._parameter("value")

        assert param == "?"
