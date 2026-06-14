"""Regression tests for Blueprint helper methods that previously crashed
on `.nullable()` because Column is a dataclass whose `nullable` field is
a plain bool, not a fluent setter.

See: https://github.com/avltree9798/pyloquent/issues/_  (bug filed by
downstream Mado project).
"""
from __future__ import annotations

import pytest

from pyloquent.grammars.sqlite_grammar import SQLiteGrammar
from pyloquent.schema.blueprint import Blueprint
from pyloquent.schema.column import Column


class TestTimestampsHelper:
    def test_timestamps_returns_two_nullable_columns(self) -> None:
        blueprint = Blueprint("widgets")
        # Must not crash. Prior to 0.3.4 this raised:
        #   TypeError: 'bool' object is not callable
        columns = blueprint.timestamps()
        assert isinstance(columns, list)
        assert len(columns) == 2
        names = {col.name for col in columns}
        assert names == {"created_at", "updated_at"}
        for col in columns:
            assert isinstance(col, Column)
            assert col.nullable is True
            assert col.type == "timestamp"

    def test_timestamps_appends_columns_to_blueprint(self) -> None:
        blueprint = Blueprint("widgets")
        blueprint.timestamps()
        assert len(blueprint.columns) == 2

    def test_timestamps_tz_returns_two_nullable_tz_columns(self) -> None:
        blueprint = Blueprint("widgets")
        columns = blueprint.timestamps_tz()
        assert len(columns) == 2
        for col in columns:
            assert col.nullable is True
            assert col.type == "timestamp_tz"


class TestSoftDeletesHelper:
    def test_soft_deletes_returns_nullable_deleted_at(self) -> None:
        blueprint = Blueprint("widgets")
        col = blueprint.soft_deletes()
        assert isinstance(col, Column)
        assert col.name == "deleted_at"
        assert col.nullable is True
        assert col.type == "timestamp"

    def test_soft_deletes_supports_custom_column_name(self) -> None:
        blueprint = Blueprint("widgets")
        col = blueprint.soft_deletes(column="archived_at")
        assert col.name == "archived_at"
        assert col.nullable is True

    def test_soft_deletes_tz_returns_nullable_timestamp_tz(self) -> None:
        blueprint = Blueprint("widgets")
        col = blueprint.soft_deletes_tz()
        assert col.nullable is True
        assert col.type == "timestamp_tz"


class TestColumnChaining:
    """Fluent column modifiers must chain without crashing and update state."""

    def test_unique_chaining_returns_column_and_sets_flag(self) -> None:
        blueprint = Blueprint("widgets")
        # Previously raised: TypeError: 'bool' object is not callable
        col = blueprint.string("uid").unique()
        assert isinstance(col, Column)
        assert bool(col.unique) is True
        assert blueprint.columns[-1] is col

    def test_nullable_chaining_toggles_value(self) -> None:
        blueprint = Blueprint("widgets")
        col = blueprint.string("name").nullable(False)
        assert col.nullable is False
        assert bool(col.nullable) is False

    def test_chaining_multiple_modifiers(self) -> None:
        blueprint = Blueprint("widgets")
        col = blueprint.string("slug").nullable(False).unique().index()
        assert col.nullable is False
        assert bool(col.unique) is True
        assert bool(col.index) is True

    def test_default_chaining_sets_value(self) -> None:
        blueprint = Blueprint("widgets")
        col = blueprint.integer("score").default(0)
        assert col.default == 0

    def test_unset_modifiers_have_sensible_defaults(self) -> None:
        col = Column(name="x", type="string")
        assert bool(col.nullable) is True
        assert bool(col.unsigned) is False
        assert bool(col.unique) is False
        assert bool(col.primary) is False
        # Unset value modifier must not look like a concrete default.
        assert callable(col.default)

    def test_unique_chaining_emits_unique_index_sql(self) -> None:
        blueprint = Blueprint("widgets")
        blueprint.id()
        blueprint.string("uid").unique()
        statements = SQLiteGrammar().compile_create_table(blueprint)
        assert any("UNIQUE INDEX" in s and "uid" in s for s in statements)

    def test_index_chaining_emits_index_sql(self) -> None:
        blueprint = Blueprint("widgets")
        blueprint.id()
        blueprint.string("slug").index()
        statements = SQLiteGrammar().compile_create_table(blueprint)
        assert any(
            "INDEX" in s and "UNIQUE" not in s and "slug" in s for s in statements
        )

    def test_default_chaining_emits_default_sql(self) -> None:
        blueprint = Blueprint("widgets")
        blueprint.integer("score").default(0)
        statements = SQLiteGrammar().compile_create_table(blueprint)
        assert any("DEFAULT 0" in s for s in statements)

    def test_unset_column_has_no_default_sql(self) -> None:
        blueprint = Blueprint("widgets")
        blueprint.string("name")
        statements = SQLiteGrammar().compile_create_table(blueprint)
        assert all("DEFAULT" not in s for s in statements)
