"""Unit tests covering uncovered Collection paths:
- first/last with callback
- unique with key
- sort_by with dict items and callable key
- sum/avg/max/min on empty collection
- map_async / each_async
- __getitem__ slice, __str__
"""
import pytest
from pyloquent.orm.collection import Collection


class Item:
    def __init__(self, name, score):
        self.name = name
        self.score = score

    def __repr__(self):
        return f"Item({self.name!r}, {self.score})"


def items(*pairs):
    return Collection([Item(n, s) for n, s in pairs])


# ---------------------------------------------------------------------------
# first / last with callback
# ---------------------------------------------------------------------------

def test_first_with_callback_match():
    c = items(("a", 1), ("b", 2), ("c", 3))
    result = c.first(lambda i: i.score > 1)
    assert result.name == "b"


def test_first_with_callback_no_match():
    c = items(("a", 1), ("b", 2))
    result = c.first(lambda i: i.score > 99)
    assert result is None


def test_last_with_callback_match():
    c = items(("a", 1), ("b", 2), ("c", 3))
    result = c.last(lambda i: i.score < 3)
    assert result.name == "b"


def test_last_with_callback_no_match():
    c = items(("a", 1), ("b", 2))
    result = c.last(lambda i: i.score > 99)
    assert result is None


# ---------------------------------------------------------------------------
# unique with key on dict items
# ---------------------------------------------------------------------------

def test_unique_with_key_on_dicts():
    c = Collection([{"tag": "a"}, {"tag": "b"}, {"tag": "a"}])
    result = c.unique("tag")
    assert len(result) == 2


def test_unique_with_list_value():
    c = Collection([[1, 2], [1, 2], [3, 4]])
    result = c.unique()
    assert len(result) == 2


# ---------------------------------------------------------------------------
# sort_by with dict items and callable key
# ---------------------------------------------------------------------------

def test_sort_by_dict_items():
    c = Collection([{"v": 3}, {"v": 1}, {"v": 2}])
    result = c.sort_by("v")
    assert result.pluck("v") == [1, 2, 3]


def test_sort_by_callable_key():
    c = items(("c", 3), ("a", 1), ("b", 2))
    result = c.sort_by(lambda i: i.score)
    assert [i.name for i in result] == ["a", "b", "c"]


def test_sort_by_callable_descending():
    c = items(("c", 3), ("a", 1), ("b", 2))
    result = c.sort_by(lambda i: i.score, descending=True)
    assert [i.name for i in result] == ["c", "b", "a"]


# ---------------------------------------------------------------------------
# sum / avg / max / min on empty
# ---------------------------------------------------------------------------

def test_sum_empty():
    c = items()
    assert c.sum("score") == 0


def test_avg_empty():
    c = items()
    assert c.avg("score") == 0.0


def test_max_empty():
    c = items()
    assert c.max("score") is None


def test_min_empty():
    c = items()
    assert c.min("score") is None


# ---------------------------------------------------------------------------
# sum/avg/max/min with None values
# ---------------------------------------------------------------------------

def test_sum_filters_none():
    c = Collection([{"v": 1}, {"v": None}, {"v": 2}])
    assert c.sum("v") == 3


def test_avg_filters_none():
    c = Collection([{"v": 4}, {"v": None}, {"v": 6}])
    assert c.avg("v") == 5.0


# ---------------------------------------------------------------------------
# map_async / each_async
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_map_async():
    c = items(("a", 1), ("b", 2))

    async def double_score(item):
        return item.score * 2

    result = await c.map_async(double_score)
    assert list(result) == [2, 4]


@pytest.mark.asyncio
async def test_each_async():
    seen = []
    c = items(("x", 10), ("y", 20))

    async def record(item):
        seen.append(item.name)

    returned = await c.each_async(record)
    assert seen == ["x", "y"]
    assert returned is c


# ---------------------------------------------------------------------------
# __getitem__ slice, __str__
# ---------------------------------------------------------------------------

def test_getitem_slice_returns_collection():
    c = items(("a", 1), ("b", 2), ("c", 3))
    sliced = c[0:2]
    assert isinstance(sliced, Collection)
    assert len(sliced) == 2


def test_str_representation():
    c = Collection([1, 2, 3])
    assert str(c) == str([1, 2, 3])


# ---------------------------------------------------------------------------
# sort_by_desc (extended)
# ---------------------------------------------------------------------------

def test_sort_by_desc_extended():
    c = items(("a", 1), ("b", 3), ("c", 2))
    result = c.sort_by_desc(lambda i: i.score)
    assert [i.score for i in result] == [3, 2, 1]


# ---------------------------------------------------------------------------
# where with dict items
# ---------------------------------------------------------------------------

def test_where_dict_items():
    c = Collection([{"x": 1}, {"x": 2}, {"x": 3}])
    result = c.where("x", ">", 1)
    assert len(result) == 2


def test_where_dict_items_two_arg():
    c = Collection([{"x": 1}, {"x": 2}, {"x": 2}])
    result = c.where("x", 2)
    assert len(result) == 2
