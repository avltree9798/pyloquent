"""Integration tests for uncovered Model instance and class methods."""
import pytest
from typing import ClassVar, Dict, List, Optional
from pyloquent import Model
from pyloquent.orm.collection import Collection


class MmUser(Model):
    __table__ = "mm_users"
    __fillable__ = ["name", "score", "email"]
    __hidden__: ClassVar[List[str]] = ["email"]
    id: Optional[int] = None
    name: str
    score: Optional[int] = 0
    email: Optional[str] = None

    def posts(self):
        return self.has_many(MmPost, foreign_key="user_id")

    @property
    def name_upper(self) -> str:
        return self.name.upper()

    def get_display_name_attribute(self) -> str:
        return f"[{self.name}]"


class MmPost(Model):
    __table__ = "mm_posts"
    __fillable__ = ["title", "user_id"]
    id: Optional[int] = None
    title: str
    user_id: Optional[int] = None

    def author(self):
        return self.belongs_to(MmUser, foreign_key="user_id", owner_key="id")


class GuardedUser(Model):
    __table__ = "mm_users"
    __fillable__: ClassVar[List[str]] = []
    __guarded__: ClassVar[List[str]] = ["id"]
    id: Optional[int] = None
    name: str
    score: Optional[int] = 0
    email: Optional[str] = None


@pytest.fixture
async def mm_tables(sqlite_db):
    conn = sqlite_db.connection()
    await conn.execute("""
        CREATE TABLE mm_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            score INTEGER DEFAULT 0,
            email TEXT,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    await conn.execute("""
        CREATE TABLE mm_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            user_id INTEGER,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    yield


# ---------------------------------------------------------------------------
# get_key_name / _get_key_name / _set_key
# ---------------------------------------------------------------------------

def test_get_key_name():
    u = MmUser(name="A")
    assert u.get_key_name() == "id"
    assert u._get_key_name() == "id"


def test_set_key():
    u = MmUser(name="B")
    u._set_key(99)
    assert u.id == 99


# ---------------------------------------------------------------------------
# _is_fillable without __fillable__ list (uses __guarded__)
# ---------------------------------------------------------------------------

def test_is_fillable_guarded_list():
    g = GuardedUser(name="G")
    assert g._is_fillable("name") is True
    assert g._is_fillable("id") is False


# ---------------------------------------------------------------------------
# to_dict with __visible__ list
# ---------------------------------------------------------------------------

def test_to_dict_visible_list():
    class VisUser(MmUser):
        __visible__: ClassVar[List[str]] = ["name"]

    u = VisUser(name="Vis", email="vis@test.com", score=5)
    d = u.to_dict()
    assert "name" in d
    assert "email" not in d
    assert "score" not in d


# ---------------------------------------------------------------------------
# to_dict with accessor appends
# ---------------------------------------------------------------------------

def test_to_dict_with_appends():
    u = MmUser(name="App", email="a@b.com")
    u.__class__.__appends__ = ["display_name"]
    d = u.to_dict()
    assert "display_name" in d
    assert d["display_name"] == "[App]"
    u.__class__.__appends__ = []


def test_to_dict_with_property_appends():
    u = MmUser(name="Prop", email="p@b.com")
    u._appended = ["name_upper"]
    d = u.to_dict()
    assert d.get("name_upper") == "PROP"


# ---------------------------------------------------------------------------
# to_array / model_dump
# ---------------------------------------------------------------------------

def test_to_array_alias():
    u = MmUser(name="Arr")
    assert u.to_array() == u.to_dict()


def test_model_dump_overrides_pydantic():
    u = MmUser(name="Dump", email="d@x.com")
    d = u.model_dump()
    assert "email" not in d  # hidden


# ---------------------------------------------------------------------------
# append / append_attributes
# ---------------------------------------------------------------------------

def test_append_attributes():
    u = MmUser(name="Append")
    result = u.append("display_name")
    assert result is u
    assert "display_name" in u._appended


# ---------------------------------------------------------------------------
# increment (model instance method with extra)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_model_instance_increment_with_extra(sqlite_db, mm_tables):
    u = await MmUser.create({"name": "IncTest", "score": 0})
    await u.increment("score", 5, extra={"name": "Updated"})
    assert u.score == 5
    assert u.name == "Updated"


# ---------------------------------------------------------------------------
# push (save model + relations)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_push_saves_model(sqlite_db, mm_tables):
    u = await MmUser.create({"name": "PushUser"})
    u.name = "PushedName"
    await u.push()
    refreshed = await MmUser.find(u.id)
    assert refreshed.name == "PushedName"


@pytest.mark.asyncio
async def test_push_saves_has_many_relations(sqlite_db, mm_tables):
    u = await MmUser.create({"name": "PushRel"})
    p = await MmPost.create({"title": "OldTitle", "user_id": u.id})
    p.title = "NewTitle"
    u.set_relation("posts", Collection([p]))
    await u.push()
    refreshed = await MmPost.find(p.id)
    assert refreshed.title == "NewTitle"


# ---------------------------------------------------------------------------
# load_missing only loads unloaded relations
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_load_missing_skips_already_loaded(sqlite_db, mm_tables):
    u = await MmUser.create({"name": "LM"})
    await MmPost.create({"title": "P1", "user_id": u.id})
    await u.load("posts")
    original_posts = u._relations.get("posts")
    await u.load_missing("posts")
    assert u._relations.get("posts") is original_posts


@pytest.mark.asyncio
async def test_load_missing_loads_unloaded(sqlite_db, mm_tables):
    u = await MmUser.create({"name": "LM2"})
    await MmPost.create({"title": "P2", "user_id": u.id})
    assert "posts" not in u._relations
    await u.load_missing("posts")
    assert "posts" in u._relations


# ---------------------------------------------------------------------------
# cursor classmethod
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cursor_classmethod(sqlite_db, mm_tables):
    for i in range(3):
        await MmUser.create({"name": f"CU{i}"})
    items = []
    async for item in MmUser.cursor():
        items.append(item)
    assert len(items) == 3


# ---------------------------------------------------------------------------
# first_or_new classmethod
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_first_or_new_returns_existing(sqlite_db, mm_tables):
    await MmUser.create({"name": "Existing"})
    result = await MmUser.first_or_new({"name": "Existing"})
    assert result._exists is True
    assert result.name == "Existing"


@pytest.mark.asyncio
async def test_first_or_new_returns_new_unsaved(sqlite_db, mm_tables):
    result = await MmUser.first_or_new({"name": "NewUnsaved"})
    assert result._exists is False
    assert result.name == "NewUnsaved"


@pytest.mark.asyncio
async def test_first_or_new_with_values(sqlite_db, mm_tables):
    result = await MmUser.first_or_new({"name": "NewV"}, values={"score": 42})
    assert result.score == 42
    assert result._exists is False


# ---------------------------------------------------------------------------
# where_exists / where_not_exists classmethods
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_where_exists_classmethod(sqlite_db, mm_tables):
    u = await MmUser.create({"name": "WE"})
    await MmPost.create({"title": "WEP", "user_id": u.id})
    results = await MmUser.where_exists(
        lambda q: q.from_("mm_posts").where_raw('"mm_posts"."user_id" = "mm_users"."id"')
    ).get()
    assert any(r.name == "WE" for r in results)


@pytest.mark.asyncio
async def test_where_not_exists_classmethod(sqlite_db, mm_tables):
    await MmUser.create({"name": "WNE"})
    results = await MmUser.where_not_exists(
        lambda q: q.from_("mm_posts").where_raw('"mm_posts"."user_id" = "mm_users"."id"')
    ).get()
    assert any(r.name == "WNE" for r in results)


# ---------------------------------------------------------------------------
# lock_for_update / for_share classmethods (SQL shape)
# ---------------------------------------------------------------------------

def test_lock_for_update_classmethod():
    qb = MmUser.lock_for_update()
    sql, _ = qb.to_sql()
    assert sql


def test_for_share_classmethod():
    qb = MmUser.for_share()
    sql, _ = qb.to_sql()
    assert sql


# ---------------------------------------------------------------------------
# to_raw_sql classmethod
# ---------------------------------------------------------------------------

def test_to_raw_sql_classmethod():
    raw = MmUser.to_raw_sql()
    assert "mm_users" in raw
    assert "?" not in raw


# ---------------------------------------------------------------------------
# set_event_dispatcher / get_event_dispatcher
# ---------------------------------------------------------------------------

def test_set_and_get_event_dispatcher():
    from unittest.mock import MagicMock
    dispatcher = MagicMock()
    MmUser.set_event_dispatcher(dispatcher)
    assert MmUser.get_event_dispatcher() is dispatcher
    MmUser._dispatcher = None


# ---------------------------------------------------------------------------
# with_ classmethod (eager loads)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_with_classmethod(sqlite_db, mm_tables):
    u = await MmUser.create({"name": "WithTest"})
    await MmPost.create({"title": "WTP", "user_id": u.id})
    results = await MmUser.with_("posts").where("id", u.id).get()
    assert "posts" in results[0]._relations


# ---------------------------------------------------------------------------
# first classmethod
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_first_classmethod(sqlite_db, mm_tables):
    await MmUser.create({"name": "FirstTest"})
    result = await MmUser.first()
    assert result is not None


# ---------------------------------------------------------------------------
# find_many classmethod
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_find_many_classmethod(sqlite_db, mm_tables):
    u1 = await MmUser.create({"name": "FM1"})
    u2 = await MmUser.create({"name": "FM2"})
    await MmUser.create({"name": "FM3"})
    results = await MmUser.find_many([u1.id, u2.id])
    assert len(results) == 2


# ---------------------------------------------------------------------------
# destroy classmethod (single ID)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_destroy_classmethod(sqlite_db, mm_tables):
    u = await MmUser.create({"name": "ToDestroy"})
    await MmUser.destroy(u.id)
    found = await MmUser.find(u.id)
    assert found is None


@pytest.mark.asyncio
async def test_destroy_classmethod_with_list(sqlite_db, mm_tables):
    u1 = await MmUser.create({"name": "D1"})
    u2 = await MmUser.create({"name": "D2"})
    await MmUser.destroy([u1.id, u2.id])
    assert await MmUser.find(u1.id) is None
    assert await MmUser.find(u2.id) is None


# ---------------------------------------------------------------------------
# load_count with missing relation name (should skip)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_load_count_skips_missing_relation(sqlite_db, mm_tables):
    u = await MmUser.create({"name": "LC"})
    await u.load_count("nonexistent_relation")
    assert not hasattr(u, "nonexistent_relation_count")


# ---------------------------------------------------------------------------
# Saving event abort (saving returns False)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_saving_event_abort(sqlite_db, mm_tables):
    class AbortUser(MmUser):
        __table__ = "mm_users"

    fired = []

    async def abort_saving(model):
        fired.append("saving")
        return False

    AbortUser.on("saving", abort_saving)
    u = AbortUser(name="AbortMe")
    result = await u.save()
    assert result is u
    assert u._exists is False
    AbortUser._dispatcher = None
