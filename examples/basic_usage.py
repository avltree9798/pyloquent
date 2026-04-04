"""Basic usage example for Pyloquent."""

import asyncio
from datetime import datetime
from typing import Optional

from pyloquent import ConnectionManager, Model
from pyloquent.database.manager import set_manager


# Configure connection manager
manager = ConnectionManager()


class User(Model):
    """User model example."""

    __table__ = "users"
    __fillable__ = ["name", "email", "is_active"]

    id: Optional[int] = None
    name: str
    email: str
    is_active: bool = True


class Post(Model):
    """Post model example."""

    __table__ = "posts"
    __fillable__ = ["user_id", "title", "content", "is_published"]

    id: Optional[int] = None
    user_id: int
    title: str
    content: Optional[str] = None
    is_published: bool = False

    def author(self):
        return self.belongs_to(User)


async def setup_database():
    """Set up in-memory database with test tables."""
    manager.add_connection(
        "default",
        {
            "driver": "sqlite",
            "database": ":memory:",
        },
        default=True,
    )

    set_manager(manager)
    await manager.connect()

    # Create tables
    conn = manager.connection()
    await conn.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    await conn.execute(
        """
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT,
            is_published BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """
    )


async def create_users():
    """Create some example users."""
    print("=== Creating Users ===")

    users_data = [
        {"name": "Alice Johnson", "email": "alice@example.com"},
        {"name": "Bob Smith", "email": "bob@example.com"},
        {"name": "Charlie Brown", "email": "charlie@example.com", "is_active": False},
    ]

    created_users = []
    for data in users_data:
        user = await User.create(data)
        created_users.append(user)
        print(f"Created user: {user.name} (ID: {user.id})")

    return created_users


async def query_examples():
    """Demonstrate query builder examples."""
    print("\n=== Query Examples ===")

    # Get all users
    all_users = await User.all()
    print(f"Total users: {all_users.count()}")

    # Find specific user
    alice = await User.where("email", "alice@example.com").first()
    if alice:
        print(f"Found: {alice.name}")

    # Active users only
    active_users = await User.where("is_active", True).get()
    print(f"Active users: {active_users.count()}")

    # Complex query
    users = await User.where("is_active", True).order_by("name").get()
    print("Active users sorted by name:")
    for user in users:
        print(f"  - {user.name}")


async def crud_examples(users):
    """Demonstrate CRUD operations."""
    print("\n=== CRUD Examples ===")

    # Update
    alice = users[0]
    alice.name = "Alice Updated"
    await alice.save()
    print(f"Updated user: {alice.name}")

    # Find and update
    bob = await User.find(users[1].id)
    if bob:
        bob.is_active = False
        await bob.save()
        print(f"Deactivated user: {bob.name}")

    # Delete
    charlie = users[2]
    await charlie.delete()
    print(f"Deleted user: {charlie.name}")

    # Verify deletion
    remaining = await User.count()
    print(f"Remaining users: {remaining}")


async def relationship_examples():
    """Demonstrate relationships."""
    print("\n=== Relationship Examples ===")

    # Create user with posts
    user = await User.create({"name": "John Doe", "email": "john@example.com"})

    # Create posts
    posts_data = [
        {"user_id": user.id, "title": "First Post", "content": "This is my first post!"},
        {"user_id": user.id, "title": "Second Post", "content": "Another day, another post."},
        {
            "user_id": user.id,
            "title": "Published Post",
            "content": "This one is published!",
            "is_published": True,
        },
    ]

    for data in posts_data:
        post = await Post.create(data)
        print(f"Created post: {post.title}")

    # Get user's posts
    user_posts = await Post.where("user_id", user.id).get()
    print(f"\nUser has {user_posts.count()} posts")

    # Get published posts only
    published = await Post.where("user_id", user.id).where("is_published", True).get()
    print(f"Published posts: {published.count()}")

    # Get post with author
    post = await Post.first()
    if post:
        author = await post.author().get()
        if author:
            print(f"\nPost '{post.title}' by {author.name}")


async def aggregate_examples():
    """Demonstrate aggregate functions."""
    print("\n=== Aggregate Examples ===")

    # Create some posts with view counts
    user = await User.first()
    if user:
        await Post.create(
            {"user_id": user.id, "title": "Popular Post", "content": "Lots of views"}
        )
        await Post.create(
            {"user_id": user.id, "title": "Another Post", "content": "Some views"}
        )

    # Count
    total_posts = await Post.count()
    print(f"Total posts: {total_posts}")

    # Count with where
    published_count = await Post.where("is_published", True).count()
    print(f"Published posts: {published_count}")


async def transaction_example():
    """Demonstrate transactions."""
    print("\n=== Transaction Example ===")

    try:
        async with manager.transaction() as conn:
            # These operations will be atomic
            user = await User.create({"name": "Transaction User", "email": "tx@example.com"})
            await Post.create(
                {"user_id": user.id, "title": "Transactional Post", "content": "Created in transaction"}
            )
            print("Transaction committed successfully")
    except Exception as e:
        print(f"Transaction failed: {e}")


async def main():
    """Run all examples."""
    print("Pyloquent Basic Usage Examples")
    print("=" * 40)

    await setup_database()

    users = await create_users()
    await query_examples()
    await crud_examples(users)
    await relationship_examples()
    await aggregate_examples()
    await transaction_example()

    print("\n" + "=" * 40)
    print("Examples completed!")

    # Cleanup
    await manager.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
