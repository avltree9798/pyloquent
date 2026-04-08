"""Base relation class."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Generic, Optional, Type, TypeVar

from pyloquent.query.builder import QueryBuilder, _UNSET

if TYPE_CHECKING:  # pragma: no cover
    from pyloquent.orm.collection import Collection
    from pyloquent.orm.model import Model

T = TypeVar("T", bound="Model")


class Relation(ABC, Generic[T]):
    """Base class for all relations.

    This class provides common functionality for all relationship types
    and defines the interface that specific relations must implement.
    """

    def __init__(
        self,
        parent: "Model",
        related: Type[T],
        foreign_key: str,
        local_key: str,
    ):
        """Initialize the relation.

        Args:
            parent: The parent model instance
            related: The related model class
            foreign_key: The foreign key column
            local_key: The local key column
        """
        self.parent = parent
        self.related = related
        self.foreign_key = foreign_key
        self.local_key = local_key
        self._query: Optional[QueryBuilder[T]] = None

    @property
    def query(self) -> QueryBuilder[T]:
        """Get the query builder for this relation.

        Returns:
            QueryBuilder instance
        """
        if self._query is None:
            self._query = self._create_query()
            self.add_constraints()
        return self._query

    def _create_query(self) -> QueryBuilder[T]:
        """Create a query builder for the related model.

        Returns:
            QueryBuilder instance
        """
        return self.related.query

    @abstractmethod
    def add_constraints(self) -> None:
        """Add base constraints to the relation query.

        This method should add the default WHERE clause(s) that
        define the relationship.
        """
        pass

    @abstractmethod
    async def get_results(self) -> Any:
        """Get the results of the relationship.

        Returns:
            Collection for has-many, Model or None for belongs-to
        """
        pass

    async def get(self) -> Any:
        """Execute the relation query and get results.

        Returns:
            Relationship results
        """
        return await self.get_results()

    async def first(self) -> Optional[T]:
        """Get the first result of the relation.

        Returns:
            First related model or None
        """
        return await self.query.first()

    async def count(self) -> int:
        """Count the related models.

        Returns:
            Count of related models
        """
        return await self.query.count()

    def where(self, column: str, operator: Any = None, value: Any = _UNSET) -> QueryBuilder[T]:
        """Add a where clause to the relation query.

        Args:
            column: Column name
            operator: Comparison operator or value
            value: Value to compare

        Returns:
            QueryBuilder instance for chaining
        """
        return self.query.where(column, operator, value)

    def order_by(self, column: str, direction: str = "asc") -> QueryBuilder[T]:
        """Add an order by clause to the relation query.

        Args:
            column: Column name
            direction: Sort direction

        Returns:
            QueryBuilder instance for chaining
        """
        return self.query.order_by(column, direction)

    def limit(self, value: int) -> QueryBuilder[T]:
        """Set a limit on the relation query.

        Args:
            value: Maximum number of results

        Returns:
            QueryBuilder instance for chaining
        """
        return self.query.limit(value)

    async def chunk(self, count: int):
        """Chunk the relation results.

        Args:
            count: Chunk size

        Yields:
            Chunks of related models
        """
        async for chunk in self.query.chunk(count):
            yield chunk

    def __call__(self) -> QueryBuilder[T]:
        """Allow the relation to be called like a method.

        Returns:
            QueryBuilder instance
        """
        return self.query
