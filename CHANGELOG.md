# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.1] - 2026-04-08

### Fixed

- **`MySQLConnection.fetch_all` / `fetch_one`** — `aiomysql` was only imported inside `connect()` but referenced as `aiomysql.DictCursor` in `fetch_all` and `fetch_one` without a local import, causing `NameError: name 'aiomysql' is not defined` on every MySQL query.  Both methods now import `aiomysql` locally before use.

### Added

- **Connection health checks** — all three driver connections (`SQLiteConnection`, `PostgresConnection`, `MySQLConnection`) now accept three new config keys:
  - `pool_pre_ping` *(bool, default `False`)* — executes `SELECT 1` before every query and transparently reconnects if the connection is stale.  Equivalent to SQLAlchemy's `pool_pre_ping`.
  - `pool_recycle` *(int seconds, default `None`)* — maximum connection age before recycling.  For SQLite this triggers a reconnect on the next query after the threshold; for asyncpg it is forwarded as `max_inactive_connection_lifetime`; for aiomysql it is forwarded as the native `pool_recycle` pool option.
  - `reconnect_on_error` *(bool, default `False`)* — if a query raises a driver-level exception *and* a subsequent `ping()` confirms the connection is dead, the driver disconnects, reconnects, and retries the original statement once before re-raising as `QueryException`.  SQL errors on a live connection (bad table name, constraint violation, etc.) do **not** trigger reconnect.
- **`Connection.ping()`** — base-class implementation that temporarily disables `pool_pre_ping` to avoid infinite recursion, then issues `SELECT 1` via `fetch_one`.  All three concrete drivers override this with a lighter, pool-native check.
- **`Connection.ensure_connected()`** — evaluates `pool_recycle` age and `pool_pre_ping` liveness, then calls `disconnect` + `connect` if a reconnect is needed.  Called automatically at the top of every `execute`, `fetch_all`, and `fetch_one` in `SQLiteConnection`.

## [0.3.0] - 2026-04-08

### Added

#### Query Builder — Advanced SQL
- **CTEs** (`with_cte`, `with_recursive_cte`) — attach named `WITH` and `WITH RECURSIVE` clauses to any query via a fluent callback or a `QueryBuilder` instance.
- **Window functions** (`select_window`) — add `ROW_NUMBER`, `RANK`, `DENSE_RANK`, `SUM`, `AVG`, and any other window function with `PARTITION BY`, `ORDER BY`, and `ROWS/RANGE` framing.
- **Full outer join** (`full_join`) — `FULL OUTER JOIN` support across all grammars.
- **Raw joins** (`join_raw`) — attach a verbatim JOIN fragment including custom `ON` conditions and bindings.
- **Subquery joins** (`join_sub`, `left_join_sub`) — join against an inline subquery with an alias; accepts a builder or callback.
- **Callback ON clauses** (`join_on`) — build complex multi-condition `ON` clauses with `j.on(…).or_on(…)` inside a callback.
- `JoinClause.on()` and `JoinClause.or_on()` fluent helpers for multi-condition joins.

#### Batch Insert
- `Connection.execute_many(sql, rows)` — base fallback implementation that loops `execute()`.
- `SQLiteConnection.execute_many` — native `aiosqlite.executemany` override for batch performance.
- `QueryBuilder.insert()` now automatically uses `execute_many` when inserting multiple rows.

#### Schema Reflection
- `SQLiteGrammar`: `compile_table_exists`, `compile_column_exists`, `compile_index_exists`, `compile_get_tables`, `compile_get_columns`, `compile_get_indexes`, `compile_get_foreign_keys`.
- `PostgresGrammar`: full `information_schema` + `pg_indexes` reflection.
- `MySQLGrammar`: full `information_schema` + `statistics` reflection.

#### Model Enhancements
- **Composite primary keys** — `__primary_key__` now accepts `List[str]`. `_get_key()`, `_perform_update()`, `_perform_insert()`, and `delete()` all handle composite keys correctly.
- **Single Table Inheritance** — declare `__discriminator__` (column name) and `__discriminator_value__` (value for this subclass) on any `Model` subclass. `ModelMeta` automatically registers a global scope so every query is scoped to the right rows.
- **TypeDecorator integration** — `__casts__` now accepts `TypeDecorator` instances, subclasses, or string aliases registered via `register_type()`. Built-in types: `JSONType`, `CommaSeparatedType`.

#### New ORM Modules
- `pyloquent.orm.hybrid_property.hybrid_property` — descriptor giving Python-property behaviour on instances and a configurable SQL expression at the class level via `.expression`.
- `pyloquent.orm.type_decorator` — `TypeDecorator`, `JSONType`, `CommaSeparatedType`, `register_type`, `get_type`.
- `pyloquent.orm.identity_map.IdentityMap` — lightweight per-session row cache. Attach to any query with `query.with_identity_map(imap)`. Async context manager `IdentityMap.session()` scopes and auto-clears the map.
- `pyloquent.sync` — `run_sync(coro)`, `@sync` decorator, `SyncConnectionManager`, `SyncQueryProxy` for use in synchronous contexts (scripts, notebooks, tests).

#### SQLite Driver
- `journal_mode` config key — set `'wal'` for WAL mode (recommended for concurrent reads).
- `foreign_keys` config key — disable FK enforcement when needed.

#### QueryBuilder
- `with_identity_map(imap)` — attach an `IdentityMap` to a query; instances are cached and deduped on hydration.
- `clone()` now also copies `_ctes`, `_identity_map`, `_eager_loads`, `_scopes`, `_removed_scopes`, and cache state.

#### Cloudflare D1 — Native Worker Binding
- `D1BindingConnection` — full `Connection` subclass that wraps a native D1 binding (`env.DB`) without any HTTP round-trips.
  - `execute()`, `fetch_all()`, `fetch_one()`, `insert_get_id()` — core statement methods.
  - `execute_many(sql, rows)` — sends all rows via `db.batch()` in a single atomic call.
  - `batch(queries)` — low-level multi-statement atomic execution (`[(sql, bindings), ...]`).
  - `exec(sql)` — DDL via `db.exec()` (no parameter binding).
  - `dump()` — full SQLite database export as `bytes`.
  - `begin_transaction()` / `commit()` / `rollback()` — transaction-via-batch accumulation (no `BEGIN`/`COMMIT` SQL).
  - `get_tables()`, `table_exists()`, `column_exists()`, `get_columns()`, `get_indexes()`, `get_foreign_keys()` — schema reflection helpers.
  - `table(name)` — `QueryBuilder` factory shortcut.
- `D1Statement` — Pythonic prepared-statement wrapper with `.bind()`, `.all()`, `.first()`, `.run()`.
- `ConnectionManager.from_binding(binding)` — one-liner factory that returns a ready-to-use `ConnectionManager` with no `await connect()` required.
- `'d1_binding'` driver registered in `ConnectionManager._create_connection()` for config-dict construction.
- `_to_python()` / `_await_js()` helpers handle both real Pyodide JS proxies and duck-typed Python mocks transparently.

### Changed
- Version bumped to **0.3.0**.
- `QueryBuilder.insert()` now routes through `execute_many` for multi-row lists (single-row inserts are unchanged).

## [0.1.0] - 2024-XX-XX

### Added
- Initial release of Pyloquent
- Query Builder with fluent API
  - WHERE clauses (basic, IN, BETWEEN, NULL, NOT)
  - JOIN support (INNER, LEFT, RIGHT, CROSS)
  - ORDER BY, GROUP BY, HAVING
  - LIMIT and OFFSET
  - Aggregate functions (COUNT, MAX, MIN, SUM, AVG)
  - Raw SQL support
- Grammar-based SQL compilation
  - SQLite grammar
  - PostgreSQL grammar
  - MySQL grammar
- Model base class
  - Pydantic integration for validation
  - CRUD operations (Create, Read, Update, Delete)
  - Mass assignment protection (fillable/guarded)
  - Hidden attributes for serialisation
  - Dirty tracking
  - Model metadata via metaclass
- Collection class
  - Filtering (where, where_in, filter, reject)
  - Sorting (sort_by, sort_by_desc)
  - Transformation (pluck, map, key_by)
  - Aggregates (sum, avg, max, min)
  - Chunking support
- Relationships
  - HasOne - one-to-one relationships
  - HasMany - one-to-many relationships
  - BelongsTo - inverse relationships
  - Eager loading with `load()` method
- Database connections
  - SQLite support via aiosqlite
  - PostgreSQL support via asyncpg
  - MySQL support via aiomysql
  - Connection pooling for PostgreSQL and MySQL
  - Transaction support
- Connection Manager
  - Multiple named connections
  - FastAPI lifespan integration
  - Async context manager support
- Comprehensive test suite
  - Unit tests for grammar compilation
  - Unit tests for query builder
  - Unit tests for collection
  - Integration tests for CRUD operations
  - Integration tests for relationships
- Documentation
  - README with usage examples
  - FastAPI integration example
  - Basic usage example

### Features

#### Query Builder Example
```python
users = await User.where('is_active', True) \
    .where_in('role', ['admin', 'moderator']) \
    .order_by('created_at', 'desc') \
    .limit(10) \
    .get()
```

#### Model Example
```python
class User(Model):
    __table__ = 'users'
    __fillable__ = ['name', 'email']
    
    id: Optional[int] = None
    name: str
    email: EmailStr
    
    def posts(self):
        return self.has_many(Post)
```

#### CRUD Operations
```python
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
```

#### Relationships
```python
# Get related models
posts = await user.posts().get()
author = await post.author().get()

# Create through relationship
post = await user.posts().create({'title': 'New Post'})
```

### Technical Details

- **Architecture**: Grammar-based SQL compilation separates query building from execution
- **Async-First**: All database operations use async/await
- **Type Safety**: Full type hints and Pydantic validation
- **Testability**: SQL can be compiled and tested without database connection
- **Framework Integration**: Native FastAPI support with lifespan events

### Dependencies

- pydantic >= 2.0.0
- pydantic-core >= 2.0.0
- asyncpg >= 0.28.0 (PostgreSQL)
- aiomysql >= 0.2.0 (MySQL)
- aiosqlite >= 0.19.0 (SQLite)
- typing-extensions >= 4.0.0

[0.1.0]: https://github.com/pyloquent/pyloquent/releases/tag/v0.1.0
