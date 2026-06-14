# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.8] - 2026-06-14

### Added

- **Full table-alteration support in `Schema.table()`** — previously only `ADD COLUMN` worked and every drop/rename method was a silent no-op stub. The Blueprint now records alteration commands (modelled on Laravel's Blueprint) and the grammars compile them per dialect:
  - `drop_column(name | [names])`, `rename_column(from, to)`
  - `drop_index(name | [columns])`, `drop_unique(...)`, `drop_full_text(...)`, `drop_spatial_index(...)`, `rename_index(from, to)`
  - `drop_primary([name])`, `drop_foreign(name | [columns])`, `drop_constrained_foreign_id(column)`
  - Convenience drops: `drop_timestamps()`, `drop_soft_deletes()`, `drop_remember_token()` (previously broken — missing `self`), `drop_morphs(name)`
  - Adding indexes and foreign keys in alter mode (`compile_alter_table` previously ignored `blueprint.indexes` / `blueprint.foreign_keys`)
  - Column modification via `.change()` — `MODIFY COLUMN` on MySQL, `ALTER COLUMN TYPE/SET|DROP NOT NULL/SET DEFAULT` on PostgreSQL
  - **SQLite** emits native `ADD COLUMN` / `RENAME COLUMN` (3.25+) / `DROP COLUMN` (3.35+); dropping a primary/foreign key, renaming an index, or `.change()` raise a clear `NotImplementedError` (SQLite requires a table rebuild). Coverage in `tests/unit/test_grammar_alter.py` and `tests/integration/test_schema_alter.py`.

- **Generate migrations from models** (`pyloquent.migrations.generator`) — Pyloquent models carry typed Pydantic fields, so a create-table migration can be scaffolded from a model (something Eloquent cannot do). CLI: `pyloquent make:migration <name> --model app.models.User`. Field types map to Blueprint calls (`str→string`, `int→integer`, `datetime→timestamp`, `dict`/`list→json`, `UUID→uuid`, `Decimal→decimal`, …); `Optional[...]→.nullable()`, literal defaults `→.default(...)`, `created_at`/`updated_at`→`timestamps()`, soft-delete `deleted_at`→`soft_deletes()`; primary key honours `__primary_key__` / `__incrementing__` / `__key_type__`.

- **Schema diff migrations** — `pyloquent migrate:diff <name> --model app.models.User --config ...` introspects the live table and emits an alter migration that adds model columns missing from the database and drops database columns no longer on the model. Coverage in `tests/unit/test_migration_generator.py` and `tests/integration/test_cli_generate.py`.

### Notes

- The alter API names mirror Laravel's Blueprint for familiarity.
- Test count: **1120 passing, 4 skipped** (+39 from 0.3.7); 100% coverage maintained.

## [0.3.7] - 2026-06-14

### Fixed

- **`Model.create()` / `save()` crashed for non-incrementing string/UUID primary keys** — `_perform_insert` always force-assigned the database's integer `lastrowid` to the primary key, ignoring `__incrementing__`. A model with `__incrementing__ = False` and a caller-supplied string key (e.g. `id: str`) therefore had its key overwritten with an `int`, raising `pydantic_core.ValidationError: Input should be a valid string`. The insert path now honours `__incrementing__`: for non-incrementing single primary keys the row is inserted as-is and the caller's key is preserved. Regression coverage in `tests/integration/test_string_primary_key.py`.

### Notes

- Discovered in the wild by the downstream Ometsuke project.
- Test count: **1081 passing, 4 skipped** (+3 from 0.3.6); 100% coverage maintained.

## [0.3.6] - 2026-06-14

### Fixed

- **Fluent column modifiers crashed with `'bool' object is not callable`** — chaining such as `table.string("uid").unique()` or `table.string("name").nullable(False)` raised a `TypeError` because `Column` was a dataclass whose `nullable` / `unique` / `index` / etc. were plain attributes, not callable setters. `Column` now backs every modifier with a non-data descriptor: reading (`column.nullable`) still returns the stored value (so grammars keep using `if not column.nullable` and identity checks keep working), while calling (`column.nullable()`) sets the modifier and returns the column for chaining. Supported chainable modifiers: `nullable`, `unsigned`, `primary`, `auto_increment`, `unique`, `index`, `first`, `change`, `default`, `comment`, `after`, `charset`, `collation`, `virtual_as`, `stored_as`, `srid`.
  - Column-level `.unique()` / `.index()` now emit the matching `CREATE [UNIQUE] INDEX` statements from `compile_create_table`.
  - The `DEFAULT` clause skips unset value modifiers (which read back as a callable proxy).
  - Regression coverage in `tests/unit/test_blueprint_helpers.py`.

- **`pyloquent migrate` (and `migrate:rollback` / `migrate:status` / `migrate:fresh`) failed with `'SQLiteConnection' object has no attribute 'connection'`** — the CLI constructed `SchemaBuilder(connection)` with a raw connection, but `SchemaBuilder` resolves its connection through a `ConnectionManager` (`manager.connection()`). The `DatabaseCommand` base now builds and connects a `ConnectionManager` from the loaded config, passes it to `SchemaBuilder`, hands the runner the underlying connection, and registers the manager globally via `set_manager` so migrations referencing models resolve correctly. Integration coverage in `tests/integration/test_cli_migrate.py`.

### Notes

- Both fixes were discovered in the wild by the downstream Ometsuke project.
- Test count: **1078 passing, 4 skipped** (+17 from 0.3.5); 100% coverage maintained.

## [0.3.5] - 2026-05-12

### Tests

- Restore 100% coverage. The dialect-specific overrides introduced in
  0.3.4 (SQLite / Postgres / MySQL `_compile_auto_increment_column`)
  shadowed the base `Grammar` implementation, leaving 11 lines
  unreachable through the per-dialect test paths. Added
  `tests/unit/test_grammar_base_fallbacks.py` which exercises the
  base class directly via a minimal `Grammar` subclass:

  * the inline `PRIMARY KEY` branch for non-auto-increment primary
    columns (e.g. UUID PKs),
  * the MySQL-flavoured fallback for grammars that don't override
    `_compile_auto_increment_column`,
  * the bare `_compile_auto_increment()` keyword.

  Total: 1061 passing, 4 skipped (+5 from 0.3.4).

## [0.3.4] - 2026-05-12

### Fixed

- **`Blueprint.timestamps()` / `timestamps_tz()` / `soft_deletes()` / `soft_deletes_tz()` crashed with `'bool' object is not callable`** — the helpers called `.nullable()` on the freshly-returned `Column`, but `Column` is a dataclass whose `nullable` field is a plain bool, not a fluent setter. They now set the attribute directly. Regression coverage in `tests/unit/test_blueprint_helpers.py`.

- **SchemaBuilder emitted invalid DDL in every dialect for auto-incrementing primary keys**. `id()`, `increments()`, `big_increments()`, etc. all produced `BIGINT UNSIGNED NULL AUTOINCREMENT` — which SQLite, PostgreSQL, and MySQL all reject:
  - **SQLite** now emits `"id" INTEGER PRIMARY KEY AUTOINCREMENT` (the only valid ROWID-alias form).
  - **PostgreSQL** now emits `"id" BIGSERIAL PRIMARY KEY` (or `SERIAL` / `SMALLSERIAL` for `increments()` / `small_increments()`).
  - **MySQL** now emits `` `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY `` (note: `AUTO_INCREMENT` with underscore is the correct MySQL spelling; the SQLite-style `AUTOINCREMENT` keyword is no longer leaked across dialects).
  - Each dialect's grammar now overrides `_compile_auto_increment_column` independently. Inline `PRIMARY KEY` is also emitted for any column with `column.primary = True`.
  - Acid-test coverage in `tests/unit/test_grammar_create_table.py` (runs the generated SQLite DDL against an in-memory `sqlite3` and asserts auto-increment works).

- **`__casts__ = "json"` was asymmetric — it decoded on read but did not re-encode on `.save()`**. `Model._perform_insert` correctly went through `_get_attributes_for_save()` (which calls `_set_cast_attribute`), but `_perform_update` used `_get_dirty_attributes()` directly and shipped a Python `dict` / `list` straight to the driver, where it crashed with `Error binding parameter: type 'dict' is not supported`. The cast is now applied symmetrically. Regression coverage in `tests/integration/test_json_cast_save.py`.

### Added

- **`QueryBuilder.order_by_raw(sql, bindings=None)`** — for dialect-specific ORDER BY expressions the builder doesn't model natively (e.g. `NULLS FIRST`, `COALESCE(...)`, computed `CASE` ordering). Bindings are tracked in the existing `order` bucket and bubble up to the final binding list. Companion type `RawOrderClause` exported from `pyloquent.query.expression`. Coverage in `tests/unit/test_order_by_raw.py`.

### Notes

- All four fixes were discovered in the wild by the downstream Mado project (built on Pyloquent + FastAPI). The Mado tests pass against this release without per-table workarounds.
- Test count: **1056 passing, 4 skipped** (1034 → 1056, +22).

## [0.3.3] - 2026-04-08

### Fixed

- **`UserWarning: Field name "value" shadows an attribute in parent "Model"`** — `Model` and `QueryBuilder` exposed a classmethod / method named `value()` (a proxy for retrieving a single scalar column from the first result).  Any user model with a `value` field would trigger a Pydantic v2 `UserWarning` on class creation.  Renamed `value()` → `scalar()` on both `QueryBuilder` and `Model` to free `value` as a safe field name.  Update call sites: `Model.scalar(column)` / `qs.scalar(column)`.

## [0.3.2] - 2026-04-08

### Fixed

- **CI: optional-driver tests skipped when not installed** — tests that patch `asyncpg.create_pool` or `aiomysql.create_pool` now call `pytest.importorskip` so they are gracefully skipped (not failed) in environments where those optional drivers are absent.

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
