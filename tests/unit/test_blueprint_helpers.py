"""Regression tests for Blueprint helper methods that previously crashed
on `.nullable()` because Column is a dataclass whose `nullable` field is
a plain bool, not a fluent setter.

See: https://github.com/avltree9798/pyloquent/issues/_  (bug filed by
downstream Mado project).
"""
from __future__ import annotations

import pytest

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
