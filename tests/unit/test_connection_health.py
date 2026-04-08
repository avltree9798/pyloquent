"""Unit tests for pool_pre_ping, pool_recycle, and reconnect_on_error."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pyloquent.database.sqlite_connection import SQLiteConnection
from pyloquent.exceptions import QueryException


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sqlite(extra: dict | None = None) -> SQLiteConnection:
    cfg = {"database": ":memory:", **(extra or {})}
    return SQLiteConnection(cfg)


# ---------------------------------------------------------------------------
# Base Connection.ping() fallback (connection.py lines 99-111)
# ---------------------------------------------------------------------------

from pyloquent.database.connection import Connection


class _MinimalConn(Connection):
    """Concrete subclass that does NOT override ping() — exercises the base fallback."""

    async def connect(self): self._connected = True
    async def disconnect(self): self._connected = False
    async def execute(self, sql, bindings=None): return 1
    async def fetch_all(self, sql, bindings=None): return [{"1": 1}]
    async def fetch_one(self, sql, bindings=None): return {"1": 1}
    async def execute_many(self, sql, rows): return len(rows)
    def get_grammar(self): return None
    async def begin_transaction(self): pass
    async def commit(self): pass
    async def rollback(self): pass


@pytest.mark.asyncio
async def test_base_ping_success():
    """Base Connection.ping() returns True when fetch_one succeeds (line 109)."""
    c = _MinimalConn({})
    result = await c.ping()
    assert result is True


@pytest.mark.asyncio
async def test_base_ping_failure():
    """Base Connection.ping() returns False when fetch_one raises (line 111)."""
    c = _MinimalConn({})
    with patch.object(c, "fetch_one", AsyncMock(side_effect=Exception("dead"))):
        result = await c.ping()
    assert result is False


@pytest.mark.asyncio
async def test_base_ping_restores_pool_pre_ping_flag():
    """Base ping() temporarily disables pool_pre_ping to prevent recursion (lines 103-108)."""
    c = _MinimalConn({"pool_pre_ping": True})
    assert c._pool_pre_ping is True
    await c.ping()
    assert c._pool_pre_ping is True   # restored after ping


# ---------------------------------------------------------------------------
# Base Connection — config parsing
# ---------------------------------------------------------------------------

def test_default_flags():
    c = _sqlite()
    assert c._pool_pre_ping is False
    assert c._pool_recycle is None
    assert c._reconnect_on_error is False
    assert c._pinging is False


def test_pool_pre_ping_parsed():
    assert _sqlite({"pool_pre_ping": True})._pool_pre_ping is True


def test_pool_recycle_parsed():
    assert _sqlite({"pool_recycle": 3600})._pool_recycle == 3600


def test_reconnect_on_error_parsed():
    assert _sqlite({"reconnect_on_error": True})._reconnect_on_error is True


# ---------------------------------------------------------------------------
# ensure_connected() logic
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ensure_connected_no_op_when_disconnected():
    """ensure_connected() is a no-op when _connected is False."""
    c = _sqlite({"pool_pre_ping": True})
    c.ping = AsyncMock(return_value=False)
    await c.ensure_connected()          # _connected is False
    c.ping.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_connected_no_op_while_pinging():
    """ensure_connected() is a no-op when _pinging guard is set (prevents recursion)."""
    c = _sqlite({"pool_pre_ping": True})
    c._connected = True
    c._pinging = True                   # guard already active
    c.ping = AsyncMock(return_value=False)
    await c.ensure_connected()
    c.ping.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_connected_pre_ping_alive():
    """pool_pre_ping: ping returns True → no reconnect."""
    c = _sqlite({"pool_pre_ping": True})
    c._connected = True
    c.ping = AsyncMock(return_value=True)
    c.disconnect = AsyncMock()
    c.connect = AsyncMock()
    await c.ensure_connected()
    c.ping.assert_called_once()
    c.disconnect.assert_not_called()
    c.connect.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_connected_pre_ping_dead():
    """pool_pre_ping: ping returns False → disconnect + reconnect."""
    c = _sqlite({"pool_pre_ping": True})
    c._connected = True
    c.ping = AsyncMock(return_value=False)
    c.disconnect = AsyncMock()
    c.connect = AsyncMock()
    await c.ensure_connected()
    c.disconnect.assert_called_once()
    c.connect.assert_called_once()


@pytest.mark.asyncio
async def test_ensure_connected_pool_recycle_fresh():
    """pool_recycle: connection within threshold → no reconnect."""
    c = _sqlite({"pool_recycle": 3600})
    c._connected = True
    c._connected_at = time.monotonic()
    c.disconnect = AsyncMock()
    c.connect = AsyncMock()
    await c.ensure_connected()
    c.disconnect.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_connected_pool_recycle_expired():
    """pool_recycle: connection past threshold → reconnect."""
    c = _sqlite({"pool_recycle": 1})
    c._connected = True
    c._connected_at = time.monotonic() - 10   # 10 s ago, threshold 1 s
    c.disconnect = AsyncMock()
    c.connect = AsyncMock()
    await c.ensure_connected()
    c.disconnect.assert_called_once()
    c.connect.assert_called_once()


# ---------------------------------------------------------------------------
# SQLiteConnection — ping() override
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sqlite_ping_no_connection():
    assert await _sqlite().ping() is False


@pytest.mark.asyncio
async def test_sqlite_ping_live():
    c = SQLiteConnection({"database": ":memory:"})
    await c.connect()
    assert await c.ping() is True
    await c.disconnect()


@pytest.mark.asyncio
async def test_sqlite_ping_broken():
    c = _sqlite()
    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock(side_effect=Exception("broken"))
    c._connection = mock_conn
    assert await c.ping() is False


# ---------------------------------------------------------------------------
# connected_at timestamp
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sqlite_connected_at_set_on_connect():
    c = SQLiteConnection({"database": ":memory:"})
    before = time.monotonic()
    await c.connect()
    after = time.monotonic()
    assert c._connected_at is not None
    assert before <= c._connected_at <= after
    await c.disconnect()


# ---------------------------------------------------------------------------
# reconnect_on_error — only reconnects when ping() is False
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sqlite_no_reconnect_on_bad_sql():
    """Bad SQL raises QueryException without triggering reconnect (ping stays True)."""
    c = SQLiteConnection({"database": ":memory:", "reconnect_on_error": True})
    await c.connect()

    disconnect_mock = AsyncMock()
    connect_mock = AsyncMock()

    with patch.object(c, "disconnect", disconnect_mock), \
         patch.object(c, "connect", connect_mock):
        with pytest.raises(QueryException):
            await c.execute("SELECT * FROM nonexistent_table_xyz")

    # ping() succeeds (real conn alive) → reconnect must NOT be called
    disconnect_mock.assert_not_called()
    await c.disconnect()


@pytest.mark.asyncio
async def test_sqlite_execute_reconnects_when_ping_dead():
    """execute() reconnects and retries when ping() reports dead connection."""
    c = SQLiteConnection({"database": ":memory:", "reconnect_on_error": True})
    await c.connect()
    await c.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    original_conn = c._connection

    # Replace connection with a broken mock
    broken = AsyncMock()
    broken.execute.side_effect = Exception("server has gone away")
    c._connection = broken

    reconnect_log: list[str] = []
    real_disconnect = SQLiteConnection.disconnect.__get__(c)
    real_connect = SQLiteConnection.connect.__get__(c)

    async def do_disconnect():
        reconnect_log.append("disconnect")
        c._connection = None
        c._connected = False

    async def do_connect():
        reconnect_log.append("connect")
        c._connection = original_conn
        c._connected = True

    # ping() returns False so reconnect is triggered
    with patch.object(c, "ping", AsyncMock(return_value=False)), \
         patch.object(c, "disconnect", do_disconnect), \
         patch.object(c, "connect", do_connect):
        result = await c.execute("INSERT INTO t (v) VALUES (?)", ["hello"])

    assert reconnect_log == ["disconnect", "connect"]
    assert result is not None

    c._connection = original_conn
    c._connected = True
    await c.disconnect()


@pytest.mark.asyncio
async def test_sqlite_fetch_all_reconnects_when_ping_dead():
    """fetch_all() reconnects and retries when connection is dead."""
    c = SQLiteConnection({"database": ":memory:", "reconnect_on_error": True})
    await c.connect()
    await c.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    await c.execute("INSERT INTO t (v) VALUES (?)", ["row1"])
    original_conn = c._connection

    broken = AsyncMock()
    broken.execute.side_effect = Exception("gone")
    c._connection = broken

    async def do_disconnect():
        c._connection = None
        c._connected = False

    async def do_connect():
        c._connection = original_conn
        c._connected = True

    with patch.object(c, "ping", AsyncMock(return_value=False)), \
         patch.object(c, "disconnect", do_disconnect), \
         patch.object(c, "connect", do_connect):
        rows = await c.fetch_all("SELECT * FROM t")

    assert rows == [{"id": 1, "v": "row1"}]
    c._connection = original_conn
    c._connected = True
    await c.disconnect()


@pytest.mark.asyncio
async def test_sqlite_fetch_one_reconnects_when_ping_dead():
    """fetch_one() reconnects and retries when connection is dead."""
    c = SQLiteConnection({"database": ":memory:", "reconnect_on_error": True})
    await c.connect()
    await c.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    await c.execute("INSERT INTO t (v) VALUES (?)", ["hello"])
    original_conn = c._connection

    broken = AsyncMock()
    broken.execute.side_effect = Exception("gone")
    c._connection = broken

    async def do_disconnect():
        c._connection = None
        c._connected = False

    async def do_connect():
        c._connection = original_conn
        c._connected = True

    with patch.object(c, "ping", AsyncMock(return_value=False)), \
         patch.object(c, "disconnect", do_disconnect), \
         patch.object(c, "connect", do_connect):
        row = await c.fetch_one("SELECT * FROM t WHERE id = 1")

    assert row == {"id": 1, "v": "hello"}
    c._connection = original_conn
    c._connected = True
    await c.disconnect()


@pytest.mark.asyncio
async def test_sqlite_retry_failure_raises_query_exception():
    """If retry after reconnect also fails, QueryException is raised."""
    c = SQLiteConnection({"database": ":memory:", "reconnect_on_error": True})
    await c.connect()
    original_conn = c._connection

    broken = AsyncMock()
    broken.execute.side_effect = Exception("always broken")
    c._connection = broken

    async def do_connect():
        c._connection = broken          # still broken after reconnect
        c._connected = True

    with patch.object(c, "ping", AsyncMock(return_value=False)), \
         patch.object(c, "disconnect", AsyncMock()), \
         patch.object(c, "connect", do_connect):
        with pytest.raises(QueryException, match="always broken"):
            await c.execute("SELECT 1")

    c._connection = original_conn
    c._connected = True
    await c.disconnect()


# ---------------------------------------------------------------------------
# PostgresConnection — pool_recycle forwarded as max_inactive_connection_lifetime
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_postgres_pool_recycle_kwarg():
    """pool_recycle is forwarded to asyncpg.create_pool."""
    pytest.importorskip("asyncpg")
    from pyloquent.database.postgres_connection import PostgresConnection

    conn = PostgresConnection({"pool_recycle": 600})
    assert conn._pool_recycle == 600

    mock_pool = AsyncMock()
    with patch("asyncpg.create_pool", new=AsyncMock(return_value=mock_pool)) as mock_create:
        await conn.connect()
        kwargs = mock_create.call_args.kwargs
        assert kwargs.get("max_inactive_connection_lifetime") == 600.0


@pytest.mark.asyncio
async def test_postgres_no_pool_recycle_no_kwarg():
    """Without pool_recycle, max_inactive_connection_lifetime is not passed."""
    pytest.importorskip("asyncpg")
    from pyloquent.database.postgres_connection import PostgresConnection

    conn = PostgresConnection({})
    mock_pool = AsyncMock()
    with patch("asyncpg.create_pool", new=AsyncMock(return_value=mock_pool)) as mock_create:
        await conn.connect()
        kwargs = mock_create.call_args.kwargs
        assert "max_inactive_connection_lifetime" not in kwargs


# ---------------------------------------------------------------------------
# MySQLConnection — pool_recycle forwarded natively
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mysql_pool_recycle_kwarg():
    """pool_recycle is forwarded to aiomysql.create_pool."""
    pytest.importorskip("aiomysql")
    from pyloquent.database.mysql_connection import MySQLConnection

    conn = MySQLConnection({"pool_recycle": 1800})
    assert conn._pool_recycle == 1800

    mock_pool = AsyncMock()
    with patch("aiomysql.create_pool", new=AsyncMock(return_value=mock_pool)) as mock_create:
        await conn.connect()
        kwargs = mock_create.call_args.kwargs
        assert kwargs.get("pool_recycle") == 1800


@pytest.mark.asyncio
async def test_mysql_no_pool_recycle_no_kwarg():
    """Without pool_recycle, pool_recycle kwarg is not passed to aiomysql."""
    pytest.importorskip("aiomysql")
    from pyloquent.database.mysql_connection import MySQLConnection

    conn = MySQLConnection({})
    mock_pool = AsyncMock()
    with patch("aiomysql.create_pool", new=AsyncMock(return_value=mock_pool)) as mock_create:
        await conn.connect()
        kwargs = mock_create.call_args.kwargs
        assert "pool_recycle" not in kwargs


# ---------------------------------------------------------------------------
# Regression: aiomysql.DictCursor NameError in fetch_all / fetch_one
# Bug: aiomysql was only imported inside connect(); fetch_all and fetch_one
# used aiomysql.DictCursor without a local import → NameError at query time.
# ---------------------------------------------------------------------------

def _make_mysql_with_mock_pool():
    """Return a MySQLConnection wired to a fully-mocked aiomysql pool."""
    import sys
    from types import ModuleType
    from pyloquent.database.mysql_connection import MySQLConnection

    # Build a fake aiomysql module with DictCursor so the local import succeeds
    fake_aiomysql = ModuleType("aiomysql")
    fake_aiomysql.DictCursor = object()          # any sentinel works

    # Cursor mock: fetchall returns rows, fetchone returns a single row
    cursor_ctx = MagicMock()
    cursor_ctx.__aenter__ = AsyncMock(return_value=cursor_ctx)
    cursor_ctx.__aexit__ = AsyncMock(return_value=False)
    cursor_ctx.execute = AsyncMock()
    cursor_ctx.fetchall = AsyncMock(return_value=[{"id": 1, "name": "Alice"}])
    cursor_ctx.fetchone = AsyncMock(return_value={"id": 1, "name": "Alice"})

    # conn mock: cursor() returns the cursor_ctx
    conn_ctx = MagicMock()
    conn_ctx.__aenter__ = AsyncMock(return_value=conn_ctx)
    conn_ctx.__aexit__ = AsyncMock(return_value=False)
    conn_ctx.cursor = MagicMock(return_value=cursor_ctx)

    # pool mock: acquire() returns conn_ctx
    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(return_value=conn_ctx)

    fake_aiomysql.create_pool = AsyncMock(return_value=mock_pool)

    conn = MySQLConnection({})
    conn._pool = mock_pool
    conn._connected = True

    return conn, fake_aiomysql


@pytest.mark.asyncio
async def test_mysql_fetch_all_no_nameerror():
    """fetch_all() must not raise NameError for aiomysql (regression for missing import).

    Previously, aiomysql.DictCursor was used in fetch_all without a local
    import of aiomysql, causing NameError on every MySQL SELECT query.
    """
    conn, fake_aiomysql = _make_mysql_with_mock_pool()

    with patch.dict("sys.modules", {"aiomysql": fake_aiomysql}):
        rows = await conn.fetch_all("SELECT * FROM users")

    assert rows == [{"id": 1, "name": "Alice"}]


@pytest.mark.asyncio
async def test_mysql_fetch_one_no_nameerror():
    """fetch_one() must not raise NameError for aiomysql (regression for missing import).

    Previously, aiomysql.DictCursor was used in fetch_one without a local
    import of aiomysql, causing NameError on every MySQL SELECT query.
    """
    conn, fake_aiomysql = _make_mysql_with_mock_pool()

    with patch.dict("sys.modules", {"aiomysql": fake_aiomysql}):
        row = await conn.fetch_one("SELECT * FROM users WHERE id = ?", [1])

    assert row == {"id": 1, "name": "Alice"}


# ---------------------------------------------------------------------------
# sqlite_connection.py — QueryException re-raise (lines 118, 156, 190)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_reraises_query_exception_without_reconnect():
    """QueryException raised inside execute() try block is re-raised unchanged (line 118)."""
    c = SQLiteConnection({"database": ":memory:", "reconnect_on_error": True})
    await c.connect()

    mock_conn = AsyncMock()
    mock_conn.execute.side_effect = QueryException("inner QE")
    c._connection = mock_conn

    disconnect_mock = AsyncMock()
    with patch.object(c, "disconnect", disconnect_mock):
        with pytest.raises(QueryException, match="inner QE"):
            await c.execute("SELECT 1")
    disconnect_mock.assert_not_called()

    c._connection = None
    c._connected = False


@pytest.mark.asyncio
async def test_fetch_all_reraises_query_exception_without_reconnect():
    """QueryException raised inside fetch_all() try block is re-raised unchanged (line 156)."""
    c = SQLiteConnection({"database": ":memory:", "reconnect_on_error": True})
    await c.connect()

    mock_conn = AsyncMock()
    mock_conn.execute.side_effect = QueryException("inner QE fetch_all")
    c._connection = mock_conn

    disconnect_mock = AsyncMock()
    with patch.object(c, "disconnect", disconnect_mock):
        with pytest.raises(QueryException, match="inner QE fetch_all"):
            await c.fetch_all("SELECT 1")
    disconnect_mock.assert_not_called()

    c._connection = None
    c._connected = False


@pytest.mark.asyncio
async def test_fetch_one_reraises_query_exception_without_reconnect():
    """QueryException raised inside fetch_one() try block is re-raised unchanged (line 190)."""
    c = SQLiteConnection({"database": ":memory:", "reconnect_on_error": True})
    await c.connect()

    mock_conn = AsyncMock()
    mock_conn.execute.side_effect = QueryException("inner QE fetch_one")
    c._connection = mock_conn

    disconnect_mock = AsyncMock()
    with patch.object(c, "disconnect", disconnect_mock):
        with pytest.raises(QueryException, match="inner QE fetch_one"):
            await c.fetch_one("SELECT 1")
    disconnect_mock.assert_not_called()

    c._connection = None
    c._connected = False


# ---------------------------------------------------------------------------
# sqlite_connection.py — execute retry rowcount path (line 130)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sqlite_execute_retry_rowcount_path():
    """execute() retry for non-INSERT SQL returns rowcount (line 130)."""
    c = SQLiteConnection({"database": ":memory:", "reconnect_on_error": True})
    await c.connect()
    await c.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    await c.execute("INSERT INTO t (v) VALUES (?)", ["x"])
    original_conn = c._connection

    broken = AsyncMock()
    broken.execute.side_effect = Exception("gone")
    c._connection = broken

    async def do_disconnect():
        c._connection = None
        c._connected = False

    async def do_connect():
        c._connection = original_conn
        c._connected = True

    with patch.object(c, "ping", AsyncMock(return_value=False)), \
         patch.object(c, "disconnect", do_disconnect), \
         patch.object(c, "connect", do_connect):
        # DELETE is non-INSERT → hits cursor.rowcount in retry (line 130)
        result = await c.execute("DELETE FROM t WHERE v = ?", ["x"])

    assert result == 1
    c._connection = original_conn
    c._connected = True
    await c.disconnect()


# ---------------------------------------------------------------------------
# sqlite_connection.py — retry failure paths (lines 165-166, 199-200)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sqlite_fetch_all_retry_failure():
    """If fetch_all retry also fails, QueryException is raised (lines 165-166)."""
    c = SQLiteConnection({"database": ":memory:", "reconnect_on_error": True})
    await c.connect()
    original_conn = c._connection

    broken = AsyncMock()
    broken.execute.side_effect = Exception("always broken")
    c._connection = broken

    async def do_connect():
        c._connection = broken
        c._connected = True

    with patch.object(c, "ping", AsyncMock(return_value=False)), \
         patch.object(c, "disconnect", AsyncMock()), \
         patch.object(c, "connect", do_connect):
        with pytest.raises(QueryException, match="always broken"):
            await c.fetch_all("SELECT 1")

    c._connection = original_conn
    c._connected = True
    await c.disconnect()


@pytest.mark.asyncio
async def test_sqlite_fetch_one_retry_failure():
    """If fetch_one retry also fails, QueryException is raised (lines 199-200)."""
    c = SQLiteConnection({"database": ":memory:", "reconnect_on_error": True})
    await c.connect()
    original_conn = c._connection

    broken = AsyncMock()
    broken.execute.side_effect = Exception("always broken fetch_one")
    c._connection = broken

    async def do_connect():
        c._connection = broken
        c._connected = True

    with patch.object(c, "ping", AsyncMock(return_value=False)), \
         patch.object(c, "disconnect", AsyncMock()), \
         patch.object(c, "connect", do_connect):
        with pytest.raises(QueryException, match="always broken fetch_one"):
            await c.fetch_one("SELECT 1")

    c._connection = original_conn
    c._connected = True
    await c.disconnect()
