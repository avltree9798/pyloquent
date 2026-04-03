"""Collection class for model collections."""

from collections import UserList
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    TypeVar,
    Union,
)

T = TypeVar("T")


class Collection(UserList, Generic[T]):
    """Enhanced list for model collections with Eloquent-style helpers.

    This class extends UserList to provide convenient methods for working
    with collections of models, similar to Laravel's Collection class.

    Example:
        users = await User.where('active', True).get()
        names = users.pluck('name')
        adults = users.where('age', '>=', 18)
    """

    def __init__(self, items: Optional[List[T]] = None):
        """Initialize the collection.

        Args:
            items: Initial list of items
        """
        super().__init__(items or [])

    # ========================================================================
    # Accessors
    # ========================================================================

    def first(self, callback: Optional[Callable[[T], bool]] = None) -> Optional[T]:
        """Get the first item in the collection.

        Args:
            callback: Optional callback to filter items

        Returns:
            First item or None if collection is empty
        """
        if callback:
            for item in self.data:
                if callback(item):
                    return item
            return None
        return self.data[0] if self.data else None

    def last(self, callback: Optional[Callable[[T], bool]] = None) -> Optional[T]:
        """Get the last item in the collection.

        Args:
            callback: Optional callback to filter items

        Returns:
            Last item or None if collection is empty
        """
        if callback:
            for item in reversed(self.data):
                if callback(item):
                    return item
            return None
        return self.data[-1] if self.data else None

    def nth(self, n: int) -> Optional[T]:
        """Get the nth item in the collection (0-indexed).

        Args:
            n: Index of item to retrieve

        Returns:
            Item at index n or None if out of range
        """
        try:
            return self.data[n]
        except IndexError:
            return None

    # ========================================================================
    # Filtering
    # ========================================================================

    def where(self, key: str, operator: Any, value: Any = None) -> "Collection[T]":
        """Filter items where key matches value.

        Args:
            key: Attribute/column name
            operator: Comparison operator or value (implies =)
            value: Value to compare

        Returns:
            New filtered collection
        """
        # Handle 2-argument form
        if value is None and operator is not None:
            value = operator
            operator = "="

        def _get_value(item: T, key: str) -> Any:
            if isinstance(item, dict):
                return item.get(key)
            return getattr(item, key, None)

        operators = {
            "=": lambda a, b: a == b,
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
            "<>": lambda a, b: a != b,
            ">": lambda a, b: a is not None and b is not None and a > b,
            "<": lambda a, b: a is not None and b is not None and a < b,
            ">=": lambda a, b: a is not None and b is not None and a >= b,
            "<=": lambda a, b: a is not None and b is not None and a <= b,
        }

        op_func = operators.get(operator, operators["="])

        return Collection([item for item in self.data if op_func(_get_value(item, key), value)])

    def where_in(self, key: str, values: List[Any]) -> "Collection[T]":
        """Filter items where key is in values.

        Args:
            key: Attribute/column name
            values: List of values to match

        Returns:
            New filtered collection
        """

        def _get_value(item: T, key: str) -> Any:
            if isinstance(item, dict):
                return item.get(key)
            return getattr(item, key, None)

        value_set = set(values)
        return Collection([item for item in self.data if _get_value(item, key) in value_set])

    def reject(self, callback: Callable[[T], bool]) -> "Collection[T]":
        """Filter items, excluding those that pass the callback.

        Args:
            callback: Function that returns True for items to exclude

        Returns:
            New filtered collection
        """
        return Collection([item for item in self.data if not callback(item)])

    def filter(self, callback: Callable[[T], bool]) -> "Collection[T]":
        """Filter items, keeping only those that pass the callback.

        Args:
            callback: Function that returns True for items to keep

        Returns:
            New filtered collection
        """
        return Collection([item for item in self.data if callback(item)])

    def unique(self, key: Optional[str] = None) -> "Collection[T]":
        """Get unique items from the collection.

        Args:
            key: Optional attribute to use for uniqueness

        Returns:
            New collection with unique items
        """
        seen = set()
        result = []

        for item in self.data:
            if key:
                if isinstance(item, dict):
                    value = item.get(key)
                else:
                    value = getattr(item, key, None)
            else:
                value = item

            # Convert to something hashable
            try:
                hashable_value = tuple(value) if isinstance(value, (list, dict)) else value
            except TypeError:
                hashable_value = str(value)

            if hashable_value not in seen:
                seen.add(hashable_value)
                result.append(item)

        return Collection(result)

    # ========================================================================
    # Sorting
    # ========================================================================

    def sort_by(self, key: str, reverse: bool = False) -> "Collection[T]":
        """Sort the collection by a key.

        Args:
            key: Attribute/column name to sort by
            reverse: Whether to sort in descending order

        Returns:
            New sorted collection
        """

        def _get_key(item: T) -> Any:
            if isinstance(item, dict):
                return item.get(key)
            return getattr(item, key, None)

        return Collection(sorted(self.data, key=_get_key, reverse=reverse))

    def sort_by_desc(self, key: str) -> "Collection[T]":
        """Sort the collection by a key in descending order.

        Args:
            key: Attribute/column name to sort by

        Returns:
            New sorted collection
        """
        return self.sort_by(key, reverse=True)

    # ========================================================================
    # Transformation
    # ========================================================================

    def pluck(self, key: str) -> List[Any]:
        """Get a list of values for a specific key.

        Args:
            key: Attribute/column name

        Returns:
            List of values
        """
        result = []
        for item in self.data:
            if isinstance(item, dict):
                result.append(item.get(key))
            else:
                result.append(getattr(item, key, None))
        return result

    def key_by(self, key: str) -> Dict[Any, T]:
        """Create a dictionary keyed by a specific attribute.

        Args:
            key: Attribute/column name to use as key

        Returns:
            Dictionary with items keyed by the specified attribute
        """
        result = {}
        for item in self.data:
            if isinstance(item, dict):
                k = item.get(key)
            else:
                k = getattr(item, key, None)
            result[k] = item
        return result

    def map(self, callback: Callable[[T], Any]) -> "Collection[Any]":
        """Transform each item using a callback.

        Args:
            callback: Function to transform each item

        Returns:
            New collection with transformed items
        """
        return Collection([callback(item) for item in self.data])

    # ========================================================================
    # Aggregates
    # ========================================================================

    def count(self) -> int:
        """Get the number of items in the collection.

        Returns:
            Item count
        """
        return len(self.data)

    def sum(self, key: str) -> Any:
        """Sum the values of a specific key.

        Args:
            key: Attribute/column name

        Returns:
            Sum of values (or 0 if collection is empty)
        """
        values = self.pluck(key)
        # Filter out None values
        values = [v for v in values if v is not None]
        if not values:
            return 0
        return sum(values)

    def avg(self, key: str) -> float:
        """Get the average of values for a specific key.

        Args:
            key: Attribute/column name

        Returns:
            Average value (or 0.0 if collection is empty)
        """
        values = self.pluck(key)
        # Filter out None values
        values = [v for v in values if v is not None]
        if not values:
            return 0.0
        return sum(values) / len(values)

    def max(self, key: str) -> Any:
        """Get the maximum value of a specific key.

        Args:
            key: Attribute/column name

        Returns:
            Maximum value (or None if collection is empty)
        """
        values = self.pluck(key)
        # Filter out None values
        values = [v for v in values if v is not None]
        if not values:
            return None
        return max(values)

    def min(self, key: str) -> Any:
        """Get the minimum value of a specific key.

        Args:
            key: Attribute/column name

        Returns:
            Minimum value (or None if collection is empty)
        """
        values = self.pluck(key)
        # Filter out None values
        values = [v for v in values if v is not None]
        if not values:
            return None
        return min(values)

    # ========================================================================
    # Iteration
    # ========================================================================

    def each(self, callback: Callable[[T], None]) -> "Collection[T]":
        """Execute a callback for each item.

        Args:
            callback: Function to call for each item

        Returns:
            Self for chaining
        """
        for item in self.data:
            callback(item)
        return self

    def chunk(self, size: int) -> Iterator["Collection[T]"]:
        """Split the collection into chunks.

        Args:
            size: Size of each chunk

        Yields:
            Collection chunks
        """
        for i in range(0, len(self.data), size):
            yield Collection(self.data[i : i + size])

    # ========================================================================
    # Async Helpers
    # ========================================================================

    async def map_async(self, callback: Callable[[T], Any]) -> "Collection[Any]":
        """Transform each item using an async callback.

        Args:
            callback: Async function to transform each item

        Returns:
            New collection with transformed items
        """
        results = []
        for item in self.data:
            result = await callback(item)
            results.append(result)
        return Collection(results)

    async def each_async(self, callback: Callable[[T], Any]) -> "Collection[T]":
        """Execute an async callback for each item.

        Args:
            callback: Async function to call for each item

        Returns:
            Self for chaining
        """
        for item in self.data:
            await callback(item)
        return self

    # ========================================================================
    # Magic Methods
    # ========================================================================

    def __iter__(self) -> Iterator[T]:
        """Allow iterating over the collection."""
        return iter(self.data)

    def __len__(self) -> int:
        """Get the count of items."""
        return len(self.data)

    def __getitem__(self, index: Union[int, slice]) -> Union[T, "Collection[T]"]:
        """Get item(s) by index."""
        result = self.data[index]
        if isinstance(index, slice):
            return Collection(result)
        return result

    def __repr__(self) -> str:
        """Get string representation."""
        return f"Collection({self.data!r})"

    def __str__(self) -> str:
        """Get string representation."""
        return str(self.data)
