"""Belongs-To-Many relationship implementation."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type

from pyloquent.orm.collection import Collection
from pyloquent.orm.relations.relation import Relation, T

if TYPE_CHECKING:  # pragma: no cover
    from pyloquent.orm.model import Model


class BelongsToMany(Relation[T]):
    """Many-to-many relationship.

    This class represents a many-to-many relationship where
    both sides can have many related models through a pivot table.

    Example:
        class User(Model):
            def roles(self):
                return self.belongs_to_many(Role)

        class Role(Model):
            def users(self):
                return self.belongs_to_many(User)

        # Usage
        user = await User.find(1)
        roles = await user.roles().get()

        # Attach/detach/sync
        await user.roles().attach([1, 2, 3])
        await user.roles().detach([1])
        await user.roles().sync([2, 3, 4])

        # With pivot data
        await user.roles().attach({
            1: {'expires_at': datetime.now()},
            2: {'expires_at': datetime.now()},
        })
    """

    def __init__(
        self,
        parent: "Model",
        related: Type[T],
        table: Optional[str] = None,
        foreign_pivot_key: Optional[str] = None,
        related_pivot_key: Optional[str] = None,
        parent_key: Optional[str] = None,
        related_key: Optional[str] = None,
    ):
        """Initialize the belongs-to-many relation.

        Args:
            parent: The parent model instance
            related: The related model class
            table: Pivot table name (auto-generated if not set)
            foreign_pivot_key: Foreign key for parent in pivot table
            related_pivot_key: Foreign key for related in pivot table
            parent_key: Local key on parent model
            related_key: Local key on related model
        """
        # For belongs-to-many, we use the related model's key
        super().__init__(parent, related, "", "")

        self.table = table or self._get_pivot_table_name()
        self.foreign_pivot_key = foreign_pivot_key or parent._get_foreign_key()
        self.related_pivot_key = related_pivot_key or related._get_foreign_key()
        self.parent_key = parent_key or parent.__primary_key__
        self.related_key = related_key or related.__primary_key__

        # Pivot columns to select
        self._pivot_columns: List[str] = []
        self._pivot_wheres: List[Dict[str, Any]] = []

    def _get_pivot_table_name(self) -> str:
        """Get the pivot table name.

        Returns:
            Table name (alphabetically ordered, snake_case, plural)
        """
        models = sorted([self.parent.__class__.__name__.lower(), self.related.__name__.lower()])
        return f"{models[0]}_{models[1]}"

    def add_constraints(self) -> None:
        """Add constraints for the pivot table join."""
        self._query = self._query

    async def get_results(self) -> Collection[T]:
        """Get the related models through the pivot table.

        Returns:
            Collection of related models
        """
        # Build query with pivot table join
        query = self._create_pivot_query()

        # Execute and hydrate
        results = await query.get()

        # Attach pivot data to models
        for model in results:
            self._hydrate_pivot(model)

        return results

    def _create_pivot_query(self) -> "QueryBuilder[T]":
        """Create query with pivot table join.

        Returns:
            QueryBuilder instance
        """
        # Get parent key value
        parent_value = getattr(self.parent, self.parent_key)

        # Build query
        query = self.related.query

        # Join pivot table
        query = query.join(
            self.table,
            f"{self.related.__table__}.{self.related_key}",
            "=",
            f"{self.table}.{self.related_pivot_key}",
        )

        # Where on pivot table
        query = query.where(f"{self.table}.{self.foreign_pivot_key}", parent_value)

        # Add pivot wheres
        for where in self._pivot_wheres:
            query = query.where(
                f"{self.table}.{where['column']}", where.get("operator", "="), where["value"]
            )

        # Select related model columns
        query = query.select_raw(f"{self.related.__table__}.*")

        # Select pivot columns
        if self._pivot_columns:
            for col in self._pivot_columns:
                query = query.select_raw(f"{self.table}.{col} as pivot_{col}")
        else:
            query = query.select_raw(
                f"{self.table}.{self.foreign_pivot_key} as pivot_{self.foreign_pivot_key},"
                f" {self.table}.{self.related_pivot_key} as pivot_{self.related_pivot_key}"
            )

        return query

    def _hydrate_pivot(self, model: T) -> None:
        """Hydrate pivot data onto the model.

        Args:
            model: Related model instance
        """
        pivot_data = {}

        # Extract pivot attributes
        for attr in list(model.__dict__.keys()):
            if attr.startswith("pivot_"):
                pivot_data[attr[6:]] = getattr(model, attr)
                delattr(model, attr)

        # Set pivot relation
        model.set_relation("pivot", pivot_data)

    def with_pivot(self, *columns: str) -> "BelongsToMany[T]":
        """Specify additional pivot columns to retrieve.

        Args:
            *columns: Column names

        Returns:
            Self for chaining
        """
        self._pivot_columns.extend(columns)
        return self

    def where_pivot(self, column: str, operator: Any, value: Any = None) -> "BelongsToMany[T]":
        """Add where clause on pivot table.

        Args:
            column: Column name
            operator: Operator or value
            value: Value (if operator provided)

        Returns:
            Self for chaining
        """
        if value is None:
            value = operator
            operator = "="

        self._pivot_wheres.append({"column": column, "operator": operator, "value": value})

        return self

    async def attach(self, ids: Any, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Attach related models to the parent.

        Args:
            ids: Single ID, list of IDs, or dict mapping IDs to pivot attributes
            attributes: Additional attributes for pivot table (if ids is not dict)
        """
        # Normalize ids to dict format
        if not isinstance(ids, dict):
            if not isinstance(ids, list):
                ids = [ids]
            ids = {id_: attributes or {} for id_ in ids}

        # Get parent key value
        parent_value = getattr(self.parent, self.parent_key)

        # Insert records into pivot table
        records = []
        for related_id, attrs in ids.items():
            record = {
                self.foreign_pivot_key: parent_value,
                self.related_pivot_key: related_id,
                **attrs,
            }
            records.append(record)

        if records:
            await self._new_pivot_query().insert(records)

    async def detach(self, ids: Optional[Any] = None) -> int:
        """Detach related models from the parent.

        Args:
            ids: Single ID, list of IDs, or None to detach all

        Returns:
            Number of detached records
        """
        query = self._new_pivot_query()

        if ids is not None:
            if not isinstance(ids, list):
                ids = [ids]
            query = query.where_in(self.related_pivot_key, ids)

        return await query.delete()

    async def sync(self, ids: List[Any], detaching: bool = True) -> Dict[str, List[Any]]:
        """Sync related models to the parent.

        This will add new relations and optionally remove existing ones
        not in the list.

        Args:
            ids: List of IDs to sync
            detaching: Whether to detach IDs not in the list

        Returns:
            Dict with 'attached', 'detached', and 'updated' lists
        """
        changes = {"attached": [], "detached": [], "updated": []}

        # Get current attached IDs
        current = await self._new_pivot_query().pluck(self.related_pivot_key)
        current_set = set(current)
        new_set = set(ids)

        # Detach
        if detaching:
            to_detach = list(current_set - new_set)
            if to_detach:
                await self.detach(to_detach)
                changes["detached"] = to_detach

        # Attach new
        to_attach = list(new_set - current_set)
        if to_attach:
            await self.attach(to_attach)
            changes["attached"] = to_attach

        return changes

    async def toggle(self, ids: List[Any]) -> Dict[str, List[Any]]:
        """Toggle related models attachment.

        Args:
            ids: List of IDs to toggle

        Returns:
            Dict with 'attached' and 'detached' lists
        """
        changes = {"attached": [], "detached": []}

        # Get current attached IDs
        current = await self._new_pivot_query().pluck(self.related_pivot_key)
        current_set = set(current)
        toggle_set = set(ids)

        to_detach = list(current_set & toggle_set)
        to_attach = list(toggle_set - current_set)

        if to_detach:
            await self.detach(to_detach)
            changes["detached"] = to_detach

        if to_attach:
            await self.attach(to_attach)
            changes["attached"] = to_attach

        return changes

    async def update_existing_pivot(self, id: Any, attributes: Dict[str, Any]) -> int:
        """Update pivot table attributes for an existing relation.

        Args:
            id: Related model ID
            attributes: Attributes to update

        Returns:
            Number of updated records
        """
        return await self._new_pivot_query().where(self.related_pivot_key, id).update(attributes)

    def _new_pivot_query(self) -> "QueryBuilder":
        """Create a query builder for the pivot table.

        Returns:
            QueryBuilder instance
        """
        from pyloquent.query.builder import QueryBuilder

        parent_query = self.parent._new_query()
        query = QueryBuilder(parent_query.grammar, connection=parent_query.connection)
        query = query.from_(self.table)
        query = query.where(self.foreign_pivot_key, getattr(self.parent, self.parent_key))

        return query

    def find(self, id: Any) -> Any:
        """Find a related model by ID.

        Args:
            id: Model ID

        Returns:
            Coroutine that resolves to model or None
        """
        return (
            self._create_pivot_query()
            .where(f"{self.related.__table__}.{self.related_key}", id)
            .first()
        )

    def find_many(self, ids: List[Any]) -> Any:
        """Find multiple related models by ID.

        Args:
            ids: List of model IDs

        Returns:
            Coroutine that resolves to Collection
        """
        return (
            self._create_pivot_query()
            .where_in(f"{self.related.__table__}.{self.related_key}", ids)
            .get()
        )
