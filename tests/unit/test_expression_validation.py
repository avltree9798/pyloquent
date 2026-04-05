"""Unit tests for expression dataclass validation edge cases."""
import pytest
from pyloquent.query.expression import WhereClause, OrderClause, Aggregate


def test_where_clause_raises_without_operator():
    with pytest.raises(ValueError):
        WhereClause(type="basic", column="x", operator=None, value=1)


def test_order_clause_raises_on_invalid_direction():
    with pytest.raises(ValueError):
        OrderClause(column="x", direction="sideways")


def test_aggregate_raises_on_invalid_function():
    with pytest.raises(ValueError):
        Aggregate(function="median", column="x")
