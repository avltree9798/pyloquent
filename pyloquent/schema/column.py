"""Column definition for schema builder."""

from dataclasses import dataclass
from typing import Any, List, Optional


# Sentinel meaning "enable this flag" when a boolean modifier is called with
# no explicit value, e.g. ``table.string("email").unique()``.
_ON = object()


class _FluentValue:
    """Callable stand-in returned when a fluent modifier has not been set.

    Evaluates to the modifier's default value in boolean / equality contexts
    (so grammars can keep using ``if not column.nullable``), and applies the
    modifier — returning the owning :class:`Column` — when called.
    """

    __slots__ = ("_column", "_name", "_default", "_flag")

    def __init__(self, column: "Column", name: str, default: Any, flag: bool):
        self._column = column
        self._name = name
        self._default = default
        self._flag = flag

    def __call__(self, value: Any = _ON) -> "Column":
        if value is _ON:
            resolved: Any = True if self._flag else None
        else:
            resolved = value
        setattr(self._column, self._name, resolved)
        return self._column

    def __bool__(self) -> bool:
        return bool(self._default)

    def __eq__(self, other: Any) -> bool:
        return self._default == other

    def __ne__(self, other: Any) -> bool:
        return self._default != other

    def __hash__(self) -> int:
        return hash(self._default)

    def __repr__(self) -> str:
        return repr(self._default)


class _FluentDescriptor:
    """Non-data descriptor backing a fluent column modifier.

    A single attribute name serves two purposes:

    * **Read** — ``column.nullable`` returns the stored value so grammars can
      test truthiness (``if not column.nullable``) or read a value (``default``).
    * **Chaining** — ``column.nullable()`` sets the modifier and returns the
      owning :class:`Column`, enabling Laravel-style fluent definitions such as
      ``table.string("email").unique().nullable()``.

    Because this is a *non-data* descriptor (no ``__set__``), a direct
    assignment (``column.nullable = True``) or a value supplied at construction
    time transparently shadows the descriptor with a plain attribute on the
    instance, so reads such as ``column.nullable is True`` behave as expected.
    """

    def __init__(self, default: Any, *, flag: bool = True) -> None:
        self._default = default
        self._flag = flag

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    def __get__(self, instance: Optional["Column"], owner: Optional[type] = None):
        if instance is None:
            return self
        return _FluentValue(instance, self._name, self._default, self._flag)


class Column:
    """Represents a column in a database table.

    Modifiers may be supplied either as keyword arguments at construction time
    (``Column(name="x", type="string", nullable=False)``) or fluently by
    chaining method calls (``table.string("x").nullable(False)``).
    """

    # Boolean flag modifiers (read as truthy/falsy, set via chaining).
    nullable = _FluentDescriptor(True)
    unsigned = _FluentDescriptor(False)
    primary = _FluentDescriptor(False)
    auto_increment = _FluentDescriptor(False)
    unique = _FluentDescriptor(False)
    index = _FluentDescriptor(False)
    first = _FluentDescriptor(False)
    change = _FluentDescriptor(False)

    # Value modifiers (read as their value, default None).
    default = _FluentDescriptor(None, flag=False)
    comment = _FluentDescriptor(None, flag=False)
    after = _FluentDescriptor(None, flag=False)
    charset = _FluentDescriptor(None, flag=False)
    collation = _FluentDescriptor(None, flag=False)
    virtual_as = _FluentDescriptor(None, flag=False)
    stored_as = _FluentDescriptor(None, flag=False)
    srid = _FluentDescriptor(None, flag=False)

    def __init__(
        self,
        name: str,
        type: str,
        *,
        length: Optional[int] = None,
        precision: Optional[int] = None,
        scale: Optional[int] = None,
        allowed: Optional[List[str]] = None,
        **modifiers: Any,
    ) -> None:
        self.name = name
        self.type = type
        self.length = length
        self.precision = precision
        self.scale = scale
        # For enum/set types.
        self.allowed: List[str] = list(allowed) if allowed is not None else []
        # Any modifier passed at construction shadows the descriptor with a
        # plain instance attribute holding the concrete value.
        for key, value in modifiers.items():
            setattr(self, key, value)

    def to_sql(self, grammar: "Grammar") -> str:
        """Convert column to SQL.

        Args:
            grammar: Grammar instance

        Returns:
            SQL string for column definition
        """
        return grammar._compile_column(self)


@dataclass
class Index:
    """Represents a table index."""

    name: str
    columns: List[str]
    unique: bool = False
    primary: bool = False
    fulltext: bool = False
    spatial: bool = False
    algorithm: Optional[str] = None


@dataclass
class ForeignKey:
    """Represents a foreign key constraint."""

    name: str
    columns: List[str]
    referenced_table: str
    referenced_columns: List[str]
    on_delete: Optional[str] = None
    on_update: Optional[str] = None
