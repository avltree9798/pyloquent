"""Comprehensive usage examples for Pyloquent."""

import asyncio
from datetime import datetime
from typing import Optional

from pyloquent import ConnectionManager, Model, SoftDeletes
from pyloquent.database.manager import set_manager


# Configure connection manager
manager = ConnectionManager()


class User(Model):
    """User model example."""

    __table__ = "users"
    __fillable__ = ["name", "email", "score", "is_active"]
    __hidden__ = ["score"]
    __per_page__ = 10

    id: Optional[int] = None
    name: str
    email: str
    score: int = 0
    is_active: bool = True

    def posts(self):
        return self.has_many(Post)


class Post(Model):
    """Post model example."""

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
            email TEXT NOT NULL UNIQUE,
            score INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            views INTEGER DEFAULT 0,
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
        {"name": "Alice Johnson", "email": "alice@example.com", "score": 80},
        {"name": "Bob Smith", "email": "bob@example.com", "score": 60},
        {"name": "Charlie Brown", "email": "charlie@example.com", "score": 40, "is_active": False},
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

    alice = users[0]
    alice.name = "Alice Updated"
    await alice.save()
    print(f"Updated user: {alice.name}")

    bob = await User.find(users[1].id)
    if bob:
        bob.is_active = False
        await bob.save()
        print(f"Deactivated user: {bob.name}")

    charlie = users[2]
    await charlie.delete()
    print(f"Deleted user: {charlie.name}")

    remaining = await User.count()
    print(f"Remaining users: {remaining}")


async def relationship_examples():
    """Demonstrate relationships."""
    print("\n=== Relationship Examples ===")

    user = await User.create({"name": "John Doe", "email": "john@example.com"})

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

    user_posts = await Post.where("user_id", user.id).get()
    print(f"\nUser has {user_posts.count()} posts")

    published = await Post.where("user_id", user.id).where("is_published", True).get()
    print(f"Published posts: {published.count()}")

    post = await Post.first()
    if post:
        author = await post.author().get()
        if author:
            print(f"\nPost '{post.title}' by {author.name}")


async def aggregate_examples():
    """Demonstrate aggregate functions."""
    print("\n=== Aggregate Examples ===")

    user = await User.first()
    if user:
        await Post.create(
            {"user_id": user.id, "title": "Popular Post", "content": "Lots of views"}
        )
        await Post.create(
            {"user_id": user.id, "title": "Another Post", "content": "Some views"}
        )

    total_posts = await Post.count()
    print(f"Total posts: {total_posts}")

    published_count = await Post.where("is_published", True).count()
    print(f"Published posts: {published_count}")


async def transaction_example():
    """Demonstrate transactions."""
    print("\n=== Transaction Example ===")

    try:
        async with manager.transaction() as conn:
            user = await User.create({"name": "Transaction User", "email": "tx@example.com"})
            await Post.create(
                {"user_id": user.id, "title": "Transactional Post", "content": "Created in transaction"}
            )
            print("Transaction committed successfully")
    except Exception as e:
        print(f"Transaction failed: {e}")


# ---------------------------------------------------------------------------
# New feature demonstrations
# ---------------------------------------------------------------------------

async def increment_decrement_examples():
    """Demonstrate atomic increment / decrement."""
    print("\n=== Increment / Decrement ===")

    user = await User.create({"name": "Score Tracker", "email": "score@example.com", "score": 10})

    # Instance-level
    await user.increment("score", 5)
    refreshed = await User.find(user.id)
    print(f"After increment: score = {refreshed.score}")  # 15

    await user.decrement("score", 3)
    refreshed = await User.find(user.id)
    print(f"After decrement: score = {refreshed.score}")  # 12

    # Query-level (bulk)
    await User.where("is_active", True).increment("score", 1)
    print("Incremented all active users' scores by 1")


async def upsert_examples():
    """Demonstrate upsert and insert_or_ignore."""
    print("\n=== Upsert / Insert-or-Ignore ===")

    # insert_or_ignore: duplicate email is silently skipped
    await User.create({"name": "Existing", "email": "exist@example.com"})
    await User.query.insert_or_ignore([{"name": "Duplicate", "email": "exist@example.com"}])
    count = await User.where("email", "exist@example.com").count()
    print(f"insert_or_ignore kept exactly 1 row: {count == 1}")

    # upsert: insert new or update on conflict
    await User.query.upsert(
        [{"name": "Upsert User", "email": "upsert@example.com", "score": 100}],
        unique_by=["email"],
        update_columns=["name", "score"],
    )
    u = await User.where("email", "upsert@example.com").first()
    print(f"Upserted user score: {u.score}")  # 100

    # run again → should UPDATE
    await User.query.upsert(
        [{"name": "Upsert User v2", "email": "upsert@example.com", "score": 200}],
        unique_by=["email"],
        update_columns=["name", "score"],
    )
    u = await User.where("email", "upsert@example.com").first()
    print(f"After second upsert score: {u.score}")  # 200


async def conditional_query_examples():
    """Demonstrate when / unless / tap."""
    print("\n=== Conditional Queries (when / unless / tap) ===")

    # when: only filter when condition is truthy
    search_active_only = True
    results = await (
        User.query
        .when(search_active_only, lambda q: q.where("is_active", True))
        .get()
    )
    print(f"when(True)  → {results.count()} active users")

    results2 = await (
        User.query
        .when(False, lambda q: q.where("is_active", True))
        .get()
    )
    print(f"when(False) → {results2.count()} total users (no filter applied)")

    # unless: only filter when condition is falsy
    skip_filter = False
    results3 = await (
        User.query
        .unless(skip_filter, lambda q: q.where("is_active", True))
        .get()
    )
    print(f"unless(False) → {results3.count()} active users")

    # tap: side-effect without modifying query
    tables_seen = []
    await (
        User.query
        .tap(lambda q: tables_seen.append(q._table))
        .get()
    )
    print(f"tap() saw table: {tables_seen[0]}")


async def where_exists_examples():
    """Demonstrate where_exists / where_not_exists."""
    print("\n=== WHERE EXISTS / NOT EXISTS ===")

    # Users who have at least one post
    with_posts = await User.where_exists(
        lambda q: q.from_("posts").where_raw('"posts"."user_id" = "users"."id"')
    ).get()
    print(f"Users with posts: {with_posts.count()}")

    # Users who have no posts
    without_posts = await User.where_not_exists(
        lambda q: q.from_("posts").where_raw('"posts"."user_id" = "users"."id"')
    ).get()
    print(f"Users without posts: {without_posts.count()}")


async def pagination_examples():
    """Demonstrate paginate / simple_paginate / cursor."""
    print("\n=== Pagination ===")

    # paginate() returns dict with metadata
    page = await User.paginate(per_page=3, page=1)
    print(f"paginate: {len(page['data'])} items, total={page['total']}, last_page={page['last_page']}")

    # simple_paginate() – cheaper, no COUNT(*)
    simple = await User.simple_paginate(per_page=3, page=1)
    print(f"simple_paginate: {len(simple['data'])} items")

    # cursor() – memory-efficient streaming
    print("cursor iteration: ", end="")
    async for user in User.query.cursor():
        print(user.name.split()[0], end=" ")
    print()


async def lock_examples():
    """Demonstrate lock_for_update / for_share (SQL-level only; SQLite ignores)."""
    print("\n=== Row Locking (SQL) ===")

    from pyloquent.grammars.grammar import Grammar
    from pyloquent.grammars.sqlite_grammar import SQLiteGrammar
    from pyloquent.query.builder import QueryBuilder

    g = SQLiteGrammar()
    sql_update, _ = QueryBuilder(g).from_("users").where("id", 1).lock_for_update().to_sql()
    sql_share, _ = QueryBuilder(g).from_("users").where("id", 1).for_share().to_sql()
    print(f"lock_for_update SQL: {sql_update}")
    print(f"for_share       SQL: {sql_share}")
    print("(SQLite silently omits FOR UPDATE / FOR SHARE)")


async def to_raw_sql_examples():
    """Demonstrate to_raw_sql for debugging."""
    print("\n=== to_raw_sql ===")

    from pyloquent.query.builder import QueryBuilder
    from pyloquent.grammars.sqlite_grammar import SQLiteGrammar

    raw = (
        QueryBuilder(SQLiteGrammar())
        .from_("users")
        .where("is_active", True)
        .where("score", ">", 50)
        .order_by("name")
        .limit(10)
        .to_raw_sql()
    )
    print(f"Raw SQL: {raw}")


async def collection_advanced_examples():
    """Demonstrate advanced Collection methods."""
    print("\n=== Collection Advanced Methods ===")

    users = await User.all()

    # group_by
    groups = users.group_by("is_active")
    for key, grp in groups.items():
        print(f"  is_active={key}: {grp.count()} users")

    # partition
    active, inactive = users.partition(lambda u: u.is_active)
    print(f"partition → active={active.count()}, inactive={inactive.count()}")

    # is_empty / is_not_empty
    print(f"is_empty: {users.is_empty()}, is_not_empty: {users.is_not_empty()}")

    # contains
    names = [u.name for u in users]
    print(f"contains 'John Doe': {users.contains('name', 'John Doe')}")

    # reduce
    total_score = users.reduce(lambda carry, u: carry + u.score, 0)
    print(f"Total score (reduce): {total_score}")

    # median / mode
    scores = [u.score for u in users if u.score > 0]
    from pyloquent.orm.collection import Collection
    score_col = Collection(scores)
    print(f"Score median: {score_col.median()}, mode: {score_col.mode()}")

    # take / skip / take_while
    first_two = users.take(2)
    print(f"take(2): {[u.name for u in first_two]}")

    # sort_by / sort_by_desc
    sorted_asc = users.sort_by("name")
    sorted_desc = users.sort_by_desc("name")
    print(f"sort_by name asc first: {sorted_asc.first().name}")
    print(f"sort_by name desc first: {sorted_desc.first().name}")

    # when / unless on collection
    filtered = users.when(True, lambda c: c.filter(lambda u: u.is_active))
    print(f"collection.when(True, filter_active): {filtered.count()} users")

    # to_json
    import json
    sample = users.take(1).only("name", "email")
    print(f"to_json sample: {sample.to_json()}")


async def model_instance_examples():
    """Demonstrate model instance methods."""
    print("\n=== Model Instance Methods ===")

    user = await User.create({"name": "Instance User", "email": "instance@example.com", "score": 5})

    # make_visible overrides __hidden__
    user.make_visible("score")
    d = user.to_dict()
    print(f"make_visible('score') → score in dict: {'score' in d}")

    # make_hidden
    user.make_hidden("name")
    d2 = user.to_dict()
    print(f"make_hidden('name')   → name in dict: {'name' in d2}")

    # get_key / get_key_name
    print(f"get_key(): {user.get_key()}, get_key_name(): {user.get_key_name()}")

    # was_changed / get_changes
    user.name = "Instance User Updated"
    await user.save()
    print(f"was_changed('name'): {user.was_changed('name')}")
    print(f"get_changes(): {list(user.get_changes().keys())}")

    # replicate
    replica = await user.replicate({"email": "replica@example.com"})
    print(f"replicate → new id={replica.id}, name={replica.name}")

    # json()
    import json
    parsed = json.loads(user.json())
    print(f"json() → keys: {list(parsed.keys())}")


async def find_many_destroy_examples():
    """Demonstrate find_many and destroy."""
    print("\n=== find_many / destroy ===")

    u1 = await User.create({"name": "FindMe1", "email": "fm1@example.com"})
    u2 = await User.create({"name": "FindMe2", "email": "fm2@example.com"})

    found = await User.find_many([u1.id, u2.id])
    print(f"find_many([{u1.id}, {u2.id}]) → {found.count()} users")

    await User.destroy(u1.id, u2.id)
    remaining = await User.find_many([u1.id, u2.id])
    print(f"After destroy → {remaining.count()} users remaining")


async def main():
    """Run all examples."""
    print("Pyloquent Comprehensive Usage Examples")
    print("=" * 40)

    await setup_database()

    users = await create_users()
    await query_examples()
    await crud_examples(users)
    await relationship_examples()
    await aggregate_examples()
    await transaction_example()
    await increment_decrement_examples()
    await upsert_examples()
    await conditional_query_examples()
    await where_exists_examples()
    await pagination_examples()
    await lock_examples()
    await to_raw_sql_examples()
    await collection_advanced_examples()
    await model_instance_examples()
    await find_many_destroy_examples()

    print("\n" + "=" * 40)
    print("Examples completed!")

    await manager.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
