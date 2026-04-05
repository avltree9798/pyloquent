"""Integration tests for Model classmethod query proxies."""
import pytest
from typing import Optional
from pyloquent import Model


class CmUser(Model):
    __table__ = "cm_users"
    __fillable__ = ["name", "score", "active"]
    id: Optional[int] = None
    name: str
    score: Optional[int] = 0
    active: Optional[bool] = True

    def posts(self):
        return self.has_many(CmPost, foreign_key="user_id")


class CmPost(Model):
    __table__ = "cm_posts"
    __fillable__ = ["title", "user_id", "published"]
    id: Optional[int] = None
    title: str
    user_id: Optional[int] = None
    published: Optional[bool] = False

    def author(self):
        return self.belongs_to(CmUser, foreign_key="user_id", owner_key="id")


@pytest.fixture
async def cm_tables(sqlite_db):
    conn = sqlite_db.connection()
    await conn.execute("""
        CREATE TABLE cm_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            score INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    await conn.execute("""
        CREATE TABLE cm_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            user_id INTEGER,
            published INTEGER DEFAULT 0,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    yield


# ---------------------------------------------------------------------------
# select / select_raw / distinct
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_select_proxy(sqlite_db, cm_tables):
    await CmUser.create({"name": "Alice", "score": 10})
    results = await CmUser.select("name", "score").get()
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_select_raw_proxy(sqlite_db, cm_tables):
    await CmUser.create({"name": "Bob"})
    results = await CmUser.select_raw("name").get()
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_distinct_proxy(sqlite_db, cm_tables):
    await CmUser.create({"name": "Carol"})
    await CmUser.create({"name": "Carol"})
    results = await CmUser.select("name").distinct().get()
    names = [r.name for r in results]
    assert names.count("Carol") == 1


# ---------------------------------------------------------------------------
# join / left_join
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_join_proxy(sqlite_db, cm_tables):
    u = await CmUser.create({"name": "Dave"})
    await CmPost.create({"title": "JP", "user_id": u.id})
    results = await CmUser.join(
        "cm_posts", "cm_users.id", "=", "cm_posts.user_id"
    ).select_raw("cm_users.name, cm_posts.title").get()
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_left_join_proxy(sqlite_db, cm_tables):
    await CmUser.create({"name": "Eve"})
    results = await CmUser.left_join(
        "cm_posts", "cm_users.id", "=", "cm_posts.user_id"
    ).get()
    assert len(results) >= 1


# ---------------------------------------------------------------------------
# group_by / having
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_group_by_proxy(sqlite_db, cm_tables):
    await CmUser.create({"name": "Frank", "score": 5})
    await CmUser.create({"name": "Frank", "score": 5})
    results = await CmUser.select_raw("name, COUNT(*) as cnt").group_by("name").get()
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_having_proxy(sqlite_db, cm_tables):
    await CmUser.create({"name": "Gina", "score": 5})
    results = await CmUser.select_raw("name, COUNT(*) as cnt").group_by("name").having("cnt", ">=", 1).get()
    assert len(results) >= 1


# ---------------------------------------------------------------------------
# where_null / where_not_null
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_where_null_proxy(sqlite_db, cm_tables):
    await CmPost.create({"title": "NullUser"})
    results = await CmPost.where_null("user_id").get()
    assert any(p.title == "NullUser" for p in results)


@pytest.mark.asyncio
async def test_where_not_null_proxy(sqlite_db, cm_tables):
    u = await CmUser.create({"name": "Hal"})
    await CmPost.create({"title": "HasUser", "user_id": u.id})
    results = await CmPost.where_not_null("user_id").get()
    assert any(p.title == "HasUser" for p in results)


# ---------------------------------------------------------------------------
# where_between / where_not_between
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_where_between_proxy(sqlite_db, cm_tables):
    await CmUser.create({"name": "Iris", "score": 50})
    results = await CmUser.where_between("score", [10, 100]).get()
    assert any(u.name == "Iris" for u in results)


@pytest.mark.asyncio
async def test_where_not_between_proxy(sqlite_db, cm_tables):
    await CmUser.create({"name": "Jack", "score": 200})
    results = await CmUser.where_not_between("score", [10, 100]).get()
    assert any(u.name == "Jack" for u in results)


# ---------------------------------------------------------------------------
# or_where / where_raw / where_column
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_or_where_proxy(sqlite_db, cm_tables):
    await CmUser.create({"name": "Kim"})
    await CmUser.create({"name": "Leo"})
    results = await CmUser.where("name", "Kim").or_where("name", "Leo").get()
    names = {u.name for u in results}
    assert "Kim" in names and "Leo" in names


@pytest.mark.asyncio
async def test_where_raw_proxy(sqlite_db, cm_tables):
    await CmUser.create({"name": "Mia", "score": 99})
    results = await CmUser.where_raw("score = ?", [99]).get()
    assert any(u.name == "Mia" for u in results)


@pytest.mark.asyncio
async def test_where_column_proxy(sqlite_db, cm_tables):
    await CmPost.create({"title": "WC", "user_id": 1, "published": False})
    qb = CmPost.where_column("user_id", "=", "id")
    sql, _ = qb.to_sql()
    assert "user_id" in sql


# ---------------------------------------------------------------------------
# latest / oldest
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_latest_proxy(sqlite_db, cm_tables):
    await CmUser.create({"name": "Ned"})
    qb = CmUser.latest()
    sql, _ = qb.to_sql()
    assert "DESC" in sql.upper()


@pytest.mark.asyncio
async def test_oldest_proxy(sqlite_db, cm_tables):
    await CmUser.create({"name": "Ora"})
    qb = CmUser.oldest()
    sql, _ = qb.to_sql()
    assert "ASC" in sql.upper()


# ---------------------------------------------------------------------------
# has / doesnt_have / where_has / with_count (class proxies)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_has_proxy(sqlite_db, cm_tables):
    u = await CmUser.create({"name": "Pat"})
    await CmPost.create({"title": "Post", "user_id": u.id})
    results = await CmUser.has("posts").get()
    assert any(r.name == "Pat" for r in results)


@pytest.mark.asyncio
async def test_doesnt_have_proxy(sqlite_db, cm_tables):
    await CmUser.create({"name": "Quinn"})
    results = await CmUser.doesnt_have("posts").get()
    assert any(r.name == "Quinn" for r in results)


@pytest.mark.asyncio
async def test_where_has_proxy(sqlite_db, cm_tables):
    u = await CmUser.create({"name": "Rob"})
    await CmPost.create({"title": "Pub", "user_id": u.id, "published": True})
    results = await CmUser.where_has(
        "posts", lambda q: q.where("published", True)
    ).get()
    assert any(r.name == "Rob" for r in results)


@pytest.mark.asyncio
async def test_with_count_proxy(sqlite_db, cm_tables):
    u = await CmUser.create({"name": "Sue"})
    await CmPost.create({"title": "C1", "user_id": u.id})
    await CmPost.create({"title": "C2", "user_id": u.id})
    results = await CmUser.with_count("posts").where("id", u.id).get()
    assert getattr(results[0], "posts_count") == 2


# ---------------------------------------------------------------------------
# where_in / where_not_in
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_where_in_proxy(sqlite_db, cm_tables):
    u1 = await CmUser.create({"name": "Tim"})
    u2 = await CmUser.create({"name": "Uma"})
    u3 = await CmUser.create({"name": "Val"})
    results = await CmUser.where_in("id", [u1.id, u3.id]).get()
    names = {u.name for u in results}
    assert "Tim" in names and "Val" in names and "Uma" not in names


# ---------------------------------------------------------------------------
# value proxy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_value_proxy(sqlite_db, cm_tables):
    await CmUser.create({"name": "Walt"})
    name = await CmUser.order_by("id").value("name")
    assert name == "Walt"


# ---------------------------------------------------------------------------
# exists / doesnt_exist proxies
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_exists_proxy(sqlite_db, cm_tables):
    assert not await CmUser.where("name", "NONEXISTENT_XYZ").exists()
    await CmUser.create({"name": "NONEXISTENT_XYZ"})
    assert await CmUser.where("name", "NONEXISTENT_XYZ").exists()
