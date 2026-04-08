# Pyloquent Documentation

> **Eloquent-inspired ORM for Python with Pydantic integration and async support**

Pyloquent brings the elegant ORM patterns from Laravel's Eloquent to Python, with full async/await support, Pydantic v2 validation, and FastAPI integration.

---

## Table of Contents

- [Installation](#installation)
- [Getting Started](#getting-started)
- [Models](#models)
  - [Model Conventions](#model-conventions)
  - [Default Attribute Values](#default-attribute-values)
  - [Hidden & Visible Fields](#hidden--visible-fields)
  - [Instance Methods](#instance-methods)
- [Retrieving Models](#retrieving-models)
  - [Chunking Results](#chunking-results)
  - [Pagination](#pagination)
  - [Cursor Streaming](#cursor-streaming)
- [Inserting & Updating Models](#inserting--updating-models)
  - [Inserts](#inserts)
  - [Updates](#updates)
  - [Upsert & Bulk Operations](#upsert--bulk-operations)
  - [Increment & Decrement](#increment--decrement)
  - [Mass Assignment](#mass-assignment)
- [Deleting Models](#deleting-models)
  - [Soft Deletes](#soft-deletes)
- [Query Builder](#query-builder)
  - [Where Clauses](#where-clauses)
  - [WHERE EXISTS / NOT EXISTS](#where-exists--not-exists)
  - [Conditional Clauses](#conditional-clauses)
  - [Ordering, Grouping, Limit](#ordering-grouping-limit)
  - [Aggregates](#aggregates)
  - [Joins](#joins)
  - [Row Locking](#row-locking)
  - [Debugging Queries](#debugging-queries)
- [Relationships](#relationships)
  - [One to One](#one-to-one)
  - [One to Many](#one-to-many)
  - [Belongs To](#belongs-to)
  - [Many to Many](#many-to-many)
  - [Has One Through](#has-one-through)
  - [Has Many Through](#has-many-through)
  - [Polymorphic Relationships](#polymorphic-relationships)
  - [Polymorphic Many-to-Many](#polymorphic-many-to-many)
  - [Querying Relations](#querying-relations)
- [Collections](#collections)
- [Mutators & Casting](#mutators--casting)
- [Query Scopes](#query-scopes)
- [Events & Observers](#events--observers)
- [Query Caching](#query-caching)
- [Database Migrations](#database-migrations)
- [Testing with Factories](#testing-with-factories)
- [Cloudflare D1](#cloudflare-d1)
- [FastAPI Integration](#fastapi-integration)

---

## Installation

```bash
pip install pyloquent
```

### Optional Dependencies

```bash
pip install pyloquent[postgres]   # PostgreSQL via asyncpg
pip install pyloquent[mysql]      # MySQL via aiomysql
pip install pyloquent[redis]      # Redis caching
pip install pyloquent[factory]    # Model factories (faker)
pip install pyloquent[d1]         # Cloudflare D1 HTTP API
pip install pyloquent[all]        # Everything
```

---

## Getting Started

### Configuration

```python
from pyloquent import ConnectionManager
from pyloquent.database.manager import set_manager

manager = ConnectionManager()

# SQLite (great for development/testing)
manager.add_connection('default', {
    'driver': 'sqlite',
    'database': 'database.db',   # or ':memory:' for tests
}, default=True)

# PostgreSQL
manager.add_connection('postgres', {
    'driver': 'postgres',
    'host': 'localhost',
    'port': 5432,
    'database': 'myapp',
    'user': 'postgres',
    'password': 'secret',
})

# MySQL
manager.add_connection('mysql', {
    'driver': 'mysql',
    'host': 'localhost',
    'port': 3306,
    'database': 'myapp',
    'user': 'root',
    'password': 'secret',
})

set_manager(manager)   # make globally available to all models
await manager.connect()
```

### Your First Model

```python
from typing import Optional
from pyloquent import Model

class User(Model):
    __table__ = 'users'
    __fillable__ = ['name', 'email', 'age']

    id: Optional[int] = None
    name: str
    email: str
    age: Optional[int] = None
```

---

## Models

### Model Conventions

| Feature | Convention | Override |
|---------|-----------|----------|
| Table name | Pluralised snake_case | `__table__ = 'custom'` |
| Primary key | `id` | `__primary_key__ = 'uuid'` |
| Timestamps | `created_at`, `updated_at` | `__timestamps__ = False` |
| Per-page (pagination) | 15 | `__per_page__ = 25` |
| Foreign key | ModelName + `_id` | Specify in relation |
| Connection | `'default'` | `__connection__ = 'postgres'` |

```python
class Flight(Model):
    __table__       = 'my_flights'
    __primary_key__ = 'flight_id'
    __timestamps__  = False
    __per_page__    = 25
    __connection__  = 'postgres'   # named connection

    flight_id: Optional[int] = None
    flight_number: str
    origin: str
    destination: str
```

### Default Attribute Values

```python
class Post(Model):
    __table__    = 'posts'
    __fillable__ = ['title', 'status', 'published_at']

    id: Optional[int] = None
    title: str
    status: str = 'draft'          # default value
    published_at: Optional[datetime] = None
```

### Hidden & Visible Fields

```python
class User(Model):
    __hidden__  = ['password', 'remember_token']  # excluded from to_dict() / json()
    __visible__ = []                               # if set, ONLY these are included
    __appends__ = ['full_name']                    # computed properties added to output

    password: str
    remember_token: Optional[str] = None

    def get_full_name_attribute(self):
        return f'{self.first_name} {self.last_name}'
```

Per-instance overrides:

```python
user = await User.find(1)

user.make_visible('password')         # show normally-hidden fields
user.make_hidden('email')             # hide normally-visible fields
user.append('full_name')              # add computed attribute
d = user.to_dict()                    # respects all overrides
j = user.json()                       # JSON string
```

### Instance Methods

```python
user = await User.find(1)

# Fill and save
await user.update({'name': 'New Name', 'age': 31})

# Atomic column changes
await user.increment('login_count')          # +1
await user.increment('score', 10)            # +10
await user.decrement('credits', 5)           # -5

# Update timestamp only
await user.touch()

# Duplicate the record
replica = await user.replicate({'email': 'copy@example.com'})

# Change tracking
user.name = 'Changed'
await user.save()
print(user.was_changed('name'))   # True
print(user.get_changes())         # {'name': 'Changed'}

# Key helpers
print(user.get_key())       # value of primary key
print(user.get_key_name())  # 'id'

# Serialisation
user.to_dict()    # dict respecting __hidden__ / make_visible / make_hidden
user.to_array()   # alias for to_dict()
user.json()       # JSON string
```

---

## Retrieving Models

```python
# All records → Collection
users = await User.all()

# Find by primary key (None if missing)
user = await User.find(1)

# Find or raise ModelNotFoundException
user = await User.find_or_fail(1)

# Find many by primary keys → Collection
users = await User.find_many([1, 2, 3])

# First matching record
user = await User.where('email', 'alice@example.com').first()

# First or return new unsaved instance
user = await User.first_or_new({'email': 'new@example.com'}, {'name': 'New'})

# First or raise ModelNotFoundException
user = await User.first_or_fail({'active': True})

# First or create (saves the record)
user = await User.first_or_create(
    {'email': 'alice@example.com'},
    {'name': 'Alice', 'age': 30}
)

# Update or create
user = await User.update_or_create(
    {'email': 'alice@example.com'},
    {'name': 'Alice Updated'}
)

# Check existence
exists = await User.where('email', 'alice@example.com').exists()
missing = await User.where('email', 'ghost@example.com').doesnt_exist()

# Scalar value
name = await User.where('id', 1).scalar('name')

# Destroy by primary keys (returns count)
await User.destroy(1, 2, 3)
```

### Chunking Results

```python
# Process 100 records at a time
async for chunk in User.chunk(100):
    for user in chunk:
        await process(user)
```

### Pagination

```python
# Full pagination (executes COUNT + SELECT)
page = await User.paginate(per_page=15, page=2)
# Returns:
# {
#   'data': [<User>, ...],
#   'total': 120,
#   'per_page': 15,
#   'current_page': 2,
#   'last_page': 8,
#   'from': 16,
#   'to': 30,
# }

# Simple pagination (no COUNT, cheaper)
page = await User.simple_paginate(per_page=15, page=2)
# {'data': [...], 'per_page': 15, 'current_page': 2, 'has_more': True}
```

### Cursor Streaming

Memory-efficient iteration without loading all records:

```python
async for user in User.query.cursor():
    await process(user)

# Or collect lazily
async for user in User.query.lazy(100):   # buffered in chunks of 100
    await process(user)
```

---

## Inserting & Updating Models

### Inserts

```python
# Instantiate and save
user = User(name='John', email='john@example.com')
await user.save()

# Create in one call
user = await User.create({'name': 'John', 'email': 'john@example.com'})

# Batch insert (raw, no model events)
await User.query.insert([
    {'name': 'Alice', 'email': 'alice@example.com'},
    {'name': 'Bob',   'email': 'bob@example.com'},
])
```

### Updates

```python
# Save dirty attributes
user = await User.find(1)
user.name = 'Jane'
await user.save()

# Fluent update
await user.update({'name': 'Jane', 'age': 31})

# Mass update via query
await User.where('active', False).update({'status': 'inactive'})
```

### Upsert & Bulk Operations

```python
# Insert rows; skip (silently) on unique constraint violation
await User.query.insert_or_ignore([
    {'email': 'alice@example.com', 'name': 'Alice'},
    {'email': 'new@example.com',   'name': 'New'},
])

# Insert rows or update specific columns on conflict
await User.query.upsert(
    values=[
        {'email': 'alice@example.com', 'name': 'Alice', 'score': 100},
        {'email': 'bob@example.com',   'name': 'Bob',   'score': 80},
    ],
    unique_by=['email'],
    update_columns=['name', 'score'],
)

# Find or insert; update if found
await User.query.update_or_insert(
    {'email': 'alice@example.com'},   # search criteria
    {'name': 'Alice', 'score': 50},   # values to set
)
```

### Increment & Decrement

```python
# Query-level (bulk)
await User.where('active', True).increment('score', 1)
await User.where('level', 1).decrement('health', 10)

# Instance-level (also updates the in-memory attribute)
await user.increment('login_count')
await user.decrement('credits', 5, extra={'last_action': 'purchase'})
```

### Mass Assignment

```python
class User(Model):
    __fillable__ = ['name', 'email', 'age']   # allowed
    __guarded__  = ['id', 'is_admin']         # blocked
```

---

## Deleting Models

```python
user = await User.find(1)
await user.delete()

# Bulk delete
await User.where('active', False).delete()

# Truncate
await User.query.truncate()
```

### Soft Deletes

```python
from datetime import datetime
from typing import Optional
from pyloquent import Model, SoftDeletes

class Post(Model, SoftDeletes):
    __table__    = 'posts'
    __fillable__ = ['title', 'content']

    id: Optional[int] = None
    title: str
    content: str
    deleted_at: Optional[datetime] = None   # required field

# Soft delete — sets deleted_at
await post.delete()

# Restore
await post.restore()

# Permanent delete (bypasses soft delete)
await post.force_delete()

# Check status
post.trashed()   # True / False

# Query variants
posts   = await Post.with_trashed().get()    # include soft-deleted
trashed = await Post.only_trashed().get()    # only soft-deleted
active  = await Post.without_trashed().get() # exclude soft-deleted (default)
```

**Soft delete events** — `deleting`, `deleted`, `restoring`, `restored` are all fired:

```python
Post.on('deleting',  lambda p: log(f'soft-deleting {p.id}'))
Post.on('restoring', lambda p: False if p.is_protected else None)  # abort
```

---

## Query Builder

### Where Clauses

```python
# Equality (shorthand)
User.where('age', 18)

# Operator
User.where('age', '>=', 18)
User.where('name', 'like', 'Ali%')

# Multiple ANDs
User.where('age', '>=', 18).where('active', True)

# OR
User.where('age', '>=', 18).or_where('vip', True)

# IN / NOT IN
User.where_in('id', [1, 2, 3])
User.where_not_in('status', ['banned', 'pending'])

# BETWEEN
User.where_between('age', [18, 65])
User.where_not_between('score', [0, 10])

# NULL
User.where_null('deleted_at')
User.where_not_null('email_verified_at')

# Column comparison
User.where_column('updated_at', '>', 'created_at')

# Raw
User.where_raw('LOWER(email) = ?', ['alice@example.com'])

# Nested closure
User.where(lambda q: q.where('age', '<', 18).or_where('age', '>', 65))
```

### WHERE EXISTS / NOT EXISTS

```python
# Users who have at least one published post
users = await User.where_exists(
    lambda q: q.from_('posts')
               .where_raw('"posts"."user_id" = "users"."id"')
               .where('posts.published', True)
).get()

# Users with no orders
users = await User.where_not_exists(
    lambda q: q.from_('orders').where_raw('"orders"."user_id" = "users"."id"')
).get()
```

### Conditional Clauses

```python
search = request.get('name')
active_only = True

results = await (
    User.query
    .when(search,      lambda q: q.where('name', 'like', f'%{search}%'))
    .unless(not active_only, lambda q: q.where('active', True))
    .tap(lambda q: logger.debug(q.to_raw_sql()))
    .get()
)
```

- **`when(condition, callback)`** — applies `callback` only when `condition` is truthy
- **`unless(condition, callback)`** — applies `callback` only when `condition` is falsy
- **`tap(callback)`** — side-effect (logging, debugging) without modifying the query

### Ordering, Grouping, Limit

```python
User.order_by('name')
User.order_by('created_at', 'desc')
User.latest()            # ORDER BY created_at DESC
User.latest('updated_at')
User.oldest()            # ORDER BY created_at ASC

User.group_by('status')
User.group_by('status').having('count', '>', 5)

User.limit(10)
User.offset(20).limit(10)
User.for_page(page=3, per_page=15)
```

### Aggregates

```python
await User.count()
await User.where('active', True).count()
await User.max('age')
await User.min('age')
await User.sum('points')
await User.avg('age')
await User.scalar('name')  # scalar value of first row's column
```

### Selects

```python
User.select('name', 'email')
User.select_raw('COUNT(*) as total, status')
User.distinct().select('country')
User.add_select('created_at')
```

### Joins

```python
User.join('posts', 'users.id', '=', 'posts.user_id')
User.left_join('posts', 'users.id', '=', 'posts.user_id')
User.right_join('posts', 'users.id', '=', 'posts.user_id')
User.cross_join('categories')

# Advanced join with closure
User.join('posts', lambda j: (
    j.on('users.id', '=', 'posts.user_id')
     .where('posts.published', True)
))
```

### Row Locking

```python
# Lock for update — prevents other transactions reading until commit
user = await User.where('id', 1).lock_for_update().first()

# Shared lock — others can read but not write
user = await User.where('id', 1).for_share().first()
```

> **Note:** Row locking is a no-op on SQLite. It is fully honoured on PostgreSQL and MySQL.

### Debugging Queries

```python
# Get parameterised SQL and bindings
sql, bindings = User.where('active', True).to_sql()
print(sql)       # SELECT * FROM "users" WHERE "active" = ?
print(bindings)  # [True]

# Get final SQL with values interpolated (for logging/debugging only)
raw = User.where('active', True).where('score', '>', 50).to_raw_sql()
print(raw)
# SELECT * FROM "users" WHERE "active" = 1 AND "score" > 50
```

---

## Relationships

### One to One

```python
class User(Model):
    def phone(self):
        return self.has_one(Phone)

class Phone(Model):
    def user(self):
        return self.belongs_to(User)

# Usage
phone = await user.phone().get_results()
owner = await phone.user().get_results()
```

### One to Many

```python
class User(Model):
    def posts(self):
        return self.has_many(Post)

class Post(Model):
    def author(self):
        return self.belongs_to(User)

posts  = await user.posts().get()
author = await post.author().get_results()

# Create through relation
post = await user.posts().create({'title': 'Hello World', 'content': '...'})
```

### Belongs To

```python
class Post(Model):
    def user(self):
        return self.belongs_to(User, foreign_key='author_id')
```

### Many to Many

```python
class User(Model):
    def roles(self):
        return self.belongs_to_many(Role)   # pivot table: role_user

class Role(Model):
    def users(self):
        return self.belongs_to_many(User)

# Attach / detach
await user.roles().attach(role_id)
await user.roles().attach(role_id, {'expires_at': some_date})
await user.roles().detach(role_id)
await user.roles().sync([1, 2, 3])   # replace all

# Toggle
await user.roles().toggle([1, 2])

# With pivot columns
roles = await user.roles().with_pivot('expires_at').get()
for role in roles:
    print(role.pivot.expires_at)
```

### Has One Through

A one-to-one relation through an intermediate model.

```python
# Country → User → Profile  (country has one profile through user)
class Country(Model):
    def latest_profile(self):
        return self.has_one_through(Profile, User)
        # has_one_through(related, through, first_key=None, second_key=None,
        #                 local_key=None, second_local_key=None)

profile = await country.latest_profile().get_results()
```

### Has Many Through

A one-to-many relation through an intermediate model.

```python
# Country → User → Post  (country has many posts through users)
class Country(Model):
    def posts(self):
        return self.has_many_through(Post, User)

posts = await country.posts().get()
```

### Polymorphic Relationships

```python
class Comment(Model):
    def commentable(self):
        return self.morph_to('commentable')   # morph_to(name)

class Post(Model):
    def comments(self):
        return self.morph_many(Comment, 'commentable')

class Video(Model):
    def comments(self):
        return self.morph_many(Comment, 'commentable')

# Usage — comments table needs: id, body, commentable_type, commentable_id
comments = await post.comments().get()
parent   = await comment.commentable().get_results()   # Post or Video instance
```

### Polymorphic Many-to-Many

Tags shared across multiple model types.

```python
# taggables pivot table: tag_id, taggable_id, taggable_type

class Post(Model):
    def tags(self):
        return self.morph_to_many(Tag, 'taggable')

class Video(Model):
    def tags(self):
        return self.morph_to_many(Tag, 'taggable')

class Tag(Model):
    def posts(self):
        return self.morphed_by_many(Post, 'taggable')

    def videos(self):
        return self.morphed_by_many(Video, 'taggable')

# Attach tags to a post
await post.tags().attach([tag1.id, tag2.id])

# Sync (replaces existing)
await post.tags().sync([tag2.id, tag3.id])

# Detach
await post.tags().detach([tag1.id])

# Query
tags   = await post.tags().get()
posts  = await tag.posts().get()
videos = await tag.videos().get()
```

### Querying Relations

```python
# Has (existence check)
users = await User.has('posts').get()
users = await User.has('posts', '>=', 3).get()

# Doesnt have
users = await User.doesnt_have('posts').get()

# Where has (with constraints)
users = await User.where_has('posts', lambda q: q.where('published', True)).get()

# With count
users = await User.with_count('posts').get()
for u in users:
    print(u.posts_count)

# Eager loading
users = await User.with_('posts', 'profile').get()
users = await User.with_({'posts': lambda q: q.where('published', True)}).get()

# Lazy load on an already-retrieved model
await user.load('posts', 'comments')
await user.load_missing('profile')   # only if not already loaded
```

---

## Collections

All query results are returned as `Collection` instances, which wrap a list with 60+ methods.

### Presence

```python
col.is_empty()
col.is_not_empty()
col.contains('name', 'Alice')          # attribute match
col.contains(lambda u: u.age > 18)    # predicate
col.doesnt_contain('status', 'banned')
col.first_where('age', '>=', 18)
col.sole()                             # raises if count != 1
```

### Filtering & Slicing

```python
col.filter(lambda u: u.active)
col.where('active', True)
col.where_not_in('status', ['banned'])
col.take(10)
col.skip(20)
col.take_while(lambda u: u.score > 0)
col.skip_while(lambda u: u.score > 100)
col.only('id', 'name', 'email')        # keep only these keys in each item dict
col.except_('password')
```

### Sorting

```python
col.sort_by('name')
col.sort_by_desc('created_at')
col.sort_by(lambda u: (u.last_name, u.first_name))
```

### Set Operations

```python
col.diff(other)         # items in col not in other
col.intersect(other)    # items in both
col.unique('email')     # deduplicate by attribute
col.duplicates('email') # items with duplicate attribute values
```

### Merging & Combining

```python
col.merge(other)        # concatenate two collections
col.concat(other)       # alias
col.zip(other)          # pair items: [(a1,b1), (a2,b2), ...]
col.collapse()          # flatten one level (collection of collections)
col.flatten()           # fully flatten nested structure
```

### Grouping & Splitting

```python
groups = col.group_by('country')       # dict[key, Collection]
active, inactive = col.partition(lambda u: u.active)
chunks = col.split(3)                  # list of 3 equal-ish Collections
removed = col.splice(start, delete_count, replacements)
```

### Transformations

```python
col.map(lambda u: u.name.upper())
col.flat_map(lambda u: u.roles)
col.map_with_keys(lambda u: (u.id, u.name))   # → dict
col.map_into(UserDTO)                         # instantiate another class
col.key_by('id')                              # → dict keyed by attribute
col.pluck('name')
col.pluck('name', 'id')                       # → dict id→name
```

### Statistics & Reduction

```python
col.count()
col.sum('score')
col.avg('age')
col.min('age')
col.max('age')
col.median()          # or col.median('age')
col.mode()            # or col.mode('status')
col.count_by(lambda u: u.country)   # frequency dict
col.reduce(lambda carry, u: carry + u.score, 0)
```

### Pipelines

```python
result  = col.pipe(lambda c: c.filter(...).sort_by('name'))
col.tap(lambda c: logger.debug(f'{c.count()} items'))
filtered = col.when(flag, lambda c: c.filter(pred))
filtered = col.unless(flag, lambda c: c.filter(pred))
```

### Mutation

```python
col.push(item)
col.prepend(item)
col.pop()            # remove and return last
col.shift()          # remove and return first
col.forget(2)        # remove index
col.shuffle()        # in-place random shuffle, returns self
col.random()         # single random item
col.random(3)        # Collection of 3 random items
col.pad(10, default) # pad to minimum length
```

### Serialisation

```python
col.to_array()   # list of dicts
col.to_json()    # JSON string
col.all()        # raw list
```

---

## Mutators & Casting

```python
from decimal import Decimal
from pyloquent import Model

class User(Model):
    __casts__ = {
        'age':        'int',
        'balance':    'decimal:2',
        'is_active':  'bool',
        'metadata':   'json',
        'birth_date': 'date',
        'last_login': 'datetime',
    }
```

Available cast types: `int`, `float`, `bool`, `string`, `json`, `date`, `datetime`, `decimal:N`

---

## Query Scopes

### Local Scopes

```python
class Post(Model):
    def scope_published(self, query):
        return query.where('status', 'published')

    def scope_recent(self, query):
        return query.order_by('created_at', 'desc')

# Chainable
posts = await Post.published().recent().get()
```

### Global Scopes

```python
class Post(Model):
    @classmethod
    def boot(cls):
        super().boot()
        cls.add_global_scope('active', lambda q: q.where('active', True))

# All queries automatically include WHERE active = 1
posts = await Post.all()

# Remove for a single query
posts = await Post.without_global_scope('active').get()
```

---

## Events & Observers

### Available Events

| Event | Fired when |
|-------|-----------|
| `retrieved` | Model is loaded from the database |
| `creating` | Before inserting a new record |
| `created` | After inserting a new record |
| `updating` | Before updating an existing record |
| `updated` | After updating an existing record |
| `saving` | Before creating or updating |
| `saved` | After creating or updating |
| `deleting` | Before deleting (soft or hard) |
| `deleted` | After deleting |
| `restoring` | Before restoring a soft-deleted record |
| `restored` | After restoring a soft-deleted record |

**Returning `False` from `creating`, `updating`, `saving`, `deleting`, or `restoring` aborts the operation.**

```python
class User(Model):
    @classmethod
    def boot(cls):
        super().boot()

        cls.on('retrieved', lambda u: audit_log('read', u.id))
        cls.on('creating',  lambda u: setattr(u, 'slug', slugify(u.name)))
        cls.on('created',   lambda u: send_welcome_email(u))
        cls.on('updating',  lambda u: False if u.is_locked else None)
        cls.on('deleting',  lambda u: False if u.is_admin else None)
        cls.on('restoring', lambda u: log(f'restoring {u.id}'))
```

Register a listener anywhere:

```python
User.on('created', lambda user: print(f"New user: {user.name}"))
```

### Observers

```python
from pyloquent import ModelObserver

class UserObserver(ModelObserver):
    async def creating(self, user):
        user.slug = slugify(user.name)

    async def created(self, user):
        await send_welcome_email(user)

    async def updating(self, user):
        if user.is_dirty('email'):
            user.email_verified_at = None

    async def deleted(self, user):
        await cleanup_user_data(user)

User.observe(UserObserver())
```

---

## Query Caching

```python
from pyloquent import CacheManager, MemoryStore, FileStore, RedisStore

# Choose a store
CacheManager.store(MemoryStore())
CacheManager.store(FileStore('/var/cache/app'))
CacheManager.store(RedisStore(host='localhost', port=6379, db=0))

# Cache a query for N seconds
users = await User.cache(3600).get()

# Cache forever
users = await User.cache_forever().get()

# Custom key
users = await User.cache(3600, 'active_users').where('active', True).get()

# Cache with tags (Redis / tagged stores only)
users = await User.cache(3600).cache_tags('users', 'active').get()
```

---

## Database Migrations

### Creating Migrations

```bash
pyloquent make:migration create_users_table
pyloquent make:migration create_posts_table --table=posts --create
```

### Migration Structure

```python
from pyloquent.migrations import Migration
from pyloquent.schema import SchemaBuilder

class CreateUsersTable(Migration):
    async def up(self, schema: SchemaBuilder) -> None:
        await schema.create('users', lambda table: (
            table.id(),
            table.string('name'),
            table.string('email').unique(),
            table.string('password'),
            table.timestamp('email_verified_at').nullable(),
            table.timestamps(),
        ))

    async def down(self, schema: SchemaBuilder) -> None:
        await schema.drop('users')
```

### Column Types

```python
# IDs
table.id()               # SERIAL / INTEGER AUTO_INCREMENT PRIMARY KEY
table.uuid('id')

# Strings
table.string('name', 255)
table.text('bio')
table.char('code', 2)

# Numbers
table.integer('age')
table.big_integer('views')
table.float('rating', 8, 2)
table.decimal('price', 10, 2)

# Boolean
table.boolean('is_active')

# Dates / Times
table.date('birth_date')
table.datetime('last_login')
table.timestamp('created_at')
table.timestamps()          # created_at + updated_at

# JSON
table.json('metadata')

# Enums
table.enum('status', ['pending', 'active', 'inactive'])

# Modifiers
table.string('email').unique()
table.integer('user_id').index()
table.string('bio').nullable()
table.string('avatar').default('default.png')
table.integer('views').unsigned()

# Foreign keys
table.foreign('user_id').references('id').on('users').on_delete('cascade')
```

### Running Migrations

```bash
pyloquent migrate                   # run all pending
pyloquent migrate:rollback          # rollback last batch
pyloquent migrate:rollback --steps=3
pyloquent migrate:reset             # rollback everything
pyloquent migrate:fresh             # drop all + re-run
pyloquent migrate:status            # show status table
```

---

## Testing with Factories

### Defining Factories

```python
from pyloquent import Factory
import random

class UserFactory(Factory[User]):
    model = User

    def definition(self):
        return {
            'name':      self.faker.name(),
            'email':     self.faker.unique.email(),
            'age':       random.randint(18, 65),
            'is_active': True,
        }

class PostFactory(Factory[Post]):
    model = Post

    def definition(self):
        return {
            'title':   self.faker.sentence(),
            'content': self.faker.paragraph(),
            'status':  'published',
        }

    def draft(self):
        return self.state({'status': 'draft'})

    def featured(self):
        return self.state({'is_featured': True})
```

### Using Factories

```python
user  = await UserFactory.create()
user  = await UserFactory.create({'name': 'Alice'})
users = await UserFactory.create_many(10)

# States
post     = await PostFactory.draft().create()
featured = await PostFactory.featured().create_many(5)

# Make (don't save)
user = UserFactory.make()
```

---

## Cloudflare D1

```python
# HTTP API
manager.add_connection('d1', {
    'driver':      'd1',
    'api_token':   'your-cloudflare-api-token',
    'account_id':  'your-account-id',
    'database_id': 'your-database-id',
}, default=True)

# Worker binding (edge runtime)
manager.add_connection('d1', {
    'driver':  'd1',
    'binding': env.DB,   # D1 binding from Worker environment
})

await manager.connect()
users = await User.all()   # works identically to any other driver
```

---

## FastAPI Integration

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pyloquent import ConnectionManager, Model
from pyloquent.database.manager import set_manager
from pyloquent.exceptions import ModelNotFoundException

manager = ConnectionManager()
manager.add_connection('default', {
    'driver':   'sqlite',
    'database': 'app.db',
}, default=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    set_manager(manager)
    await manager.connect()
    yield
    await manager.disconnect()

app = FastAPI(lifespan=lifespan)

@app.get('/users')
async def list_users(page: int = 1, per_page: int = 20):
    return await User.paginate(per_page=per_page, page=page)

@app.get('/users/{id}')
async def get_user(id: int):
    try:
        return await User.find_or_fail(id)
    except ModelNotFoundException:
        raise HTTPException(status_code=404, detail='User not found')

@app.post('/users')
async def create_user(data: dict):
    return await User.create(data)

@app.put('/users/{id}')
async def update_user(id: int, data: dict):
    user = await User.find_or_fail(id)
    return await user.update(data)

@app.delete('/users/{id}')
async def delete_user(id: int):
    user = await User.find_or_fail(id)
    await user.delete()
    return {'message': 'Deleted'}
```

---

## Advanced Usage

### Raw Queries

```python
results = await User.query.select_raw('COUNT(*) as count, status').group_by('status').get()
users   = await User.where_raw('age > ? AND status = ?', [18, 'active']).get()
users   = await User.order_by_raw('RANDOM()').limit(5).get()
```

### Database Transactions

```python
# Context manager (recommended)
async with manager.transaction():
    user = await User.create({'name': 'John'})
    await Post.create({'user_id': user.id, 'title': 'Hello'})

# Manual control
conn = manager.connection()
await conn.begin_transaction()
try:
    await User.create({'name': 'John'})
    await conn.commit()
except Exception:
    await conn.rollback()
    raise
```

---

## 0.3.0 — New Features

### CTEs (Common Table Expressions)

Use `with_cte()` or `with_recursive_cte()` to attach a `WITH` or `WITH RECURSIVE`
clause to any query.  Both methods accept either a builder instance or a callback
that receives a fresh builder.

```python
# Named CTE via callback
results = await (
    Order.query
    .with_cte('recent', lambda q: q.from_('orders').where('status', 'open'))
    .from_('recent')
    .order_by('created_at', 'desc')
    .get()
)

# Recursive CTE — hierarchical category tree
from pyloquent import QueryBuilder

tree = await (
    QueryBuilder(grammar, conn)
    .with_recursive_cte(
        'tree',
        lambda q: q.from_('categories').where('parent_id', None),          # anchor
        lambda q: q.from_('categories')
                   .join('tree', 'tree.id', '=', 'categories.parent_id'),  # recursive
    )
    .from_('tree')
    .select('id', 'name', 'parent_id')
    .get()
)
```

### Window Functions

`select_window()` adds a window function column to the `SELECT` list.

```python
from pyloquent import WindowFrame

# ROW_NUMBER partitioned by region
results = await (
    Sale.query
    .select('region', 'rep', 'amount')
    .select_window('RANK', partition_by=['region'], order_by=['amount DESC'], alias='rank')
    .get()
)

# Running total with explicit ROWS frame
frame = WindowFrame(mode='ROWS', start='UNBOUNDED PRECEDING', end='CURRENT ROW')
results = await (
    Order.query
    .select('created_at', 'total')
    .select_window('SUM', 'total', order_by=['created_at'], frame=frame, alias='running_total')
    .get()
)
```

Supported aggregates: any function name is accepted — `ROW_NUMBER`, `RANK`, `DENSE_RANK`,
`NTILE`, `LAG`, `LEAD`, `FIRST_VALUE`, `LAST_VALUE`, `SUM`, `AVG`, `COUNT`, `MIN`, `MAX`.

### Advanced Joins

```python
# Raw JOIN fragment (custom ON clause, extra bindings)
User.query.join_raw('LEFT JOIN audit_log al ON al.user_id = users.id AND al.active = ?', [1])

# Subquery join — builder or callback
User.query.join_sub(
    lambda q: q.from_('orders').select('user_id').where('status', 'paid'),
    alias='paid',
    first='users.id', operator='=', second='paid.user_id',
)

# Left subquery join
User.query.left_join_sub(
    lambda q: q.from_('orders').select('user_id'),
    alias='o', first='users.id', operator='=', second='o.user_id',
)

# Callback ON clause — multi-condition joins
User.query.join_on(
    'orders',
    lambda j: j.on('orders.user_id', '=', 'users.id')
               .or_on('orders.alt_id', '=', 'users.id'),
)

# Full outer join
QueryBuilder(grammar, conn).from_('a').full_join('b', 'a.id', '=', 'b.a_id').get()
```

### Single Table Inheritance (STI)

Map multiple Python classes to a single database table using a discriminator column.

```python
class Animal(Model):
    __table__ = 'animals'
    __fillable__ = ['name', 'type']

    id: Optional[int] = None
    name: str
    type: str = 'animal'

class Dog(Animal):
    __discriminator__ = 'type'          # column that holds the type value
    __discriminator_value__ = 'dog'     # value for this subclass

class Cat(Animal):
    __discriminator__ = 'type'
    __discriminator_value__ = 'cat'

# Queries are automatically scoped — no manual WHERE needed
dogs = await Dog.query.get()     # SELECT … WHERE type = 'dog'
cats = await Cat.query.get()     # SELECT … WHERE type = 'cat'
all_ = await Animal.query.get()  # no scope applied
```

`ModelMeta` registers a global scope for the discriminator value at class creation time.

### Composite Primary Keys

Set `__primary_key__` to a list of column names.

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

# _get_key() returns a dict for composite keys
key = item._get_key()  # {'order_id': 1, 'product_id': 42}

await item.delete()    # DELETE WHERE order_id = 1 AND product_id = 42
```

### Hybrid Properties

`@hybrid_property` works like a regular `@property` on model instances but can expose
a SQL expression at the class level for use in raw WHERE / SELECT fragments.

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

# Instance access
user = User(first_name='Jane', last_name='Doe')
print(user.full_name)   # 'Jane Doe'

# Class-level expression (for use in select_raw / where_raw)
expr = User.full_name   # RawExpression("first_name || ' ' || last_name")
```

### TypeDecorator — Custom Column Types

Register custom serialisation / deserialisation logic for any column.

```python
from pyloquent import TypeDecorator, register_type, JSONType, CommaSeparatedType

# Built-in types — registered as 'json' and 'comma_separated'
class Product(Model):
    __casts__ = {
        'metadata': 'json',           # dict ↔ JSON text
        'tags':     'comma_separated', # list ↔ 'a,b,c' text
    }
    metadata: Optional[dict] = None
    tags: Optional[list] = None

# Custom type
class UpperCaseType(TypeDecorator):
    impl = 'TEXT'

    def process_bind_param(self, value, dialect=None):
        return value.upper() if value else value

    def process_result_value(self, value, dialect=None):
        return value.lower() if value else value

register_type('upper', UpperCaseType())

class Tag(Model):
    __casts__ = {'slug': 'upper'}
    slug: Optional[str] = None

# TypeDecorator instances and subclasses are also accepted directly:
class Log(Model):
    __casts__ = {'payload': JSONType()}  # instance
```

### Identity Map

`IdentityMap` ensures the same database row always produces the same Python object
within a scope, preventing duplicate hydration.

```python
from pyloquent import IdentityMap

# Manual usage
imap = IdentityMap()
u1 = await User.query.with_identity_map(imap).find(1)
u2 = await User.query.with_identity_map(imap).find(1)
assert u1 is u2   # True — cached after first query

# Scoped session (recommended) — map is cleared on exit
async with IdentityMap.session() as imap:
    u1 = await User.query.with_identity_map(imap).find(1)
    u2 = await User.query.with_identity_map(imap).find(1)
    assert u1 is u2

# Works with composite primary keys too
imap.register(OrderItem, {'order_id': 1, 'product_id': 42}, item)
cached = imap.get(OrderItem, {'order_id': 1, 'product_id': 42})
assert cached is item
```

### Batch Insert

Pass a list of dicts to `QueryBuilder.insert()` and Pyloquent automatically uses
the driver's native `executemany` for bulk performance.

```python
# One executemany call instead of N separate execute() calls
await Product.query.insert([
    {'name': 'Widget A', 'price': 9.99},
    {'name': 'Widget B', 'price': 19.99},
    {'name': 'Widget C', 'price': 29.99},
])

# Single-dict insert continues to use the standard path
await Product.query.insert({'name': 'Solo', 'price': 4.99})
```

### Sync Support

For scripts, notebooks, CLI tools, or any context that cannot use `async/await`.

```python
from pyloquent.sync import run_sync, sync, SyncConnectionManager

# Execute any coroutine synchronously
user = run_sync(User.find(1))
users = run_sync(User.where('active', True).order_by('name').get())

# Decorator — wraps an async function into a sync one
@sync
async def get_users():
    return await User.all()

users = get_users()   # no await needed

# Synchronous context manager
with SyncConnectionManager({
    'default': {'driver': 'sqlite', 'database': 'app.db'}
}) as mgr:
    users = mgr.table('users').where('active', True).get()
    count = mgr.table('users').count()
```

### SQLite WAL Mode & Foreign Keys

```python
manager.add_connection('default', {
    'driver': 'sqlite',
    'database': 'app.db',
    'journal_mode': 'wal',     # enable WAL for concurrent reads
    'foreign_keys': True,      # default True; set False to disable FK enforcement
}, default=True)
```

### Schema Reflection

All grammars expose `compile_*` methods for introspecting the live database schema.
Use them directly or via `D1BindingConnection`'s helper methods.

```python
grammar = SQLiteGrammar()

sql = grammar.compile_get_tables()
sql, b = grammar.compile_table_exists('users')
sql, b = grammar.compile_column_exists('users', 'email')
sql, b = grammar.compile_get_columns('orders')
sql, b = grammar.compile_get_indexes('users')
sql, b = grammar.compile_get_foreign_keys('orders')
```

---

## Cloudflare D1 — Native Worker Binding

Pyloquent supports two modes for Cloudflare D1:

| Mode | Class | When to use |
|------|-------|-------------|
| HTTP API | `D1Connection` | External Python apps, scripts, CI pipelines |
| Worker binding | `D1BindingConnection` | Python Workers on Cloudflare's runtime |

### HTTP API (external apps)

```python
from pyloquent import ConnectionManager

manager = ConnectionManager()
manager.add_connection('default', {
    'driver': 'd1',
    'api_token':    'your-cloudflare-api-token',
    'account_id':  'your-account-id',
    'database_id': 'your-d1-database-id',
}, default=True)
await manager.connect()
```

### Native Worker Binding

When running Python inside a Cloudflare Worker, the D1 binding (`self.env.DB`)
is a JavaScript proxy object available through the Worker environment.  Python
Workers require `compatibility_flags = ["python_workers"]` in `wrangler.jsonc`.

#### `wrangler.jsonc`

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

#### `src/entry.py`

Python Workers use `WorkerEntrypoint` from the `workers` module (provided by
the Cloudflare runtime).  The D1 binding is accessed via `self.env.DB` where
`DB` matches the `binding` name in `wrangler.jsonc`.

```python
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
        # self.env.DB is the D1 binding — no HTTP credentials needed
        manager = ConnectionManager.from_binding(self.env.DB)
        set_manager(manager)

        users = await User.where('active', True).order_by('name').get()
        return Response.json(users.to_dict_list())
```

> **Note** — The official Python Workers D1 API uses `await stmt.run()` for
> both SELECT and write queries.  Pyloquent’s `D1BindingConnection.fetch_all()`
> calls `stmt.run()` as the primary path, exactly as shown in the
> [Cloudflare docs](https://developers.cloudflare.com/d1/examples/query-d1-from-python-workers/).

#### Manual construction

```python
from pyloquent.d1.binding import D1BindingConnection

conn = D1BindingConnection(self.env.DB)
await conn.connect()

# QueryBuilder shortcut
rows = await conn.table('users').where('active', True).get()
```

#### Batch writes (atomic)

D1 Worker bindings do not support `BEGIN`/`COMMIT`.  Pyloquent implements
transactions by accumulating statements and flushing them via `db.batch()`.

```python
async with manager.transaction():
    await User.create({'name': 'Alice', 'email': 'alice@example.com'})
    await Post.create({'user_id': 1, 'title': 'Hello'})
# Both inserts sent in a single db.batch() call
```

Or use `conn.batch()` directly:

```python
results = await conn.batch([
    ("INSERT INTO users (name) VALUES (?)", ["Alice"]),
    ("INSERT INTO users (name) VALUES (?)", ["Bob"]),
    ("SELECT COUNT(*) AS n FROM users", None),
])
count = results[-1][0]["n"]   # 2
```

#### execute_many via native batch

```python
conn = D1BindingConnection(self.env.DB)
await conn.connect()

await conn.execute_many(
    "INSERT INTO products (name, price) VALUES (?, ?)",
    [["Widget A", 9.99], ["Widget B", 19.99], ["Widget C", 29.99]],
)
# Sent as a single db.batch() — one round-trip
```

#### Database dump

```python
data = await conn.dump()   # bytes — full SQLite file
with open('backup.sqlite', 'wb') as f:
    f.write(data)
```

#### D1Statement — low-level prepared statements

```python
from pyloquent.d1.binding import D1Statement

stmt = D1Statement(conn, "SELECT * FROM users WHERE id = ?").bind(1)
rows  = await stmt.all()    # list of dicts
row   = await stmt.first()  # dict or None
count = await stmt.run()    # affected rows (int)
```

#### Schema reflection

```python
tables  = await conn.get_tables()
exists  = await conn.table_exists('users')
columns = await conn.get_columns('orders')
indexes = await conn.get_indexes('users')
fks     = await conn.get_foreign_keys('orders')
```

#### DDL via exec()

```python
await conn.exec("CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, msg TEXT)")
```

#### config-dict usage with ConnectionManager

```python
manager = ConnectionManager()
manager.add_connection('default', {
    'driver': 'd1_binding',
    'binding': self.env.DB,     # the D1 binding from self.env
}, default=True)
await manager.connect()
```

---

## License

Pyloquent is open-sourced software licensed under the MIT license.
