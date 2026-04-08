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
        discriminator = namespace.get("__discriminator__")
        discriminator_value = namespace.get("__discriminator_value__")

        # Auto-infer table name if not specified
        if table_name is None:
            # STI: inherit parent model's table when discriminator is set
            if discriminator or discriminator_value is not None:
                for base in bases:
                    parent_table = getattr(base, "__table__", None)
                    if parent_table and base.__name__ not in ("Model", "BaseModel"):
                        table_name = parent_table
                        break
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

        # Auto-boot SoftDeletes trait if present in the MRO
        for base in cls.__mro__:
            if base.__name__ == "SoftDeletes" and hasattr(cls, "boot_soft_deletes"):
                cls.boot_soft_deletes()
                break

        # Auto-register STI discriminator scope
        if discriminator and discriminator_value is not None:
            if not hasattr(cls, "_global_scopes"):
                cls._global_scopes = {}
            _disc_col = discriminator
            _disc_val = discriminator_value
            cls._global_scopes[f"sti_{_disc_col}"] = (
                lambda q, col=_disc_col, val=_disc_val: q.where(col, val)
            )

        return cls

    @staticmethod
    def _get_table_name(class_name: str) -> str:
        """Convert class name to table name.

        Converts CamelCase to snake_case and pluralises.
        e.g., User -> users, AirTrafficController -> air_traffic_controllers

        Args:
            class_name: The model class name

        Returns:
            Table name
        """
        # Convert CamelCase to snake_case
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", class_name)
        snake_case = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()

        # Pluralise
        return ModelMeta._pluralise(snake_case)

    @staticmethod
    def _pluralise(word: str) -> str:
        """Simple pluralisation.

        Args:
            word: Singular word

        Returns:
            Plural word
        """
        # Handle basic pluralisation rules
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

        builder = builder.from_(cls.__table__)

        # Apply class-level global scopes (e.g. from SoftDeletes.boot_soft_deletes)
        if hasattr(cls, "_global_scopes"):
            for scope_name, callback in cls._global_scopes.items():
                builder.with_global_scope(scope_name, callback)

        # STI: apply discriminator scope when __discriminator_value__ is set
        disc = getattr(cls, "__discriminator__", None)
        disc_val = getattr(cls, "__discriminator_value__", None)
        if disc and disc_val is not None:
            _col = disc
            _val = disc_val
            builder.with_global_scope(
                f"sti_{_col}",
                lambda q, col=_col, val=_val: q.where(col, val),
            )

        return builder

    def where(cls, column: str, operator: Any = None, value: Any = None) -> "QueryBuilder":  # pragma: no cover
        """Start a query with a where clause.

        Args:
            column: Column name
            operator: Comparison operator or value
            value: Value to compare

        Returns:
            QueryBuilder instance
        """
        return cls.query.where(column, operator, value)

    def all(cls) -> Any:  # pragma: no cover
        """Get all records.

        Returns:
            Coroutine that resolves to Collection
        """
        return cls.query.get()

    def find(cls, id: Any) -> Any:  # pragma: no cover
        """Find a record by primary key.

        Args:
            id: Primary key value

        Returns:
            Coroutine that resolves to model or None
        """
        return cls.query.find(id)

    def find_or_fail(cls, id: Any) -> Any:  # pragma: no cover
        """Find a record by primary key or fail.

        Args:
            id: Primary key value

        Returns:
            Coroutine that resolves to model
        """
        return cls.query.find_or_fail(id)

    def create(cls, attributes: Dict[str, Any]) -> Any:  # pragma: no cover
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

    def first_or_create(  # pragma: no cover
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

    def update_or_create(cls, attributes: Dict[str, Any], values: Dict[str, Any]) -> Any:  # pragma: no cover
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

    def with_(cls, *relations: str) -> "QueryBuilder":  # pragma: no cover
        """Eager load relations.

        Args:
            *relations: Relation names to eager load

        Returns:
            QueryBuilder instance
        """
        return cls.query.with_(*relations)
