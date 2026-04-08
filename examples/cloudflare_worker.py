"""Cloudflare D1 Python Worker example using Pyloquent.

Deployment
----------
1. Install Wrangler: ``npm install -g wrangler``
2. Create a D1 database: ``npx wrangler d1 create my-db``
3. Copy the database_id from the output into ``wrangler.jsonc`` below.
4. Deploy: ``npx wrangler deploy``

``wrangler.jsonc`` (place in project root)
------------------------------------------
::

    {
      "name": "my-pyloquent-worker",
      "main": "examples/cloudflare_worker.py",
      "compatibility_flags": ["python_workers"],
      "compatibility_date": "2026-04-08",
      "d1_databases": [
        {
          "binding": "DB",
          "database_name": "my-db",
          "database_id": "YOUR_DATABASE_ID_HERE"
        }
      ]
    }

Notes
-----
- ``compatibility_flags = ["python_workers"]`` is **required** for Python.
- The D1 binding name (``"DB"``) must match ``self.env.DB`` in the code.
- The ``workers`` module (``WorkerEntrypoint``, ``Response``) is provided
  by the Cloudflare runtime — it is not installed via pip.
- D1 statements use ``await stmt.run()`` for both SELECT and write queries
  (the canonical Python Workers API shown in Cloudflare's documentation).
- Transactions in D1 Workers bindings are implemented via ``db.batch()``
  (no ``BEGIN``/``COMMIT`` support); Pyloquent handles this automatically
  inside ``async with manager.transaction()``.
"""

from __future__ import annotations

from typing import Optional

# ---------------------------------------------------------------------------
# These imports are only available inside the Cloudflare Workers runtime.
# They are commented out here so the file can be imported in normal Python
# for documentation / linting purposes.
# ---------------------------------------------------------------------------
# from workers import Response, WorkerEntrypoint

from pyloquent import ConnectionManager, Model
from pyloquent.database.manager import set_manager


# ---------------------------------------------------------------------------
# Model definitions
# ---------------------------------------------------------------------------

class User(Model):
    """User model backed by the D1 ``users`` table."""

    __table__ = "users"
    __fillable__ = ["name", "email", "active"]

    id: Optional[int] = None
    name: str
    email: str
    active: bool = True

    def posts(self):
        return self.has_many(Post)


class Post(Model):
    """Post model backed by the D1 ``posts`` table."""

    __table__ = "posts"
    __fillable__ = ["user_id", "title", "body", "published"]

    id: Optional[int] = None
    user_id: Optional[int] = None
    title: str
    body: Optional[str] = None
    published: bool = False

    def author(self):
        return self.belongs_to(User)


# ---------------------------------------------------------------------------
# Helper — set up the manager from the binding once per request
# ---------------------------------------------------------------------------

def _setup(binding) -> ConnectionManager:
    """Wire Pyloquent to the D1 binding and set it as the global manager.

    Args:
        binding: The D1 binding object (``self.env.DB``).

    Returns:
        Ready-to-use :class:`~pyloquent.database.manager.ConnectionManager`.
    """
    manager = ConnectionManager.from_binding(binding)
    set_manager(manager)
    return manager


# ---------------------------------------------------------------------------
# Worker entry-point
#
# Uncomment the ``WorkerEntrypoint`` base class and ``Response`` import when
# deploying to Cloudflare Workers.
# ---------------------------------------------------------------------------

class Default:  # (WorkerEntrypoint):
    """Cloudflare Worker entry-point.

    Replace ``class Default:`` with ``class Default(WorkerEntrypoint):`` and
    uncomment the ``from workers import ...`` line at the top when deploying.
    """

    async def fetch(self, request):
        """Handle incoming HTTP requests.

        Routes:
            GET /users         — list active users
            POST /users        — create a user (JSON body: {name, email})
            GET /users/{id}    — fetch a single user
            DELETE /users/{id} — delete a user
            GET /schema        — introspect D1 schema
            GET /seed          — seed demo data (idempotent)
        """
        _setup(self.env.DB)

        url = request.url
        method = request.method.upper()
        path = url.pathname.rstrip("/")

        # ---- GET /users ---------------------------------------------------
        if method == "GET" and path == "/users":
            users = await User.where("active", True).order_by("name").get()
            return Response.json({"users": users.to_dict_list()})

        # ---- POST /users --------------------------------------------------
        if method == "POST" and path == "/users":
            body = await request.json()
            user = await User.create({
                "name":  body.get("name", ""),
                "email": body.get("email", ""),
            })
            return Response.json({"user": user.to_dict()}, status=201)

        # ---- GET /users/{id} ---------------------------------------------
        if method == "GET" and path.startswith("/users/"):
            user_id = int(path.split("/")[-1])
            user = await User.find(user_id)
            if user is None:
                return Response.json({"error": "Not found"}, status=404)
            posts = await Post.where("user_id", user_id).get()
            data = user.to_dict()
            data["posts"] = posts.to_dict_list()
            return Response.json({"user": data})

        # ---- DELETE /users/{id} ------------------------------------------
        if method == "DELETE" and path.startswith("/users/"):
            user_id = int(path.split("/")[-1])
            user = await User.find(user_id)
            if user is None:
                return Response.json({"error": "Not found"}, status=404)
            await user.delete()
            return Response.json({"deleted": user_id})

        # ---- GET /schema -------------------------------------------------
        if method == "GET" and path == "/schema":
            from pyloquent.d1.binding import D1BindingConnection
            conn = _setup(self.env.DB).connection()
            tables  = await conn.get_tables()
            columns = {}
            for t in tables:
                columns[t] = await conn.get_columns(t)
            return Response.json({"tables": tables, "columns": columns})

        # ---- GET /seed ---------------------------------------------------
        if method == "GET" and path == "/seed":
            await _seed()
            return Response.json({"seeded": True})

        # ---- GET /batch-demo ---------------------------------------------
        if method == "GET" and path == "/batch-demo":
            return await _batch_demo()

        return Response.json({"error": "Not found"}, status=404)


# ---------------------------------------------------------------------------
# Seed helper
# ---------------------------------------------------------------------------

async def _seed() -> None:
    """Create the tables and insert demo data if they don't already exist."""
    from pyloquent.database.manager import get_manager
    conn = get_manager().connection()

    await conn.exec("""
        CREATE TABLE IF NOT EXISTS users (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT    NOT NULL,
            email   TEXT    NOT NULL UNIQUE,
            active  INTEGER NOT NULL DEFAULT 1
        )
    """)
    await conn.exec("""
        CREATE TABLE IF NOT EXISTS posts (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   INTEGER NOT NULL,
            title     TEXT    NOT NULL,
            body      TEXT,
            published INTEGER NOT NULL DEFAULT 0
        )
    """)

    # Batch insert — one round-trip for all rows
    await User.query.insert_or_ignore([
        {"name": "Alice",   "email": "alice@example.com"},
        {"name": "Bob",     "email": "bob@example.com"},
        {"name": "Charlie", "email": "charlie@example.com"},
    ])

    alice = await User.where("email", "alice@example.com").first()
    if alice:
        await Post.query.insert_or_ignore([
            {"user_id": alice.id, "title": "Hello D1",   "published": True},
            {"user_id": alice.id, "title": "Second post", "published": False},
        ])


# ---------------------------------------------------------------------------
# Batch demo helper
# ---------------------------------------------------------------------------

async def _batch_demo():
    """Demonstrate D1 native batch and transaction support."""
    from pyloquent.database.manager import get_manager
    from pyloquent.d1.binding import D1BindingConnection

    conn = get_manager().connection()
    assert isinstance(conn, D1BindingConnection)

    # Low-level batch: multi-statement atomic round-trip
    results = await conn.batch([
        ("SELECT COUNT(*) AS n FROM users", None),
        ("SELECT COUNT(*) AS n FROM posts", None),
    ])
    user_count = results[0][0]["n"] if results[0] else 0
    post_count = results[1][0]["n"] if results[1] else 0

    # Transaction via batch accumulation
    async with get_manager().transaction():
        await User.create({"name": "TxUser", "email": "tx@example.com"})

    return Response.json({
        "user_count": user_count,
        "post_count": post_count,
        "transaction": "ok",
    })
