"""Integration tests targeting uncovered lines in database/ORM/sync layers."""

from __future__ import annotations

from typing import ClassVar, Dict, List, Optional
from unittest.mock import patch

import pytest

from pyloquent.database.manager import ConnectionManager, set_manager
from pyloquent.database.sqlite_connection import SQLiteConnection
from pyloquent.exceptions import QueryException
from pyloquent.orm.identity_map import IdentityMap
from pyloquent.orm.model import Model
from pyloquent.sync import SyncConnectionManager, SyncQueryProxy, run_sync


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def raw_sqlite():
    """A bare SQLiteConnection (not via manager) for direct method tests."""
    conn = SQLiteConnection({"database": ":memory:"})
    await conn.connect()
    await conn.execute(
        "CREATE TABLE things (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL)"
    )
    yield conn
    await conn.disconnect()


@pytest.fixture
async def gap_manager():
    """ConnectionManager wired to an in-memory SQLite DB."""
    mgr = ConnectionManager()
    mgr.add_connection("default", {"driver": "sqlite", "database": ":memory:"}, default=True)
    from pyloquent.database.manager import set_manager as _set
    _set(mgr)
    await mgr.connect()
    conn = mgr.connection()
    await conn.execute(
        "CREATE TABLE gap_users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL)"
    )
    yield mgr
    await mgr.disconnect()


# ---------------------------------------------------------------------------
# sqlite_connection — line 70 (journal_mode pragma)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sqlite_journal_mode_wal():
    """Connecting with journal_mode exercises the PRAGMA path (line 70)."""
    conn = SQLiteConnection({"database": ":memory:", "journal_mode": "WAL"})
    await conn.connect()
    assert conn._connected
    await conn.disconnect()


# ---------------------------------------------------------------------------
# sqlite_connection — lines 165-166 (execute_many not connected)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sqlite_execute_many_not_connected():
    """execute_many raises QueryException when not connected (lines 165-166)."""
    conn = SQLiteConnection({"database": ":memory:"})
    with pytest.raises(QueryException, match="Not connected"):
        await conn.execute_many("INSERT INTO t VALUES (?)", [[1]])


# ---------------------------------------------------------------------------
# sqlite_connection — lines 173-175 (execute_many bad SQL)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sqlite_execute_many_bad_sql(raw_sqlite):
    """execute_many wraps driver errors in QueryException (lines 173-175)."""
    with pytest.raises(QueryException):
        await raw_sqlite.execute_many("INSERT INTO nonexistent VALUES (?)", [[1]])


# ---------------------------------------------------------------------------
# database/connection.py — lines 81-85 (base execute_many fallback)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_base_execute_many_fallback(raw_sqlite):
    """Connection.execute_many base impl loops rows via execute (lines 81-85).

    We call the *base class* method directly, bypassing the SQLite override.
    """
    from pyloquent.database.connection import Connection

    count = await Connection.execute_many(
        raw_sqlite,
        "INSERT INTO things (name) VALUES (?)",
        [["alpha"], ["beta"], ["gamma"]],
    )
    assert count == 3
    rows = await raw_sqlite.fetch_all("SELECT name FROM things ORDER BY name")
    names = [r["name"] for r in rows]
    assert names == ["alpha", "beta", "gamma"]


# ---------------------------------------------------------------------------
# database/manager.py — lines 120-128 (d1_binding without 'binding' key)
# ---------------------------------------------------------------------------

def test_manager_d1_binding_no_binding_key():
    """_create_connection raises when d1_binding driver has no 'binding' (lines 120-128)."""
    from pyloquent.exceptions import PyloquentException

    mgr = ConnectionManager()
    with pytest.raises(PyloquentException, match="binding"):
        mgr._create_connection("test", {"driver": "d1_binding"})


def test_manager_d1_binding_with_mock_binding():
    """_create_connection returns D1BindingConnection when binding is provided (line 128)."""
    from unittest.mock import MagicMock, patch

    mock_conn_cls = MagicMock()
    mock_binding = MagicMock()

    mgr = ConnectionManager()
    config = {"driver": "d1_binding", "binding": mock_binding}

    with patch("pyloquent.database.manager.D1BindingConnection", mock_conn_cls, create=True):
        # Patch the import inside _create_connection
        with patch.dict("sys.modules", {"pyloquent.d1.binding": MagicMock(D1BindingConnection=mock_conn_cls)}):
            conn = mgr._create_connection("test", config)
    mock_conn_cls.assert_called_once_with(mock_binding, config)
    assert conn is mock_conn_cls.return_value


# ---------------------------------------------------------------------------
# database/manager.py — lines 224, 228 (connect_all / disconnect_all)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_manager_connect_all_disconnect_all():
    """connect_all / disconnect_all are aliases that exercise lines 224 and 228."""
    mgr = ConnectionManager()
    mgr.add_connection("default", {"driver": "sqlite", "database": ":memory:"}, default=True)
    await mgr.connect_all()
    conn = mgr.connection()
    assert conn.is_connected()
    await mgr.disconnect_all()
    assert not conn.is_connected()


# ---------------------------------------------------------------------------
# model.py — lines 208-210 (composite PK _perform_update)
# ---------------------------------------------------------------------------

@pytest.fixture
async def composite_pk_table(gap_manager):
    conn = gap_manager.connection()
    await conn.execute(
        """
        CREATE TABLE order_items_gap (
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER DEFAULT 1,
            PRIMARY KEY (order_id, product_id)
        )
        """
    )
    yield gap_manager


class OrderItemGap(Model):
    __table__ = "order_items_gap"
    __primary_key__ = ["order_id", "product_id"]
    __incrementing__ = False
    __fillable__ = ["order_id", "product_id", "quantity"]
    __timestamps__ = False

    order_id: int
    product_id: int
    quantity: int = 1


@pytest.mark.asyncio
async def test_composite_pk_update(composite_pk_table):
    """Updating a composite-PK model exercises the list-PK where loop (lines 208-210)."""
    item = OrderItemGap(order_id=1, product_id=5, quantity=2)
    await item.save()

    item.quantity = 99
    await item.save()

    found = await OrderItemGap.query.where("order_id", 1).where("product_id", 5).first()
    assert found.quantity == 99


# ---------------------------------------------------------------------------
# model.py — line 879 (composite PK component that is None → skip del)
# ---------------------------------------------------------------------------

class _OrderItemNullable(Model):
    """Composite PK model with Optional fields so None is accepted by Pydantic."""

    __table__ = "order_items_gap"
    __primary_key__ = ["order_id", "product_id"]
    __incrementing__ = False
    __fillable__ = ["order_id", "product_id", "quantity"]
    __timestamps__ = False

    order_id: Optional[int] = None
    product_id: Optional[int] = None
    quantity: int = 1


def test_composite_pk_none_component_skipped():
    """_get_attributes_for_save deletes None composite PK components (line 879)."""
    item = _OrderItemNullable(product_id=10, quantity=3)
    attrs = item._get_attributes_for_save()
    # order_id was None → deleted; product_id kept
    assert "order_id" not in attrs
    assert attrs["product_id"] == 10


# ---------------------------------------------------------------------------
# model.py — lines 1722-1726 (_cast_attribute JSON fallback, bypassing TypeDecorator)
# ---------------------------------------------------------------------------

def test_cast_attribute_json_fallback_str():
    """_cast_attribute JSON str→dict fallback when TypeDecorator is bypassed (lines 1722-1725)."""
    class _M(Model):
        __table__ = "x"
        __timestamps__ = False
        __casts__: ClassVar[Dict] = {"data": "json"}
        id: Optional[int] = None
        data: Optional[dict] = None

    m = _M(id=1, data=None)
    with patch("pyloquent.orm.type_decorator.get_type", return_value=None):
        result = m._cast_attribute("data", '{"k": 1}')
    assert result == {"k": 1}


def test_cast_attribute_json_fallback_already_dict():
    """_cast_attribute JSON already-dict fallback (line 1726)."""
    class _M(Model):
        __table__ = "x"
        __timestamps__ = False
        __casts__: ClassVar[Dict] = {"data": "json"}
        id: Optional[int] = None
        data: Optional[dict] = None

    m = _M(id=1, data=None)
    d = {"k": 1}
    with patch("pyloquent.orm.type_decorator.get_type", return_value=None):
        result = m._cast_attribute("data", d)
    assert result is d


# ---------------------------------------------------------------------------
# model.py — lines 1776-1780 (_set_cast_attribute JSON fallback)
# ---------------------------------------------------------------------------

def test_set_cast_attribute_json_fallback_dict():
    """_set_cast_attribute JSON dict→str fallback (lines 1776-1779)."""
    class _M(Model):
        __table__ = "x"
        __timestamps__ = False
        __casts__: ClassVar[Dict] = {"data": "json"}
        id: Optional[int] = None
        data: Optional[dict] = None

    m = _M(id=1, data=None)
    import json
    with patch("pyloquent.orm.type_decorator.get_type", return_value=None):
        result = m._set_cast_attribute("data", {"k": 1})
    assert result == json.dumps({"k": 1})


def test_set_cast_attribute_json_fallback_str_passthrough():
    """_set_cast_attribute JSON already-str passthrough (line 1780)."""
    class _M(Model):
        __table__ = "x"
        __timestamps__ = False
        __casts__: ClassVar[Dict] = {"data": "json"}
        id: Optional[int] = None
        data: Optional[dict] = None

    m = _M(id=1, data=None)
    with patch("pyloquent.orm.type_decorator.get_type", return_value=None):
        result = m._set_cast_attribute("data", '{"k":1}')
    assert result == '{"k":1}'


# ---------------------------------------------------------------------------
# builder — line 1728 (composite PK in identity map via first())
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_identity_map_composite_pk_first(composite_pk_table):
    """first() with identity map on composite-PK model exercises line 1728."""
    await OrderItemGap.query.insert({"order_id": 7, "product_id": 3, "quantity": 5})
    imap = IdentityMap()
    r1 = await OrderItemGap.query.with_identity_map(imap).where("order_id", 7).where("product_id", 3).first()
    r2 = await OrderItemGap.query.with_identity_map(imap).where("order_id", 7).where("product_id", 3).first()
    assert r1 is r2


# ---------------------------------------------------------------------------
# builder — lines 2497-2501, 2504, 2515 (identity map via get() / _hydrate_models)
# ---------------------------------------------------------------------------

@pytest.fixture
async def simple_user_table(gap_manager):
    """Ensure gap_users table exists and return manager."""
    yield gap_manager


class GapUser(Model):
    __table__ = "gap_users"
    __fillable__ = ["name"]
    __timestamps__ = False

    id: Optional[int] = None
    name: str


@pytest.mark.asyncio
async def test_identity_map_get_caches_objects(simple_user_table):
    """_hydrate_models uses identity map (lines 2497-2501, 2515): second get() returns same instances."""
    await GapUser.create({"name": "Hydrate1"})
    await GapUser.create({"name": "Hydrate2"})

    imap = IdentityMap()
    results1 = list(await GapUser.query.with_identity_map(imap).order_by("id").get())
    results2 = list(await GapUser.query.with_identity_map(imap).order_by("id").get())

    assert results1[0] is results2[0]
    assert results1[1] is results2[1]


@pytest.mark.asyncio
async def test_identity_map_hydrate_returns_cached(simple_user_table):
    """_hydrate_models returns the cached instance on a second pass (line 2504)."""
    u = await GapUser.create({"name": "CachedUser"})

    imap = IdentityMap()
    # First call — populates cache (line 2515)
    first_batch = list(await GapUser.query.with_identity_map(imap).where("id", u.id).get())
    # Second call — hits cached_model path (line 2504)
    second_batch = list(await GapUser.query.with_identity_map(imap).where("id", u.id).get())

    assert first_batch[0] is second_batch[0]


@pytest.mark.asyncio
async def test_identity_map_composite_pk_get(composite_pk_table):
    """_hydrate_models with composite PK + identity map exercises lines 2497-2498."""
    await OrderItemGap.query.insert({"order_id": 9, "product_id": 4, "quantity": 1})

    imap = IdentityMap()
    r1 = list(await OrderItemGap.query.with_identity_map(imap).where("order_id", 9).get())
    r2 = list(await OrderItemGap.query.with_identity_map(imap).where("order_id", 9).get())
    assert r1[0] is r2[0]


# ---------------------------------------------------------------------------
# sync — SyncConnectionManager + SyncQueryProxy (lines 126-162, 182, 200-218,
#          226, 230, 234, 238, 242, 246, 250, 254, 258)
# ---------------------------------------------------------------------------

def _make_sync_manager():
    return SyncConnectionManager({"default": {"driver": "sqlite", "database": ":memory:"}})


def test_sync_manager_context_manager():
    """SyncConnectionManager __enter__ / __exit__ (lines 141-148)."""
    with _make_sync_manager() as mgr:
        assert isinstance(mgr, SyncConnectionManager)


def test_sync_manager_explicit_connect_disconnect():
    """SyncConnectionManager.connect / disconnect (lines 133-139)."""
    mgr = _make_sync_manager()
    mgr.connect()
    mgr.disconnect()


def test_sync_query_proxy_table_and_get():
    """SyncConnectionManager.table returns SyncQueryProxy; .get() works (lines 150-162, 226)."""
    with _make_sync_manager() as mgr:
        conn = mgr._manager.connection()
        run_sync(conn.execute(
            "CREATE TABLE sync_items (id INTEGER PRIMARY KEY, val TEXT)"
        ))
        run_sync(conn.execute("INSERT INTO sync_items VALUES (1, 'hello')"))

        proxy = mgr.table("sync_items")
        assert isinstance(proxy, SyncQueryProxy)
        results = proxy.get()
        assert len(list(results)) == 1


def test_sync_proxy_explicit_terminals():
    """Exercise all explicit terminal methods on SyncQueryProxy (lines 226-258)."""
    with _make_sync_manager() as mgr:
        conn = mgr._manager.connection()
        run_sync(conn.execute(
            "CREATE TABLE sync_t (id INTEGER PRIMARY KEY AUTOINCREMENT, val TEXT)"
        ))

        # insert — fresh proxy each time to avoid state mutation
        mgr.table("sync_t").insert({"val": "a"})
        mgr.table("sync_t").insert({"val": "b"})

        # count
        assert mgr.table("sync_t").count() == 2

        # first
        first = mgr.table("sync_t").first()
        assert first is not None

        # find
        found = mgr.table("sync_t").find(first["id"])
        assert found is not None

        # exists
        assert mgr.table("sync_t").exists() is True

        # pluck
        vals = mgr.table("sync_t").pluck("val")
        assert len(vals) == 2

        # update via where chain
        mgr.table("sync_t").where("val", "a").update({"val": "A"})

        # delete via where chain
        mgr.table("sync_t").where("val", "b").delete()
        assert mgr.table("sync_t").count() == 1


def test_sync_proxy_getattr_chainable():
    """__getattr__ re-wraps QueryBuilder returns as SyncQueryProxy (lines 200-218)."""
    with _make_sync_manager() as mgr:
        conn = mgr._manager.connection()
        run_sync(conn.execute(
            "CREATE TABLE sync_chain (id INTEGER PRIMARY KEY, score INTEGER)"
        ))
        run_sync(conn.execute("INSERT INTO sync_chain VALUES (1, 10)"))
        run_sync(conn.execute("INSERT INTO sync_chain VALUES (2, 20)"))

        proxy = mgr.table("sync_chain")
        # order_by returns QueryBuilder → should be re-wrapped
        chained = proxy.order_by("score", "desc")
        assert isinstance(chained, SyncQueryProxy)
        results = list(chained.get())
        assert results[0]["score"] == 20


def test_sync_proxy_getattr_non_callable():
    """__getattr__ returns non-callable attribute directly (line 203)."""
    with _make_sync_manager() as mgr:
        conn = mgr._manager.connection()
        run_sync(conn.execute("CREATE TABLE sync_nc (id INTEGER PRIMARY KEY)"))
        proxy = mgr.table("sync_nc")
        # Access a non-callable attribute on the underlying builder
        table_name = proxy._table
        assert table_name == "sync_nc"
