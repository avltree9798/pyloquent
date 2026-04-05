"""Integration tests for remaining uncovered Model edge cases."""
import pytest
from typing import ClassVar, Dict, List, Optional
from pyloquent import Model
from pyloquent.exceptions import ModelNotFoundException


class EcUser(Model):
    __table__ = "ec_users"
    __fillable__ = ["name", "score"]
    id: Optional[int] = None
    name: str
    score: Optional[int] = 0

    def posts(self):
        return self.has_many(EcPost, foreign_key="user_id")

    def profile(self):
        return self.has_one(EcPost, foreign_key="user_id")


class EcPost(Model):
    __table__ = "ec_posts"
    __fillable__ = ["title", "user_id"]
    id: Optional[int] = None
    title: str
    user_id: Optional[int] = None

    def author(self):
        return self.belongs_to(EcUser, foreign_key="user_id", owner_key="id")


@pytest.fixture
async def ec_tables(sqlite_db):
    conn = sqlite_db.connection()
    await conn.execute("""
        CREATE TABLE ec_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            score INTEGER DEFAULT 0,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    await conn.execute("""
        CREATE TABLE ec_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            user_id INTEGER,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    yield


# ---------------------------------------------------------------------------
# creating event abort
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_creating_event_abort(sqlite_db, ec_tables):
    class AbortCreate(EcUser):
        __table__ = "ec_users"

    async def abort(model):
        return False

    AbortCreate.on("creating", abort)
    u = AbortCreate(name="ShouldNotCreate")
    result = await u.save()
    assert result is u
    assert u._exists is False
    AbortCreate._dispatcher = None


# ---------------------------------------------------------------------------
# updating event abort
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_updating_event_abort(sqlite_db, ec_tables):
    class AbortUpdate(EcUser):
        __table__ = "ec_users"

    async def abort(model):
        return False

    AbortUpdate.on("updating", abort)
    u = AbortUpdate(name="First")
    await u.save()
    assert u._exists is True

    u.name = "Changed"
    result = await u.save()
    assert result is u
    AbortUpdate._dispatcher = None


# ---------------------------------------------------------------------------
# deleting event abort
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deleting_event_abort(sqlite_db, ec_tables):
    class AbortDel(EcUser):
        __table__ = "ec_users"

    async def abort(model):
        return False

    AbortDel.on("deleting", abort)
    u = AbortDel(name="ShouldNotDel")
    await u.save()
    result = await u.delete()
    assert result is False
    assert u._exists is True
    AbortDel._dispatcher = None


# ---------------------------------------------------------------------------
# delete on non-existent model
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_non_existent_model(sqlite_db, ec_tables):
    u = EcUser(name="Ghost")
    result = await u.delete()
    assert result is False


# ---------------------------------------------------------------------------
# delete with None key
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_with_no_key(sqlite_db, ec_tables):
    u = EcUser(name="NoKey")
    u._exists = True
    u.id = None
    result = await u.delete()
    assert result is False


# ---------------------------------------------------------------------------
# refresh raises on non-existent model
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_raises_when_not_exists(sqlite_db, ec_tables):
    u = EcUser(name="NotSaved")
    with pytest.raises(ModelNotFoundException):
        await u.refresh()


# ---------------------------------------------------------------------------
# _get_default_table_name pluralisation rules
# ---------------------------------------------------------------------------

def test_default_table_name_y_ending():
    class Category(Model):
        pass
    assert Category._get_default_table_name() == "categories"


def test_default_table_name_s_ending():
    class Address(Model):
        pass
    assert Address._get_default_table_name() == "addresses"


def test_default_table_name_regular():
    class Post(Model):
        pass
    assert Post._get_default_table_name() == "posts"


def test_default_table_name_vowel_y():
    class Day(Model):
        pass
    assert Day._get_default_table_name() == "days"


# ---------------------------------------------------------------------------
# belongs_to_many auto-generates pivot table and keys
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_belongs_to_many_auto_pivot_table(sqlite_db, ec_tables):
    class TagUser(EcUser):
        __table__ = "ec_users"

        def tags(self):
            return self.belongs_to_many(EcPost)

    u = TagUser(name="AutoPivot")
    u._exists = True
    rel = u.tags()
    assert rel.table is not None
    assert isinstance(rel.table, str)


@pytest.mark.asyncio
async def test_belongs_to_many_auto_foreign_key(sqlite_db, ec_tables):
    class TagUser2(EcUser):
        __table__ = "ec_users"

        def tags(self):
            return self.belongs_to_many(EcPost, table="ec_user_posts")

    u = TagUser2(name="AutoFK")
    u._exists = True
    rel = u.tags()
    assert rel.foreign_key is not None


@pytest.mark.asyncio
async def test_belongs_to_many_auto_related_key(sqlite_db, ec_tables):
    class TagUser3(EcUser):
        __table__ = "ec_users"

        def tags(self):
            return self.belongs_to_many(EcPost, table="ec_user_posts", foreign_key="user_id")

    u = TagUser3(name="AutoRK")
    u._exists = True
    rel = u.tags()
    assert rel.related_key is not None


# ---------------------------------------------------------------------------
# load raises AttributeError for missing relation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_load_raises_on_missing_relation(sqlite_db, ec_tables):
    u = await EcUser.create({"name": "LoadErr"})
    with pytest.raises(AttributeError):
        await u.load("nonexistent_relation")


# ---------------------------------------------------------------------------
# dirty tracking with specific key
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_is_dirty_specific_key(sqlite_db, ec_tables):
    u = await EcUser.create({"name": "DirtyKey"})
    assert u.is_dirty("name") is False
    u.name = "Changed"
    assert u.is_dirty("name") is True
    assert u.is_dirty("score") is False


@pytest.mark.asyncio
async def test_is_clean_with_key(sqlite_db, ec_tables):
    u = await EcUser.create({"name": "CleanKey"})
    assert u.is_clean("name") is True
    u.name = "Changed"
    assert u.is_clean("name") is False


@pytest.mark.asyncio
async def test_was_changed_with_key(sqlite_db, ec_tables):
    u = await EcUser.create({"name": "WasChanged"})
    u.name = "Updated"
    await u.save()
    assert u.was_changed("name") is True
    assert u.was_changed("score") is False


@pytest.mark.asyncio
async def test_get_original_with_key(sqlite_db, ec_tables):
    u = await EcUser.create({"name": "OrigKey"})
    original_name = u.get_original("name")
    assert original_name == "OrigKey"


@pytest.mark.asyncio
async def test_get_original_with_default(sqlite_db, ec_tables):
    u = await EcUser.create({"name": "OrigDef"})
    result = u.get_original("nonexistent", default="fallback")
    assert result == "fallback"


@pytest.mark.asyncio
async def test_is_dirty_unknown_key_returns_false(sqlite_db, ec_tables):
    u = await EcUser.create({"name": "UnknownKey"})
    assert u.is_dirty("totally_unknown_field") is False


# ---------------------------------------------------------------------------
# touch method
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_touch_updates_timestamp(sqlite_db, ec_tables):
    u = await EcUser.create({"name": "Touch"})
    result = await u.touch()
    assert result is True


# ---------------------------------------------------------------------------
# push with a belongs_to relation (single model, not collection)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_push_with_single_relation(sqlite_db, ec_tables):
    u = await EcUser.create({"name": "PushSingle"})
    p = await EcPost.create({"title": "PushPost", "user_id": u.id})
    await p.load("author")
    author = p._relations.get("author")
    if author:
        author.name = "PushedAuthor"
    await p.push()
    if author:
        refreshed = await EcUser.find(author.id)
        assert refreshed.name == "PushedAuthor"


# ---------------------------------------------------------------------------
# Model classmethod proxies: value, distinct, left_join, right_join,
# group_by, having, where_null, where_not_null, where_between,
# where_not_between, or_where
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_value_classmethod(sqlite_db, ec_tables):
    await EcUser.create({"name": "ValTest"})
    name = await EcUser.value("name")
    assert name is not None


def test_distinct_classmethod():
    qb = EcUser.distinct()
    sql, _ = qb.to_sql()
    assert "DISTINCT" in sql


def test_left_join_classmethod():
    qb = EcUser.left_join("ec_posts", "ec_users.id", "=", "ec_posts.user_id")
    sql, _ = qb.to_sql()
    assert "LEFT JOIN" in sql.upper()


def test_right_join_classmethod():
    qb = EcUser.right_join("ec_posts", "ec_users.id", "=", "ec_posts.user_id")
    sql, _ = qb.to_sql()
    assert "RIGHT JOIN" in sql.upper()


def test_group_by_classmethod():
    qb = EcUser.group_by("name")
    sql, _ = qb.to_sql()
    assert "GROUP BY" in sql.upper()


def test_having_classmethod():
    qb = EcUser.having("score", ">", 10)
    sql, bindings = qb.to_sql()
    assert "HAVING" in sql.upper()


def test_where_null_classmethod():
    qb = EcUser.where_null("score")
    sql, _ = qb.to_sql()
    assert "IS NULL" in sql.upper()


def test_where_not_null_classmethod():
    qb = EcUser.where_not_null("score")
    sql, _ = qb.to_sql()
    assert "IS NOT NULL" in sql.upper()


def test_where_between_classmethod():
    qb = EcUser.where_between("score", [1, 10])
    sql, bindings = qb.to_sql()
    assert "BETWEEN" in sql.upper()


def test_where_not_between_classmethod():
    qb = EcUser.where_not_between("score", [1, 10])
    sql, bindings = qb.to_sql()
    assert "NOT BETWEEN" in sql.upper()


def test_or_where_classmethod():
    qb = EcUser.or_where("name", "Alice")
    sql, _ = qb.to_sql()
    assert "name" in sql.lower()
