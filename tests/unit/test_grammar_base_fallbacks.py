"""Coverage for the base `Grammar` class's fallback paths.

These are normally shadowed by the dialect-specific subclasses
(`SQLiteGrammar` / `PostgresGrammar` / `MySQLGrammar`). Custom grammars
that *don't* override the per-dialect hooks still need to produce
sensible SQL — these tests pin that behaviour.

Specifically:

  * the inline `PRIMARY KEY` emitted on a non-auto-increment column
    flagged `primary=True`,
  * the base `_compile_auto_increment_column` fallback which produces a
    MySQL-flavoured `BIGINT UNSIGNED NOT NULL AUTOINCREMENT PRIMARY KEY`,
  * the base `_compile_auto_increment()` returning the string
    `"AUTOINCREMENT"`.
"""
from __future__ import annotations

import pytest

from pyloquent.grammars.grammar import Grammar
from pyloquent.schema.blueprint import Blueprint


class _MinimalGrammar(Grammar):
    """Concrete subclass of `Grammar` that only provides what the schema
    builder needs — no dialect-specific overrides. Used to exercise the
    base-class fallback paths."""

    def _wrap_value(self, value: str) -> str:
        return f'"{value}"'

    def _parameter(self, value):  # noqa: ANN001
        return "?"


class TestBaseGrammarPrimaryKey:
    def test_non_autoinc_primary_column_gets_inline_primary_key(self) -> None:
        """When `column.primary` is True but `auto_increment` is False
        the base `_compile_column` must still emit `PRIMARY KEY` inline."""
        bp = Blueprint("widgets")
        col = bp.uuid("id")
        col.primary = True
        col.nullable = False

        sql = _MinimalGrammar().compile_create_table(bp)[0]
        # The column appears with NOT NULL + PRIMARY KEY, no AUTOINCREMENT.
        assert '"id"' in sql
        assert "NOT NULL" in sql
        assert "PRIMARY KEY" in sql
        assert "AUTOINCREMENT" not in sql

    def test_non_primary_column_does_not_emit_primary_key(self) -> None:
        bp = Blueprint("widgets")
        bp.string("name")
        sql = _MinimalGrammar().compile_create_table(bp)[0]
        assert "PRIMARY KEY" not in sql


class TestBaseGrammarAutoIncrementFallback:
    """Custom grammars that don't override `_compile_auto_increment_column`
    fall back to the MySQL-flavoured base implementation."""

    def test_id_column_uses_base_autoincrement_form(self) -> None:
        bp = Blueprint("widgets")
        bp.id()

        sql = _MinimalGrammar().compile_create_table(bp)[0]
        assert '"id"' in sql
        assert "BIGINT" in sql            # default for big_increments
        assert "UNSIGNED" in sql           # `id()` sets unsigned=True
        assert "NOT NULL" in sql
        assert "AUTOINCREMENT" in sql      # base `_compile_auto_increment`
        assert "PRIMARY KEY" in sql

    def test_unsigned_flag_carried_through(self) -> None:
        """When `auto_increment` is set but `unsigned` is not, the
        fallback omits the UNSIGNED token."""
        bp = Blueprint("widgets")
        col = bp.big_integer("id")
        col.auto_increment = True
        col.primary = True
        col.unsigned = False
        col.nullable = False

        sql = _MinimalGrammar().compile_create_table(bp)[0]
        assert "UNSIGNED" not in sql
        assert "AUTOINCREMENT" in sql

    def test_compile_auto_increment_returns_keyword(self) -> None:
        """The base `_compile_auto_increment` is just the keyword."""
        assert _MinimalGrammar()._compile_auto_increment() == "AUTOINCREMENT"
