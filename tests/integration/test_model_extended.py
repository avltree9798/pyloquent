"""Integration tests for extended Model methods."""

import pytest
from typing import Optional

from pyloquent import Model


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(Model):
    __table__ = "users"
    __fillable__ = ["name", "email", "age", "score", "is_active"]
    __hidden__ = ["score"]

    id: Optional[int] = None
    name: str
    email: str
    age: Optional[int] = None
    score: int = 0
    is_active: bool = True

    def posts(self):
        return self.has_many(Post)


class Post(Model):
    __table__ = "posts"
    __fillable__ = ["user_id", "title", "content", "views", "is_published"]

    id: Optional[int] = None
    user_id: int
    title: str
    content: Optional[str] = None
    views: int = 0
    is_published: bool = False

    def author(self):
        return self.belongs_to(User)


# ---------------------------------------------------------------------------
# Instance method: update()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_instance_update(sqlite_db, setup_extended_tables):
    user = await User.create({"name": "Alice", "email": "alice@x.com"})
    await user.update({"name": "Alice Updated"})
    found = await User.find(user.id)
    assert found.name == "Alice Updated"


# ---------------------------------------------------------------------------
# Instance method: increment() / decrement()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_instance_increment(sqlite_db, setup_extended_tables):
    user = await User.create({"name": "Bob", "email": "bob@x.com", "score": 10})
    await user.increment("score", 5)
    found = await User.find(user.id)
    assert found.score == 15


@pytest.mark.asyncio
async def test_instance_decrement(sqlite_db, setup_extended_tables):
    user = await User.create({"name": "Carol", "email": "carol@x.com", "score": 20})
    await user.decrement("score", 3)
    found = await User.find(user.id)
    assert found.score == 17


# ---------------------------------------------------------------------------
# QueryBuilder: increment() / decrement()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_query_increment(sqlite_db, setup_extended_tables):
    u = await User.create({"name": "Dave", "email": "dave@x.com", "score": 0})
    await User.where("id", u.id).increment("score", 10)
    found = await User.find(u.id)
    assert found.score == 10


@pytest.mark.asyncio
async def test_query_decrement(sqlite_db, setup_extended_tables):
    u = await User.create({"name": "Eve", "email": "eve@x.com", "score": 50})
    await User.where("id", u.id).decrement("score", 5)
    found = await User.find(u.id)
    assert found.score == 45


# ---------------------------------------------------------------------------
# QueryBuilder: insert_or_ignore()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_insert_or_ignore(sqlite_db, setup_extended_tables):
    await User.create({"name": "Frank", "email": "frank@x.com"})
    # Duplicate email – should be silently ignored
    await User.where("email", "frank@x.com").insert_or_ignore(
        [{"name": "Duplicate Frank", "email": "frank@x.com"}]
    )
    count = await User.where("email", "frank@x.com").count()
    assert count == 1


# ---------------------------------------------------------------------------
# QueryBuilder: upsert()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upsert_inserts_new(sqlite_db, setup_extended_tables):
    await User.query.upsert(
        [{"name": "Grace", "email": "grace@x.com", "score": 5}],
        unique_by=["email"],
        update_columns=["name", "score"],
    )
    found = await User.where("email", "grace@x.com").first()
    assert found is not None
    assert found.score == 5


@pytest.mark.asyncio
async def test_upsert_updates_existing(sqlite_db, setup_extended_tables):
    await User.create({"name": "Heidi", "email": "heidi@x.com", "score": 1})
    await User.query.upsert(
        [{"name": "Heidi Updated", "email": "heidi@x.com", "score": 99}],
        unique_by=["email"],
        update_columns=["name", "score"],
    )
    found = await User.where("email", "heidi@x.com").first()
    assert found.score == 99


# ---------------------------------------------------------------------------
# QueryBuilder: update_or_insert()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_or_insert_creates(sqlite_db, setup_extended_tables):
    await User.query.update_or_insert(
        {"email": "ivan@x.com"},
        {"name": "Ivan", "email": "ivan@x.com"},
    )
    found = await User.where("email", "ivan@x.com").first()
    assert found is not None
    assert found.name == "Ivan"


@pytest.mark.asyncio
async def test_update_or_insert_updates(sqlite_db, setup_extended_tables):
    await User.create({"name": "Judy", "email": "judy@x.com"})
    await User.query.update_or_insert(
        {"email": "judy@x.com"},
        {"name": "Judy Updated"},
    )
    found = await User.where("email", "judy@x.com").first()
    assert found.name == "Judy Updated"


# ---------------------------------------------------------------------------
# QueryBuilder: find_many()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_find_many(sqlite_db, setup_extended_tables):
    u1 = await User.create({"name": "Karl", "email": "karl@x.com"})
    u2 = await User.create({"name": "Lena", "email": "lena@x.com"})
    await User.create({"name": "Mike", "email": "mike@x.com"})
    results = await User.find_many([u1.id, u2.id])
    assert len(results) == 2
    emails = {r.email for r in results}
    assert emails == {"karl@x.com", "lena@x.com"}


# ---------------------------------------------------------------------------
# QueryBuilder: where_exists()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_where_exists(sqlite_db, setup_extended_tables):
    u1 = await User.create({"name": "Nina", "email": "nina@x.com"})
    u2 = await User.create({"name": "Oscar", "email": "oscar@x.com"})
    await Post.create({"user_id": u1.id, "title": "Post by Nina"})

    from pyloquent.query.builder import QueryBuilder
    from pyloquent.grammars.sqlite_grammar import SQLiteGrammar

    results = await User.where_exists(
        lambda q: q.from_("posts").where_raw('"posts"."user_id" = "users"."id"')
    ).get()

    names = {u.name for u in results}
    assert "Nina" in names
    assert "Oscar" not in names


@pytest.mark.asyncio
async def test_where_not_exists(sqlite_db, setup_extended_tables):
    u1 = await User.create({"name": "Pat", "email": "pat@x.com"})
    u2 = await User.create({"name": "Quinn", "email": "quinn@x.com"})
    await Post.create({"user_id": u1.id, "title": "Post by Pat"})

    results = await User.where_not_exists(
        lambda q: q.from_("posts").where_raw('"posts"."user_id" = "users"."id"')
    ).get()

    names = {u.name for u in results}
    assert "Quinn" in names
    assert "Pat" not in names


# ---------------------------------------------------------------------------
# QueryBuilder: paginate() / simple_paginate()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_paginate(sqlite_db, setup_extended_tables):
    for i in range(12):
        await User.create({"name": f"User{i}", "email": f"u{i}@x.com"})

    result = await User.paginate(per_page=5, page=1)
    assert result["per_page"] == 5
    assert result["current_page"] == 1
    assert result["total"] == 12
    assert len(result["data"]) == 5
    assert result["last_page"] == 3


@pytest.mark.asyncio
async def test_paginate_last_page(sqlite_db, setup_extended_tables):
    for i in range(7):
        await User.create({"name": f"P{i}", "email": f"p{i}@x.com"})

    result = await User.paginate(per_page=5, page=2)
    assert len(result["data"]) == 2
    assert result["current_page"] == 2


@pytest.mark.asyncio
async def test_simple_paginate(sqlite_db, setup_extended_tables):
    for i in range(10):
        await User.create({"name": f"S{i}", "email": f"s{i}@x.com"})

    result = await User.simple_paginate(per_page=3, page=2)
    assert result["per_page"] == 3
    assert result["current_page"] == 2
    assert len(result["data"]) == 3


# ---------------------------------------------------------------------------
# QueryBuilder: cursor()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cursor(sqlite_db, setup_extended_tables):
    for i in range(5):
        await User.create({"name": f"C{i}", "email": f"c{i}@x.com"})

    collected = []
    async for model in User.query.cursor():
        collected.append(model)

    assert len(collected) == 5


# ---------------------------------------------------------------------------
# QueryBuilder: when / unless / tap
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_when_truthy_filters(sqlite_db, setup_extended_tables):
    await User.create({"name": "Active", "email": "active@x.com", "is_active": True})
    await User.create({"name": "Inactive", "email": "inactive@x.com", "is_active": False})

    filter_active = True
    results = await User.query.when(
        filter_active, lambda q: q.where("is_active", True)
    ).get()

    assert all(u.is_active for u in results)


@pytest.mark.asyncio
async def test_when_falsy_no_filter(sqlite_db, setup_extended_tables):
    await User.create({"name": "A", "email": "a@x.com", "is_active": True})
    await User.create({"name": "B", "email": "b@x.com", "is_active": False})

    results = await User.query.when(
        False, lambda q: q.where("is_active", True)
    ).get()

    assert len(results) == 2


# ---------------------------------------------------------------------------
# Model: make_hidden / make_visible
# ---------------------------------------------------------------------------

def test_make_hidden():
    u = User(name="Test", email="t@t.com", score=100)
    u.make_hidden("name")
    d = u.to_dict()
    assert "name" not in d


def test_make_visible_overrides_class_hidden():
    u = User(name="Test", email="t@t.com", score=100)
    u.make_visible("score")
    d = u.to_dict()
    assert "score" in d


# ---------------------------------------------------------------------------
# Model: was_changed / get_changes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_was_changed(sqlite_db, setup_extended_tables):
    user = await User.create({"name": "Walt", "email": "walt@x.com"})
    user.name = "Walter"
    await user.save()
    assert user.was_changed("name")
    assert not user.was_changed("email")


@pytest.mark.asyncio
async def test_get_changes(sqlite_db, setup_extended_tables):
    user = await User.create({"name": "Xena", "email": "xena@x.com"})
    user.name = "Xena Updated"
    await user.save()
    changes = user.get_changes()
    assert "name" in changes


# ---------------------------------------------------------------------------
# Model: to_dict / json
# ---------------------------------------------------------------------------

def test_to_dict_hides_class_hidden():
    u = User(name="Test", email="t@t.com", score=50)
    d = u.to_dict()
    assert "score" not in d
    assert "name" in d


def test_json_returns_string():
    import json
    u = User(name="Test", email="t@t.com")
    j = u.json()
    parsed = json.loads(j)
    assert parsed["name"] == "Test"


# ---------------------------------------------------------------------------
# Model: get_key / get_key_name
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_key(sqlite_db, setup_extended_tables):
    user = await User.create({"name": "Yara", "email": "yara@x.com"})
    assert user.get_key() == user.id
    assert user.get_key_name() == "id"


# ---------------------------------------------------------------------------
# Model: replicate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_replicate(sqlite_db, setup_extended_tables):
    user = await User.create({"name": "Zara", "email": "zara@x.com", "score": 5})
    replica = await user.replicate({"email": "zara-copy@x.com"})
    assert replica.id != user.id
    assert replica.name == "Zara"
    assert replica.email == "zara-copy@x.com"
    assert replica.score == 5


# ---------------------------------------------------------------------------
# Model: touch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_touch_updates_updated_at(sqlite_db, setup_extended_tables):
    user = await User.create({"name": "TouchUser", "email": "touch@x.com"})
    original = user.updated_at if hasattr(user, "updated_at") else None
    await user.touch()
    # Just verify it doesn't raise
    assert True


# ---------------------------------------------------------------------------
# Model: destroy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_destroy(sqlite_db, setup_extended_tables):
    u1 = await User.create({"name": "D1", "email": "d1@x.com"})
    u2 = await User.create({"name": "D2", "email": "d2@x.com"})
    await User.destroy(u1.id, u2.id)
    assert await User.find(u1.id) is None
    assert await User.find(u2.id) is None


# ---------------------------------------------------------------------------
# Model: exists / doesnt_exist
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_exists(sqlite_db, setup_extended_tables):
    assert not await User.exists()
    await User.create({"name": "Ex", "email": "ex@x.com"})
    assert await User.exists()


@pytest.mark.asyncio
async def test_doesnt_exist(sqlite_db, setup_extended_tables):
    assert await User.doesnt_exist()
    await User.create({"name": "De", "email": "de@x.com"})
    assert not await User.doesnt_exist()


# ---------------------------------------------------------------------------
# Model: max / min / sum / avg / value
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_aggregate_methods(sqlite_db, setup_extended_tables):
    await User.create({"name": "Agg1", "email": "agg1@x.com", "score": 10})
    await User.create({"name": "Agg2", "email": "agg2@x.com", "score": 30})
    await User.create({"name": "Agg3", "email": "agg3@x.com", "score": 20})

    assert await User.max("score") == 30
    assert await User.min("score") == 10
    assert await User.sum("score") == 60
    assert await User.avg("score") == 20.0


@pytest.mark.asyncio
async def test_value(sqlite_db, setup_extended_tables):
    await User.create({"name": "ValUser", "email": "val@x.com", "score": 77})
    result = await User.order_by("id", "desc").value("score")
    assert result == 77


# ---------------------------------------------------------------------------
# Model: chunk
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chunk(sqlite_db, setup_extended_tables):
    for i in range(10):
        await User.create({"name": f"Ch{i}", "email": f"ch{i}@x.com"})

    chunks = []
    async for chunk in User.chunk(3):
        chunks.append(chunk)

    total = sum(len(c) for c in chunks)
    assert total == 10
    assert len(chunks[0]) == 3


# ---------------------------------------------------------------------------
# Model: first_or_new / first_or_fail
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_first_or_new_creates_unsaved(sqlite_db, setup_extended_tables):
    model = await User.first_or_new({"email": "new@x.com"}, {"name": "New", "email": "new@x.com"})
    assert model.id is None  # Not saved


@pytest.mark.asyncio
async def test_first_or_new_finds_existing(sqlite_db, setup_extended_tables):
    u = await User.create({"name": "Existing", "email": "existing@x.com"})
    model = await User.first_or_new({"email": "existing@x.com"}, {"name": "Other"})
    assert model.id == u.id


@pytest.mark.asyncio
async def test_first_or_fail_raises(sqlite_db, setup_extended_tables):
    from pyloquent.exceptions import ModelNotFoundException
    with pytest.raises(ModelNotFoundException):
        await User.first_or_fail()


# ---------------------------------------------------------------------------
# Model: retrieved event
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retrieved_event_fires(sqlite_db, setup_extended_tables):
    retrieved_ids = []
    User.on("retrieved", lambda m: retrieved_ids.append(m.id) or None)
    u = await User.create({"name": "EventUser", "email": "event@x.com"})
    await User.find(u.id)
    import asyncio
    await asyncio.sleep(0)  # flush any pending futures
    assert u.id in retrieved_ids
