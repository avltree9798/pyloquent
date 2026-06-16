"""Generate migration files from Pyloquent models.

Pyloquent models are Pydantic classes with **typed fields**, so unlike
Laravel/Eloquent (where the database is the source of truth) we can introspect
a model and emit a matching migration:

* :func:`generate_create_migration` — a ``create`` migration that builds the
  table from the model's fields.
* :func:`generate_diff_migration` — an ``alter`` migration that adds columns
  present on the model but missing from the live table, and drops columns that
  exist in the database but no longer on the model.
"""
from __future__ import annotations

import datetime
import decimal
import enum
import typing
import uuid
from typing import Any, List, Optional, Tuple, Type

try:  # Python 3.10+ PEP 604 unions (``int | None``)
    from types import UnionType  # type: ignore
except ImportError:  # pragma: no cover - <3.10 fallback
    UnionType = None  # type: ignore

try:
    from pydantic_core import PydanticUndefined
except ImportError:  # pragma: no cover - defensive
    PydanticUndefined = object()  # type: ignore


# Map concrete Python types to Blueprint factory method names.
_TYPE_METHODS = {
    bool: "boolean",
    int: "integer",
    float: "float_",
    str: "string",
    bytes: "binary",
    datetime.datetime: "timestamp",
    datetime.date: "date",
    datetime.time: "time",
    uuid.UUID: "uuid",
    decimal.Decimal: "decimal",
}

# Columns managed by dedicated Blueprint helpers rather than per-field calls.
_TIMESTAMP_COLUMNS = ("created_at", "updated_at")
_SOFT_DELETE_COLUMN = "deleted_at"


def _unwrap_optional(annotation: Any) -> Tuple[Any, bool]:
    """Strip ``Optional[...]`` / ``X | None`` and report whether it was nullable.

    Returns:
        A tuple of (inner annotation, is_optional).
    """
    origin = typing.get_origin(annotation)
    is_union = origin is typing.Union or (UnionType is not None and origin is UnionType)
    if is_union:
        args = typing.get_args(annotation)
        non_none = [a for a in args if a is not type(None)]  # noqa: E721
        optional = len(non_none) < len(args)
        inner = non_none[0] if non_none else annotation
        return inner, optional
    return annotation, False


def _resolve_method(annotation: Any) -> str:
    """Resolve the Blueprint method name for a (possibly generic) annotation."""
    inner, _ = _unwrap_optional(annotation)
    origin = typing.get_origin(inner)
    if origin in (list, dict, set, tuple) or inner in (list, dict, set, tuple):
        return "json"
    return _TYPE_METHODS.get(inner, "string")


def _render_default(value: Any) -> Optional[str]:
    """Render a literal default for ``.default(...)``, or None to skip.

    ``Enum`` members are unwrapped to their underlying ``.value`` first. This is
    essential for ``str``/``int``-based enums (e.g. ``class Status(str, Enum)``):
    ``isinstance(Status.ACTIVE, str)`` is ``True`` but ``repr(Status.ACTIVE)``
    is ``"<Status.ACTIVE: 'active'>"`` — invalid Python that would break the
    generated migration. Rendering ``repr(value.value)`` yields ``"'active'"``.
    """
    if isinstance(value, enum.Enum):
        value = value.value
    if isinstance(value, bool):
        return repr(value)
    if isinstance(value, (int, float, str)):
        return repr(value)
    return None


def _field_is_required(field: Any) -> bool:
    """Whether a Pydantic v2 FieldInfo has no default."""
    is_required = getattr(field, "is_required", None)
    if callable(is_required):
        return bool(is_required())
    return getattr(field, "default", PydanticUndefined) is PydanticUndefined


def _field_default(field: Any) -> Any:
    """Return a field's default, or ``PydanticUndefined`` when none is set."""
    return getattr(field, "default", PydanticUndefined)


def _column_line(name: str, method: str, *, nullable: bool, default: Any, primary: bool) -> str:
    """Build a single ``table.<method>("name")...`` chained call string."""
    line = f'table.{method}("{name}")'
    if primary:
        line += ".primary()"
    if nullable:
        line += ".nullable()"
    rendered = _render_default(default)
    if rendered is not None:
        line += f".default({rendered})"
    return line


def get_table_name(model: Type) -> str:
    """Resolve a model's table name (explicit ``__table__`` or pluralised name)."""
    return model.__table__ or model._get_default_table_name()


def generate_create_lines(model: Type) -> List[str]:
    """Produce the list of ``table.*`` Blueprint calls for a model.

    Args:
        model: A Pyloquent model class.

    Returns:
        Ordered list of Blueprint call strings (without trailing commas).
    """
    fields = dict(model.model_fields)
    pk = getattr(model, "__primary_key__", "id")
    incrementing = getattr(model, "__incrementing__", True)
    key_type = getattr(model, "__key_type__", "int")
    has_timestamps = getattr(model, "__timestamps__", True)
    has_soft_deletes = bool(getattr(model, "__soft_deletes__", False))

    pk_names = pk if isinstance(pk, list) else [pk]
    skip = set()

    # Timestamp / soft-delete columns are emitted via dedicated helpers.
    timestamps_present = has_timestamps and all(c in fields for c in _TIMESTAMP_COLUMNS)
    soft_deletes_present = has_soft_deletes and _SOFT_DELETE_COLUMN in fields
    if timestamps_present:
        skip.update(_TIMESTAMP_COLUMNS)
    if soft_deletes_present:
        skip.add(_SOFT_DELETE_COLUMN)

    lines: List[str] = []

    # Primary key first.
    if not isinstance(pk, list):
        if incrementing and key_type == "int":
            lines.append('table.id()' if pk == "id" else f'table.big_increments("{pk}")')
        elif pk in fields:
            method = _resolve_method(fields[pk].annotation)
            lines.append(_column_line(pk, method, nullable=False, default=PydanticUndefined, primary=True))
        skip.update(pk_names)

    # Remaining fields in declaration order.
    for name, field in fields.items():
        if name in skip:
            continue
        annotation = field.annotation
        _, optional = _unwrap_optional(annotation)
        method = _resolve_method(annotation)
        required = _field_is_required(field)
        default = _field_default(field)
        nullable = optional or (not required and default is None)
        default_for_render = default if (not required and default is not None) else PydanticUndefined
        lines.append(
            _column_line(name, method, nullable=nullable, default=default_for_render, primary=False)
        )

    # Composite primary key constraint.
    if isinstance(pk, list):
        cols = ", ".join(f'"{c}"' for c in pk)
        lines.append(f"table.primary([{cols}])")

    if timestamps_present:
        lines.append("table.timestamps()")
    if soft_deletes_present:
        lines.append("table.soft_deletes()")

    return lines


def _to_class_name(name: str) -> str:
    """Convert a migration name (snake_case) to a class name (PascalCase)."""
    import re

    parts = re.split(r"[_\-]", name)
    return "".join(part.capitalize() for part in parts if part)


def generate_create_migration(model: Type, name: Optional[str] = None) -> str:
    """Generate the full source of a create-table migration for a model.

    Args:
        model: A Pyloquent model class.
        name: Optional migration name (defaults to ``create_<table>_table``).

    Returns:
        Python source code for the migration file.
    """
    table = get_table_name(model)
    migration_name = name or f"create_{table}_table"
    class_name = _to_class_name(migration_name)
    lines = generate_create_lines(model)
    body = ",\n            ".join(lines)

    return f'''"""Migration for creating {table} table (generated from {model.__name__})."""

from pyloquent.migrations import Migration
from pyloquent.schema.builder import SchemaBuilder


class {class_name}(Migration):
    """Create the {table} table."""

    async def up(self, schema: SchemaBuilder) -> None:
        """Run the migration."""
        await schema.create("{table}", lambda table: [
            {body},
        ])

    async def down(self, schema: SchemaBuilder) -> None:
        """Reverse the migration."""
        await schema.drop("{table}")
'''


def diff_columns(model: Type, existing_columns: List[str]) -> Tuple[List[str], List[str]]:
    """Compute the column add/drop diff between a model and a live table.

    Args:
        model: A Pyloquent model class.
        existing_columns: Column names currently present in the database.

    Returns:
        A tuple of (columns_to_add, columns_to_drop) — both lists of names.
    """
    fields = dict(model.model_fields)
    model_columns = list(fields.keys())
    existing = set(existing_columns)

    to_add = [c for c in model_columns if c not in existing]
    to_drop = [c for c in existing_columns if c not in set(model_columns)]
    return to_add, to_drop


def generate_add_line(model: Type, name: str) -> str:
    """Build the Blueprint add-column line for a single model field."""
    field = model.model_fields[name]
    annotation = field.annotation
    _, optional = _unwrap_optional(annotation)
    method = _resolve_method(annotation)
    required = _field_is_required(field)
    default = _field_default(field)
    nullable = optional or (not required and default is None)
    default_for_render = default if (not required and default is not None) else PydanticUndefined
    return _column_line(name, method, nullable=nullable, default=default_for_render, primary=False)


def generate_diff_migration(
    model: Type,
    existing_columns: List[str],
    name: Optional[str] = None,
) -> str:
    """Generate an alter migration from a model-vs-database column diff.

    Args:
        model: A Pyloquent model class.
        existing_columns: Column names currently present in the database.
        name: Optional migration name.

    Returns:
        Python source code for the migration file.
    """
    table = get_table_name(model)
    to_add, to_drop = diff_columns(model, existing_columns)
    migration_name = name or f"update_{table}_table"
    class_name = _to_class_name(migration_name)

    up_lines: List[str] = [generate_add_line(model, c) for c in to_add]
    for col in to_drop:
        up_lines.append(f'table.drop_column("{col}")')

    down_lines: List[str] = [f'table.drop_column("{c}")' for c in to_add]

    up_body = ",\n            ".join(up_lines) if up_lines else "pass  # no changes detected"
    down_body = ",\n            ".join(down_lines) if down_lines else "pass"

    # When there are no statements, emit a bare callback that returns nothing.
    up_block = (
        f'await schema.table("{table}", lambda table: [\n            {up_body},\n        ])'
        if up_lines
        else "pass  # no changes detected"
    )
    down_block = (
        f'await schema.table("{table}", lambda table: [\n            {down_body},\n        ])'
        if down_lines
        else "pass"
    )

    return f'''"""Migration for updating {table} table (generated from {model.__name__} diff)."""

from pyloquent.migrations import Migration
from pyloquent.schema.builder import SchemaBuilder


class {class_name}(Migration):
    """Update the {table} table to match {model.__name__}."""

    async def up(self, schema: SchemaBuilder) -> None:
        """Run the migration."""
        {up_block}

    async def down(self, schema: SchemaBuilder) -> None:
        """Reverse the migration."""
        {down_block}
'''
