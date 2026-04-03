"""Morph-Many relationship implementation (polymorphic one-to-many)."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type

from pyloquent.orm.collection import Collection
from pyloquent.orm.relations.relation import Relation, T

if TYPE_CHECKING:
    from pyloquent.orm.model import Model


class MorphMany(Relation[T]):
    """Polymorphic one-to-many relationship.

    This class represents a polymorphic relationship where the parent
    model can have many related models of different types.

    Example:
        class Post(Model):
            def comments(self):
                return self.morph_many(Comment, 'commentable')

        class Video(Model):
            def comments(self):
                return self.morph_many(Comment, 'commentable')

        class Comment(Model):
            def commentable(self):
                return self.morph_to('commentable')

        # Usage
        post = await Post.find(1)
        comments = await post.comments().get()

        # Create with polymorphic fields set automatically
        comment = await post.comments().create({
            'body': 'Great post!'
        })
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
        """Initialize the morph-many relation.

        Args:
            parent: The parent model instance
            related: The related model class
            name: Relationship name (e.g., 'commentable')
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

    async def get_results(self) -> Collection[T]:
        """Get the related models.

        Returns:
            Collection of related models
        """
        return await self.query.get()

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

    async def save_many(self, models: Collection[T]) -> Collection[T]:
        """Save multiple models.

        Args:
            models: Models to save

        Returns:
            Collection of saved models
        """
        saved = []
        for model in models:
            saved.append(await self.save(model))
        return Collection(saved)

    async def create_many(self, attributes_list: List[Dict[str, Any]]) -> Collection[T]:
        """Create multiple related models.

        Args:
            attributes_list: List of attribute dictionaries

        Returns:
            Collection of created models
        """
        created = []
        for attributes in attributes_list:
            created.append(await self.create(attributes))
        return Collection(created)

    def find(self, id: Any) -> Any:
        """Find a related model by ID.

        Args:
            id: Model ID

        Returns:
            Coroutine that resolves to model or None
        """
        return self.query.where(self.related.__primary_key__, id).first()

    def find_many(self, ids: List[Any]) -> Any:
        """Find multiple related models by ID.

        Args:
            ids: List of model IDs

        Returns:
            Coroutine that resolves to Collection
        """
        return self.query.where_in(self.related.__primary_key__, ids).get()

    async def delete(self) -> int:
        """Delete all related models.

        Returns:
            Number of deleted models
        """
        return await self.query.delete_all()

    async def update(self, attributes: Dict[str, Any]) -> int:
        """Update all related models.

        Args:
            attributes: Attributes to update

        Returns:
            Number of updated models
        """
        return await self.query.update_all(attributes)
