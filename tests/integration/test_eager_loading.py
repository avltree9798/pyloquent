"""Integration tests for eager loading (with_) and chunk_by_id."""
import pytest
from typing import Optional
from pyloquent import Model


class ElUser(Model):
    __table__ = "el_users"
    __fillable__ = ["name"]
    id: Optional[int] = None
    name: str

    def posts(self):
        return self.has_many(ElPost, foreign_key="user_id")


class ElPost(Model):
    __table__ = "el_posts"
    __fillable__ = ["title", "user_id"]
    id: Optional[int] = None
    title: str
    user_id: Optional[int] = None


@pytest.fixture
async def el_tables(sqlite_db):
    conn = sqlite_db.connection()
    await conn.execute("""
        CREATE TABLE el_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    await conn.execute("""
        CREATE TABLE el_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            user_id INTEGER,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    yield


# ---------------------------------------------------------------------------
# with_() eager loading
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_with_eager_loads_relation(sqlite_db, el_tables):
    u = await ElUser.create({"name": "Alice"})
    await ElPost.create({"title": "P1", "user_id": u.id})
    await ElPost.create({"title": "P2", "user_id": u.id})

    users = await ElUser.query.with_("posts").where("id", u.id).get()
    assert len(users) == 1
    assert "posts" in users[0]._relations
    assert len(users[0]._relations["posts"]) == 2


@pytest.mark.asyncio
async def test_with_eager_loads_empty_relation(sqlite_db, el_tables):
    u = await ElUser.create({"name": "Bob"})
    users = await ElUser.query.with_("posts").where("id", u.id).get()
    assert "posts" in users[0]._relations
    assert len(users[0]._relations["posts"]) == 0


@pytest.mark.asyncio
async def test_with_missing_relation_raises(sqlite_db, el_tables):
    await ElUser.create({"name": "Carol"})
    from pyloquent.exceptions import RelationNotFoundException
    with pytest.raises(RelationNotFoundException):
        await ElUser.query.with_("nonexistent").get()


# ---------------------------------------------------------------------------
# chunk_by_id
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chunk_by_id_yields_all(sqlite_db, el_tables):
    for i in range(5):
        await ElUser.create({"name": f"User{i}"})

    collected = []
    async for chunk in ElUser.query.chunk_by_id(2):
        collected.extend(chunk)

    assert len(collected) == 5


@pytest.mark.asyncio
async def test_chunk_by_id_chunk_size(sqlite_db, el_tables):
    for i in range(6):
        await ElUser.create({"name": f"CU{i}"})

    chunk_sizes = []
    async for chunk in ElUser.query.chunk_by_id(2):
        chunk_sizes.append(len(chunk))

    assert max(chunk_sizes) <= 2
    assert sum(chunk_sizes) == 6


@pytest.mark.asyncio
async def test_chunk_by_id_empty_table(sqlite_db, el_tables):
    chunks = []
    async for chunk in ElUser.query.chunk_by_id(10):
        chunks.append(chunk)
    assert chunks == []
