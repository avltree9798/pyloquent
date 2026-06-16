"""Regression test: FastAPI ``response_model`` must honour ``Model.__hidden__``.

Reproduces the downstream report where a column listed in ``__hidden__`` leaked
through a FastAPI ``response_model``. FastAPI serialises responses via
``TypeAdapter(Model).dump_python`` — Pydantic's *core* serialiser — which bypasses
an overridden :meth:`Model.model_dump`. The fix registers a Pydantic
``model_serializer`` (``Model._pyloquent_serialise``) so the hiding rules apply on
that path too.

The test is skipped automatically if FastAPI / httpx are not installed.
"""
from typing import Optional

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from fastapi import FastAPI  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from pyloquent import Model  # noqa: E402


class HiddenWidget(Model):
    __table__ = "hidden_widgets"
    __fillable__ = ["name", "secret"]
    __hidden__ = ["secret"]

    id: Optional[int] = None
    name: str
    secret: Optional[str] = None


@pytest.fixture
async def hidden_widget_table(sqlite_db):
    conn = sqlite_db.connection()
    await conn.execute(
        """
        CREATE TABLE hidden_widgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            secret TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
        """
    )
    yield


def _build_app() -> "FastAPI":
    app = FastAPI()

    @app.post("/widgets", response_model=HiddenWidget)
    async def create_widget(payload: HiddenWidget):
        # ``payload.secret`` is still accessible as an attribute — hiding only
        # affects serialisation, not attribute access.
        return await HiddenWidget.create({"name": payload.name, "secret": payload.secret})

    @app.get("/widgets/{wid}", response_model=HiddenWidget)
    async def get_widget(wid: int):
        return await HiddenWidget.find(wid)

    return app


@pytest.mark.asyncio
async def test_hidden_field_not_leaked_through_response_model(sqlite_db, hidden_widget_table):
    app = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post("/widgets", json={"name": "A", "secret": "shh"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "A"
        assert "secret" not in body  # regression: must never leak

        wid = body["id"]
        resp2 = await client.get(f"/widgets/{wid}")
        assert resp2.status_code == 200
        assert "secret" not in resp2.json()


@pytest.mark.asyncio
async def test_response_model_still_documented_in_openapi(sqlite_db, hidden_widget_table):
    """The fix must not blank out / split away the OpenAPI component schema."""
    app = _build_app()
    schema = app.openapi()
    components = schema.get("components", {}).get("schemas", {})
    assert "HiddenWidget" in components
    # The response schema must still describe the model's fields.
    assert "name" in components["HiddenWidget"].get("properties", {})
