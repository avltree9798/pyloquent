# AGENTS.md — Developer & AI Agent Guide

> Guidelines for humans and AI agents working on Pyloquent.

---

## Project Overview

Pyloquent is an async-first ORM for Python, modelled on Laravel's Eloquent. It uses **Pydantic v2** for model definitions and **aiosqlite / asyncpg / aiomysql** for database I/O.

```
pyloquent/
├── database/          # ConnectionManager, driver connections
├── grammars/          # SQL compilation (Grammar, SQLiteGrammar, PostgresGrammar, MySQLGrammar)
├── orm/               # Model, ModelMeta, Collection
│   └── relations/     # All relationship classes
├── query/             # QueryBuilder, Expression types
├── traits/            # SoftDeletes
├── migrations/        # Migration runner & creator
├── schema/            # SchemaBuilder, Blueprint, Column
├── observers/         # EventDispatcher, ModelObserver
├── cache/             # CacheManager, MemoryStore, FileStore, RedisStore
├── factories/         # Factory base class
├── cli/               # CLI commands (make:model, migrate, etc.)
└── d1/                # Cloudflare D1 driver
```

---

## Architecture Decisions

### Global ConnectionManager

Models resolve their database connection via a **global** `ConnectionManager` set with `set_manager()`. Always call `set_manager(manager)` before using models; never pass a local manager directly.

```python
from pyloquent.database.manager import set_manager
set_manager(manager)
```

### Grammar / QueryBuilder Split

- **`Grammar`** — pure SQL compiler; takes a `QueryBuilder` state and returns `(sql, bindings)`.
- **`QueryBuilder`** — fluent builder; holds state, delegates compilation to the injected grammar, and executes via `self.connection`.

New SQL dialects: subclass `Grammar` and override `_compile_*` methods, then register in `ConnectionManager`.

### Model ↔ QueryBuilder

`ModelMeta.query` (a property) creates a fresh `QueryBuilder` bound to the model's grammar and connection. Every classmethod proxy on `Model` delegates to `cls.query.<method>`.

### Relationship Queries

All relationship classes receive `parent` (model instance) and `related` (model class). `_create_query()` builds the `QueryBuilder`; `get_results()` / `get()` execute it. Pivot queries (BelongsToMany, MorphToMany, MorphedByMany) must carry both `grammar` **and** `connection` from the parent's query.

---

## Key Conventions

| Convention | Detail |
|-----------|--------|
| **Spelling** | British English throughout — serialisation, initialisation, pluralise, parameterise, organised, etc. |
| **Async** | All DB methods are `async def`. Pure computation methods are synchronous. |
| **Type hints** | All public methods fully type-hinted. Use `TypeVar T` bound to `Model` for instance methods that return `self`. |
| **Private methods** | Prefixed with `_`. Never part of the public API. |
| **Events** | Fire with `await self._fire_event('event_name')`. Returning `False` from a listener aborts the operation. |
| **`model_fields`** | Access via `self.__class__.model_fields`, not `self.model_fields` (Pydantic v2 deprecation). |
| **Sentinel `None`** | Use `None` (not empty list `[]`) as sentinel for "not set" private attributes (e.g. `_instance_hidden`). |

---

## Running Tests

```bash
# Full test suite
pytest tests/

# With coverage report
pytest tests/ --cov=pyloquent --cov-report=term-missing

# Specific test file
pytest tests/unit/test_collection_extended.py -v

# Integration tests only
pytest tests/integration/ -v

# Exclude slow tests
pytest tests/ -m "not slow"
```

Tests use **in-memory SQLite** (`':memory:'`) and `pytest-asyncio` for async test functions. All fixtures are in `tests/conftest.py`.

---

## Writing Tests

### Unit Tests (no DB)

Unit tests live in `tests/unit/`. Use `SQLiteGrammar()` and a bare `QueryBuilder` to test SQL compilation without a real connection.

```python
from pyloquent.query.builder import QueryBuilder
from pyloquent.grammars.sqlite_grammar import SQLiteGrammar

def test_something():
    sql, bindings = QueryBuilder(SQLiteGrammar()).from_("users").where("id", 1).to_sql()
    assert '"id" = ?' in sql
    assert bindings == [1]
```

### Integration Tests (with DB)

Integration tests live in `tests/integration/`. Use the `sqlite_db` fixture from `conftest.py` which provides a `ConnectionManager` wired to an in-memory SQLite database.

```python
import pytest

@pytest.mark.asyncio
async def test_something(sqlite_db):
    user = await User.create({"name": "Alice", "email": "a@test.com"})
    assert user.id is not None
```

Create per-test table fixtures to keep tests isolated:

```python
@pytest.fixture
async def my_tables(sqlite_db):
    conn = sqlite_db.connection()
    await conn.execute("CREATE TABLE ...")
    yield
```

### Event Listener Cleanup

Event listeners registered via `Model.on(...)` are stored at the class level. Reset them between tests or use unique model classes per test module to avoid cross-test pollution.

---

## Adding a New Feature

### New QueryBuilder Method

1. Add the method to `QueryBuilder` in `pyloquent/query/builder.py` — it should mutate `self` (clone first if chaining) and `return self`.
2. If it requires new SQL output, add a `_compile_<feature>` method to `Grammar` and call it from `compile_select` (or the relevant compile method).
3. Override in `SQLiteGrammar` / `PostgresGrammar` / `MySQLGrammar` if the syntax differs.
4. Add a classmethod proxy on `Model` if it should be accessible as `Model.<method>()`.
5. Write unit tests (SQL shape) in `tests/unit/test_query_builder_extended.py`.
6. Write integration tests in `tests/integration/test_model_extended.py`.

### New Relationship Type

1. Create `pyloquent/orm/relations/<name>.py` subclassing `Relation[T]`.
2. Implement `add_constraints()`, `_create_query()`, and `get_results()` at minimum.
3. Add a convenience method on `Model` (e.g. `def has_one_through(...)`).
4. Register the export in `pyloquent/orm/relations/__init__.py` and `pyloquent/__init__.py`.
5. Add integration tests in `tests/integration/test_new_relationships.py`.

### New Model Event

1. Call `await self._fire_event('event_name')` at the appropriate point in `model.py` or `soft_deletes.py`.
2. Respect the abort pattern: `if await self._fire_event('event') is False: return False`.
3. Document the new event in the table in `DOCUMENTATION.md` and `README.md`.

### New Grammar

1. Subclass `Grammar` in `pyloquent/grammars/<dialect>_grammar.py`.
2. Override `_wrap_value`, `_wrap_table`, `_parameter`, and any dialect-specific compile methods.
3. Create a matching connection class in `pyloquent/database/<dialect>_connection.py`.
4. Register the driver in `ConnectionManager.add_connection`.
5. Add grammar tests in `tests/unit/test_grammar.py`.

---

## Common Pitfalls

- **`_force_deleting` in SoftDeletes** — this is a plain class attribute (not a Pydantic `PrivateAttr`). Accessing it on an instance works through normal attribute lookup, but it is not serialised.
- **`Model.delete()` MRO** — `Model.delete()` explicitly checks `__soft_deletes__` and delegates to `SoftDeletes.delete()`. Do not rely on Python MRO ordering when mixing `Model` and `SoftDeletes`.
- **Pivot query connections** — always construct pivot `QueryBuilder` instances with both `grammar` **and** `connection` from the parent model's query. A grammar-only builder has no connection and will raise `QueryException` on execution.
- **Pydantic `model_fields`** — use `self.__class__.model_fields` in instance methods to avoid the Pydantic v2.11 deprecation warning.
- **Empty list vs `None` sentinel** — `_instance_hidden = []` is falsy and cannot be distinguished from "never set". Use `None` as the "not yet overridden" sentinel.

---

## Code Style

- Follow the existing style — no reformatting of unrelated code in a PR.
- British English in all docstrings, comments, and documentation.
- No emoji in source files unless they were already present.
- Docstrings follow Google style (Args / Returns / Raises sections).
- `# noqa` comments are acceptable but prefer fixing the underlying issue.

---

## Release Checklist

1. Bump version in `pyloquent/__version__.py` and `pyproject.toml`.
2. Update `CHANGELOG.md` with a new section for the release.
3. Run the full test suite: `pytest tests/ --tb=short -q`.
4. Run the example: `python examples/basic_usage.py`.
5. Build: `python -m build`.
6. Publish: `twine upload dist/*`.
