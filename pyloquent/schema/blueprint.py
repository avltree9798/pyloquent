"""Blueprint for defining database tables."""

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Union

from pyloquent.schema.column import Column, ForeignKey, Index

if TYPE_CHECKING:
    from pyloquent.grammars.grammar import Grammar


class Blueprint:
    """Blueprint for defining database tables.

    This class provides a fluent interface for defining table structure,
    similar to Laravel's Blueprint class.

    Example:
        async def up(self):
            await Schema.create('users', lambda table: [
                table.id(),
                table.string('name', 100),
                table.string('email').unique(),
                table.timestamps(),
            ])
    """

    def __init__(self, table: str):
        """Initialize blueprint.

        Args:
            table: Table name
        """
        self.table = table
        self.columns: List[Column] = []
        self.indexes: List[Index] = []
        self.foreign_keys: List[ForeignKey] = []
        self._temporary = False
        self._engine: Optional[str] = None
        self._charset: Optional[str] = None
        self._collation: Optional[str] = None
        self._comment: Optional[str] = None

    # ========================================================================
    # Table Options
    # ========================================================================

    def temporary(self) -> "Blueprint":
        """Mark table as temporary."""
        self._temporary = True
        return self

    def engine(self, engine: str) -> "Blueprint":
        """Set table engine (MySQL)."""
        self._engine = engine
        return self

    def charset(self, charset: str) -> "Blueprint":
        """Set table charset."""
        self._charset = charset
        return self

    def collation(self, collation: str) -> "Blueprint":
        """Set table collation."""
        self._collation = collation
        return self

    def comment(self, comment: str) -> "Blueprint":
        """Set table comment."""
        self._comment = comment
        return self

    # ========================================================================
    # ID Columns
    # ========================================================================

    def id(self, column: str = "id") -> Column:
        """Create auto-incrementing primary key.

        Args:
            column: Column name (default: id)

        Returns:
            Column instance
        """
        return self.big_increments(column)

    def increments(self, column: str) -> Column:
        """Create auto-incrementing UNSIGNED INTEGER primary key."""
        column = Column(
            name=column,
            type="integer",
            unsigned=True,
            auto_increment=True,
            primary=True,
        )
        self.columns.append(column)
        return column

    def big_increments(self, column: str) -> Column:
        """Create auto-incrementing UNSIGNED BIGINT primary key."""
        column = Column(
            name=column,
            type="big_integer",
            unsigned=True,
            auto_increment=True,
            primary=True,
        )
        self.columns.append(column)
        return column

    def medium_increments(self, column: str) -> Column:
        """Create auto-incrementing UNSIGNED MEDIUMINT primary key."""
        column = Column(
            name=column,
            type="medium_integer",
            unsigned=True,
            auto_increment=True,
            primary=True,
        )
        self.columns.append(column)
        return column

    def small_increments(self, column: str) -> Column:
        """Create auto-incrementing UNSIGNED SMALLINT primary key."""
        column = Column(
            name=column,
            type="small_integer",
            unsigned=True,
            auto_increment=True,
            primary=True,
        )
        self.columns.append(column)
        return column

    def tiny_increments(self, column: str) -> Column:
        """Create auto-incrementing UNSIGNED TINYINT primary key."""
        column = Column(
            name=column,
            type="tiny_integer",
            unsigned=True,
            auto_increment=True,
            primary=True,
        )
        self.columns.append(column)
        return column

    def foreign_id(self, column: str) -> Column:
        """Create UNSIGNED BIGINT column for foreign key."""
        return self.unsigned_big_integer(column)

    def foreign_id_for(self, model: type, column: Optional[str] = None) -> Column:
        """Create foreign key column for a model.

        Args:
            model: Related model class
            column: Column name (default: modelname_id)
        """
        if column is None:
            column = model._get_foreign_key()
        return self.foreign_id(column)

    def foreign_uuid(self, column: str) -> Column:
        """Create UUID column for foreign key."""
        return self.uuid(column)

    def foreign_ulid(self, column: str) -> Column:
        """Create ULID column for foreign key."""
        return self.ulid(column)

    # ========================================================================
    # Numeric Types
    # ========================================================================

    def integer(self, column: str, auto_increment: bool = False, unsigned: bool = False) -> Column:
        """Create INTEGER column."""
        column = Column(
            name=column,
            type="integer",
            auto_increment=auto_increment,
            unsigned=unsigned,
        )
        self.columns.append(column)
        return column

    def big_integer(
        self, column: str, auto_increment: bool = False, unsigned: bool = False
    ) -> Column:
        """Create BIGINT column."""
        column = Column(
            name=column,
            type="big_integer",
            auto_increment=auto_increment,
            unsigned=unsigned,
        )
        self.columns.append(column)
        return column

    def unsigned_big_integer(self, column: str) -> Column:
        """Create UNSIGNED BIGINT column."""
        return self.big_integer(column, unsigned=True)

    def medium_integer(
        self, column: str, auto_increment: bool = False, unsigned: bool = False
    ) -> Column:
        """Create MEDIUMINT column."""
        column = Column(
            name=column,
            type="medium_integer",
            auto_increment=auto_increment,
            unsigned=unsigned,
        )
        self.columns.append(column)
        return column

    def small_integer(
        self, column: str, auto_increment: bool = False, unsigned: bool = False
    ) -> Column:
        """Create SMALLINT column."""
        column = Column(
            name=column,
            type="small_integer",
            auto_increment=auto_increment,
            unsigned=unsigned,
        )
        self.columns.append(column)
        return column

    def tiny_integer(
        self, column: str, auto_increment: bool = False, unsigned: bool = False
    ) -> Column:
        """Create TINYINT column."""
        column = Column(
            name=column,
            type="tiny_integer",
            auto_increment=auto_increment,
            unsigned=unsigned,
        )
        self.columns.append(column)
        return column

    def float_(self, column: str, precision: int = 53) -> Column:
        """Create FLOAT column."""
        column = Column(
            name=column,
            type="float",
            precision=precision,
        )
        self.columns.append(column)
        return column

    def double(self, column: str) -> Column:
        """Create DOUBLE column."""
        column = Column(
            name=column,
            type="double",
        )
        self.columns.append(column)
        return column

    def decimal(self, column: str, total: int = 8, places: int = 2) -> Column:
        """Create DECIMAL column."""
        column = Column(
            name=column,
            type="decimal",
            precision=total,
            scale=places,
        )
        self.columns.append(column)
        return column

    def unsigned_integer(self, column: str) -> Column:
        """Create UNSIGNED INTEGER column."""
        return self.integer(column, unsigned=True)

    def unsigned_medium_integer(self, column: str) -> Column:
        """Create UNSIGNED MEDIUMINT column."""
        return self.medium_integer(column, unsigned=True)

    def unsigned_small_integer(self, column: str) -> Column:
        """Create UNSIGNED SMALLINT column."""
        return self.small_integer(column, unsigned=True)

    def unsigned_tiny_integer(self, column: str) -> Column:
        """Create UNSIGNED TINYINT column."""
        return self.tiny_integer(column, unsigned=True)

    # ========================================================================
    # String Types
    # ========================================================================

    def char(self, column: str, length: int = 255) -> Column:
        """Create CHAR column."""
        column = Column(
            name=column,
            type="char",
            length=length,
        )
        self.columns.append(column)
        return column

    def string(self, column: str, length: int = 255) -> Column:
        """Create VARCHAR column."""
        column = Column(
            name=column,
            type="string",
            length=length,
        )
        self.columns.append(column)
        return column

    def text(self, column: str) -> Column:
        """Create TEXT column."""
        column = Column(
            name=column,
            type="text",
        )
        self.columns.append(column)
        return column

    def medium_text(self, column: str) -> Column:
        """Create MEDIUMTEXT column."""
        column = Column(
            name=column,
            type="medium_text",
        )
        self.columns.append(column)
        return column

    def long_text(self, column: str) -> Column:
        """Create LONGTEXT column."""
        column = Column(
            name=column,
            type="long_text",
        )
        self.columns.append(column)
        return column

    # ========================================================================
    # Binary Types
    # ========================================================================

    def binary(self, column: str, length: Optional[int] = None) -> Column:
        """Create BINARY/VARBINARY column."""
        column = Column(
            name=column,
            type="binary",
            length=length,
        )
        self.columns.append(column)
        return column

    # ========================================================================
    # JSON Types
    # ========================================================================

    def json(self, column: str) -> Column:
        """Create JSON column."""
        column = Column(
            name=column,
            type="json",
        )
        self.columns.append(column)
        return column

    def jsonb(self, column: str) -> Column:
        """Create JSONB column (PostgreSQL)."""
        column = Column(
            name=column,
            type="jsonb",
        )
        self.columns.append(column)
        return column

    # ========================================================================
    # Date/Time Types
    # ========================================================================

    def date(self, column: str) -> Column:
        """Create DATE column."""
        column = Column(
            name=column,
            type="date",
        )
        self.columns.append(column)
        return column

    def date_time(self, column: str, precision: int = 0) -> Column:
        """Create DATETIME column."""
        column = Column(
            name=column,
            type="date_time",
            precision=precision,
        )
        self.columns.append(column)
        return column

    def date_time_tz(self, column: str, precision: int = 0) -> Column:
        """Create DATETIME with timezone column."""
        column = Column(
            name=column,
            type="date_time_tz",
            precision=precision,
        )
        self.columns.append(column)
        return column

    def time(self, column: str, precision: int = 0) -> Column:
        """Create TIME column."""
        column = Column(
            name=column,
            type="time",
            precision=precision,
        )
        self.columns.append(column)
        return column

    def time_tz(self, column: str, precision: int = 0) -> Column:
        """Create TIME with timezone column."""
        column = Column(
            name=column,
            type="time_tz",
            precision=precision,
        )
        self.columns.append(column)
        return column

    def timestamp(self, column: str, precision: int = 0) -> Column:
        """Create TIMESTAMP column."""
        column = Column(
            name=column,
            type="timestamp",
            precision=precision,
        )
        self.columns.append(column)
        return column

    def timestamp_tz(self, column: str, precision: int = 0) -> Column:
        """Create TIMESTAMP with timezone column."""
        column = Column(
            name=column,
            type="timestamp_tz",
            precision=precision,
        )
        self.columns.append(column)
        return column

    def timestamps(self, precision: int = 0) -> List[Column]:
        """Create created_at and updated_at columns."""
        return [
            self.timestamp("created_at", precision).nullable(),
            self.timestamp("updated_at", precision).nullable(),
        ]

    def timestamps_tz(self, precision: int = 0) -> List[Column]:
        """Create created_at and updated_at columns with timezone."""
        return [
            self.timestamp_tz("created_at", precision).nullable(),
            self.timestamp_tz("updated_at", precision).nullable(),
        ]

    def soft_deletes(self, column: str = "deleted_at", precision: int = 0) -> Column:
        """Create deleted_at column for soft deletes."""
        return self.timestamp(column, precision).nullable()

    def soft_deletes_tz(self, column: str = "deleted_at", precision: int = 0) -> Column:
        """Create deleted_at column with timezone for soft deletes."""
        return self.timestamp_tz(column, precision).nullable()

    def year(self, column: str) -> Column:
        """Create YEAR column."""
        column = Column(
            name=column,
            type="year",
        )
        self.columns.append(column)
        return column

    # ========================================================================
    # Special Types
    # ========================================================================

    def enum(self, column: str, allowed: List[str]) -> Column:
        """Create ENUM column.

        Args:
            column: Column name
            allowed: List of allowed values
        """
        column = Column(
            name=column,
            type="enum",
            allowed=allowed,
        )
        self.columns.append(column)
        return column

    def set_(self, column: str, allowed: List[str]) -> Column:
        """Create SET column (MySQL).

        Args:
            column: Column name
            allowed: List of allowed values
        """
        column = Column(
            name=column,
            type="set",
            allowed=allowed,
        )
        self.columns.append(column)
        return column

    def uuid(self, column: str) -> Column:
        """Create UUID column."""
        column = Column(
            name=column,
            type="uuid",
        )
        self.columns.append(column)
        return column

    def ulid(self, column: str) -> Column:
        """Create ULID column."""
        column = Column(
            name=column,
            type="ulid",
        )
        self.columns.append(column)
        return column

    def ip_address(self, column: str) -> Column:
        """Create IP address column."""
        column = Column(
            name=column,
            type="ip_address",
        )
        self.columns.append(column)
        return column

    def mac_address(self, column: str) -> Column:
        """Create MAC address column."""
        column = Column(
            name=column,
            type="mac_address",
        )
        self.columns.append(column)
        return column

    def remember_token(self) -> Column:
        """Create remember token column."""
        return self.string("remember_token", 100).nullable()

    def boolean(self, column: str) -> Column:
        """Create BOOLEAN column."""
        column = Column(
            name=column,
            type="boolean",
        )
        self.columns.append(column)
        return column

    def vector(self, column: str, dimensions: int) -> Column:
        """Create VECTOR column (for AI embeddings).

        Args:
            column: Column name
            dimensions: Number of dimensions
        """
        column = Column(
            name=column,
            type="vector",
            length=dimensions,
        )
        self.columns.append(column)
        return column

    # ========================================================================
    # Morphs (Polymorphic Relationships)
    # ========================================================================

    def morphs(self, name: str, index_name: Optional[str] = None) -> List[Column]:
        """Create columns for polymorphic relationship.

        Creates {name}_id and {name}_type columns.

        Args:
            name: Morph name
            index_name: Custom index name
        """
        columns = [
            self.unsigned_big_integer(f"{name}_id"),
            self.string(f"{name}_type"),
        ]
        self.index([f"{name}_id", f"{name}_type"], index_name)
        return columns

    def nullable_morphs(self, name: str, index_name: Optional[str] = None) -> List[Column]:
        """Create nullable columns for polymorphic relationship."""
        columns = [
            self.unsigned_big_integer(f"{name}_id").nullable(),
            self.string(f"{name}_type").nullable(),
        ]
        self.index([f"{name}_id", f"{name}_type"], index_name)
        return columns

    def uuid_morphs(self, name: str, index_name: Optional[str] = None) -> List[Column]:
        """Create UUID columns for polymorphic relationship."""
        columns = [
            self.uuid(f"{name}_id"),
            self.string(f"{name}_type"),
        ]
        self.index([f"{name}_id", f"{name}_type"], index_name)
        return columns

    def nullable_uuid_morphs(self, name: str, index_name: Optional[str] = None) -> List[Column]:
        """Create nullable UUID columns for polymorphic relationship."""
        columns = [
            self.uuid(f"{name}_id").nullable(),
            self.string(f"{name}_type").nullable(),
        ]
        self.index([f"{name}_id", f"{name}_type"], index_name)
        return columns

    def ulid_morphs(self, name: str, index_name: Optional[str] = None) -> List[Column]:
        """Create ULID columns for polymorphic relationship."""
        columns = [
            self.ulid(f"{name}_id"),
            self.string(f"{name}_type"),
        ]
        self.index([f"{name}_id", f"{name}_type"], index_name)
        return columns

    def nullable_ulid_morphs(self, name: str, index_name: Optional[str] = None) -> List[Column]:
        """Create nullable ULID columns for polymorphic relationship."""
        columns = [
            self.ulid(f"{name}_id").nullable(),
            self.string(f"{name}_type").nullable(),
        ]
        self.index([f"{name}_id", f"{name}_type"], index_name)
        return columns

    # ========================================================================
    # Indexes
    # ========================================================================

    def primary(self, columns: Union[str, List[str]], name: Optional[str] = None) -> "Blueprint":
        """Create primary key index."""
        if isinstance(columns, str):
            columns = [columns]
        index = Index(
            name=name or f"{self.table}_pkey",
            columns=columns,
            primary=True,
        )
        self.indexes.append(index)
        return self

    def unique(self, columns: Union[str, List[str]], name: Optional[str] = None) -> "Blueprint":
        """Create unique index."""
        if isinstance(columns, str):
            columns = [columns]
        index = Index(
            name=name or f"{self.table}_{'_'.join(columns)}_unique",
            columns=columns,
            unique=True,
        )
        self.indexes.append(index)
        return self

    def index(
        self,
        columns: Union[str, List[str]],
        name: Optional[str] = None,
        algorithm: Optional[str] = None,
    ) -> "Blueprint":
        """Create index."""
        if isinstance(columns, str):
            columns = [columns]
        index = Index(
            name=name or f"{self.table}_{'_'.join(columns)}_index",
            columns=columns,
            algorithm=algorithm,
        )
        self.indexes.append(index)
        return self

    def full_text(self, columns: Union[str, List[str]], name: Optional[str] = None) -> "Blueprint":
        """Create full-text index."""
        if isinstance(columns, str):
            columns = [columns]
        index = Index(
            name=name or f"{self.table}_{'_'.join(columns)}_fulltext",
            columns=columns,
            fulltext=True,
        )
        self.indexes.append(index)
        return self

    def spatial_index(
        self, columns: Union[str, List[str]], name: Optional[str] = None
    ) -> "Blueprint":
        """Create spatial index."""
        if isinstance(columns, str):
            columns = [columns]
        index = Index(
            name=name or f"{self.table}_{'_'.join(columns)}_spatial",
            columns=columns,
            spatial=True,
        )
        self.indexes.append(index)
        return self

    def drop_primary(self, index_name: Optional[str] = None) -> "Blueprint":
        """Drop primary key (for migrations)."""
        # This would be handled by the migration compiler
        return self

    def drop_unique(self, index_name: str) -> "Blueprint":
        """Drop unique index (for migrations)."""
        return self

    def drop_index(self, index_name: str) -> "Blueprint":
        """Drop index (for migrations)."""
        return self

    def drop_full_text(self, index_name: str) -> "Blueprint":
        """Drop full-text index (for migrations)."""
        return self

    def drop_spatial_index(self, index_name: str) -> "Blueprint":
        """Drop spatial index (for migrations)."""
        return self

    # ========================================================================
    # Foreign Keys
    # ========================================================================

    def foreign(
        self, columns: Union[str, List[str]], name: Optional[str] = None
    ) -> "ForeignKeyConstraint":
        """Create foreign key constraint."""
        if isinstance(columns, str):
            columns = [columns]
        fk = ForeignKey(
            name=name or f"{self.table}_{'_'.join(columns)}_foreign",
            columns=columns,
            referenced_table="",
            referenced_columns=[],
        )
        self.foreign_keys.append(fk)
        return ForeignKeyConstraint(self, fk)

    def drop_foreign(self, name: str) -> "Blueprint":
        """Drop foreign key (for migrations)."""
        return self

    def drop_constrained_foreign_id(self, column: str) -> "Blueprint":
        """Drop foreign key and column (for migrations)."""
        return self

    # ========================================================================
    # Column Modifiers
    # ========================================================================

    def rename_column(self, from_column: str, to_column: str) -> "Blueprint":
        """Rename column (for migrations)."""
        return self

    def drop_column(self, columns: Union[str, List[str]]) -> "Blueprint":
        """Drop column(s) (for migrations)."""
        return self

    def drop_soft_deletes(self) -> "Blueprint":
        """Drop deleted_at column (for migrations)."""
        return self.drop_column("deleted_at")

    def drop_soft_deletes_tz(self) -> "Blueprint":
        """Drop deleted_at column with timezone (for migrations)."""
        return self.drop_column("deleted_at")

    def drop_remember_token() -> "Blueprint":
        """Drop remember_token column (for migrations)."""
        return self.drop_column("remember_token")

    def drop_timestamps(self) -> "Blueprint":
        """Drop created_at and updated_at columns (for migrations)."""
        return self.drop_column(["created_at", "updated_at"])

    def drop_timestamps_tz(self) -> "Blueprint":
        """Drop created_at and updated_at columns with timezone (for migrations)."""
        return self.drop_column(["created_at", "updated_at"])


class ForeignKeyConstraint:
    """Fluent interface for defining foreign key constraints."""

    def __init__(self, blueprint: Blueprint, foreign_key: ForeignKey):
        self.blueprint = blueprint
        self.foreign_key = foreign_key

    def references(self, columns: Union[str, List[str]]) -> "ForeignKeyConstraint":
        """Set referenced columns."""
        if isinstance(columns, str):
            columns = [columns]
        self.foreign_key.referenced_columns = columns
        return self

    def on(self, table: str) -> "ForeignKeyConstraint":
        """Set referenced table."""
        self.foreign_key.referenced_table = table
        return self

    def on_delete(self, action: str) -> "ForeignKeyConstraint":
        """Set ON DELETE action (cascade, set null, restrict, etc.)."""
        self.foreign_key.on_delete = action
        return self

    def on_update(self, action: str) -> "ForeignKeyConstraint":
        """Set ON UPDATE action."""
        self.foreign_key.on_update = action
        return self

    def cascade_on_delete(self) -> "ForeignKeyConstraint":
        """Set ON DELETE CASCADE."""
        return self.on_delete("cascade")

    def cascade_on_update(self) -> "ForeignKeyConstraint":
        """Set ON UPDATE CASCADE."""
        return self.on_update("cascade")

    def null_on_delete(self) -> "ForeignKeyConstraint":
        """Set ON DELETE SET NULL."""
        return self.on_delete("set null")

    def restrict_on_delete(self) -> "ForeignKeyConstraint":
        """Set ON DELETE RESTRICT."""
        return self.on_delete("restrict")

    def no_action_on_delete(self) -> "ForeignKeyConstraint":
        """Set ON DELETE NO ACTION."""
        return self.on_delete("no action")
