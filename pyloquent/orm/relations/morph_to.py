"""Morph-To relationship implementation (polymorphic inverse)."""

from typing import TYPE_CHECKING, Any, Optional, Type

from pyloquent.orm.relations.relation import Relation, T

if TYPE_CHECKING:  # pragma: no cover
    from pyloquent.orm.model import Model


class MorphTo(Relation[T]):
    """Polymorphic inverse relationship.

    This class represents a polymorphic relationship where the parent
    model belongs to one of multiple related models based on a type field.

    Example:
        class Comment(Model):
            def commentable(self):
                return self.morph_to('commentable')

        class Post(Model):
            def comments(self):
                return self.morph_many(Comment, 'commentable')

        class Video(Model):
            def comments(self):
                return self.morph_many(Comment, 'commentable')

        # Usage
        comment = await Comment.find(1)
        parent = await comment.commentable().get()  # Could be Post or Video
    """

    def __init__(
        self,
        parent: "Model",
        name: str,
        type_column: Optional[str] = None,
        id_column: Optional[str] = None,
        owner_key: Optional[str] = None,
    ):
        """Initialize the morph-to relation.

        Args:
            parent: The parent model instance
            name: Relationship name
            type_column: Column storing the related model class
            id_column: Column storing the related model ID
            owner_key: Key on related model
        """
        # We'll determine the related model dynamically
        super().__init__(parent, None, "", "")  # type: ignore

        self.name = name
        self.type_column = type_column or f"{name}_type"
        self.id_column = id_column or f"{name}_id"
        self.owner_key = owner_key or "id"

        # Get the related model class from the type column
        self._related_class = self._get_related_class()

    def _get_related_class(self) -> Optional[Type[T]]:
        """Get the related model class from the type column.

        Returns:
            Model class or None
        """
        type_value = getattr(self.parent, self.type_column, None)
        if not type_value:
            return None

        # type_value should be a fully qualified class name
        # e.g., "app.models.Post" or "models.Post"
        try:
            parts = type_value.rsplit(".", 1)
            if len(parts) == 2:
                module_name, class_name = parts
                import importlib

                module = importlib.import_module(module_name)
                return getattr(module, class_name)
            else:
                # Try to find in globals
                return globals().get(type_value)
        except (ImportError, AttributeError):
            return None

    def _create_query(self) -> "QueryBuilder[T]":
        """Create query for the resolved related model class."""
        if self._related_class:
            return self._related_class.query
        from pyloquent.query.builder import QueryBuilder
        from pyloquent.grammars.sqlite_grammar import SQLiteGrammar
        return QueryBuilder(SQLiteGrammar())

    def add_constraints(self) -> None:
        """Add constraints to the query."""
        if self._related_class:
            id_value = getattr(self.parent, self.id_column)
            self._query = self._query.where(self.owner_key, id_value)

    async def get_results(self) -> Optional[T]:
        """Get the related model.

        Returns:
            Related model or None
        """
        if not self._related_class:
            return None

        return await self.query.first()

    def associate(self, model: T) -> "Model":
        """Associate a model with the parent.

        Args:
            model: Model to associate

        Returns:
            Parent model
        """
        setattr(self.parent, self.type_column, model.__class__.__name__)
        setattr(self.parent, self.id_column, getattr(model, self.owner_key))

        return self.parent

    def dissociate(self) -> "Model":
        """Dissociate the related model.

        Returns:
            Parent model
        """
        setattr(self.parent, self.type_column, None)
        setattr(self.parent, self.id_column, None)

        return self.parent

    def get_related_type(self) -> Optional[str]:
        """Get the related model type.

        Returns:
            Type string or None
        """
        return getattr(self.parent, self.type_column, None)

    def get_related_id(self) -> Any:
        """Get the related model ID.

        Returns:
            ID value
        """
        return getattr(self.parent, self.id_column, None)
