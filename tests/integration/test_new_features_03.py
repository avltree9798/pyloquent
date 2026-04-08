"""Integration tests for Pyloquent 0.3.0 new features.

Uses in-memory SQLite via the sqlite_db fixture.
"""

from typing import Optional, List
import pytest
import pytest_asyncio

from pydantic import PrivateAttr
from pyloquent.orm.model import Model
from pyloquent.orm.identity_map import IdentityMap


# ---------------------------------------------------------------------------
# Model definitions
# ---------------------------------------------------------------------------

class Product(Model):
    __table__ = "products"
    __fillable__ = ["name", "category", "price", "metadata", "tags", "active"]
    __timestamps__ = False
    __casts__ = {"metadata": "json", "tags": "comma_separated"}

    id: Optional[int] = None
    name: str
    category: str = "general"
    price: float = 0.0
    metadata: Optional[dict] = None
    tags: Optional[List] = None
    active: bool = True


class Animal(Model):
    """Base STI model stored in a single 'animals' table."""
    __table__ = "animals"
    __fillable__ = ["name", "type"]
    __timestamps__ = False

    id: Optional[int] = None
    name: str
    type: str = "animal"


class Dog(Animal):
    __discriminator__ = "type"
    __discriminator_value__ = "dog"


class Cat(Animal):
    __discriminator__ = "type"
    __discriminator_value__ = "cat"


class OrderItem(Model):
    """Model with composite primary key."""
    __table__ = "order_items"
    __primary_key__ = ["order_id", "product_id"]
    __incrementing__ = False
    __fillable__ = ["order_id", "product_id", "quantity"]
    __timestamps__ = False

    order_id: int
    product_id: int
    quantity: int = 1


class Post(Model):
    __table__ = "posts_03"
    __fillable__ = ["user_id", "title", "status"]
    __timestamps__ = False

    id: Optional[int] = None
    user_id: Optional[int] = None
    title: str
    status: str = "draft"


class UserSimple(Model):
    __table__ = "users_03"
    __fillable__ = ["name", "email"]
    __timestamps__ = False

    id: Optional[int] = None
    name: str
    email: str


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def products_table(sqlite_db):
    conn = sqlite_db.connection()
    await conn.execute("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            price REAL DEFAULT 0.0,
            metadata TEXT,
            tags TEXT,
            active INTEGER DEFAULT 1
        )
    """)
    yield
    await conn.execute("DROP TABLE IF EXISTS products")


@pytest_asyncio.fixture
async def animals_table(sqlite_db):
    conn = sqlite_db.connection()
    await conn.execute("""
        CREATE TABLE animals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT 'animal'
        )
    """)
    await conn.execute("INSERT INTO animals (name, type) VALUES ('Rex', 'dog')")
    await conn.execute("INSERT INTO animals (name, type) VALUES ('Whiskers', 'cat')")
    await conn.execute("INSERT INTO animals (name, type) VALUES ('Unknown', 'animal')")
    await sqlite_db.connection()._connection.commit()
    yield
    await conn.execute("DROP TABLE IF EXISTS animals")


@pytest_asyncio.fixture
async def order_items_table(sqlite_db):
    conn = sqlite_db.connection()
    await conn.execute("""
        CREATE TABLE order_items (
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER DEFAULT 1,
            PRIMARY KEY (order_id, product_id)
        )
    """)
    yield
    await conn.execute("DROP TABLE IF EXISTS order_items")


@pytest_asyncio.fixture
async def posts_users_table(sqlite_db):
    conn = sqlite_db.connection()
    await conn.execute("""
        CREATE TABLE users_03 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL
        )
    """)
    await conn.execute("""
        CREATE TABLE posts_03 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT NOT NULL,
            status TEXT DEFAULT 'draft'
        )
    """)
    yield
    await conn.execute("DROP TABLE IF EXISTS posts_03")
    await conn.execute("DROP TABLE IF EXISTS users_03")


# ---------------------------------------------------------------------------
# Batch insert
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_insert_multiple_rows(sqlite_db, products_table):
    rows = [
        {"name": "Widget A", "category": "tools", "price": 9.99},
        {"name": "Widget B", "category": "tools", "price": 19.99},
        {"name": "Gadget C", "category": "gadgets", "price": 49.99},
    ]
    result = await Product.query.insert(rows)
    assert result is True

    count = await Product.query.count()
    assert count == 3


@pytest.mark.asyncio
async def test_batch_insert_single_row_uses_execute(sqlite_db, products_table):
    result = await Product.query.insert({"name": "Solo", "price": 1.0})
    assert result is True
    assert await Product.query.count() == 1


# ---------------------------------------------------------------------------
# TypeDecorator integration (JSON + comma_separated casts)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_json_cast_roundtrip(sqlite_db, products_table):
    p = await Product.create({"name": "JSON Product", "metadata": {"color": "blue", "size": "M"}})
    assert p.id is not None

    fresh = await Product.query.find(p.id)
    assert fresh is not None
    assert fresh.metadata == {"color": "blue", "size": "M"}


@pytest.mark.asyncio
async def test_comma_separated_cast_roundtrip(sqlite_db, products_table):
    p = await Product.create({"name": "Tagged", "tags": ["python", "orm", "async"]})
    fresh = await Product.query.find(p.id)
    assert fresh is not None
    assert fresh.tags == ["python", "orm", "async"]


# ---------------------------------------------------------------------------
# Composite primary keys
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_composite_pk_save_and_delete(sqlite_db, order_items_table):
    item = OrderItem(order_id=1, product_id=10, quantity=3)
    await item.save()

    # Retrieve it
    found = await OrderItem.query.where("order_id", 1).where("product_id", 10).first()
    assert found is not None
    assert found.quantity == 3

    # Delete using composite PK
    await found.delete()
    gone = await OrderItem.query.where("order_id", 1).where("product_id", 10).first()
    assert gone is None


@pytest.mark.asyncio
async def test_composite_pk_get_key(sqlite_db, order_items_table):
    item = OrderItem(order_id=2, product_id=20, quantity=5)
    await item.save()

    key = item._get_key()
    assert isinstance(key, dict)
    assert key["order_id"] == 2
    assert key["product_id"] == 20


# ---------------------------------------------------------------------------
# Single Table Inheritance (STI)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sti_dog_query_scoped(sqlite_db, animals_table):
    dogs = await Dog.query.get()
    assert all(d.type == "dog" for d in dogs)
    assert len(dogs) == 1
    assert dogs[0].name == "Rex"


@pytest.mark.asyncio
async def test_sti_cat_query_scoped(sqlite_db, animals_table):
    cats = await Cat.query.get()
    assert len(cats) == 1
    assert cats[0].name == "Whiskers"


@pytest.mark.asyncio
async def test_sti_base_query_returns_all(sqlite_db, animals_table):
    all_animals = await Animal.query.get()
    assert len(all_animals) == 3


# ---------------------------------------------------------------------------
# Identity map
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_identity_map_returns_same_object(sqlite_db, posts_users_table):
    u = await UserSimple.create({"name": "Alice", "email": "alice@test.com"})

    imap = IdentityMap()
    r1 = await UserSimple.query.with_identity_map(imap).where("id", u.id).first()
    r2 = await UserSimple.query.with_identity_map(imap).where("id", u.id).first()

    assert r1 is r2


@pytest.mark.asyncio
async def test_identity_map_session_context(sqlite_db, posts_users_table):
    u = await UserSimple.create({"name": "Bob", "email": "bob@test.com"})

    async with IdentityMap.session() as imap:
        r1 = await UserSimple.query.with_identity_map(imap).find(u.id)
        r2 = await UserSimple.query.with_identity_map(imap).find(u.id)
        assert r1 is r2
        assert len(imap) >= 1

    assert len(imap) == 0


# ---------------------------------------------------------------------------
# join_sub (subquery join)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_join_sub_returns_results(sqlite_db, posts_users_table):
    u = await UserSimple.create({"name": "Carol", "email": "carol@test.com"})
    await Post.create({"user_id": u.id, "title": "Hello", "status": "published"})
    await Post.create({"user_id": u.id, "title": "World", "status": "draft"})

    conn = sqlite_db.connection()
    from pyloquent.query.builder import QueryBuilder

    results = await (
        QueryBuilder(conn.grammar, conn)
        .from_("users_03")
        .select("users_03.name")
        .join_sub(
            lambda q: q.from_("posts_03").select("user_id").where("status", "published"),
            alias="pub",
            first="users_03.id",
            operator="=",
            second="pub.user_id",
        )
        .get()
    )
    assert len(results) == 1


# ---------------------------------------------------------------------------
# join_raw
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_join_raw(sqlite_db, posts_users_table):
    u = await UserSimple.create({"name": "Dave", "email": "dave@test.com"})
    await Post.create({"user_id": u.id, "title": "Raw Join Post", "status": "published"})

    conn = sqlite_db.connection()
    from pyloquent.query.builder import QueryBuilder

    results = await (
        QueryBuilder(conn.grammar, conn)
        .from_("users_03")
        .select("users_03.name", "posts_03.title")
        .join_raw("INNER JOIN posts_03 ON posts_03.user_id = users_03.id")
        .get()
    )
    assert len(results) >= 1


# ---------------------------------------------------------------------------
# CTEs in live queries
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cte_live_query(sqlite_db, posts_users_table):
    u = await UserSimple.create({"name": "Eve", "email": "eve@test.com"})
    await Post.create({"user_id": u.id, "title": "CTE Post", "status": "published"})

    conn = sqlite_db.connection()
    from pyloquent.query.builder import QueryBuilder

    results = await (
        QueryBuilder(conn.grammar, conn)
        .with_cte(
            "published_posts",
            lambda q: q.from_("posts_03").where("status", "published"),
        )
        .from_("published_posts")
        .get()
    )
    assert len(results) >= 1
    assert all(r["status"] == "published" for r in results)


# ---------------------------------------------------------------------------
# Window functions in live queries
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_window_function_live_query(sqlite_db, products_table):
    await Product.query.insert([
        {"name": "A", "category": "x", "price": 10.0},
        {"name": "B", "category": "x", "price": 20.0},
        {"name": "C", "category": "x", "price": 30.0},
    ])

    conn = sqlite_db.connection()
    from pyloquent.query.builder import QueryBuilder

    results = await (
        QueryBuilder(conn.grammar, conn)
        .from_("products")
        .select("name", "price")
        .select_window("ROW_NUMBER", order_by=["price"], alias="row_num")
        .get()
    )
    row_nums = [r["row_num"] for r in results]
    assert row_nums == sorted(row_nums)
