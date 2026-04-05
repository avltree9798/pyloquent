"""Integration tests for Model attribute casting (__casts__ + _cast_attribute / _set_cast_attribute)."""
import json
import pytest
from datetime import date, datetime
from decimal import Decimal
from typing import ClassVar, Dict, Optional
from pyloquent import Model


class CastModel(Model):
    __table__ = "cast_models"
    __fillable__ = ["meta", "active", "score", "ratio", "label", "born_on", "created_ts", "price"]
    __casts__: ClassVar[Dict[str, str]] = {
        "meta": "json",
        "active": "bool",
        "score": "int",
        "ratio": "float",
        "label": "string",
        "born_on": "date",
        "created_ts": "datetime",
        "price": "decimal:2",
    }

    id: Optional[int] = None
    meta: Optional[str] = None
    active: Optional[int] = None
    score: Optional[int] = None
    ratio: Optional[float] = None
    label: Optional[str] = None
    born_on: Optional[str] = None
    created_ts: Optional[str] = None
    price: Optional[str] = None


@pytest.fixture
async def cast_table(sqlite_db):
    conn = sqlite_db.connection()
    await conn.execute("""
        CREATE TABLE cast_models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meta TEXT,
            active INTEGER,
            score INTEGER,
            ratio REAL,
            label TEXT,
            born_on TEXT,
            created_ts TEXT,
            price TEXT,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    yield


# ---------------------------------------------------------------------------
# _set_cast_attribute: json serialisation on save
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_set_cast_json_serialises_on_save(sqlite_db, cast_table):
    m = CastModel()
    result = m._set_cast_attribute("meta", {"a": 1})
    assert isinstance(result, str)
    assert json.loads(result) == {"a": 1}


@pytest.mark.asyncio
async def test_set_cast_json_string_passthrough(sqlite_db, cast_table):
    m = CastModel()
    result = m._set_cast_attribute("meta", '{"a":1}')
    assert result == '{"a":1}'


@pytest.mark.asyncio
async def test_set_cast_datetime_isoformat(sqlite_db, cast_table):
    m = CastModel()
    dt = datetime(2024, 1, 15, 12, 0, 0)
    result = m._set_cast_attribute("created_ts", dt)
    assert result == dt.isoformat()


@pytest.mark.asyncio
async def test_set_cast_date_isoformat(sqlite_db, cast_table):
    m = CastModel()
    d = date(2024, 6, 1)
    result = m._set_cast_attribute("born_on", d)
    assert result == d.isoformat()


@pytest.mark.asyncio
async def test_set_cast_decimal_to_string(sqlite_db, cast_table):
    m = CastModel()
    result = m._set_cast_attribute("price", Decimal("9.99"))
    assert result == "9.99"


@pytest.mark.asyncio
async def test_set_cast_primitive_passthrough(sqlite_db, cast_table):
    m = CastModel()
    assert m._set_cast_attribute("active", True) is True
    assert m._set_cast_attribute("score", 42) == 42


@pytest.mark.asyncio
async def test_set_cast_none_returns_none(sqlite_db, cast_table):
    m = CastModel()
    assert m._set_cast_attribute("meta", None) is None


@pytest.mark.asyncio
async def test_set_cast_unknown_key_passthrough(sqlite_db, cast_table):
    m = CastModel()
    assert m._set_cast_attribute("nonexistent", "val") == "val"


# ---------------------------------------------------------------------------
# _cast_attribute: read-side casting
# ---------------------------------------------------------------------------

def test_cast_json_string_to_dict():
    m = CastModel()
    result = m._cast_attribute("meta", '{"x": 1}')
    assert result == {"x": 1}


def test_cast_json_already_dict():
    m = CastModel()
    result = m._cast_attribute("meta", {"x": 1})
    assert result == {"x": 1}


def test_cast_bool():
    m = CastModel()
    assert m._cast_attribute("active", 1) is True
    assert m._cast_attribute("active", 0) is False


def test_cast_int():
    m = CastModel()
    assert m._cast_attribute("score", "42") == 42


def test_cast_float():
    m = CastModel()
    assert m._cast_attribute("ratio", "3.14") == pytest.approx(3.14)


def test_cast_string():
    m = CastModel()
    assert m._cast_attribute("label", 42) == "42"


def test_cast_datetime_from_string():
    m = CastModel()
    result = m._cast_attribute("created_ts", "2024-01-15T12:00:00")
    assert isinstance(result, datetime)


def test_cast_datetime_passthrough():
    m = CastModel()
    dt = datetime(2024, 1, 15)
    result = m._cast_attribute("created_ts", dt)
    assert result is dt


def test_cast_date_from_string():
    m = CastModel()
    result = m._cast_attribute("born_on", "2024-06-01")
    assert isinstance(result, date)


def test_cast_date_passthrough():
    m = CastModel()
    d = date(2024, 6, 1)
    result = m._cast_attribute("born_on", d)
    assert result is d


def test_cast_decimal():
    m = CastModel()
    result = m._cast_attribute("price", "9.99")
    assert result == Decimal("9.99")


def test_cast_none_returns_none():
    m = CastModel()
    assert m._cast_attribute("meta", None) is None


def test_cast_unknown_key_passthrough():
    m = CastModel()
    assert m._cast_attribute("nonexistent", "val") == "val"


def test_cast_datetime_utc_z_suffix():
    m = CastModel()
    result = m._cast_attribute("created_ts", "2024-01-15T12:00:00Z")
    assert isinstance(result, datetime)
