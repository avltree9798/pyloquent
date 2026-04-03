"""Type definitions for Pyloquent."""

from typing import (
    Any,
    AsyncIterator,
    Callable,
    Coroutine,
    Dict,
    List,
    Optional,
    TypeVar,
    Union,
)

# Generic type variable for models
T = TypeVar("T")
ModelType = TypeVar("ModelType", bound="Model")

# Query result types
BindingValue = Union[str, int, float, bool, None]
Bindings = Dict[str, List[BindingValue]]
QueryResult = List[Dict[str, Any]]
SingleResult = Optional[Dict[str, Any]]

# Callback types
WhereCallback = Callable[["QueryBuilder"], None]
ScopeCallback = Callable[["QueryBuilder"], "QueryBuilder"]

# Relation types
RelationValue = Union[List[Any], Optional[Any]]

# Import types that reference other modules
from pyloquent.orm import Model  # noqa: E402
from pyloquent.query import QueryBuilder  # noqa: E402

__all__ = [
    "Any",
    "AsyncIterator",
    "BindingValue",
    "Bindings",
    "Callable",
    "Coroutine",
    "Dict",
    "List",
    "Model",
    "ModelType",
    "Optional",
    "QueryBuilder",
    "QueryResult",
    "RelationValue",
    "ScopeCallback",
    "SingleResult",
    "T",
    "WhereCallback",
]
