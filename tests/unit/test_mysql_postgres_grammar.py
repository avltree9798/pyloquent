"""Unit tests for MySQLGrammar and PostgresGrammar."""
from unittest.mock import MagicMock
from pyloquent.grammars.mysql_grammar import MySQLGrammar
from pyloquent.grammars.postgres_grammar import PostgresGrammar
from pyloquent.query.builder import QueryBuilder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def mysql_qb():
    return QueryBuilder(MySQLGrammar())


def pg_qb():
    return QueryBuilder(PostgresGrammar())


# ===========================================================================
# MySQLGrammar
# ===========================================================================

class TestMySQLGrammar:

    def test_wrap_value_uses_backticks(self):
        g = MySQLGrammar()
        assert g._wrap_value("users") == "`users`"

    def test_parameter_uses_percent_s(self):
        g = MySQLGrammar()
        assert g._parameter("x") == "%s"

    def test_select_wraps_identifiers_in_backticks(self):
        sql, _ = mysql_qb().from_("users").where("id", 1).to_sql()
        assert "`users`" in sql
        assert "`id`" in sql

    def test_compile_insert_get_id(self):
        g = MySQLGrammar()
        qb = mysql_qb().from_("users")
        sql, bindings = g.compile_insert_get_id(qb, {"name": "Alice"})
        assert "INSERT" in sql
        assert bindings == ["Alice"]

    def test_compile_update_with_order_and_limit(self):
        g = MySQLGrammar()
        qb = mysql_qb().from_("users").order_by("id").limit(5)
        sql, _ = g.compile_update(qb, {"active": 1})
        assert "ORDER BY" in sql.upper()
        assert "LIMIT" in sql.upper()

    def test_compile_update_without_order_limit(self):
        g = MySQLGrammar()
        qb = mysql_qb().from_("users")
        sql, _ = g.compile_update(qb, {"active": 1})
        assert "ORDER BY" not in sql.upper()
        assert "LIMIT" not in sql.upper()

    def test_compile_delete_with_order_and_limit(self):
        g = MySQLGrammar()
        qb = mysql_qb().from_("users").order_by("id").limit(3)
        sql, _ = g.compile_delete(qb)
        assert "ORDER BY" in sql.upper()
        assert "LIMIT" in sql.upper()

    def test_compile_delete_without_order_limit(self):
        g = MySQLGrammar()
        qb = mysql_qb().from_("users")
        sql, _ = g.compile_delete(qb)
        assert "ORDER BY" not in sql.upper()


# ===========================================================================
# PostgresGrammar
# ===========================================================================

class TestPostgresGrammar:

    def test_wrap_value_uses_double_quotes(self):
        g = PostgresGrammar()
        assert g._wrap_value("users") == '"users"'

    def test_parameter_returns_question_mark(self):
        g = PostgresGrammar()
        assert g._parameter("x") == "?"

    def test_supports_returning(self):
        g = PostgresGrammar()
        assert g.supports_returning() is True

    def test_supports_ilike(self):
        g = PostgresGrammar()
        assert g.supports_ilike() is True

    def test_compile_insert_get_id_has_returning(self):
        g = PostgresGrammar()
        qb = pg_qb().from_("users")
        sql, bindings = g.compile_insert_get_id(qb, {"name": "Bob"})
        assert "RETURNING" in sql
        assert '"id"' in sql
        assert bindings == ["Bob"]

    def test_compile_insert_get_id_custom_sequence(self):
        g = PostgresGrammar()
        qb = pg_qb().from_("users")
        sql, _ = g.compile_insert_get_id(qb, {"name": "Carol"}, sequence="uuid")
        assert '"uuid"' in sql

    def test_select_plain(self):
        sql, _ = pg_qb().from_("users").to_sql()
        assert "SELECT *" in sql
        assert '"users"' in sql

    def test_select_distinct(self):
        sql, _ = pg_qb().from_("users").distinct().to_sql()
        assert "SELECT DISTINCT" in sql

    def test_select_distinct_on(self):
        g = PostgresGrammar()
        qb = pg_qb().from_("users")
        qb._distinct_on = ["email"]
        sql, _ = qb.to_sql()
        assert "DISTINCT ON" in sql
        assert '"email"' in sql

    def test_compile_columns_with_specific_select(self):
        sql, _ = pg_qb().from_("users").select("name", "email").to_sql()
        assert '"name"' in sql
        assert '"email"' in sql

    def test_where_clause_compilation(self):
        sql, bindings = pg_qb().from_("users").where("id", 42).to_sql()
        assert '"id"' in sql
        assert 42 in bindings

    def test_compile_update_delegates_to_parent(self):
        g = PostgresGrammar()
        qb = pg_qb().from_("users")
        sql, bindings = g._compile_update(qb, {"name": "Dave"})
        assert "UPDATE" in sql
