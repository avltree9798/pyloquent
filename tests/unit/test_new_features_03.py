"""Unit tests for Pyloquent 0.3.0 new features.

Tests CTE compilation, window functions, complex joins, schema reflection
SQL generation, and the hybrid_property / TypeDecorator APIs.
All tests are pure SQL compilation tests — no live database required.
"""

import pytest
from pyloquent.query.builder import QueryBuilder
from pyloquent.query.expression import JoinClause, WindowFrame
from pyloquent.grammars.sqlite_grammar import SQLiteGrammar
from pyloquent.grammars.postgres_grammar import PostgresGrammar


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def qb() -> QueryBuilder:
    """Fresh SQLite QueryBuilder with no connection."""
    return QueryBuilder(SQLiteGrammar())


# ---------------------------------------------------------------------------
# CTEs
# ---------------------------------------------------------------------------

class TestCTEs:
    def test_with_cte_callback(self):
        sql, bindings = (
            qb()
            .with_cte("active", lambda q: q.from_("users").where("active", True))
            .from_("active")
            .to_sql()
        )
        assert 'WITH "active" AS' in sql
        assert '"active" = ?' in sql
        assert True in bindings

    def test_with_cte_builder(self):
        inner = qb().from_("users").where("role", "admin")
        sql, bindings = (
            qb()
            .with_cte("admins", inner)
            .from_("admins")
            .to_sql()
        )
        assert 'WITH "admins" AS' in sql
        assert "admin" in bindings

    def test_multiple_ctes(self):
        sql, _ = (
            qb()
            .with_cte("a", lambda q: q.from_("t1").where("x", 1))
            .with_cte("b", lambda q: q.from_("t2").where("y", 2))
            .from_("a")
            .to_sql()
        )
        assert '"a" AS' in sql
        assert '"b" AS' in sql

    def test_with_recursive_cte(self):
        sql, _ = (
            qb()
            .with_recursive_cte(
                "tree",
                lambda q: q.from_("cats").where("parent_id", None),
                lambda q: q.from_("cats").join("tree", "tree.id", "=", "cats.parent_id"),
            )
            .from_("tree")
            .to_sql()
        )
        assert "WITH RECURSIVE" in sql
        assert '"tree" AS' in sql
        assert "UNION ALL" in sql


# ---------------------------------------------------------------------------
# Window functions
# ---------------------------------------------------------------------------

class TestWindowFunctions:
    def test_row_number(self):
        sql, _ = (
            qb()
            .from_("orders")
            .select_window(
                "ROW_NUMBER",
                partition_by=["user_id"],
                order_by=["created_at"],
                alias="row_num",
            )
            .to_sql()
        )
        assert "ROW_NUMBER() OVER" in sql
        assert "PARTITION BY" in sql
        assert "row_num" in sql

    def test_rank_no_partition(self):
        sql, _ = (
            qb()
            .from_("scores")
            .select_window("RANK", order_by=["score"], alias="rnk")
            .to_sql()
        )
        assert "RANK() OVER" in sql
        assert "PARTITION BY" not in sql

    def test_sum_with_frame(self):
        frame = WindowFrame(mode="ROWS", start="UNBOUNDED PRECEDING", end="CURRENT ROW")
        sql, _ = (
            qb()
            .from_("sales")
            .select_window("SUM", "amount", order_by=["date"], frame=frame, alias="running")
            .to_sql()
        )
        assert "SUM(" in sql
        assert "ROWS BETWEEN" in sql
        assert "UNBOUNDED PRECEDING" in sql


# ---------------------------------------------------------------------------
# Complex joins
# ---------------------------------------------------------------------------

class TestComplexJoins:
    def test_join_raw(self):
        sql, bindings = (
            qb()
            .from_("users")
            .join_raw("LEFT JOIN orders ON orders.user_id = users.id AND orders.active = ?", [1])
            .to_sql()
        )
        assert "LEFT JOIN orders ON" in sql
        assert 1 in bindings

    def test_join_sub_callback(self):
        sql, bindings = (
            qb()
            .from_("users")
            .join_sub(
                lambda q: q.from_("orders").where("status", "paid"),
                alias="paid",
                first="users.id",
                operator="=",
                second="paid.user_id",
            )
            .to_sql()
        )
        assert "JOIN (" in sql
        assert '"paid"' in sql
        assert "paid" in bindings

    def test_left_join_sub(self):
        sql, _ = (
            qb()
            .from_("users")
            .left_join_sub(
                lambda q: q.from_("orders").select("user_id"),
                alias="o",
                first="users.id",
                operator="=",
                second="o.user_id",
            )
            .to_sql()
        )
        assert "LEFT JOIN" in sql

    def test_join_on_callback(self):
        sql, _ = (
            qb()
            .from_("users")
            .join_on(
                "orders",
                lambda j: j.on("orders.user_id", "=", "users.id"),
            )
            .to_sql()
        )
        assert "JOIN" in sql
        assert "user_id" in sql

    def test_join_on_or_condition(self):
        sql, _ = (
            qb()
            .from_("users")
            .join_on(
                "orders",
                lambda j: j.on("orders.user_id", "=", "users.id")
                           .or_on("orders.alt_id", "=", "users.id"),
            )
            .to_sql()
        )
        assert "OR" in sql

    def test_full_join(self):
        sql, _ = (
            qb()
            .from_("a")
            .full_join("b", "a.id", "=", "b.a_id")
            .to_sql()
        )
        assert "FULL OUTER JOIN" in sql


# ---------------------------------------------------------------------------
# Schema reflection SQL shape (SQLiteGrammar)
# ---------------------------------------------------------------------------

class TestSchemaReflectionSQLite:
    def setup_method(self):
        self.g = SQLiteGrammar()

    def test_table_exists(self):
        sql, bindings = self.g.compile_table_exists("users")
        assert "sqlite_master" in sql
        assert "users" in bindings

    def test_column_exists(self):
        sql, bindings = self.g.compile_column_exists("users", "email")
        assert "pragma_table_info" in sql
        assert "users" in bindings
        assert "email" in bindings

    def test_get_tables(self):
        sql = self.g.compile_get_tables()
        assert "sqlite_master" in sql
        assert "type='table'" in sql

    def test_get_columns(self):
        sql, bindings = self.g.compile_get_columns("orders")
        assert "pragma_table_info" in sql
        assert "orders" in bindings

    def test_get_indexes(self):
        sql, bindings = self.g.compile_get_indexes("users")
        assert "pragma_index_list" in sql

    def test_get_foreign_keys(self):
        sql, bindings = self.g.compile_get_foreign_keys("orders")
        assert "pragma_foreign_key_list" in sql


# ---------------------------------------------------------------------------
# Schema reflection SQL shape (PostgresGrammar)
# ---------------------------------------------------------------------------

class TestSchemaReflectionPostgres:
    def setup_method(self):
        self.g = PostgresGrammar()

    def test_table_exists(self):
        sql, bindings = self.g.compile_table_exists("users")
        assert "information_schema.tables" in sql

    def test_get_columns(self):
        sql, bindings = self.g.compile_get_columns("users")
        assert "information_schema.columns" in sql

    def test_get_indexes(self):
        sql, bindings = self.g.compile_get_indexes("users")
        assert "pg_indexes" in sql

    def test_get_foreign_keys(self):
        sql, bindings = self.g.compile_get_foreign_keys("orders")
        assert "FOREIGN KEY" in sql


# ---------------------------------------------------------------------------
# hybrid_property
# ---------------------------------------------------------------------------

class TestHybridProperty:
    def test_instance_access(self):
        from pyloquent.orm.hybrid_property import hybrid_property

        class Dummy:
            def __init__(self, first, last):
                self.first = first
                self.last = last

            @hybrid_property
            def full_name(self) -> str:
                return f"{self.first} {self.last}"

        d = Dummy("Jane", "Doe")
        assert d.full_name == "Jane Doe"

    def test_class_level_expression(self):
        from pyloquent.orm.hybrid_property import hybrid_property
        from pyloquent.query.expression import RawExpression

        class Dummy:
            @hybrid_property
            def full_name(self):
                return "instance"

            @full_name.expression
            @classmethod
            def full_name(cls):
                return RawExpression("first || ' ' || last")

        expr = Dummy.full_name
        assert isinstance(expr, RawExpression)
        assert "first" in expr.sql

    def test_no_expression_returns_descriptor(self):
        from pyloquent.orm.hybrid_property import hybrid_property

        class Dummy:
            @hybrid_property
            def name(self):
                return "ok"

        # Without an expression registered, class-level returns the descriptor
        assert isinstance(Dummy.name, hybrid_property)


# ---------------------------------------------------------------------------
# TypeDecorator
# ---------------------------------------------------------------------------

class TestTypeDecorator:
    def test_json_type_bind(self):
        from pyloquent.orm.type_decorator import JSONType
        t = JSONType()
        result = t.process_bind_param({"key": "value"})
        assert result == '{"key": "value"}'

    def test_json_type_result(self):
        from pyloquent.orm.type_decorator import JSONType
        t = JSONType()
        result = t.process_result_value('{"x": 1}')
        assert result == {"x": 1}

    def test_comma_separated_bind(self):
        from pyloquent.orm.type_decorator import CommaSeparatedType
        t = CommaSeparatedType()
        assert t.process_bind_param(["a", "b", "c"]) == "a,b,c"

    def test_comma_separated_result(self):
        from pyloquent.orm.type_decorator import CommaSeparatedType
        t = CommaSeparatedType()
        assert t.process_result_value("a,b,c") == ["a", "b", "c"]

    def test_register_and_get(self):
        from pyloquent.orm.type_decorator import TypeDecorator, register_type, get_type

        class UpperType(TypeDecorator):
            impl = "TEXT"
            def process_bind_param(self, value, dialect=None):
                return value.upper() if value else value
            def process_result_value(self, value, dialect=None):
                return value.lower() if value else value

        register_type("upper", UpperType())
        t = get_type("upper")
        assert t is not None
        assert t.process_bind_param("hello") == "HELLO"

    def test_get_type_from_class(self):
        from pyloquent.orm.type_decorator import JSONType, get_type
        t = get_type(JSONType)
        assert isinstance(t, JSONType)

    def test_get_type_none_for_unknown(self):
        from pyloquent.orm.type_decorator import get_type
        assert get_type("unknown_string_cast") is None


# ---------------------------------------------------------------------------
# IdentityMap
# ---------------------------------------------------------------------------

class TestIdentityMap:
    def test_register_and_get(self):
        from pyloquent.orm.identity_map import IdentityMap

        class FakeModel:
            pass

        imap = IdentityMap()
        obj = FakeModel()
        imap.register(FakeModel, 1, obj)
        assert imap.get(FakeModel, 1) is obj

    def test_get_missing_returns_none(self):
        from pyloquent.orm.identity_map import IdentityMap

        class FakeModel:
            pass

        imap = IdentityMap()
        assert imap.get(FakeModel, 999) is None

    def test_get_or_register_creates(self):
        from pyloquent.orm.identity_map import IdentityMap

        class FakeModel:
            def __init__(self, **kw):
                self.__dict__.update(kw)

        imap = IdentityMap()
        obj = imap.get_or_register(FakeModel, 1, {"id": 1, "name": "Alice"})
        assert isinstance(obj, FakeModel)
        assert obj.name == "Alice"

    def test_get_or_register_returns_cached(self):
        from pyloquent.orm.identity_map import IdentityMap

        class FakeModel:
            pass

        imap = IdentityMap()
        original = FakeModel()
        imap.register(FakeModel, 1, original)
        returned = imap.get_or_register(FakeModel, 1, FakeModel())
        assert returned is original

    def test_evict(self):
        from pyloquent.orm.identity_map import IdentityMap

        class FakeModel:
            pass

        imap = IdentityMap()
        obj = FakeModel()
        imap.register(FakeModel, 1, obj)
        imap.evict(FakeModel, 1)
        assert imap.get(FakeModel, 1) is None

    def test_clear(self):
        from pyloquent.orm.identity_map import IdentityMap

        class FakeModel:
            pass

        imap = IdentityMap()
        imap.register(FakeModel, 1, FakeModel())
        imap.register(FakeModel, 2, FakeModel())
        imap.clear()
        assert len(imap) == 0

    def test_composite_key_normalisation(self):
        from pyloquent.orm.identity_map import IdentityMap

        class FakeModel:
            pass

        imap = IdentityMap()
        obj = FakeModel()
        imap.register(FakeModel, {"user_id": 1, "role_id": 2}, obj)
        assert imap.get(FakeModel, {"user_id": 1, "role_id": 2}) is obj

    def test_contains_syntax(self):
        from pyloquent.orm.identity_map import IdentityMap

        class FakeModel:
            pass

        imap = IdentityMap()
        imap.register(FakeModel, 5, FakeModel())
        assert (FakeModel, 5) in imap
        assert (FakeModel, 99) not in imap

    @pytest.mark.asyncio
    async def test_session_context_manager(self):
        from pyloquent.orm.identity_map import IdentityMap

        class FakeModel:
            pass

        async with IdentityMap.session() as imap:
            imap.register(FakeModel, 1, FakeModel())
            assert len(imap) == 1

        # Cleared on exit
        assert len(imap) == 0


# ---------------------------------------------------------------------------
# Sync support
# ---------------------------------------------------------------------------

class TestRunSync:
    def test_runs_coroutine(self):
        from pyloquent.sync import run_sync

        async def add(a, b):
            return a + b

        assert run_sync(add(2, 3)) == 5

    def test_propagates_exception(self):
        from pyloquent.sync import run_sync

        async def fail():
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            run_sync(fail())

    def test_sync_decorator(self):
        from pyloquent.sync import sync

        @sync
        async def greet(name: str) -> str:
            return f"Hello, {name}"

        assert greet("world") == "Hello, world"
