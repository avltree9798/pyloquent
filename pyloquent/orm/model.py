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
from pyloquent.query.builder import QueryBuilder

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
    __casts__: ClassVar[Dict[str, str]] = {}
    __timestamps__: ClassVar[bool] = True
    __connection__: ClassVar[Optional[str]] = None
    __primary_key__: ClassVar[str] = "id"

    # Event dispatcher reference (class-level)
    _dispatcher: ClassVar[Optional[Any]] = None

    # ========================================================================
    # Instance State (private)
    # ========================================================================

    _exists: bool = PrivateAttr(default=False)
    _original: Dict[str, Any] = PrivateAttr(default_factory=dict)
    _relations: Dict[str, Any] = PrivateAttr(default_factory=dict)

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
            if "created_at" in self.model_fields:
                attributes["created_at"] = now
            if "updated_at" in self.model_fields:
                attributes["updated_at"] = now

        # Insert and get ID
        query = self._new_query()
        id = await query.insert_get_id(attributes)

        # Set ID on model
        if id is not None and self.__primary_key__ in self.model_fields:
            setattr(self, self.__primary_key__, id)

        # Mark as existing and set original
        self._exists = True
        self._original = attributes.copy()
        self._original[self.__primary_key__] = id

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

            if "updated_at" in self.model_fields:
                dirty["updated_at"] = datetime.now()

        # Update
        query = self._new_query().where(self.__primary_key__, self._get_key())
        await query.update(dirty)

        # Update original
        self._original.update(dirty)

        # Fire updated event
        await self._fire_event("updated")

        return self

    async def delete(self: T) -> bool:
        """Delete the model from the database.

        Returns:
            True on success
        """
        if not self._exists:
            return False

        # Fire deleting event (abort if returns False)
        if await self._fire_event("deleting") is False:
            return False

        key = self._get_key()
        if key is None:
            return False

        query = self._new_query().where(self.__primary_key__, key)
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
        for field_name in self.model_fields:
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
            if key in self.model_fields:
                setattr(self, key, value)

        return self

    # ========================================================================
    # Query Building
    # ========================================================================

    @classmethod
    def query(cls: Type[T]) -> QueryBuilder[T]:
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

        Note: This is not fully implemented in current version.

        Args:
            key: Optional specific key to check

        Returns:
            True if changed
        """
        # For now, just check if dirty
        # In a full implementation, we'd track changes across saves
        return self.is_dirty(key)

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
        if key not in self.model_fields:
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
        for key in self.model_fields:
            if self._is_dirty_key(key):
                dirty[key] = getattr(self, key)
        return dirty

    def _get_attributes(self) -> Dict[str, Any]:
        """Get all model attributes.

        Returns:
            Dictionary of all attributes
        """
        return {key: getattr(self, key) for key in self.model_fields}

    def _get_attributes_for_save(self) -> Dict[str, Any]:
        """Get attributes to save to database.

        Returns:
            Dictionary of attributes
        """
        attributes = self._get_attributes()

        # Remove the primary key if it's None (auto-increment)
        pk = self.__primary_key__
        if pk in attributes and attributes[pk] is None:
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

        Returns:
            Primary key value
        """
        return getattr(self, self.__primary_key__, None)

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

        Excludes hidden fields.

        Returns:
            Dictionary representation
        """
        data = super().model_dump(**kwargs)

        # Remove hidden fields
        for key in self.__hidden__:
            data.pop(key, None)

        return data

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
        return self.model_dump_json(**kwargs)

    # ========================================================================
    # Class Methods for Querying
    # ========================================================================

    @classmethod
    def where(
        cls: Type[T], column: str, operator: Any = None, value: Any = None
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
