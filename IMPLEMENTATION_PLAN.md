# Pyloquent v0.1.0 Implementation Plan

## Research Summary

Based on deep research of:
- **Laravel Eloquent ORM** - The gold standard for Active Record pattern
- **Prisma Client Python** - Type-safe ORM with excellent async/sync design
- **Peewee ORM** - Lightweight, expressive Python ORM
- **SQLAlchemy 2.0** - Modern Python ORM with PEP 484 type annotations
- **Cloudflare D1** - Serverless SQLite-based database with HTTP & Worker bindings

## Key Design Decisions

### 1. Architecture Philosophy
- **Pydantic-Native**: Models inherit from `pydantic.BaseModel` for validation & serialization
- **Async-First**: All database operations are async by default
- **Eloquent-Compatible API**: Familiar method names for Laravel developers
- **Type-Safe**: Full mypy/Pyright support with proper type annotations
- **Grammar-Based**: Separate SQL compilation from execution for testability

### 2. Version 0.1.0 Scope (MVP)
**Goal**: A working Active Record ORM with Query Builder for SQLite/PostgreSQL/MySQL

**Core Features**:
- Query Builder (WHERE, JOIN, ORDER BY, LIMIT, aggregates)
- Model base class with CRUD operations
- Basic relationships (hasMany, belongsTo)
- Pydantic integration
- Grammar-based SQL compilation
- Async connection management
- Basic FastAPI integration

**Out of Scope for v0.1.0**:
- D1 HTTP API (v0.2.0)
- Migrations system (v0.2.0)
- Soft deletes, scopes, accessors
- Advanced relationships (many-to-many, polymorphic)
- CLI tool
- Database seeding/factories

## Implementation Phases

---

## Phase 0: Project Foundation (Week 1)

### 0.1 Project Structure
```
pyloquent/
├── pyproject.toml
├── README.md
├── LICENSE
├── CHANGELOG.md
├── .gitignore
├── .pre-commit-config.yaml
├── pyloquent/
│   ├── __init__.py
│   ├── __version__.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py
│   │   ├── manager.py
│   │   └── transaction.py
│   ├── query/
│   │   ├── __init__.py
│   │   ├── builder.py
│   │   ├── grammar.py
│   │   └── expression.py
│   ├── orm/
│   │   ├── __init__.py
│   │   ├── model.py
│   │   ├── model_meta.py
│   │   ├── collection.py
│   │   └── relations/
│   │       ├── __init__.py
│   │       ├── relation.py
│   │       ├── has_many.py
│   │       └── belongs_to.py
│   ├── grammars/
│   │   ├── __init__.py
│   │   ├── grammar.py
│   │   ├── sqlite_grammar.py
│   │   ├── postgres_grammar.py
│   │   └── mysql_grammar.py
│   ├── types.py
│   └── exceptions.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_query_builder.py
│   │   ├── test_grammar.py
│   │   └── test_model.py
│   └── integration/
│       └── test_database.py
└── examples/
    └── basic_usage.py
```

### 0.2 Dependencies (pyproject.toml)
```toml
[project]
name = "pyloquent"
version = "0.1.0"
description = "Eloquent-inspired ORM for Python with Pydantic and FastAPI support"
requires-python = ">=3.10"
dependencies = [
    "pydantic>=2.0.0",
    "pydantic-core>=2.0.0",
    "asyncpg>=0.28.0",        # PostgreSQL async driver
    "aiomysql>=0.2.0",        # MySQL async driver
    "aiosqlite>=0.19.0",      # SQLite async driver
    "typing-extensions>=4.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0.0",
    "mypy>=1.0.0",
    "ruff>=0.1.0",
    "pre-commit>=3.0.0",
]
fastapi = [
    "fastapi>=0.100.0",
]
```

### 0.3 Development Tools Setup
- Configure ruff for linting/formatting
- Configure mypy for type checking
- Setup pre-commit hooks
- Setup pytest with asyncio support

---

## Phase 1: Core Infrastructure (Week 1-2)

### 1.1 Grammar System (SQL Compilation)
**Purpose**: Convert query builder state to SQL strings and bindings

**Key Classes**:
```python
class Grammar(ABC):
    """Base class for SQL grammar implementations"""
    
    def compile_select(self, query: QueryBuilder) -> Tuple[str, List[Any]]: ...
    def compile_insert(self, query: QueryBuilder, values: Dict) -> Tuple[str, List[Any]]: ...
    def compile_update(self, query: QueryBuilder, values: Dict) -> Tuple[str, List[Any]]: ...
    def compile_delete(self, query: QueryBuilder) -> Tuple[str, List[Any]]: ...
    
    # Clause compilers
    def compile_wheres(self, query: QueryBuilder) -> str: ...
    def compile_joins(self, query: QueryBuilder) -> str: ...
    def compile_orders(self, query: QueryBuilder) -> str: ...
    def compile_groups(self, query: QueryBuilder) -> str: ...
    def compile_havings(self, query: QueryBuilder) -> str: ...
    def compile_limit(self, query: QueryBuilder) -> str: ...
    def compile_offset(self, query: QueryBuilder) -> str: ...
    
    # Helpers
    def wrap_table(self, table: str) -> str: ...
    def wrap_column(self, column: str) -> str: ...
    def parameter(self, value: Any) -> str: ...

class SQLiteGrammar(Grammar):
    """SQLite-specific grammar"""
    
class PostgresGrammar(Grammar):
    """PostgreSQL-specific grammar"""
    # Handle RETURNING, ILIKE, etc.
    
class MySQLGrammar(Grammar):
    """MySQL-specific grammar"""
    # Handle backticks, etc.
```

**Design Notes**:
- Grammar is stateless and can be reused
- Separate SQL generation from execution for testability
- Each driver can override specific compilation methods

### 1.2 Database Connection Management
**Purpose**: Abstract database connections and execute queries

```python
class Connection(ABC):
    """Abstract base for database connections"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.grammar = self.get_grammar()
    
    @abstractmethod
    async def connect(self) -> None: ...
    
    @abstractmethod
    async def disconnect(self) -> None: ...
    
    @abstractmethod
    async def execute(self, sql: str, bindings: List[Any] = None) -> Any: ...
    
    @abstractmethod
    async def fetch_all(self, sql: str, bindings: List[Any] = None) -> List[Dict]: ...
    
    @abstractmethod
    async def fetch_one(self, sql: str, bindings: List[Any] = None) -> Optional[Dict]: ...
    
    @abstractmethod
    def get_grammar(self) -> Grammar: ...

class PostgresConnection(Connection):
    """PostgreSQL async connection using asyncpg"""
    
class MySQLConnection(Connection):
    """MySQL async connection using aiomysql"""
    
class SQLiteConnection(Connection):
    """SQLite async connection using aiosqlite"""
```

### 1.3 Connection Manager
**Purpose**: Manage multiple named connections

```python
class ConnectionManager:
    """Manages database connections with FastAPI lifecycle integration"""
    
    def __init__(self):
        self._connections: Dict[str, Connection] = {}
        self._default: Optional[str] = None
    
    def add_connection(self, name: str, config: Dict[str, Any]) -> None:
        """Add a new connection configuration"""
        
    async def connect(self, name: Optional[str] = None) -> None:
        """Connect to a specific or all connections"""
        
    async def disconnect(self, name: Optional[str] = None) -> None:
        """Disconnect from a specific or all connections"""
        
    def connection(self, name: Optional[str] = None) -> Connection:
        """Get a connection by name (default if not specified)"""
        
    async def transaction(self, name: Optional[str] = None):
        """Context manager for transactions"""
        
    # FastAPI lifespan integration
    def lifespan(self):
        """Returns asynccontextmanager for FastAPI lifespan"""
```

---

## Phase 2: Query Builder (Week 2-3)

### 2.1 QueryBuilder Class
**Purpose**: Fluent interface for building SQL queries

```python
class QueryBuilder:
    """
    Query builder with synchronous state mutation and async execution.
    
    Pattern: 
    - Chaining methods return self (sync)
    - Terminator methods are async and execute
    """
    
    def __init__(
        self,
        grammar: Grammar,
        connection: Optional[Connection] = None,
        model_class: Optional[Type[Model]] = None
    ):
        self.grammar = grammar
        self.connection = connection
        self.model_class = model_class
        
        # Query state
        self._table: Optional[str] = None
        self._selects: List[str] = []
        self._wheres: List[WhereClause] = []
        self._joins: List[JoinClause] = []
        self._orders: List[OrderClause] = []
        self._groups: List[str] = []
        self._havings: List[HavingClause] = []
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None
        self._bindings: Dict[str, List[Any]] = {
            'select': [], 'from': [], 'join': [], 
            'where': [], 'having': [], 'order': []
        }
    
    # ===== Table Selection =====
    def from_(self, table: str) -> Self: ...
    def table(self, table: str) -> Self: ...  # alias
    
    # ===== Column Selection =====
    def select(self, *columns: str) -> Self: ...
    def add_select(self, *columns: str) -> Self: ...
    def distinct(self) -> Self: ...
    
    # ===== WHERE Clauses =====
    def where(self, column: str, operator: Any = None, value: Any = None) -> Self: ...
    def where_not(self, column: str, operator: Any = None, value: Any = None) -> Self: ...
    def where_in(self, column: str, values: List[Any]) -> Self: ...
    def where_not_in(self, column: str, values: List[Any]) -> Self: ...
    def where_between(self, column: str, values: Tuple[Any, Any]) -> Self: ...
    def where_null(self, column: str) -> Self: ...
    def where_not_null(self, column: str) -> Self: ...
    def where_raw(self, sql: str, bindings: List[Any] = None) -> Self: ...
    
    def or_where(self, column: str, operator: Any = None, value: Any = None) -> Self: ...
    def or_where_in(self, column: str, values: List[Any]) -> Self: ...
    
    def where_column(self, first: str, operator: Any, second: str) -> Self: ...
    
    # Logical grouping
    def where_group(self, callback: Callable[[QueryBuilder], None]) -> Self: ...
    def or_where_group(self, callback: Callable[[QueryBuilder], None]) -> Self: ...
    
    # ===== JOINs =====
    def join(self, table: str, first: str, operator: str, second: str) -> Self: ...
    def left_join(self, table: str, first: str, operator: str, second: str) -> Self: ...
    def right_join(self, table: str, first: str, operator: str, second: str) -> Self: ...
    def join_sub(self, query: QueryBuilder, alias: str, first: str, operator: str, second: str) -> Self: ...
    
    # ===== Ordering, Grouping, Limiting =====
    def order_by(self, column: str, direction: str = 'asc') -> Self: ...
    def order_by_desc(self, column: str) -> Self: ...
    def latest(self, column: str = 'created_at') -> Self: ...
    def oldest(self, column: str = 'created_at') -> Self: ...
    
    def group_by(self, *columns: str) -> Self: ...
    def having(self, column: str, operator: Any, value: Any) -> Self: ...
    
    def limit(self, value: int) -> Self: ...
    def offset(self, value: int) -> Self: ...
    def for_page(self, page: int, per_page: int = 15) -> Self: ...
    
    # ===== Aggregates =====
    async def count(self, column: str = '*') -> int: ...
    async def max(self, column: str) -> Any: ...
    async def min(self, column: str) -> Any: ...
    async def sum(self, column: str) -> Any: ...
    async def avg(self, column: str) -> Any: ...
    
    # ===== Async Terminators =====
    async def get(self) -> Collection[Model] | List[Dict]: ...
    async def first(self) -> Optional[Model | Dict]: ...
    async def first_or_fail(self) -> Model: ...
    async def find(self, id: Any) -> Optional[Model]: ...
    async def find_or_fail(self, id: Any) -> Model: ...
    async def pluck(self, column: str) -> List[Any]: ...
    async def value(self, column: str) -> Any: ...
    
    # ===== Insert / Update / Delete =====
    async def insert(self, values: Dict[str, Any] | List[Dict[str, Any]]) -> Any: ...
    async def insert_get_id(self, values: Dict[str, Any]) -> Any: ...
    async def update(self, values: Dict[str, Any]) -> int: ...
    async def delete(self) -> int: ...
    
    # ===== Chunking =====
    async def chunk(self, count: int) -> AsyncIterator[List[Model]]: ...
    async def chunk_by_id(self, count: int, column: str = 'id') -> AsyncIterator[List[Model]]: ...
    
    # ===== Utilities =====
    def to_sql(self) -> Tuple[str, List[Any]]: ...
    def clone(self) -> QueryBuilder: ...
    async def exists(self) -> bool: ...
    async def doesnt_exist(self) -> bool: ...
```

### 2.2 Expression Classes
```python
@dataclass
class WhereClause:
    column: str
    operator: str
    value: Any
    boolean: str = 'and'  # 'and' or 'or'
    type: str = 'basic'   # 'basic', 'in', 'between', 'null', 'nested'

@dataclass
class JoinClause:
    table: str
    type: str  # 'inner', 'left', 'right'
    conditions: List[JoinCondition]

@dataclass
class OrderClause:
    column: str
    direction: str  # 'asc' or 'desc'
```

---

## Phase 3: Model Base Class (Week 3-4)

### 3.1 Model Metaclass
**Purpose**: Handle model metadata and query builder forwarding

```python
class ModelMeta(ModelMetaclass):
    """
    Metaclass that combines Pydantic's validation with Eloquent-style metadata.
    """
    
    def __new__(mcs, name, bases, namespace, **kwargs):
        # Extract Pyloquent-specific metadata from class definition
        # - __table__: explicit table name
        # - __fillable__: mass-assignable fields
        # - __guarded__: protected from mass assignment
        # - __hidden__: hidden from serialization
        # - __casts__: type casts
        # - __timestamps__: auto-manage timestamps
        # - __connection__: connection name
        # - __primary_key__: primary key column
        
        # Auto-infer table name from class name (snake_case plural)
        # e.g., User -> users, AirTrafficController -> air_traffic_controllers
        
        # Build field mapping for relationships
        
        return super().__new__(mcs, name, bases, namespace, **kwargs)
```

### 3.2 Model Base Class
```python
class Model(BaseModel, metaclass=ModelMeta):
    """
    Eloquent-inspired Active Record model with Pydantic integration.
    """
    
    # ===== Model Configuration (class-level) =====
    __table__: ClassVar[Optional[str]] = None
    __fillable__: ClassVar[List[str]] = []
    __guarded__: ClassVar[List[str]] = ['id']
    __hidden__: ClassVar[List[str]] = []
    __casts__: ClassVar[Dict[str, str]] = {}
    __timestamps__: ClassVar[bool] = True
    __connection__: ClassVar[Optional[str]] = None
    __primary_key__: ClassVar[str] = 'id'
    
    # ===== Instance State =====
    _original: Dict[str, Any] = PrivateAttr(default_factory=dict)
    _exists: bool = PrivateAttr(default=False)
    _relations: Dict[str, Any] = PrivateAttr(default_factory=dict)
    
    # ===== Pydantic Configuration =====
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        from_attributes=True,
    )
    
    # ===== CRUD Operations =====
    async def save(self) -> Self:
        """Save the model to the database (insert or update)"""
        
    async def delete(self) -> bool:
        """Delete the model from the database"""
        
    async def refresh(self) -> Self:
        """Refresh model attributes from database"""
        
    async def fill(self, attributes: Dict[str, Any]) -> Self:
        """Fill the model with attributes (respects fillable/guarded)"""
        
    # ===== Query Scopes =====
    @classmethod
    def query(cls) -> QueryBuilder:
        """Start a new query for this model"""
        
    @classmethod
    def where(cls, *args, **kwargs) -> QueryBuilder:
        """Start a query with where clause"""
        
    @classmethod
    def all(cls) -> Coroutine[Any, Any, Collection[Self]]:
        """Get all models"""
        
    @classmethod
    def find(cls, id: Any) -> Coroutine[Any, Any, Optional[Self]]:
        """Find a model by primary key"""
        
    @classmethod
    def find_or_fail(cls, id: Any) -> Coroutine[Any, Any, Self]:
        """Find or raise ModelNotFoundException"""
        
    @classmethod
    def create(cls, attributes: Dict[str, Any]) -> Coroutine[Any, Any, Self]:
        """Create a new model instance and save to database"""
        
    @classmethod
    def first_or_create(
        cls, 
        attributes: Dict[str, Any], 
        values: Optional[Dict[str, Any]] = None
    ) -> Coroutine[Any, Any, Self]:
        """Find first matching or create new"""
        
    @classmethod
    def update_or_create(
        cls,
        attributes: Dict[str, Any],
        values: Dict[str, Any]
    ) -> Coroutine[Any, Any, Self]:
        """Update or create model"""
        
    # ===== Relationships =====
    def has_many(
        self, 
        related: Type[Model], 
        foreign_key: Optional[str] = None,
        local_key: Optional[str] = None
    ) -> HasMany:
        """Define a has-many relationship"""
        
    def belongs_to(
        self,
        related: Type[Model],
        foreign_key: Optional[str] = None,
        owner_key: Optional[str] = None
    ) -> BelongsTo:
        """Define a belongs-to relationship"""
        
    # ===== Serialization =====
    def to_dict(self, **kwargs) -> Dict[str, Any]:
        """Convert model to dictionary (respects __hidden__)"""
        
    def json(self, **kwargs) -> str:
        """Convert model to JSON"""
        
    # ===== Dirty Tracking =====
    def is_dirty(self, key: Optional[str] = None) -> bool:
        """Check if model has unsaved changes"""
        
    def is_clean(self, key: Optional[str] = None) -> bool:
        """Check if model has no unsaved changes"""
        
    def was_changed(self, key: Optional[str] = None) -> bool:
        """Check if attribute was changed in last save"""
        
    def get_original(self, key: Optional[str] = None) -> Any:
        """Get original attribute values"""
        
    # ===== Relationship Loading =====
    async def load(self, *relations: str) -> Self:
        """Eager load relations on existing model"""
        
    def set_relation(self, name: str, value: Any) -> Self:
        """Set a loaded relation"""
        
    def get_relation(self, name: str) -> Any:
        """Get a loaded relation"""
```

### 3.3 Collection Class
```python
class Collection(Generic[T], UserList):
    """
    Enhanced list for model collections with Eloquent-style helpers.
    """
    
    def __init__(self, items: List[T] = None):
        super().__init__(items or [])
    
    # ===== Accessors =====
    def first(self, callback: Optional[Callable[[T], bool]] = None) -> Optional[T]: ...
    def last(self, callback: Optional[Callable[[T], bool]] = None) -> Optional[T]: ...
    def nth(self, n: int) -> Optional[T]: ...
    
    # ===== Filtering =====
    def where(self, key: str, operator: Any, value: Any = None) -> Collection[T]: ...
    def where_in(self, key: str, values: List[Any]) -> Collection[T]: ...
    def reject(self, callback: Callable[[T], bool]) -> Collection[T]: ...
    def filter(self, callback: Callable[[T], bool]) -> Collection[T]: ...
    def unique(self, key: Optional[str] = None) -> Collection[T]: ...
    
    # ===== Sorting =====
    def sort_by(self, key: str, reverse: bool = False) -> Collection[T]: ...
    def sort_by_desc(self, key: str) -> Collection[T]: ...
    
    # ===== Transformation =====
    def pluck(self, key: str) -> List[Any]: ...
    def key_by(self, key: str) -> Dict[Any, T]: ...
    def map(self, callback: Callable[[T], Any]) -> Collection[Any]: ...
    
    # ===== Aggregates =====
    def count(self) -> int: ...
    def sum(self, key: str) -> Any: ...
    def avg(self, key: str) -> float: ...
    def max(self, key: str) -> Any: ...
    def min(self, key: str) -> Any: ...
    
    # ===== Iteration =====
    def each(self, callback: Callable[[T], None]) -> Self: ...
    def chunk(self, size: int) -> Iterator[List[T]]: ...
    
    # ===== Async Helpers =====
    async def map_async(self, callback: Callable[[T], Awaitable[Any]]) -> Collection[Any]: ...
    async def each_async(self, callback: Callable[[T], Awaitable[None]]) -> Self: ...
```

---

## Phase 4: Query Execution (Week 4)

### 4.1 Result Hydration
```python
class Hydrator:
    """Hydrates database results into model instances"""
    
    def hydrate(
        self,
        results: List[Dict[str, Any]],
        model_class: Type[Model]
    ) -> Collection[Model]:
        """Convert raw database results to model instances"""
        
    def hydrate_one(
        self,
        result: Dict[str, Any],
        model_class: Type[Model]
    ) -> Model:
        """Convert single database result to model instance"""
```

### 4.2 Eager Loading
```python
class RelationLoader:
    """Handles eager loading of relationships to avoid N+1"""
    
    async def eager_load_relations(
        self,
        models: Collection[Model],
        relations: List[str]
    ) -> Collection[Model]:
        """Load specified relations for all models in collection"""
        
    async def load_relation(
        self,
        models: Collection[Model],
        relation: str
    ) -> None:
        """Load a single relation for all models"""
```

---

## Phase 5: Basic Relationships (Week 4-5)

### 5.1 Relation Base Class
```python
class Relation(ABC, Generic[T]):
    """Base class for all relations"""
    
    def __init__(
        self,
        parent: Model,
        related: Type[Model],
        foreign_key: str,
        local_key: str
    ):
        self.parent = parent
        self.related = related
        self.foreign_key = foreign_key
        self.local_key = local_key
        self.query: Optional[QueryBuilder] = None
    
    @abstractmethod
    def add_constraints(self) -> None:
        """Add base constraints to query"""
        
    @abstractmethod
    async def get_results(self) -> Any:
        """Get relation results"""
        
    def get_query(self) -> QueryBuilder:
        """Get the query builder instance"""
        
    async def get(self) -> Collection[T]:
        """Execute query and get results"""
```

### 5.2 HasMany Relation
```python
class HasMany(Relation[T]):
    """One-to-many relationship"""
    
    def __init__(
        self,
        parent: Model,
        related: Type[Model],
        foreign_key: str,
        local_key: str
    ):
        super().__init__(parent, related, foreign_key, local_key)
    
    def add_constraints(self) -> None:
        """Add constraints: WHERE foreign_key = parent.local_key"""
        self.query = self.related.query().where(
            self.foreign_key, 
            getattr(self.parent, self.local_key)
        )
    
    async def get_results(self) -> Collection[T]:
        return await self.query.get()
    
    async def create(self, attributes: Dict[str, Any]) -> T:
        """Create related model"""
        attributes[self.foreign_key] = getattr(self.parent, self.local_key)
        return await self.related.create(attributes)
    
    async def save(self, model: T) -> T:
        """Save existing model with foreign key set"""
        setattr(model, self.foreign_key, getattr(self.parent, self.local_key))
        return await model.save()
```

### 5.3 BelongsTo Relation
```python
class BelongsTo(Relation[T]):
    """Inverse of has-many relationship"""
    
    def add_constraints(self) -> None:
        """Add constraints: WHERE local_key = parent.foreign_key"""
        self.query = self.related.query().where(
            self.local_key,
            getattr(self.parent, self.foreign_key)
        )
    
    async def get_results(self) -> Optional[T]:
        return await self.query.first()
    
    async function associate(self, model: T) -> None:
        """Associate a model with the parent"""
        setattr(self.parent, self.foreign_key, getattr(model, self.local_key))
        await self.parent.save()
```

### 5.4 Eager Loading Implementation
```python
class HasManyLoader:
    """Loader for has-many eager loading"""
    
    async function load(
        self,
        models: Collection[Model],
        relation_name: str,
        relation: HasMany
    ) -> None:
        # 1. Get all local keys from parent models
        keys = models.pluck(relation.local_key)
        
        # 2. Execute single query: WHERE foreign_key IN (keys)
        related_models = await relation.related.query() \
            .where_in(relation.foreign_key, keys) \
            .get()
        
        # 3. Group related models by foreign key
        dictionary = {}
        for related in related_models:
            key = getattr(related, relation.foreign_key)
            if key not in dictionary:
                dictionary[key] = Collection()
            dictionary[key].append(related)
        
        # 4. Match and set relations on parent models
        for model in models:
            key = getattr(model, relation.local_key)
            matches = dictionary.get(key, Collection())
            model.set_relation(relation_name, matches)
```

---

## Phase 6: Testing & Quality (Week 5-6)

### 6.1 Testing Strategy

**Unit Tests** (Grammar & QueryBuilder):
```python
# tests/unit/test_grammar.py
def test_basic_select_compilation():
    grammar = SQLiteGrammar()
    builder = QueryBuilder(grammar).from_('users')
    sql, bindings = builder.to_sql()
    assert sql == 'SELECT * FROM "users"'
    assert bindings == []

def test_where_clause_compilation():
    grammar = SQLiteGrammar()
    builder = QueryBuilder(grammar) \
        .from_('users') \
        .where('id', '=', 1) \
        .where('active', True)
    sql, bindings = builder.to_sql()
    assert sql == 'SELECT * FROM "users" WHERE "id" = ? AND "active" = ?'
    assert bindings == [1, True]

def test_join_compilation():
    grammar = SQLiteGrammar()
    builder = QueryBuilder(grammar) \
        .from_('users') \
        .join('posts', 'users.id', '=', 'posts.user_id')
    sql, bindings = builder.to_sql()
    assert 'JOIN "posts" ON "users"."id" = "posts"."user_id"' in sql
```

**Integration Tests** (Real database):
```python
# tests/integration/test_database.py
@pytest.mark.asyncio
async def test_model_crud(db):
    # Create
    user = await User.create({'name': 'John', 'email': 'john@example.com'})
    assert user.id is not None
    
    # Read
    found = await User.find(user.id)
    assert found.name == 'John'
    
    # Update
    found.name = 'Jane'
    await found.save()
    refreshed = await User.find(user.id)
    assert refreshed.name == 'Jane'
    
    # Delete
    await found.delete()
    deleted = await User.find(user.id)
    assert deleted is None
```

### 6.2 Test Fixtures
```python
# tests/conftest.py
import pytest
import pytest_asyncio

@pytest_asyncio.fixture
async def sqlite_db():
    """Create in-memory SQLite database for testing"""
    from pyloquent import ConnectionManager
    
    manager = ConnectionManager()
    manager.add_connection('default', {
        'driver': 'sqlite',
        'database': ':memory:'
    })
    await manager.connect()
    yield manager
    await manager.disconnect()

@pytest_asyncio.fixture
async def setup_tables(sqlite_db):
    """Create test tables"""
    conn = sqlite_db.connection()
    await conn.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    await conn.execute('''
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
```

### 6.3 Quality Checks
- **mypy**: Type checking with strict mode
- **ruff**: Linting and formatting
- **pytest**: Test coverage > 80%
- **pre-commit**: Automated checks on commit

---

## Phase 7: Advanced Features (Post v0.1.0)

### 7.1 Mass Assignment Protection
```python
class User(Model):
    __fillable__ = ['name', 'email']  # Only these can be mass assigned
    # OR
    __guarded__ = ['id', 'is_admin']  # These cannot be mass assigned
    
# Usage
user = User.create(request.data)  # Only fillable fields used
```

### 7.2 Query Scopes
```python
class Post(Model):
    @scope
    def published(self, query):
        return query.where('status', 'published')
    
    @scope
    def recent(self, query, days=7):
        return query.where('created_at', '>', datetime.now() - timedelta(days=days))

# Usage
posts = await Post.published().recent(30).get()
```

### 7.3 Soft Deletes
```python
class User(Model, SoftDeletes):
    # Adds deleted_at column
    pass

# Automatically excludes soft-deleted records
users = await User.all()  # Only non-deleted

# Include soft-deleted
all_users = await User.with_trashed().all()

# Only soft-deleted
trashed = await User.only_trashed().all()

# Restore
await user.restore()

# Force delete (permanent)
await user.force_delete()
```

### 7.4 Attribute Casting
```python
class User(Model):
    __casts__ = {
        'is_admin': 'bool',
        'settings': 'json',
        'birth_date': 'date',
        'balance': 'decimal:2'
    }
```

### 7.5 Events/Observers
```python
class User(Model):
    async def saving(self):
        # Before save (create or update)
        self.email = self.email.lower()
    
    async function saved(self):
        # After save
        await cache.delete(f'user:{self.id}')
    
    async function creating(self):
        # Before create only
        self.uuid = str(uuid.uuid4())
    
    async function created(self):
        # After create only
        await EventBus.dispatch('user.created', self)
    
    async function deleting(self):
        # Before delete
        if self.has_posts():
            raise Exception("Cannot delete user with posts")
```

---

## API Examples (Target Usage)

### Basic CRUD
```python
from pyloquent import Model
from pydantic import EmailStr

class User(Model):
    __table__ = 'users'
    __fillable__ = ['name', 'email']
    
    id: int | None = None
    name: str
    email: EmailStr

# Create
user = await User.create({'name': 'John', 'email': 'john@example.com'})

# Read
user = await User.find(1)
user = await User.where('email', 'john@example.com').first()
users = await User.where('active', True).order_by('name').get()

# Update
user.name = 'Jane'
await user.save()
# Or mass update
await User.where('active', False).update({'active': True})

# Delete
await user.delete()
# Or mass delete
await User.where('last_login', '<', '2023-01-01').delete()
```

### Query Builder
```python
# Chaining
users = await User.where('active', True) \
    .where_in('role', ['admin', 'moderator']) \
    .where_not_null('verified_at') \
    .order_by('created_at', 'desc') \
    .limit(10) \
    .get()

# Aggregates
count = await User.where('active', True).count()
max_age = await User.max('age')
avg_salary = await User.where('department', 'engineering').avg('salary')

# Joins
users = await User.join('posts', 'users.id', '=', 'posts.user_id') \
    .where('posts.published', True) \
    .select('users.*') \
    .distinct() \
    .get()
```

### Relationships
```python
class User(Model):
    def posts(self):
        return self.has_many(Post)
    
    def recent_posts(self):
        return self.has_many(Post).where('created_at', '>', '2024-01-01')

class Post(Model):
    def author(self):
        return self.belongs_to(User)
    
    def comments(self):
        return self.has_many(Comment)

# Usage
user = await User.with_('posts').find(1)
for post in user.posts:
    print(post.title)

# Lazy loading
user = await User.find(1)
posts = await user.posts().get()  # Explicit async load
await user.load('posts', 'profile')  # Load multiple relations
print(user.posts)  # Now available sync
```

### FastAPI Integration
```python
from fastapi import FastAPI
from pyloquent import ConnectionManager

app = FastAPI()
manager = ConnectionManager()

@app.on_event('startup')
async def startup():
    manager.add_connection('default', {
        'driver': 'postgres',
        'host': 'localhost',
        'database': 'myapp',
        'user': 'user',
        'password': 'pass'
    })
    await manager.connect()

@app.on_event('shutdown')
async def shutdown():
    await manager.disconnect()

@app.get('/users', response_model=List[User])
async def list_users():
    return await User.all()

@app.post('/users', response_model=User)
async function create_user(data: User):
    return await User.create(data.model_dump())

@app.get('/users/{user_id}', response_model=User)
async def get_user(user_id: int):
    return await User.find_or_fail(user_id)
```

---

## Migration Path (Future Versions)

### v0.2.0
- D1 HTTP API support
- Basic migration system
- More relationship types (hasOne, belongsToMany)
- Query scopes
- Mass assignment protection

### v0.3.0
- D1 Worker binding support
- CLI tool (pyloquent-cli)
- Model factories/seeders
- Collection enhancements
- More aggregate functions

### v0.4.0
- Soft deletes
- Attribute casting
- Model observers/events
- Polymorphic relationships

### v0.5.0+
- Query caching
- Full-text search helpers
- Performance optimizations
- Advanced eager loading strategies
- Subquery support

---

## Success Criteria

**v0.1.0 is successful when:**
1. ✅ QueryBuilder compiles correct SQL for SQLite/PostgreSQL/MySQL
2. ✅ Model CRUD operations work with all three databases
3. ✅ Basic relationships (hasMany, belongsTo) work with eager loading
4. ✅ All code is type-annotated and passes mypy strict mode
5. ✅ Unit tests cover all public APIs with >80% coverage
6. ✅ Integration tests pass against real databases
7. ✅ FastAPI integration example works end-to-end
8. ✅ Documentation with usage examples is complete

---

## Notes on Eloquent Compatibility

**What We're Keeping:**
- Method names and patterns (where, order_by, has_many, etc.)
- Mass assignment protection (fillable/guarded)
- Fluent query builder API
- Eager loading syntax (`with_()`)
- Collection helpers

**What We're Adapting:**
- Properties for relationships need explicit `await` in Python (vs PHP's implicit)
- Using Pydantic for validation/serialization instead of Eloquent's casting
- Async-first design (Python's async/await vs PHP's synchronous)
- Type annotations throughout (Python's advantage)

**What's Different:**
- No magic methods (__get, __set) - Pydantic handles attributes
- Explicit relation loading due to Python's async constraints
- Grammar-based SQL compilation for better testing
- Connection manager integrates with FastAPI lifespan
