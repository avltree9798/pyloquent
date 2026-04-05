"""Integration tests for HasMany, HasOne, BelongsTo relation helper methods."""
import pytest
from typing import Optional
from pyloquent import Model
from pyloquent.orm.collection import Collection


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class RelUser(Model):
    __table__ = "rel_users"
    __fillable__ = ["name"]
    id: Optional[int] = None
    name: str

    def posts(self):
        return self.has_many(RelPost, foreign_key="user_id")

    def profile(self):
        return self.has_one(RelProfile, foreign_key="user_id")


class RelPost(Model):
    __table__ = "rel_posts"
    __fillable__ = ["title", "body", "user_id", "published"]
    id: Optional[int] = None
    title: str
    body: Optional[str] = None
    user_id: Optional[int] = None
    published: Optional[bool] = False

    def author(self):
        return self.belongs_to(RelUser, foreign_key="user_id", owner_key="id")


class RelProfile(Model):
    __table__ = "rel_profiles"
    __fillable__ = ["bio", "user_id"]
    id: Optional[int] = None
    bio: str
    user_id: Optional[int] = None


@pytest.fixture
async def rel_tables(sqlite_db):
    conn = sqlite_db.connection()
    await conn.execute("""
        CREATE TABLE rel_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    await conn.execute("""
        CREATE TABLE rel_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT,
            user_id INTEGER,
            published INTEGER DEFAULT 0,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    await conn.execute("""
        CREATE TABLE rel_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bio TEXT NOT NULL,
            user_id INTEGER,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    yield


# ---------------------------------------------------------------------------
# HasMany: save, save_many, create_many, find, find_many, update, delete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_has_many_save(sqlite_db, rel_tables):
    user = await RelUser.create({"name": "Alice"})
    post = RelPost(title="Saved", user_id=0)
    saved = await user.posts().save(post)
    assert saved.user_id == user.id


@pytest.mark.asyncio
async def test_has_many_save_many(sqlite_db, rel_tables):
    user = await RelUser.create({"name": "Bob"})
    p1 = RelPost(title="P1", user_id=0)
    p2 = RelPost(title="P2", user_id=0)
    result = await user.posts().save_many(Collection([p1, p2]))
    assert len(result) == 2
    assert all(p.user_id == user.id for p in result)


@pytest.mark.asyncio
async def test_has_many_create(sqlite_db, rel_tables):
    user = await RelUser.create({"name": "Carol"})
    post = await user.posts().create({"title": "Created"})
    assert post.user_id == user.id
    assert post.id is not None


@pytest.mark.asyncio
async def test_has_many_create_many(sqlite_db, rel_tables):
    user = await RelUser.create({"name": "Dave"})
    posts = await user.posts().create_many([
        {"title": "CM1"},
        {"title": "CM2"},
        {"title": "CM3"},
    ])
    assert len(posts) == 3
    assert all(p.user_id == user.id for p in posts)


@pytest.mark.asyncio
async def test_has_many_find(sqlite_db, rel_tables):
    user = await RelUser.create({"name": "Eve"})
    post = await user.posts().create({"title": "FindMe"})
    found = await user.posts().find(post.id)
    assert found is not None
    assert found.title == "FindMe"


@pytest.mark.asyncio
async def test_has_many_find_returns_none_for_wrong_parent(sqlite_db, rel_tables):
    u1 = await RelUser.create({"name": "U1"})
    u2 = await RelUser.create({"name": "U2"})
    post = await u1.posts().create({"title": "NotYours"})
    found = await u2.posts().find(post.id)
    assert found is None


@pytest.mark.asyncio
async def test_has_many_find_many(sqlite_db, rel_tables):
    user = await RelUser.create({"name": "Frank"})
    p1 = await user.posts().create({"title": "FM1"})
    p2 = await user.posts().create({"title": "FM2"})
    results = await user.posts().find_many([p1.id, p2.id])
    assert len(results) == 2


@pytest.mark.asyncio
async def test_has_many_update(sqlite_db, rel_tables):
    user = await RelUser.create({"name": "Gina"})
    await user.posts().create({"title": "OldTitle"})
    count = await user.posts().update({"title": "NewTitle"})
    assert count == 1
    posts = await user.posts().get()
    assert posts[0].title == "NewTitle"


@pytest.mark.asyncio
async def test_has_many_delete(sqlite_db, rel_tables):
    user = await RelUser.create({"name": "Hal"})
    await user.posts().create({"title": "Del1"})
    await user.posts().create({"title": "Del2"})
    deleted = await user.posts().delete()
    assert deleted == 2
    posts = await user.posts().get()
    assert len(posts) == 0


# ---------------------------------------------------------------------------
# HasOne: create, save, delete, update
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_has_one_create(sqlite_db, rel_tables):
    user = await RelUser.create({"name": "Iris"})
    profile = await user.profile().create({"bio": "Hello"})
    assert profile.user_id == user.id
    assert profile.id is not None


@pytest.mark.asyncio
async def test_has_one_save(sqlite_db, rel_tables):
    user = await RelUser.create({"name": "Jack"})
    profile = RelProfile(bio="Bio", user_id=0)
    saved = await user.profile().save(profile)
    assert saved.user_id == user.id


@pytest.mark.asyncio
async def test_has_one_get_results(sqlite_db, rel_tables):
    user = await RelUser.create({"name": "Kim"})
    await user.profile().create({"bio": "My Bio"})
    found = await user.profile().get_results()
    assert found is not None
    assert found.bio == "My Bio"


@pytest.mark.asyncio
async def test_has_one_delete_when_exists(sqlite_db, rel_tables):
    user = await RelUser.create({"name": "Leo"})
    await user.profile().create({"bio": "Delete Me"})
    result = await user.profile().delete()
    assert result is True
    assert await user.profile().get_results() is None


@pytest.mark.asyncio
async def test_has_one_delete_when_absent(sqlite_db, rel_tables):
    user = await RelUser.create({"name": "Mia"})
    result = await user.profile().delete()
    assert result is False


@pytest.mark.asyncio
async def test_has_one_update(sqlite_db, rel_tables):
    user = await RelUser.create({"name": "Ned"})
    await user.profile().create({"bio": "Old Bio"})
    count = await user.profile().update({"bio": "New Bio"})
    assert count == 1
    profile = await user.profile().get_results()
    assert profile.bio == "New Bio"


# ---------------------------------------------------------------------------
# BelongsTo: get_results, associate, dissociate, get_parent_key, get_related_key
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_belongs_to_get_results(sqlite_db, rel_tables):
    user = await RelUser.create({"name": "Ora"})
    post = await RelPost.create({"title": "Belongs", "user_id": user.id})
    author = await post.author().get_results()
    assert author is not None
    assert author.name == "Ora"


@pytest.mark.asyncio
async def test_belongs_to_associate(sqlite_db, rel_tables):
    user = await RelUser.create({"name": "Pat"})
    post = await RelPost.create({"title": "Assoc"})
    await post.author().associate(user)
    assert post.user_id == user.id


@pytest.mark.asyncio
async def test_belongs_to_dissociate(sqlite_db, rel_tables):
    user = await RelUser.create({"name": "Quinn"})
    post = await RelPost.create({"title": "Dissoc", "user_id": user.id})
    await post.author().dissociate()
    assert post.user_id is None


@pytest.mark.asyncio
async def test_belongs_to_get_parent_key(sqlite_db, rel_tables):
    user = await RelUser.create({"name": "Rob"})
    post = await RelPost.create({"title": "PK", "user_id": user.id})
    assert post.author().get_parent_key() == user.id


@pytest.mark.asyncio
async def test_belongs_to_get_related_key(sqlite_db, rel_tables):
    user = await RelUser.create({"name": "Sue"})
    post = await RelPost.create({"title": "RK", "user_id": user.id})
    assert post.author().get_related_key() == "id"
