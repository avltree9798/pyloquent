"""Tests for Collection class."""

import pytest

from pyloquent.orm.collection import Collection


class TestCollectionBasics:
    """Test basic Collection functionality."""

    def test_empty_collection(self):
        """Test empty collection."""
        col = Collection()
        assert len(col) == 0
        assert col.count() == 0
        assert col.first() is None
        assert col.last() is None

    def test_collection_with_items(self):
        """Test collection with items."""
        col = Collection([1, 2, 3])
        assert len(col) == 3
        assert col.count() == 3
        assert col.first() == 1
        assert col.last() == 3

    def test_nth(self):
        """Test nth method."""
        col = Collection([1, 2, 3])
        assert col.nth(0) == 1
        assert col.nth(1) == 2
        assert col.nth(10) is None


class TestCollectionFiltering:
    """Test Collection filtering methods."""

    def test_where(self):
        """Test where with dictionaries."""
        col = Collection(
            [{"name": "John", "age": 25}, {"name": "Jane", "age": 30}, {"name": "Bob", "age": 20}]
        )

        result = col.where("age", ">=", 25)

        assert len(result) == 2
        assert result.first()["name"] == "John"
        assert result.last()["name"] == "Jane"

    def test_where_with_objects(self):
        """Test where with objects."""

        class Person:
            def __init__(self, name, age):
                self.name = name
                self.age = age

        col = Collection([Person("John", 25), Person("Jane", 30), Person("Bob", 20)])

        result = col.where("age", ">=", 25)

        assert len(result) == 2

    def test_where_in(self):
        """Test where_in."""
        col = Collection([{"id": 1}, {"id": 2}, {"id": 3}])

        result = col.where_in("id", [1, 3])

        assert len(result) == 2

    def test_filter(self):
        """Test filter."""
        col = Collection([1, 2, 3, 4, 5])

        result = col.filter(lambda x: x > 2)

        assert len(result) == 3
        assert list(result) == [3, 4, 5]

    def test_reject(self):
        """Test reject."""
        col = Collection([1, 2, 3, 4, 5])

        result = col.reject(lambda x: x > 2)

        assert len(result) == 2
        assert list(result) == [1, 2]

    def test_unique(self):
        """Test unique."""
        col = Collection([1, 2, 2, 3, 3, 3])

        result = col.unique()

        assert len(result) == 3
        assert list(result) == [1, 2, 3]


class TestCollectionTransformation:
    """Test Collection transformation methods."""

    def test_pluck(self):
        """Test pluck."""
        col = Collection([{"name": "John", "age": 25}, {"name": "Jane", "age": 30}])

        names = col.pluck("name")

        assert names == ["John", "Jane"]

    def test_map(self):
        """Test map."""
        col = Collection([1, 2, 3])

        result = col.map(lambda x: x * 2)

        assert list(result) == [2, 4, 6]

    def test_key_by(self):
        """Test key_by."""
        col = Collection([{"id": 1, "name": "John"}, {"id": 2, "name": "Jane"}])

        result = col.key_by("id")

        assert result[1]["name"] == "John"
        assert result[2]["name"] == "Jane"


class TestCollectionSorting:
    """Test Collection sorting methods."""

    def test_sort_by(self):
        """Test sort_by."""
        col = Collection([{"name": "Charlie"}, {"name": "Alice"}, {"name": "Bob"}])

        result = col.sort_by("name")

        assert result.nth(0)["name"] == "Alice"
        assert result.nth(1)["name"] == "Bob"
        assert result.nth(2)["name"] == "Charlie"

    def test_sort_by_desc(self):
        """Test sort_by_desc."""
        col = Collection([{"name": "Charlie"}, {"name": "Alice"}, {"name": "Bob"}])

        result = col.sort_by_desc("name")

        assert result.nth(0)["name"] == "Charlie"
        assert result.nth(1)["name"] == "Bob"
        assert result.nth(2)["name"] == "Alice"


class TestCollectionAggregates:
    """Test Collection aggregate methods."""

    def test_sum(self):
        """Test sum."""
        col = Collection([{"value": 10}, {"value": 20}, {"value": 30}])

        result = col.sum("value")

        assert result == 60

    def test_avg(self):
        """Test avg."""
        col = Collection([{"value": 10}, {"value": 20}, {"value": 30}])

        result = col.avg("value")

        assert result == 20.0

    def test_max(self):
        """Test max."""
        col = Collection([{"value": 10}, {"value": 30}, {"value": 20}])

        result = col.max("value")

        assert result == 30

    def test_min(self):
        """Test min."""
        col = Collection([{"value": 10}, {"value": 30}, {"value": 20}])

        result = col.min("value")

        assert result == 10


class TestCollectionIteration:
    """Test Collection iteration methods."""

    def test_each(self):
        """Test each."""
        col = Collection([1, 2, 3])
        result = []

        col.each(lambda x: result.append(x * 2))

        assert result == [2, 4, 6]

    def test_chunk(self):
        """Test chunk."""
        col = Collection([1, 2, 3, 4, 5])

        chunks = list(col.chunk(2))

        assert len(chunks) == 3
        assert list(chunks[0]) == [1, 2]
        assert list(chunks[1]) == [3, 4]
        assert list(chunks[2]) == [5]
