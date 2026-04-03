"""Base migration class."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyloquent.schema.builder import SchemaBuilder


class Migration(ABC):
    """Base class for database migrations.

    Migrations allow you to evolve your database schema over time.
    Each migration class should implement the `up` and `down` methods.

    Example:
        class CreateUsersTable(Migration):
            async def up(self, schema: SchemaBuilder) -> None:
                await schema.create('users', lambda table: (
                    table.id(),
                    table.string('name'),
                    table.string('email').unique(),
                    table.timestamps()
                ))

            async def down(self, schema: SchemaBuilder) -> None:
                await schema.drop('users')
    """

    # Migration metadata
    name: str = ""
    batch: int = 0

    @abstractmethod
    async def up(self, schema: "SchemaBuilder") -> None:
        """Run the migration (forward).

        Args:
            schema: Schema builder instance
        """
        pass

    @abstractmethod
    async def down(self, schema: "SchemaBuilder") -> None:
        """Reverse the migration (rollback).

        Args:
            schema: Schema builder instance
        """
        pass
