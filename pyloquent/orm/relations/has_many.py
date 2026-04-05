"""Has-Many relation implementation."""

from typing import TYPE_CHECKING, Any, Dict, Type

from pyloquent.orm.collection import Collection
from pyloquent.orm.relations.relation import Relation, T

if TYPE_CHECKING:  # pragma: no cover
    from pyloquent.orm.model import Model


class HasMany(Relation[T]):
    """One-to-many relationship.

    This class represents a one-to-many relationship where
    the parent model has many related models.

    Example:
        class User(Model):
            def posts(self):
                return self.has_many(Post)

        # Usage
        user = await User.find(1)
        posts = await user.posts().get()
        for post in posts:
            print(post.title)
    """

    def __init__(
        self,
        parent: "Model",
        related: Type[T],
        foreign_key: str,
        local_key: str,
    ):
        """Initialize the has-many relation.

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

    async def get_results(self) -> Collection[T]:
        """Get the related models.

        Returns:
            Collection of related models
        """
        return await self.query.get()

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

    async def create_many(self, attributes_list: list) -> Collection[T]:
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

    def find_many(self, ids: list) -> Any:
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
