"""Morph-One relationship implementation (polymorphic one-to-one)."""

from typing import TYPE_CHECKING, Any, Dict, Optional, Type

from pyloquent.orm.relations.relation import Relation, T

if TYPE_CHECKING:  # pragma: no cover
    from pyloquent.orm.model import Model


class MorphOne(Relation[T]):
    """Polymorphic one-to-one relationship.

    This class represents a polymorphic relationship where the parent
    model has one related model of a specific type.

    Example:
        class User(Model):
            def image(self):
                return self.morph_one(Image, 'imageable')

        class Post(Model):
            def image(self):
                return self.morph_one(Image, 'imageable')

        class Image(Model):
            def imageable(self):
                return self.morph_to('imageable')

        # Usage
        user = await User.find(1)
        image = await user.image().get()
    """

    def __init__(
        self,
        parent: "Model",
        related: Type[T],
        name: str,
        type_column: Optional[str] = None,
        id_column: Optional[str] = None,
        local_key: Optional[str] = None,
    ):
        """Initialize the morph-one relation.

        Args:
            parent: The parent model instance
            related: The related model class
            name: Relationship name
            type_column: Column storing the parent model class
            id_column: Column storing the parent model ID
            local_key: Local key on parent model
        """
        super().__init__(parent, related, "", "")

        self.name = name
        self.type_column = type_column or f"{name}_type"
        self.id_column = id_column or f"{name}_id"
        self.local_key = local_key or parent.__primary_key__

    def add_constraints(self) -> None:
        """Add constraints for the polymorphic relationship."""
        parent_type = self.parent.__class__.__name__
        parent_id = getattr(self.parent, self.local_key)

        self._query = self._query.where(self.type_column, parent_type)
        self._query = self._query.where(self.id_column, parent_id)

    async def get_results(self) -> Optional[T]:
        """Get the related model.

        Returns:
            Related model or None
        """
        return await self.query.first()

    async def create(self, attributes: Dict[str, Any]) -> T:
        """Create a new related model with polymorphic fields set.

        Args:
            attributes: Model attributes

        Returns:
            Created model
        """
        # Set polymorphic fields
        attributes[self.type_column] = self.parent.__class__.__name__
        attributes[self.id_column] = getattr(self.parent, self.local_key)

        # Create the model
        return await self.related.create(attributes)

    async def save(self, model: T) -> T:
        """Save an existing model with polymorphic fields set.

        Args:
            model: Model to save

        Returns:
            Saved model
        """
        # Set polymorphic fields
        setattr(model, self.type_column, self.parent.__class__.__name__)
        setattr(model, self.id_column, getattr(self.parent, self.local_key))

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
