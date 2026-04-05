"""Targeted unit tests for uncovered Grammar lines."""
import pytest
from pyloquent.grammars.grammar import Grammar
from pyloquent.grammars.sqlite_grammar import SQLiteGrammar
from pyloquent.query.builder import QueryBuilder


class _BaseGrammar(Grammar):
    """Concrete subclass of the abstract base Grammar for direct testing."""

    def _wrap_value(self, value: str) -> str:
        return f'"{value}"'

    def _parameter(self, value) -> str:
        return "?"


# ---------------------------------------------------------------------------
# Grammar.compile_insert with empty values (line 135)
# ---------------------------------------------------------------------------

def test_compile_insert_empty_values_raises():
    g = _BaseGrammar()
    qb = QueryBuilder(g).from_("users")
    with pytest.raises(ValueError, match="empty"):
        g.compile_insert(qb, [])


# ---------------------------------------------------------------------------
# Grammar.compile_insert_get_id (lines 172-173) — delegates to compile_insert
# ---------------------------------------------------------------------------

def test_compile_insert_get_id_delegates():
    g = _BaseGrammar()
    qb = QueryBuilder(g).from_("users")
    sql, bindings = g.compile_insert_get_id(qb, {"name": "Alice"})
    assert "INSERT" in sql
    assert "Alice" in bindings


# ---------------------------------------------------------------------------
# _compile_select: aliased column dict (lines 253-254)
# ---------------------------------------------------------------------------

def test_compile_select_aliased_column():
    g = SQLiteGrammar()
    qb = QueryBuilder(g).from_("users").select({"email": "user_email"})
    sql, _ = g.compile_select(qb)
    assert "AS" in sql.upper()
    assert "user_email" in sql


# ---------------------------------------------------------------------------
# _compile_where: no wheres → returns empty (line 309)
# ---------------------------------------------------------------------------

def test_compile_wheres_no_wheres():
    g = _BaseGrammar()
    qb = QueryBuilder(g).from_("users")
    clause, bindings = g._compile_wheres(qb)
    assert clause == ""
    assert bindings == []


# ---------------------------------------------------------------------------
# compile_exists (lines 506-507)
# ---------------------------------------------------------------------------

def test_compile_exists():
    g = SQLiteGrammar()
    qb = QueryBuilder(g).from_("users").where("active", 1)
    sql, bindings = g._compile_exists(qb)
    assert "SELECT EXISTS(" in sql
    assert "AS exists" in sql
    assert 1 in bindings


# ---------------------------------------------------------------------------
# _wrap_table: schema.table dot format (lines 520-521)
# ---------------------------------------------------------------------------

def test_wrap_table_schema_dot_format():
    g = _BaseGrammar()
    result = g._wrap_table("public.users")
    assert "." in result
    assert '"public"' in result
    assert '"users"' in result


# ---------------------------------------------------------------------------
# Grammar._wrap_value base implementation (line 552)
# ---------------------------------------------------------------------------

def test_base_grammar_wrap_value():
    g = _BaseGrammar()
    assert g._wrap_value("foo") == '"foo"'


# ---------------------------------------------------------------------------
# Grammar._parameter base implementation (line 565)
# ---------------------------------------------------------------------------

def test_base_grammar_parameter():
    g = _BaseGrammar()
    assert g._parameter("anything") == "?"


# ---------------------------------------------------------------------------
# compile_insert_ignore (lines 607-609)
# ---------------------------------------------------------------------------

def test_compile_insert_or_ignore():
    from pyloquent.grammars.mysql_grammar import MySQLGrammar
    g = MySQLGrammar()
    qb = QueryBuilder(g).from_("users")
    sql, bindings = g.compile_insert_or_ignore(qb, [{"name": "Bob"}])
    assert "INSERT OR IGNORE INTO" in sql
    assert "Bob" in bindings


# ---------------------------------------------------------------------------
# _compile_lock: returns "" when lock is None (line 652)
# ---------------------------------------------------------------------------

def test_compile_lock_returns_empty_when_no_lock():
    g = _BaseGrammar()
    qb = QueryBuilder(g).from_("users")
    result = g._compile_lock(qb)
    assert result == ""
