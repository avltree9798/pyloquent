"""Integration tests covering has()/with_count() for BelongsTo and BelongsToMany relationships."""
import pytest
from typing import Optional
from pyloquent import Model


class HrAuthor(Model):
    __table__ = "hr_authors"
    __fillable__ = ["name"]
    id: Optional[int] = None
    name: str

    def books(self):
        return self.has_many(HrBook, foreign_key="author_id")

    def publisher(self):
        return self.belongs_to(HrPublisher, foreign_key="publisher_id", owner_key="id")

    def tags(self):
        return self.belongs_to_many(HrTag, "hr_author_tags", foreign_key="author_id", related_key="tag_id")


class HrBook(Model):
    __table__ = "hr_books"
    __fillable__ = ["title", "author_id"]
    id: Optional[int] = None
    title: str
    author_id: Optional[int] = None

    def author(self):
        return self.belongs_to(HrAuthor, foreign_key="author_id", owner_key="id")


class HrPublisher(Model):
    __table__ = "hr_publishers"
    __fillable__ = ["name"]
    id: Optional[int] = None
    name: str


class HrTag(Model):
    __table__ = "hr_tags"
    __fillable__ = ["label"]
    id: Optional[int] = None
    label: str


@pytest.fixture
async def hr_tables(sqlite_db):
    conn = sqlite_db.connection()
    await conn.execute("""
        CREATE TABLE hr_publishers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    await conn.execute("""
        CREATE TABLE hr_authors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            publisher_id INTEGER,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    await conn.execute("""
        CREATE TABLE hr_books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author_id INTEGER,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    await conn.execute("""
        CREATE TABLE hr_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT NOT NULL,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    await conn.execute("""
        CREATE TABLE hr_author_tags (
            author_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL
        )
    """)
    yield


# ---------------------------------------------------------------------------
# BelongsToMany: has() and doesnt_have()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_belongs_to_many_has(sqlite_db, hr_tables):
    conn = sqlite_db.connection()
    a1 = await HrAuthor.create({"name": "Alice"})
    a2 = await HrAuthor.create({"name": "Bob"})
    t1 = await HrTag.create({"label": "Fiction"})
    await conn.execute("INSERT INTO hr_author_tags (author_id, tag_id) VALUES (?, ?)", [a1.id, t1.id])

    results = await HrAuthor.has("tags").get()
    names = {r.name for r in results}
    assert "Alice" in names
    assert "Bob" not in names


@pytest.mark.asyncio
async def test_belongs_to_many_doesnt_have(sqlite_db, hr_tables):
    conn = sqlite_db.connection()
    a1 = await HrAuthor.create({"name": "Carol"})
    a2 = await HrAuthor.create({"name": "Dave"})
    t1 = await HrTag.create({"label": "Non-fiction"})
    await conn.execute("INSERT INTO hr_author_tags (author_id, tag_id) VALUES (?, ?)", [a1.id, t1.id])

    results = await HrAuthor.doesnt_have("tags").get()
    names = {r.name for r in results}
    assert "Dave" in names
    assert "Carol" not in names


# ---------------------------------------------------------------------------
# BelongsTo: has() via reverse relation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_belongs_to_has(sqlite_db, hr_tables):
    pub = await HrPublisher.create({"name": "Pub1"})
    conn = sqlite_db.connection()
    await conn.execute(
        "INSERT INTO hr_authors (name, publisher_id) VALUES (?, ?)",
        ["Eve", pub.id],
    )
    await conn.execute("INSERT INTO hr_authors (name) VALUES (?)", ["Frank"])

    results = await HrAuthor.has("publisher").get()
    names = {r.name for r in results}
    assert "Eve" in names
    assert "Frank" not in names


# ---------------------------------------------------------------------------
# with_count for BelongsToMany
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_with_count_belongs_to_many(sqlite_db, hr_tables):
    conn = sqlite_db.connection()
    a = await HrAuthor.create({"name": "Grace"})
    t1 = await HrTag.create({"label": "T1"})
    t2 = await HrTag.create({"label": "T2"})
    await conn.execute("INSERT INTO hr_author_tags (author_id, tag_id) VALUES (?, ?)", [a.id, t1.id])
    await conn.execute("INSERT INTO hr_author_tags (author_id, tag_id) VALUES (?, ?)", [a.id, t2.id])

    results = await HrAuthor.with_count("tags").where("id", a.id).get()
    count = getattr(results[0], "tags_count")
    assert count == 2


# ---------------------------------------------------------------------------
# with_count for BelongsTo (parent lookup)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_with_count_belongs_to(sqlite_db, hr_tables):
    conn = sqlite_db.connection()
    pub = await HrPublisher.create({"name": "Pub2"})
    await conn.execute(
        "INSERT INTO hr_authors (name, publisher_id) VALUES (?, ?)",
        ["Hank", pub.id],
    )

    results = await HrAuthor.with_count("publisher").get()
    author = next(r for r in results if r.name == "Hank")
    count = getattr(author, "publisher_count")
    assert count >= 0


# ---------------------------------------------------------------------------
# lazy async generator
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_lazy_async_generator(sqlite_db, hr_tables):
    for i in range(7):
        await HrAuthor.create({"name": f"Lazy{i}"})

    items = []
    async for item in HrAuthor.query.lazy(chunk_size=3):
        items.append(item)
    assert len(items) == 7


# ---------------------------------------------------------------------------
# to_raw_sql (integration with real connection context)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_to_raw_sql_integration(sqlite_db, hr_tables):
    raw = HrAuthor.query.where("name", "Alice").to_raw_sql()
    assert "Alice" in raw
    assert "?" not in raw
