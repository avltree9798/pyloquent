# Pyloquent Documentation

> **Eloquent-inspired ORM for Python with Pydantic integration and async support**

Pyloquent brings the elegant ORM patterns from Laravel's Eloquent to Python, with full async/await support, Pydantic validation, and FastAPI integration.

---

## Table of Contents

- [Installation](#installation)
- [Getting Started](#getting-started)
- [Models](#models)
  - [Generating Models](#generating-models)
  - [Model Conventions](#model-conventions)
  - [Default Attribute Values](#default-attribute-values)
- [Retrieving Models](#retrieving-models)
  - [Collections](#collections)
  - [Chunking Results](#chunking-results)
- [Inserting & Updating Models](#inserting--updating-models)
  - [Inserts](#inserts)
  - [Updates](#updates)
  - [Mass Assignment](#mass-assignment)
- [Deleting Models](#deleting-models)
  - [Soft Deletes](#soft-deletes)
- [Query Builder](#query-builder)
  - [Retrieving All Rows](#retrieving-all-rows)
  - [Where Clauses](#where-clauses)
  - [Ordering, Grouping, Limit](#ordering-grouping-limit)
  - [Aggregates](#aggregates)
  - [Joins](#joins)
- [Relationships](#relationships)
  - [One to One](#one-to-one)
  - [One to Many](#one-to-many)
  - [Belongs To](#belongs-to)
  - [Many to Many](#many-to-many)
  - [Polymorphic Relationships](#polymorphic-relationships)
  - [Querying Relations](#querying-relations)
- [Collections](#collections-1)
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
# For PostgreSQL
pip install pyloquent[postgres]

# For MySQL
pip install pyloquent[mysql]

# For Redis caching
pip install pyloquent[redis]

# For model factories
pip install pyloquent[factory]

# For Cloudflare D1 HTTP API
pip install pyloquent[d1]

# Install everything
pip install pyloquent[all]
```

---

## Getting Started

### Configuration

```python
from pyloquent import ConnectionManager

# Create manager
manager = ConnectionManager()

# SQLite
manager.add_connection('default', {
    'driver': 'sqlite',
    'database': 'database.db',  # or ':memory:' for testing
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

# Connect
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

### Generating Models

Use the CLI to generate models:

```bash
# Create a model
pyloquent make:model User

# Create a model with migration
pyloquent make:model User --migration

# Create a model with explicit table name
pyloquent make:model User --table=admins
```

### Model Conventions

| Feature | Convention | Override |
|---------|-----------|----------|
| Table name | Pluralized snake_case | `__table__ = 'custom'` |
| Primary key | `id` | `__primary_key__ = 'uuid'` |
| Timestamps | `created_at`, `updated_at` | `__timestamps__ = False` |
| Foreign key | Model name + `_id` | Specify in relation |

```python
class Flight(Model):
    # Table: flights
    # Primary key: id
    # Timestamps: enabled by default
    
    __table__ = 'my_flights'
    __primary_key__ = 'flight_id'
    __timestamps__ = False
    
    id: Optional[int] = None
    flight_number: str
    origin: str
    destination: str
```

### Default Attribute Values

```python
from datetime import datetime
from typing import Optional
from pyloquent import Model

class Flight(Model):
    __table__ = 'flights'
    __fillable__ = ['flight_number', 'status', 'boarded_at']
    
    id: Optional[int] = None
    flight_number: str
    status: str = 'pending'  # Default value
    boarded_at: Optional[datetime] = None
```

---

## Retrieving Models

### Retrieving All Models

```python
# All users
users = await User.all()

# Chunked - memory efficient for large datasets
async for users in User.chunk(100):
    for user in users:
        print(user.name)
```

### Retrieving Single Models

```python
# Find by primary key
user = await User.find(1)

# Find or throw exception
user = await User.find_or_fail(1)  # Raises ModelNotFoundException

# Find first matching
user = await User.where('email', 'john@example.com').first()

# First or create
user = await User.first_or_create(
    {'email': 'john@example.com'},
    {'name': 'John Doe'}
)

# Update or create
user = await User.update_or_create(
    {'email': 'john@example.com'},
    {'name': 'John Doe', 'age': 30}
)
```

### Not Found Exceptions

```python
from pyloquent import ModelNotFoundException

try:
    user = await User.find_or_fail(1)
except ModelNotFoundException:
    print("User not found")
```

### Collections

Results are returned as Collection instances:

```python
users = await User.all()

# Check if empty
if users.is_empty():
    print("No users")

# Count
count = users.count()

# First / Last
first = users.first()
last = users.last()

# Map
names = users.map(lambda u: u.name.upper())

# Filter
adults = users.filter(lambda u: u.age and u.age >= 18)

# Pluck
emails = users.pluck('email')

# Sort
sorted_users = users.sort_by('name')
sorted_desc = users.sort_by_desc('created_at')
```

---

## Inserting & Updating Models

### Inserts

```python
# Create and save
user = User(name='John', email='john@example.com')
await user.save()

# Create with dictionary
user = await User.create({
    'name': 'John',
    'email': 'john@example.com',
    'age': 30
})

# Create via relationship
user = await User.find(1)
post = await user.posts().create({
    'title': 'My First Post',
    'content': 'Hello World!'
})
```

### Updates

```python
# Fetch and update
user = await User.find(1)
user.name = 'Jane Doe'
await user.save()

# Mass update
await User.where('active', False).update({'status': 'inactive'})

# Update or create
user = await User.update_or_create(
    {'email': 'john@example.com'},
    {'name': 'John Doe', 'age': 31}
)
```

### Mass Assignment

```python
class User(Model):
    __fillable__ = ['name', 'email', 'age']  # Allowed
    __guarded__ = ['id', 'is_admin']          # Protected
    
    id: Optional[int] = None
    name: str
    email: str
    age: Optional[int] = None
    is_admin: bool = False
```

---

## Deleting Models

```python
# Delete a single model
user = await User.find(1)
await user.delete()

# Delete by query
await User.where('active', False).delete()

# Delete all (use with caution!)
await User.query.delete()

# Truncate
await User.query.truncate()
```

### Soft Deletes

```python
from datetime import datetime
from typing import Optional
from pyloquent import Model
from pyloquent.traits import SoftDeletes

class Post(Model, SoftDeletes):
    __table__ = 'posts'
    __fillable__ = ['title', 'content']
    
    id: Optional[int] = None
    title: str
    content: str
    deleted_at: Optional[datetime] = None  # Required for SoftDeletes

# Usage
post = await Post.find(1)
await post.delete()  # Soft delete - sets deleted_at

# Restore
await post.restore()

# Force delete (permanent)
await post.force_delete()

# Query soft deletes
posts = await Post.with_trashed().get()      # Include soft deleted
trashed = await Post.only_trashed().get()    # Only soft deleted
```

---

## Query Builder

### Retrieving All Rows

```python
users = await User.query.get()
```

### Where Clauses

```python
# Basic where
users = await User.where('age', '>', 18).get()

# Multiple conditions (AND)
users = await User.where('age', '>', 18).where('active', True).get()

# OR where
users = await User.where('age', '>', 18).or_where('vip', True).get()

# Where in
users = await User.where_in('id', [1, 2, 3]).get()

# Where not in
users = await User.where_not_in('id', [4, 5, 6]).get()

# Where between
users = await User.where_between('age', [18, 65]).get()

# Where null
users = await User.where_null('deleted_at').get()

# Where not null
users = await User.where_not_null('email_verified_at').get()

# Nested where
users = await User.where(lambda q: (
    q.where('age', '<', 18).or_where('age', '>', 65)
)).get()
```

### Ordering, Grouping, Limit

```python
# Order by
users = await User.order_by('name').get()
users = await User.order_by('created_at', 'desc').get()

# Latest / Oldest
users = await User.latest().get()  # by created_at
users = await User.latest('updated_at').get()

# Group by
users = await User.group_by('status').get()

# Having
users = await User.group_by('status').having('count', '>', 5).get()

# Limit / Offset
users = await User.limit(10).get()
users = await User.offset(10).limit(10).get()

# Pagination helper
users = await User.for_page(2, 15).get()  # Page 2, 15 per page
```

### Aggregates

```python
# Count
count = await User.where('active', True).count()

# Max / Min
oldest = await User.max('age')
youngest = await User.min('age')

# Sum / Avg
total = await User.sum('points')
average = await User.avg('age')
```

### Selects

```python
# Select specific columns
users = await User.select('name', 'email').get()

# Distinct
users = await User.distinct().select('country').get()

# Add select
users = await User.select('name').add_select('email').get()

# Raw expressions
users = await User.select_raw('COUNT(*) as total').get()
```

### Joins

```python
# Inner join
users = await User.join('posts', 'users.id', '=', 'posts.user_id').get()

# Left join
users = await User.left_join('posts', 'users.id', '=', 'posts.user_id').get()

# Right join
users = await User.right_join('posts', 'users.id', '=', 'posts.user_id').get()

# Cross join
users = await User.cross_join('categories').get()

# Advanced join with callback
users = await User.join('posts', lambda join: (
    join.on('users.id', '=', 'posts.user_id')
        .where('posts.published', True)
)).get()
```

---

## Relationships

### One to One

```python
class User(Model):
    __table__ = 'users'
    
    id: Optional[int] = None
    name: str
    
    def phone(self):
        return self.has_one(Phone)

class Phone(Model):
    __table__ = 'phones'
    
    id: Optional[int] = None
    user_id: int
    number: str
    
    def user(self):
        return self.belongs_to(User)

# Usage
phone = await user.phone().get()
owner = await phone.user().get()
```

### One to Many

```python
class User(Model):
    def posts(self):
        return self.has_many(Post)

class Post(Model):
    def user(self):
        return self.belongs_to(User)

# Usage
posts = await user.posts().get()
user = await post.user().get()

# Create through relation
post = await user.posts().create({
    'title': 'New Post',
    'content': 'Content here'
})
```

### Many to Many

```python
class User(Model):
    def roles(self):
        return self.belongs_to_many(Role)

class Role(Model):
    def users(self):
        return self.belongs_to_many(User)

# Usage
roles = await user.roles().get()
users = await role.users().get()

# Attach / Detach
await user.roles().attach(role_id)
await user.roles().detach(role_id)
await user.roles().sync([1, 2, 3])  # Replace all

# With pivot data
await user.roles().attach(role_id, {
    'expires_at': datetime.now() + timedelta(days=30)
})

# Access pivot data
roles = await user.roles().with_pivot('expires_at').get()
for role in roles:
    print(role.pivot.expires_at)
```

### Polymorphic Relationships

```python
class Comment(Model):
    def commentable(self):
        return self.morph_to('commentable')

class Post(Model):
    def comments(self):
        return self.morph_many(Comment, 'commentable')

class Video(Model):
    def comments(self):
        return self.morph_many(Comment, 'commentable')

# Usage
# Comments table needs: id, body, commentable_type, commentable_id

# Get comments for a post
comments = await post.comments().get()

# Get parent of a comment
parent = await comment.commentable().get()  # Returns Post or Video
```

### Querying Relations

```python
# Has
users_with_posts = await User.has('posts').get()
users_with_many_posts = await User.has('posts', '>=', 5).get()

# Doesnt Have
users_without_posts = await User.doesnt_have('posts').get()

# Where Has
users = await User.where_has('posts', lambda q: (
    q.where('published', True)
)).get()

# With Count
users = await User.with_count('posts').get()
for user in users:
    print(f"{user.name} has {user.posts_count} posts")

# Load relations (eager loading)
users = await User.with_('posts', 'profile').get()

# Lazy eager loading
user = await User.find(1)
await user.load('posts', 'comments')
```

---

## Collections

Collections extend Python lists with powerful methods:

```python
users = await User.all()

# Checking
users.is_empty()
users.is_not_empty()
users.contains(lambda u: u.id == 1)

# Filtering
adults = users.where('age', '>=', 18)
active = users.filter(lambda u: u.active)

# Transformation
names = users.pluck('name')
upper_names = users.map(lambda u: u.name.upper())
keyed = users.key_by('id')  # Dict by key

# Sorting
sorted_users = users.sort_by('name')
sorted_desc = users.sort_by_desc('created_at')

# Aggregates
total_age = users.sum('age')
avg_age = users.avg('age')
max_age = users.max('age')

# Slicing
first_10 = users.take(10)
except_first = users.skip(1)
page_2 = users.for_page(2, 15)

# Iteration
users.each(lambda u: print(u.name))

# Unique
unique_countries = users.unique('country')
```

---

## Mutators & Casting

### Attribute Casting

```python
from datetime import datetime
from decimal import Decimal
from pyloquent import Model

class User(Model):
    __casts__ = {
        'age': 'int',
        'balance': 'decimal:2',
        'is_active': 'bool',
        'metadata': 'json',
        'birth_date': 'date',
        'last_login': 'datetime',
    }
    
    id: Optional[int] = None
    age: int = 0
    balance: Decimal = Decimal('0.00')
    is_active: bool = True
    metadata: dict = {}
    birth_date: Optional[date] = None
    last_login: Optional[datetime] = None
```

Available cast types:
- `int`, `float`, `bool`, `string`
- `json` - Automatically JSON encode/decode
- `date` - Date object
- `datetime` - Datetime object
- `decimal:X` - Decimal with X precision

---

## Query Scopes

### Local Scopes

```python
class Post(Model):
    def scope_published(self, query):
        return query.where('status', 'published')
    
    def scope_recent(self, query):
        return query.order_by('created_at', 'desc')

# Usage
posts = await Post.published().recent().get()
```

### Global Scopes

```python
class Post(Model):
    @classmethod
    def boot(cls):
        super().boot()
        cls.add_global_scope('active', lambda q: q.where('active', True))

# Now all queries include WHERE active = True
posts = await Post.all()  # Only active posts

# Remove scope
posts = await Post.without_global_scope('active').get()
```

---

## Events & Observers

### Model Events

```python
class User(Model):
    @classmethod
    def boot(cls):
        super().boot()
        
        cls.on('creating', lambda user: print(f"Creating {user.name}"))
        cls.on('created', lambda user: print(f"Created {user.name}"))
        cls.on('updating', lambda user: print(f"Updating {user.name}"))
        cls.on('updated', lambda user: print(f"Updated {user.name}"))
        cls.on('deleting', lambda user: print(f"Deleting {user.name}"))
        cls.on('deleted', lambda user: print(f"Deleted {user.name}"))
        cls.on('saving', lambda user: print(f"Saving {user.name}"))
        cls.on('saved', lambda user: print(f"Saved {user.name}"))
```

### Observers

```python
from pyloquent import ModelObserver, observes

@observes(User)
class UserObserver(ModelObserver):
    async def creating(self, user):
        user.slug = slugify(user.name)
    
    async function created(self, user):
        await send_welcome_email(user)
    
    async function updating(self, user):
        if user.is_dirty('email'):
            user.email_verified_at = None
    
    async function deleted(self, user):
        await cleanup_user_data(user)

# Register observer
User.observe(UserObserver())
```

---

## Query Caching

### Basic Caching

```python
from pyloquent import CacheManager, MemoryStore

# Setup cache
CacheManager.store(MemoryStore())

# Cache for 1 hour
users = await User.cache(3600).get()

# Cache forever
users = await User.cache_forever().get()

# Custom cache key
users = await User.cache(3600, 'active_users').get()

# Cache with tags
users = await User.cache(3600).cache_tags('users', 'active').get()
```

### Cache Stores

```python
from pyloquent import CacheManager, FileStore, RedisStore

# File-based cache
CacheManager.store(FileStore('/path/to/cache'))

# Redis cache
CacheManager.store(RedisStore(
    host='localhost',
    port=6379,
    db=0
))

# Memory cache (default)
CacheManager.store(MemoryStore())
```

---

## Database Migrations

### Creating Migrations

```bash
# Create a migration
pyloquent make:migration create_users_table

# Create a table migration
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
            table.timestamp('email_verified_at').nullable(),
            table.string('password'),
            table.timestamps()  # created_at, updated_at
        ))
    
    async def down(self, schema: SchemaBuilder) -> None:
        await schema.drop('users')
```

### Column Types

```python
# IDs
table.id()  # Auto-increment primary key
table.uuid('id')  # UUID primary key

# Strings
table.string('name', 255)
table.text('description')
table.char('country_code', 2)

# Numbers
table.integer('age')
table.big_integer('views')
table.small_integer('priority')
table.tiny_integer('status')
table.float('rating', 8, 2)
table.double('amount', 15, 8)
table.decimal('price', 10, 2)

# Boolean
table.boolean('is_active')

# Dates
table.date('birth_date')
table.datetime('last_login')
table.time('opens_at')
table.timestamp('created_at')
table.timestamps()  # created_at + updated_at

# JSON
table.json('metadata')
table.jsonb('settings')  # PostgreSQL

# Special
table.enum('status', ['pending', 'active', 'inactive'])
table.uuid('uuid')
table.ip_address('last_ip')
table.mac_address('device_mac')

# Modifiers
table.string('email').unique()
table.integer('user_id').index()
table.string('name').nullable()
table.string('avatar').default('default.png')
table.integer('views').unsigned()

# Foreign keys
table.foreign('user_id').references('id').on('users').on_delete('cascade')
```

### Running Migrations

```bash
# Run all pending migrations
pyloquent migrate

# Rollback last batch
pyloquent migrate:rollback

# Rollback specific number
pyloquent migrate:rollback --steps=3

# Reset all migrations
pyloquent migrate:reset

# Fresh (drop all and re-run)
pyloquent migrate:fresh

# Check status
pyloquent migrate:status
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
            'name': self.faker.name(),
            'email': self.faker.email(),
            'age': random.randint(18, 65),
            'is_active': True,
        }

# Factory with states
class PostFactory(Factory[Post]):
    model = Post
    
    def definition(self):
        return {
            'title': self.faker.sentence(),
            'content': self.faker.paragraph(),
            'published': True,
        }
    
    def unpublished(self):
        return self.state({'published': False})
    
    def featured(self):
        return self.state({'is_featured': True})
```

### Using Factories

```python
# Create a user
user = await UserFactory.create()

# Create with overrides
user = await UserFactory.create({'name': 'John Doe'})

# Create many
users = await UserFactory.create_many(10)

# Make (don't save)
user = UserFactory.make()

# States
post = await PostFactory.unpublished().create()
featured = await PostFactory.featured().create_many(5)

# Batch create
users = await UserFactory.create_batch(50)
```

---

## Cloudflare D1

### Using D1 with HTTP API

```python
from pyloquent import ConnectionManager

manager = ConnectionManager()
manager.add_connection('d1', {
    'driver': 'd1',
    'api_token': 'your-cloudflare-api-token',
    'account_id': 'your-account-id',
    'database_id': 'your-database-id',
}, default=True)

await manager.connect()

# Use normally
users = await User.all()
```

### Using D1 with Worker Bindings

```python
# In your Cloudflare Worker
from pyloquent import ConnectionManager

manager = ConnectionManager()
manager.add_connection('d1', {
    'driver': 'd1',
    'binding': env.DB,  # D1 binding from Worker environment
}, default=True)

await manager.connect()
```

### D1 HTTP Client (Direct)

```python
from pyloquent import D1HttpClient

client = D1HttpClient(
    account_id='your-account-id',
    database_id='your-database-id',
    api_token='your-api-token'
)

# Query
results = await client.query(
    'SELECT * FROM users WHERE id = ?',
    [1]
)

# Execute
await client.execute(
    'INSERT INTO users (name, email) VALUES (?, ?)',
    ['John', 'john@example.com']
)

# Batch
await client.batch([
    {'sql': 'INSERT INTO users (name) VALUES (?)', 'params': ['John']},
    {'sql': 'INSERT INTO users (name) VALUES (?)', 'params': ['Jane']},
])
```

---

## FastAPI Integration

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pyloquent import ConnectionManager

manager = ConnectionManager()
manager.add_connection('default', {
    'driver': 'sqlite',
    'database': 'app.db',
}, default=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await manager.connect()
    yield
    # Shutdown
    await manager.disconnect()

app = FastAPI(lifespan=lifespan)

@app.get('/users')
async def get_users():
    users = await User.all()
    return {'data': users}

@app.get('/users/{id}')
async def get_user(id: int):
    user = await User.find_or_fail(id)
    return {'data': user}

@app.post('/users')
async function create_user(data: dict):
    user = await User.create(data)
    return {'data': user}

@app.put('/users/{id}')
async def update_user(id: int, data: dict):
    user = await User.find_or_fail(id)
    for key, value in data.items():
        setattr(user, key, value)
    await user.save()
    return {'data': user}

@app.delete('/users/{id}')
async function delete_user(id: int):
    user = await User.find_or_fail(id)
    await user.delete()
    return {'message': 'User deleted'}
```

---

## Advanced Usage

### Raw Queries

```python
# Select
results = await User.query.select_raw('COUNT(*) as count').get()

# Where raw
users = await User.where_raw('age > ? AND status = ?', [18, 'active']).get()

# Order by raw
users = await User.order_by_raw('RANDOM()').get()
```

### Subqueries

```python
# Where exists
users = await User.where_exists(
    Post.where_column('posts.user_id', 'users.id')
        .where('published', True)
).get()

# Subquery select
users = await User.add_select([
    'name',
    Post.where_column('user_id', 'users.id')
        .count()
        .as_('posts_count')
]).get()
```

### Database Transactions

```python
# Manual transaction
await manager.connection().begin_transaction()
try:
    await User.create({'name': 'John'})
    await Post.create({'title': 'Hello'})
    await manager.connection().commit()
except Exception:
    await manager.connection().rollback()

# Context manager (if supported by driver)
async with manager.connection().transaction():
    await User.create({'name': 'John'})
    await Post.create({'title': 'Hello'})
```

---

## License

Pyloquent is open-sourced software licensed under the MIT license.
