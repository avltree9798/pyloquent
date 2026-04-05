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

    def unique(self, key: Optional[str] = None) -> "Collection[T]":  # pragma: no cover
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

    def sort_by(self, key: str, reverse: bool = False) -> "Collection[T]":  # pragma: no cover
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

    def sort_by_desc(self, key: str) -> "Collection[T]":  # pragma: no cover
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

    def pluck(self, key: str) -> List[Any]:  # pragma: no cover
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

    def key_by(self, key: str) -> Dict[Any, T]:  # pragma: no cover
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
    # Presence / Membership
    # ========================================================================

    def is_empty(self) -> bool:
        """Check if the collection has no items."""
        return len(self.data) == 0

    def is_not_empty(self) -> bool:
        """Check if the collection has at least one item."""
        return len(self.data) > 0

    def contains(self, key_or_callback: Any, value: Any = None) -> bool:
        """Check if the collection contains an item.

        Args:
            key_or_callback: Attribute name, value to search for, or callable
            value: Value to compare against (if key_or_callback is an attribute name)

        Returns:
            True if item is found
        """
        if callable(key_or_callback):
            return any(key_or_callback(item) for item in self.data)
        if value is None:
            return key_or_callback in self.data
        for item in self.data:
            item_val = item.get(key_or_callback) if isinstance(item, dict) else getattr(item, key_or_callback, None)
            if item_val == value:
                return True
        return False

    def doesnt_contain(self, key_or_callback: Any, value: Any = None) -> bool:
        """Opposite of contains."""
        return not self.contains(key_or_callback, value)

    def first_where(self, key: str, operator: Any = None, value: Any = None) -> Optional[T]:
        """Get first item matching a key/value pair.

        Args:
            key: Attribute name
            operator: Comparison operator or value
            value: Value to compare

        Returns:
            First matching item or None
        """
        if value is None:
            value = operator
            operator = "="
        for item in self.data:
            item_val = item.get(key) if isinstance(item, dict) else getattr(item, key, None)
            if operator in ("=", "==") and item_val == value:
                return item
            elif operator == "!=" and item_val != value:
                return item
            elif operator == ">" and item_val > value:
                return item
            elif operator == ">=" and item_val >= value:
                return item
            elif operator == "<" and item_val < value:
                return item
            elif operator == "<=" and item_val <= value:
                return item
        return None

    def sole(self) -> T:
        """Get the only item in the collection, or raise if not exactly one.

        Returns:
            The single item

        Raises:
            ValueError: If collection does not contain exactly one item
        """
        if len(self.data) == 0:
            raise ValueError("Collection is empty")
        if len(self.data) > 1:
            raise ValueError(f"Collection contains {len(self.data)} items")
        return self.data[0]

    # ========================================================================
    # Set Operations
    # ========================================================================

    def diff(self, items: List[T]) -> "Collection[T]":
        """Return items in this collection not present in items."""
        return Collection([x for x in self.data if x not in items])

    def intersect(self, items: List[T]) -> "Collection[T]":
        """Return items present in both this collection and items."""
        return Collection([x for x in self.data if x in items])

    def unique(self, key: Optional[str] = None) -> "Collection[T]":
        """Return collection with duplicate items removed.

        Args:
            key: Attribute to determine uniqueness

        Returns:
            Collection with unique items
        """
        if key is None:
            seen = []
            result = []
            for item in self.data:
                if item not in seen:
                    seen.append(item)
                    result.append(item)
            return Collection(result)
        seen_keys = set()
        result = []
        for item in self.data:
            k = item.get(key) if isinstance(item, dict) else getattr(item, key, None)
            if k not in seen_keys:
                seen_keys.add(k)
                result.append(item)
        return Collection(result)

    def duplicates(self, key: Optional[str] = None) -> "Collection[T]":
        """Return items that appear more than once."""
        from collections import Counter
        if key is None:
            counts: Dict[Any, int] = {}
            result = []
            for item in self.data:
                k = id(item)
                counts[k] = counts.get(k, 0) + 1
            return Collection([x for x in self.data if self.data.count(x) > 1])
        seen: Dict[Any, int] = {}
        for item in self.data:
            k = item.get(key) if isinstance(item, dict) else getattr(item, key, None)
            seen[k] = seen.get(k, 0) + 1
        return Collection([
            x for x in self.data
            if seen.get(x.get(key) if isinstance(x, dict) else getattr(x, key, None), 0) > 1
        ])

    # ========================================================================
    # Merging / Combining
    # ========================================================================

    def merge(self, *collections: Any) -> "Collection[T]":
        """Merge one or more collections or lists into this collection.

        Returns:
            New merged collection
        """
        result = list(self.data)
        for c in collections:
            result.extend(c)
        return Collection(result)

    def concat(self, *iterables: Any) -> "Collection[T]":
        """Concatenate iterables onto the collection."""
        return self.merge(*iterables)

    def zip(self, *iterables: Any) -> "Collection[tuple]":
        """Zip the collection with other iterables."""
        return Collection(list(zip(self.data, *iterables)))

    def collapse(self) -> "Collection[Any]":
        """Flatten a collection of lists into a single collection."""
        result = []
        for item in self.data:
            if hasattr(item, "__iter__") and not isinstance(item, (str, bytes, dict)):
                result.extend(item)
            else:
                result.append(item)
        return Collection(result)

    def flatten(self, depth: Optional[int] = None) -> "Collection[Any]":
        """Recursively flatten nested collections/lists.

        Args:
            depth: Maximum depth to flatten (None = unlimited)

        Returns:
            Flattened collection
        """
        def _flatten(items: list, current_depth: int) -> list:
            result = []
            for item in items:
                if hasattr(item, "__iter__") and not isinstance(item, (str, bytes, dict)):
                    if depth is None or current_depth < depth:
                        result.extend(_flatten(list(item), current_depth + 1))
                    else:
                        result.append(item)
                else:
                    result.append(item)
            return result
        return Collection(_flatten(self.data, 0))

    # ========================================================================
    # Grouping / Splitting
    # ========================================================================

    def group_by(self, key: Union[str, Callable]) -> Dict[Any, "Collection[T]"]:
        """Group items by a key or callback.

        Args:
            key: Attribute name or callable returning group key

        Returns:
            Dictionary mapping group keys to Collections
        """
        result: Dict[Any, list] = {}
        for item in self.data:
            if callable(key):
                k = key(item)
            elif isinstance(item, dict):
                k = item.get(key)
            else:
                k = getattr(item, key, None)
            if k not in result:
                result[k] = []
            result[k].append(item)
        return {k: Collection(v) for k, v in result.items()}

    def partition(self, callback: Callable[[T], bool]) -> "tuple[Collection[T], Collection[T]]":
        """Split into two collections: truthy and falsy results.

        Args:
            callback: Predicate function

        Returns:
            Tuple of (matching, non-matching) Collections
        """
        truthy, falsy = [], []
        for item in self.data:
            (truthy if callback(item) else falsy).append(item)
        return Collection(truthy), Collection(falsy)

    def split(self, count: int) -> "Collection[Collection[T]]":
        """Split the collection into the given number of groups.

        Args:
            count: Number of groups

        Returns:
            Collection of Collections
        """
        size = max(1, -(-len(self.data) // count))  # ceiling division
        return Collection([
            Collection(self.data[i:i + size])
            for i in range(0, len(self.data), size)
        ])

    def splice(self, index: int, delete: Optional[int] = None, replacement: Optional[list] = None) -> "Collection[T]":
        """Remove and return a slice, optionally replacing it.

        Args:
            index: Start index
            delete: Number of items to remove (None = all remaining)
            replacement: Items to insert in place of removed items

        Returns:
            Collection of removed items
        """
        if delete is None:
            removed = self.data[index:]
            self.data = self.data[:index]
        else:
            removed = self.data[index:index + delete]
            self.data = self.data[:index] + (replacement or []) + self.data[index + delete:]
        return Collection(removed)

    # ========================================================================
    # Transformations
    # ========================================================================

    def flat_map(self, callback: Callable[[T], Any]) -> "Collection[Any]":
        """Map then flatten one level deep.

        Args:
            callback: Transform function returning an iterable

        Returns:
            New flattened collection
        """
        result = []
        for item in self.data:
            val = callback(item)
            if hasattr(val, "__iter__") and not isinstance(val, (str, bytes, dict)):
                result.extend(val)
            else:
                result.append(val)
        return Collection(result)

    def map_with_keys(self, callback: Callable[[T], tuple]) -> Dict[Any, Any]:
        """Map items to a dictionary using callback returning (key, value) tuples.

        Args:
            callback: Function returning (key, value) pair

        Returns:
            Dictionary of results
        """
        result = {}
        for item in self.data:
            k, v = callback(item)
            result[k] = v
        return result

    def map_into(self, cls: type) -> "Collection[Any]":
        """Map each item into a new class instance.

        Args:
            cls: Class to instantiate with each item

        Returns:
            Collection of new instances
        """
        return Collection([cls(item) for item in self.data])

    def key_by(self, key: Union[str, Callable]) -> Dict[Any, T]:
        """Key collection items by a given attribute or callback.

        Args:
            key: Attribute name or callable

        Returns:
            Dictionary keyed by the given attribute
        """
        result = {}
        for item in self.data:
            k = key(item) if callable(key) else (item.get(key) if isinstance(item, dict) else getattr(item, key, None))
            result[k] = item
        return result

    # ========================================================================
    # Reduction
    # ========================================================================

    def reduce(self, callback: Callable, initial: Any = None) -> Any:
        """Reduce the collection to a single value.

        Args:
            callback: Function(carry, item) -> carry
            initial: Initial carry value

        Returns:
            Reduced value
        """
        import functools
        return functools.reduce(callback, self.data, initial)

    def count_by(self, callback: Optional[Callable[[T], Any]] = None) -> Dict[Any, int]:
        """Count occurrences of each unique value.

        Args:
            callback: Optional function to derive the key from each item

        Returns:
            Dictionary mapping value -> count
        """
        result: Dict[Any, int] = {}
        for item in self.data:
            k = callback(item) if callback else item
            result[k] = result.get(k, 0) + 1
        return result

    def median(self, key: Optional[str] = None) -> Optional[float]:
        """Get the median value.

        Args:
            key: Attribute to use (for model collections)

        Returns:
            Median value or None
        """
        def _get(item: Any) -> Any:
            if key:
                return item.get(key) if isinstance(item, dict) else getattr(item, key, None)
            return item

        values = sorted(v for item in self.data if (v := _get(item)) is not None)
        if not values:
            return None
        n = len(values)
        mid = n // 2
        return (values[mid - 1] + values[mid]) / 2 if n % 2 == 0 else float(values[mid])

    def mode(self, key: Optional[str] = None) -> Optional[Any]:
        """Get the most frequently occurring value.

        Args:
            key: Attribute to use (for model collections)

        Returns:
            Mode value or None
        """
        counts = self.count_by(
            (lambda item: item.get(key) if isinstance(item, dict) else getattr(item, key, None)) if key else None
        )
        if not counts:
            return None
        return max(counts, key=counts.__getitem__)

    # ========================================================================
    # Pipelines
    # ========================================================================

    def pipe(self, callback: Callable[["Collection[T]"], Any]) -> Any:
        """Pass the collection through a callback and return the result.

        Args:
            callback: Function that receives the collection

        Returns:
            Result of callback
        """
        return callback(self)

    def tap(self, callback: Callable[["Collection[T]"], None]) -> "Collection[T]":
        """Tap into the collection chain without modifying it.

        Args:
            callback: Callback that receives the collection

        Returns:
            Self for chaining
        """
        callback(self)
        return self

    def when(
        self,
        condition: Any,
        callback: Callable[["Collection[T]"], "Collection[T]"],
        default: Optional[Callable[["Collection[T]"], "Collection[T]"]] = None,
    ) -> "Collection[T]":
        """Apply a callback only when condition is truthy.

        Returns:
            Self (or result of callback)
        """
        if condition:
            return callback(self) or self
        elif default is not None:
            return default(self) or self
        return self

    def unless(
        self,
        condition: Any,
        callback: Callable[["Collection[T]"], "Collection[T]"],
        default: Optional[Callable[["Collection[T]"], "Collection[T]"]] = None,
    ) -> "Collection[T]":
        """Apply a callback only when condition is falsy."""
        return self.when(not condition, callback, default)

    # ========================================================================
    # Mutation
    # ========================================================================

    def push(self, *items: T) -> "Collection[T]":
        """Append one or more items to the end of the collection.

        Returns:
            Self for chaining
        """
        for item in items:
            self.data.append(item)
        return self

    def prepend(self, *items: T) -> "Collection[T]":
        """Prepend one or more items to the beginning of the collection.

        Returns:
            Self for chaining
        """
        for item in reversed(items):
            self.data.insert(0, item)
        return self

    def pop(self) -> Optional[T]:
        """Remove and return the last item."""
        return self.data.pop() if self.data else None

    def shift(self) -> Optional[T]:
        """Remove and return the first item."""
        return self.data.pop(0) if self.data else None

    def forget(self, index: int) -> "Collection[T]":
        """Remove the item at the given index.

        Args:
            index: Index to remove

        Returns:
            Self for chaining
        """
        if 0 <= index < len(self.data):
            del self.data[index]
        return self

    def shuffle(self) -> "Collection[T]":
        """Randomly shuffle the items in the collection.

        Returns:
            Self for chaining
        """
        import random
        random.shuffle(self.data)
        return self

    def random(self, count: Optional[int] = None) -> Union[T, "Collection[T]"]:
        """Get one or more random items.

        Args:
            count: Number of items to return (None = single item)

        Returns:
            Single item or Collection
        """
        import random
        if count is None:
            return random.choice(self.data)
        return Collection(random.sample(self.data, min(count, len(self.data))))

    def pad(self, size: int, value: Any = None) -> "Collection[T]":
        """Pad the collection to the given size.

        Args:
            size: Target size (negative = pad left)
            value: Value to pad with

        Returns:
            New padded collection
        """
        n = abs(size)
        padding = [value] * max(0, n - len(self.data))
        if size < 0:
            return Collection(padding + list(self.data))
        return Collection(list(self.data) + padding)

    # ========================================================================
    # Serialization
    # ========================================================================

    def to_array(self) -> List[Any]:
        """Convert collection to plain list.

        Returns:
            List representation
        """
        result = []
        for item in self.data:
            if hasattr(item, "to_dict"):
                result.append(item.to_dict())
            elif hasattr(item, "to_array"):
                result.append(item.to_array())
            else:
                result.append(item)
        return result

    def to_json(self) -> str:
        """Convert collection to JSON string.

        Returns:
            JSON string
        """
        import json
        return json.dumps(self.to_array(), default=str)

    def only(self, *keys: str) -> "Collection[Any]":
        """Return a collection of dicts/models with only the specified keys.

        Args:
            *keys: Keys to include

        Returns:
            New collection with filtered keys
        """
        result = []
        for item in self.data:
            if isinstance(item, dict):
                result.append({k: v for k, v in item.items() if k in keys})
            else:
                result.append({k: getattr(item, k, None) for k in keys})
        return Collection(result)

    def except_(self, *keys: str) -> "Collection[Any]":
        """Return collection with specified keys removed.

        Args:
            *keys: Keys to exclude

        Returns:
            New collection with keys removed
        """
        result = []
        for item in self.data:
            if isinstance(item, dict):
                result.append({k: v for k, v in item.items() if k not in keys})
            else:
                d = item.to_dict() if hasattr(item, "to_dict") else vars(item)
                result.append({k: v for k, v in d.items() if k not in keys})
        return Collection(result)

    def where_not_in(self, key: str, values: List[Any]) -> "Collection[T]":
        """Filter items where key is not in the given list of values.

        Args:
            key: Attribute name
            values: Values to exclude

        Returns:
            Filtered collection
        """
        return Collection([
            item for item in self.data
            if (item.get(key) if isinstance(item, dict) else getattr(item, key, None)) not in values
        ])

    def take(self, count: int) -> "Collection[T]":
        """Take the first (or last if negative) n items.

        Args:
            count: Number of items (negative = from end)

        Returns:
            New collection
        """
        if count < 0:
            return Collection(self.data[count:])
        return Collection(self.data[:count])

    def skip(self, count: int) -> "Collection[T]":
        """Skip the first n items.

        Args:
            count: Number to skip

        Returns:
            New collection
        """
        return Collection(self.data[count:])

    def take_while(self, callback: Callable[[T], bool]) -> "Collection[T]":
        """Take items while callback returns True."""
        result = []
        for item in self.data:
            if callback(item):
                result.append(item)
            else:
                break
        return Collection(result)

    def skip_while(self, callback: Callable[[T], bool]) -> "Collection[T]":
        """Skip items while callback returns True."""
        result = []
        skipping = True
        for item in self.data:
            if skipping and callback(item):
                continue
            skipping = False
            result.append(item)
        return Collection(result)

    def sort_by(self, key: Union[str, Callable], descending: bool = False) -> "Collection[T]":
        """Sort by a key attribute or callback.

        Args:
            key: Attribute name or callable
            descending: Sort in descending order

        Returns:
            New sorted collection
        """
        def sort_key(item: Any) -> Any:
            if callable(key):
                return key(item)
            if isinstance(item, dict):
                return item.get(key)
            return getattr(item, key, None)

        return Collection(sorted(self.data, key=sort_key, reverse=descending))

    def sort_by_desc(self, key: Union[str, Callable]) -> "Collection[T]":
        """Sort by key in descending order."""
        return self.sort_by(key, descending=True)

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
