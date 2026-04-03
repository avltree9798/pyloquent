"""Pyloquent - Eloquent-inspired ORM for Python with Pydantic and FastAPI support."""

from pyloquent.__version__ import __version__
from pyloquent.cache import CacheManager, FileStore, MemoryStore, RedisStore
from pyloquent.d1 import D1Connection, D1HttpClient
from pyloquent.database import ConnectionManager
from pyloquent.exceptions import (
    ModelNotFoundException,
    PyloquentException,
    QueryException,
    RelationNotFoundException,
)
from pyloquent.factories import Factory
from pyloquent.migrations import Migration, MigrationCreator, MigrationRunner
from pyloquent.observers import EventDispatcher, ModelObserver, observes
from pyloquent.orm import Collection, Model
from pyloquent.query import QueryBuilder
from pyloquent.schema import Blueprint, SchemaBuilder
from pyloquent.traits import SoftDeletes

__all__ = [
    "__version__",
    "Blueprint",
    "CacheManager",
    "Collection",
    "ConnectionManager",
    "D1Connection",
    "D1HttpClient",
    "EventDispatcher",
    "Factory",
    "FileStore",
    "MemoryStore",
    "Migration",
    "MigrationCreator",
    "MigrationRunner",
    "Model",
    "ModelNotFoundException",
    "ModelObserver",
    "PyloquentException",
    "QueryBuilder",
    "QueryException",
    "RedisStore",
    "RelationNotFoundException",
    "SchemaBuilder",
    "SoftDeletes",
    "observes",
]
