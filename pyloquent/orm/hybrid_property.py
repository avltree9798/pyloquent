"""Hybrid property descriptor for Pyloquent models.

A hybrid property behaves like a regular Python property when accessed on a model
instance, but can also expose a SQL expression when accessed at the class level
for use in QueryBuilder conditions.

Example::

    from pyloquent.orm.hybrid_property import hybrid_property
    from pyloquent.query.expression import RawExpression

    class User(Model):
        first_name: str
        last_name: str

        @hybrid_property
        def full_name(self) -> str:
            return f"{self.first_name} {self.last_name}"

        @full_name.expression
        @classmethod
        def full_name(cls) -> RawExpression:
            from pyloquent.query.expression import RawExpression
            return RawExpression("first_name || ' ' || last_name")

    # Instance access
    user = User(first_name='Jane', last_name='Doe')
    print(user.full_name)  # "Jane Doe"

    # Class-level expression (in raw WHERE / SELECT)
    sql_expr = User.full_name  # RawExpression("first_name || ' ' || last_name")
"""

from typing import Any, Callable, Generic, Optional, Type, TypeVar, overload

T = TypeVar("T")
R = TypeVar("R")


class hybrid_property(Generic[T, R]):
    """Descriptor that provides both instance-level and class-level behaviour.

    When accessed on an *instance*, calls the decorated instance method.
    When accessed on the *class*, calls the expression method (if defined),
    or raises ``AttributeError`` if no expression has been registered.

    Args:
        fget: The instance-level getter function.
    """

    def __init__(self, fget: Callable[[T], R]) -> None:
        """Initialise the hybrid property.

        Args:
            fget: Instance getter callable.
        """
        self._fget = fget
        self._expr: Optional[Callable[[Type[T]], Any]] = None
        self.__doc__ = fget.__doc__

    def expression(self, expr: Callable[[Type[T]], Any]) -> "hybrid_property[T, R]":
        """Register a class-level SQL expression factory.

        The decorated callable receives the *class* (not an instance) and should
        return a :class:`~pyloquent.query.expression.RawExpression` or any value
        understood by the grammar.

        Args:
            expr: Class method that returns the SQL expression.

        Returns:
            Self, so the decorator can be chained.

        Example::

            @full_name.expression
            @classmethod
            def full_name(cls):
                from pyloquent.query.expression import RawExpression
                return RawExpression("first_name || ' ' || last_name")
        """
        # Accept either a regular function or a classmethod descriptor
        if isinstance(expr, classmethod):
            self._expr = expr.__func__  # type: ignore[union-attr]
        else:
            self._expr = expr
        return self

    @overload
    def __get__(self, obj: None, objtype: Type[T]) -> Any: ...

    @overload
    def __get__(self, obj: T, objtype: Optional[Type[T]] = None) -> R: ...

    def __get__(self, obj: Optional[T], objtype: Optional[Type[T]] = None) -> Any:
        """Descriptor protocol — dispatch to instance getter or class expression.

        Args:
            obj: The model instance, or ``None`` when accessed on the class.
            objtype: The model class.

        Returns:
            Instance value when ``obj`` is not ``None``, otherwise the SQL expression.

        Raises:
            AttributeError: If accessed at class level and no expression is registered.
        """
        if obj is None:
            # Class-level access
            if self._expr is not None:
                return self._expr(objtype)
            return self  # Return the descriptor itself as fallback
        return self._fget(obj)
