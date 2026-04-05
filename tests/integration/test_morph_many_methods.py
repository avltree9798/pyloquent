"""Integration tests for MorphMany helper methods: save, save_many, create_many, find, find_many, update, delete."""
import pytest
from typing import Optional
from pyloquent import Model
from pyloquent.orm.collection import Collection


class MmPost(Model):
    __table__ = "mm_posts"
    __fillable__ = ["title"]
    id: Optional[int] = None
    title: str

    def comments(self):
        return self.morph_many(MmComment, "commentable")


class MmVideo(Model):
    __table__ = "mm_videos"
    __fillable__ = ["title"]
    id: Optional[int] = None
    title: str

    def comments(self):
        return self.morph_many(MmComment, "commentable")


class MmComment(Model):
    __table__ = "mm_comments"
    __fillable__ = ["body", "commentable_type", "commentable_id"]
    id: Optional[int] = None
    body: str
    commentable_type: Optional[str] = None
    commentable_id: Optional[int] = None


@pytest.fixture
async def mm_tables(sqlite_db):
    conn = sqlite_db.connection()
    await conn.execute("""
        CREATE TABLE mm_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    await conn.execute("""
        CREATE TABLE mm_videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    await conn.execute("""
        CREATE TABLE mm_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            body TEXT NOT NULL,
            commentable_type TEXT,
            commentable_id INTEGER,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    yield


@pytest.mark.asyncio
async def test_morph_many_save(sqlite_db, mm_tables):
    post = await MmPost.create({"title": "P"})
    comment = MmComment(body="Saved", commentable_type="", commentable_id=0)
    saved = await post.comments().save(comment)
    assert saved.commentable_type == "MmPost"
    assert saved.commentable_id == post.id


@pytest.mark.asyncio
async def test_morph_many_save_many(sqlite_db, mm_tables):
    post = await MmPost.create({"title": "SaveMany"})
    c1 = MmComment(body="C1", commentable_type="", commentable_id=0)
    c2 = MmComment(body="C2", commentable_type="", commentable_id=0)
    result = await post.comments().save_many(Collection([c1, c2]))
    assert len(result) == 2
    assert all(c.commentable_id == post.id for c in result)


@pytest.mark.asyncio
async def test_morph_many_create_many(sqlite_db, mm_tables):
    post = await MmPost.create({"title": "CreateMany"})
    result = await post.comments().create_many([{"body": "A"}, {"body": "B"}])
    assert len(result) == 2
    assert all(c.commentable_type == "MmPost" for c in result)


@pytest.mark.asyncio
async def test_morph_many_find(sqlite_db, mm_tables):
    post = await MmPost.create({"title": "Find"})
    c = await post.comments().create({"body": "FindMe"})
    found = await post.comments().find(c.id)
    assert found is not None
    assert found.body == "FindMe"


@pytest.mark.asyncio
async def test_morph_many_find_many(sqlite_db, mm_tables):
    post = await MmPost.create({"title": "FM"})
    c1 = await post.comments().create({"body": "FM1"})
    c2 = await post.comments().create({"body": "FM2"})
    results = await post.comments().find_many([c1.id, c2.id])
    assert len(results) == 2


@pytest.mark.asyncio
async def test_morph_many_update(sqlite_db, mm_tables):
    post = await MmPost.create({"title": "U"})
    await post.comments().create({"body": "Old"})
    count = await post.comments().update({"body": "New"})
    assert count == 1
    comments = await post.comments().get()
    assert comments[0].body == "New"


@pytest.mark.asyncio
async def test_morph_many_delete(sqlite_db, mm_tables):
    post = await MmPost.create({"title": "D"})
    await post.comments().create({"body": "D1"})
    await post.comments().create({"body": "D2"})
    deleted = await post.comments().delete()
    assert deleted == 2
    assert len(await post.comments().get()) == 0


@pytest.mark.asyncio
async def test_morph_many_polymorphic_isolation(sqlite_db, mm_tables):
    post = await MmPost.create({"title": "PP"})
    video = await MmVideo.create({"title": "VV"})
    await post.comments().create({"body": "PostComment"})
    await video.comments().create({"body": "VideoComment"})
    post_comments = await post.comments().get()
    video_comments = await video.comments().get()
    assert len(post_comments) == 1
    assert len(video_comments) == 1
    assert post_comments[0].body == "PostComment"
    assert video_comments[0].body == "VideoComment"
