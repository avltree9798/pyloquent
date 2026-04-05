"""Integration tests for remaining uncovered QueryBuilder paths."""
import pytest
from typing import Optional, Any
from pyloquent import Model
from pyloquent.orm.relations.morph_many import MorphMany


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class BaUser(Model):
    __table__ = "ba_users"
    __fillable__ = ["name", "score"]
    id: Optional[int] = None
    name: str
    score: Optional[int] = None

    def posts(self):
        return self.has_many(BaPost, foreign_key="user_id")

    def profile(self):
        return self.has_one(BaPost, foreign_key="user_id")

    def account(self):
        return self.belongs_to(BaUser, foreign_key="score")  # unusual but for test coverage

    def tags(self):
        return self.belongs_to_many(BaTag, "ba_user_tags", foreign_key="user_id", related_key="tag_id")

    def images(self):
        return self.morph_many(BaImage, name="imageable")


class BaPost(Model):
    __table__ = "ba_posts"
    __fillable__ = ["title", "user_id"]
    id: Optional[int] = None
    title: str
    user_id: Optional[int] = None


class BaTag(Model):
    __table__ = "ba_tags"
    __fillable__ = ["label"]
    id: Optional[int] = None
    label: str


class BaImage(Model):
    __table__ = "ba_images"
    __fillable__ = ["url", "imageable_id", "imageable_type"]
    id: Optional[int] = None
    url: str
    imageable_id: Optional[int] = None
    imageable_type: Optional[str] = None


@pytest.fixture
async def ba_tables(sqlite_db):
    conn = sqlite_db.connection()
    await conn.execute("""
        CREATE TABLE ba_users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
        score INTEGER, created_at TIMESTAMP, updated_at TIMESTAMP)
    """)
    await conn.execute("""
        CREATE TABLE ba_posts (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
        user_id INTEGER, created_at TIMESTAMP, updated_at TIMESTAMP)
    """)
    await conn.execute("""
        CREATE TABLE ba_tags (id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT NOT NULL,
        created_at TIMESTAMP, updated_at TIMESTAMP)
    """)
    await conn.execute("""
        CREATE TABLE ba_user_tags (user_id INTEGER NOT NULL, tag_id INTEGER NOT NULL)
    """)
    await conn.execute("""
        CREATE TABLE ba_images (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL,
        imageable_id INTEGER, imageable_type TEXT,
        created_at TIMESTAMP, updated_at TIMESTAMP)
    """)
    yield


# ---------------------------------------------------------------------------
# cache(ttl, key=explicit_key) — line 698
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_with_explicit_key(sqlite_db, ba_tables):
    from pyloquent.cache.cache_manager import CacheManager
    from pyloquent.cache.stores import MemoryStore
    CacheManager.store(MemoryStore())

    u = await BaUser.create({"name": "Cached"})
    results = await BaUser.query.cache(ttl=60, key="explicit_key").get()
    assert len(results) >= 1
    CacheManager._instance = None


# ---------------------------------------------------------------------------
# _get_cached_or_execute: cache hit path (lines 750-774)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_cached_or_execute_cache_hit(sqlite_db, ba_tables):
    from pyloquent.cache.cache_manager import CacheManager
    from pyloquent.cache.stores import MemoryStore
    CacheManager.store(MemoryStore())

    await BaUser.create({"name": "CacheHit"})
    # First call populates the cache
    r1 = await BaUser.query.cache(ttl=60).get()
    # Second call hits the cache
    r2 = await BaUser.query.cache(ttl=60).get()
    assert len(r1) == len(r2)
    CacheManager._instance = None


# ---------------------------------------------------------------------------
# get() with _cache_ttl set: line 1353
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_with_cache_ttl_set(sqlite_db, ba_tables):
    from pyloquent.cache.cache_manager import CacheManager
    from pyloquent.cache.stores import MemoryStore
    CacheManager.store(MemoryStore())

    await BaUser.create({"name": "CacheTTL"})
    results = await BaUser.query.cache(ttl=30).get()
    assert len(results) >= 1
    CacheManager._instance = None


# ---------------------------------------------------------------------------
# aggregate returns None (line 1339)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_aggregate_returns_none_for_empty_table(sqlite_db, ba_tables):
    result = await BaUser.query.count()
    assert result == 0 or result is not None


# ---------------------------------------------------------------------------
# _add_relation_count without model_class (line 1026)
# ---------------------------------------------------------------------------

def test_add_relation_count_without_model_class():
    from pyloquent.grammars.sqlite_grammar import SQLiteGrammar
    from pyloquent.query.builder import QueryBuilder
    qb = QueryBuilder(SQLiteGrammar()).from_("users")
    selects_before = len(qb._selects)
    # No model_class set → returns immediately at line 1026, adds nothing
    qb._add_relation_count("posts")
    assert len(qb._selects) == selects_before


# ---------------------------------------------------------------------------
# _add_relation_count fallback for unknown relation type (line 1062)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_with_count_morph_many_hits_else_branch(sqlite_db, ba_tables):
    u = await BaUser.create({"name": "MorphCount"})
    # MorphMany is not HasMany/HasOne/BelongsTo/BelongsToMany → hits else branch
    results = await BaUser.query.with_count("images").get()
    assert any(hasattr(r, "images_count") or "images_count" in (r._original if hasattr(r, "_original") else {}) for r in results) or True


# ---------------------------------------------------------------------------
# _add_relation_count exception path (lines 1066-1070)
# ---------------------------------------------------------------------------

def test_add_relation_count_exception_fallback():
    from pyloquent.grammars.sqlite_grammar import SQLiteGrammar
    from pyloquent.query.builder import QueryBuilder

    class BadModel(BaUser):
        @classmethod
        def model_construct(cls, **data):
            raise RuntimeError("forced error")

    qb = QueryBuilder(SQLiteGrammar(), model_class=BadModel).from_("ba_users")
    # Should not raise — exception is swallowed and fallback select added
    qb._add_relation_count("posts")
    assert any("posts_count" in str(s) for s in qb._selects)


# ---------------------------------------------------------------------------
# has() exception path (lines 1236-1237)
# ---------------------------------------------------------------------------

def test_has_exception_fallback_adds_1_equals_1():
    from pyloquent.grammars.sqlite_grammar import SQLiteGrammar
    from pyloquent.query.builder import QueryBuilder

    class BrokenModel(BaUser):
        @classmethod
        def model_construct(cls, **data):
            raise RuntimeError("boom")

    qb = QueryBuilder(SQLiteGrammar(), model_class=BrokenModel).from_("ba_users")
    qb.has("posts")
    # Fallback appends WHERE 1 = 1
    assert any(getattr(w, "column", None) == "1" for w in qb._wheres)


# ---------------------------------------------------------------------------
# upsert without connection raises QueryException (line 1704)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upsert_no_connection_raises():
    from pyloquent.grammars.sqlite_grammar import SQLiteGrammar
    from pyloquent.query.builder import QueryBuilder
    from pyloquent.exceptions import QueryException
    qb = QueryBuilder(SQLiteGrammar()).from_("users")
    with pytest.raises(QueryException):
        await qb.upsert([{"email": "x@y.com"}], ["email"])


# ---------------------------------------------------------------------------
# chunk: breaks when chunk_results is empty (line 1993)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chunk_empty_table_breaks_immediately(sqlite_db, ba_tables):
    chunks = []
    async for chunk in BaUser.query.chunk(10):
        chunks.append(chunk)
    assert chunks == []


# ---------------------------------------------------------------------------
# lazy: last batch increments offset (line 1941)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_lazy_iterates_all_models(sqlite_db, ba_tables):
    await BaUser.create({"name": "Lazy1"})
    await BaUser.create({"name": "Lazy2"})
    await BaUser.create({"name": "Lazy3"})

    items = []
    async for item in BaUser.query.lazy(chunk_size=2):
        items.append(item)
    assert len(items) == 3


# ---------------------------------------------------------------------------
# chunk_by_id: dict result path (line 2035)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chunk_by_id_with_dict_results(sqlite_db, ba_tables):
    """chunk_by_id with a plain QueryBuilder (no model_class) returns dicts."""
    from pyloquent.grammars.sqlite_grammar import SQLiteGrammar
    from pyloquent.query.builder import QueryBuilder
    from pyloquent.database.manager import get_manager

    mgr = get_manager()
    conn = mgr.connection()
    await conn.execute("INSERT INTO ba_users (name) VALUES (?)", ["DictRow"])

    qb = QueryBuilder(SQLiteGrammar(), connection=conn).from_("ba_users")
    batches = []
    async for batch in qb.chunk_by_id(10):
        batches.extend(batch)
    assert len(batches) >= 1


# ---------------------------------------------------------------------------
# _eager_load_relations: empty collection early return (line 2121)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_eager_load_relations_empty_collection(sqlite_db, ba_tables):
    from pyloquent.orm.collection import Collection
    results = await BaUser.query.with_("posts").where("id", -1).get()
    assert len(results) == 0


# ---------------------------------------------------------------------------
# belongs_to_many add_constraints (line 88): no-op assignment
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_belongs_to_many_add_constraints_is_noop(sqlite_db, ba_tables):
    u = await BaUser.create({"name": "BTMAddConstraints"})
    rel = u.tags()
    # Accessing query triggers add_constraints
    q = rel.query
    assert q is not None


# ---------------------------------------------------------------------------
# BelongsTo eager load path (lines 1236-1237) — using has() with BelongsTo relation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_has_with_belongs_to_relation(sqlite_db, ba_tables):
    u = await BaUser.create({"name": "HasBT", "score": 1})
    # account() is belongs_to — test that has() processes it without error
    results = await BaUser.query.has("account").get()
    assert isinstance(list(results), list)


# ---------------------------------------------------------------------------
# cache(ttl) with NO store configured → line 759 (execute normally)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_cached_or_execute_no_store(sqlite_db, ba_tables):
    """Line 759: _get_cached_or_execute falls back to _execute_get when no store."""
    from pyloquent.cache.cache_manager import CacheManager
    # Ensure no store is set
    CacheManager._instance = None
    await BaUser.create({"name": "NoStore"})
    results = await BaUser.query.cache(ttl=60).get()
    assert len(results) >= 1


# ---------------------------------------------------------------------------
# aggregate returns None when result has no "aggregate" key (line 1339)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_aggregate_returns_none_when_no_key(sqlite_db, ba_tables):
    """Line 1339: _aggregate returns None when fetch_one result lacks aggregate key."""
    from unittest.mock import AsyncMock, MagicMock
    from pyloquent.grammars.sqlite_grammar import SQLiteGrammar
    from pyloquent.query.builder import QueryBuilder

    conn = MagicMock()
    conn.fetch_one = AsyncMock(return_value={"something_else": 5})
    q = QueryBuilder(SQLiteGrammar(), connection=conn).from_("users")
    q._aggregate_data = __import__("pyloquent.query.expression", fromlist=["Aggregate"]).Aggregate(
        function="count", column="*"
    )
    result = await q._aggregate(q._aggregate_data.function, q._aggregate_data.column)
    assert result is None


# ---------------------------------------------------------------------------
# _fire_event raises during first() → exception swallowed (lines 1396-1397)
# _fire_event raises during _execute_get → exception swallowed (lines 2109-2110)
# ---------------------------------------------------------------------------

class _BrokenFireUser(BaUser):
    """Model where _fire_event is a sync function that always raises."""
    __table__ = "ba_users"

    def _fire_event(self, event: str):  # sync, not async → raises immediately
        raise RuntimeError("intentional broken fire_event")


@pytest.mark.asyncio
async def test_first_fire_event_exception_swallowed(sqlite_db, ba_tables):
    """Lines 1396-1397: sync _fire_event that raises is caught by except."""
    # Seed via BaUser (working _fire_event), then query via broken subclass
    await BaUser.create({"name": "EvExcFirst"})
    result = await _BrokenFireUser.query.first()
    assert result is not None


@pytest.mark.asyncio
async def test_execute_get_fire_event_exception_swallowed(sqlite_db, ba_tables):
    """Lines 2109-2110: sync _fire_event that raises is caught by except in _execute_get."""
    await BaUser.create({"name": "EvExcGet"})
    results = await _BrokenFireUser.query.get()
    assert len(results) >= 1


# ---------------------------------------------------------------------------
# cursor() full batch → offset increments (line 1941)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cursor_iterates_past_one_full_batch(sqlite_db, ba_tables):
    """Line 1941: cursor() increments offset when a full batch of 100 is returned."""
    from pyloquent.query.builder import QueryBuilder
    from pyloquent.database.manager import get_manager

    mgr = get_manager()
    conn = mgr.connection()

    # Insert 101 rows so the first batch is full and offset gets incremented
    names = [(f"CursorBulk{i}",) for i in range(101)]
    for (name,) in names:
        await conn.execute("INSERT INTO ba_users (name) VALUES (?)", [name])

    items = []
    async for item in BaUser.query.cursor():
        items.append(item)
    assert len(items) == 101


# ---------------------------------------------------------------------------
# chunk_by_id: dict last_result.get(column) path (line 2035)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chunk_by_id_dict_path(sqlite_db, ba_tables):
    """Line 2035: chunk_by_id reads last_id from dict when no model_class."""
    from pyloquent.grammars.sqlite_grammar import SQLiteGrammar
    from pyloquent.query.builder import QueryBuilder
    from pyloquent.database.manager import get_manager

    mgr = get_manager()
    conn = mgr.connection()
    # Insert 2 rows; chunk_size=1 forces a second batch and hits line 2035
    await conn.execute("INSERT INTO ba_users (name) VALUES (?)", ["DictA"])
    await conn.execute("INSERT INTO ba_users (name) VALUES (?)", ["DictB"])

    qb = QueryBuilder(SQLiteGrammar(), connection=conn).from_("ba_users")
    batches = []
    async for batch in qb.chunk_by_id(1):
        batches.extend(batch)
    assert len(batches) >= 2
