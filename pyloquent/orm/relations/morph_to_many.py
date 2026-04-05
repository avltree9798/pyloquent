"""Morph-To-Many polymorphic many-to-many relation."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type

from pyloquent.orm.collection import Collection
from pyloquent.orm.relations.relation import Relation, T

if TYPE_CHECKING:  # pragma: no cover
    from pyloquent.orm.model import Model
    from pyloquent.query.builder import QueryBuilder


class MorphToMany(Relation[T]):
    """Polymorphic many-to-many relationship (e.g., Post/Video -> Tag).

    Example:
        class Post(Model):
            def tags(self):
                return self.morph_to_many(Tag, 'taggable')

        class Video(Model):
            def tags(self):
                return self.morph_to_many(Tag, 'taggable')
    """

    def __init__(
        self,
        parent: "Model",
        related: Type[T],
        name: str,
        table: Optional[str] = None,
        foreign_pivot_key: Optional[str] = None,
        related_pivot_key: Optional[str] = None,
        parent_key: Optional[str] = None,
        related_key: Optional[str] = None,
    ):
        super().__init__(parent, related, "", "")
        self.name = name
        self.morph_type = f"{name}_type"
        self.morph_id = f"{name}_id"
        self.table = table or f"{name}s"
        self.foreign_pivot_key = foreign_pivot_key or self.morph_id
        self.related_pivot_key = related_pivot_key or related._get_foreign_key()
        self.parent_key = parent_key or parent.__primary_key__
        self.related_key = related_key or related.__primary_key__
        self._pivot_columns: List[str] = []

    def add_constraints(self) -> None:
        pass

    def _create_query(self) -> "QueryBuilder[T]":
        related_table = getattr(self.related, "__table__", None) or self.related._get_default_table_name()
        parent_value = getattr(self.parent, self.parent_key)
        morph_class = self.parent.__class__.__name__

        query = self.related.query
        query = query.join(
            self.table,
            f"{related_table}.{self.related_key}",
            "=",
            f"{self.table}.{self.related_pivot_key}",
        )
        query = query.where(f"{self.table}.{self.morph_id}", parent_value)
        query = query.where(f"{self.table}.{self.morph_type}", morph_class)
        query = query.select_raw(f"{related_table}.*")
        return query

    async def get_results(self) -> Collection[T]:
        return await self.query.get()

    def with_pivot(self, *columns: str) -> "MorphToMany[T]":
        self._pivot_columns.extend(columns)
        return self

    async def attach(self, ids: Any, attributes: Optional[Dict[str, Any]] = None) -> None:
        if not isinstance(ids, dict):
            if not isinstance(ids, list):
                ids = [ids]
            ids = {id_: attributes or {} for id_ in ids}

        parent_value = getattr(self.parent, self.parent_key)
        morph_class = self.parent.__class__.__name__
        records = []
        for related_id, attrs in ids.items():
            record = {
                self.morph_id: parent_value,
                self.morph_type: morph_class,
                self.related_pivot_key: related_id,
                **attrs,
            }
            records.append(record)
        if records:
            await self._new_pivot_query().insert(records)

    async def detach(self, ids: Optional[Any] = None) -> int:
        query = self._new_pivot_query()
        if ids is not None:
            if not isinstance(ids, list):
                ids = [ids]
            query = query.where_in(self.related_pivot_key, ids)
        return await query.delete()

    async def sync(self, ids: List[Any]) -> Dict[str, List[Any]]:
        changes: Dict[str, List[Any]] = {"attached": [], "detached": []}
        current = await self._new_pivot_query().pluck(self.related_pivot_key)
        current_set = set(current)
        new_set = set(ids)
        to_detach = list(current_set - new_set)
        if to_detach:
            await self.detach(to_detach)
            changes["detached"] = to_detach
        to_attach = list(new_set - current_set)
        if to_attach:
            await self.attach(to_attach)
            changes["attached"] = to_attach
        return changes

    def _new_pivot_query(self) -> "QueryBuilder":
        from pyloquent.query.builder import QueryBuilder
        morph_class = self.parent.__class__.__name__
        parent_value = getattr(self.parent, self.parent_key)
        parent_query = self.parent._new_query()
        q = QueryBuilder(parent_query.grammar, connection=parent_query.connection)
        q = q.from_(self.table)
        q = q.where(self.morph_id, parent_value)
        q = q.where(self.morph_type, morph_class)
        return q
