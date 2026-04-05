"""Has-Many-Through relation implementation."""

from typing import TYPE_CHECKING, Any, Type

from pyloquent.orm.collection import Collection
from pyloquent.orm.relations.relation import Relation, T

if TYPE_CHECKING:  # pragma: no cover
    from pyloquent.orm.model import Model
    from pyloquent.query.builder import QueryBuilder


class HasManyThrough(Relation[T]):
    """Has-many-through relationship (e.g., Country -> User -> Post).

    Example:
        class Country(Model):
            def posts(self):
                return self.has_many_through(Post, User)
    """

    def __init__(
        self,
        parent: "Model",
        related: Type[T],
        through: Type["Model"],
        first_key: str,
        second_key: str,
        local_key: str,
        second_local_key: str,
    ):
        """Initialize the has-many-through relation.

        Args:
            parent: The parent model instance
            related: The final related model class
            through: The intermediate model class
            first_key: FK on through model pointing to parent
            second_key: FK on related model pointing to through model
            local_key: Local key on parent model
            second_local_key: Local key on through model
        """
        super().__init__(parent, related, second_key, local_key)
        self.through = through
        self.first_key = first_key
        self.second_key = second_key
        self.second_local_key = second_local_key

    def add_constraints(self) -> None:
        """Add the through-join constraints."""
        pass

    def _create_query(self) -> "QueryBuilder[T]":
        through_table = getattr(self.through, "__table__", None) or self.through._get_default_table_name()
        related_table = getattr(self.related, "__table__", None) or self.related._get_default_table_name()
        parent_value = getattr(self.parent, self.local_key)

        query = self.related.query
        query = query.join(
            through_table,
            f"{related_table}.{self.second_key}",
            "=",
            f"{through_table}.{self.second_local_key}",
        )
        query = query.where(f"{through_table}.{self.first_key}", parent_value)
        return query

    async def get_results(self) -> Collection[T]:
        """Get all related models through the intermediate.

        Returns:
            Collection of related models
        """
        return await self.query.get()

    async def create(self, attributes: dict) -> T:
        """Create a related model via the through model.

        Args:
            attributes: Model attributes

        Returns:
            Created model
        """
        through_instance = await self.through.create({
            self.first_key: getattr(self.parent, self.local_key)
        })
        attributes[self.second_key] = getattr(through_instance, self.second_local_key)
        return await self.related.create(attributes)
