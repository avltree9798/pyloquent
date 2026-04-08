"""Custom SQL type system for Pyloquent models.

Provides a ``TypeDecorator`` base class that lets you attach custom
Python-to-database serialisation / deserialisation logic to any model field,
similar in spirit to SQLAlchemy's ``TypeDecorator``.

Example::

    import json
    from pyloquent.orm.type_decorator import TypeDecorator

    class JSONType(TypeDecorator):
        impl = "TEXT"

        def process_bind_param(self, value, dialect=None):
            if value is None:
                return None
            return json.dumps(value)

        def process_result_value(self, value, dialect=None):
            if value is None:
                return None
            return json.loads(value)

    class User(Model):
        __casts__ = {"settings": JSONType}

        id: Optional[int] = None
        name: str
        settings: Optional[dict] = None

Custom types registered in ``__casts__`` are applied automatically during
``_get_attributes_for_save()`` (outbound) and ``_cast_attribute()`` (inbound).
"""

from typing import Any, ClassVar, Optional, Type


_registry: dict[str, "TypeDecorator"] = {}


def register_type(name: str, instance: "TypeDecorator") -> None:
    """Register a TypeDecorator instance under a named alias.

    Args:
        name: Alias to use in ``__casts__``.
        instance: Instantiated TypeDecorator.
    """
    _registry[name] = instance


def get_type(name_or_cls: Any) -> Optional["TypeDecorator"]:
    """Resolve a ``__casts__`` value to a TypeDecorator instance.

    Accepts:
    - A string alias registered via ``register_type()``.
    - A TypeDecorator subclass (will be instantiated lazily).
    - An already-instantiated TypeDecorator.

    Args:
        name_or_cls: The cast specification from ``__casts__``.

    Returns:
        TypeDecorator instance or ``None`` if not a custom type.
    """
    if isinstance(name_or_cls, str):
        return _registry.get(name_or_cls)
    if isinstance(name_or_cls, TypeDecorator):
        return name_or_cls
    if isinstance(name_or_cls, type) and issubclass(name_or_cls, TypeDecorator):
        return name_or_cls()
    return None


class TypeDecorator:
    """Base class for custom column types.

    Subclass this and override :meth:`process_bind_param` and
    :meth:`process_result_value` to control how Python values are
    converted to / from database values.

    Class Attributes:
        impl: The underlying SQL type string (e.g. ``'TEXT'``, ``'INTEGER'``).
            Used only informatively; Pyloquent does not generate DDL from it.
    """

    impl: ClassVar[str] = "TEXT"

    def process_bind_param(self, value: Any, dialect: Optional[str] = None) -> Any:
        """Convert a Python value to the database representation.

        Called before the value is passed to the database driver.

        Args:
            value: The Python value from the model field.
            dialect: The database dialect string (e.g. ``'sqlite'``). May be
                ``None`` if dialect is unavailable.

        Returns:
            The serialised value to store in the database.
        """
        return value

    def process_result_value(self, value: Any, dialect: Optional[str] = None) -> Any:
        """Convert a database value back to its Python representation.

        Called after the value is retrieved from the database.

        Args:
            value: The raw value from the database row.
            dialect: The database dialect string.

        Returns:
            The deserialised Python value.
        """
        return value

    def __repr__(self) -> str:
        """Return a human-readable representation."""
        return f"{self.__class__.__name__}(impl={self.impl!r})"


# ---------------------------------------------------------------------------
# Built-in convenience types
# ---------------------------------------------------------------------------

class JSONType(TypeDecorator):
    """Serialise/deserialise Python dicts and lists as JSON TEXT columns."""

    impl = "TEXT"

    def process_bind_param(self, value: Any, dialect: Optional[str] = None) -> Any:
        """Serialise to JSON string.

        Args:
            value: Python object.
            dialect: Dialect name.

        Returns:
            JSON string or None.
        """
        if value is None:
            return None
        if isinstance(value, str):
            return value
        import json
        return json.dumps(value)

    def process_result_value(self, value: Any, dialect: Optional[str] = None) -> Any:
        """Deserialise from JSON string.

        Args:
            value: JSON string from database.
            dialect: Dialect name.

        Returns:
            Python object or None.
        """
        if value is None:
            return None
        if isinstance(value, str):
            import json
            return json.loads(value)
        return value


class CommaSeparatedType(TypeDecorator):
    """Serialise/deserialise Python lists as comma-separated TEXT columns."""

    impl = "TEXT"

    def process_bind_param(self, value: Any, dialect: Optional[str] = None) -> Any:
        """Serialise list to comma-separated string.

        Args:
            value: Python list.
            dialect: Dialect name.

        Returns:
            Comma-separated string or None.
        """
        if value is None:
            return None
        if isinstance(value, (list, tuple)):
            return ",".join(str(v) for v in value)
        return value

    def process_result_value(self, value: Any, dialect: Optional[str] = None) -> Any:
        """Deserialise comma-separated string to list.

        Args:
            value: Comma-separated string.
            dialect: Dialect name.

        Returns:
            Python list or None.
        """
        if value is None:
            return None
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        return value


# Register built-ins
register_type("json", JSONType())
register_type("comma_separated", CommaSeparatedType())
