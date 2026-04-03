"""Column definition for schema builder."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


@dataclass
class Column:
    """Represents a column in a database table."""

    name: str
    type: str
    length: Optional[int] = None
    precision: Optional[int] = None
    scale: Optional[int] = None
    nullable: bool = True
    default: Any = None
    unsigned: bool = False
    auto_increment: bool = False
    primary: bool = False
    unique: bool = False
    index: bool = False
    comment: Optional[str] = None
    collation: Optional[str] = None
    charset: Optional[str] = None
    after: Optional[str] = None
    first: bool = False
    virtual_as: Optional[str] = None
    stored_as: Optional[str] = None
    srid: Optional[int] = None

    # For enum/set types
    allowed: List[str] = field(default_factory=list)

    def to_sql(self, grammar: "Grammar") -> str:
        """Convert column to SQL.

        Args:
            grammar: Grammar instance

        Returns:
            SQL string for column definition
        """
        return grammar.compile_column(self)


@dataclass
class Index:
    """Represents a table index."""

    name: str
    columns: List[str]
    unique: bool = False
    primary: bool = False
    fulltext: bool = False
    spatial: bool = False
    algorithm: Optional[str] = None


@dataclass
class ForeignKey:
    """Represents a foreign key constraint."""

    name: str
    columns: List[str]
    referenced_table: str
    referenced_columns: List[str]
    on_delete: Optional[str] = None
    on_update: Optional[str] = None
