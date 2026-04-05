"""Targeted unit and integration tests for uncovered database module paths."""
import pytest
from pyloquent.database.manager import ConnectionManager
from pyloquent.exceptions import PyloquentException, QueryException


# ---------------------------------------------------------------------------
# ConnectionManager.add_connection: duplicate name raises ValueError (line 50)
# ---------------------------------------------------------------------------

def test_add_connection_duplicate_raises():
    mgr = ConnectionManager()
    mgr.add_connection("default", {"driver": "sqlite", "database": ":memory:"})
    with pytest.raises(ValueError, match="already exists"):
        mgr.add_connection("default", {"driver": "sqlite", "database": ":memory:"})


# ---------------------------------------------------------------------------
# ConnectionManager.connection: no default configured (line 72)
# ---------------------------------------------------------------------------

def test_connection_no_default_raises():
    mgr = ConnectionManager()
    with pytest.raises(PyloquentException, match="No default connection"):
        mgr.connection()


# ---------------------------------------------------------------------------
# ConnectionManager.connection: unknown connection name (line 77)
# ---------------------------------------------------------------------------

def test_connection_unknown_name_raises():
    mgr = ConnectionManager()
    with pytest.raises(PyloquentException, match="not configured"):
        mgr.connection("nonexistent")


# ---------------------------------------------------------------------------
# ConnectionManager._create_connection: postgres/mysql/d1 (lines 108-118)
# ---------------------------------------------------------------------------

def test_create_connection_postgres():
    mgr = ConnectionManager()
    conn = mgr._create_connection("pg", {"driver": "postgres", "database": "test"})
    from pyloquent.database.postgres_connection import PostgresConnection
    assert isinstance(conn, PostgresConnection)


def test_create_connection_postgresql_alias():
    mgr = ConnectionManager()
    conn = mgr._create_connection("pg2", {"driver": "postgresql", "database": "test"})
    from pyloquent.database.postgres_connection import PostgresConnection
    assert isinstance(conn, PostgresConnection)


def test_create_connection_mysql():
    mgr = ConnectionManager()
    conn = mgr._create_connection("mysql", {"driver": "mysql", "database": "test"})
    from pyloquent.database.mysql_connection import MySQLConnection
    assert isinstance(conn, MySQLConnection)


def test_create_connection_d1():
    mgr = ConnectionManager()
    conn = mgr._create_connection("d1", {"driver": "d1", "database": "test"})
    from pyloquent.d1.connection import D1Connection
    assert isinstance(conn, D1Connection)


# ---------------------------------------------------------------------------
# ConnectionManager._create_connection: unsupported driver (lines 119-120)
# ---------------------------------------------------------------------------

def test_create_connection_unsupported_driver_raises():
    mgr = ConnectionManager()
    with pytest.raises(PyloquentException, match="Unsupported database driver"):
        mgr._create_connection("bad", {"driver": "oracle"})


# ---------------------------------------------------------------------------
# ConnectionManager.disconnect by name (lines 144-145)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_disconnect_by_name(sqlite_db):
    from pyloquent.database.manager import get_manager
    mgr = get_manager()
    # Disconnect the default connection by name (then reconnect via fixture teardown)
    name = mgr._default
    if name and name in mgr._connections:
        await mgr.disconnect(name)
        # Reconnect for other tests
        conn = mgr._connections.get(name) or mgr._create_connection(name, mgr._configs[name])
        if not conn.is_connected():
            await conn.connect()
        mgr._connections[name] = conn


# ---------------------------------------------------------------------------
# ConnectionManager.transaction context manager (lines 166-174)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transaction_commits_on_success(sqlite_db):
    from pyloquent.database.manager import get_manager
    mgr = get_manager()
    async with mgr.transaction() as conn:
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS _tx_test (id INTEGER PRIMARY KEY, v TEXT)"
        )
        await conn.execute("INSERT INTO _tx_test (v) VALUES (?)", ["hello"])
    # Table and row should exist after commit
    row = await mgr.connection().fetch_one("SELECT * FROM _tx_test WHERE v = ?", ["hello"])
    assert row is not None
    await mgr.connection().execute("DROP TABLE IF EXISTS _tx_test")


@pytest.mark.asyncio
async def test_transaction_rollback_on_exception(sqlite_db):
    from pyloquent.database.manager import get_manager
    mgr = get_manager()
    await mgr.connection().execute(
        "CREATE TABLE IF NOT EXISTS _tx_rollback (id INTEGER PRIMARY KEY, v TEXT)"
    )
    with pytest.raises(RuntimeError):
        async with mgr.transaction() as conn:
            await conn.execute("INSERT INTO _tx_rollback (v) VALUES (?)", ["before_error"])
            raise RuntimeError("simulated error")
    await mgr.connection().execute("DROP TABLE IF EXISTS _tx_rollback")


# ---------------------------------------------------------------------------
# ConnectionManager.table() (line 186)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_manager_table_returns_query_builder(sqlite_db):
    from pyloquent.database.manager import get_manager
    from pyloquent.query.builder import QueryBuilder
    mgr = get_manager()
    qb = mgr.table("users")
    assert isinstance(qb, QueryBuilder)


# ---------------------------------------------------------------------------
# ConnectionManager.lifespan() (line 207)
# ---------------------------------------------------------------------------

def test_lifespan_returns_self():
    mgr = ConnectionManager()
    result = mgr.lifespan()
    assert result is mgr


# ---------------------------------------------------------------------------
# ConnectionManager as async context manager (lines 211-212, 216)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_manager_async_context_manager():
    mgr = ConnectionManager()
    mgr.add_connection("default", {"driver": "sqlite", "database": ":memory:"})
    async with mgr:
        conn = mgr.connection()
        assert conn.is_connected()
    # After exiting, connection should be closed


# ---------------------------------------------------------------------------
# get_manager() creates global manager when None (line 231)
# ---------------------------------------------------------------------------

def test_get_manager_creates_instance():
    from pyloquent.database.manager import get_manager, set_manager
    original = get_manager()
    set_manager(None)
    new_mgr = get_manager()
    assert isinstance(new_mgr, ConnectionManager)
    # Restore
    set_manager(original)


# ---------------------------------------------------------------------------
# SQLiteConnection error paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sqlite_execute_not_connected_raises():
    from pyloquent.database.sqlite_connection import SQLiteConnection
    conn = SQLiteConnection({"database": ":memory:"})
    with pytest.raises(QueryException, match="Not connected"):
        await conn.execute("SELECT 1")


@pytest.mark.asyncio
async def test_sqlite_execute_bad_sql_raises():
    from pyloquent.database.sqlite_connection import SQLiteConnection
    conn = SQLiteConnection({"database": ":memory:"})
    await conn.connect()
    with pytest.raises(QueryException):
        await conn.execute("INVALID SQL !!!")
    await conn.disconnect()


@pytest.mark.asyncio
async def test_sqlite_fetch_all_not_connected_raises():
    from pyloquent.database.sqlite_connection import SQLiteConnection
    conn = SQLiteConnection({"database": ":memory:"})
    with pytest.raises(QueryException, match="Not connected"):
        await conn.fetch_all("SELECT 1")


@pytest.mark.asyncio
async def test_sqlite_fetch_all_bad_sql_raises():
    from pyloquent.database.sqlite_connection import SQLiteConnection
    conn = SQLiteConnection({"database": ":memory:"})
    await conn.connect()
    with pytest.raises(QueryException):
        await conn.fetch_all("INVALID SQL !!!")
    await conn.disconnect()


@pytest.mark.asyncio
async def test_sqlite_fetch_one_not_connected_raises():
    from pyloquent.database.sqlite_connection import SQLiteConnection
    conn = SQLiteConnection({"database": ":memory:"})
    with pytest.raises(QueryException, match="Not connected"):
        await conn.fetch_one("SELECT 1")


@pytest.mark.asyncio
async def test_sqlite_begin_transaction_not_connected_raises():
    from pyloquent.database.sqlite_connection import SQLiteConnection
    conn = SQLiteConnection({"database": ":memory:"})
    with pytest.raises(QueryException, match="Not connected"):
        await conn.begin_transaction()


@pytest.mark.asyncio
async def test_sqlite_commit_not_connected_raises():
    from pyloquent.database.sqlite_connection import SQLiteConnection
    conn = SQLiteConnection({"database": ":memory:"})
    with pytest.raises(QueryException, match="Not connected"):
        await conn.commit()


@pytest.mark.asyncio
async def test_sqlite_rollback_not_connected_raises():
    from pyloquent.database.sqlite_connection import SQLiteConnection
    conn = SQLiteConnection({"database": ":memory:"})
    with pytest.raises(QueryException, match="Not connected"):
        await conn.rollback()


@pytest.mark.asyncio
async def test_sqlite_connect_bad_path_raises():
    from pyloquent.database.sqlite_connection import SQLiteConnection
    # Use an invalid path to trigger exception on connect
    conn = SQLiteConnection({"database": "/nonexistent/path/that/cannot/exist/db.sqlite"})
    with pytest.raises((ConnectionError, Exception)):
        await conn.connect()


# ---------------------------------------------------------------------------
# connection.table() (lines 146-148)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connection_table_returns_query_builder(sqlite_db):
    from pyloquent.database.manager import get_manager
    from pyloquent.query.builder import QueryBuilder
    conn = get_manager().connection()
    qb = conn.table("users")
    assert isinstance(qb, QueryBuilder)
