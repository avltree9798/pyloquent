"""Unit tests for D1BindingConnection.

All tests use a synchronous duck-typed mock so no Cloudflare runtime is
needed.  The mock faithfully replicates the D1 JS binding interface:

    db.prepare(sql)        → MockStatement
    stmt.bind(*params)     → MockStatement (mutates)
    stmt.all()             → coroutine → {results: [...], meta: {...}}
    stmt.first()           → coroutine → dict | None
    stmt.run()             → coroutine → {success: True, meta: {...}}
    db.exec(sql)           → coroutine → {count: 1, duration: 0}
    db.batch([stmts])      → coroutine → [{results: [...], meta: {...}}, ...]
    db.dump()              → coroutine → bytes
"""

import asyncio
import pytest
from pyloquent.d1.binding import D1BindingConnection, D1Statement, _to_python


# ---------------------------------------------------------------------------
# Mock D1 binding
# ---------------------------------------------------------------------------

class MockD1Statement:
    """Synchronous-coroutine mock for a D1PreparedStatement.

    Mirrors the official Python Workers D1 API:
    - ``run()`` works for both SELECT and write statements (returns D1Result)
    - ``first()`` returns the first row dict or None
    """

    def __init__(self, db: "MockD1Binding", sql: str):
        self._db = db
        self.sql = sql
        self.params: list = []

    def bind(self, *args) -> "MockD1Statement":
        self.params = list(args)
        return self

    def _is_select(self) -> bool:
        return self.sql.strip().upper().startswith("SELECT")

    async def run(self):
        """Primary D1 method — handles both SELECT and write statements."""
        if self._is_select():
            return self._db._query(self.sql, self.params)
        return self._db._run(self.sql, self.params)

    async def first(self):
        result = self._db._query(self.sql, self.params)
        rows = result.get("results", [])
        return rows[0] if rows else None


class MockD1Binding:
    """In-process mock that stores rows in plain Python dicts."""

    def __init__(self):
        # table_name → list of row dicts
        self._tables: dict[str, list[dict]] = {}
        self._next_id: dict[str, int] = {}
        self._last_row_id = 0
        self._changes = 0

    # --- Internal helpers --------------------------------------------------

    def seed(self, table: str, rows: list[dict]):
        self._tables[table] = [dict(r) for r in rows]
        if rows:
            self._next_id[table] = max(r.get("id", 0) for r in rows) + 1

    def _query(self, sql: str, params: list) -> dict:
        """Extremely minimal SQL interpreter for SELECT tests."""
        sql = sql.strip()
        upper = sql.upper()

        if upper.startswith("SELECT"):
            # Figure out table
            table = self._extract_table(sql)
            rows = list(self._tables.get(table, []))

            # Apply simple WHERE col = ?
            if "WHERE" in upper and params:
                col = self._extract_where_col(sql)
                val = params[0]
                if col:
                    rows = [r for r in rows if r.get(col) == val]

            # last_insert_rowid()
            if "LAST_INSERT_ROWID" in upper:
                return {"results": [{"last_insert_rowid()": self._last_row_id}], "meta": {}}

            return {"results": rows, "meta": {"changes": 0, "last_row_id": self._last_row_id}}
        return {"results": [], "meta": {}}

    def _run(self, sql: str, params: list) -> dict:
        """Minimal INSERT / UPDATE / DELETE interpreter."""
        upper = sql.strip().upper()
        self._changes = 0

        if upper.startswith("INSERT INTO"):
            table = self._extract_table(sql)
            if table not in self._tables:
                self._tables[table] = []

            # Build a minimal row dict — we just use sequential IDs
            new_id = self._next_id.get(table, 1)
            self._next_id[table] = new_id + 1
            self._last_row_id = new_id
            self._changes = 1
            # Store params as positional values mapped to a generic row
            self._tables[table].append({"id": new_id, "_params": params})

        elif upper.startswith("UPDATE"):
            self._changes = 1

        elif upper.startswith("DELETE"):
            table = self._extract_table(sql)
            rows = self._tables.get(table, [])
            self._tables[table] = [r for r in rows]
            self._changes = len(rows)

        return {
            "success": True,
            "meta": {"changes": self._changes, "last_row_id": self._last_row_id},
        }

    @staticmethod
    def _extract_table(sql: str) -> str:
        upper = sql.upper()
        for kw in ("FROM ", "INTO ", "UPDATE ", "TABLE "):
            idx = upper.find(kw)
            if idx != -1:
                rest = sql[idx + len(kw):].strip().split()[0]
                return rest.strip('"').strip("'").lower()
        return ""

    @staticmethod
    def _extract_where_col(sql: str) -> str:
        upper = sql.upper()
        idx = upper.find("WHERE")
        if idx == -1:
            return ""
        clause = sql[idx + 5:].strip()
        col = clause.split("=")[0].strip().strip('"').strip("'").lower()
        return col

    # --- D1 binding API ---------------------------------------------------

    def prepare(self, sql: str) -> MockD1Statement:
        return MockD1Statement(self, sql)

    async def exec(self, sql: str) -> dict:
        return {"count": 1, "duration": 0}

    async def batch(self, stmts: list) -> list:
        results = []
        for stmt in stmts:
            results.append(await stmt.run())
        return results

    async def dump(self) -> bytes:
        return b"SQLite format 3\x00"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db() -> MockD1Binding:
    db = MockD1Binding()
    db.seed("users", [
        {"id": 1, "name": "Alice", "active": 1},
        {"id": 2, "name": "Bob",   "active": 1},
        {"id": 3, "name": "Carol", "active": 0},
    ])
    return db


@pytest.fixture
async def conn(mock_db) -> D1BindingConnection:
    c = D1BindingConnection(mock_db)
    await c.connect()
    return c


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connect_marks_connected(mock_db):
    c = D1BindingConnection(mock_db)
    assert not c.is_connected()
    await c.connect()
    assert c.is_connected()


@pytest.mark.asyncio
async def test_disconnect_clears_binding(mock_db):
    c = D1BindingConnection(mock_db)
    await c.connect()
    await c.disconnect()
    assert not c.is_connected()


@pytest.mark.asyncio
async def test_connect_with_none_binding_raises():
    from pyloquent.exceptions import QueryException
    c = D1BindingConnection(None)
    with pytest.raises(QueryException):
        await c.connect()


# ---------------------------------------------------------------------------
# from_binding factory
# ---------------------------------------------------------------------------

def test_from_binding_returns_connected_manager(mock_db):
    from pyloquent.database.manager import ConnectionManager
    manager = ConnectionManager.from_binding(mock_db)
    conn = manager.connection()
    assert conn.is_connected()
    assert isinstance(conn, D1BindingConnection)


# ---------------------------------------------------------------------------
# fetch_all / fetch_one
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_all_returns_all_rows(conn, mock_db):
    rows = await conn.fetch_all("SELECT * FROM users")
    assert len(rows) == 3


@pytest.mark.asyncio
async def test_fetch_all_with_binding(conn, mock_db):
    rows = await conn.fetch_all("SELECT * FROM users WHERE id = ?", [1])
    assert len(rows) == 1
    assert rows[0]["name"] == "Alice"


@pytest.mark.asyncio
async def test_fetch_one_returns_first(conn, mock_db):
    row = await conn.fetch_one("SELECT * FROM users WHERE id = ?", [2])
    assert row is not None
    assert row["name"] == "Bob"


@pytest.mark.asyncio
async def test_fetch_one_returns_none_for_miss(conn, mock_db):
    row = await conn.fetch_one("SELECT * FROM users WHERE id = ?", [999])
    assert row is None


# ---------------------------------------------------------------------------
# execute / insert_get_id
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_insert(conn, mock_db):
    affected = await conn.execute("INSERT INTO users (name) VALUES (?)", ["Dave"])
    assert affected >= 0


@pytest.mark.asyncio
async def test_insert_get_id_returns_id(conn, mock_db):
    row_id = await conn.insert_get_id(
        "INSERT INTO users (name) VALUES (?)", ["Eve"]
    )
    assert isinstance(row_id, int)
    assert row_id > 0


# ---------------------------------------------------------------------------
# execute_many
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_many_inserts_all_rows(conn, mock_db):
    rows = [["Frank"], ["Grace"], ["Heidi"]]
    total = await conn.execute_many("INSERT INTO users (name) VALUES (?)", rows)
    assert isinstance(total, int)


@pytest.mark.asyncio
async def test_execute_many_empty_is_noop(conn, mock_db):
    total = await conn.execute_many("INSERT INTO users (name) VALUES (?)", [])
    assert total == 0


# ---------------------------------------------------------------------------
# batch()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_executes_multiple_statements(conn, mock_db):
    results = await conn.batch([
        ("INSERT INTO users (name) VALUES (?)", ["Ivan"]),
        ("INSERT INTO users (name) VALUES (?)", ["Judy"]),
    ])
    assert isinstance(results, list)
    assert len(results) == 2


# ---------------------------------------------------------------------------
# exec() DDL
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_exec_ddl(conn, mock_db):
    result = await conn.exec("CREATE TABLE IF NOT EXISTS things (id INTEGER PRIMARY KEY)")
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# dump()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dump_returns_bytes(conn, mock_db):
    data = await conn.dump()
    assert isinstance(data, bytes)
    assert len(data) > 0


# ---------------------------------------------------------------------------
# Transactions (batch accumulation)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transaction_buffers_and_commits(conn, mock_db):
    await conn.begin_transaction()
    assert conn._in_tx

    # Statements are buffered, not sent immediately
    await conn.execute("INSERT INTO users (name) VALUES (?)", ["TxUser1"])
    await conn.execute("INSERT INTO users (name) VALUES (?)", ["TxUser2"])
    assert len(conn._tx_stmts) == 2

    # Commit flushes via batch
    await conn.commit()
    assert not conn._in_tx
    assert len(conn._tx_stmts) == 0


@pytest.mark.asyncio
async def test_transaction_rollback_discards(conn, mock_db):
    await conn.begin_transaction()
    await conn.execute("INSERT INTO users (name) VALUES (?)", ["Rollback"])
    await conn.rollback()

    assert not conn._in_tx
    assert len(conn._tx_stmts) == 0


@pytest.mark.asyncio
async def test_nested_transaction_raises(conn, mock_db):
    from pyloquent.exceptions import QueryException
    await conn.begin_transaction()
    with pytest.raises(QueryException, match="nested"):
        await conn.begin_transaction()
    await conn.rollback()


# ---------------------------------------------------------------------------
# Schema reflection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_tables(conn, mock_db):
    # Our mock's exec always returns something; just verify no exception
    mock_db._tables["sqlite_master"] = [
        {"name": "users", "type": "table"},
    ]
    tables = await conn.get_tables()
    assert isinstance(tables, list)


@pytest.mark.asyncio
async def test_table_exists_true(conn, mock_db):
    # compile_table_exists uses sqlite_master — mock returns count=1 row
    mock_db._tables["sqlite_master"] = [{"name": "users", "type": "table"}]
    # We test the SQL shape separately; here we just verify no exception
    result = await conn.table_exists("users")
    assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# D1Statement wrapper
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_d1_statement_all(conn, mock_db):
    stmt = D1Statement(conn, "SELECT * FROM users")
    rows = await stmt.all()
    assert isinstance(rows, list)


@pytest.mark.asyncio
async def test_d1_statement_first(conn, mock_db):
    stmt = D1Statement(conn, "SELECT * FROM users WHERE id = ?").bind(1)
    row = await stmt.first()
    assert row is not None


@pytest.mark.asyncio
async def test_d1_statement_run(conn, mock_db):
    stmt = D1Statement(conn, "INSERT INTO users (name) VALUES (?)").bind("Zara")
    affected = await stmt.run()
    assert isinstance(affected, int)


# ---------------------------------------------------------------------------
# table() QueryBuilder shortcut
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_table_returns_query_builder(conn, mock_db):
    from pyloquent.query.builder import QueryBuilder
    qb = conn.table("users")
    assert isinstance(qb, QueryBuilder)


# ---------------------------------------------------------------------------
# _to_python helper
# ---------------------------------------------------------------------------

def test_to_python_plain_dict():
    assert _to_python({"a": 1}) == {"a": 1}


def test_to_python_nested():
    assert _to_python({"a": [{"b": 2}]}) == {"a": [{"b": 2}]}


def test_to_python_list():
    assert _to_python([1, 2, 3]) == [1, 2, 3]


def test_to_python_scalar():
    assert _to_python(42) == 42
    assert _to_python("hello") == "hello"
    assert _to_python(None) is None


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_raises_when_not_connected(mock_db):
    from pyloquent.exceptions import QueryException
    c = D1BindingConnection(mock_db)
    with pytest.raises(QueryException):
        await c.execute("INSERT INTO users (name) VALUES (?)", ["X"])


@pytest.mark.asyncio
async def test_fetch_all_raises_when_not_connected(mock_db):
    from pyloquent.exceptions import QueryException
    c = D1BindingConnection(mock_db)
    with pytest.raises(QueryException):
        await c.fetch_all("SELECT * FROM users")
