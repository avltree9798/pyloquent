"""Integration tests for non-incrementing (string / UUID) primary keys.

Regression coverage for the bug where ``Model.create`` force-assigned the
database's integer ``lastrowid`` to the primary key even when
``__incrementing__ = False``, crashing Pydantic validation for string keys:

    pydantic_core._pydantic_core.ValidationError: 1 validation error for ...
    id
      Input should be a valid string [type=string_type, input_value=1, ...]
"""
from __future__ import annotations

from typing import Optional

import pytest
import pytest_asyncio

from pyloquent.orm.model import Model


class Widget(Model):
    """Model with a caller-supplied string primary key."""

    __table__ = "widgets_strpk"
    __primary_key__ = "id"
    __incrementing__ = False
    __key_type__ = "str"
    __fillable__ = ["id", "name"]
    __timestamps__ = False

    id: str
    name: str


@pytest_asyncio.fixture
async def widgets_table(sqlite_db):
    conn = sqlite_db.connection()
    await conn.execute(
        """
        CREATE TABLE widgets_strpk (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL
        )
        """
    )
    yield
    await conn.execute("DROP TABLE IF EXISTS widgets_strpk")


@pytest.mark.asyncio
async def test_create_keeps_string_primary_key(widgets_table):
    # Previously raised a Pydantic ValidationError (int lastrowid -> str field).
    widget = await Widget.create({"id": "wid_abc", "name": "Sprocket"})

    assert widget.id == "wid_abc"
    assert isinstance(widget.id, str)
    assert widget._exists is True


@pytest.mark.asyncio
async def test_string_pk_round_trips(widgets_table):
    await Widget.create({"id": "wid_xyz", "name": "Cog"})

    fetched = await Widget.find("wid_xyz")
    assert fetched is not None
    assert fetched.id == "wid_xyz"
    assert fetched.name == "Cog"


@pytest.mark.asyncio
async def test_string_pk_update_after_create(widgets_table):
    widget = await Widget.create({"id": "wid_1", "name": "Before"})
    widget.name = "After"
    await widget.save()

    fetched = await Widget.find("wid_1")
    assert fetched is not None
    assert fetched.name == "After"
    assert fetched.id == "wid_1"
