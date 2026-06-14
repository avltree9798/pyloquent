"""Unit tests for the model -> migration generator."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pyloquent.migrations.generator import (
    diff_columns,
    generate_create_lines,
    generate_create_migration,
    generate_diff_migration,
)
from pyloquent.orm.model import Model


class GenUser(Model):
    __table__ = "gen_users"
    __fillable__ = ["name", "email", "age", "bio"]

    id: Optional[int] = None
    name: str
    email: Optional[str] = None
    age: int = 0
    bio: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class GenToken(Model):
    __table__ = "gen_tokens"
    __primary_key__ = "id"
    __incrementing__ = False
    __key_type__ = "str"
    __timestamps__ = False
    __fillable__ = ["id", "value"]

    id: str
    value: str


def test_create_lines_for_incrementing_int_pk():
    lines = generate_create_lines(GenUser)
    assert lines[0] == "table.id()"
    assert 'table.string("name")' in lines
    assert 'table.string("email").nullable()' in lines
    # age has a non-null default of 0
    assert any(line.startswith('table.integer("age")') and ".default(0)" in line for line in lines)
    assert "table.timestamps()" in lines
    # created_at/updated_at handled by timestamps(), not as separate columns
    assert not any('"created_at"' in line for line in lines)


def test_create_lines_for_string_pk():
    lines = generate_create_lines(GenToken)
    assert 'table.string("id").primary()' in lines
    assert 'table.string("value")' in lines
    assert "table.timestamps()" not in lines


def test_generated_create_migration_is_valid_python():
    source = generate_create_migration(GenUser)
    # Must compile and reference the right table + class.
    compile(source, "<generated>", "exec")
    assert "class CreateGenUsersTable(Migration)" in source
    assert 'schema.create("gen_users"' in source
    assert 'schema.drop("gen_users")' in source


def test_diff_columns_add_and_drop():
    to_add, to_drop = diff_columns(GenUser, ["id", "name", "legacy_col"])
    assert "email" in to_add
    assert "age" in to_add
    assert "bio" in to_add
    assert to_drop == ["legacy_col"]


def test_generated_diff_migration_is_valid_python():
    source = generate_diff_migration(GenUser, ["id", "name", "legacy_col"])
    compile(source, "<generated>", "exec")
    assert 'schema.table("gen_users"' in source
    assert 'table.drop_column("legacy_col")' in source
    assert 'table.string("email").nullable()' in source


def test_diff_migration_no_changes():
    cols = list(GenToken.model_fields.keys())
    source = generate_diff_migration(GenToken, cols)
    compile(source, "<generated>", "exec")
    assert "no changes detected" in source
