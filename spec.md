
# **SPEC v8.0: Pyloquent - Deep Dive Architectural Blueprint**

## **1. Core Engine: D1 Dual-Mode & FastAPI Lifecycle**
*(Eloquent Refs: Database Configuration)*

The framework must gracefully handle both traditional TCP databases (Postgres/MySQL) and Cloudflare D1 (HTTP vs. Worker Binding).

### **1.1. FastAPI Connection Manager**
```python
# pyloquent/database/manager.py
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request

class PyloquentManager:
    def __init__(self, config: dict):
        self.config = config
        self.connections = {} # Holds connection pools

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        # Startup: Initialize HTTP clients or TCP pools
        for name, cfg in self.config['connections'].items():
            if cfg['driver'] == 'd1_http':
                self.connections[name] = D1HTTPConnection(cfg)
            elif cfg['driver'] == 'postgres':
                self.connections[name] = PostgresConnection(cfg)
        yield
        # Shutdown: Close clients/pools
        for conn in self.connections.values():
            await conn.close()

# D1 Binding Middleware (For Cloudflare Workers)
class PyloquentWorkerMiddleware:
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and "env" in scope:
            # Bind the D1 object from the Worker request context to a local ContextVar
            from pyloquent.context import d1_binding_var
            d1_binding_var.set(scope["env"].DB)
        await self.app(scope, receive, send)
```

## **2. The Active Record Model (Pydantic Native)**
*(Eloquent Refs: Defining Models, Mass Assignment, Serialization)*

Pyloquent `Model` inherits from `pydantic.BaseModel`. A metaclass handles the Eloquent setup (table guessing, builder forwarding) without interfering with Pydantic's core validation.

### **2.1. Model Definition & Metadata**
```python
# app/models.py
from pyloquent import Model
from pyloquent.traits import SoftDeletes
from pydantic import EmailStr, Field
from datetime import datetime

class User(Model, SoftDeletes): # Integrates SoftDeletes scope automatically
    # 1. Pyloquent Metadata
    __table__ = "users"
    __fillable__ = ["name", "email", "is_active"]
    __hidden__ = ["password"] # Stored in DB, hidden from Pydantic model_dump()
    
    # 2. Pydantic Schema (Handles type casting natively)
    id: int | None = None
    name: str
    email: EmailStr
    password: str
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None

    # 3. Eloquent Relationships
    def posts(self):
        from app.models.post import Post
        return self.has_many(Post, foreign_key="user_id", local_key="id")

    # 4. Accessors (Eloquent $appends equivalent)
    @property
    def display_name(self) -> str:
        return f"{self.name} ({self.email})"
```

### **2.2. Async Execution (FastAPI Route Example)**
```python
# app/routes/users.py
from fastapi import APIRouter
from app.models import User

router = APIRouter()

@router.post("/", response_model=User)
async def create_user(data: User):
    # 'data' is already validated by Pydantic.
    # Instantiate Pyloquent Model, which skips re-validation for raw dicts
    user = User(**data.model_dump())
    
    # Async save executes: INSERT INTO users (...) VALUES (...)
    await user.save() 
    return user # Pydantic hides 'password' automatically in the response
```

## **3. The Query Builder (100% Eloquent Coverage)**
*(Eloquent Refs: Retrieving Models, Chunking, Aggregates)*

The builder mutates state synchronously, but terminates asynchronously.

### **3.1. Builder State & Execution**
```python
# Synchronous chaining
query = User.where('is_active', True).where_in('role', ['admin', 'editor']).order_by('created_at', 'desc')

# Async Terminators (Compiles to Grammar and executes)
users = await query.get()           # Returns pyloquent.Collection[User]
first_user = await query.first()    # Returns User | None
count = await query.count()         # Returns int

# Eloquent "Chunking" for memory safety
async for chunk in User.where('is_active', True).chunk(100):
    for user in chunk:
        await process_user(user)
```

## **4. Relationships & Loading Strategies**
*(Eloquent Refs: Relationships, Eager Loading)*

### **4.1. Eager Loading (Solving N+1)**
```python
# Executes EXACTLY 2 queries:
# 1. SELECT * FROM users WHERE is_active = 1
# 2. SELECT * FROM posts WHERE user_id IN (1, 2, 3...)
users = await User.with_('posts').where('is_active', True).get()

for user in users:
    # Synchronous access, data is already hydrated in memory
    print(user.posts) # pyloquent.Collection[Post]
```

### **4.2. Explicit Async Lazy Loading**
Because Python `properties` cannot be `async`, we use an explicit `load()` method to respect the event loop.
```python
user = await User.find(1)

# Await the relation method directly to fetch results
posts = await user.posts().get()

# OR: Load it into the model's memory for later synchronous access
await user.load('posts', 'profile')
print(user.posts)
```

### **4.3. Querying Relationship Existence**
```python
# Eloquent's whereHas equivalent
active_writers = await User.where_has(
    'posts', 
    lambda q: q.where('views', '>', 1000)
).get()
```

## **5. Migrations & Schema Builder (`pyloquent-cli`)**
*(Eloquent Refs: Migrations, Schema Builder)*

The CLI uses the exact same grammar engine to compile DDL statements. For D1, running migrations locally uses the HTTP transport layer to modify the remote database.

### **5.1. The Migration File**
```python
# migrations/2023_10_27_create_users_table.py
from pyloquent.schema import Schema, Blueprint

class CreateUsersTable:
    async def up(self):
        # Schema.create yields a Blueprint object
        await Schema.create('users', lambda table: [
            table.id(),
            table.string('name', length=100),
            table.string('email').unique(),
            table.string('password'),
            table.boolean('is_active').default(True),
            table.timestamps(),
            table.soft_deletes()
        ])
    
    async def down(self):
        await Schema.drop_if_exists('users')
```

## **6. Testing Strategy**
To guarantee 100% coverage, unit tests must assert exact SQL compilation without needing a live database.

### **6.1. Grammar Compilation Tests (`pytest`)**
```python
# tests/test_query_builder.py
import pytest
from pyloquent.query import QueryBuilder
from pyloquent.grammars import SQLiteGrammar

def test_basic_where_compilation():
    builder = QueryBuilder(grammar=SQLiteGrammar())
    
    builder.from_('users').where('id', '=', 1).where('is_active', True)
    sql, bindings = builder.to_sql()
    
    assert sql == 'SELECT * FROM "users" WHERE "id" = ? AND "is_active" = ?'
    assert bindings == [1, True]

def test_where_in_compilation():
    builder = QueryBuilder(grammar=SQLiteGrammar())
    
    builder.from_('users').where_in('id', [1, 2, 3])
    sql, bindings = builder.to_sql()
    
    assert sql == 'SELECT * FROM "users" WHERE "id" IN (?, ?, ?)'
    assert bindings == [1, 2, 3]
```
