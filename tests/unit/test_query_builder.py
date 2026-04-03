"""Tests for QueryBuilder."""

import pytest

from pyloquent.grammars.sqlite_grammar import SQLiteGrammar
from pyloquent.query.builder import QueryBuilder


class TestQueryBuilderBasics:
    """Test basic QueryBuilder functionality."""

    def test_from_table(self):
        """Test setting table."""
        builder = QueryBuilder(SQLiteGrammar()).from_("users")
        assert builder._table == "users"

    def test_select_columns(self):
        """Test selecting specific columns."""
        builder = QueryBuilder(SQLiteGrammar()).from_("users").select("id", "name")
        assert builder._selects == ["id", "name"]

    def test_distinct(self):
        """Test distinct."""
        builder = QueryBuilder(SQLiteGrammar()).from_("users").distinct()
        assert builder._distinct is True

    def test_where_basic(self):
        """Test basic where clause."""
        builder = QueryBuilder(SQLiteGrammar()).from_("users").where("id", 1)

        assert len(builder._wheres) == 1
        assert builder._wheres[0].column == "id"
        assert builder._wheres[0].operator == "="
        assert builder._wheres[0].value == 1

    def test_where_with_operator(self):
        """Test where with explicit operator."""
        builder = QueryBuilder(SQLiteGrammar()).from_("users").where("age", ">", 18)

        assert builder._wheres[0].operator == ">"
        assert builder._wheres[0].value == 18

    def test_where_in(self):
        """Test where in clause."""
        builder = QueryBuilder(SQLiteGrammar()).from_("users").where_in("id", [1, 2, 3])

        assert len(builder._wheres) == 1
        assert builder._wheres[0].type == "in"
        assert builder._wheres[0].value == [1, 2, 3]

    def test_where_null(self):
        """Test where null clause."""
        builder = QueryBuilder(SQLiteGrammar()).from_("users").where_null("deleted_at")

        assert len(builder._wheres) == 1
        assert builder._wheres[0].type == "null"
        assert builder._wheres[0].column == "deleted_at"

    def test_order_by(self):
        """Test order by."""
        builder = QueryBuilder(SQLiteGrammar()).from_("users").order_by("name", "desc")

        assert len(builder._orders) == 1
        assert builder._orders[0].column == "name"
        assert builder._orders[0].direction == "desc"

    def test_limit(self):
        """Test limit."""
        builder = QueryBuilder(SQLiteGrammar()).from_("users").limit(10)

        assert builder._limit == 10

    def test_offset(self):
        """Test offset."""
        builder = QueryBuilder(SQLiteGrammar()).from_("users").offset(20)

        assert builder._offset == 20

    def test_for_page(self):
        """Test pagination."""
        builder = QueryBuilder(SQLiteGrammar()).from_("users").for_page(3, 15)

        assert builder._offset == 30  # (3-1) * 15
        assert builder._limit == 15

    def test_join(self):
        """Test join."""
        builder = (
            QueryBuilder(SQLiteGrammar())
            .from_("users")
            .join("posts", "users.id", "=", "posts.user_id")
        )

        assert len(builder._joins) == 1
        assert builder._joins[0].table == "posts"
        assert builder._joins[0].type == "inner"

    def test_left_join(self):
        """Test left join."""
        builder = (
            QueryBuilder(SQLiteGrammar())
            .from_("users")
            .left_join("posts", "users.id", "=", "posts.user_id")
        )

        assert builder._joins[0].type == "left"

    def test_group_by(self):
        """Test group by."""
        builder = QueryBuilder(SQLiteGrammar()).from_("users").group_by("department", "role")

        assert builder._groups == ["department", "role"]

    def test_or_where(self):
        """Test or where."""
        builder = (
            QueryBuilder(SQLiteGrammar())
            .from_("users")
            .where("active", True)
            .or_where("role", "admin")
        )

        assert builder._wheres[0].boolean == "and"
        assert builder._wheres[1].boolean == "or"


class TestQueryBuilderChaining:
    """Test query builder method chaining."""

    def test_fluent_interface(self):
        """Test that methods return self for chaining."""
        builder = QueryBuilder(SQLiteGrammar())

        result = (
            builder.from_("users")
            .select("id", "name")
            .where("active", True)
            .where("age", ">=", 18)
            .order_by("name")
            .limit(10)
        )

        assert result is builder
        assert builder._table == "users"
        assert len(builder._wheres) == 2


class TestQueryBuilderClone:
    """Test query builder cloning."""

    def test_clone_creates_independent_copy(self):
        """Test that clone creates an independent copy."""
        builder = QueryBuilder(SQLiteGrammar()).from_("users").where("active", True)

        clone = builder.clone()

        # Modify clone
        clone.where("age", ">", 18)

        # Original should be unchanged
        assert len(builder._wheres) == 1
        assert len(clone._wheres) == 2
