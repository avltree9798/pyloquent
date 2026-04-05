"""Has-One-Through relation implementation."""

from typing import TYPE_CHECKING, Any, Optional, Type

from pyloquent.orm.relations.relation import Relation, T

if TYPE_CHECKING:  # pragma: no cover
    from pyloquent.orm.model import Model
    from pyloquent.query.builder import QueryBuilder


class HasOneThrough(Relation[T]):
    """Has-one-through relationship (e.g., Country -> User -> Phone).

    Example:
        class Country(Model):
            def phone(self):
                return self.has_one_through(Phone, User)
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
        """Initialize the has-one-through relation.

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

    async def get_results(self) -> Optional[T]:
        """Get the single related model through the intermediate.

        Returns:
            Related model or None
        """
        return await self.query.first()
