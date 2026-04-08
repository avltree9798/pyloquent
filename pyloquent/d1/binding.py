"""Native Cloudflare D1 binding connection for Pyloquent ORM.

This module provides :class:`D1BindingConnection`, a full Pyloquent
:class:`~pyloquent.database.connection.Connection` implementation that speaks
directly to a **Cloudflare Workers D1 binding** (``env.DB``) without going
through the HTTP API.

Supported environments
----------------------
- **Python Workers** — Cloudflare's native Python Worker runtime exposes D1
  bindings as awaitable JavaScript proxy objects via Pyodide.  Import this
  module inside your ``worker.py`` and pass the binding directly.
- **Test / mock** — Any Python object that implements the D1 binding duck-type
  (``prepare``, ``exec``, ``batch``) works, enabling fully offline unit tests.

Quickstart (Worker)
-------------------
::

    # src/entry.py  — wrangler must have compatibility_flags = ["python_workers"]
    from workers import Response, WorkerEntrypoint
    from pyloquent import ConnectionManager, Model, set_manager
    from typing import Optional

    class User(Model):
        __table__ = 'users'
        __fillable__ = ['name', 'email']
        id: Optional[int] = None
        name: str
        email: str

    class Default(WorkerEntrypoint):
        async def fetch(self, request):
            # self.env.DB is the D1 binding declared in wrangler.jsonc
            manager = ConnectionManager.from_binding(self.env.DB)
            set_manager(manager)

            users = await User.where('active', True).get()
            return Response.json(users.to_dict_list())

Batch / atomic writes
---------------------
D1 Worker bindings do not support explicit ``BEGIN``/``COMMIT``.  Instead,
multiple statements are sent atomically via ``db.batch()``.  Pyloquent
transparently accumulates statements opened with :meth:`begin_transaction` and
flushes them with :meth:`commit`.

::

    async with manager.transaction():
        await User.create({'name': 'Alice'})
        await Post.create({'user_id': 1, 'title': 'Hello'})
    # Both statements sent in a single db.batch() call.

D1 Binding API reference
-------------------------
The official Python Workers D1 API (``compatibility_flags = ["python_workers"]``):

``db.prepare(sql)``
    Returns a ``D1PreparedStatement``.

``stmt.bind(*params)``
    Returns a bound copy of the statement with positional parameters.

``stmt.run()``
    **Primary method** — execute the statement and return a ``D1Result``
    object containing ``results``, ``meta`` (``changes``, ``last_row_id``),
    and ``success``.  Works for both SELECT and write statements.
    (Official docs: ``await self.env.DB.prepare("SQL").run()``)

``stmt.all()``
    Alternative to ``run()`` — semantically identical in D1's JS API.
    Pyloquent prefers ``run()`` to match the official Python Workers docs.

``stmt.first()``
    Returns the first row dict or ``None``.

``db.exec(sql)``
    Run raw SQL with no parameter binding (DDL etc.).
    Returns ``{count: int, duration: float}``.

``db.batch([stmts])``
    Execute a list of prepared statements atomically.
    Returns a list of ``D1Result`` objects.

``db.dump()``
    Return an ``ArrayBuffer`` of the SQLite database file.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Tuple

from pyloquent.database.connection import Connection
from pyloquent.exceptions import QueryException
from pyloquent.grammars.sqlite_grammar import SQLiteGrammar


# ---------------------------------------------------------------------------
# JS proxy → Python conversion helpers
# ---------------------------------------------------------------------------

def _to_python(obj: Any) -> Any:
    """Recursively convert a JS proxy object to a plain Python value.

    Handles both real Pyodide ``JsProxy`` objects (in the Workers runtime)
    and ordinary Python dicts/lists (in tests / mock mode).

    Args:
        obj: Value to convert.

    Returns:
        Plain Python value.
    """
    # Real Pyodide JsProxy — convert to Python native
    try:
        from pyodide.ffi import JsProxy  # type: ignore[import]
        if isinstance(obj, JsProxy):
            return obj.to_py()
    except ImportError:
        pass

    # Already Python
    if isinstance(obj, dict):
        return {k: _to_python(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_python(v) for v in obj]
    return obj


async def _await_js(value: Any) -> Any:
    """Await a value that may be a JS Promise or a plain Python coroutine.

    In Cloudflare's Python Worker runtime, D1 calls return JS Promise objects
    that can be awaited directly.  In mock mode they may be plain coroutines
    or plain values.

    Args:
        value: Promise, coroutine, or plain value.

    Returns:
        Resolved value.
    """
    if asyncio.iscoroutine(value):
        return await value
    # JS promise proxy (Pyodide) — it is awaitable
    if hasattr(value, "__await__"):
        return await value
    return value


# ---------------------------------------------------------------------------
# D1BindingConnection
# ---------------------------------------------------------------------------

class D1BindingConnection(Connection):
    """Full Pyloquent connection backed by a native Cloudflare D1 binding.

    Pass the raw D1 binding object (``env.DB`` in a Worker, or a mock in
    tests) to the constructor.  No HTTP credentials or network calls are
    required — all queries go through the in-process Workers binding.

    Args:
        binding: The D1 binding object (``env.DB`` or a compatible mock).
        config: Optional extra config dict (passed to the base class).

    Attributes:
        grammar: :class:`~pyloquent.grammars.sqlite_grammar.SQLiteGrammar` —
            D1 uses SQLite syntax.
    """

    def __init__(self, binding: Any, config: Optional[Dict[str, Any]] = None) -> None:
        """Initialise the D1 binding connection.

        Args:
            binding: Raw D1 binding object.
            config: Optional config dict (for compatibility with base class).
        """
        super().__init__(config or {"driver": "d1_binding"})
        self._binding = binding
        self._grammar = SQLiteGrammar()
        self._connected = False

        # Transaction accumulation buffer
        self._in_tx: bool = False
        self._tx_stmts: List[Tuple[str, Optional[List[Any]]]] = []

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    @property
    def grammar(self) -> SQLiteGrammar:
        """SQL grammar (SQLite dialect)."""
        return self._grammar

    def get_grammar(self) -> SQLiteGrammar:
        """Return the SQLite grammar.

        Returns:
            :class:`~pyloquent.grammars.sqlite_grammar.SQLiteGrammar` instance.
        """
        return self._grammar

    async def connect(self) -> None:
        """Mark the connection as ready.

        D1 bindings are always available in the Workers runtime — there is no
        TCP handshake to perform.
        """
        if self._binding is None:
            raise QueryException("D1 binding is None — cannot connect")
        self._connected = True

    async def disconnect(self) -> None:
        """Release the binding reference."""
        self._binding = None
        self._connected = False
        self._in_tx = False
        self._tx_stmts.clear()

    def is_connected(self) -> bool:
        """Return ``True`` if the binding is available.

        Returns:
            Connection status.
        """
        return self._connected and self._binding is not None

    # ------------------------------------------------------------------
    # Core statement helpers
    # ------------------------------------------------------------------

    def _prepare(self, sql: str) -> Any:
        """Build a prepared statement from the binding.

        Args:
            sql: SQL string with ``?`` placeholders.

        Returns:
            D1PreparedStatement proxy.
        """
        return self._binding.prepare(sql)

    def _bind(self, stmt: Any, bindings: Optional[List[Any]]) -> Any:
        """Optionally bind parameters to a prepared statement.

        Args:
            stmt: D1PreparedStatement.
            bindings: List of parameter values, or ``None``.

        Returns:
            Bound (or unbound) statement.
        """
        if bindings:
            return stmt.bind(*bindings)
        return stmt

    # ------------------------------------------------------------------
    # Execute (write statements)
    # ------------------------------------------------------------------

    async def execute(self, sql: str, bindings: Optional[List[Any]] = None) -> Any:
        """Execute a write statement (INSERT / UPDATE / DELETE / DDL).

        When inside a :meth:`begin_transaction` block the statement is
        buffered; it will be sent atomically when :meth:`commit` is called.

        Args:
            sql: SQL statement with ``?`` placeholders.
            bindings: Parameter values.

        Returns:
            Number of affected rows (``int``).

        Raises:
            :class:`~pyloquent.exceptions.QueryException`: On execution error.
        """
        if not self.is_connected():
            raise QueryException("D1 binding is not connected")

        if self._in_tx:
            # Buffer for later batch flush
            self._tx_stmts.append((sql, bindings))
            return 0

        try:
            stmt = self._bind(self._prepare(sql), bindings)
            raw = await _await_js(stmt.run())
            result = _to_python(raw)
            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            return meta.get("changes", 0)
        except QueryException:
            raise
        except Exception as exc:
            raise QueryException(f"D1 execute failed: {exc}", sql) from exc

    async def execute_many(self, sql: str, rows: List[List[Any]]) -> int:
        """Execute a parameterised statement for multiple rows via D1 batch.

        Uses D1's native ``db.batch()`` so all rows are sent atomically in a
        single round-trip.

        Args:
            sql: SQL template with ``?`` placeholders.
            rows: List of parameter lists, one per row.

        Returns:
            Total number of rows affected.

        Raises:
            :class:`~pyloquent.exceptions.QueryException`: On batch error.
        """
        if not self.is_connected():
            raise QueryException("D1 binding is not connected")

        if not rows:
            return 0

        try:
            stmts = [self._bind(self._prepare(sql), row) for row in rows]
            results = await self._batch_raw(stmts)
            total = sum(
                (r.get("meta", {}).get("changes", 0) if isinstance(r, dict) else 0)
                for r in results
            )
            return total
        except QueryException:
            raise
        except Exception as exc:
            raise QueryException(f"D1 execute_many failed: {exc}", sql) from exc

    # ------------------------------------------------------------------
    # Fetch
    # ------------------------------------------------------------------

    async def fetch_all(
        self, sql: str, bindings: Optional[List[Any]] = None
    ) -> List[Dict[str, Any]]:
        """Fetch all rows from a SELECT query.

        Uses ``stmt.run()`` as the primary method (matching the official
        Cloudflare Python Workers documentation), falling back to
        ``stmt.all()`` if ``run`` is unavailable on the proxy object.

        Args:
            sql: SQL query with ``?`` placeholders.
            bindings: Parameter values.

        Returns:
            List of row dicts.

        Raises:
            :class:`~pyloquent.exceptions.QueryException`: On query error.
        """
        if not self.is_connected():
            raise QueryException("D1 binding is not connected")

        try:
            stmt = self._bind(self._prepare(sql), bindings)
            raw = await _await_js(stmt.run())
            result = _to_python(raw)
            if isinstance(result, dict):
                rows = result.get("results", [])
            elif isinstance(result, list):
                rows = result
            else:
                rows = []
            return [r for r in rows if isinstance(r, dict)]
        except QueryException:
            raise
        except Exception as exc:
            raise QueryException(f"D1 fetch_all failed: {exc}", sql) from exc

    async def fetch_one(
        self, sql: str, bindings: Optional[List[Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Fetch the first row from a SELECT query.

        Prefers ``stmt.first()`` when available (a D1 JS API optimisation).
        Falls back to ``stmt.run()`` and returns the first element of the
        ``results`` list when ``first`` is not present on the proxy object.

        Args:
            sql: SQL query with ``?`` placeholders.
            bindings: Parameter values.

        Returns:
            Row dict or ``None``.

        Raises:
            :class:`~pyloquent.exceptions.QueryException`: On query error.
        """
        if not self.is_connected():
            raise QueryException("D1 binding is not connected")

        try:
            stmt = self._bind(self._prepare(sql), bindings)
            # Use stmt.first() when available (D1 JS API optimisation),
            # otherwise fall through to run() and take the first result.
            if hasattr(stmt, "first"):
                raw = await _await_js(stmt.first())
                if raw is None:
                    return None
                result = _to_python(raw)
                # first() can return a plain dict or a D1Result
                if isinstance(result, dict) and "results" in result:
                    rows = result["results"]
                    return rows[0] if rows else None
                return result if isinstance(result, dict) else None
            else:
                rows = await self.fetch_all(sql, bindings)
                return rows[0] if rows else None
        except QueryException:
            raise
        except Exception as exc:
            raise QueryException(f"D1 fetch_one failed: {exc}", sql) from exc

    async def insert_get_id(
        self, sql: str, bindings: Optional[List[Any]] = None, sequence: Optional[str] = None
    ) -> Optional[int]:
        """Execute an INSERT and return the auto-generated primary key.

        D1 exposes the last inserted row ID in ``result.meta.last_row_id``.

        Args:
            sql: INSERT SQL with ``?`` placeholders.
            bindings: Parameter values.
            sequence: Ignored (D1 always uses ``last_row_id``).

        Returns:
            Last inserted row ID, or ``None``.

        Raises:
            :class:`~pyloquent.exceptions.QueryException`: On insert error.
        """
        if not self.is_connected():
            raise QueryException("D1 binding is not connected")

        try:
            stmt = self._bind(self._prepare(sql), bindings)
            raw = await _await_js(stmt.run())
            result = _to_python(raw)
            meta = result.get("meta", {}) if isinstance(result, dict) else {}
            return meta.get("last_row_id") or meta.get("lastRowId")
        except QueryException:
            raise
        except Exception as exc:
            raise QueryException(f"D1 insert_get_id failed: {exc}", sql) from exc

    # ------------------------------------------------------------------
    # Batch API
    # ------------------------------------------------------------------

    async def _batch_raw(self, stmts: List[Any]) -> List[Dict[str, Any]]:
        """Send a list of prepared statements via ``db.batch()``.

        Args:
            stmts: List of D1PreparedStatement (possibly bound) objects.

        Returns:
            List of result dicts, one per statement.

        Raises:
            :class:`~pyloquent.exceptions.QueryException`: On batch error.
        """
        try:
            raw = await _await_js(self._binding.batch(stmts))
            results = _to_python(raw)
            if isinstance(results, list):
                return results
            return []
        except QueryException:
            raise
        except Exception as exc:
            raise QueryException(f"D1 batch failed: {exc}") from exc

    async def batch(
        self, queries: List[Tuple[str, Optional[List[Any]]]]
    ) -> List[List[Dict[str, Any]]]:
        """Execute multiple SQL statements atomically via ``db.batch()``.

        This is the recommended way to perform multiple writes inside a single
        atomic operation when not using the :meth:`begin_transaction` context.

        Args:
            queries: List of ``(sql, bindings)`` tuples.

        Returns:
            List of result sets, one per statement.  Write statements produce
            an empty list; SELECT statements return row dicts.

        Raises:
            :class:`~pyloquent.exceptions.QueryException`: On batch error.

        Example::

            results = await conn.batch([
                ("INSERT INTO users (name) VALUES (?)", ["Alice"]),
                ("INSERT INTO users (name) VALUES (?)", ["Bob"]),
                ("SELECT COUNT(*) AS n FROM users", None),
            ])
            count = results[-1][0]["n"]  # 2
        """
        if not self.is_connected():
            raise QueryException("D1 binding is not connected")

        stmts = [self._bind(self._prepare(sql), b) for sql, b in queries]
        raw_results = await self._batch_raw(stmts)
        output = []
        for r in raw_results:
            if isinstance(r, dict):
                rows = r.get("results", [])
                output.append(rows if isinstance(rows, list) else [])
            else:
                output.append([])
        return output

    # ------------------------------------------------------------------
    # DDL via exec()
    # ------------------------------------------------------------------

    async def exec(self, sql: str) -> Dict[str, Any]:
        """Execute a raw SQL statement with no parameter binding.

        Intended for DDL (``CREATE TABLE``, ``DROP INDEX``, etc.).  D1's
        ``db.exec()`` does not support parameter binding.

        Args:
            sql: Raw SQL statement.

        Returns:
            Dict with ``count`` (statements executed) and ``duration`` (ms).

        Raises:
            :class:`~pyloquent.exceptions.QueryException`: On execution error.
        """
        if not self.is_connected():
            raise QueryException("D1 binding is not connected")

        try:
            raw = await _await_js(self._binding.exec(sql))
            return _to_python(raw) if raw else {}
        except QueryException:
            raise
        except Exception as exc:
            raise QueryException(f"D1 exec failed: {exc}", sql) from exc

    # ------------------------------------------------------------------
    # Database dump
    # ------------------------------------------------------------------

    async def dump(self) -> bytes:
        """Export the D1 database as a raw SQLite file (``ArrayBuffer``).

        Returns a ``bytes`` object containing the binary SQLite database.
        Useful for backups, migrations, or local inspection.

        Returns:
            Raw SQLite file bytes.

        Raises:
            :class:`~pyloquent.exceptions.QueryException`: On dump error.

        Example::

            data = await conn.dump()
            with open('backup.sqlite', 'wb') as f:
                f.write(data)
        """
        if not self.is_connected():
            raise QueryException("D1 binding is not connected")

        try:
            raw = await _await_js(self._binding.dump())
            if isinstance(raw, (bytes, bytearray)):
                return bytes(raw)
            # JS ArrayBuffer proxy — convert via Pyodide
            try:
                from pyodide.ffi import JsProxy  # type: ignore[import]
                if isinstance(raw, JsProxy):
                    return bytes(raw.to_py())
            except ImportError:
                pass
            # Fallback: memoryview / buffer protocol
            return bytes(raw)
        except QueryException:
            raise
        except Exception as exc:
            raise QueryException(f"D1 dump failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Transaction (via batch accumulation)
    # ------------------------------------------------------------------

    async def begin_transaction(self) -> None:
        """Begin a logical transaction.

        D1 Worker bindings do not support ``BEGIN``/``COMMIT`` SQL.  Instead,
        all statements executed while in a transaction are buffered and flushed
        atomically via :meth:`commit` using ``db.batch()``.
        """
        if self._in_tx:
            raise QueryException("D1 does not support nested transactions")
        self._in_tx = True
        self._tx_stmts.clear()

    async def commit(self) -> None:
        """Commit the buffered transaction by flushing via ``db.batch()``.

        All statements accumulated since :meth:`begin_transaction` are sent
        in a single atomic ``db.batch()`` call.
        """
        if not self._in_tx:
            return
        stmts_snapshot = list(self._tx_stmts)
        self._in_tx = False
        self._tx_stmts.clear()

        if not stmts_snapshot:
            return

        stmts = [self._bind(self._prepare(sql), b) for sql, b in stmts_snapshot]
        await self._batch_raw(stmts)

    async def rollback(self) -> None:
        """Discard all buffered transaction statements.

        No SQL is sent to D1 — the accumulated statements are simply dropped.
        """
        self._in_tx = False
        self._tx_stmts.clear()

    # ------------------------------------------------------------------
    # Schema reflection (delegates to SQLiteGrammar)
    # ------------------------------------------------------------------

    async def get_tables(self) -> List[str]:
        """Return the names of all user tables in the D1 database.

        Returns:
            List of table name strings.
        """
        sql = self._grammar.compile_get_tables()
        rows = await self.fetch_all(sql)
        return [r["name"] for r in rows if "name" in r]

    async def table_exists(self, table: str) -> bool:
        """Check whether a table exists.

        Args:
            table: Table name.

        Returns:
            ``True`` if the table exists.
        """
        sql, bindings = self._grammar.compile_table_exists(table)
        row = await self.fetch_one(sql, bindings)
        if row is None:
            return False
        val = next(iter(row.values()), 0)
        return bool(val)

    async def column_exists(self, table: str, column: str) -> bool:
        """Check whether a column exists in a table.

        Args:
            table: Table name.
            column: Column name.

        Returns:
            ``True`` if the column exists.
        """
        sql, bindings = self._grammar.compile_column_exists(table, column)
        row = await self.fetch_one(sql, bindings)
        if row is None:
            return False
        val = next(iter(row.values()), 0)
        return bool(val)

    async def get_columns(self, table: str) -> List[Dict[str, Any]]:
        """Return column information for a table.

        Args:
            table: Table name.

        Returns:
            List of column info dicts (``cid``, ``name``, ``type``, ``notnull``, ``dflt_value``, ``pk``).
        """
        sql, bindings = self._grammar.compile_get_columns(table)
        return await self.fetch_all(sql, bindings)

    async def get_indexes(self, table: str) -> List[Dict[str, Any]]:
        """Return index information for a table.

        Args:
            table: Table name.

        Returns:
            List of index info dicts.
        """
        sql, bindings = self._grammar.compile_get_indexes(table)
        return await self.fetch_all(sql, bindings)

    async def get_foreign_keys(self, table: str) -> List[Dict[str, Any]]:
        """Return foreign key information for a table.

        Args:
            table: Table name.

        Returns:
            List of foreign key info dicts.
        """
        sql, bindings = self._grammar.compile_get_foreign_keys(table)
        return await self.fetch_all(sql, bindings)

    # ------------------------------------------------------------------
    # QueryBuilder factory shortcut
    # ------------------------------------------------------------------

    def table(self, name: str) -> "QueryBuilder":  # noqa: F821
        """Return a QueryBuilder scoped to ``name``.

        Args:
            name: Table name.

        Returns:
            :class:`~pyloquent.query.builder.QueryBuilder` instance.
        """
        from pyloquent.query.builder import QueryBuilder
        return QueryBuilder(self._grammar, connection=self).from_(name)


# ---------------------------------------------------------------------------
# D1Statement — friendly wrapper for standalone use
# ---------------------------------------------------------------------------

class D1Statement:
    """Thin Python wrapper around a D1 prepared statement.

    Provides a more idiomatic interface when using ``D1BindingConnection``
    directly rather than through the QueryBuilder.

    Args:
        conn: Owning :class:`D1BindingConnection`.
        sql: SQL string with ``?`` placeholders.

    Example::

        stmt = D1Statement(conn, "SELECT * FROM users WHERE id = ?")
        rows = await stmt.bind(1).all()
    """

    def __init__(self, conn: D1BindingConnection, sql: str) -> None:
        """Initialise the statement.

        Args:
            conn: Owning connection.
            sql: SQL string.
        """
        self._conn = conn
        self._sql = sql
        self._bindings: Optional[List[Any]] = None

    def bind(self, *params: Any) -> "D1Statement":
        """Bind positional parameters to the statement.

        Args:
            *params: Parameter values (one per ``?`` placeholder).

        Returns:
            Self for chaining.
        """
        self._bindings = list(params)
        return self

    async def all(self) -> List[Dict[str, Any]]:
        """Execute and return all result rows.

        Returns:
            List of row dicts.
        """
        return await self._conn.fetch_all(self._sql, self._bindings)

    async def first(self) -> Optional[Dict[str, Any]]:
        """Execute and return the first result row.

        Returns:
            Row dict or ``None``.
        """
        return await self._conn.fetch_one(self._sql, self._bindings)

    async def run(self) -> int:
        """Execute a write statement and return the number of affected rows.

        Returns:
            Number of rows affected.
        """
        return await self._conn.execute(self._sql, self._bindings)
