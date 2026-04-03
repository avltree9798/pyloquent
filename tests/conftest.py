"""Pytest configuration and fixtures."""

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def sqlite_db():
    """Create an in-memory SQLite database for testing."""
    from pyloquent import ConnectionManager
    from pyloquent.database.manager import set_manager

    manager = ConnectionManager()
    manager.add_connection("default", {"driver": "sqlite", "database": ":memory:"}, default=True)
    await manager.connect()

    # Set as global manager
    set_manager(manager)

    yield manager

    await manager.disconnect()


@pytest_asyncio.fixture
async def setup_tables(sqlite_db):
    """Create test tables in the database."""
    conn = sqlite_db.connection()

    # Create users table
    await conn.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            age INTEGER,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Create posts table
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

    # Create profiles table (for has-one relationship)
    await conn.execute(
        """
        CREATE TABLE profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            bio TEXT,
            website TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """
    )

    yield

    # Cleanup happens automatically with :memory: database
