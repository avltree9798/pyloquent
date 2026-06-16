"""Unit tests for the model serialiser that enforces ``__hidden__``.

Pyloquent registers a Pydantic ``model_serializer`` (``Model._pyloquent_serialise``)
so that the ``__hidden__`` / ``__visible__`` / ``__appends__`` rules are applied by
Pydantic's *core* serialiser — not just the Python-level :meth:`Model.model_dump`.

That distinction matters: ``model_dump_json``, recursive serialisation of nested
models, and ``TypeAdapter(Model).dump_python`` (which is exactly how FastAPI renders
a ``response_model``) all bypass an overridden ``model_dump`` and call the core
serialiser directly. These tests pin that behaviour at the unit level — no database
connection is required.
"""
import json
from typing import ClassVar, List, Optional

from pydantic import TypeAdapter

from pyloquent import Model


class SerUser(Model):
    __table__ = "ser_users"
    __fillable__: ClassVar[List[str]] = ["name", "secret"]
    __hidden__: ClassVar[List[str]] = ["secret"]

    id: Optional[int] = None
    name: str
    secret: Optional[str] = None


class SerVisibleUser(Model):
    __table__ = "ser_visible_users"
    __visible__: ClassVar[List[str]] = ["name"]

    id: Optional[int] = None
    name: str
    secret: Optional[str] = None


class SerAppendUser(Model):
    __table__ = "ser_append_users"
    __hidden__: ClassVar[List[str]] = ["secret"]
    __appends__: ClassVar[List[str]] = ["display_name"]

    id: Optional[int] = None
    name: str
    secret: Optional[str] = None

    def get_display_name_attribute(self) -> str:
        return f"[{self.name}]"


# ---------------------------------------------------------------------------
# Core-serialiser paths must honour __hidden__
# ---------------------------------------------------------------------------

def test_model_dump_hides_class_hidden():
    u = SerUser(id=1, name="A", secret="shh")
    assert u.model_dump() == {"id": 1, "name": "A"}


def test_model_dump_json_hides_class_hidden():
    u = SerUser(id=1, name="A", secret="shh")
    data = json.loads(u.model_dump_json())
    assert "secret" not in data
    assert data == {"id": 1, "name": "A"}


def test_type_adapter_dump_python_hides_hidden():
    """This is the exact path FastAPI uses to render a response_model."""
    u = SerUser(id=1, name="A", secret="shh")
    dumped = TypeAdapter(SerUser).dump_python(u)
    assert "secret" not in dumped
    assert dumped == {"id": 1, "name": "A"}


def test_type_adapter_dump_json_hides_hidden():
    u = SerUser(id=1, name="A", secret="shh")
    dumped = json.loads(TypeAdapter(SerUser).dump_json(u))
    assert "secret" not in dumped


def test_type_adapter_list_hides_hidden():
    """Simulates ``response_model=List[Model]`` — nested serialisation."""
    users = [SerUser(id=1, name="A", secret="x"), SerUser(id=2, name="B", secret="y")]
    dumped = TypeAdapter(List[SerUser]).dump_python(users)
    assert all("secret" not in row for row in dumped)


# ---------------------------------------------------------------------------
# __visible__ whitelist via the core serialiser
# ---------------------------------------------------------------------------

def test_visible_whitelist_via_core_serialiser():
    u = SerVisibleUser(id=1, name="A", secret="shh")
    dumped = TypeAdapter(SerVisibleUser).dump_python(u)
    assert dumped == {"name": "A"}


# ---------------------------------------------------------------------------
# Per-instance overrides via the core serialiser
# ---------------------------------------------------------------------------

def test_make_visible_reveals_via_core_serialiser():
    u = SerUser(id=1, name="A", secret="shh")
    u.make_visible("secret")
    assert "secret" in TypeAdapter(SerUser).dump_python(u)


def test_make_hidden_hides_via_core_serialiser():
    u = SerUser(id=1, name="A", secret="shh")
    u.make_hidden("name")
    dumped = TypeAdapter(SerUser).dump_python(u)
    assert "name" not in dumped
    assert "secret" not in dumped


# ---------------------------------------------------------------------------
# __appends__ accessor still applied through the core serialiser
# ---------------------------------------------------------------------------

def test_appends_applied_via_model_dump_json():
    u = SerAppendUser(id=1, name="A", secret="shh")
    data = json.loads(u.model_dump_json())
    assert data["display_name"] == "[A]"
    assert "secret" not in data


# ---------------------------------------------------------------------------
# JSON schema must keep field properties (guards the no-return-annotation rule)
# ---------------------------------------------------------------------------

def test_serialization_schema_retains_field_properties():
    """The serialiser must NOT collapse the model's JSON ``serialization`` schema.

    Annotating ``_pyloquent_serialise`` with ``-> Dict[str, Any]`` would reduce the
    serialisation schema to a bare ``{"type": "object"}`` and wipe the field list
    from a FastAPI ``response_model`` OpenAPI schema. Assert the field properties
    survive so that regression is caught.
    """
    schema = SerUser.model_json_schema(mode="serialization")
    props = schema.get("properties", {})
    assert "name" in props
    assert "id" in props
