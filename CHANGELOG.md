# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
  - Hidden attributes for serialization
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
