"""Integration tests for SoftDeletes trait."""

import pytest
from datetime import datetime
from typing import Optional

from pyloquent import Model, SoftDeletes
from pyloquent.observers.dispatcher import EventDispatcher


# ---------------------------------------------------------------------------
# Model with soft deletes
# ---------------------------------------------------------------------------

class SoftUser(Model, SoftDeletes):
    __table__ = "soft_users"
    __fillable__ = ["name", "email"]

    id: Optional[int] = None
    name: str
    email: str
    deleted_at: Optional[datetime] = None


@pytest.fixture(autouse=True)
def clear_soft_user_listeners():
    """Reset SoftUser event listeners before every test to prevent pollution."""
    EventDispatcher.forget_model(SoftUser)
    yield
    EventDispatcher.forget_model(SoftUser)


@pytest.fixture
async def soft_tables(sqlite_db):
    conn = sqlite_db.connection()
    await conn.execute(
        """
        CREATE TABLE soft_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            deleted_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )
    yield


# ---------------------------------------------------------------------------
# Basic soft delete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_soft_delete_sets_deleted_at(sqlite_db, soft_tables):
    user = await SoftUser.create({"name": "Alice", "email": "alice@sd.com"})
    await user.delete()
    assert user.deleted_at is not None


@pytest.mark.asyncio
async def test_trashed_returns_true_after_delete(sqlite_db, soft_tables):
    user = await SoftUser.create({"name": "Bob", "email": "bob@sd.com"})
    await user.delete()
    assert user.trashed()


@pytest.mark.asyncio
async def test_trashed_returns_false_before_delete(sqlite_db, soft_tables):
    user = await SoftUser.create({"name": "Carol", "email": "carol@sd.com"})
    assert not user.trashed()


# ---------------------------------------------------------------------------
# restore()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_restore_clears_deleted_at(sqlite_db, soft_tables):
    user = await SoftUser.create({"name": "Dave", "email": "dave@sd.com"})
    await user.delete()
    assert user.trashed()
    result = await user.restore()
    assert result is True
    assert not user.trashed()
    assert user.deleted_at is None


@pytest.mark.asyncio
async def test_restore_not_trashed_returns_false(sqlite_db, soft_tables):
    user = await SoftUser.create({"name": "Eve", "email": "eve@sd.com"})
    result = await user.restore()
    assert result is False


# ---------------------------------------------------------------------------
# force_delete()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_force_delete_removes_record(sqlite_db, soft_tables):
    user = await SoftUser.create({"name": "Frank", "email": "frank@sd.com"})
    user_id = user.id
    await user.force_delete()
    # Record should be gone
    found = await SoftUser.query.from_("soft_users").where("id", user_id).first()
    assert found is None


# ---------------------------------------------------------------------------
# Event: deleting / deleted
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deleting_event_fires(sqlite_db, soft_tables):
    fired = []
    SoftUser.on("deleting", lambda m: fired.append(m.id) or None)
    user = await SoftUser.create({"name": "Gina", "email": "gina@sd.com"})
    await user.delete()
    import asyncio
    await asyncio.sleep(0)
    assert user.id in fired


@pytest.mark.asyncio
async def test_deleting_event_abort(sqlite_db, soft_tables):
    """Returning False from 'deleting' should abort the delete."""
    user = await SoftUser.create({"name": "Hal", "email": "hal@sd.com"})

    # Register aborting listener
    SoftUser.on("deleting", lambda m: False)
    result = await user.delete()

    # deleted_at should not be set
    assert result is False
    assert not user.trashed()


@pytest.mark.asyncio
async def test_deleted_event_fires(sqlite_db, soft_tables):
    fired = []
    SoftUser.on("deleted", lambda m: fired.append(m.id) or None)
    user = await SoftUser.create({"name": "Iris", "email": "iris@sd.com"})
    await user.delete()
    import asyncio
    await asyncio.sleep(0)
    assert user.id in fired


# ---------------------------------------------------------------------------
# Event: restoring / restored
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_restoring_event_fires(sqlite_db, soft_tables):
    fired = []
    SoftUser.on("restoring", lambda m: fired.append(m.id) or None)
    user = await SoftUser.create({"name": "Jack", "email": "jack@sd.com"})
    await user.delete()
    await user.restore()
    import asyncio
    await asyncio.sleep(0)
    assert user.id in fired


@pytest.mark.asyncio
async def test_restoring_event_abort(sqlite_db, soft_tables):
    """Returning False from 'restoring' should abort the restore."""
    user = await SoftUser.create({"name": "Kim", "email": "kim@sd.com"})
    await user.delete()

    SoftUser.on("restoring", lambda m: False)
    result = await user.restore()

    assert result is False
    assert user.trashed()


@pytest.mark.asyncio
async def test_restored_event_fires(sqlite_db, soft_tables):
    fired = []
    SoftUser.on("restored", lambda m: fired.append(m.id) or None)
    user = await SoftUser.create({"name": "Leo", "email": "leo@sd.com"})
    await user.delete()
    await user.restore()
    import asyncio
    await asyncio.sleep(0)
    assert user.id in fired


# ---------------------------------------------------------------------------
# with_trashed / only_trashed / without_trashed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_with_trashed_includes_deleted(sqlite_db, soft_tables):
    u = await SoftUser.create({"name": "WT", "email": "wt@sd.com"})
    await u.delete()
    results = await SoftUser.with_trashed().get()
    ids = [r.id for r in results]
    assert u.id in ids


@pytest.mark.asyncio
async def test_default_query_excludes_deleted(sqlite_db, soft_tables):
    u = await SoftUser.create({"name": "DEL", "email": "del@sd.com"})
    await u.delete()
    results = await SoftUser.all()
    ids = [r.id for r in results]
    assert u.id not in ids


@pytest.mark.asyncio
async def test_only_trashed_returns_only_deleted(sqlite_db, soft_tables):
    u1 = await SoftUser.create({"name": "OT1", "email": "ot1@sd.com"})
    u2 = await SoftUser.create({"name": "OT2", "email": "ot2@sd.com"})
    await u1.delete()
    results = await SoftUser.only_trashed().get()
    ids = [r.id for r in results]
    assert u1.id in ids
    assert u2.id not in ids


@pytest.mark.asyncio
async def test_without_trashed_excludes_deleted(sqlite_db, soft_tables):
    u = await SoftUser.create({"name": "WOTH", "email": "woth@sd.com"})
    await u.delete()
    results = await SoftUser.without_trashed().get()
    ids = [r.id for r in results]
    assert u.id not in ids


# ---------------------------------------------------------------------------
# restore_trashed / force_delete_trashed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_restore_trashed_all(sqlite_db, soft_tables):
    u1 = await SoftUser.create({"name": "RT1", "email": "rt1@sd.com"})
    u2 = await SoftUser.create({"name": "RT2", "email": "rt2@sd.com"})
    await u1.delete()
    await u2.delete()
    await SoftUser.restore_trashed()
    results = await SoftUser.all()
    ids = [r.id for r in results]
    assert u1.id in ids
    assert u2.id in ids


@pytest.mark.asyncio
async def test_restore_trashed_specific_ids(sqlite_db, soft_tables):
    u1 = await SoftUser.create({"name": "RS1", "email": "rs1@sd.com"})
    u2 = await SoftUser.create({"name": "RS2", "email": "rs2@sd.com"})
    await u1.delete()
    await u2.delete()
    await SoftUser.restore_trashed([u1.id])
    active = await SoftUser.all()
    ids = [r.id for r in active]
    assert u1.id in ids
    assert u2.id not in ids


@pytest.mark.asyncio
async def test_force_delete_trashed_all(sqlite_db, soft_tables):
    u = await SoftUser.create({"name": "FDT", "email": "fdt@sd.com"})
    await u.delete()
    await SoftUser.force_delete_trashed()
    results = await SoftUser.with_trashed().get()
    ids = [r.id for r in results]
    assert u.id not in ids


@pytest.mark.asyncio
async def test_force_delete_trashed_specific(sqlite_db, soft_tables):
    u1 = await SoftUser.create({"name": "FDS1", "email": "fds1@sd.com"})
    u2 = await SoftUser.create({"name": "FDS2", "email": "fds2@sd.com"})
    await u1.delete()
    await u2.delete()
    await SoftUser.force_delete_trashed([u1.id])
    remaining = await SoftUser.with_trashed().get()
    ids = [r.id for r in remaining]
    assert u1.id not in ids
    assert u2.id in ids


# ---------------------------------------------------------------------------
# force_delete event
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_force_delete_fires_deleting_event(sqlite_db, soft_tables):
    fired = []
    SoftUser.on("deleting", lambda m: fired.append("deleting") or None)
    u = await SoftUser.create({"name": "FDE", "email": "fde@sd.com"})
    await u.force_delete()
    import asyncio
    await asyncio.sleep(0)
    assert "deleting" in fired


@pytest.mark.asyncio
async def test_force_delete_aborted_by_event(sqlite_db, soft_tables):
    SoftUser.on("deleting", lambda m: False)
    u = await SoftUser.create({"name": "FDA", "email": "fda@sd.com"})
    result = await u.force_delete()
    assert result is False
