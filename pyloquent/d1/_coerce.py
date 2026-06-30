"""Coerce Python values into Cloudflare D1-compatible bind parameters.

Cloudflare D1 accepts only ``NULL``, numbers, strings, booleans and
``ArrayBuffer`` as bound parameters. Other Python objects are passed straight
through to the underlying layer — and rejected:

* **Binding driver (Workers/Pyodide):** Pyodide converts a Python ``datetime``
  to a JS ``Date``, so D1 raises
  ``D1_TYPE_ERROR: Type 'object' not supported for value 'Tue Jun 30 2026 …'``.
* **HTTP driver:** the value is placed in the JSON request body, so a
  ``datetime`` raises ``TypeError: Object of type datetime is not JSON
  serializable``.

This conversion is **D1-specific** and deliberately lives in the D1 layer, not
the model: other drivers keep native objects (asyncpg, for example, *requires*
real ``datetime`` values for ``timestamptz`` columns, and aiosqlite adapts them
itself).
"""
from __future__ import annotations

import datetime as _datetime
import decimal as _decimal
import enum as _enum
import json as _json
import uuid as _uuid
from typing import Any, List, Optional


def to_d1_value(value: Any) -> Any:
    """Coerce a single bind parameter into a D1-safe primitive.

    Args:
        value: A raw bind parameter.

    Returns:
        A value D1 can bind (``None`` / ``str`` / ``int`` / ``float`` /
        ``bool``), or the value unchanged when it is already safe.
    """
    # Already a D1-native primitive (bool is a subclass of int).
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    # datetime is a subclass of date; both (and time) serialise via isoformat.
    if isinstance(value, (_datetime.datetime, _datetime.date, _datetime.time)):
        return value.isoformat()
    if isinstance(value, _decimal.Decimal):
        return str(value)
    if isinstance(value, _uuid.UUID):
        return str(value)
    if isinstance(value, _enum.Enum):
        return to_d1_value(value.value)
    if isinstance(value, (dict, list, tuple)):
        return _json.dumps(value, default=str)
    return value


def to_d1_params(params: Optional[List[Any]]) -> Optional[List[Any]]:
    """Coerce a list of bind parameters; ``None`` / empty passes through.

    Args:
        params: List of bind parameters, or ``None``.

    Returns:
        A new list with each value coerced, or the original falsy value.
    """
    if not params:
        return params
    return [to_d1_value(p) for p in params]
