"""Query expression classes for building SQL queries."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Union

if TYPE_CHECKING:  # pragma: no cover
    from pyloquent.query.builder import QueryBuilder


@dataclass
class WhereClause:
    """Represents a WHERE clause in a query."""

    column: str
    operator: Optional[str] = None
    value: Any = None
    boolean: str = "and"  # "and" or "or"
    type: str = "basic"  # "basic", "in", "not_in", "between", "not_between", "null", "not_null", "nested", "raw"

    # For nested queries
    query: Optional["QueryBuilder"] = None

    # For raw where clauses
    sql: Optional[str] = None
    bindings: List[Any] = field(default_factory=list)

    def __post_init__(self):
        """Validate the where clause after initialisation."""
        if self.type == "basic" and self.operator is None:
            raise ValueError("Operator is required for basic where clauses")


@dataclass
class JoinClause:
    """Represents a JOIN clause in a query."""

    table: str
    type: str  # "inner", "left", "right", "cross"
    conditions: List["JoinCondition"] = field(default_factory=list)

    def add_condition(
        self, first: str, operator: str, second: str, boolean: str = "and"
    ) -> "JoinClause":
        """Add a condition to the join.

        Args:
            first: First column
            operator: Comparison operator
            second: Second column
            boolean: Boolean connector (and/or)

        Returns:
            Self for chaining
        """
        self.conditions.append(JoinCondition(first, operator, second, boolean))
        return self

    def on(self, first: str, operator: str, second: str) -> "JoinClause":
        """Add an AND ON condition.

        Args:
            first: First column
            operator: Comparison operator
            second: Second column

        Returns:
            Self for chaining
        """
        return self.add_condition(first, operator, second, boolean="and")

    def or_on(self, first: str, operator: str, second: str) -> "JoinClause":
        """Add an OR ON condition.

        Args:
            first: First column
            operator: Comparison operator
            second: Second column

        Returns:
            Self for chaining
        """
        return self.add_condition(first, operator, second, boolean="or")


@dataclass
class JoinCondition:
    """Represents a condition within a JOIN clause."""

    first: str
    operator: str
    second: str
    boolean: str = "and"  # "and" or "or"


@dataclass
class OrderClause:
    """Represents an ORDER BY clause."""

    column: str
    direction: str = "asc"  # "asc" or "desc"

    def __post_init__(self):
        """Normalize direction to lowercase."""
        self.direction = self.direction.lower()
        if self.direction not in ("asc", "desc"):
            raise ValueError(f"Invalid order direction: {self.direction}")


@dataclass
class HavingClause:
    """Represents a HAVING clause."""

    column: str
    operator: str
    value: Any
    boolean: str = "and"  # "and" or "or"


@dataclass
class Aggregate:
    """Represents an aggregate function (COUNT, MAX, MIN, etc.)."""

    function: str  # "count", "max", "min", "sum", "avg"
    column: str

    def __post_init__(self):
        """Normalize function name to lowercase."""
        self.function = self.function.lower()
        if self.function not in ("count", "max", "min", "sum", "avg"):
            raise ValueError(f"Invalid aggregate function: {self.function}")


@dataclass
class RawExpression:
    """Represents a raw SQL expression."""

    sql: str
    bindings: List[Any] = field(default_factory=list)


@dataclass
class CteClause:
    """Represents a Common Table Expression (WITH clause)."""

    name: str
    query: "QueryBuilder"
    recursive: bool = False
    recursive_union_all: bool = True


@dataclass
class WindowFrame:
    """Represents a window frame specification (ROWS/RANGE BETWEEN ...)."""

    mode: str = "ROWS"  # "ROWS" or "RANGE" or "GROUPS"
    start: str = "UNBOUNDED PRECEDING"
    end: str = "CURRENT ROW"


@dataclass
class WindowExpression:
    """Represents an OVER () window function expression."""

    function: str
    args: List[Any] = field(default_factory=list)
    partition_by: List[str] = field(default_factory=list)
    order_by: List["OrderClause"] = field(default_factory=list)
    frame: Optional[WindowFrame] = None
    alias: Optional[str] = None


@dataclass
class JoinRaw:
    """Represents a raw JOIN clause."""

    sql: str
    bindings: List[Any] = field(default_factory=list)


@dataclass
class SubqueryJoin:
    """Represents a subquery JOIN clause."""

    subquery: "QueryBuilder"
    alias: str
    first: str
    operator: str
    second: str
    type: str = "inner"
