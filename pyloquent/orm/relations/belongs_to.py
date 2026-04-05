"""Belongs-To relation implementation."""

from typing import TYPE_CHECKING, Any, Optional, Type

from pyloquent.orm.relations.relation import Relation, T

if TYPE_CHECKING:  # pragma: no cover
    from pyloquent.orm.model import Model


class BelongsTo(Relation[T]):
    """Inverse of has-many relationship.

    This class represents a belongs-to relationship where
    the parent model belongs to a single related model.

    Example:
        class Post(Model):
            def author(self):
                return self.belongs_to(User)

        # Usage
        post = await Post.find(1)
        author = await post.author().get()
        print(author.name)
    """

    def __init__(
        self,
        parent: "Model",
        related: Type[T],
        foreign_key: str,
        owner_key: str,
    ):
        """Initialize the belongs-to relation.

        Args:
            parent: The parent model instance
            related: The related model class
            foreign_key: Foreign key on the parent model
            owner_key: Key on the related model
        """
        super().__init__(parent, related, foreign_key, owner_key)
        # In belongs-to, foreign_key is on parent, local_key is on related
        self.owner_key = owner_key

    def add_constraints(self) -> None:
        """Add constraints: WHERE related.owner_key = parent.foreign_key."""
        foreign_value = getattr(self.parent, self.foreign_key)
        self._query = self._query.where(self.owner_key, foreign_value)

    async def get_results(self) -> Optional[T]:
        """Get the related model.

        Returns:
            Related model or None
        """
        return await self.query.first()

    async def associate(self, model: T) -> "Model":
        """Associate a model with the parent.

        Sets the foreign key on the parent to the related model's key.

        Args:
            model: Model to associate

        Returns:
            The parent model
        """
        # Set the foreign key on the parent
        setattr(self.parent, self.foreign_key, getattr(model, self.owner_key))

        # Save the parent
        await self.parent.save()

        return self.parent

    async def dissociate(self) -> "Model":
        """Dissociate the related model.

        Sets the foreign key on the parent to None.

        Returns:
            The parent model
        """
        # Set the foreign key to None
        setattr(self.parent, self.foreign_key, None)

        # Save the parent
        await self.parent.save()

        return self.parent

    def get_parent_key(self) -> Any:
        """Get the foreign key value from the parent.

        Returns:
            Foreign key value
        """
        return getattr(self.parent, self.foreign_key)

    def get_related_key(self) -> str:
        """Get the owner key name on the related model.

        Returns:
            Owner key name
        """
        return self.owner_key
