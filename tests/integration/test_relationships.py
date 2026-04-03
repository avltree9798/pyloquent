"""Integration tests for relationships."""

import pytest

from pyloquent import Model


class User(Model):
    """Test User model."""

    __table__ = "users"
    __fillable__ = ["name", "email"]

    id: int | None = None
    name: str
    email: str

    def posts(self):
        return self.has_many(Post)

    def profile(self):
        return self.has_one(Profile)


class Post(Model):
    """Test Post model."""

    __table__ = "posts"
    __fillable__ = ["user_id", "title", "content"]

    id: int | None = None
    user_id: int
    title: str
    content: str | None = None

    def author(self):
        return self.belongs_to(User)


class Profile(Model):
    """Test Profile model."""

    __table__ = "profiles"
    __fillable__ = ["user_id", "bio", "website"]

    id: int | None = None
    user_id: int
    bio: str | None = None
    website: str | None = None

    def user(self):
        return self.belongs_to(User)


@pytest.mark.asyncio
async def test_has_many_relationship(sqlite_db, setup_tables):
    """Test has-many relationship."""
    # Create user with posts
    user = await User.create({"name": "Test User", "email": "test@example.com"})

    # Create posts
    await Post.create({"user_id": user.id, "title": "Post 1", "content": "Content 1"})
    await Post.create({"user_id": user.id, "title": "Post 2", "content": "Content 2"})
    await Post.create({"user_id": user.id, "title": "Post 3", "content": "Content 3"})

    # Get posts through relationship
    posts = await user.posts().get()

    assert len(posts) == 3


@pytest.mark.asyncio
async def test_has_one_relationship(sqlite_db, setup_tables):
    """Test has-one relationship."""
    # Create user with profile
    user = await User.create({"name": "Test User", "email": "test@example.com"})
    await Profile.create({"user_id": user.id, "bio": "Test bio", "website": "https://example.com"})

    # Get profile through relationship
    profile = await user.profile().get()

    assert profile is not None
    assert profile.bio == "Test bio"


@pytest.mark.asyncio
async def test_belongs_to_relationship(sqlite_db, setup_tables):
    """Test belongs-to relationship."""
    # Create user and post
    user = await User.create({"name": "Author", "email": "author@example.com"})
    post = await Post.create({"user_id": user.id, "title": "Test Post", "content": "Content"})

    # Get author through relationship
    author = await post.author().get()

    assert author is not None
    assert author.name == "Author"


@pytest.mark.asyncio
async def test_has_many_create(sqlite_db, setup_tables):
    """Test creating through has-many relationship."""
    user = await User.create({"name": "Test User", "email": "test@example.com"})

    # Create post through relationship
    post = await user.posts().create({"title": "New Post", "content": "New content"})

    assert post.id is not None
    assert post.user_id == user.id
    assert post.title == "New Post"


@pytest.mark.asyncio
async def test_has_one_create(sqlite_db, setup_tables):
    """Test creating through has-one relationship."""
    user = await User.create({"name": "Test User", "email": "test@example.com"})

    # Create profile through relationship
    profile = await user.profile().create({"bio": "New bio"})

    assert profile.id is not None
    assert profile.user_id == user.id
    assert profile.bio == "New bio"


@pytest.mark.asyncio
async def test_belongs_to_associate(sqlite_db, setup_tables):
    """Test associating through belongs-to relationship."""
    # Create user first
    user = await User.create({"name": "New Author", "email": "new@example.com"})

    # Create post with that user
    post = await Post.create({"user_id": user.id, "title": "Test Post"})

    # Create another user
    new_user = await User.create({"name": "Another Author", "email": "another@example.com"})

    # Associate new user to post
    await post.author().associate(new_user)

    # Verify
    refreshed = await Post.find(post.id)
    assert refreshed.user_id == new_user.id


@pytest.mark.asyncio
async def test_load_relations(sqlite_db, setup_tables):
    """Test lazy loading relations on existing model."""
    user = await User.create({"name": "Test User", "email": "test@example.com"})
    await Post.create({"user_id": user.id, "title": "Post 1"})
    await Post.create({"user_id": user.id, "title": "Post 2"})

    # Load relations
    await user.load("posts")

    # Should be able to access posts synchronously
    posts = user.get_relation("posts")
    assert posts is not None
    assert len(posts) == 2


@pytest.mark.asyncio
async def test_has_many_count(sqlite_db, setup_tables):
    """Test counting through has-many relationship."""
    user = await User.create({"name": "Test User", "email": "test@example.com"})
    await Post.create({"user_id": user.id, "title": "Post 1"})
    await Post.create({"user_id": user.id, "title": "Post 2"})

    count = await user.posts().count()

    assert count == 2


@pytest.mark.asyncio
async def test_relation_chaining(sqlite_db, setup_tables):
    """Test chaining query methods on relationships."""
    user = await User.create({"name": "Test User", "email": "test@example.com"})
    await Post.create({"user_id": user.id, "title": "First Post"})
    await Post.create({"user_id": user.id, "title": "Second Post"})
    await Post.create({"user_id": user.id, "title": "Third Post"})

    # Chain limit
    posts = await user.posts().limit(2).get()

    assert len(posts) == 2

    # Chain order
    posts = await user.posts().order_by("title", "asc").get()
    assert posts.first().title == "First Post"
