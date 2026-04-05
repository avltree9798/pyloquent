"""Unit tests for exception classes."""
import pytest
from pyloquent.exceptions import (
    MassAssignmentException,
    ModelNotFoundException,
    PyloquentException,
    QueryException,
    RelationNotFoundException,
)


class TestQueryException:
    def test_message_only(self):
        exc = QueryException("bad sql")
        assert str(exc) == "bad sql"
        assert exc.sql == ""
        assert exc.bindings == []

    def test_with_sql_and_bindings(self):
        exc = QueryException("failed", sql="SELECT 1", bindings=[1, 2])
        assert exc.sql == "SELECT 1"
        assert exc.bindings == [1, 2]

    def test_bindings_default_empty_list(self):
        exc = QueryException("msg", sql="SELECT 1")
        assert exc.bindings == []

    def test_is_pyloquent_exception(self):
        assert isinstance(QueryException("x"), PyloquentException)


class TestModelNotFoundException:
    def test_without_identifier(self):
        class User:
            __name__ = "User"
        exc = ModelNotFoundException(User)
        assert "User" in str(exc)
        assert exc.identifier is None

    def test_with_identifier(self):
        class Post:
            __name__ = "Post"
        exc = ModelNotFoundException(Post, 42)
        assert "42" in str(exc)
        assert exc.identifier == 42

    def test_model_class_stored(self):
        class Foo:
            __name__ = "Foo"
        exc = ModelNotFoundException(Foo, 99)
        assert exc.model_class is Foo

    def test_is_pyloquent_exception(self):
        class M:
            __name__ = "M"
        assert isinstance(ModelNotFoundException(M), PyloquentException)


class TestRelationNotFoundException:
    def test_message(self):
        class User:
            __name__ = "User"
        exc = RelationNotFoundException(User, "posts")
        assert "posts" in str(exc)
        assert "User" in str(exc)

    def test_attributes(self):
        class Tag:
            __name__ = "Tag"
        exc = RelationNotFoundException(Tag, "images")
        assert exc.model_class is Tag
        assert exc.relation == "images"

    def test_is_pyloquent_exception(self):
        class M:
            __name__ = "M"
        assert isinstance(RelationNotFoundException(M, "r"), PyloquentException)


class TestMassAssignmentException:
    def test_message(self):
        class User:
            __name__ = "User"
        exc = MassAssignmentException("is_admin", User)
        assert "is_admin" in str(exc)
        assert "User" in str(exc)

    def test_attributes(self):
        class Role:
            __name__ = "Role"
        exc = MassAssignmentException("permissions", Role)
        assert exc.key == "permissions"
        assert exc.model_class is Role

    def test_is_pyloquent_exception(self):
        class M:
            __name__ = "M"
        assert isinstance(MassAssignmentException("k", M), PyloquentException)
