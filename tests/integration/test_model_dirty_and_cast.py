"""Tests for remaining uncovered model.py paths: dirty tracking (no-key), fill guard, touch, truncate, casts."""
import pytest
from typing import Any, ClassVar, Dict, List, Optional
from pyloquent import Model
from pyloquent.exceptions import ModelNotFoundException, MassAssignmentException


class DcUser(Model):
    __table__ = "dc_users"
    __fillable__ = ["name", "score"]
    __guarded__: ClassVar[List[str]] = ["id"]
    id: Optional[int] = None
    name: str
    score: Optional[int] = 0


class NoTsUser(Model):
    __table__ = "dc_users"
    __fillable__ = ["name"]
    __timestamps__: ClassVar[bool] = False
    id: Optional[int] = None
    name: str
    score: Optional[int] = 0


@pytest.fixture
async def dc_tables(sqlite_db):
    conn = sqlite_db.connection()
    await conn.execute("""
        CREATE TABLE dc_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            score INTEGER DEFAULT 0,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    yield


# ---------------------------------------------------------------------------
# is_dirty without key (line 755)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_is_dirty_no_key(sqlite_db, dc_tables):
    u = await DcUser.create({"name": "D1"})
    assert u.is_dirty() is False
    u.name = "Changed"
    assert u.is_dirty() is True


@pytest.mark.asyncio
async def test_is_clean_no_key(sqlite_db, dc_tables):
    u = await DcUser.create({"name": "D2"})
    assert u.is_clean() is True
    u.name = "Dirty"
    assert u.is_clean() is False


# ---------------------------------------------------------------------------
# was_changed without key (line 779)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_was_changed_no_key(sqlite_db, dc_tables):
    u = await DcUser.create({"name": "WC1"})
    assert u.was_changed() is False
    u.name = "Upd"
    await u.save()
    assert u.was_changed() is True


# ---------------------------------------------------------------------------
# get_original without key (line 801)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_original_no_key(sqlite_db, dc_tables):
    u = await DcUser.create({"name": "Orig"})
    original = u.get_original()
    assert isinstance(original, dict)
    assert "name" in original


# ---------------------------------------------------------------------------
# fill raises MassAssignmentException for guarded attribute (line 288)
# ---------------------------------------------------------------------------

def test_fill_raises_for_guarded_attribute():
    u = DcUser(name="G")
    with pytest.raises(MassAssignmentException):
        u.fill({"id": 999})


# ---------------------------------------------------------------------------
# refresh raises when record deleted from DB (line 257)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_raises_when_deleted_from_db(sqlite_db, dc_tables):
    u = await DcUser.create({"name": "Gone"})
    conn = sqlite_db.connection()
    await conn.execute("DELETE FROM dc_users WHERE id = ?", [u.id])
    with pytest.raises(ModelNotFoundException):
        await u.refresh()


# ---------------------------------------------------------------------------
# touch when __timestamps__ is False (line 1078)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_touch_returns_false_when_no_timestamps(sqlite_db, dc_tables):
    conn = sqlite_db.connection()
    await conn.execute("INSERT INTO dc_users (name) VALUES (?)", ["NoTsUser"])
    u = NoTsUser(name="NoTs")
    u._exists = True
    u.id = 1
    result = await u.touch()
    assert result is False


# ---------------------------------------------------------------------------
# touch updates updated_at (lines 1082-1085)
# ---------------------------------------------------------------------------

class TsUser(Model):
    __table__ = "dc_users"
    __fillable__ = ["name"]
    id: Optional[int] = None
    name: str
    score: Optional[int] = 0
    updated_at: Optional[Any] = None


@pytest.mark.asyncio
async def test_touch_updates_updated_at(sqlite_db, dc_tables):
    conn = sqlite_db.connection()
    await conn.execute("INSERT INTO dc_users (name) VALUES (?)", ["TouchMe"])
    row = await conn.fetch_one("SELECT id FROM dc_users WHERE name = ?", ["TouchMe"])
    u = TsUser(name="TouchMe")
    u._exists = True
    u.id = row["id"]
    result = await u.touch()
    assert result is True
    assert "updated_at" in u._original


# ---------------------------------------------------------------------------
# truncate classmethod (lines 1395-1397)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_truncate_classmethod(sqlite_db, dc_tables):
    await DcUser.create({"name": "T1"})
    await DcUser.create({"name": "T2"})
    count_before = await DcUser.query.count()
    assert count_before == 2
    await DcUser.truncate()
    count_after = await DcUser.query.count()
    assert count_after == 0


# ---------------------------------------------------------------------------
# _cast_attribute fallback (unknown cast type → line 1710)
# ---------------------------------------------------------------------------

def test_cast_attribute_unknown_type_passthrough():
    class CastUser(DcUser):
        __casts__: ClassVar[Dict[str, str]] = {"name": "unknown_type"}

    u = CastUser(name="X")
    result = u._cast_attribute("name", "hello")
    assert result == "hello"


# ---------------------------------------------------------------------------
# _set_cast_attribute datetime/date passthrough string (line 1738)
# ---------------------------------------------------------------------------

def test_set_cast_attribute_datetime_string_passthrough():
    class CastUser2(DcUser):
        __casts__: ClassVar[Dict[str, str]] = {"name": "datetime"}

    u = CastUser2(name="X")
    result = u._set_cast_attribute("name", "2024-01-15")
    assert result == "2024-01-15"


def test_set_cast_attribute_date_string_passthrough():
    class CastUser3(DcUser):
        __casts__: ClassVar[Dict[str, str]] = {"name": "date"}

    u = CastUser3(name="X")
    result = u._set_cast_attribute("name", "2024-01-15")
    assert result == "2024-01-15"


# ---------------------------------------------------------------------------
# _set_cast_attribute unknown cast type fallback (line 1742)
# ---------------------------------------------------------------------------

def test_set_cast_attribute_unknown_type_passthrough():
    class CastUser4(DcUser):
        __casts__: ClassVar[Dict[str, str]] = {"name": "unknown_type"}

    u = CastUser4(name="X")
    result = u._set_cast_attribute("name", "hello")
    assert result == "hello"
