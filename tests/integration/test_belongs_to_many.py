"""Integration tests for BelongsToMany relationship."""
import pytest
from typing import Optional
from pyloquent import Model


class BTMUser(Model):
    __table__ = "btm_users"
    __fillable__ = ["name", "email"]
    id: Optional[int] = None
    name: str
    email: str

    def roles(self):
        return self.belongs_to_many(BTMRole, table="btm_role_btm_user",
                                    foreign_key="btm_user_id",
                                    related_key="btm_role_id")


class BTMRole(Model):
    __table__ = "btm_roles"
    __fillable__ = ["name"]
    id: Optional[int] = None
    name: str

    def users(self):
        return self.belongs_to_many(BTMUser, table="btm_role_btm_user",
                                    foreign_key="btm_role_id",
                                    related_key="btm_user_id")


@pytest.fixture
async def btm_tables(sqlite_db):
    conn = sqlite_db.connection()
    await conn.execute("CREATE TABLE btm_users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, created_at TIMESTAMP, updated_at TIMESTAMP)")
    await conn.execute("CREATE TABLE btm_roles (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, created_at TIMESTAMP, updated_at TIMESTAMP)")
    await conn.execute("CREATE TABLE btm_role_btm_user (btm_user_id INTEGER NOT NULL, btm_role_id INTEGER NOT NULL, level INTEGER DEFAULT 0)")
    yield


@pytest.mark.asyncio
async def test_attach_and_get(sqlite_db, btm_tables):
    user = await BTMUser.create({"name": "Alice", "email": "alice@btm.com"})
    role = await BTMRole.create({"name": "admin"})
    await user.roles().attach([role.id])
    roles = await user.roles().get()
    assert len(roles) == 1
    assert roles[0].name == "admin"


@pytest.mark.asyncio
async def test_attach_single_id(sqlite_db, btm_tables):
    user = await BTMUser.create({"name": "Bob", "email": "bob@btm.com"})
    role = await BTMRole.create({"name": "editor"})
    await user.roles().attach(role.id)
    roles = await user.roles().get()
    assert len(roles) == 1


@pytest.mark.asyncio
async def test_attach_with_pivot_attributes(sqlite_db, btm_tables):
    user = await BTMUser.create({"name": "Carol", "email": "carol@btm.com"})
    role = await BTMRole.create({"name": "mod"})
    await user.roles().attach({role.id: {"level": 5}})
    roles = await user.roles().get()
    assert len(roles) == 1


@pytest.mark.asyncio
async def test_detach_specific(sqlite_db, btm_tables):
    user = await BTMUser.create({"name": "Dave", "email": "dave@btm.com"})
    r1 = await BTMRole.create({"name": "r1"})
    r2 = await BTMRole.create({"name": "r2"})
    await user.roles().attach([r1.id, r2.id])
    await user.roles().detach([r1.id])
    roles = await user.roles().get()
    assert len(roles) == 1
    assert roles[0].name == "r2"


@pytest.mark.asyncio
async def test_detach_single_id(sqlite_db, btm_tables):
    user = await BTMUser.create({"name": "Eve", "email": "eve@btm.com"})
    role = await BTMRole.create({"name": "viewer"})
    await user.roles().attach([role.id])
    await user.roles().detach(role.id)
    roles = await user.roles().get()
    assert len(roles) == 0


@pytest.mark.asyncio
async def test_detach_all(sqlite_db, btm_tables):
    user = await BTMUser.create({"name": "Frank", "email": "frank@btm.com"})
    r1 = await BTMRole.create({"name": "ra"})
    r2 = await BTMRole.create({"name": "rb"})
    await user.roles().attach([r1.id, r2.id])
    await user.roles().detach()
    roles = await user.roles().get()
    assert len(roles) == 0


@pytest.mark.asyncio
async def test_sync_replaces(sqlite_db, btm_tables):
    user = await BTMUser.create({"name": "Gina", "email": "gina@btm.com"})
    r1 = await BTMRole.create({"name": "old"})
    r2 = await BTMRole.create({"name": "new"})
    await user.roles().attach([r1.id])
    changes = await user.roles().sync([r2.id])
    assert r2.id in changes["attached"]
    assert r1.id in changes["detached"]
    roles = await user.roles().get()
    assert len(roles) == 1
    assert roles[0].name == "new"


@pytest.mark.asyncio
async def test_sync_without_detaching(sqlite_db, btm_tables):
    user = await BTMUser.create({"name": "Hal", "email": "hal@btm.com"})
    r1 = await BTMRole.create({"name": "keep"})
    r2 = await BTMRole.create({"name": "add"})
    await user.roles().attach([r1.id])
    changes = await user.roles().sync([r1.id, r2.id], detaching=False)
    assert r2.id in changes["attached"]
    assert changes["detached"] == []
    roles = await user.roles().get()
    assert len(roles) == 2


@pytest.mark.asyncio
async def test_toggle_attaches_new_detaches_existing(sqlite_db, btm_tables):
    user = await BTMUser.create({"name": "Iris", "email": "iris@btm.com"})
    r1 = await BTMRole.create({"name": "tog1"})
    r2 = await BTMRole.create({"name": "tog2"})
    await user.roles().attach([r1.id])
    changes = await user.roles().toggle([r1.id, r2.id])
    assert r1.id in changes["detached"]
    assert r2.id in changes["attached"]


@pytest.mark.asyncio
async def test_update_existing_pivot(sqlite_db, btm_tables):
    user = await BTMUser.create({"name": "Jack", "email": "jack@btm.com"})
    role = await BTMRole.create({"name": "updatable"})
    await user.roles().attach({role.id: {"level": 1}})
    count = await user.roles().update_existing_pivot(role.id, {"level": 9})
    assert count == 1


@pytest.mark.asyncio
async def test_find_related(sqlite_db, btm_tables):
    user = await BTMUser.create({"name": "Kim", "email": "kim@btm.com"})
    role = await BTMRole.create({"name": "findable"})
    await user.roles().attach([role.id])
    found = await user.roles().find(role.id)
    assert found is not None
    assert found.name == "findable"


@pytest.mark.asyncio
async def test_find_many_related(sqlite_db, btm_tables):
    user = await BTMUser.create({"name": "Leo", "email": "leo@btm.com"})
    r1 = await BTMRole.create({"name": "many1"})
    r2 = await BTMRole.create({"name": "many2"})
    await user.roles().attach([r1.id, r2.id])
    results = await user.roles().find_many([r1.id, r2.id])
    assert len(results) == 2


@pytest.mark.asyncio
async def test_where_pivot(sqlite_db, btm_tables):
    user = await BTMUser.create({"name": "Mia", "email": "mia@btm.com"})
    r1 = await BTMRole.create({"name": "wp1"})
    r2 = await BTMRole.create({"name": "wp2"})
    await user.roles().attach({r1.id: {"level": 1}, r2.id: {"level": 5}})
    roles = await user.roles().where_pivot("level", ">=", 5).get()
    assert len(roles) == 1
    assert roles[0].name == "wp2"


@pytest.mark.asyncio
async def test_with_pivot_columns(sqlite_db, btm_tables):
    user = await BTMUser.create({"name": "Ned", "email": "ned@btm.com"})
    role = await BTMRole.create({"name": "pivotcol"})
    await user.roles().attach({role.id: {"level": 7}})
    roles = await user.roles().with_pivot("level").get()
    assert len(roles) == 1


@pytest.mark.asyncio
async def test_inverse_belongs_to_many(sqlite_db, btm_tables):
    user = await BTMUser.create({"name": "Ora", "email": "ora@btm.com"})
    role = await BTMRole.create({"name": "inverse"})
    await user.roles().attach([role.id])
    users = await role.users().get()
    assert len(users) == 1
    assert users[0].name == "Ora"


@pytest.mark.asyncio
async def test_get_pivot_table_name_auto(sqlite_db, btm_tables):
    user = await BTMUser.create({"name": "Pat", "email": "pat@btm.com"})
    rel = user.roles()
    assert rel.table == "btm_role_btm_user"
