"""Base model class for Pyloquent ORM."""

from typing import (
    Any,
    ClassVar,
    Dict,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
    get_type_hints,
)

from pydantic import BaseModel, ConfigDict, PrivateAttr

from pyloquent.exceptions import MassAssignmentException, ModelNotFoundException
from pyloquent.orm.collection import Collection
from pyloquent.orm.model_meta import ModelMeta
from pyloquent.query.builder import QueryBuilder, _UNSET

T = TypeVar("T", bound="Model")


class Model(BaseModel, metaclass=ModelMeta):
    """Base model class with Eloquent-style Active Record functionality.

    This class combines Pydantic's validation with Eloquent's
    Active Record pattern for database operations.

    Example:
        class User(Model):
            __table__ = 'users'
            __fillable__ = ['name', 'email']

            id: Optional[int] = None
            name: str
            email: str

        # Create
        user = await User.create({'name': 'John', 'email': 'john@example.com'})

        # Read
        user = await User.find(1)
        users = await User.where('active', True).get()

        # Update
        user.name = 'Jane'
        await user.save()

        # Delete
        await user.delete()
    """

    # ========================================================================
    # Model Configuration (class-level)
    # ========================================================================

    __table__: ClassVar[Optional[str]] = None
    __fillable__: ClassVar[List[str]] = []
    __guarded__: ClassVar[List[str]] = ["id"]
    __hidden__: ClassVar[List[str]] = []
    __visible__: ClassVar[List[str]] = []
    __appends__: ClassVar[List[str]] = []
    __casts__: ClassVar[Dict[str, str]] = {}
    __timestamps__: ClassVar[bool] = True
    __connection__: ClassVar[Optional[str]] = None
    __primary_key__: ClassVar[Union[str, List[str]]] = "id"
    __incrementing__: ClassVar[bool] = True
    __key_type__: ClassVar[str] = "int"
    __with__: ClassVar[List[str]] = []
    __per_page__: ClassVar[int] = 15
    __discriminator__: ClassVar[Optional[str]] = None
    __discriminator_value__: ClassVar[Optional[Any]] = None

    # Event dispatcher reference (class-level)
    _dispatcher: ClassVar[Optional[Any]] = None

    # ========================================================================
    # Instance State (private)
    # ========================================================================

    _exists: bool = PrivateAttr(default=False)
    _original: Dict[str, Any] = PrivateAttr(default_factory=dict)
    _relations: Dict[str, Any] = PrivateAttr(default_factory=dict)
    _instance_hidden: Optional[List[str]] = PrivateAttr(default=None)
    _instance_visible: List[str] = PrivateAttr(default_factory=list)
    _appended: List[str] = PrivateAttr(default_factory=list)
    _changes: Dict[str, Any] = PrivateAttr(default_factory=dict)

    # ========================================================================
    # Pydantic Configuration
    # ========================================================================

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        from_attributes=True,
        validate_assignment=True,
    )

    # ========================================================================
    # CRUD Operations
    # ========================================================================

    async def save(self: T) -> T:
        """Save the model to the database.

        Creates a new record if the model doesn't exist,
        otherwise updates the existing record.

        Returns:
            The saved model instance
        """
        # Fire saving event (abort if returns False)
        if await self._fire_event("saving") is False:
            return self

        if self._exists:
            result = await self._perform_update()
        else:
            result = await self._perform_insert()

        # Fire saved event
        if result:
            await self._fire_event("saved")

        return result

    async def _perform_insert(self: T) -> T:
        """Insert the model into the database.

        Returns:
            The inserted model with ID
        """
        # Fire creating event (abort if returns False)
        if await self._fire_event("creating") is False:
            return self

        # Get attributes to insert
        attributes = self._get_attributes_for_save()

        # Handle timestamps
        if self.__timestamps__:
            from datetime import datetime

            now = datetime.now()
            if "created_at" in self.__class__.model_fields:
                attributes["created_at"] = now
            if "updated_at" in self.__class__.model_fields:
                attributes["updated_at"] = now

        # Insert and get ID
        query = self._new_query()
        pk = self.__class__.__primary_key__
        is_composite = isinstance(pk, list)

        if is_composite:
            # For composite PKs, just insert — no auto-increment ID retrieval
            await query.insert(attributes)
            id = None
        else:
            id = await query.insert_get_id(attributes, sequence=pk)

            # Set ID on model
            if id is not None and pk in self.__class__.model_fields:
                setattr(self, pk, id)

        # Mark as existing and set original
        self._exists = True
        self._original = attributes.copy()
        if not is_composite and id is not None:
            self._original[pk] = id

        # Fire created event
        await self._fire_event("created")

        return self

    async def _perform_update(self: T) -> T:
        """Update the model in the database.

        Returns:
            The updated model
        """
        # Get dirty attributes
        dirty = self._get_dirty_attributes()

        if not dirty:
            return self

        # Fire updating event (abort if returns False)
        if await self._fire_event("updating") is False:
            return self

        # Handle timestamps
        if self.__timestamps__:
            from datetime import datetime

            if "updated_at" in self.__class__.model_fields:
                dirty["updated_at"] = datetime.now()

        # Update — handles both single and composite primary keys
        query = self._new_query()
        key = self._get_key()
        pk = self.__class__.__primary_key__
        if isinstance(pk, list):
            assert isinstance(key, dict)
            for col, val in key.items():
                query = query.where(col, val)
        else:
            query = query.where(pk, key)
        await query.update(dirty)

        # Track changes
        self._changes = dirty.copy()

        # Update original
        self._original.update(dirty)

        # Fire updated event
        await self._fire_event("updated")

        return self

    async def delete(self: T) -> bool:
        """Delete the model from the database.

        If the model uses SoftDeletes, this performs a soft delete instead.

        Returns:
            True on success
        """
        if not self._exists:
            return False

        # Delegate to SoftDeletes if the trait is in use
        if getattr(self.__class__, "__soft_deletes__", False):
            from pyloquent.traits.soft_deletes import SoftDeletes
            return await SoftDeletes.delete(self)

        # Fire deleting event (abort if returns False)
        if await self._fire_event("deleting") is False:
            return False

        key = self._get_key()
        if key is None:
            return False

        query = self._new_query()
        pk = self.__class__.__primary_key__
        if isinstance(pk, list):
            assert isinstance(key, dict)
            for col, val in key.items():
                query = query.where(col, val)
        else:
            query = query.where(pk, key)
        await query.delete()

        self._exists = False
        self._original = {}

        # Fire deleted event
        await self._fire_event("deleted")

        return True

    async def refresh(self: T) -> T:
        """Refresh the model from the database.

        Reloads the model's attributes from the database.

        Returns:
            The refreshed model
        """
        if not self._exists:
            raise ModelNotFoundException(self.__class__)

        key = self._get_key()
        fresh = await self._new_query().find(key)

        if fresh is None:
            raise ModelNotFoundException(self.__class__, key)

        # Update attributes
        for field_name in self.__class__.model_fields:
            value = getattr(fresh, field_name, None)
            setattr(self, field_name, value)

        self._original = self._get_attributes()
        self._relations = {}

        return self

    def fill(self: T, attributes: Dict[str, Any]) -> T:
        """Fill the model with attributes.

        Only fills attributes that are in __fillable__ and
        not in __guarded__.

        Args:
            attributes: Dictionary of attributes

        Returns:
            Self for chaining

        Raises:
            MassAssignmentException: If trying to fill guarded attribute
        """
        for key, value in attributes.items():
            if self._is_fillable(key):
                setattr(self, key, value)
            else:
                raise MassAssignmentException(key, self.__class__)

        return self

    def force_fill(self: T, attributes: Dict[str, Any]) -> T:
        """Force fill the model with attributes.

        Bypasses mass assignment protection.

        Args:
            attributes: Dictionary of attributes

        Returns:
            Self for chaining
        """
        for key, value in attributes.items():
            if key in self.__class__.model_fields:
                setattr(self, key, value)

        return self

    # ========================================================================
    # Query Building
    # ========================================================================

    @classmethod
    def query(cls: Type[T]) -> QueryBuilder[T]:  # pragma: no cover
        """Get a query builder for this model.

        Returns:
            QueryBuilder instance
        """
        # This is overridden by ModelMeta, but provide fallback
        from pyloquent.grammars.sqlite_grammar import SQLiteGrammar

        builder = QueryBuilder(SQLiteGrammar(), model_class=cls)
        return builder.from_(cls.__table__ or cls._get_default_table_name())

    @classmethod
    def _get_default_table_name(cls) -> str:
        """Get the default table name for this model."""
        import re

        name = cls.__name__
        # Convert CamelCase to snake_case
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
        snake_case = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
        # Pluralize
        if snake_case.endswith("y") and snake_case[-2] not in "aeiou":
            return snake_case[:-1] + "ies"
        elif snake_case.endswith(("s", "x", "z", "ch", "sh")):
            return snake_case + "es"
        else:
            return snake_case + "s"

    def _new_query(self) -> "QueryBuilder[T]":
        """Create a new query builder instance for this model.

        Returns:
            QueryBuilder instance
        """
        return self.__class__.query

    # ========================================================================
    # Relationships
    # ========================================================================

    def has_one_through(
        self,
        related: Type["Model"],
        through: Type["Model"],
        first_key: Optional[str] = None,
        second_key: Optional[str] = None,
        local_key: Optional[str] = None,
        second_local_key: Optional[str] = None,
    ) -> "HasOneThrough":
        """Define a has-one-through relationship.

        Args:
            related: The final related model
            through: The intermediate model
            first_key: FK on through model pointing to this model
            second_key: FK on related model pointing to through model
            local_key: Local key on this model
            second_local_key: Local key on through model

        Returns:
            HasOneThrough relation
        """
        from pyloquent.orm.relations.has_one_through import HasOneThrough
        if first_key is None:
            first_key = self._get_foreign_key()
        if second_key is None:
            second_key = through._get_foreign_key()
        if local_key is None:
            local_key = self.__primary_key__
        if second_local_key is None:
            second_local_key = through.__primary_key__
        return HasOneThrough(self, related, through, first_key, second_key, local_key, second_local_key)

    def has_many_through(
        self,
        related: Type["Model"],
        through: Type["Model"],
        first_key: Optional[str] = None,
        second_key: Optional[str] = None,
        local_key: Optional[str] = None,
        second_local_key: Optional[str] = None,
    ) -> "HasManyThrough":
        """Define a has-many-through relationship.

        Args:
            related: The final related model
            through: The intermediate model
            first_key: FK on through model pointing to this model
            second_key: FK on related model pointing to through model
            local_key: Local key on this model
            second_local_key: Local key on through model

        Returns:
            HasManyThrough relation
        """
        from pyloquent.orm.relations.has_many_through import HasManyThrough
        if first_key is None:
            first_key = self._get_foreign_key()
        if second_key is None:
            second_key = through._get_foreign_key()
        if local_key is None:
            local_key = self.__primary_key__
        if second_local_key is None:
            second_local_key = through.__primary_key__
        return HasManyThrough(self, related, through, first_key, second_key, local_key, second_local_key)

    def morph_to_many(
        self,
        related: Type["Model"],
        name: str,
        table: Optional[str] = None,
        foreign_pivot_key: Optional[str] = None,
        related_pivot_key: Optional[str] = None,
        parent_key: Optional[str] = None,
        related_key: Optional[str] = None,
    ) -> "MorphToMany":
        """Define a polymorphic many-to-many relationship.

        Args:
            related: Related model class
            name: Morph name (e.g., 'taggable')
            table: Pivot table name
            foreign_pivot_key: FK column for this model on pivot table
            related_pivot_key: FK column for related model on pivot table
            parent_key: Local key on this model
            related_key: Local key on related model

        Returns:
            MorphToMany relation
        """
        from pyloquent.orm.relations.morph_to_many import MorphToMany
        return MorphToMany(
            self, related, name, table,
            foreign_pivot_key, related_pivot_key,
            parent_key, related_key,
        )

    def morphed_by_many(
        self,
        related: Type["Model"],
        name: str,
        table: Optional[str] = None,
        foreign_pivot_key: Optional[str] = None,
        related_pivot_key: Optional[str] = None,
        parent_key: Optional[str] = None,
        related_key: Optional[str] = None,
    ) -> "MorphedByMany":
        """Define the inverse of a polymorphic many-to-many relationship.

        Args:
            related: Related model class
            name: Morph name
            table: Pivot table name
            foreign_pivot_key: FK column for related model on pivot table
            related_pivot_key: FK column for this model on pivot table
            parent_key: Local key on this model
            related_key: Local key on related model

        Returns:
            MorphedByMany relation
        """
        from pyloquent.orm.relations.morphed_by_many import MorphedByMany
        return MorphedByMany(
            self, related, name, table,
            foreign_pivot_key, related_pivot_key,
            parent_key, related_key,
        )

    def has_many(
        self,
        related: Type["Model"],
        foreign_key: Optional[str] = None,
        local_key: Optional[str] = None,
    ) -> "HasMany":
        """Define a has-many relationship.

        Args:
            related: Related model class
            foreign_key: Foreign key on related model
            local_key: Local key on this model

        Returns:
            HasMany relation
        """
        from pyloquent.orm.relations.has_many import HasMany

        if foreign_key is None:
            foreign_key = self._get_foreign_key()

        if local_key is None:
            local_key = self.__primary_key__

        return HasMany(self, related, foreign_key, local_key)

    def has_one(
        self,
        related: Type["Model"],
        foreign_key: Optional[str] = None,
        local_key: Optional[str] = None,
    ) -> "HasOne":
        """Define a has-one relationship.

        Args:
            related: Related model class
            foreign_key: Foreign key on related model
            local_key: Local key on this model

        Returns:
            HasOne relation
        """
        from pyloquent.orm.relations.has_one import HasOne

        if foreign_key is None:
            foreign_key = self._get_foreign_key()

        if local_key is None:
            local_key = self.__primary_key__

        return HasOne(self, related, foreign_key, local_key)

    def belongs_to(
        self,
        related: Type["Model"],
        foreign_key: Optional[str] = None,
        owner_key: Optional[str] = None,
    ) -> "BelongsTo":
        """Define a belongs-to relationship.

        Args:
            related: Related model class
            foreign_key: Foreign key on this model
            owner_key: Key on related model

        Returns:
            BelongsTo relation
        """
        from pyloquent.orm.relations.belongs_to import BelongsTo

        if foreign_key is None:
            # Foreign key on this model (e.g., user_id for Post)
            foreign_key = related._get_foreign_key()

        if owner_key is None:
            owner_key = related.__primary_key__

        return BelongsTo(self, related, foreign_key, owner_key)

    def belongs_to_many(
        self,
        related: Type["Model"],
        table: Optional[str] = None,
        foreign_key: Optional[str] = None,
        related_key: Optional[str] = None,
    ) -> "BelongsToMany":
        """Define a many-to-many relationship.

        Args:
            related: Related model class
            table: Pivot table name (auto-generated if None)
            foreign_key: Foreign key for this model on pivot table
            related_key: Foreign key for related model on pivot table

        Returns:
            BelongsToMany relation
        """
        from pyloquent.orm.relations.belongs_to_many import BelongsToMany

        if table is None:
            # Generate pivot table name (alphabetical order)
            models = sorted([self.__class__.__name__, related.__name__])
            table = f"{models[0].lower()}_{models[1].lower()}"

        if foreign_key is None:
            foreign_key = self._get_foreign_key()

        if related_key is None:
            foreign_key_related = related._get_foreign_key()
            related_key = foreign_key_related

        return BelongsToMany(self, related, table, foreign_key, related_key)

    def morph_to(
        self,
        name: str,
        type_column: Optional[str] = None,
        id_column: Optional[str] = None,
        owner_key: Optional[str] = None,
    ) -> "MorphTo":
        """Define a polymorphic inverse relationship.

        Args:
            name: Relationship name (e.g., 'commentable')
            type_column: Column storing the related model type
            id_column: Column storing the related model ID
            owner_key: Key on related model

        Returns:
            MorphTo relation
        """
        from pyloquent.orm.relations.morph_to import MorphTo

        return MorphTo(self, name, type_column, id_column, owner_key)

    def morph_one(
        self,
        related: Type["Model"],
        name: str,
        type_column: Optional[str] = None,
        id_column: Optional[str] = None,
        local_key: Optional[str] = None,
    ) -> "MorphOne":
        """Define a polymorphic one-to-one relationship.

        Args:
            related: Related model class
            name: Relationship name (e.g., 'imageable')
            type_column: Column storing this model type
            id_column: Column storing this model ID
            local_key: Local key on this model

        Returns:
            MorphOne relation
        """
        from pyloquent.orm.relations.morph_one import MorphOne

        return MorphOne(self, related, name, type_column, id_column, local_key)

    def morph_many(
        self,
        related: Type["Model"],
        name: str,
        type_column: Optional[str] = None,
        id_column: Optional[str] = None,
        local_key: Optional[str] = None,
    ) -> "MorphMany":
        """Define a polymorphic one-to-many relationship.

        Args:
            related: Related model class
            name: Relationship name (e.g., 'commentable')
            type_column: Column storing this model type
            id_column: Column storing this model ID
            local_key: Local key on this model

        Returns:
            MorphMany relation
        """
        from pyloquent.orm.relations.morph_many import MorphMany

        return MorphMany(self, related, name, type_column, id_column, local_key)

    @classmethod
    def _get_foreign_key(cls) -> str:
        """Get the default foreign key name for this model.

        Returns:
            Foreign key name (e.g., 'user_id')
        """
        import re

        name = cls.__name__
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
        snake_case = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
        return f"{snake_case}_id"

    # ========================================================================
    # Eager Loading
    # ========================================================================

    async def load(self: T, *relations: str) -> T:
        """Eager load relations on this model.

        Args:
            *relations: Relation names to load

        Returns:
            Self with loaded relations
        """
        for relation_name in relations:
            if not hasattr(self, relation_name):
                raise AttributeError(
                    f"Relation '{relation_name}' not found on {self.__class__.__name__}"
                )

            relation = getattr(self, relation_name)()
            result = await relation.get_results()
            self.set_relation(relation_name, result)

        return self

    def set_relation(self: T, name: str, value: Any) -> T:
        """Set a loaded relation.

        Args:
            name: Relation name
            value: Relation value

        Returns:
            Self for chaining
        """
        self._relations[name] = value
        return self

    def get_relation(self, name: str) -> Any:
        """Get a loaded relation.

        Args:
            name: Relation name

        Returns:
            Relation value or None
        """
        return self._relations.get(name)

    def relation_loaded(self, name: str) -> bool:
        """Check if a relation is loaded.

        Args:
            name: Relation name

        Returns:
            True if loaded
        """
        return name in self._relations

    # ========================================================================
    # Dirty Tracking
    # ========================================================================

    def is_dirty(self, key: Optional[str] = None) -> bool:
        """Check if model has unsaved changes.

        Args:
            key: Optional specific key to check

        Returns:
            True if dirty
        """
        if key:
            return self._is_dirty_key(key)
        return len(self._get_dirty_attributes()) > 0

    def is_clean(self, key: Optional[str] = None) -> bool:
        """Check if model has no unsaved changes.

        Args:
            key: Optional specific key to check

        Returns:
            True if clean
        """
        return not self.is_dirty(key)

    def was_changed(self, key: Optional[str] = None) -> bool:
        """Check if attribute was changed in last save.

        Args:
            key: Optional specific key to check

        Returns:
            True if changed
        """
        if key:
            return key in self._changes
        return len(self._changes) > 0

    def get_changes(self) -> Dict[str, Any]:
        """Get attributes changed during the last save.

        Returns:
            Dictionary of changed attributes
        """
        return self._changes.copy()

    def get_original(self, key: Optional[str] = None, default: Any = None) -> Any:
        """Get original attribute values.

        Args:
            key: Optional specific key
            default: Default value if key not found

        Returns:
            Original value(s)
        """
        if key:
            return self._original.get(key, default)
        return self._original.copy()

    def _is_dirty_key(self, key: str) -> bool:
        """Check if a specific key is dirty.

        Args:
            key: Attribute key

        Returns:
            True if dirty
        """
        if key not in self.__class__.model_fields:
            return False

        current = getattr(self, key, None)
        original = self._original.get(key)

        return current != original

    def _get_dirty_attributes(self) -> Dict[str, Any]:
        """Get all dirty attributes.

        Returns:
            Dictionary of changed attributes
        """
        dirty = {}
        for key in self.__class__.model_fields:
            if self._is_dirty_key(key):
                dirty[key] = getattr(self, key)
        return dirty

    def _get_attributes(self) -> Dict[str, Any]:
        """Get all model attributes.

        Returns:
            Dictionary of all attributes
        """
        return {key: getattr(self, key) for key in self.__class__.model_fields}

    def _get_attributes_for_save(self) -> Dict[str, Any]:
        """Get attributes to save to database.

        Returns:
            Dictionary of attributes
        """
        attributes = self._get_attributes()

        # Remove the primary key if it's None (auto-increment)
        pk = self.__primary_key__
        if isinstance(pk, list):
            for k in pk:
                if k in attributes and attributes[k] is None:
                    del attributes[k]
        elif pk in attributes and attributes[pk] is None:
            del attributes[pk]

        # Apply casting for storage
        for key in list(attributes.keys()):
            attributes[key] = self._set_cast_attribute(key, attributes[key])

        return attributes

    # ========================================================================
    # Key Access
    # ========================================================================

    def _get_key(self) -> Any:
        """Get the primary key value.

        For composite primary keys, returns a dict mapping each key column to its value.
        For single primary keys, returns the scalar value.

        Returns:
            Primary key value (scalar or dict for composite keys)
        """
        pk = self.__class__.__primary_key__
        if isinstance(pk, list):
            return {col: getattr(self, col, None) for col in pk}
        return getattr(self, pk, None)

    def _get_key_name(self) -> str:
        """Get the primary key column name.

        Returns:
            Primary key name
        """
        return self.__primary_key__

    def _set_key(self, value: Any) -> None:
        """Set the primary key value.

        Args:
            value: Primary key value
        """
        setattr(self, self.__primary_key__, value)

    # ========================================================================
    # Mass Assignment Protection
    # ========================================================================

    def _is_fillable(self, key: str) -> bool:
        """Check if an attribute is fillable.

        Args:
            key: Attribute name

        Returns:
            True if fillable
        """
        # If fillable is defined, key must be in it
        if self.__fillable__:
            return key in self.__fillable__

        # Otherwise, key must not be in guarded
        return key not in self.__guarded__

    # ========================================================================
    # Serialization
    # ========================================================================

    def to_dict(self, **kwargs) -> Dict[str, Any]:
        """Convert model to dictionary.

        Respects __hidden__, __visible__, __appends__, and instance overrides.

        Returns:
            Dictionary representation
        """
        data = super().model_dump(**kwargs)

        # Determine effective hidden list (instance overrides class)
        hidden = self._instance_hidden if self._instance_hidden is not None else list(self.__hidden__)

        # Determine effective visible list (instance overrides class)
        visible = self._instance_visible if self._instance_visible else list(self.__visible__)

        if visible:
            data = {k: v for k, v in data.items() if k in visible}
        else:
            for key in hidden:
                data.pop(key, None)

        # Add computed accessor properties (__appends__)
        for attr in list(self.__appends__) + list(self._appended):
            accessor = f"get_{attr}_attribute"
            if hasattr(self, accessor):
                data[attr] = getattr(self, accessor)()
            elif hasattr(self, attr) and isinstance(getattr(type(self), attr, None), property):
                data[attr] = getattr(self, attr)

        return data

    def to_array(self) -> Dict[str, Any]:
        """Alias for to_dict.

        Returns:
            Dictionary representation
        """
        return self.to_dict()

    def model_dump(self, **kwargs) -> Dict[str, Any]:
        """Override Pydantic's model_dump to respect hidden fields.

        Returns:
            Dictionary representation
        """
        return self.to_dict(**kwargs)

    def json(self, **kwargs) -> str:
        """Convert model to JSON string.

        Returns:
            JSON string
        """
        import json as _json
        return _json.dumps(self.to_dict())

    def make_hidden(self: T, *columns: str) -> T:
        """Hide additional attributes on this instance.

        Args:
            *columns: Column names to hide

        Returns:
            Self for chaining
        """
        current = list(self._instance_hidden) if self._instance_hidden is not None else list(self.__hidden__)
        for col in columns:
            if col not in current:
                current.append(col)
        self._instance_hidden = current
        return self

    def make_visible(self: T, *columns: str) -> T:
        """Make previously hidden attributes visible on this instance.

        Args:
            *columns: Column names to make visible

        Returns:
            Self for chaining
        """
        current = list(self._instance_hidden) if self._instance_hidden is not None else list(self.__hidden__)
        self._instance_hidden = [c for c in current if c not in columns]
        return self

    def append(self: T, *attributes: str) -> T:
        """Add computed accessor attributes to serialisation for this instance.

        Args:
            *attributes: Accessor names to append

        Returns:
            Self for chaining
        """
        self._appended = list(self._appended) + [a for a in attributes if a not in self._appended]
        return self

    def get_key(self) -> Any:
        """Get the primary key value.

        Returns:
            Primary key value
        """
        return self._get_key()

    def get_key_name(self) -> str:
        """Get the primary key column name.

        Returns:
            Primary key name
        """
        return self.__primary_key__

    async def update(self: T, attributes: Dict[str, Any]) -> T:
        """Fill and save the model in one call.

        Args:
            attributes: Attributes to update

        Returns:
            The saved model
        """
        self.fill(attributes)
        return await self.save()

    async def increment(self: T, column: str, amount: Union[int, float] = 1, extra: Optional[Dict[str, Any]] = None) -> T:
        """Atomically increment a column value.

        Args:
            column: Column to increment
            amount: Amount to increment by (default: 1)
            extra: Extra columns to update

        Returns:
            Self with updated value
        """
        query = self._new_query().where(self.__primary_key__, self._get_key())
        await query.increment(column, amount, extra)
        current = getattr(self, column, 0)
        setattr(self, column, current + amount)
        if extra:
            for k, v in extra.items():
                setattr(self, k, v)
        self._original[column] = getattr(self, column)
        return self

    async def decrement(self: T, column: str, amount: Union[int, float] = 1, extra: Optional[Dict[str, Any]] = None) -> T:
        """Atomically decrement a column value.

        Args:
            column: Column to decrement
            amount: Amount to decrement by (default: 1)
            extra: Extra columns to update

        Returns:
            Self with updated value
        """
        return await self.increment(column, -amount, extra)

    async def touch(self: T) -> bool:
        """Update the updated_at timestamp.

        Returns:
            True if timestamps are enabled, False otherwise
        """
        if not self.__timestamps__:
            return False
        from datetime import datetime
        now = datetime.now()
        if "updated_at" in self.__class__.model_fields:
            setattr(self, "updated_at", now)
            query = self._new_query().where(self.__primary_key__, self._get_key())
            await query.update({"updated_at": now})
            self._original["updated_at"] = now
        return True

    async def replicate(self: T, overrides: Optional[Dict[str, Any]] = None, except_: Optional[List[str]] = None) -> T:
        """Create a saved copy of this model without its primary key.

        Args:
            overrides: Attribute values to override in the copy
            except_: Attributes to exclude from the copy

        Returns:
            New saved model instance
        """
        await self._fire_event("replicating")
        exclude = set(except_ or [])
        exclude.add(self.__primary_key__)
        attributes = {k: v for k, v in self._get_attributes().items() if k not in exclude}
        if overrides:
            attributes.update(overrides)
        instance = self.__class__(**attributes)
        await instance.save()
        return instance

    async def push(self: T) -> T:
        """Save the model and all loaded relations.

        Returns:
            Self after saving
        """
        await self.save()
        for relation_value in self._relations.values():
            if isinstance(relation_value, Collection):
                for model in relation_value:
                    if hasattr(model, "push"):
                        await model.push()
            elif relation_value is not None and hasattr(relation_value, "push"):
                await relation_value.push()
        return self

    async def load_missing(self: T, *relations: str) -> T:
        """Eager load relations that are not already loaded.

        Args:
            *relations: Relation names to load if missing

        Returns:
            Self for chaining
        """
        to_load = [r for r in relations if not self.relation_loaded(r)]
        if to_load:
            await self.load(*to_load)
        return self

    async def load_count(self: T, *relations: str) -> T:
        """Load the count of the specified relations onto the model.

        Args:
            *relations: Relation names to count

        Returns:
            Self with {relation}_count attributes set
        """
        for relation_name in relations:
            if not hasattr(self, relation_name):
                continue
            relation = getattr(self, relation_name)()
            count = await relation.query.count()
            object.__setattr__(self, f"{relation_name}_count", count)
        return self

    # ========================================================================
    # Class Methods for Querying
    # ========================================================================

    @classmethod
    def where(
        cls: Type[T], column: str, operator: Any = None, value: Any = _UNSET
    ) -> QueryBuilder[T]:
        """Start a query with a where clause.

        Args:
            column: Column name
            operator: Comparison operator or value
            value: Value to compare

        Returns:
            QueryBuilder instance
        """
        return cls.query.where(column, operator, value)

    @classmethod
    def where_in(cls: Type[T], column: str, values: list) -> "QueryBuilder[T]":
        """Start a query with a where_in clause.

        Args:
            column: Column name
            values: List of values

        Returns:
            QueryBuilder instance
        """
        return cls.query.where_in(column, values)

    @classmethod
    def order_by(cls: Type[T], column: str, direction: str = "asc") -> "QueryBuilder[T]":
        """Start a query with an order_by clause.

        Args:
            column: Column name
            direction: Sort direction

        Returns:
            QueryBuilder instance
        """
        return cls.query.order_by(column, direction)

    @classmethod
    def limit(cls: Type[T], value: int) -> "QueryBuilder[T]":
        """Start a query with a limit.

        Args:
            value: Maximum number of rows

        Returns:
            QueryBuilder instance
        """
        return cls.query.limit(value)

    @classmethod
    def count(cls: Type[T], column: str = "*") -> Any:
        """Count the number of records.

        Args:
            column: Column to count (default: *)

        Returns:
            Coroutine that resolves to count
        """
        return cls.query.count(column)

    @classmethod
    def pluck(cls: Type[T], column: str) -> Any:
        """Get a list of a single column's values.

        Args:
            column: Column name

        Returns:
            Coroutine that resolves to list of values
        """
        return cls.query.pluck(column)

    @classmethod
    def all(cls: Type[T]) -> Any:
        """Get all records.

        Returns:
            Coroutine that resolves to Collection
        """
        return cls.query.get()

    @classmethod
    def first(cls: Type[T]) -> Any:
        """Get the first record.

        Returns:
            Coroutine that resolves to model or None
        """
        return cls.query.first()

    @classmethod
    def find(cls: Type[T], id: Any) -> Any:
        """Find a record by primary key.

        Args:
            id: Primary key value

        Returns:
            Coroutine that resolves to model or None
        """
        return cls.query.find(id)

    @classmethod
    def find_or_fail(cls: Type[T], id: Any) -> Any:
        """Find a record by primary key or fail.

        Args:
            id: Primary key value

        Returns:
            Coroutine that resolves to model
        """
        return cls.query.find_or_fail(id)

    @classmethod
    def create(cls: Type[T], attributes: Dict[str, Any]) -> Any:
        """Create a new record.

        Args:
            attributes: Record attributes

        Returns:
            Coroutine that resolves to created model
        """
        instance = cls(**attributes)
        return instance.save()

    @classmethod
    def first_or_create(
        cls: Type[T], attributes: Dict[str, Any], values: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Find first matching record or create a new one.

        Args:
            attributes: Attributes to search for
            values: Additional values to set on create

        Returns:
            Coroutine that resolves to model
        """

        async def _first_or_create():
            query = cls.query
            for key, value in attributes.items():
                query = query.where(key, value)

            existing = await query.first()
            if existing:
                return existing

            create_attributes = attributes.copy()
            if values:
                create_attributes.update(values)

            return await cls.create(create_attributes)

        return _first_or_create()

    @classmethod
    def update_or_create(cls: Type[T], attributes: Dict[str, Any], values: Dict[str, Any]) -> Any:
        """Update or create a record.

        Args:
            attributes: Attributes to search for
            values: Values to update/set

        Returns:
            Coroutine that resolves to model
        """

        async def _update_or_create():
            query = cls.query
            for key, value in attributes.items():
                query = query.where(key, value)

            existing = await query.first()
            if existing:
                for key, value in values.items():
                    setattr(existing, key, value)
                return await existing.save()

            create_attributes = attributes.copy()
            create_attributes.update(values)
            return await cls.create(create_attributes)

        return _update_or_create()

    @classmethod
    def with_(cls: Type[T], *relations: str) -> "QueryBuilder[T]":
        """Eager load relations.

        Args:
            *relations: Relation names to eager load

        Returns:
            QueryBuilder instance with eager loads configured
        """
        query = cls.query
        for relation in relations:
            query = query.with_(relation)
        return query

    @classmethod
    def first_or_fail(cls: Type[T]) -> Any:
        """Get the first record or raise ModelNotFoundException."""
        return cls.query.first_or_fail()

    @classmethod
    def find_many(cls: Type[T], ids: List[Any]) -> Any:
        """Find multiple records by primary key."""
        return cls.query.where_in(cls.__primary_key__, ids).get()

    @classmethod
    def destroy(cls: Type[T], *ids: Any) -> Any:
        """Delete one or more records by primary key.

        Args:
            *ids: Primary key value(s) or a single list

        Returns:
            Coroutine that resolves to number of deleted rows
        """
        async def _destroy():
            id_list = list(ids[0]) if len(ids) == 1 and isinstance(ids[0], (list, tuple)) else list(ids)
            return await cls.query.where_in(cls.__primary_key__, id_list).delete()
        return _destroy()

    @classmethod
    def truncate(cls: Type[T]) -> Any:
        """Truncate the model's table."""
        async def _truncate():
            return await cls.query.delete_all()
        return _truncate()

    @classmethod
    def max(cls: Type[T], column: str) -> Any:
        """Get the maximum value of a column."""
        return cls.query.max(column)

    @classmethod
    def min(cls: Type[T], column: str) -> Any:
        """Get the minimum value of a column."""
        return cls.query.min(column)

    @classmethod
    def sum(cls: Type[T], column: str) -> Any:
        """Get the sum of a column."""
        return cls.query.sum(column)

    @classmethod
    def avg(cls: Type[T], column: str) -> Any:
        """Get the average of a column."""
        return cls.query.avg(column)

    @classmethod
    def exists(cls: Type[T]) -> Any:
        """Check if any records exist."""
        return cls.query.exists()

    @classmethod
    def doesnt_exist(cls: Type[T]) -> Any:
        """Check if no records exist."""
        return cls.query.doesnt_exist()

    @classmethod
    def value(cls: Type[T], column: str) -> Any:
        """Get a single column value from the first record."""
        return cls.query.value(column)

    @classmethod
    def select(cls: Type[T], *columns: str) -> "QueryBuilder[T]":
        """Start a query selecting specific columns."""
        return cls.query.select(*columns)

    @classmethod
    def select_raw(cls: Type[T], sql: str, bindings: Optional[List[Any]] = None) -> "QueryBuilder[T]":
        """Start a query with a raw SELECT expression."""
        return cls.query.select_raw(sql, bindings)

    @classmethod
    def distinct(cls: Type[T]) -> "QueryBuilder[T]":
        """Start a query with DISTINCT."""
        return cls.query.distinct()

    @classmethod
    def join(cls: Type[T], table: str, first: str, operator: Any = None, second: str = None) -> "QueryBuilder[T]":
        """Start a query with a JOIN."""
        return cls.query.join(table, first, operator, second)

    @classmethod
    def left_join(cls: Type[T], table: str, first: str, operator: Any = None, second: str = None) -> "QueryBuilder[T]":
        """Start a query with a LEFT JOIN."""
        return cls.query.left_join(table, first, operator, second)

    @classmethod
    def right_join(cls: Type[T], table: str, first: str, operator: Any = None, second: str = None) -> "QueryBuilder[T]":
        """Start a query with a RIGHT JOIN."""
        return cls.query.right_join(table, first, operator, second)

    @classmethod
    def group_by(cls: Type[T], *columns: str) -> "QueryBuilder[T]":
        """Start a query with GROUP BY."""
        return cls.query.group_by(*columns)

    @classmethod
    def having(cls: Type[T], column: str, operator: Any = None, value: Any = None) -> "QueryBuilder[T]":
        """Start a query with a HAVING clause."""
        return cls.query.having(column, operator, value)

    @classmethod
    def where_null(cls: Type[T], column: str) -> "QueryBuilder[T]":
        """Start a query with WHERE column IS NULL."""
        return cls.query.where_null(column)

    @classmethod
    def where_not_null(cls: Type[T], column: str) -> "QueryBuilder[T]":
        """Start a query with WHERE column IS NOT NULL."""
        return cls.query.where_not_null(column)

    @classmethod
    def where_between(cls: Type[T], column: str, values: Any) -> "QueryBuilder[T]":
        """Start a query with WHERE column BETWEEN."""
        return cls.query.where_between(column, values)

    @classmethod
    def where_not_between(cls: Type[T], column: str, values: Any) -> "QueryBuilder[T]":
        """Start a query with WHERE column NOT BETWEEN."""
        return cls.query.where_not_between(column, values)

    @classmethod
    def or_where(cls: Type[T], column: str, operator: Any = None, value: Any = None) -> "QueryBuilder[T]":
        """Start a query with an OR WHERE clause."""
        return cls.query.or_where(column, operator, value)

    @classmethod
    def where_raw(cls: Type[T], sql: str, bindings: Optional[List[Any]] = None) -> "QueryBuilder[T]":
        """Start a query with a raw WHERE clause."""
        return cls.query.where_raw(sql, bindings)

    @classmethod
    def where_column(cls: Type[T], first: str, operator: Any = None, second: str = None) -> "QueryBuilder[T]":
        """Start a query comparing two columns."""
        return cls.query.where_column(first, operator, second)

    @classmethod
    def latest(cls: Type[T], column: str = "created_at") -> "QueryBuilder[T]":
        """Order by column descending."""
        return cls.query.latest(column)

    @classmethod
    def oldest(cls: Type[T], column: str = "created_at") -> "QueryBuilder[T]":
        """Order by column ascending."""
        return cls.query.oldest(column)

    @classmethod
    def has(cls: Type[T], relation: str, operator: str = ">=", count: int = 1) -> "QueryBuilder[T]":
        """Filter models that have a related model."""
        return cls.query.has(relation, operator, count)

    @classmethod
    def doesnt_have(cls: Type[T], relation: str) -> "QueryBuilder[T]":
        """Filter models that don't have a related model."""
        return cls.query.doesnt_have(relation)

    @classmethod
    def where_has(cls: Type[T], relation: str, callback: Any = None, operator: str = ">=", count: int = 1) -> "QueryBuilder[T]":
        """Filter models that have a related model matching conditions."""
        return cls.query.where_has(relation, callback, operator, count)

    @classmethod
    def with_count(cls: Type[T], *relations: str) -> "QueryBuilder[T]":
        """Add relationship count columns to query."""
        return cls.query.with_count(*relations)

    @classmethod
    def chunk(cls: Type[T], count: int) -> Any:
        """Chunk results in groups of the given size."""
        return cls.query.chunk(count)

    @classmethod
    def paginate(cls: Type[T], per_page: Optional[int] = None, page: int = 1) -> Any:
        """Paginate the results."""
        return cls.query.paginate(per_page or cls.__per_page__, page)

    @classmethod
    def simple_paginate(cls: Type[T], per_page: Optional[int] = None, page: int = 1) -> Any:
        """Simple paginate without total count."""
        return cls.query.simple_paginate(per_page or cls.__per_page__, page)

    @classmethod
    def cursor(cls: Type[T]) -> Any:
        """Iterate over results using a cursor."""
        return cls.query.cursor()

    @classmethod
    def first_or_new(cls: Type[T], attributes: Dict[str, Any], values: Optional[Dict[str, Any]] = None) -> Any:
        """Find first matching record or return a new (unsaved) instance."""
        async def _first_or_new():
            query = cls.query
            for key, value in attributes.items():
                query = query.where(key, value)
            existing = await query.first()
            if existing:
                return existing
            create_attributes = attributes.copy()
            if values:
                create_attributes.update(values)
            return cls(**create_attributes)
        return _first_or_new()

    @classmethod
    def where_exists(cls: Type[T], callback: Any) -> "QueryBuilder[T]":
        """Filter records where a subquery exists."""
        return cls.query.where_exists(callback)

    @classmethod
    def where_not_exists(cls: Type[T], callback: Any) -> "QueryBuilder[T]":
        """Filter records where a subquery does not exist."""
        return cls.query.where_not_exists(callback)

    @classmethod
    def lock_for_update(cls: Type[T]) -> "QueryBuilder[T]":
        """Lock the selected rows for update."""
        return cls.query.lock_for_update()

    @classmethod
    def for_share(cls: Type[T]) -> "QueryBuilder[T]":
        """Lock the selected rows in share mode."""
        return cls.query.for_share()

    @classmethod
    def to_raw_sql(cls: Type[T]) -> str:
        """Get the raw SQL with bindings interpolated."""
        return cls.query.to_raw_sql()

    # ========================================================================
    # Event Handling
    # ========================================================================

    @classmethod
    def observe(cls, observer: Any) -> None:
        """Register a model observer.

        Args:
            observer: ModelObserver instance
        """
        from pyloquent.observers.dispatcher import EventDispatcher

        callbacks = observer._get_callbacks()
        for event, callback in callbacks.items():
            EventDispatcher.listen_for_model(cls, event, callback)

    @classmethod
    def on(cls, event: str, callback: Any) -> None:
        """Register an event listener for this model.

        Args:
            event: Event name (e.g., 'creating', 'created')
            callback: Callback function
        """
        from pyloquent.observers.dispatcher import EventDispatcher

        EventDispatcher.listen_for_model(cls, event, callback)

    @classmethod
    def set_event_dispatcher(cls, dispatcher: Any) -> None:
        """Set the event dispatcher for this model.

        Args:
            dispatcher: EventDispatcher instance
        """
        cls._dispatcher = dispatcher

    @classmethod
    def get_event_dispatcher(cls) -> Any:
        """Get the event dispatcher for this model.

        Returns:
            EventDispatcher instance or None
        """
        return cls._dispatcher

    async def _fire_event(self, event: str) -> Any:
        """Fire a model event.

        Args:
            event: Event name

        Returns:
            Event result (False to abort)
        """
        from pyloquent.observers.dispatcher import EventDispatcher

        return await EventDispatcher.dispatch(event, self)

    # ========================================================================
    # Attribute Casting
    # ========================================================================

    def _cast_attribute(self, key: str, value: Any) -> Any:
        """Cast an attribute value based on __casts__.

        Args:
            key: Attribute name
            value: Raw value from database

        Returns:
            Cast value
        """
        if key not in self.__casts__ or value is None:
            return value

        cast_type = self.__casts__[key]

        # TypeDecorator support — checked first
        from pyloquent.orm.type_decorator import get_type as _get_type
        custom = _get_type(cast_type)
        if custom is not None:
            return custom.process_result_value(value)

        if cast_type == "json":
            import json

            if isinstance(value, str):
                return json.loads(value)
            return value
        elif cast_type == "bool":
            return bool(value)
        elif cast_type == "int":
            return int(value)
        elif cast_type == "float":
            return float(value)
        elif cast_type == "string":
            return str(value)
        elif cast_type == "datetime":
            from datetime import datetime

            if isinstance(value, str):
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            return value
        elif cast_type == "date":
            from datetime import date

            if isinstance(value, str):
                return date.fromisoformat(value)
            return value
        elif cast_type.startswith("decimal:"):
            from decimal import Decimal

            return Decimal(str(value))

        return value

    def _set_cast_attribute(self, key: str, value: Any) -> Any:
        """Cast a value for database storage.

        Args:
            key: Attribute name
            value: Value to cast

        Returns:
            Cast value for storage
        """
        if key not in self.__casts__ or value is None:
            return value

        cast_type = self.__casts__[key]

        # TypeDecorator support — checked first
        from pyloquent.orm.type_decorator import get_type as _get_type
        custom = _get_type(cast_type)
        if custom is not None:
            return custom.process_bind_param(value)

        if cast_type == "json":
            import json

            if not isinstance(value, str):
                return json.dumps(value)
            return value
        elif cast_type in ["bool", "int", "float", "string"]:
            return value
        elif cast_type in ["datetime", "date"]:
            if hasattr(value, "isoformat"):
                return value.isoformat()
            return value
        elif cast_type.startswith("decimal:"):
            return str(value)

        return value
