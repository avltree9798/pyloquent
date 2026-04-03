"""Soft deletes trait for models."""

from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional, Type, TypeVar

if TYPE_CHECKING:
    from pyloquent.orm.model import Model
    from pyloquent.query.builder import QueryBuilder

T = TypeVar("T", bound="Model")


class SoftDeletes:
    """Trait for soft delete functionality.

    Models using this trait will not be permanently deleted. Instead,
    they will have their 'deleted_at' timestamp set. You can restore
    soft-deleted models or permanently delete them with forceDelete.

    Example:
        class User(Model, SoftDeletes):
            __table__ = 'users'
            __fillable__ = ['name', 'email']

            id: Optional[int] = None
            name: str
            email: str
            deleted_at: Optional[datetime] = None

        # Soft delete
        user = await User.find(1)
        await user.delete()  # Sets deleted_at timestamp

        # Restore
        await user.restore()  # Clears deleted_at

        # Permanent delete
        await user.force_delete()  # Actually removes from database

        # Query soft deleted models
        all_users = await User.with_trashed().get()
        trashed = await User.only_trashed().get()
    """

    __soft_deletes__: ClassVar[bool] = True
    __deleted_at_column__: ClassVar[str] = "deleted_at"

    # Instance state
    _force_deleting: bool = False

    async def delete(self: T) -> bool:
        """Soft delete the model.

        Sets the deleted_at timestamp instead of actually deleting.

        Returns:
            True on success
        """
        if self._force_deleting:
            return await self._perform_force_delete()

        return await self._perform_soft_delete()

    async def _perform_soft_delete(self: T) -> bool:
        """Perform the soft delete operation.

        Returns:
            True on success
        """
        # Set deleted_at timestamp
        setattr(self, self.__deleted_at_column__, datetime.now())

        # Update the record
        query = self._new_query_without_scope().where(self.__primary_key__, self._get_key())
        await query.update({self.__deleted_at_column__: datetime.now()})

        return True

    async def _perform_force_delete(self: T) -> bool:
        """Perform the actual database deletion.

        Returns:
            True on success
        """
        # Call parent delete method
        from pyloquent.orm.model import Model

        return await super(SoftDeletes, self).delete()

    async def restore(self: T) -> bool:
        """Restore a soft-deleted model.

        Returns:
            True if restored, False if not deleted
        """
        if not self.trashed():
            return False

        # Clear deleted_at
        setattr(self, self.__deleted_at_column__, None)

        # Update the record
        query = self._new_query_without_scope().where(self.__primary_key__, self._get_key())
        await query.update({self.__deleted_at_column__: None})

        return True

    async def force_delete(self: T) -> bool:
        """Permanently delete the model from the database.

        Returns:
            True on success
        """
        self._force_deleting = True
        result = await self.delete()
        self._force_deleting = False
        return result

    def trashed(self: T) -> bool:
        """Check if the model has been soft deleted.

        Returns:
            True if soft deleted
        """
        deleted_at = getattr(self, self.__deleted_at_column__, None)
        return deleted_at is not None

    @classmethod
    def with_trashed(cls: Type[T]) -> "QueryBuilder[T]":
        """Include soft-deleted models in query results.

        Returns:
            QueryBuilder instance
        """
        return cls.query.without_global_scope("soft_deletes")

    @classmethod
    def without_trashed(cls: Type[T]) -> "QueryBuilder[T]":
        """Exclude soft-deleted models from query results (default).

        Returns:
            QueryBuilder instance
        """
        return cls.query

    @classmethod
    def only_trashed(cls: Type[T]) -> "QueryBuilder[T]":
        """Only include soft-deleted models in query results.

        Returns:
            QueryBuilder instance
        """
        return cls.query.without_global_scope("soft_deletes").where_not_null(
            cls.__deleted_at_column__
        )

    @classmethod
    def restore_trashed(cls: Type[T], ids: Optional[List[Any]] = None) -> int:
        """Restore multiple soft-deleted models.

        Args:
            ids: Optional list of IDs to restore (all if None)

        Returns:
            Number of restored models
        """
        query = cls.only_trashed()

        if ids is not None:
            query = query.where_in(cls.__primary_key__, ids)

        async def _restore():
            return await query.update({cls.__deleted_at_column__: None})

        return _restore()

    @classmethod
    def force_delete_trashed(cls: Type[T], ids: Optional[List[Any]] = None) -> int:
        """Permanently delete soft-deleted models.

        Args:
            ids: Optional list of IDs to delete (all if None)

        Returns:
            Number of deleted models
        """
        query = cls.only_trashed()

        if ids is not None:
            query = query.where_in(cls.__primary_key__, ids)

        async def _delete():
            return await query.delete()

        return _delete()

    def _new_query_without_scope(self: T) -> "QueryBuilder[T]":
        """Create new query without soft delete scope.

        Returns:
            QueryBuilder instance
        """
        return self._new_query()

    @classmethod
    def boot_soft_deletes(cls: Type[T]) -> None:
        """Boot the soft deletes trait.

        This adds the global scope to exclude soft-deleted models.
        """
        # Add global scope to exclude deleted models
        cls.add_global_scope(
            "soft_deletes", lambda query: query.where_null(cls.__deleted_at_column__)
        )

    @classmethod
    def add_global_scope(cls: Type[T], name: str, callback: callable) -> None:
        """Add a global scope to the model.

        Args:
            name: Scope name
            callback: Scope callback
        """
        if not hasattr(cls, "_global_scopes"):
            cls._global_scopes = {}
        cls._global_scopes[name] = callback
