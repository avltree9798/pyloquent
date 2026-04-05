"""Extended tests for all new Collection methods."""

import json
import pytest
from pyloquent.orm.collection import Collection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _Obj:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


# ---------------------------------------------------------------------------
# Presence / Membership
# ---------------------------------------------------------------------------

class TestIsEmpty:
    def test_empty(self):
        assert Collection().is_empty()

    def test_not_empty(self):
        assert not Collection([1]).is_empty()

    def test_is_not_empty_true(self):
        assert Collection([1]).is_not_empty()

    def test_is_not_empty_false(self):
        assert not Collection().is_not_empty()


class TestContains:
    def test_callable_truthy(self):
        assert Collection([1, 2, 3]).contains(lambda x: x == 2)

    def test_callable_falsy(self):
        assert not Collection([1, 2, 3]).contains(lambda x: x == 9)

    def test_value_present(self):
        assert Collection([1, 2, 3]).contains(2)

    def test_value_absent(self):
        assert not Collection([1, 2, 3]).contains(9)

    def test_key_value_dict(self):
        col = Collection([{"name": "Alice"}, {"name": "Bob"}])
        assert col.contains("name", "Alice")
        assert not col.contains("name", "Charlie")

    def test_key_value_object(self):
        col = Collection([_Obj(name="Alice"), _Obj(name="Bob")])
        assert col.contains("name", "Alice")
        assert not col.contains("name", "Charlie")

    def test_doesnt_contain_absent(self):
        assert Collection([1, 2]).doesnt_contain(5)

    def test_doesnt_contain_present(self):
        assert not Collection([1, 2]).doesnt_contain(1)


class TestFirstWhere:
    def test_equals_shorthand(self):
        col = Collection([{"age": 10}, {"age": 20}])
        assert col.first_where("age", 20)["age"] == 20

    def test_equals_explicit(self):
        col = Collection([{"age": 10}, {"age": 20}])
        assert col.first_where("age", "=", 20)["age"] == 20

    def test_double_equals(self):
        col = Collection([{"age": 10}, {"age": 20}])
        assert col.first_where("age", "==", 20)["age"] == 20

    def test_not_equals(self):
        col = Collection([{"age": 10}, {"age": 20}])
        assert col.first_where("age", "!=", 10)["age"] == 20

    def test_greater_than(self):
        col = Collection([{"age": 10}, {"age": 20}])
        assert col.first_where("age", ">", 15)["age"] == 20

    def test_greater_than_or_equal(self):
        col = Collection([{"age": 10}, {"age": 20}])
        assert col.first_where("age", ">=", 20)["age"] == 20

    def test_less_than(self):
        col = Collection([{"age": 10}, {"age": 20}])
        assert col.first_where("age", "<", 15)["age"] == 10

    def test_less_than_or_equal(self):
        col = Collection([{"age": 10}, {"age": 20}])
        assert col.first_where("age", "<=", 10)["age"] == 10

    def test_not_found(self):
        assert Collection([{"age": 10}]).first_where("age", 99) is None

    def test_object_attribute(self):
        col = Collection([_Obj(age=5), _Obj(age=10)])
        assert col.first_where("age", 10).age == 10


class TestSole:
    def test_exactly_one(self):
        assert Collection([42]).sole() == 42

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="empty"):
            Collection().sole()

    def test_multiple_raises(self):
        with pytest.raises(ValueError):
            Collection([1, 2]).sole()


# ---------------------------------------------------------------------------
# Set Operations
# ---------------------------------------------------------------------------

class TestDiff:
    def test_removes_matching(self):
        result = Collection([1, 2, 3, 4]).diff([2, 4])
        assert list(result) == [1, 3]

    def test_empty_diff(self):
        result = Collection([1, 2]).diff([])
        assert list(result) == [1, 2]


class TestIntersect:
    def test_common_items(self):
        result = Collection([1, 2, 3, 4]).intersect([2, 4, 6])
        assert list(result) == [2, 4]

    def test_no_overlap(self):
        result = Collection([1, 2]).intersect([3, 4])
        assert list(result) == []


class TestUnique:
    def test_without_key(self):
        result = Collection([1, 2, 2, 3, 3, 3]).unique()
        assert list(result) == [1, 2, 3]

    def test_with_key_dict(self):
        col = Collection([{"id": 1, "x": "a"}, {"id": 2, "x": "b"}, {"id": 1, "x": "c"}])
        result = col.unique("id")
        assert len(result) == 2
        assert result[0]["x"] == "a"

    def test_with_key_object(self):
        col = Collection([_Obj(id=1), _Obj(id=2), _Obj(id=1)])
        result = col.unique("id")
        assert len(result) == 2


class TestDuplicates:
    def test_without_key(self):
        result = Collection([1, 2, 2, 3]).duplicates()
        values = list(result)
        assert values.count(2) >= 1

    def test_with_key(self):
        col = Collection([{"k": "a"}, {"k": "b"}, {"k": "a"}])
        result = col.duplicates("k")
        assert all(x["k"] == "a" for x in result)


# ---------------------------------------------------------------------------
# Merging / Combining
# ---------------------------------------------------------------------------

class TestMerge:
    def test_single(self):
        result = Collection([1, 2]).merge([3, 4])
        assert list(result) == [1, 2, 3, 4]

    def test_multiple(self):
        result = Collection([1]).merge([2], [3])
        assert list(result) == [1, 2, 3]

    def test_concat_alias(self):
        result = Collection([1]).concat([2, 3])
        assert list(result) == [1, 2, 3]


class TestZip:
    def test_zip(self):
        result = Collection([1, 2, 3]).zip(["a", "b", "c"])
        assert list(result) == [(1, "a"), (2, "b"), (3, "c")]


class TestCollapse:
    def test_lists_of_lists(self):
        result = Collection([[1, 2], [3, 4], [5]]).collapse()
        assert list(result) == [1, 2, 3, 4, 5]

    def test_mixed(self):
        result = Collection([1, [2, 3]]).collapse()
        assert list(result) == [1, 2, 3]

    def test_strings_not_collapsed(self):
        result = Collection(["ab", "cd"]).collapse()
        assert list(result) == ["ab", "cd"]


class TestFlatten:
    def test_deep(self):
        result = Collection([[1, [2, [3]]]]).flatten()
        assert list(result) == [1, 2, 3]

    def test_depth_1(self):
        result = Collection([[1, [2, 3]], [4]]).flatten(depth=1)
        assert list(result) == [1, [2, 3], 4]

    def test_strings_not_flattened(self):
        result = Collection([["ab", "cd"]]).flatten()
        assert list(result) == ["ab", "cd"]


# ---------------------------------------------------------------------------
# Grouping / Splitting
# ---------------------------------------------------------------------------

class TestGroupBy:
    def test_by_dict_key(self):
        col = Collection([{"t": "a", "v": 1}, {"t": "b", "v": 2}, {"t": "a", "v": 3}])
        groups = col.group_by("t")
        assert len(groups["a"]) == 2
        assert len(groups["b"]) == 1

    def test_by_callable(self):
        groups = Collection([1, 2, 3, 4]).group_by(lambda x: "even" if x % 2 == 0 else "odd")
        assert list(groups["even"]) == [2, 4]
        assert list(groups["odd"]) == [1, 3]

    def test_by_object_attr(self):
        col = Collection([_Obj(type="x"), _Obj(type="y"), _Obj(type="x")])
        groups = col.group_by("type")
        assert len(groups["x"]) == 2


class TestPartition:
    def test_even_odd(self):
        evens, odds = Collection([1, 2, 3, 4, 5]).partition(lambda x: x % 2 == 0)
        assert list(evens) == [2, 4]
        assert list(odds) == [1, 3, 5]

    def test_empty(self):
        a, b = Collection([]).partition(lambda x: x)
        assert len(a) == 0
        assert len(b) == 0


class TestSplit:
    def test_two_groups(self):
        chunks = Collection([1, 2, 3, 4, 5]).split(2)
        assert len(chunks) == 2
        assert list(chunks[0]) == [1, 2, 3]
        assert list(chunks[1]) == [4, 5]

    def test_single_group(self):
        chunks = Collection([1, 2, 3]).split(1)
        assert len(chunks) == 1


class TestSplice:
    def test_all_remaining(self):
        col = Collection([1, 2, 3, 4, 5])
        removed = col.splice(2)
        assert list(removed) == [3, 4, 5]
        assert list(col) == [1, 2]

    def test_with_count(self):
        col = Collection([1, 2, 3, 4, 5])
        removed = col.splice(1, 2)
        assert list(removed) == [2, 3]
        assert list(col) == [1, 4, 5]

    def test_with_replacement(self):
        col = Collection([1, 2, 3, 4, 5])
        removed = col.splice(1, 2, [10, 20])
        assert list(removed) == [2, 3]
        assert list(col) == [1, 10, 20, 4, 5]


# ---------------------------------------------------------------------------
# Transformations
# ---------------------------------------------------------------------------

class TestFlatMap:
    def test_returns_list(self):
        result = Collection([1, 2, 3]).flat_map(lambda x: [x, x * 10])
        assert list(result) == [1, 10, 2, 20, 3, 30]

    def test_returns_scalar(self):
        result = Collection([1, 2]).flat_map(lambda x: x * 2)
        assert list(result) == [2, 4]


class TestMapWithKeys:
    def test_basic(self):
        result = Collection([{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]).map_with_keys(
            lambda x: (x["id"], x["name"])
        )
        assert result == {1: "A", 2: "B"}


class TestMapInto:
    def test_instantiates_class(self):
        class Box:
            def __init__(self, val):
                self.val = val
        result = Collection([1, 2]).map_into(Box)
        assert all(isinstance(x, Box) for x in result)
        assert result[0].val == 1


class TestKeyBy:
    def test_string_key_dict(self):
        result = Collection([{"id": 1, "n": "A"}, {"id": 2, "n": "B"}]).key_by("id")
        assert result[1]["n"] == "A"
        assert result[2]["n"] == "B"

    def test_callable_key(self):
        result = Collection([{"id": 1}, {"id": 2}]).key_by(lambda x: x["id"] * 10)
        assert 10 in result
        assert 20 in result

    def test_object_attr(self):
        result = Collection([_Obj(id=5)]).key_by("id")
        assert 5 in result


# ---------------------------------------------------------------------------
# Reduction
# ---------------------------------------------------------------------------

class TestReduce:
    def test_sum(self):
        result = Collection([1, 2, 3, 4]).reduce(lambda carry, x: carry + x, 0)
        assert result == 10

    def test_with_initial(self):
        result = Collection([1, 2, 3]).reduce(lambda carry, x: carry * x, 1)
        assert result == 6


class TestCountBy:
    def test_no_callback(self):
        result = Collection(["a", "b", "a", "c", "a", "b"]).count_by()
        assert result == {"a": 3, "b": 2, "c": 1}

    def test_with_callback(self):
        result = Collection([1, 2, 3, 4, 5]).count_by(lambda x: "even" if x % 2 == 0 else "odd")
        assert result["even"] == 2
        assert result["odd"] == 3


class TestMedian:
    def test_odd_count(self):
        assert Collection([3, 1, 2]).median() == 2.0

    def test_even_count(self):
        assert Collection([1, 2, 3, 4]).median() == 2.5

    def test_with_key(self):
        col = Collection([{"v": 10}, {"v": 30}, {"v": 20}])
        assert col.median("v") == 20.0

    def test_empty(self):
        assert Collection().median() is None

    def test_with_key_empty_values(self):
        col = Collection([{"v": None}, {"v": None}])
        assert col.median("v") is None


class TestMode:
    def test_basic(self):
        assert Collection([1, 2, 2, 3]).mode() == 2

    def test_with_key(self):
        col = Collection([{"v": "a"}, {"v": "b"}, {"v": "a"}])
        assert col.mode("v") == "a"

    def test_empty(self):
        assert Collection().mode() is None


# ---------------------------------------------------------------------------
# Pipelines
# ---------------------------------------------------------------------------

class TestPipe:
    def test_returns_callback_result(self):
        assert Collection([1, 2, 3]).pipe(lambda c: sum(c)) == 6


class TestTap:
    def test_does_not_modify(self):
        side = []
        col = Collection([1, 2, 3])
        result = col.tap(lambda c: side.append(len(c)))
        assert result is col
        assert side == [3]


class TestWhen:
    def test_truthy_callback_applied(self):
        col = Collection([1, 2, 3])
        result = col.when(True, lambda c: c.filter(lambda x: x > 1))
        assert len(result) == 2

    def test_falsy_no_callback(self):
        col = Collection([1, 2, 3])
        result = col.when(False, lambda c: c.filter(lambda x: x > 1))
        assert result is col

    def test_falsy_with_default(self):
        col = Collection([1, 2, 3])
        result = col.when(
            False,
            lambda c: c.filter(lambda x: x > 1),
            lambda c: c.filter(lambda x: x < 2),
        )
        assert len(result) == 1

    def test_unless_falsy(self):
        col = Collection([1, 2, 3])
        result = col.unless(False, lambda c: c.filter(lambda x: x > 1))
        assert len(result) == 2

    def test_unless_truthy(self):
        col = Collection([1, 2, 3])
        result = col.unless(True, lambda c: c.filter(lambda x: x > 1))
        assert result is col


# ---------------------------------------------------------------------------
# Mutation
# ---------------------------------------------------------------------------

class TestMutation:
    def test_push_multiple(self):
        col = Collection([1, 2])
        result = col.push(3, 4)
        assert result is col
        assert list(col) == [1, 2, 3, 4]

    def test_prepend_multiple(self):
        col = Collection([3, 4])
        result = col.prepend(1, 2)
        assert result is col
        assert list(col) == [1, 2, 3, 4]

    def test_pop_returns_last(self):
        col = Collection([1, 2, 3])
        assert col.pop() == 3
        assert len(col) == 2

    def test_pop_empty(self):
        assert Collection().pop() is None

    def test_shift_returns_first(self):
        col = Collection([1, 2, 3])
        assert col.shift() == 1
        assert list(col) == [2, 3]

    def test_shift_empty(self):
        assert Collection().shift() is None

    def test_forget_valid_index(self):
        col = Collection([1, 2, 3])
        col.forget(1)
        assert list(col) == [1, 3]

    def test_forget_invalid_index(self):
        col = Collection([1, 2, 3])
        col.forget(99)
        assert len(col) == 3

    def test_shuffle_keeps_length(self):
        col = Collection(list(range(100)))
        col.shuffle()
        assert len(col) == 100

    def test_random_single(self):
        col = Collection([1, 2, 3])
        r = col.random()
        assert r in [1, 2, 3]

    def test_random_count(self):
        col = Collection([1, 2, 3, 4, 5])
        r = col.random(3)
        assert len(r) == 3

    def test_random_larger_than_collection(self):
        col = Collection([1, 2])
        r = col.random(10)
        assert len(r) == 2

    def test_pad_right(self):
        result = Collection([1, 2, 3]).pad(5, 0)
        assert list(result) == [1, 2, 3, 0, 0]

    def test_pad_left(self):
        result = Collection([1, 2, 3]).pad(-5, 0)
        assert list(result) == [0, 0, 1, 2, 3]

    def test_pad_no_change_needed(self):
        result = Collection([1, 2, 3]).pad(2, 0)
        assert list(result) == [1, 2, 3]


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class TestToArray:
    def test_plain_items(self):
        assert Collection([1, 2, 3]).to_array() == [1, 2, 3]

    def test_with_to_dict(self):
        obj = _Obj(x=1, y=2)
        assert Collection([obj]).to_array() == [{"x": 1, "y": 2}]

    def test_nested_collection(self):
        inner = Collection([1, 2])
        result = Collection([inner]).to_array()
        assert len(result) == 1


class TestToJson:
    def test_roundtrip(self):
        data = [{"a": 1}, {"b": 2}]
        assert json.loads(Collection(data).to_json()) == data


class TestOnly:
    def test_from_dicts(self):
        col = Collection([{"a": 1, "b": 2, "c": 3}])
        result = col.only("a", "c")
        assert result[0] == {"a": 1, "c": 3}

    def test_from_objects(self):
        obj = _Obj(a=1, b=2)
        result = Collection([obj]).only("a")
        assert result[0] == {"a": 1}


class TestExcept:
    def test_from_dicts(self):
        col = Collection([{"a": 1, "b": 2, "c": 3}])
        result = col.except_("b")
        assert result[0] == {"a": 1, "c": 3}

    def test_from_objects_with_to_dict(self):
        obj = _Obj(a=1, b=2)
        result = Collection([obj]).except_("b")
        assert "b" not in result[0]


class TestWhereNotIn:
    def test_filters_correctly(self):
        col = Collection([{"id": 1}, {"id": 2}, {"id": 3}])
        result = col.where_not_in("id", [1, 3])
        assert len(result) == 1
        assert result[0]["id"] == 2


class TestTake:
    def test_positive(self):
        assert list(Collection([1, 2, 3, 4, 5]).take(3)) == [1, 2, 3]

    def test_negative(self):
        assert list(Collection([1, 2, 3, 4, 5]).take(-2)) == [4, 5]


class TestSkip:
    def test_skip(self):
        assert list(Collection([1, 2, 3, 4, 5]).skip(2)) == [3, 4, 5]


class TestTakeWhile:
    def test_stops_at_false(self):
        assert list(Collection([1, 2, 3, 4, 5]).take_while(lambda x: x < 4)) == [1, 2, 3]


class TestSkipWhile:
    def test_skips_until_false(self):
        assert list(Collection([1, 2, 3, 4, 5]).skip_while(lambda x: x < 3)) == [3, 4, 5]


class TestSortBy:
    def test_callable(self):
        result = Collection([3, 1, 2]).sort_by(lambda x: -x)
        assert list(result) == [3, 2, 1]

    def test_key_desc(self):
        result = Collection([{"v": 1}, {"v": 3}, {"v": 2}]).sort_by("v", descending=True)
        assert [x["v"] for x in result] == [3, 2, 1]

    def test_sort_by_desc(self):
        result = Collection([{"v": 1}, {"v": 3}, {"v": 2}]).sort_by_desc("v")
        assert [x["v"] for x in result] == [3, 2, 1]
