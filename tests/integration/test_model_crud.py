"""Integration tests for Model CRUD operations."""

import pytest

from pyloquent import ConnectionManager, Model
from pydantic import EmailStr


class User(Model):
    """Test User model."""

    __table__ = "users"
    __fillable__ = ["name", "email", "age", "is_active"]

    id: int | None = None
    name: str
    email: str
    age: int | None = None
    is_active: bool = True


class Post(Model):
    """Test Post model."""

    __table__ = "posts"
    __fillable__ = ["user_id", "title", "content", "is_published"]

    id: int | None = None
    user_id: int
    title: str
    content: str | None = None
    is_published: bool = False


@pytest.mark.asyncio
async def test_create_model(sqlite_db, setup_tables):
    """Test creating a model."""
    # Configure the connection
    User.__connection__ = "default"

    user = await User.create({"name": "John Doe", "email": "john@example.com", "age": 25})

    assert user.id is not None
    assert user.name == "John Doe"
    assert user.email == "john@example.com"
    assert user.age == 25


@pytest.mark.asyncio
async def test_find_model(sqlite_db, setup_tables):
    """Test finding a model by ID."""
    # Create a user first
    user = await User.create({"name": "Jane Doe", "email": "jane@example.com", "age": 30})

    # Find the user
    found = await User.find(user.id)

    assert found is not None
    assert found.id == user.id
    assert found.name == "Jane Doe"


@pytest.mark.asyncio
async def test_find_nonexistent_model(sqlite_db, setup_tables):
    """Test finding a non-existent model."""
    found = await User.find(9999)

    assert found is None


@pytest.mark.asyncio
async def test_find_or_fail(sqlite_db, setup_tables):
    """Test find_or_fail."""
    from pyloquent.exceptions import ModelNotFoundException

    # Create a user
    user = await User.create({"name": "Test User", "email": "test@example.com"})

    # Find should work
    found = await User.find_or_fail(user.id)
    assert found.id == user.id

    # Non-existent should raise
    with pytest.raises(ModelNotFoundException):
        await User.find_or_fail(9999)


@pytest.mark.asyncio
async def test_update_model(sqlite_db, setup_tables):
    """Test updating a model."""
    # Create a user
    user = await User.create({"name": "Original Name", "email": "original@example.com"})

    # Update
    user.name = "Updated Name"
    await user.save()

    # Refresh and verify
    refreshed = await User.find(user.id)
    assert refreshed.name == "Updated Name"


@pytest.mark.asyncio
async def test_delete_model(sqlite_db, setup_tables):
    """Test deleting a model."""
    # Create a user
    user = await User.create({"name": "To Delete", "email": "delete@example.com"})
    user_id = user.id

    # Delete
    result = await user.delete()

    assert result is True

    # Verify deleted
    found = await User.find(user_id)
    assert found is None


@pytest.mark.asyncio
async def test_query_where(sqlite_db, setup_tables):
    """Test querying with where clauses."""
    # Create users
    await User.create({"name": "Active User", "email": "active@example.com", "is_active": True})
    await User.create(
        {"name": "Inactive User", "email": "inactive@example.com", "is_active": False}
    )

    # Query active users
    active_users = await User.where("is_active", True).get()

    assert len(active_users) == 1
    assert active_users.first().name == "Active User"


@pytest.mark.asyncio
async def test_query_where_in(sqlite_db, setup_tables):
    """Test querying with where_in."""
    # Create users
    user1 = await User.create({"name": "User 1", "email": "user1@example.com"})
    user2 = await User.create({"name": "User 2", "email": "user2@example.com"})
    await User.create({"name": "User 3", "email": "user3@example.com"})

    # Query with where_in
    users = await User.where_in("id", [user1.id, user2.id]).get()

    assert len(users) == 2


@pytest.mark.asyncio
async def test_query_order_by(sqlite_db, setup_tables):
    """Test ordering results."""
    # Create users
    await User.create({"name": "Charlie", "email": "charlie@example.com"})
    await User.create({"name": "Alice", "email": "alice@example.com"})
    await User.create({"name": "Bob", "email": "bob@example.com"})

    # Order by name
    users = await User.order_by("name", "asc").get()

    assert users.nth(0).name == "Alice"
    assert users.nth(1).name == "Bob"
    assert users.nth(2).name == "Charlie"


@pytest.mark.asyncio
async def test_query_limit(sqlite_db, setup_tables):
    """Test limiting results."""
    # Create users
    for i in range(10):
        await User.create({"name": f"User {i}", "email": f"user{i}@example.com"})

    # Limit to 5
    users = await User.limit(5).get()

    assert len(users) == 5


@pytest.mark.asyncio
async def test_query_first(sqlite_db, setup_tables):
    """Test getting first result."""
    # Create users
    await User.create({"name": "First User", "email": "first@example.com"})
    await User.create({"name": "Second User", "email": "second@example.com"})

    # Get first
    first = await User.where("is_active", True).first()

    assert first is not None
    assert first.name == "First User"


@pytest.mark.asyncio
async def test_query_count(sqlite_db, setup_tables):
    """Test counting results."""
    # Create users
    for i in range(5):
        await User.create({"name": f"User {i}", "email": f"user{i}@example.com"})

    # Count
    count = await User.count()

    assert count == 5


@pytest.mark.asyncio
async def test_query_pluck(sqlite_db, setup_tables):
    """Test plucking values."""
    # Create users
    await User.create({"name": "Alice", "email": "alice@example.com"})
    await User.create({"name": "Bob", "email": "bob@example.com"})

    # Pluck names
    names = await User.pluck("name")

    assert "Alice" in names
    assert "Bob" in names


@pytest.mark.asyncio
async def test_first_or_create(sqlite_db, setup_tables):
    """Test first_or_create."""
    # First call should create
    user1 = await User.first_or_create(
        {"email": "unique@example.com"}, {"name": "Unique User", "email": "unique@example.com"}
    )

    assert user1.id is not None
    assert user1.name == "Unique User"

    # Second call should find existing
    user2 = await User.first_or_create(
        {"email": "unique@example.com"}, {"name": "Different Name", "email": "unique@example.com"}
    )

    assert user2.id == user1.id
    assert user2.name == "Unique User"  # Should not be updated


@pytest.mark.asyncio
async def test_update_or_create(sqlite_db, setup_tables):
    """Test update_or_create."""
    # First call should create
    user1 = await User.update_or_create(
        {"email": "update_or_create@example.com"},
        {"name": "Original Name", "email": "update_or_create@example.com"},
    )

    assert user1.id is not None

    # Second call should update
    user2 = await User.update_or_create(
        {"email": "update_or_create@example.com"}, {"name": "Updated Name"}
    )

    assert user2.id == user1.id
    assert user2.name == "Updated Name"
