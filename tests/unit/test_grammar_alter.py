"""Unit tests for ALTER TABLE compilation (schema alteration ops).

Covers the Laravel-style Blueprint alter API: add/drop/rename columns,
drop/rename indexes, drop primary/foreign keys, and ``.change()`` column
modification — across SQLite, PostgreSQL and MySQL grammars.
"""
from __future__ import annotations

import pytest

from pyloquent.grammars.mysql_grammar import MySQLGrammar
from pyloquent.grammars.postgres_grammar import PostgresGrammar
from pyloquent.grammars.sqlite_grammar import SQLiteGrammar
from pyloquent.schema.blueprint import Blueprint


def _alter(grammar, build):
    bp = Blueprint("users")
    build(bp)
    return grammar.compile_alter_table(bp)


# ---------------------------------------------------------------------------
# Add columns (all dialects use the base path)
# ---------------------------------------------------------------------------

def test_add_column():
    sql = _alter(SQLiteGrammar(), lambda t: t.string("phone").nullable())
    assert any("ADD COLUMN" in s and "phone" in s for s in sql)


def test_add_index_in_alter():
    sql = _alter(SQLiteGrammar(), lambda t: t.index("email"))
    assert any("CREATE INDEX" in s and "email" in s for s in sql)


def test_add_foreign_key_in_alter():
    def build(t):
        t.foreign("account_id").references("id").on("accounts").cascade_on_delete()
    sql = _alter(PostgresGrammar(), build)
    assert any("ADD CONSTRAINT" in s and "FOREIGN KEY" in s for s in sql)


# ---------------------------------------------------------------------------
# Drop column
# ---------------------------------------------------------------------------

def test_drop_single_column():
    sql = _alter(SQLiteGrammar(), lambda t: t.drop_column("phone"))
    assert sql == ['ALTER TABLE "users" DROP COLUMN "phone"']


def test_drop_multiple_columns_emits_one_statement_each():
    sql = _alter(SQLiteGrammar(), lambda t: t.drop_column(["a", "b"]))
    assert sql == [
        'ALTER TABLE "users" DROP COLUMN "a"',
        'ALTER TABLE "users" DROP COLUMN "b"',
    ]


def test_drop_timestamps_helper():
    sql = _alter(SQLiteGrammar(), lambda t: t.drop_timestamps())
    assert 'ALTER TABLE "users" DROP COLUMN "created_at"' in sql
    assert 'ALTER TABLE "users" DROP COLUMN "updated_at"' in sql


# ---------------------------------------------------------------------------
# Rename column
# ---------------------------------------------------------------------------

def test_rename_column():
    sql = _alter(SQLiteGrammar(), lambda t: t.rename_column("name", "full_name"))
    assert sql == ['ALTER TABLE "users" RENAME COLUMN "name" TO "full_name"']


# ---------------------------------------------------------------------------
# Drop indexes
# ---------------------------------------------------------------------------

def test_drop_index_by_name():
    sql = _alter(SQLiteGrammar(), lambda t: t.drop_index("users_email_index"))
    assert sql == ['DROP INDEX "users_email_index"']


def test_drop_unique_by_columns_derives_name():
    sql = _alter(SQLiteGrammar(), lambda t: t.drop_unique(["email"]))
    assert sql == ['DROP INDEX "users_email_unique"']


def test_mysql_drop_index_uses_alter_table():
    sql = _alter(MySQLGrammar(), lambda t: t.drop_index("users_email_index"))
    assert sql == ["ALTER TABLE `users` DROP INDEX `users_email_index`"]


# ---------------------------------------------------------------------------
# Drop primary / foreign
# ---------------------------------------------------------------------------

def test_mysql_drop_primary():
    sql = _alter(MySQLGrammar(), lambda t: t.drop_primary())
    assert sql == ["ALTER TABLE `users` DROP PRIMARY KEY"]


def test_postgres_drop_primary_defaults_to_pkey_name():
    sql = _alter(PostgresGrammar(), lambda t: t.drop_primary())
    assert sql == ['ALTER TABLE "users" DROP CONSTRAINT "users_pkey"']


def test_mysql_drop_foreign():
    sql = _alter(MySQLGrammar(), lambda t: t.drop_foreign("users_account_id_foreign"))
    assert sql == ["ALTER TABLE `users` DROP FOREIGN KEY `users_account_id_foreign`"]


def test_postgres_drop_foreign_uses_constraint():
    sql = _alter(PostgresGrammar(), lambda t: t.drop_foreign(["account_id"]))
    assert sql == ['ALTER TABLE "users" DROP CONSTRAINT "users_account_id_foreign"']


def test_sqlite_drop_primary_raises():
    with pytest.raises(NotImplementedError):
        _alter(SQLiteGrammar(), lambda t: t.drop_primary())


def test_sqlite_drop_foreign_raises():
    with pytest.raises(NotImplementedError):
        _alter(SQLiteGrammar(), lambda t: t.drop_foreign(["account_id"]))


# ---------------------------------------------------------------------------
# Rename index
# ---------------------------------------------------------------------------

def test_postgres_rename_index():
    sql = _alter(PostgresGrammar(), lambda t: t.rename_index("old_idx", "new_idx"))
    assert sql == ['ALTER INDEX "old_idx" RENAME TO "new_idx"']


def test_mysql_rename_index():
    sql = _alter(MySQLGrammar(), lambda t: t.rename_index("old_idx", "new_idx"))
    assert sql == ["ALTER TABLE `users` RENAME INDEX `old_idx` TO `new_idx`"]


def test_sqlite_rename_index_raises():
    with pytest.raises(NotImplementedError):
        _alter(SQLiteGrammar(), lambda t: t.rename_index("a", "b"))


# ---------------------------------------------------------------------------
# Change column
# ---------------------------------------------------------------------------

def test_mysql_change_column_modify():
    sql = _alter(MySQLGrammar(), lambda t: t.string("name", 100).change())
    assert any("MODIFY COLUMN" in s and "name" in s for s in sql)


def test_postgres_change_column_alter():
    sql = _alter(PostgresGrammar(), lambda t: t.string("name", 100).nullable(False).change())
    assert any("ALTER COLUMN" in s and "TYPE" in s for s in sql)
    assert any("SET NOT NULL" in s for s in sql)


def test_postgres_change_column_nullable_and_default():
    sql = _alter(
        PostgresGrammar(),
        lambda t: t.string("status").nullable().default("draft").change(),
    )
    assert any("DROP NOT NULL" in s for s in sql)
    assert any("SET DEFAULT" in s and "draft" in s for s in sql)


def test_sqlite_change_column_raises():
    with pytest.raises(NotImplementedError):
        _alter(SQLiteGrammar(), lambda t: t.string("name").change())


def test_unknown_alter_command_raises():
    grammar = SQLiteGrammar()
    with pytest.raises(ValueError, match="Unknown alter command"):
        grammar._compile_alter_command("users", {"type": "bogus"})


# ---------------------------------------------------------------------------
# drop_morphs
# ---------------------------------------------------------------------------

def test_drop_morphs():
    sql = _alter(SQLiteGrammar(), lambda t: t.drop_morphs("commentable"))
    assert 'DROP INDEX "users_commentable_id_commentable_type_index"' in sql
    assert 'ALTER TABLE "users" DROP COLUMN "commentable_id"' in sql
    assert 'ALTER TABLE "users" DROP COLUMN "commentable_type"' in sql
