"""Integration tests for MorphedByMany inverse polymorphic many-to-many."""
import pytest
from typing import Optional
from pyloquent import Model


class MbmTag(Model):
    __table__ = "mbm_tags"
    __fillable__ = ["name"]
    id: Optional[int] = None
    name: str

    def posts(self):
        return self.morphed_by_many(MbmPost, "taggable")

    def videos(self):
        return self.morphed_by_many(MbmVideo, "taggable")


class MbmPost(Model):
    __table__ = "mbm_posts"
    __fillable__ = ["title"]
    id: Optional[int] = None
    title: str

    def tags(self):
        return self.morph_to_many(MbmTag, "taggable")


class MbmVideo(Model):
    __table__ = "mbm_videos"
    __fillable__ = ["title"]
    id: Optional[int] = None
    title: str

    def tags(self):
        return self.morph_to_many(MbmTag, "taggable")


@pytest.fixture
async def mbm_tables(sqlite_db):
    conn = sqlite_db.connection()
    await conn.execute("""
        CREATE TABLE mbm_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    await conn.execute("""
        CREATE TABLE mbm_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    await conn.execute("""
        CREATE TABLE mbm_videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    await conn.execute("""
        CREATE TABLE taggables (
            mbm_tag_id INTEGER NOT NULL,
            taggable_id INTEGER NOT NULL,
            taggable_type TEXT NOT NULL
        )
    """)
    yield


@pytest.mark.asyncio
async def test_morphed_by_many_get_results(sqlite_db, mbm_tables):
    tag = await MbmTag.create({"name": "python"})
    post = await MbmPost.create({"title": "Post1"})
    await post.tags().attach([tag.id])
    posts = await tag.posts().get_results()
    assert len(posts) == 1
    assert posts[0].title == "Post1"


@pytest.mark.asyncio
async def test_morphed_by_many_get(sqlite_db, mbm_tables):
    tag = await MbmTag.create({"name": "async"})
    post = await MbmPost.create({"title": "AsyncPost"})
    await post.tags().attach([tag.id])
    posts = await tag.posts().get()
    assert len(posts) == 1


@pytest.mark.asyncio
async def test_morphed_by_many_attach(sqlite_db, mbm_tables):
    tag = await MbmTag.create({"name": "orm"})
    post1 = await MbmPost.create({"title": "ORM1"})
    post2 = await MbmPost.create({"title": "ORM2"})
    await tag.posts().attach([post1.id, post2.id])
    posts = await tag.posts().get()
    assert len(posts) == 2


@pytest.mark.asyncio
async def test_morphed_by_many_attach_single(sqlite_db, mbm_tables):
    tag = await MbmTag.create({"name": "single"})
    post = await MbmPost.create({"title": "Single"})
    await tag.posts().attach(post.id)
    posts = await tag.posts().get()
    assert len(posts) == 1


@pytest.mark.asyncio
async def test_morphed_by_many_detach(sqlite_db, mbm_tables):
    tag = await MbmTag.create({"name": "detach"})
    post1 = await MbmPost.create({"title": "D1"})
    post2 = await MbmPost.create({"title": "D2"})
    await tag.posts().attach([post1.id, post2.id])
    await tag.posts().detach([post1.id])
    posts = await tag.posts().get()
    assert len(posts) == 1
    assert posts[0].title == "D2"


@pytest.mark.asyncio
async def test_morphed_by_many_detach_all(sqlite_db, mbm_tables):
    tag = await MbmTag.create({"name": "detachall"})
    post = await MbmPost.create({"title": "DA"})
    await tag.posts().attach([post.id])
    await tag.posts().detach()
    posts = await tag.posts().get()
    assert len(posts) == 0


@pytest.mark.asyncio
async def test_morphed_by_many_isolated_by_type(sqlite_db, mbm_tables):
    tag = await MbmTag.create({"name": "mixed"})
    post = await MbmPost.create({"title": "IsoPost"})
    video = await MbmVideo.create({"title": "IsoVideo"})
    await tag.posts().attach([post.id])
    await tag.videos().attach([video.id])
    posts = await tag.posts().get()
    videos = await tag.videos().get()
    assert len(posts) == 1
    assert len(videos) == 1
    assert posts[0].title == "IsoPost"
    assert videos[0].title == "IsoVideo"


@pytest.mark.asyncio
async def test_morphed_by_many_attach_with_dict(sqlite_db, mbm_tables):
    tag = await MbmTag.create({"name": "dictattach"})
    post = await MbmPost.create({"title": "DictPost"})
    await tag.posts().attach({post.id: {}})
    posts = await tag.posts().get()
    assert len(posts) == 1
