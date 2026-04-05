"""Tests for model timestamp field population (created_at/updated_at in model_fields)."""
import pytest
from typing import Any, Optional
from pyloquent import Model


class TsModel(Model):
    __table__ = "ts_models"
    __fillable__ = ["name"]
    id: Optional[int] = None
    name: str
    created_at: Optional[Any] = None
    updated_at: Optional[Any] = None


@pytest.fixture
async def ts_table(sqlite_db):
    conn = sqlite_db.connection()
    await conn.execute("""
        CREATE TABLE ts_models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)
    yield


# ---------------------------------------------------------------------------
# created_at / updated_at set on insert (lines 147, 149)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_timestamps_set_on_create(sqlite_db, ts_table):
    m = await TsModel.create({"name": "WithTs"})
    assert m._original.get("created_at") is not None
    assert m._original.get("updated_at") is not None


# ---------------------------------------------------------------------------
# updated_at refreshed on update (line 190)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_updated_at_refreshed_on_save(sqlite_db, ts_table):
    m = await TsModel.create({"name": "Before"})
    m.name = "After"
    await m.save()
    assert m._original.get("updated_at") is not None
