"""Unit tests for Grammar schema DDL compilation methods."""
from unittest.mock import MagicMock
from pyloquent.grammars.sqlite_grammar import SQLiteGrammar
from pyloquent.schema.column import Column, ForeignKey, Index


def grammar():
    return SQLiteGrammar()


def _col(name, col_type, **kwargs):
    return Column(name=name, type=col_type, **kwargs)


# ---------------------------------------------------------------------------
# _compile_column  (nullable, not-null, default, unsigned, auto_increment)
# ---------------------------------------------------------------------------

def test_compile_column_not_null():
    g = grammar()
    col = _col("name", "string", nullable=False)
    sql = g._compile_column(col)
    assert "NOT NULL" in sql


def test_compile_column_nullable():
    g = grammar()
    col = _col("bio", "text", nullable=True)
    sql = g._compile_column(col)
    assert " NULL" in sql


def test_compile_column_default_int():
    g = grammar()
    col = _col("score", "integer", default=0)
    sql = g._compile_column(col)
    assert "DEFAULT 0" in sql


def test_compile_column_default_bool_true():
    g = grammar()
    col = _col("active", "boolean", default=True)
    sql = g._compile_column(col)
    assert "DEFAULT 1" in sql


def test_compile_column_default_bool_false():
    g = grammar()
    col = _col("active", "boolean", default=False)
    sql = g._compile_column(col)
    assert "DEFAULT 0" in sql


def test_compile_column_default_string():
    g = grammar()
    col = _col("status", "string", default="active")
    sql = g._compile_column(col)
    assert "DEFAULT" in sql
    assert "active" in sql


def test_compile_column_default_none():
    g = grammar()
    col = _col("deleted_at", "timestamp", default=None)
    sql = g._compile_column(col)
    assert "DEFAULT" not in sql


def test_compile_column_unsigned():
    g = grammar()
    col = _col("count", "integer", unsigned=True)
    sql = g._compile_column(col)
    assert "UNSIGNED" in sql


def test_compile_column_auto_increment():
    g = grammar()
    col = _col("id", "integer", auto_increment=True)
    sql = g._compile_column(col)
    assert sql  # just ensure it compiles


# ---------------------------------------------------------------------------
# _compile_column_type — various type mappings
# ---------------------------------------------------------------------------

def test_column_type_big_integer():
    g = grammar()
    col = _col("x", "big_integer")
    assert "BIGINT" in g._compile_column_type(col)


def test_column_type_float():
    g = grammar()
    col = _col("x", "float")
    assert "FLOAT" in g._compile_column_type(col)


def test_column_type_decimal_with_precision():
    g = grammar()
    col = _col("x", "decimal", precision=8, scale=2)
    assert "DECIMAL(8, 2)" in g._compile_column_type(col)


def test_column_type_decimal_no_precision():
    g = grammar()
    col = _col("x", "decimal")
    assert "DECIMAL" in g._compile_column_type(col)


def test_column_type_char():
    g = grammar()
    col = _col("x", "char", length=10)
    assert "CHAR(10)" in g._compile_column_type(col)


def test_column_type_string_default_length():
    g = grammar()
    col = _col("x", "string")
    assert "VARCHAR(255)" in g._compile_column_type(col)


def test_column_type_text():
    g = grammar()
    assert "TEXT" in g._compile_column_type(_col("x", "text"))


def test_column_type_json():
    g = grammar()
    assert "JSON" in g._compile_column_type(_col("x", "json"))


def test_column_type_boolean():
    g = grammar()
    assert "BOOLEAN" in g._compile_column_type(_col("x", "boolean"))


def test_column_type_uuid():
    g = grammar()
    assert "CHAR(36)" in g._compile_column_type(_col("x", "uuid"))


def test_column_type_enum():
    g = grammar()
    col = _col("x", "enum")
    col.allowed = ["a", "b"]
    result = g._compile_column_type(col)
    assert "ENUM" in result
    assert "'a'" in result


def test_column_type_datetime_with_precision():
    g = grammar()
    col = _col("x", "date_time", precision=3)
    assert "DATETIME(3)" in g._compile_column_type(col)


def test_column_type_timestamp_no_precision():
    g = grammar()
    col = _col("x", "timestamp")
    assert "TIMESTAMP" in g._compile_column_type(col)


def test_column_type_unknown_falls_back_to_upper():
    g = grammar()
    col = _col("x", "custom_type")
    assert "CUSTOM_TYPE" in g._compile_column_type(col)


# ---------------------------------------------------------------------------
# compile_alter_table
# ---------------------------------------------------------------------------

def test_compile_alter_table():
    g = grammar()
    bp = MagicMock()
    bp.table = "users"
    bp.columns = [_col("score", "integer", nullable=True)]
    result = g.compile_alter_table(bp)
    assert len(result) == 1
    assert "ALTER TABLE" in result[0]
    assert "ADD COLUMN" in result[0]


# ---------------------------------------------------------------------------
# compile_drop_table / compile_drop_table_if_exists / compile_rename_table
# ---------------------------------------------------------------------------

def test_compile_drop_table():
    g = grammar()
    sql = g.compile_drop_table("users")
    assert "DROP TABLE" in sql
    assert "users" in sql


def test_compile_drop_table_if_exists():
    g = grammar()
    sql = g.compile_drop_table_if_exists("users")
    assert "IF EXISTS" in sql


def test_compile_rename_table():
    g = grammar()
    sql = g.compile_rename_table("old_name", "new_name")
    assert "RENAME" in sql
    assert "new_name" in sql


# ---------------------------------------------------------------------------
# _compile_index
# ---------------------------------------------------------------------------

def test_compile_index_regular():
    g = grammar()
    idx = Index(name="idx_name", columns=["name"], unique=False)
    sql = g._compile_index("users", idx)
    assert "CREATE INDEX" in sql
    assert "ON" in sql


def test_compile_index_unique():
    g = grammar()
    idx = Index(name="idx_email", columns=["email"], unique=True)
    sql = g._compile_index("users", idx)
    assert "UNIQUE" in sql


# ---------------------------------------------------------------------------
# _compile_foreign_key
# ---------------------------------------------------------------------------

def test_compile_foreign_key_basic():
    g = grammar()
    fk = ForeignKey(
        name="fk_user_id",
        columns=["user_id"],
        referenced_table="users",
        referenced_columns=["id"],
    )
    sql = g._compile_foreign_key("posts", fk)
    assert "FOREIGN KEY" in sql
    assert "REFERENCES" in sql


def test_compile_foreign_key_with_on_delete_and_update():
    g = grammar()
    fk = ForeignKey(
        name="fk_user",
        columns=["user_id"],
        referenced_table="users",
        referenced_columns=["id"],
        on_delete="cascade",
        on_update="restrict",
    )
    sql = g._compile_foreign_key("posts", fk)
    assert "ON DELETE CASCADE" in sql
    assert "ON UPDATE RESTRICT" in sql


# ---------------------------------------------------------------------------
# compile_create_table with indexes and foreign keys
# ---------------------------------------------------------------------------

def test_compile_create_table_with_index_and_fk():
    g = grammar()
    bp = MagicMock()
    bp.table = "posts"
    bp.columns = [_col("id", "integer", auto_increment=True, nullable=False),
                  _col("title", "string", nullable=False)]
    bp.indexes = [Index(name="idx_title", columns=["title"])]
    bp.foreign_keys = [ForeignKey(
        name="fk_user", columns=["user_id"],
        referenced_table="users", referenced_columns=["id"]
    )]
    result = g.compile_create_table(bp)
    assert len(result) == 3  # CREATE TABLE + CREATE INDEX + ALTER TABLE FK
    assert "CREATE TABLE" in result[0]


# ---------------------------------------------------------------------------
# _compile_default_value edge cases
# ---------------------------------------------------------------------------

def test_default_value_none():
    g = grammar()
    assert g._compile_default_value(None) == "NULL"


def test_default_value_float():
    g = grammar()
    assert g._compile_default_value(3.14) == "3.14"


def test_default_value_object():
    g = grammar()
    result = g._compile_default_value(object())
    assert isinstance(result, str)
