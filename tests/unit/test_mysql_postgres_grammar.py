"""Unit tests for MySQLGrammar and PostgresGrammar."""
from unittest.mock import MagicMock
from pyloquent.grammars.mysql_grammar import MySQLGrammar
from pyloquent.grammars.postgres_grammar import PostgresGrammar
from pyloquent.query.builder import QueryBuilder
from pyloquent.schema.blueprint import Blueprint
from pyloquent.schema.column import Column


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def mysql_qb():
    return QueryBuilder(MySQLGrammar())


def pg_qb():
    return QueryBuilder(PostgresGrammar())


# ===========================================================================
# MySQLGrammar
# ===========================================================================

class TestMySQLGrammar:

    def test_wrap_value_uses_backticks(self):
        g = MySQLGrammar()
        assert g._wrap_value("users") == "`users`"

    def test_parameter_uses_percent_s(self):
        g = MySQLGrammar()
        assert g._parameter("x") == "%s"

    def test_select_wraps_identifiers_in_backticks(self):
        sql, _ = mysql_qb().from_("users").where("id", 1).to_sql()
        assert "`users`" in sql
        assert "`id`" in sql

    def test_compile_insert_get_id(self):
        g = MySQLGrammar()
        qb = mysql_qb().from_("users")
        sql, bindings = g.compile_insert_get_id(qb, {"name": "Alice"})
        assert "INSERT" in sql
        assert bindings == ["Alice"]

    def test_compile_update_with_order_and_limit(self):
        g = MySQLGrammar()
        qb = mysql_qb().from_("users").order_by("id").limit(5)
        sql, _ = g.compile_update(qb, {"active": 1})
        assert "ORDER BY" in sql.upper()
        assert "LIMIT" in sql.upper()

    def test_compile_update_without_order_limit(self):
        g = MySQLGrammar()
        qb = mysql_qb().from_("users")
        sql, _ = g.compile_update(qb, {"active": 1})
        assert "ORDER BY" not in sql.upper()
        assert "LIMIT" not in sql.upper()

    def test_compile_delete_with_order_and_limit(self):
        g = MySQLGrammar()
        qb = mysql_qb().from_("users").order_by("id").limit(3)
        sql, _ = g.compile_delete(qb)
        assert "ORDER BY" in sql.upper()
        assert "LIMIT" in sql.upper()

    def test_compile_delete_without_order_limit(self):
        g = MySQLGrammar()
        qb = mysql_qb().from_("users")
        sql, _ = g.compile_delete(qb)
        assert "ORDER BY" not in sql.upper()

    def test_boolean_default_stays_integer(self):
        # MySQL BOOLEAN is TINYINT(1); DEFAULT 0/1 is valid and must be kept
        # (regression guard so the PostgreSQL fix does not leak into MySQL).
        g = MySQLGrammar()
        assert g._compile_default_value(False) == "0"
        assert g._compile_default_value(True) == "1"

    def test_long_text_stays_longtext(self):
        # LONGTEXT is a valid MySQL type and must not be remapped to TEXT
        # (regression guard so the PostgreSQL type fix does not leak into MySQL).
        g = MySQLGrammar()
        assert g._compile_column_type(Column(name="c", type="long_text")) == "LONGTEXT"

    def test_enum_and_set_stay_native(self):
        # MySQL has native ENUM/SET — they must not be rewritten to CHECK/TEXT.
        g = MySQLGrammar()
        enum_col = Column(name="status", type="enum", allowed=["a", "b"])
        set_col = Column(name="perms", type="set", allowed=["r", "w"])
        assert g._compile_column_type(enum_col) == "ENUM('a', 'b')"
        assert g._compile_column_type(set_col) == "SET('r', 'w')"


# ===========================================================================
# PostgresGrammar
# ===========================================================================

class TestPostgresGrammar:

    def test_wrap_value_uses_double_quotes(self):
        g = PostgresGrammar()
        assert g._wrap_value("users") == '"users"'

    def test_parameter_returns_question_mark(self):
        g = PostgresGrammar()
        assert g._parameter("x") == "?"

    def test_supports_returning(self):
        g = PostgresGrammar()
        assert g.supports_returning() is True

    def test_supports_ilike(self):
        g = PostgresGrammar()
        assert g.supports_ilike() is True

    def test_compile_insert_get_id_has_returning(self):
        g = PostgresGrammar()
        qb = pg_qb().from_("users")
        sql, bindings = g.compile_insert_get_id(qb, {"name": "Bob"})
        assert "RETURNING" in sql
        assert '"id"' in sql
        assert bindings == ["Bob"]

    def test_compile_insert_get_id_custom_sequence(self):
        g = PostgresGrammar()
        qb = pg_qb().from_("users")
        sql, _ = g.compile_insert_get_id(qb, {"name": "Carol"}, sequence="uuid")
        assert '"uuid"' in sql

    def test_select_plain(self):
        sql, _ = pg_qb().from_("users").to_sql()
        assert "SELECT *" in sql
        assert '"users"' in sql

    def test_select_distinct(self):
        sql, _ = pg_qb().from_("users").distinct().to_sql()
        assert "SELECT DISTINCT" in sql

    def test_select_distinct_on(self):
        g = PostgresGrammar()
        qb = pg_qb().from_("users")
        qb._distinct_on = ["email"]
        sql, _ = qb.to_sql()
        assert "DISTINCT ON" in sql
        assert '"email"' in sql

    def test_compile_columns_with_specific_select(self):
        sql, _ = pg_qb().from_("users").select("name", "email").to_sql()
        assert '"name"' in sql
        assert '"email"' in sql

    def test_where_clause_compilation(self):
        sql, bindings = pg_qb().from_("users").where("id", 42).to_sql()
        assert '"id"' in sql
        assert 42 in bindings

    def test_compile_update_delegates_to_parent(self):
        g = PostgresGrammar()
        qb = pg_qb().from_("users")
        sql, bindings = g._compile_update(qb, {"name": "Dave"})
        assert "UPDATE" in sql

    # -- Boolean defaults: PostgreSQL is strictly typed and rejects DEFAULT 0/1
    #    on a BOOLEAN column, so they must render as TRUE / FALSE keywords.

    def test_boolean_default_renders_keyword(self):
        g = PostgresGrammar()
        assert g._compile_default_value(False) == "FALSE"
        assert g._compile_default_value(True) == "TRUE"

    def test_non_boolean_defaults_delegate_to_base(self):
        g = PostgresGrammar()
        assert g._compile_default_value(0) == "0"
        assert g._compile_default_value(None) == "NULL"

    def test_boolean_default_in_create_table(self):
        g = PostgresGrammar()
        bp = Blueprint("things")
        bp.boolean("is_active").default(False)
        sql = g.compile_create_table(bp)[0]
        assert "DEFAULT FALSE" in sql
        assert "DEFAULT 0" not in sql

    def test_boolean_default_in_change_column(self):
        g = PostgresGrammar()
        col = Column(name="is_active", type="boolean", default=False, nullable=False)
        statements = g._compile_change_column("things", col)
        assert any("SET DEFAULT FALSE" in s for s in statements)

    # -- MySQL-flavoured types that PostgreSQL rejects must be remapped.
    #    (SQLite silently accepted e.g. LONGTEXT via type affinity.)

    def test_mysql_only_types_remapped_to_postgres(self):
        g = PostgresGrammar()
        cases = {
            "long_text": "TEXT",
            "medium_text": "TEXT",
            "tiny_integer": "SMALLINT",
            "medium_integer": "INTEGER",
            "double": "DOUBLE PRECISION",
            "binary": "BYTEA",
            "year": "INTEGER",
            "date_time": "TIMESTAMP",
        }
        for col_type, expected in cases.items():
            assert g._compile_column_type(Column(name="c", type=col_type)) == expected

    def test_date_time_keeps_precision(self):
        g = PostgresGrammar()
        assert g._compile_column_type(Column(name="c", type="date_time", precision=3)) == "TIMESTAMP(3)"

    def test_valid_types_unchanged(self):
        g = PostgresGrammar()
        assert g._compile_column_type(Column(name="c", type="text")) == "TEXT"
        assert g._compile_column_type(Column(name="c", type="string")) == "VARCHAR(255)"
        assert g._compile_column_type(Column(name="c", type="boolean")) == "BOOLEAN"

    def test_long_text_in_create_table_is_text(self):
        g = PostgresGrammar()
        bp = Blueprint("docs")
        bp.long_text("body")
        sql = g.compile_create_table(bp)[0]
        assert "TEXT" in sql
        assert "LONGTEXT" not in sql

    def test_long_text_in_change_column_is_text(self):
        g = PostgresGrammar()
        col = Column(name="body", type="long_text", nullable=True)
        statements = g._compile_change_column("docs", col)
        assert any("TYPE TEXT" in s for s in statements)
        assert not any("LONGTEXT" in s for s in statements)

    # -- enum / set: PostgreSQL has no inline ENUM and no SET at all.

    def test_enum_becomes_check_constraint(self):
        g = PostgresGrammar()
        col = Column(name="status", type="enum", allowed=["active", "inactive"])
        result = g._compile_column_type(col)
        assert "ENUM" not in result
        assert 'CHECK ("status" IN (' in result
        assert "'active'" in result and "'inactive'" in result

    def test_set_becomes_text(self):
        g = PostgresGrammar()
        col = Column(name="perms", type="set", allowed=["r", "w"])
        assert g._compile_column_type(col) == "TEXT"

    def test_enum_in_create_table_has_no_enum_keyword(self):
        g = PostgresGrammar()
        bp = Blueprint("accounts")
        bp.enum("status", ["active", "inactive"])
        sql = g.compile_create_table(bp)[0]
        assert "ENUM" not in sql
        assert "CHECK" in sql
