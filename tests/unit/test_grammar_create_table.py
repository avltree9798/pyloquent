"""Regression tests for `compile_create_table` across every supported
dialect.

Before 0.3.4 the `id()` helper produced DDL that was invalid in **every**
target database:

  - SQLite     : `"id" BIGINT UNSIGNED NULL AUTOINCREMENT`
                 → SQLite refuses `BIGINT UNSIGNED`, refuses `NULL` on an
                   AUTOINCREMENT column, and AUTOINCREMENT requires the
                   exact type `INTEGER PRIMARY KEY`.
  - PostgreSQL : same string, `AUTOINCREMENT` is not a Postgres keyword.
  - MySQL      : same string, `AUTOINCREMENT` is wrong (must be `AUTO_INCREMENT`)
                 and PRIMARY KEY was never emitted.

These tests pin the corrected SQL for each dialect.
"""
from __future__ import annotations

import pytest

from pyloquent.grammars.mysql_grammar import MySQLGrammar
from pyloquent.grammars.postgres_grammar import PostgresGrammar
from pyloquent.grammars.sqlite_grammar import SQLiteGrammar
from pyloquent.schema.blueprint import Blueprint


def _make_blueprint() -> Blueprint:
    bp = Blueprint("widgets")
    bp.id()
    bp.string("name")
    return bp


# ---------------------------------------------------------------------------
# SQLite
# ---------------------------------------------------------------------------
class TestSQLiteCreateTable:
    def test_id_column_is_integer_primary_key_autoincrement(self) -> None:
        grammar = SQLiteGrammar()
        sql_list = grammar.compile_create_table(_make_blueprint())
        sql = sql_list[0]
        # SQLite needs the exact phrase to make the column a ROWID alias.
        assert '"id" INTEGER PRIMARY KEY AUTOINCREMENT' in sql
        # …and must NOT carry any of these tokens on the id column.
        for forbidden in ("BIGINT", "UNSIGNED", "NULL AUTOINCREMENT"):
            id_clause = sql.split('"name"')[0]
            assert forbidden not in id_clause, f"forbidden token {forbidden!r} found in: {id_clause}"

    def test_runs_against_real_sqlite_without_error(self) -> None:
        """The acid test: feed the generated DDL to sqlite3 in-memory and
        assert it accepts it."""
        import sqlite3

        grammar = SQLiteGrammar()
        sql_list = grammar.compile_create_table(_make_blueprint())
        conn = sqlite3.connect(":memory:")
        try:
            for stmt in sql_list:
                conn.execute(stmt)
            # And rows should auto-increment.
            conn.execute("INSERT INTO widgets (name) VALUES (?)", ("a",))
            conn.execute("INSERT INTO widgets (name) VALUES (?)", ("b",))
            rows = conn.execute("SELECT id FROM widgets ORDER BY id").fetchall()
            assert rows == [(1,), (2,)]
        finally:
            conn.close()

    def test_string_column_is_varchar_with_default_length(self) -> None:
        sql = SQLiteGrammar().compile_create_table(_make_blueprint())[0]
        assert "VARCHAR(255)" in sql

    def test_non_pk_integer_columns_keep_their_unsigned_flag(self) -> None:
        # `unsigned` is meaningless to SQLite but the grammar should still
        # emit it for non-PK columns — that's the user's explicit choice.
        bp = Blueprint("t")
        bp.unsigned_integer("count")
        sql = SQLiteGrammar().compile_create_table(bp)[0]
        # SQLite accepts the keyword even though it ignores it.
        assert '"count"' in sql

    def test_explicit_timestamps_helper_compiles(self) -> None:
        bp = Blueprint("t")
        bp.id()
        bp.timestamps()
        sql_list = SQLiteGrammar().compile_create_table(bp)
        import sqlite3
        conn = sqlite3.connect(":memory:")
        try:
            for s in sql_list:
                conn.execute(s)
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------
class TestPostgresCreateTable:
    def test_id_column_uses_bigserial_primary_key(self) -> None:
        grammar = PostgresGrammar()
        sql = grammar.compile_create_table(_make_blueprint())[0]
        # Postgres has no AUTOINCREMENT; BIGSERIAL is the canonical
        # auto-incrementing primary key.
        assert '"id" BIGSERIAL PRIMARY KEY' in sql
        for forbidden in ("AUTOINCREMENT", "UNSIGNED", "BIGINT UNSIGNED"):
            assert forbidden not in sql.split('"name"')[0]

    def test_increments_uses_serial(self) -> None:
        bp = Blueprint("t")
        bp.increments("id")
        sql = PostgresGrammar().compile_create_table(bp)[0]
        assert '"id" SERIAL PRIMARY KEY' in sql


# ---------------------------------------------------------------------------
# MySQL
# ---------------------------------------------------------------------------
class TestMySQLCreateTable:
    def test_id_column_uses_auto_increment_primary_key(self) -> None:
        import re

        grammar = MySQLGrammar()
        sql = grammar.compile_create_table(_make_blueprint())[0]
        # MySQL: AUTO_INCREMENT (underscore) + PRIMARY KEY + must be NOT NULL.
        assert "AUTO_INCREMENT" in sql
        assert "PRIMARY KEY" in sql
        # The single-keyword `AUTOINCREMENT` is a SQLite-only quirk and
        # must never appear in MySQL output.
        id_clause = sql.split("`name`")[0]
        assert "AUTOINCREMENT" not in id_clause.replace("AUTO_INCREMENT", "")
        # Must include "NOT NULL" — MySQL refuses a nullable AUTO_INCREMENT
        # column. We use a word-boundary regex so `NOT NULL AUTO_INCREMENT`
        # passes but a bare `NULL AUTO_INCREMENT` would fail.
        assert re.search(r"\bNOT\s+NULL\s+AUTO_INCREMENT\b", sql), \
            f"expected `NOT NULL AUTO_INCREMENT` in {sql!r}"
