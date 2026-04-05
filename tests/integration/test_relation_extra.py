"""Integration tests for uncovered Relation base methods and HasManyThrough.create."""
import pytest
from typing import Optional
from pyloquent import Model
from pyloquent.orm.collection import Collection


class ReUser(Model):
    __table__ = "re_users"
    __fillable__ = ["name", "country_id"]
    id: Optional[int] = None
    name: Optional[str] = None
    country_id: Optional[int] = None

    def posts(self):
        return self.has_many(RePost, foreign_key="user_id")

    def tags(self):
        return self.belongs_to_many(ReTag, "re_user_tags", foreign_key="user_id", related_key="tag_id")


class RePost(Model):
    __table__ = "re_posts"
    __fillable__ = ["title", "user_id"]
    id: Optional[int] = None
    title: str
    user_id: Optional[int] = None


class ReTag(Model):
    __table__ = "re_tags"
    __fillable__ = ["label"]
    id: Optional[int] = None
    label: str


class ReCountry(Model):
    __table__ = "re_countries"
    __fillable__ = ["name"]
    id: Optional[int] = None
    name: str

    def posts(self):
        return self.has_many_through(
            RePost, ReUser,
            first_key="country_id", second_key="user_id",
            local_key="id", second_local_key="id",
        )


@pytest.fixture
async def re_tables(sqlite_db):
    conn = sqlite_db.connection()
    await conn.execute("""
        CREATE TABLE re_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, country_id INTEGER,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    await conn.execute("""
        CREATE TABLE re_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT, user_id INTEGER,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    await conn.execute("""
        CREATE TABLE re_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    await conn.execute("""
        CREATE TABLE re_user_tags (
            user_id INTEGER, tag_id INTEGER
        )
    """)
    await conn.execute("""
        CREATE TABLE re_countries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    yield


# ---------------------------------------------------------------------------
# Relation.first()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_relation_first(sqlite_db, re_tables):
    u = await ReUser.create({"name": "RelFirst"})
    await RePost.create({"title": "P1", "user_id": u.id})
    await RePost.create({"title": "P2", "user_id": u.id})
    first = await u.posts().first()
    assert first is not None
    assert first.user_id == u.id


# ---------------------------------------------------------------------------
# Relation.where()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_relation_where(sqlite_db, re_tables):
    u = await ReUser.create({"name": "RelWhere"})
    await RePost.create({"title": "Match", "user_id": u.id})
    await RePost.create({"title": "NoMatch", "user_id": u.id})
    results = await u.posts().where("title", "Match").get()
    assert len(results) == 1
    assert results[0].title == "Match"


# ---------------------------------------------------------------------------
# Relation.chunk()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_relation_chunk(sqlite_db, re_tables):
    u = await ReUser.create({"name": "RelChunk"})
    for i in range(5):
        await RePost.create({"title": f"Post{i}", "user_id": u.id})
    chunks = []
    async for chunk in u.posts().chunk(2):
        chunks.append(chunk)
    total = sum(len(c) for c in chunks)
    assert total == 5


# ---------------------------------------------------------------------------
# Relation.__call__() — used by model.load()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_relation_callable(sqlite_db, re_tables):
    u = await ReUser.create({"name": "RelCall"})
    await RePost.create({"title": "CP", "user_id": u.id})
    rel = u.posts()
    qb = rel()
    results = await qb.get()
    assert len(results) == 1


# ---------------------------------------------------------------------------
# Relation.order_by() and limit()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_relation_order_by_and_limit(sqlite_db, re_tables):
    u = await ReUser.create({"name": "RelOrd"})
    for i in range(4):
        await RePost.create({"title": f"OrdP{i}", "user_id": u.id})
    results = await u.posts().order_by("title", "desc").limit(2).get()
    assert len(results) == 2


# ---------------------------------------------------------------------------
# HasManyThrough.create()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_has_many_through_create(sqlite_db, re_tables):
    c = await ReCountry.create({"name": "UK"})
    post = await c.posts().create({"title": "ThroughPost"})
    assert post is not None
    assert post.title == "ThroughPost"
    all_posts = await c.posts().get()
    assert any(p.title == "ThroughPost" for p in all_posts)
