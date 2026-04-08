# Pyloquent

> **Eloquent-inspired ORM for Python with Pydantic integration**

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Pyloquent brings the elegant ORM patterns from Laravel's Eloquent to Python, with full async/await support, Pydantic validation, and FastAPI integration.

## Features

- **🚀 Async/Await First** - Built from the ground up for async Python
- **✅ Pydantic Integration** - Full validation and type safety
- **🔗 Rich Relationships** - HasOne, HasMany, BelongsTo, BelongsToMany, HasOneThrough, HasManyThrough, MorphOne, MorphMany, MorphTo, MorphToMany, MorphedByMany
- **🗃️ Query Builder** - Fluent, chainable query interface with 70+ methods
- **💾 Multiple Drivers** - SQLite, PostgreSQL, MySQL, Cloudflare D1
- **⚡ Query Caching** - Memory, File, and Redis cache stores
- **📝 Migrations** - Full migration system with CLI
- **🧪 Testing Support** - Model factories and comprehensive test utilities
- **🎯 FastAPI Ready** - Lifespan context manager support
- **🔄 Soft Deletes** - Built-in soft delete with full event support
- **📡 Events/Observers** - Full model lifecycle hooks (retrieved, creating, created, updating, updated, saving, saved, deleting, deleted, restoring, restored)
- **🔒 Row Locking** - `lock_for_update()` / `for_share()` support
- **📦 Rich Collections** - 60+ collection methods for data manipulation
- **🔁 Upsert & Bulk Ops** - `upsert()`, `insert_or_ignore()`, `update_or_insert()`, `increment()`, `decrement()`
- **🔍 Subquery Support** - `where_exists()`, `where_not_exists()` with callable subqueries
- **📄 Pagination** - `paginate()`, `simple_paginate()`, `cursor()` streaming
- **🪟 CTEs & Window Functions** *(0.3.0)* - `with_cte()`, `with_recursive_cte()`, `select_window()` for `ROW_NUMBER`, `RANK`, running totals, etc.
- **🔀 Advanced Joins** *(0.3.0)* - `join_sub()`, `join_raw()`, `join_on()`, `full_join()` with callback ON clauses
- **🧬 Single Table Inheritance** *(0.3.0)* - `__discriminator__` / `__discriminator_value__` with automatic global scope
- **🔑 Composite Primary Keys** *(0.3.0)* - `__primary_key__ = ['col_a', 'col_b']`
- **🏷️ Hybrid Properties** *(0.3.0)* - `@hybrid_property` with instance getter and class-level SQL expression
- **🔧 Custom Type Decorators** *(0.3.0)* - `TypeDecorator`, `JSONType`, `CommaSeparatedType`, pluggable via `__casts__`
- **🗺️ Identity Map** *(0.3.0)* - `IdentityMap` per-session row cache with `IdentityMap.session()` async context
- **📡 Schema Reflection** *(0.3.0)* - `compile_get_tables/columns/indexes/foreign_keys` on all grammars
- **⚡ Batch Insert** *(0.3.0)* - `insert([...])` uses native `executemany` for bulk performance
- **🔄 Sync Support** *(0.3.0)* - `run_sync()`, `@sync` decorator, `SyncConnectionManager` for scripts/notebooks

## Quick Start

```bash
pip install pyloquent
```

```python
from typing import Optional
from pyloquent import Model, ConnectionManager

# Configure connection
manager = ConnectionManager()
manager.add_connection('default', {
    'driver': 'sqlite',
    'database': 'app.db',
}, default=True)

await manager.connect()

# Define model
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
users = await User.where('active', True).order_by('name').get()

# Update
user.name = 'Jane'
await user.save()

# Delete
await user.delete()
```

## Documentation

📖 **[Full Documentation](DOCUMENTATION.md)** - Comprehensive guide covering:
- Installation & Configuration
- Models & CRUD Operations
- Query Builder (60+ methods)
- All Relationship Types
- Collections (60+ methods)
- Mutators & Casting
- Query Scopes
- Events & Observers
- Query Caching
- Database Migrations
- Testing with Factories
- Cloudflare D1
- FastAPI Integration

## Quick Examples

### Relationships

```python
class Country(Model):
    def posts(self):
        return self.has_many_through(Post, User)   # HasManyThrough

    def latest_profile(self):
        return self.has_one_through(Profile, User)  # HasOneThrough

class Post(Model):
    def tags(self):
        return self.morph_to_many(Tag, 'taggable') # MorphToMany

class Tag(Model):
    def posts(self):
        return self.morphed_by_many(Post, 'taggable') # MorphedByMany

# Polymorphic many-to-many
await post.tags().attach([tag1.id, tag2.id])
await post.tags().sync([tag2.id, tag3.id])
tags = await post.tags().get()
```

### 0.3.0 — CTEs, Window Functions & Advanced Joins

```python
# Common Table Expression (WITH clause)
active_orders = await (
    Order.query
    .with_cte('recent', lambda q: q.from_('orders').where('created_at', '>', cutoff))
    .from_('recent')
    .order_by('created_at', 'desc')
    .get()
)

# Recursive CTE — tree traversal
from pyloquent import QueryBuilder
tree = await (
    QueryBuilder(grammar, conn)
    .with_recursive_cte(
        'tree',
        lambda q: q.from_('categories').where('parent_id', None),
        lambda q: q.from_('categories')
                   .join('tree', 'tree.id', '=', 'categories.parent_id'),
    )
    .from_('tree')
    .get()
)

# Window function — rank within partition
results = await (
    Sale.query
    .select('region', 'rep', 'amount')
    .select_window('RANK', partition_by=['region'], order_by=['amount DESC'], alias='region_rank')
    .get()
)

# Running total with ROWS framing
from pyloquent import WindowFrame
frame = WindowFrame(mode='ROWS', start='UNBOUNDED PRECEDING', end='CURRENT ROW')
results = await (
    Order.query
    .select('created_at', 'total')
    .select_window('SUM', 'total', order_by=['created_at'], frame=frame, alias='running_total')
    .get()
)

# Subquery join
results = await (
    User.query
    .join_sub(
        lambda q: q.from_('orders').select('user_id').where('status', 'paid'),
        alias='paid_orders',
        first='users.id', operator='=', second='paid_orders.user_id',
    )
    .get()
)

# Raw JOIN fragment
results = await (
    User.query
    .join_raw('LEFT JOIN audit_log al ON al.user_id = users.id AND al.active = ?', [1])
    .get()
)

# Callback ON clause (multi-condition)
results = await (
    User.query
    .join_on('orders', lambda j:
        j.on('orders.user_id', '=', 'users.id')
         .or_on('orders.alt_id', '=', 'users.id')
    )
    .get()
)
```

### 0.3.0 — Single Table Inheritance

```python
class Animal(Model):
    __table__ = 'animals'
    __fillable__ = ['name', 'type']

    id: Optional[int] = None
    name: str
    type: str = 'animal'

class Dog(Animal):
    __discriminator__ = 'type'
    __discriminator_value__ = 'dog'

class Cat(Animal):
    __discriminator__ = 'type'
    __discriminator_value__ = 'cat'

# Each subclass is automatically scoped — no WHERE type='dog' needed
dogs = await Dog.query.get()   # WHERE type = 'dog'
cats = await Cat.query.get()   # WHERE type = 'cat'
all_  = await Animal.query.get()  # no discriminator scope
```

### 0.3.0 — Composite Primary Keys

```python
class OrderItem(Model):
    __table__ = 'order_items'
    __primary_key__ = ['order_id', 'product_id']
    __incrementing__ = False
    __fillable__ = ['order_id', 'product_id', 'quantity']

    order_id: int
    product_id: int
    quantity: int = 1

item = OrderItem(order_id=1, product_id=42, quantity=3)
await item.save()
await item.delete()  # DELETE WHERE order_id=1 AND product_id=42
```

### 0.3.0 — Hybrid Properties

```python
from pyloquent import hybrid_property
from pyloquent.query.expression import RawExpression

class User(Model):
    first_name: str
    last_name: str

    @hybrid_property
    def full_name(self) -> str:
        return f'{self.first_name} {self.last_name}'

    @full_name.expression
    @classmethod
    def full_name(cls):
        return RawExpression("first_name || ' ' || last_name")

user = User(first_name='Jane', last_name='Doe')
print(user.full_name)       # 'Jane Doe'  (instance)
expr = User.full_name       # RawExpression  (class-level, for WHERE/SELECT)
```

### 0.3.0 — Custom Type Decorators

```python
import json
from pyloquent import TypeDecorator, register_type, JSONType

# Use a built-in type
class Product(Model):
    __casts__ = {'metadata': 'json', 'tags': 'comma_separated'}
    metadata: Optional[dict] = None
    tags: Optional[list] = None

# Define and register a custom type
class EncryptedType(TypeDecorator):
    impl = 'TEXT'
    def process_bind_param(self, value, dialect=None):
        return encrypt(value)   # your encryption logic
    def process_result_value(self, value, dialect=None):
        return decrypt(value)

register_type('encrypted', EncryptedType())

class Secret(Model):
    __casts__ = {'api_key': 'encrypted'}
    api_key: Optional[str] = None
```

### 0.3.0 — Identity Map

```python
from pyloquent import IdentityMap

# Scoped session — same DB row → same Python object
async with IdentityMap.session() as imap:
    u1 = await User.query.with_identity_map(imap).find(1)
    u2 = await User.query.with_identity_map(imap).find(1)
    assert u1 is u2   # True — no second query hydration
```

### 0.3.0 — Batch Insert & SQLite WAL Mode

```python
# Batch insert uses native executemany automatically
await Product.query.insert([
    {'name': 'Widget A', 'price': 9.99},
    {'name': 'Widget B', 'price': 19.99},
    {'name': 'Widget C', 'price': 29.99},
])  # one executemany call, not three execute() calls

# Enable WAL mode for concurrent SQLite reads
manager.add_connection('default', {
    'driver': 'sqlite',
    'database': 'app.db',
    'journal_mode': 'wal',
}, default=True)
```

### 0.3.0 — Sync Support

```python
from pyloquent.sync import run_sync, sync, SyncConnectionManager

# Run any coroutine synchronously
user = run_sync(User.find(1))

# Decorator form
@sync
async def get_active_users():
    return await User.where('active', True).get()

users = get_active_users()  # no await needed

# Synchronous script / notebook usage
with SyncConnectionManager({'default': {'driver': 'sqlite', 'database': 'app.db'}}) as mgr:
    rows = mgr.table('users').where('active', True).get()
```

### Query Builder — Methods

```python
# Atomic increment / decrement
await User.where('id', 1).increment('score', 10)
await user.decrement('credits', 5)

# Upsert (insert or update on conflict)
await User.query.upsert(
    [{'email': 'alice@example.com', 'name': 'Alice', 'score': 100}],
    unique_by=['email'],
    update_columns=['name', 'score'],
)

# Insert or ignore duplicates silently
await User.query.insert_or_ignore([{'email': 'existing@example.com', 'name': 'Dup'}])

# Update or insert
await User.query.update_or_insert({'email': 'bob@example.com'}, {'name': 'Bob'})

# WHERE EXISTS subquery
users = await User.where_exists(
    lambda q: q.from_('orders').where_raw('"orders"."user_id" = "users"."id"')
).get()

# Row locking (ignored on SQLite, honoured on PostgreSQL/MySQL)
user = await User.where('id', 1).lock_for_update().first()

# Conditional clauses
results = await User.query \
    .when(search_term, lambda q: q.where('name', 'like', f'%{search_term}%')) \
    .unless(include_inactive, lambda q: q.where('active', True)) \
    .get()

# Paginate with metadata
page = await User.paginate(per_page=15, page=2)
# {'data': [...], 'total': 120, 'per_page': 15, 'current_page': 2, 'last_page': 8}

# Cursor streaming (memory-efficient)
async for user in User.query.cursor():
    process(user)

# Debug raw SQL
print(User.where('active', True).where('score', '>', 50).to_raw_sql())
# SELECT * FROM "users" WHERE "active" = 1 AND "score" > 50
```

### Model Instance Methods

```python
user = await User.find(1)

# Atomic update
await user.increment('login_count')

# Instance update
await user.update({'name': 'New Name'})

# Replicate with overrides
replica = await user.replicate({'email': 'copy@example.com'})

# Serialisation control
user.make_visible('secret_field')
user.make_hidden('internal_field')
d = user.to_dict()   # respects __hidden__ / make_visible / make_hidden

# Change tracking
await user.save()
print(user.was_changed('name'))   # True / False
print(user.get_changes())         # {'name': 'New Name'}

# Batch delete
await User.destroy(1, 2, 3)

# Find many
users = await User.find_many([1, 2, 3])
```

### Soft Deletes with Events

```python
from pyloquent import Model, SoftDeletes

class Post(Model, SoftDeletes):
    __table__ = 'posts'
    deleted_at: Optional[datetime] = None

# Register lifecycle hooks
Post.on('deleting',  lambda m: print(f'Deleting {m.id}'))
Post.on('deleted',   lambda m: print(f'Deleted  {m.id}'))
Post.on('restoring', lambda m: print(f'Restoring {m.id}'))
Post.on('restored',  lambda m: print(f'Restored  {m.id}'))

# Abort soft delete by returning False from 'deleting'
Post.on('deleting', lambda m: False if m.is_locked else None)

await post.delete()        # soft delete  → fires deleting / deleted
await post.restore()       # undo         → fires restoring / restored
await post.force_delete()  # permanent

posts = await Post.with_trashed().get()
trashed = await Post.only_trashed().get()
```

### Collections — 60+ Methods

```python
users = await User.all()

# Presence
users.is_empty()
users.contains('name', 'Alice')
users.first_where('age', '>=', 18)
users.sole()            # raises if not exactly one

# Set operations
users.diff(other)
users.intersect(other)
users.unique('email')
users.duplicates('domain')

# Grouping / splitting
groups = users.group_by('country')
active, inactive = users.partition(lambda u: u.is_active)
chunks = users.split(3)
removed = users.splice(2, 1, [replacement])

# Transformations
users.flat_map(lambda u: u.roles)
users.map_with_keys(lambda u: (u.id, u.name))
users.map_into(UserDTO)
users.key_by('id')

# Statistics
users.reduce(lambda acc, u: acc + u.score, 0)
users.count_by(lambda u: u.country)
users.median('age')
users.mode('country')

# Pipelines
result = users.pipe(lambda c: c.filter(...).map(...))
users.tap(lambda c: logger.debug(f'{c.count()} users'))
filtered = users.when(flag, lambda c: c.filter(pred))

# Mutation
users.push(new_user)
users.prepend(admin)
users.shuffle()
sample = users.random(5)
users.pad(10, placeholder_user)

# Serialisation
users.to_json()
users.only('id', 'name', 'email')
users.except_('password')
users.where_not_in('status', ['banned', 'pending'])
users.take(10)
users.skip(20)
users.take_while(lambda u: u.score > 0)
users.sort_by('name')
users.sort_by_desc('created_at')
```

### Events & Observers

```python
class User(Model):
    @classmethod
    def boot(cls):
        super().boot()
        cls.on('retrieved', lambda u: audit_log('read', u))
        cls.on('creating',  lambda u: setattr(u, 'slug', slugify(u.name)))
        cls.on('deleting',  lambda u: False if u.is_admin else None)  # abort
```

### Migrations

```bash
pyloquent make:migration create_users_table --create
pyloquent migrate
pyloquent migrate:rollback
pyloquent migrate:fresh
```

### 0.3.0 — Cloudflare D1 Native Worker Binding

**`wrangler.jsonc`** — `compatibility_flags: ["python_workers"]` is required:

```jsonc
{
  "name": "my-pyloquent-worker",
  "main": "src/entry.py",
  "compatibility_flags": ["python_workers"],
  "compatibility_date": "2026-04-08",
  "d1_databases": [
    {
      "binding": "DB",
      "database_name": "YOUR_DB_NAME",
      "database_id": "YOUR_DB_ID"
    }
  ]
}
```

```python
# src/entry.py
from workers import Response, WorkerEntrypoint
from pyloquent import ConnectionManager, Model
from pyloquent.database.manager import set_manager
from typing import Optional

class User(Model):
    __table__ = 'users'
    __fillable__ = ['name', 'email']
    id: Optional[int] = None
    name: str
    email: str

class Default(WorkerEntrypoint):
    async def fetch(self, request):
        # self.env.DB is the D1 binding declared in wrangler.jsonc
        manager = ConnectionManager.from_binding(self.env.DB)
        set_manager(manager)

        users = await User.where('active', True).get()
        return Response.json(users.to_dict_list())
```

```python
# Low-level: batch writes, dump, DDL, schema reflection
from pyloquent.d1.binding import D1BindingConnection, D1Statement

conn = D1BindingConnection(self.env.DB)
await conn.connect()

# Atomic multi-statement batch
results = await conn.batch([
    ("INSERT INTO users (name) VALUES (?)", ["Alice"]),
    ("INSERT INTO users (name) VALUES (?)", ["Bob"]),
    ("SELECT COUNT(*) AS n FROM users", None),
])
count = results[-1][0]["n"]   # 2

# Transactions via db.batch() (no BEGIN/COMMIT in Workers)
async with manager.transaction():
    await User.create({'name': 'Carol', 'email': 'carol@example.com'})
    await Post.create({'user_id': 1, 'title': 'Hello'})

# Bulk insert — one round-trip
await conn.execute_many(
    "INSERT INTO products (name, price) VALUES (?, ?)",
    [["A", 9.99], ["B", 19.99], ["C", 29.99]],
)

# Schema reflection
tables  = await conn.get_tables()
columns = await conn.get_columns('users')

# Database dump (backup)
data = await conn.dump()  # bytes

# D1Statement prepared-statement wrapper
stmt = D1Statement(conn, "SELECT * FROM users WHERE id = ?").bind(1)
row  = await stmt.first()   # dict or None
rows = await stmt.all()     # list of dicts
```

### FastAPI Integration

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pyloquent import ConnectionManager

manager = ConnectionManager()
manager.add_connection('default', {'driver': 'sqlite', 'database': 'app.db'}, default=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await manager.connect()
    yield
    await manager.disconnect()

app = FastAPI(lifespan=lifespan)

@app.get('/users')
async def list_users(page: int = 1):
    return await User.paginate(per_page=20, page=page)
```

## Available Drivers

| Driver | Package / Mode | Status |
|--------|---------------|--------|
| SQLite | Built-in (`aiosqlite`) | ✅ Ready |
| PostgreSQL | `asyncpg` | ✅ Ready |
| MySQL | `aiomysql` | ✅ Ready |
| Cloudflare D1 (HTTP) | `httpx` + REST API | ✅ Ready |
| Cloudflare D1 (Binding) | Native Worker binding (`env.DB`) | ✅ Ready *(0.3.0)* |

## CLI Commands

```bash
pyloquent make:model User
pyloquent make:model User --migration
pyloquent make:migration create_users_table --create
pyloquent migrate
pyloquent migrate:rollback
pyloquent migrate:status
pyloquent migrate:fresh
```

## Why Pyloquent?

### Why use an ORM at all?

If you have ever built a Python application that talks to a database, you have probably written something like this:

```python
cursor.execute(
    "SELECT * FROM users WHERE active = ? AND created_at > ? ORDER BY name",
    (True, cutoff_date)
)
rows = cursor.fetchall()
users = [{"id": r[0], "name": r[1], "email": r[2]} for r in rows]
```

That works — until it doesn't. As soon as you need to join another table, filter on a related record, or serialise the result to JSON, the SQL strings grow, the column-index magic breaks, and the logic scatters across the codebase. An ORM solves this by letting you think in **Python objects and relationships** rather than SQL strings:

```python
users = await User.where('active', True) \
                  .where('created_at', '>', cutoff_date) \
                  .order_by('name') \
                  .get()
```

Concrete benefits that matter day-to-day:

- **No raw string SQL for standard queries** — inserts, updates, deletes, joins, and aggregates are method calls with IDE autocomplete and no typos.
- **Automatic SQL-injection protection** — values are always parameterised; you never concatenate user input into a query string.
- **Relationships as first-class objects** — instead of writing a JOIN, you define `def posts(self): return self.has_many(Post)` once, then call `await user.posts().get()` anywhere. Eager loading (`with_`) avoids N+1 queries automatically.
- **Validation at the model layer** — field types, default values, and constraints live alongside the data, not scattered across form handlers.
- **Database portability** — switching from SQLite in development to PostgreSQL in production is a config change, not a rewrite.
- **Change tracking and dirty checking** — `user.was_changed('email')` tells you what mutated between load and save without manual diffing.
- **A single place for business rules** — lifecycle events (`creating`, `updating`, `deleting`) let you enforce invariants (slugify a name on create, block deletion of locked records) without touching every call-site.

### Why Pyloquent specifically?

Python already has capable ORMs. Here is where Pyloquent fits in:

| | Pyloquent | SQLAlchemy | Django ORM | Tortoise ORM |
|---|---|---|---|---|
| **Async-first** | ✅ native | ⚠ async extension | ⚠ ASGI layer | ✅ native |
| **Pydantic v2 models** | ✅ built-in | ❌ separate step | ❌ separate step | ❌ separate step |
| **Fluent chainable builder** | ✅ | ⚠ verbose Core API | ✅ | ✅ |
| **Framework-agnostic** | ✅ | ✅ | ❌ Django only | ✅ |
| **Polymorphic relations** | ✅ full set | ⚠ manual | ⚠ limited | ⚠ limited |
| **Built-in soft deletes** | ✅ | ❌ | ❌ | ❌ |
| **Model events/observers** | ✅ | ⚠ | ✅ signals | ⚠ |
| **Query caching** | ✅ | ❌ | ❌ | ❌ |
| **CTEs / window functions** | ✅ | ✅ | ⚠ limited | ⚠ |
| **Composite primary keys** | ✅ | ✅ | ✅ | ⚠ |
| **Single table inheritance** | ✅ | ✅ | ⚠ manual | ⚠ |
| **Identity map / row cache** | ✅ | ✅ | ⚠ | ⚠ |
| **Hybrid properties** | ✅ | ✅ | ❌ | ❌ |
| **Custom type decorators** | ✅ | ✅ | ⚠ | ❌ |
| **Schema reflection** | ✅ all drivers | ✅ | ✅ | ⚠ |
| **Batch insert (executemany)** | ✅ | ✅ | ✅ | ✅ |
| **Sync support wrapper** | ✅ | ✅ | ✅ | ❌ |

**You do not need to know Laravel to benefit from Pyloquent.** The design choices simply happen to be good ones:

- **Pydantic v2 as the model layer** means your ORM models *are* your API schemas. Define a `User` model once and use it for database I/O, request validation, and response serialisation — no separate `UserSchema` class.
- **Async-native from the start** means it works naturally with FastAPI, Starlette, Litestar, and any other async framework without thread-pool workarounds or synchronous blocking.
- **Active Record pattern** keeps things simple: the model knows how to save and load itself. There is no separate session, unit-of-work, or mapper to configure — you call `await User.find(1)` and get a `User` back.
- **A fluent query builder over raw SQL** means you get the full power of SQL (window functions, subqueries, CTEs) via method chaining when you need it, without giving up readability.
- **Everything included** — soft deletes, model events, query caching, database migrations, model factories, and a CLI — so you are not stitching together five separate packages.

In short: if you are building an async Python application and want your database code to be readable, safe, and testable without learning a framework or writing boilerplate, Pyloquent is worth a look.

### Quick comparison

```python
# SQLAlchemy (Core + ORM)
from sqlalchemy import select
stmt = select(User).where(User.active == True).order_by(User.name)
async with async_session() as session:
    result = await session.execute(stmt)
    users = result.scalars().all()

# Pyloquent
users = await User.where('active', True).order_by('name').get()
```

```python
# With relationships — SQLAlchemy
stmt = select(User).options(selectinload(User.posts)).where(User.id == user_id)

# Pyloquent
user = await User.with_('posts').find(user_id)
posts = user.posts  # already loaded
```

- **Familiar API** — If you know Laravel Eloquent, you know Pyloquent
- **Type Safe** — Full Pydantic v2 integration for validation and serialisation
- **Async Native** — Built for modern async Python (FastAPI, Starlette, etc.)
- **Production Ready** — 100% test coverage, comprehensive test suite
- **Framework Agnostic** — Works with FastAPI, Starlette, Litestar, or standalone
- **Cloud Native** — Cloudflare D1 support for edge deployments

## Contributing

Contributions are welcome! Please see [AGENTS.md](AGENTS.md) for development guidelines.

## License

Pyloquent is open-sourced software licensed under the [MIT license](LICENSE).

---

<p align="center">Built with ❤️ for the Python community</p>
