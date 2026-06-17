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


# ---------------------------------------------------------------------------
# Timestamps must also be set on the in-memory INSTANCE (not just _original /
# the DB row), otherwise a freshly saved model serialises them as null.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_timestamps_set_on_instance_after_create(sqlite_db, ts_table):
    m = await TsModel.create({"name": "WithTs"})
    assert m.created_at is not None
    assert m.updated_at is not None


@pytest.mark.asyncio
async def test_timestamps_serialised_after_create(sqlite_db, ts_table):
    m = await TsModel.create({"name": "WithTs"})
    data = m.to_dict()
    assert data["created_at"] is not None
    assert data["updated_at"] is not None


@pytest.mark.asyncio
async def test_updated_at_set_on_instance_after_save(sqlite_db, ts_table):
    m = await TsModel.create({"name": "Before"})
    before = m.updated_at
    m.name = "After"
    await m.save()
    assert m.updated_at is not None
    assert m.updated_at != before


# ---------------------------------------------------------------------------
# Data integrity: created_at must survive a subsequent update. Previously the
# instance attribute was None while _original held the real value, so the next
# save() treated created_at as dirty and wrote NULL back over it.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_created_at_survives_update(sqlite_db, ts_table):
    m = await TsModel.create({"name": "Before"})
    original_created = m.created_at
    assert original_created is not None

    m.name = "After"
    await m.save()

    # In-memory instance keeps created_at unchanged...
    assert m.created_at == original_created
    # ...and the persisted row was not nulled out.
    reloaded = await TsModel.find(m.id)
    assert reloaded.created_at is not None
