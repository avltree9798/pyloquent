"""Integration tests for advanced Model features: global scopes, observers,
first_or_fail, update_or_create, load/load_missing/load_count, fill, refresh,
cast, append, has/doesnt_have/where_has/with_count."""
import pytest
from typing import Optional
from pyloquent import Model, SoftDeletes
from pyloquent.exceptions import ModelNotFoundException, MassAssignmentException
from pyloquent.observers.observer import ModelObserver
from pyloquent.observers.dispatcher import EventDispatcher


# ---------------------------------------------------------------------------
# Shared models
# ---------------------------------------------------------------------------

class AdvUser(Model):
    __table__ = "adv_users"
    __fillable__ = ["name", "email", "score", "active"]
    __hidden__ = ["email"]
    __casts__ = {"score": "int", "active": "bool"}

    id: Optional[int] = None
    name: str
    email: str
    score: Optional[int] = 0
    active: Optional[bool] = True

    def posts(self):
        return self.has_many(AdvPost, foreign_key="user_id")


class AdvPost(Model):
    __table__ = "adv_posts"
    __fillable__ = ["title", "user_id", "published"]
    __casts__ = {"published": "bool"}

    id: Optional[int] = None
    title: str
    user_id: Optional[int] = None
    published: Optional[bool] = False

    def author(self):
        return self.belongs_to(AdvUser, foreign_key="user_id")


@pytest.fixture
async def adv_tables(sqlite_db):
    conn = sqlite_db.connection()
    await conn.execute("""
        CREATE TABLE adv_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            score INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    await conn.execute("""
        CREATE TABLE adv_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            user_id INTEGER,
            published INTEGER DEFAULT 0,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    yield


@pytest.fixture(autouse=True)
def clean_adv_listeners():
    EventDispatcher.forget_model(AdvUser)
    EventDispatcher.forget_model(AdvPost)
    yield
    EventDispatcher.forget_model(AdvUser)
    EventDispatcher.forget_model(AdvPost)


# ---------------------------------------------------------------------------
# find_or_fail / first_or_fail
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_find_or_fail_raises(sqlite_db, adv_tables):
    with pytest.raises(ModelNotFoundException):
        await AdvUser.find_or_fail(9999)


@pytest.mark.asyncio
async def test_find_or_fail_returns_model(sqlite_db, adv_tables):
    u = await AdvUser.create({"name": "Alice", "email": "a@adv.com"})
    found = await AdvUser.find_or_fail(u.id)
    assert found.name == "Alice"


@pytest.mark.asyncio
async def test_first_or_fail_raises(sqlite_db, adv_tables):
    with pytest.raises(ModelNotFoundException):
        await AdvUser.where("email", "nobody@adv.com").first_or_fail()


@pytest.mark.asyncio
async def test_first_or_fail_returns_model(sqlite_db, adv_tables):
    await AdvUser.create({"name": "Bob", "email": "b@adv.com"})
    found = await AdvUser.where("email", "b@adv.com").first_or_fail()
    assert found.name == "Bob"


# ---------------------------------------------------------------------------
# update_or_create / first_or_create
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_or_create_creates_when_missing(sqlite_db, adv_tables):
    u = await AdvUser.update_or_create(
        {"email": "new@adv.com"},
        {"name": "New", "score": 10}
    )
    assert u.id is not None
    assert u.name == "New"


@pytest.mark.asyncio
async def test_update_or_create_updates_existing(sqlite_db, adv_tables):
    await AdvUser.create({"name": "Old", "email": "old@adv.com"})
    u = await AdvUser.update_or_create(
        {"email": "old@adv.com"},
        {"name": "Updated"}
    )
    assert u.name == "Updated"


@pytest.mark.asyncio
async def test_first_or_create_creates(sqlite_db, adv_tables):
    u = await AdvUser.first_or_create(
        {"email": "fc@adv.com"},
        {"name": "FC", "score": 5}
    )
    assert u.id is not None


@pytest.mark.asyncio
async def test_first_or_create_finds_existing(sqlite_db, adv_tables):
    await AdvUser.create({"name": "Existing", "email": "ex@adv.com"})
    u = await AdvUser.first_or_create({"email": "ex@adv.com"}, {"name": "Different"})
    assert u.name == "Existing"


# ---------------------------------------------------------------------------
# fill / force_fill / mass assignment
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fill_only_fillable(sqlite_db, adv_tables):
    u = await AdvUser.create({"name": "Fill", "email": "fill@adv.com"})
    u.fill({"name": "Filled"})
    assert u.name == "Filled"


@pytest.mark.asyncio
async def test_force_fill_ignores_guarded(sqlite_db, adv_tables):
    u = await AdvUser.create({"name": "Force", "email": "force@adv.com"})
    u.force_fill({"name": "ForceFilled"})
    assert u.name == "ForceFilled"


# ---------------------------------------------------------------------------
# refresh
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_reloads_from_db(sqlite_db, adv_tables):
    u = await AdvUser.create({"name": "Refresh", "email": "ref@adv.com"})
    await AdvUser.where("id", u.id).update({"name": "RefreshedDB"})
    await u.refresh()
    assert u.name == "RefreshedDB"


# ---------------------------------------------------------------------------
# load / load_missing / load_count
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_load_eager_loads_relation(sqlite_db, adv_tables):
    u = await AdvUser.create({"name": "Load", "email": "load@adv.com"})
    await AdvPost.create({"title": "P1", "user_id": u.id})
    await u.load("posts")
    assert "posts" in u._relations


@pytest.mark.asyncio
async def test_load_missing_only_loads_unloaded(sqlite_db, adv_tables):
    u = await AdvUser.create({"name": "LM", "email": "lm@adv.com"})
    await AdvPost.create({"title": "PM", "user_id": u.id})
    await u.load("posts")
    original_posts = u._relations["posts"]
    await u.load_missing("posts")
    assert u._relations["posts"] is original_posts


@pytest.mark.asyncio
async def test_load_count(sqlite_db, adv_tables):
    u = await AdvUser.create({"name": "LC", "email": "lc@adv.com"})
    await AdvPost.create({"title": "LC1", "user_id": u.id})
    await AdvPost.create({"title": "LC2", "user_id": u.id})
    await u.load_count("posts")
    assert getattr(u, "posts_count") == 2


# ---------------------------------------------------------------------------
# has / doesnt_have / where_has / with_count
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_has(sqlite_db, adv_tables):
    u1 = await AdvUser.create({"name": "HasU", "email": "hasu@adv.com"})
    await AdvPost.create({"title": "HP", "user_id": u1.id})
    await AdvUser.create({"name": "NoPost", "email": "np@adv.com"})
    result = await AdvUser.has("posts").get()
    names = [u.name for u in result]
    assert "HasU" in names
    assert "NoPost" not in names


@pytest.mark.asyncio
async def test_doesnt_have(sqlite_db, adv_tables):
    u1 = await AdvUser.create({"name": "DH1", "email": "dh1@adv.com"})
    await AdvPost.create({"title": "DHP", "user_id": u1.id})
    await AdvUser.create({"name": "DH2", "email": "dh2@adv.com"})
    result = await AdvUser.doesnt_have("posts").get()
    names = [u.name for u in result]
    assert "DH2" in names
    assert "DH1" not in names


@pytest.mark.asyncio
async def test_where_has(sqlite_db, adv_tables):
    u1 = await AdvUser.create({"name": "WH1", "email": "wh1@adv.com"})
    u2 = await AdvUser.create({"name": "WH2", "email": "wh2@adv.com"})
    await AdvPost.create({"title": "pub", "user_id": u1.id, "published": True})
    await AdvPost.create({"title": "draft", "user_id": u2.id, "published": False})
    result = await AdvUser.where_has(
        "posts", lambda q: q.where("published", True)
    ).get()
    assert len(result) == 1
    assert result[0].name == "WH1"


@pytest.mark.asyncio
async def test_with_count(sqlite_db, adv_tables):
    u = await AdvUser.create({"name": "WC", "email": "wc@adv.com"})
    await AdvPost.create({"title": "w1", "user_id": u.id})
    await AdvPost.create({"title": "w2", "user_id": u.id})
    users = await AdvUser.with_count("posts").where("id", u.id).get()
    assert users[0].posts_count == 2


# ---------------------------------------------------------------------------
# Casting
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cast_int(sqlite_db, adv_tables):
    u = await AdvUser.create({"name": "Cast", "email": "cast@adv.com", "score": 42})
    fetched = await AdvUser.find(u.id)
    assert isinstance(fetched.score, int)
    assert fetched.score == 42


@pytest.mark.asyncio
async def test_cast_bool(sqlite_db, adv_tables):
    u = await AdvUser.create({"name": "Bool", "email": "bool@adv.com", "active": True})
    fetched = await AdvUser.find(u.id)
    assert isinstance(fetched.active, bool)
    assert fetched.active is True


# ---------------------------------------------------------------------------
# Serialisation: hidden, make_visible, to_dict
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hidden_field_excluded_from_to_dict(sqlite_db, adv_tables):
    u = await AdvUser.create({"name": "Hid", "email": "hid@adv.com"})
    d = u.to_dict()
    assert "email" not in d


@pytest.mark.asyncio
async def test_make_visible_reveals_hidden_field(sqlite_db, adv_tables):
    u = await AdvUser.create({"name": "MV", "email": "mv@adv.com"})
    u.make_visible("email")
    d = u.to_dict()
    assert "email" in d


@pytest.mark.asyncio
async def test_make_hidden_hides_visible_field(sqlite_db, adv_tables):
    u = await AdvUser.create({"name": "MH", "email": "mh@adv.com"})
    u.make_hidden("name")
    d = u.to_dict()
    assert "name" not in d


# ---------------------------------------------------------------------------
# Observer integration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_observer_creating_fires(sqlite_db, adv_tables):
    fired = []

    class MyObs(ModelObserver):
        def creating(self, m):
            fired.append(m.name)

    AdvUser.observe(MyObs())
    await AdvUser.create({"name": "Obs", "email": "obs@adv.com"})
    assert "Obs" in fired


@pytest.mark.asyncio
async def test_observer_created_fires(sqlite_db, adv_tables):
    fired = []

    class MyObs2(ModelObserver):
        def created(self, m):
            fired.append(m.id)

    AdvUser.observe(MyObs2())
    u = await AdvUser.create({"name": "Obs2", "email": "obs2@adv.com"})
    assert u.id in fired


# ---------------------------------------------------------------------------
# Global scopes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_with_global_scope_on_query(sqlite_db, adv_tables):
    await AdvUser.create({"name": "Active", "email": "act@adv.com", "active": True})
    await AdvUser.create({"name": "Inactive", "email": "inact@adv.com", "active": False})
    users = await AdvUser.query.with_global_scope(
        "active", lambda q: q.where("active", True)
    ).get()
    names = [u.name for u in users]
    assert "Active" in names
    assert "Inactive" not in names


@pytest.mark.asyncio
async def test_without_global_scope(sqlite_db, adv_tables):
    await AdvUser.create({"name": "WGS1", "email": "wgs1@adv.com", "active": True})
    await AdvUser.create({"name": "WGS2", "email": "wgs2@adv.com", "active": False})
    qb = AdvUser.query.with_global_scope(
        "active", lambda q: q.where("active", True)
    )
    all_users = await qb.without_global_scope("active").get()
    names = [u.name for u in all_users]
    assert "WGS2" in names


# ---------------------------------------------------------------------------
# replicate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_replicate_creates_new_record(sqlite_db, adv_tables):
    u = await AdvUser.create({"name": "Orig", "email": "orig@adv.com", "score": 10})
    replica = await u.replicate({"email": "copy@adv.com"})
    assert replica.id != u.id
    assert replica.name == "Orig"
    assert replica.email == "copy@adv.com"


# ---------------------------------------------------------------------------
# was_changed / get_changes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_was_changed_after_update(sqlite_db, adv_tables):
    u = await AdvUser.create({"name": "Chg", "email": "chg@adv.com"})
    u.name = "Changed"
    await u.save()
    assert u.was_changed("name")


@pytest.mark.asyncio
async def test_get_changes(sqlite_db, adv_tables):
    u = await AdvUser.create({"name": "Changes", "email": "changes@adv.com"})
    u.name = "NewName"
    await u.save()
    chg = u.get_changes()
    assert "name" in chg


# ---------------------------------------------------------------------------
# destroy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_destroy(sqlite_db, adv_tables):
    u1 = await AdvUser.create({"name": "D1", "email": "d1@adv.com"})
    u2 = await AdvUser.create({"name": "D2", "email": "d2@adv.com"})
    count = await AdvUser.destroy(u1.id, u2.id)
    assert count == 2
    assert await AdvUser.find(u1.id) is None
    assert await AdvUser.find(u2.id) is None
