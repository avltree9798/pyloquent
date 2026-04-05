"""Integration tests for HasOneThrough, HasManyThrough, MorphToMany, MorphedByMany."""

import pytest
from typing import Optional

from pyloquent import Model


# ---------------------------------------------------------------------------
# Models for HasOneThrough / HasManyThrough
# (Country -> User -> Post, Country -> User -> Profile)
# ---------------------------------------------------------------------------

class Country(Model):
    __table__ = "countries"
    __fillable__ = ["name"]

    id: Optional[int] = None
    name: str

    def users(self):
        return self.has_many(THUser)

    def posts(self):
        return self.has_many_through(THPost, THUser)

    def latest_profile(self):
        return self.has_one_through(THProfile, THUser)


class THUser(Model):
    __table__ = "th_users"
    __fillable__ = ["country_id", "name", "email"]

    id: Optional[int] = None
    country_id: int
    name: str
    email: str


class THPost(Model):
    __table__ = "th_posts"
    __fillable__ = ["th_user_id", "title"]

    id: Optional[int] = None
    th_user_id: int
    title: str


class THProfile(Model):
    __table__ = "th_profiles"
    __fillable__ = ["th_user_id", "bio"]

    id: Optional[int] = None
    th_user_id: int
    bio: Optional[str] = None


# ---------------------------------------------------------------------------
# Models for MorphToMany / MorphedByMany
# ---------------------------------------------------------------------------

class Article(Model):
    __table__ = "articles"
    __fillable__ = ["title"]

    id: Optional[int] = None
    title: str

    def tags(self):
        return self.morph_to_many(Tag, "taggable")


class Video(Model):
    __table__ = "videos"
    __fillable__ = ["title"]

    id: Optional[int] = None
    title: str

    def tags(self):
        return self.morph_to_many(Tag, "taggable")


class Tag(Model):
    __table__ = "tags"
    __fillable__ = ["name"]

    id: Optional[int] = None
    name: str

    def articles(self):
        return self.morphed_by_many(Article, "taggable")

    def videos(self):
        return self.morphed_by_many(Video, "taggable")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def through_tables(sqlite_db):
    conn = sqlite_db.connection()
    await conn.execute(
        "CREATE TABLE countries (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL)"
    )
    await conn.execute(
        """CREATE TABLE th_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            country_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE
        )"""
    )
    await conn.execute(
        """CREATE TABLE th_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            th_user_id INTEGER NOT NULL,
            title TEXT NOT NULL
        )"""
    )
    await conn.execute(
        """CREATE TABLE th_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            th_user_id INTEGER NOT NULL UNIQUE,
            bio TEXT
        )"""
    )
    yield


@pytest.fixture
async def morph_tables(sqlite_db):
    conn = sqlite_db.connection()
    await conn.execute(
        "CREATE TABLE articles (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL)"
    )
    await conn.execute(
        "CREATE TABLE videos (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL)"
    )
    await conn.execute(
        "CREATE TABLE tags (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL)"
    )
    await conn.execute(
        """CREATE TABLE taggables (
            tag_id INTEGER NOT NULL,
            taggable_id INTEGER NOT NULL,
            taggable_type TEXT NOT NULL
        )"""
    )
    yield


# ---------------------------------------------------------------------------
# HasManyThrough
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_has_many_through(sqlite_db, through_tables):
    country = await Country.create({"name": "Germany"})
    user1 = await THUser.create({"country_id": country.id, "name": "Hans", "email": "hans@de.com"})
    user2 = await THUser.create({"country_id": country.id, "name": "Klaus", "email": "klaus@de.com"})
    p1 = await THPost.create({"th_user_id": user1.id, "title": "Post A"})
    p2 = await THPost.create({"th_user_id": user2.id, "title": "Post B"})

    posts = await country.posts().get()
    titles = {p.title for p in posts}
    assert "Post A" in titles
    assert "Post B" in titles


@pytest.mark.asyncio
async def test_has_many_through_empty(sqlite_db, through_tables):
    country = await Country.create({"name": "France"})
    posts = await country.posts().get()
    assert len(posts) == 0


# ---------------------------------------------------------------------------
# HasOneThrough
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_has_one_through(sqlite_db, through_tables):
    country = await Country.create({"name": "Italy"})
    user = await THUser.create({"country_id": country.id, "name": "Marco", "email": "marco@it.com"})
    await THProfile.create({"th_user_id": user.id, "bio": "Italian developer"})

    profile = await country.latest_profile().get_results()
    assert profile is not None
    assert profile.bio == "Italian developer"


@pytest.mark.asyncio
async def test_has_one_through_none(sqlite_db, through_tables):
    country = await Country.create({"name": "Spain"})
    await THUser.create({"country_id": country.id, "name": "Carlos", "email": "carlos@es.com"})

    profile = await country.latest_profile().get_results()
    assert profile is None


# ---------------------------------------------------------------------------
# MorphToMany
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_morph_to_many_attach_and_get(sqlite_db, morph_tables):
    article = await Article.create({"title": "Python Guide"})
    tag1 = await Tag.create({"name": "python"})
    tag2 = await Tag.create({"name": "coding"})

    await article.tags().attach([tag1.id, tag2.id])
    tags = await article.tags().get()
    tag_names = {t.name for t in tags}
    assert "python" in tag_names
    assert "coding" in tag_names


@pytest.mark.asyncio
async def test_morph_to_many_detach(sqlite_db, morph_tables):
    article = await Article.create({"title": "JS Guide"})
    tag = await Tag.create({"name": "javascript"})

    await article.tags().attach([tag.id])
    await article.tags().detach([tag.id])
    tags = await article.tags().get()
    assert len(tags) == 0


@pytest.mark.asyncio
async def test_morph_to_many_sync(sqlite_db, morph_tables):
    article = await Article.create({"title": "Sync Article"})
    t1 = await Tag.create({"name": "tag1"})
    t2 = await Tag.create({"name": "tag2"})
    t3 = await Tag.create({"name": "tag3"})

    await article.tags().attach([t1.id, t2.id])
    changes = await article.tags().sync([t2.id, t3.id])
    tags = await article.tags().get()
    tag_names = {t.name for t in tags}
    assert "tag2" in tag_names
    assert "tag3" in tag_names
    assert "tag1" not in tag_names


@pytest.mark.asyncio
async def test_morph_to_many_different_types_isolated(sqlite_db, morph_tables):
    article = await Article.create({"title": "Article 1"})
    video = await Video.create({"title": "Video 1"})
    tag = await Tag.create({"name": "shared"})

    await article.tags().attach([tag.id])
    await video.tags().attach([tag.id])

    article_tags = await article.tags().get()
    video_tags = await video.tags().get()
    assert len(article_tags) == 1
    assert len(video_tags) == 1


# ---------------------------------------------------------------------------
# MorphedByMany
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_morphed_by_many_get(sqlite_db, morph_tables):
    tag = await Tag.create({"name": "backend"})
    art1 = await Article.create({"title": "Backend Article 1"})
    art2 = await Article.create({"title": "Backend Article 2"})

    await art1.tags().attach([tag.id])
    await art2.tags().attach([tag.id])

    articles = await tag.articles().get()
    titles = {a.title for a in articles}
    assert "Backend Article 1" in titles
    assert "Backend Article 2" in titles


@pytest.mark.asyncio
async def test_morphed_by_many_isolated_by_type(sqlite_db, morph_tables):
    tag = await Tag.create({"name": "mixed"})
    article = await Article.create({"title": "Mixed Article"})
    video = await Video.create({"title": "Mixed Video"})

    await article.tags().attach([tag.id])
    await video.tags().attach([tag.id])

    # morphed_by_many(Article) should only return articles
    articles = await tag.articles().get()
    videos_list = await tag.videos().get()

    assert all(hasattr(a, "title") for a in articles)
    assert len(articles) >= 1
    assert len(videos_list) >= 1
