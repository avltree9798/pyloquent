"""Has-One relation implementation."""

from typing import TYPE_CHECKING, Any, Dict, Optional, Type

from pyloquent.orm.relations.relation import Relation, T

if TYPE_CHECKING:  # pragma: no cover
    from pyloquent.orm.model import Model


class HasOne(Relation[T]):
    """One-to-one relationship.

    This class represents a one-to-one relationship where
    the parent model has one related model.

    Example:
        class User(Model):
            def profile(self):
                return self.has_one(Profile)

        # Usage
        user = await User.find(1)
        profile = await user.profile().get()
        print(profile.bio)
    """

    def __init__(
        self,
        parent: "Model",
        related: Type[T],
        foreign_key: str,
        local_key: str,
    ):
        """Initialize the has-one relation.

        Args:
            parent: The parent model instance
            related: The related model class
            foreign_key: Foreign key on the related model
            local_key: Local key on the parent model
        """
        super().__init__(parent, related, foreign_key, local_key)

    def add_constraints(self) -> None:
        """Add constraints: WHERE foreign_key = parent.local_key."""
        local_value = getattr(self.parent, self.local_key)
        self._query = self._query.where(self.foreign_key, local_value)

    async def get_results(self) -> Optional[T]:
        """Get the related model.

        Returns:
            Related model or None
        """
        return await self.query.first()

    async def create(self, attributes: Dict[str, Any]) -> T:
        """Create a new related model.

        Args:
            attributes: Model attributes

        Returns:
            Created model
        """
        # Set the foreign key
        attributes[self.foreign_key] = getattr(self.parent, self.local_key)

        # Create the model
        return await self.related.create(attributes)

    async def save(self, model: T) -> T:
        """Save an existing model with the foreign key set.

        Args:
            model: Model to save

        Returns:
            Saved model
        """
        # Set the foreign key
        setattr(model, self.foreign_key, getattr(self.parent, self.local_key))

        # Save the model
        return await model.save()

    async def delete(self) -> bool:
        """Delete the related model.

        Returns:
            True if deleted
        """
        model = await self.get_results()
        if model:
            return await model.delete()
        return False

    async def update(self, attributes: Dict[str, Any]) -> int:
        """Update the related model.

        Args:
            attributes: Attributes to update

        Returns:
            Number of updated models (0 or 1)
        """
        return await self.query.update_all(attributes)
