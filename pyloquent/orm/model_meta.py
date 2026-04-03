"""Metaclass for Pyloquent models."""

import re
from typing import Any, Dict, List, Optional, Type, TypeVar

from pydantic._internal._model_construction import ModelMetaclass as PydanticModelMetaclass


class ModelMeta(PydanticModelMetaclass):
    """Metaclass for Pyloquent models.

    This metaclass extends Pydantic's ModelMetaclass to handle
    Pyloquent-specific metadata and query builder forwarding.
    """

    def __new__(mcs, name: str, bases: tuple, namespace: Dict[str, Any], **kwargs) -> Type:
        """Create a new model class.

        Args:
            name: Class name
            bases: Base classes
            namespace: Class namespace
            **kwargs: Additional keyword arguments

        Returns:
            New model class
        """
        # Extract Pyloquent configuration
        table_name = namespace.get("__table__")
        fillable = namespace.get("__fillable__", [])
        guarded = namespace.get("__guarded__", ["id"])
        hidden = namespace.get("__hidden__", [])
        casts = namespace.get("__casts__", {})
        timestamps = namespace.get("__timestamps__", True)
        connection = namespace.get("__connection__")
        primary_key = namespace.get("__primary_key__", "id")

        # Auto-infer table name if not specified
        if table_name is None:
            table_name = mcs._get_table_name(name)

        # Store metadata on the class
        namespace["_pyloquent_meta"] = {
            "table": table_name,
            "fillable": fillable,
            "guarded": guarded,
            "hidden": hidden,
            "casts": casts,
            "timestamps": timestamps,
            "connection": connection,
            "primary_key": primary_key,
        }

        # Set __table__ explicitly on the class
        namespace["__table__"] = table_name

        # Create the class using Pydantic's metaclass
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)

        return cls

    @staticmethod
    def _get_table_name(class_name: str) -> str:
        """Convert class name to table name.

        Converts CamelCase to snake_case and pluralizes.
        e.g., User -> users, AirTrafficController -> air_traffic_controllers

        Args:
            class_name: The model class name

        Returns:
            Table name
        """
        # Convert CamelCase to snake_case
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", class_name)
        snake_case = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()

        # Pluralize
        return ModelMeta._pluralize(snake_case)

    @staticmethod
    def _pluralize(word: str) -> str:
        """Simple pluralization.

        Args:
            word: Singular word

        Returns:
            Plural word
        """
        # Handle basic pluralization rules
        if word.endswith("y") and word[-2] not in "aeiou":
            return word[:-1] + "ies"
        elif word.endswith(("s", "x", "z", "ch", "sh")):
            return word + "es"
        else:
            return word + "s"

    @property
    def query(cls) -> "QueryBuilder":
        """Get a query builder instance for this model.

        Returns:
            QueryBuilder instance
        """
        from pyloquent.query.builder import QueryBuilder
        from pyloquent.database.manager import get_manager

        # Get connection from global manager
        try:
            manager = get_manager()
            conn = manager.connection(cls.__connection__)
            grammar = conn.grammar
            builder = QueryBuilder(grammar, connection=conn, model_class=cls)
        except Exception:
            # Fallback to SQLite grammar without connection
            # (for SQL compilation testing)
            from pyloquent.grammars.sqlite_grammar import SQLiteGrammar

            builder = QueryBuilder(SQLiteGrammar(), model_class=cls)

        return builder.from_(cls.__table__)

    def where(cls, column: str, operator: Any = None, value: Any = None) -> "QueryBuilder":
        """Start a query with a where clause.

        Args:
            column: Column name
            operator: Comparison operator or value
            value: Value to compare

        Returns:
            QueryBuilder instance
        """
        return cls.query.where(column, operator, value)

    def all(cls) -> Any:
        """Get all records.

        Returns:
            Coroutine that resolves to Collection
        """
        return cls.query.get()

    def find(cls, id: Any) -> Any:
        """Find a record by primary key.

        Args:
            id: Primary key value

        Returns:
            Coroutine that resolves to model or None
        """
        return cls.query.find(id)

    def find_or_fail(cls, id: Any) -> Any:
        """Find a record by primary key or fail.

        Args:
            id: Primary key value

        Returns:
            Coroutine that resolves to model
        """
        return cls.query.find_or_fail(id)

    def create(cls, attributes: Dict[str, Any]) -> Any:
        """Create a new record.

        Args:
            attributes: Record attributes

        Returns:
            Coroutine that resolves to created model
        """
        from pyloquent.orm.model import Model

        if issubclass(cls, Model):
            instance = cls(**attributes)
            return instance.save()
        raise TypeError("Class must be a Model subclass")

    def first_or_create(
        cls, attributes: Dict[str, Any], values: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Find first matching record or create a new one.

        Args:
            attributes: Attributes to search for
            values: Additional values to set on create

        Returns:
            Coroutine that resolves to model
        """
        query = cls.query
        for key, value in attributes.items():
            query = query.where(key, value)

        # This needs to be async, return coroutine
        async def _first_or_create():
            existing = await query.first()
            if existing:
                return existing

            # Create new
            create_attributes = attributes.copy()
            if values:
                create_attributes.update(values)

            return await cls.create(create_attributes)

        return _first_or_create()

    def update_or_create(cls, attributes: Dict[str, Any], values: Dict[str, Any]) -> Any:
        """Update or create a record.

        Args:
            attributes: Attributes to search for
            values: Values to update/set

        Returns:
            Coroutine that resolves to model
        """
        query = cls.query
        for key, value in attributes.items():
            query = query.where(key, value)

        async def _update_or_create():
            existing = await query.first()
            if existing:
                # Update existing
                for key, value in values.items():
                    setattr(existing, key, value)
                return await existing.save()

            # Create new
            create_attributes = attributes.copy()
            create_attributes.update(values)
            return await cls.create(create_attributes)

        return _update_or_create()

    def with_(cls, *relations: str) -> "QueryBuilder":
        """Eager load relations.

        Args:
            *relations: Relation names to eager load

        Returns:
            QueryBuilder instance
        """
        return cls.query.with_(*relations)
