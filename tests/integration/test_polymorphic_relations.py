"""Integration tests for polymorphic relationships: MorphOne, MorphMany, MorphTo."""
import pytest
from typing import Optional
from pyloquent import Model


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class PolyPost(Model):
    __table__ = "poly_posts"
    __fillable__ = ["title"]
    id: Optional[int] = None
    title: str

    def image(self):
        return self.morph_one(PolyImage, "imageable")

    def comments(self):
        return self.morph_many(PolyComment, "commentable")


class PolyVideo(Model):
    __table__ = "poly_videos"
    __fillable__ = ["title"]
    id: Optional[int] = None
    title: str

    def image(self):
        return self.morph_one(PolyImage, "imageable")

    def comments(self):
        return self.morph_many(PolyComment, "commentable")


class PolyImage(Model):
    __table__ = "poly_images"
    __fillable__ = ["url", "imageable_type", "imageable_id"]
    id: Optional[int] = None
    url: str
    imageable_type: Optional[str] = None
    imageable_id: Optional[int] = None

    def imageable(self):
        return self.morph_to("imageable")


class PolyComment(Model):
    __table__ = "poly_comments"
    __fillable__ = ["body", "commentable_type", "commentable_id"]
    id: Optional[int] = None
    body: str
    commentable_type: Optional[str] = None
    commentable_id: Optional[int] = None

    def commentable(self):
        return self.morph_to("commentable")


@pytest.fixture
async def poly_tables(sqlite_db):
    conn = sqlite_db.connection()
    await conn.execute("""
        CREATE TABLE poly_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    await conn.execute("""
        CREATE TABLE poly_videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    await conn.execute("""
        CREATE TABLE poly_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            imageable_type TEXT,
            imageable_id INTEGER,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    await conn.execute("""
        CREATE TABLE poly_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            body TEXT NOT NULL,
            commentable_type TEXT,
            commentable_id INTEGER,
            created_at TIMESTAMP, updated_at TIMESTAMP
        )
    """)
    yield


# ---------------------------------------------------------------------------
# MorphOne
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_morph_one_get(sqlite_db, poly_tables):
    post = await PolyPost.create({"title": "Hello"})
    await post.image().create({"url": "img.jpg"})
    img = await post.image().get_results()
    assert img is not None
    assert img.url == "img.jpg"


@pytest.mark.asyncio
async def test_morph_one_create_sets_type_and_id(sqlite_db, poly_tables):
    post = await PolyPost.create({"title": "Typed"})
    img = await post.image().create({"url": "typed.png"})
    assert img.imageable_type == "PolyPost"
    assert img.imageable_id == post.id


@pytest.mark.asyncio
async def test_morph_one_save(sqlite_db, poly_tables):
    post = await PolyPost.create({"title": "Save"})
    img = PolyImage(url="saved.png", imageable_type="", imageable_id=0)
    saved = await post.image().save(img)
    assert saved.imageable_type == "PolyPost"
    assert saved.imageable_id == post.id


@pytest.mark.asyncio
async def test_morph_one_returns_none_when_absent(sqlite_db, poly_tables):
    post = await PolyPost.create({"title": "Empty"})
    img = await post.image().get_results()
    assert img is None


@pytest.mark.asyncio
async def test_morph_one_delete(sqlite_db, poly_tables):
    post = await PolyPost.create({"title": "DelTest"})
    await post.image().create({"url": "del.jpg"})
    deleted = await post.image().delete()
    assert deleted is True
    img = await post.image().get_results()
    assert img is None


@pytest.mark.asyncio
async def test_morph_one_delete_when_no_related(sqlite_db, poly_tables):
    post = await PolyPost.create({"title": "NoImg"})
    result = await post.image().delete()
    assert result is False


@pytest.mark.asyncio
async def test_morph_one_different_parent_types_isolated(sqlite_db, poly_tables):
    post  = await PolyPost.create({"title": "P"})
    video = await PolyVideo.create({"title": "V"})
    await post.image().create({"url": "post.jpg"})
    await video.image().create({"url": "video.jpg"})
    p_img = await post.image().get_results()
    v_img = await video.image().get_results()
    assert p_img.url == "post.jpg"
    assert v_img.url == "video.jpg"


# ---------------------------------------------------------------------------
# MorphMany
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_morph_many_get(sqlite_db, poly_tables):
    post = await PolyPost.create({"title": "Multi"})
    await PolyComment.create({"body": "c1", "commentable_type": "PolyPost", "commentable_id": post.id})
    await PolyComment.create({"body": "c2", "commentable_type": "PolyPost", "commentable_id": post.id})
    comments = await post.comments().get()
    assert len(comments) == 2


@pytest.mark.asyncio
async def test_morph_many_create(sqlite_db, poly_tables):
    post = await PolyPost.create({"title": "Create"})
    c = await post.comments().create({"body": "new"})
    assert c.commentable_type == "PolyPost"
    assert c.commentable_id == post.id


@pytest.mark.asyncio
async def test_morph_many_save(sqlite_db, poly_tables):
    post = await PolyPost.create({"title": "SaveMany"})
    c = PolyComment(body="saved", commentable_type="", commentable_id=0)
    saved = await post.comments().save(c)
    assert saved.commentable_type == "PolyPost"
    assert saved.commentable_id == post.id


@pytest.mark.asyncio
async def test_morph_many_different_parents_isolated(sqlite_db, poly_tables):
    post  = await PolyPost.create({"title": "P2"})
    video = await PolyVideo.create({"title": "V2"})
    await post.comments().create({"body": "post comment"})
    await video.comments().create({"body": "video comment"})
    pc = await post.comments().get()
    vc = await video.comments().get()
    assert len(pc) == 1
    assert len(vc) == 1
    assert pc[0].body == "post comment"
    assert vc[0].body == "video comment"


@pytest.mark.asyncio
async def test_morph_many_count(sqlite_db, poly_tables):
    post = await PolyPost.create({"title": "Cnt"})
    await post.comments().create({"body": "a"})
    await post.comments().create({"body": "b"})
    n = await post.comments().count()
    assert n == 2


@pytest.mark.asyncio
async def test_morph_many_delete(sqlite_db, poly_tables):
    post = await PolyPost.create({"title": "Del"})
    await post.comments().create({"body": "gone"})
    await post.comments().delete()
    remaining = await post.comments().get()
    assert len(remaining) == 0


# ---------------------------------------------------------------------------
# MorphTo (associate / dissociate / get_related_type / get_related_id)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_morph_to_associate(sqlite_db, poly_tables):
    post = await PolyPost.create({"title": "AssocPost"})
    img = PolyImage(url="assoc.jpg", imageable_type="", imageable_id=0)
    rel = img.imageable()
    rel.associate(post)
    assert img.imageable_type == "PolyPost"
    assert img.imageable_id == post.id


@pytest.mark.asyncio
async def test_morph_to_dissociate(sqlite_db, poly_tables):
    post = await PolyPost.create({"title": "Dissoc"})
    img = PolyImage(url="d.jpg", imageable_type="PolyPost", imageable_id=post.id)
    rel = img.imageable()
    rel.dissociate()
    assert img.imageable_type is None
    assert img.imageable_id is None


@pytest.mark.asyncio
async def test_morph_to_get_related_type(sqlite_db, poly_tables):
    post = await PolyPost.create({"title": "TypeGet"})
    img = PolyImage(url="t.jpg", imageable_type="PolyPost", imageable_id=post.id)
    assert img.imageable().get_related_type() == "PolyPost"


@pytest.mark.asyncio
async def test_morph_to_get_related_id(sqlite_db, poly_tables):
    post = await PolyPost.create({"title": "IdGet"})
    img = PolyImage(url="i.jpg", imageable_type="PolyPost", imageable_id=post.id)
    assert img.imageable().get_related_id() == post.id


@pytest.mark.asyncio
async def test_morph_to_get_results_returns_none_when_no_type(sqlite_db, poly_tables):
    img = PolyImage(url="x.jpg", imageable_type=None, imageable_id=None)
    result = await img.imageable().get_results()
    assert result is None
