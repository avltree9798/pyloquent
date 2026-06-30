"""Regression tests for the JSON-cast asymmetry.

Before 0.3.4 `__casts__ = "json"` would:

  * encode dict → JSON string on `Model.create()`           ✓
  * decode JSON string → dict on read                        ✓
  * NOT re-encode dict → JSON string on `model.save()`       ✗

The third path crashed downstream (`Error binding parameter: type 'dict' is
not supported`) whenever a JSON-cast field was modified and the model was
saved.
"""
from __future__ import annotations

from typing import Any, Optional

import pytest

from pyloquent import ConnectionManager, Model
from pyloquent.database.manager import set_manager


class _Widget(Model):
    __table__ = "widgets"
    __fillable__ = ("name", "settings", "tags")
    __casts__ = {"settings": "json", "tags": "json"}

    id: Optional[int] = None
    name: str = ""
    settings: Any = None
    tags: Any = None


@pytest.fixture
async def widgets():
    mgr = ConnectionManager()
    mgr.add_connection("default", {"driver": "sqlite", "database": ":memory:"}, default=True)
    await mgr.connect()
    set_manager(mgr)
    conn = mgr.connection()
    await conn.execute(
        "CREATE TABLE widgets ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  name TEXT NOT NULL,"
        "  settings TEXT,"
        "  tags TEXT"
        ")"
    )
    try:
        yield
    finally:
        await mgr.disconnect()


class TestJsonCastOnSave:
    async def test_create_then_update_dict_field(self, widgets) -> None:
        """A dict assigned to a `json`-cast column must survive `.save()`."""
        w = await _Widget.create({"name": "x", "settings": {"theme": "dark"}})
        assert w.settings == {"theme": "dark"}

        # Mutate and save — pre-0.3.4 this raised `type 'dict' is not supported`.
        w.settings = {"theme": "light", "compact": True}
        await w.save()

        # Reload from disk and verify the round trip.
        reloaded = await _Widget.find(w.id)
        assert reloaded.settings == {"theme": "light", "compact": True}

    async def test_save_with_list_value(self, widgets) -> None:
        w = await _Widget.create({"name": "x", "tags": ["alpha"]})
        w.tags = ["alpha", "beta", "gamma"]
        await w.save()

        reloaded = await _Widget.find(w.id)
        assert reloaded.tags == ["alpha", "beta", "gamma"]

    async def test_save_with_unchanged_dict_field_is_a_noop(self, widgets) -> None:
        """If the cast field hasn't changed, save() shouldn't choke on it
        even though pyloquent loaded it as a dict via the read cast."""
        w = await _Widget.create({"name": "x", "settings": {"k": "v"}})

        reloaded = await _Widget.find(w.id)
        reloaded.name = "y"        # mutate a different field
        await reloaded.save()        # settings comes along on a UPDATE

        twice = await _Widget.find(w.id)
        assert twice.name == "y"
        assert twice.settings == {"k": "v"}

    async def test_save_with_null_dict_field(self, widgets) -> None:
        w = await _Widget.create({"name": "x", "settings": {"k": "v"}})
        w.settings = None
        await w.save()

        reloaded = await _Widget.find(w.id)
        assert reloaded.settings is None

    async def test_json_cast_serialises_nested_datetime(self, widgets) -> None:
        """A json-cast dict containing a datetime/date must serialise.

        Regression: ``json.dumps`` without ``default=str`` raised
        ``Object of type datetime is not JSON serializable`` — hit in the wild
        by a ``meta`` column holding a ``fetched_at`` timestamp.
        """
        from datetime import date, datetime

        w = await _Widget.create(
            {"name": "x", "settings": {"fetched_at": datetime(2026, 6, 30, 12, 57, 59), "day": date(2026, 6, 30)}}
        )
        reloaded = await _Widget.find(w.id)
        # Stored as ISO-ish strings inside the JSON payload.
        assert reloaded.settings["fetched_at"] == "2026-06-30 12:57:59"
        assert reloaded.settings["day"] == "2026-06-30"
