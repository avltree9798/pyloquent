# Pyloquent

> **Eloquent-inspired ORM for Python with Pydantic integration**

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Pyloquent brings the elegant ORM patterns from Laravel's Eloquent to Python, with full async/await support, Pydantic validation, and FastAPI integration.

## Features

- **🚀 Async/Await First** - Built from the ground up for async Python
- **✅ Pydantic Integration** - Full validation and type safety
- **🔗 Relationships** - HasOne, HasMany, BelongsTo, BelongsToMany, Polymorphic
- **🗃️ Query Builder** - Fluent, chainable query interface
- **💾 Multiple Drivers** - SQLite, PostgreSQL, MySQL, Cloudflare D1
- **⚡ Query Caching** - Memory, File, and Redis cache stores
- **📝 Migrations** - Full migration system with CLI
- **🧪 Testing Support** - Model factories for test data
- **🎯 FastAPI Ready** - Lifespan context manager support
- **🔄 Soft Deletes** - Built-in soft delete functionality
- **📡 Events/Observers** - Model lifecycle hooks

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
- Query Builder
- Relationships
- Collections
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
class User(Model):
    def posts(self):
        return self.has_many(Post)

class Post(Model):
    def user(self):
        return self.belongs_to(User)

# Usage
posts = await user.posts().get()
user = await post.user().get()

# Eager loading
users = await User.with_('posts', 'profile').get()
```

### Query Builder

```python
# Fluent interface
users = await User.where('age', '>=', 18) \
    .where('active', True) \
    .order_by('created_at', 'desc') \
    .limit(10) \
    .get()

# Aggregates
count = await User.where('active', True).count()
avg_age = await User.avg('age')

# Joins
users = await User.join('posts', 'users.id', '=', 'posts.user_id') \
    .where('posts.published', True) \
    .get()
```

### Soft Deletes

```python
from pyloquent import Model, SoftDeletes

class Post(Model, SoftDeletes):
    __table__ = 'posts'
    deleted_at: Optional[datetime] = None

# Soft delete
await post.delete()

# Restore
await post.restore()

# Force delete
await post.force_delete()

# Query soft deletes
all_posts = await Post.with_trashed().get()
trashed = await Post.only_trashed().get()
```

### Query Caching

```python
from pyloquent import CacheManager, RedisStore

# Setup Redis cache
CacheManager.store(RedisStore(host='localhost', port=6379))

# Cache queries
users = await User.cache(3600).get()  # Cache for 1 hour
posts = await Post.cache_forever().get()  # Cache forever
```

### Migrations

```bash
# Create migration
pyloquent make:migration create_users_table --create

# Run migrations
pyloquent migrate

# Rollback
pyloquent migrate:rollback
```

```python
from pyloquent.migrations import Migration
from pyloquent.schema import SchemaBuilder

class CreateUsersTable(Migration):
    async def up(self, schema: SchemaBuilder) -> None:
        await schema.create('users', lambda table: (
            table.id(),
            table.string('name'),
            table.string('email').unique(),
            table.timestamps()
        ))
    
    async def down(self, schema: SchemaBuilder) -> None:
        await schema.drop('users')
```

### Testing with Factories

```python
from pyloquent import Factory

class UserFactory(Factory[User]):
    model = User
    
    def definition(self):
        return {
            'name': self.faker.name(),
            'email': self.faker.email(),
            'age': random.randint(18, 65),
        }

# Usage
user = await UserFactory.create()
users = await UserFactory.create_many(10)
```

### FastAPI Integration

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
    await manager.connect()
    yield
    await manager.disconnect()

app = FastAPI(lifespan=lifespan)

@app.get('/users')
async def get_users():
    return {'data': await User.all()}
```

### Cloudflare D1

```python
# HTTP API
manager.add_connection('d1', {
    'driver': 'd1',
    'api_token': 'your-token',
    'account_id': 'your-account',
    'database_id': 'your-database',
})

# Worker Binding
manager.add_connection('d1', {
    'driver': 'd1',
    'binding': env.DB,  # From Worker environment
})
```

## Available Drivers

| Driver | Package | Status |
|--------|---------|--------|
| SQLite | Built-in | ✅ Ready |
| PostgreSQL | `asyncpg` | ✅ Ready |
| MySQL | `aiomysql` | ✅ Ready |
| Cloudflare D1 | `httpx` | ✅ Ready |

## CLI Commands

```bash
# Model generation
pyloquent make:model User
pyloquent make:model User --migration

# Migrations
pyloquent make:migration create_users_table --create
pyloquent migrate
pyloquent migrate:rollback
pyloquent migrate:status
pyloquent migrate:fresh
```

## Why Pyloquent?

- **Familiar API** - If you know Laravel Eloquent, you know Pyloquent
- **Type Safe** - Full Pydantic integration for validation
- **Async Native** - Built for modern async Python
- **Production Ready** - Comprehensive test coverage (100% passing)
- **Framework Agnostic** - Works with FastAPI, Django, or standalone
- **Cloud Native** - Cloudflare D1 support for edge deployments

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

Pyloquent is open-sourced software licensed under the [MIT license](LICENSE).

---

<p align="center">Built with ❤️ for the Python community</p>
