"""Query builder for constructing SQL queries fluently."""

from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Callable,
    Coroutine,
    Dict,
    Generic,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from pyloquent.exceptions import QueryException
from pyloquent.query.expression import (
    Aggregate,
    HavingClause,
    JoinClause,
    JoinCondition,
    OrderClause,
    RawExpression,
    WhereClause,
)

if TYPE_CHECKING:  # pragma: no cover
    from pyloquent.database.connection import Connection
    from pyloquent.grammars.grammar import Grammar
    from pyloquent.orm.collection import Collection
    from pyloquent.orm.model import Model

T = TypeVar("T")
ModelType = TypeVar("ModelType", bound="Model")


class QueryBuilder(Generic[T]):
    """Query builder with synchronous state mutation and async execution.

    This class provides a fluent interface for building SQL queries.
    All chain methods return self synchronously, while terminator methods
    are async and execute the query.

    Example:
        users = await User.where('active', True) \\
            .order_by('created_at', 'desc') \\
            .limit(10) \\
            .get()
    """

    def __init__(
        self,
        grammar: "Grammar",
        connection: Optional["Connection"] = None,
        model_class: Optional[Type[ModelType]] = None,
    ):
        """Initialize the query builder.

        Args:
            grammar: The grammar instance for SQL compilation
            connection: Optional database connection for execution
            model_class: Optional model class for result hydration
        """
        self.grammar = grammar
        self.connection = connection
        self.model_class = model_class

        # Query state
        self._table: Optional[str] = None
        self._selects: List[Union[str, Dict[str, str]]] = []
        self._distinct: bool = False
        self._distinct_on: Optional[List[str]] = None
        self._wheres: List[WhereClause] = []
        self._joins: List[JoinClause] = []
        self._orders: List[OrderClause] = []
        self._groups: List[str] = []
        self._havings: List[HavingClause] = []
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None
        self._aggregate_data: Optional[Aggregate] = None

        # Eager loading
        self._eager_loads: List[str] = []

        # Global scopes
        self._scopes: Dict[str, Callable] = {}
        self._removed_scopes: List[str] = []

        # Caching
        self._cache_key: Optional[str] = None
        self._cache_ttl: Optional[int] = None
        self._cache_tags: List[str] = []

        # Bindings organised by type
        self._bindings: Dict[str, List[Any]] = {
            "select": [],
            "from": [],
            "join": [],
            "where": [],
            "having": [],
            "order": [],
        }

        # Locking
        self._lock: Optional[str] = None

    # ========================================================================
    # Table Selection
    # ========================================================================

    def from_(self, table: str) -> "QueryBuilder[T]":
        """Set the table to query from.

        Args:
            table: Table name

        Returns:
            Self for chaining
        """
        self._table = table
        return self

    def table(self, table: str) -> "QueryBuilder[T]":
        """Alias for from_.

        Args:
            table: Table name

        Returns:
            Self for chaining
        """
        return self.from_(table)

    # ========================================================================
    # Column Selection
    # ========================================================================

    def select(self, *columns: str) -> "QueryBuilder[T]":
        """Set the columns to select.

        Args:
            *columns: Column names to select

        Returns:
            Self for chaining
        """
        self._selects = list(columns)
        return self

    def add_select(self, *columns: str) -> "QueryBuilder[T]":
        """Add columns to the select clause.

        Args:
            *columns: Column names to add

        Returns:
            Self for chaining
        """
        self._selects.extend(columns)
        return self

    def select_raw(self, sql: str, bindings: Optional[List[Any]] = None) -> "QueryBuilder[T]":
        """Add a raw expression to the select clause.

        Args:
            sql: Raw SQL expression
            bindings: Optional bindings for the expression

        Returns:
            Self for chaining
        """
        self._selects.append(RawExpression(sql, bindings or []))
        if bindings:
            self._bindings["select"].extend(bindings)
        return self

    def distinct(self, *columns: str) -> "QueryBuilder[T]":
        """Set the query to return distinct results.

        Args:
            *columns: Optional columns for DISTINCT ON (PostgreSQL only)

        Returns:
            Self for chaining
        """
        self._distinct = True
        if columns:
            self._distinct_on = list(columns)
        return self

    # ========================================================================
    # WHERE Clauses
    # ========================================================================

    def where(
        self,
        column: Union[str, Callable[["QueryBuilder[T]"], None], dict],
        operator: Any = None,
        value: Any = None,
        boolean: str = "and",
    ) -> "QueryBuilder[T]":
        """Add a WHERE clause.

        Args:
            column: Column name, dict of conditions, or callback for nested where
            operator: Comparison operator or value (if column is a dict)
            value: Value to compare
            boolean: Boolean connector ('and' or 'or')

        Returns:
            Self for chaining

        Examples:
            query.where('age', '>', 18)
            query.where({'name': 'John', 'active': True})
            query.where(lambda q: q.where('a', 1).or_where('b', 2))
        """
        # Handle dict of conditions
        if isinstance(column, dict):
            return self._add_array_of_wheres(column, boolean)

        # Handle callback (nested where)
        if callable(column):
            return self._where_nested(column, boolean)

        # Handle 2-argument form (where('name', 'John') - implied =)
        if value is None and operator is not None:
            value = operator
            operator = "="

        if operator is None:
            raise ValueError("Operator is required for where clause")

        self._wheres.append(
            WhereClause(
                column=column,
                operator=operator,
                value=value,
                boolean=boolean,
                type="basic",
            )
        )

        return self

    def or_where(
        self,
        column: Union[str, Callable[["QueryBuilder[T]"], None]],
        operator: Any = None,
        value: Any = None,
    ) -> "QueryBuilder[T]":
        """Add an OR WHERE clause.

        Args:
            column: Column name or callback for nested where
            operator: Comparison operator or value
            value: Value to compare

        Returns:
            Self for chaining
        """
        return self.where(column, operator, value, boolean="or")

    def where_not(
        self, column: str, operator: Any = None, value: Any = None, boolean: str = "and"
    ) -> "QueryBuilder[T]":
        """Add a WHERE NOT clause.

        Args:
            column: Column name
            operator: Comparison operator or value
            value: Value to compare
            boolean: Boolean connector

        Returns:
            Self for chaining
        """
        # Handle 2-argument form
        if value is None and operator is not None:
            value = operator
            operator = "="

        if operator is None:
            raise ValueError("Operator is required for where_not clause")

        # Negate the operator
        negated_operators = {
            "=": "!=",
            "!=": "=",
            "<>": "=",
            ">": "<=",
            "<": ">=",
            ">=": "<",
            "<=": ">",
        }
        negated_operator = negated_operators.get(operator, f"NOT {operator}")

        return self.where(column, negated_operator, value, boolean)

    def where_in(
        self, column: str, values: List[Any], boolean: str = "and", not_in: bool = False
    ) -> "QueryBuilder[T]":
        """Add a WHERE IN clause.

        Args:
            column: Column name
            values: List of values
            boolean: Boolean connector
            not_in: Whether to use NOT IN instead of IN

        Returns:
            Self for chaining
        """
        clause_type = "not_in" if not_in else "in"
        self._wheres.append(
            WhereClause(column=column, value=values, boolean=boolean, type=clause_type)
        )
        return self

    def where_not_in(
        self, column: str, values: List[Any], boolean: str = "and"
    ) -> "QueryBuilder[T]":
        """Add a WHERE NOT IN clause.

        Args:
            column: Column name
            values: List of values
            boolean: Boolean connector

        Returns:
            Self for chaining
        """
        return self.where_in(column, values, boolean, not_in=True)

    def or_where_in(self, column: str, values: List[Any]) -> "QueryBuilder[T]":
        """Add an OR WHERE IN clause.

        Args:
            column: Column name
            values: List of values

        Returns:
            Self for chaining
        """
        return self.where_in(column, values, boolean="or")

    def or_where_not_in(self, column: str, values: List[Any]) -> "QueryBuilder[T]":
        """Add an OR WHERE NOT IN clause.

        Args:
            column: Column name
            values: List of values

        Returns:
            Self for chaining
        """
        return self.where_in(column, values, boolean="or", not_in=True)

    def where_between(
        self, column: str, values: Tuple[Any, Any], boolean: str = "and", not_between: bool = False
    ) -> "QueryBuilder[T]":
        """Add a WHERE BETWEEN clause.

        Args:
            column: Column name
            values: Tuple of (min, max) values
            boolean: Boolean connector
            not_between: Whether to use NOT BETWEEN

        Returns:
            Self for chaining
        """
        clause_type = "not_between" if not_between else "between"
        self._wheres.append(
            WhereClause(column=column, value=list(values), boolean=boolean, type=clause_type)
        )
        return self

    def where_not_between(
        self, column: str, values: Tuple[Any, Any], boolean: str = "and"
    ) -> "QueryBuilder[T]":
        """Add a WHERE NOT BETWEEN clause.

        Args:
            column: Column name
            values: Tuple of (min, max) values
            boolean: Boolean connector

        Returns:
            Self for chaining
        """
        return self.where_between(column, values, boolean, not_between=True)

    def where_null(
        self, column: str, boolean: str = "and", not_null: bool = False
    ) -> "QueryBuilder[T]":
        """Add a WHERE NULL clause.

        Args:
            column: Column name
            boolean: Boolean connector
            not_null: Whether to use IS NOT NULL

        Returns:
            Self for chaining
        """
        clause_type = "not_null" if not_null else "null"
        self._wheres.append(WhereClause(column=column, boolean=boolean, type=clause_type))
        return self

    def where_not_null(self, column: str, boolean: str = "and") -> "QueryBuilder[T]":
        """Add a WHERE NOT NULL clause.

        Args:
            column: Column name
            boolean: Boolean connector

        Returns:
            Self for chaining
        """
        return self.where_null(column, boolean, not_null=True)

    def or_where_null(self, column: str) -> "QueryBuilder[T]":
        """Add an OR WHERE NULL clause.

        Args:
            column: Column name

        Returns:
            Self for chaining
        """
        return self.where_null(column, boolean="or")

    def or_where_not_null(self, column: str) -> "QueryBuilder[T]":
        """Add an OR WHERE NOT NULL clause.

        Args:
            column: Column name

        Returns:
            Self for chaining
        """
        return self.where_null(column, boolean="or", not_null=True)

    def where_raw(
        self, sql: str, bindings: Optional[List[Any]] = None, boolean: str = "and"
    ) -> "QueryBuilder[T]":
        """Add a raw WHERE clause.

        Args:
            sql: Raw SQL string
            bindings: Optional bindings
            boolean: Boolean connector

        Returns:
            Self for chaining
        """
        self._wheres.append(
            WhereClause(column="", sql=sql, bindings=bindings or [], boolean=boolean, type="raw")
        )
        return self

    def or_where_raw(self, sql: str, bindings: Optional[List[Any]] = None) -> "QueryBuilder[T]":
        """Add an OR raw WHERE clause.

        Args:
            sql: Raw SQL string
            bindings: Optional bindings

        Returns:
            Self for chaining
        """
        return self.where_raw(sql, bindings, boolean="or")

    def where_column(
        self, first: str, operator: Any = None, second: str = None, boolean: str = "and"
    ) -> "QueryBuilder[T]":
        """Add a WHERE clause comparing two columns.

        Args:
            first: First column name
            operator: Comparison operator or second column
            second: Second column name
            boolean: Boolean connector

        Returns:
            Self for chaining
        """
        # Handle 2-argument form
        if second is None and operator is not None:
            second = operator
            operator = "="

        if operator is None:
            raise ValueError("Operator is required for where_column clause")

        # Treat this as a raw where since we're comparing columns
        first_wrapped = f'"{first}"'
        second_wrapped = f'"{second}"'
        sql = f"{first_wrapped} {operator} {second_wrapped}"

        return self.where_raw(sql, boolean=boolean)

    def _where_nested(
        self, callback: Callable[["QueryBuilder[T]"], None], boolean: str = "and"
    ) -> "QueryBuilder[T]":
        """Add a nested WHERE clause group.

        Args:
            callback: Callback that receives a query builder
            boolean: Boolean connector

        Returns:
            Self for chaining
        """
        # Create a nested query builder
        nested = QueryBuilder(self.grammar)
        nested._table = self._table

        # Execute callback to build nested query
        callback(nested)

        # Add as a nested where clause
        self._wheres.append(WhereClause(column="", boolean=boolean, type="nested", query=nested))

        return self

    def _add_array_of_wheres(self, columns: Dict[str, Any], boolean: str) -> "QueryBuilder[T]":
        """Add multiple where clauses from a dict.

        Args:
            columns: Dict of column names to values
            boolean: Boolean connector

        Returns:
            Self for chaining
        """
        return self._where_nested(
            lambda query: [query.where(col, "=", val) for col, val in columns.items()],
            boolean,
        )

    # ========================================================================
    # JOINs
    # ========================================================================

    def join(
        self,
        table: str,
        first: str,
        operator: str = None,
        second: str = None,
        type: str = "inner",
    ) -> "QueryBuilder[T]":
        """Add a JOIN clause.

        Args:
            table: Table to join
            first: First column or callback for advanced join
            operator: Comparison operator or second column
            second: Second column
            type: Join type (inner, left, right, cross)

        Returns:
            Self for chaining
        """
        # Handle 3-argument form (table, first, second) - implied =
        if second is None and operator is not None:
            second = operator
            operator = "="

        join = JoinClause(table=table, type=type)
        join.add_condition(first, operator, second)

        self._joins.append(join)
        return self

    def left_join(
        self, table: str, first: str, operator: str = None, second: str = None
    ) -> "QueryBuilder[T]":
        """Add a LEFT JOIN clause.

        Args:
            table: Table to join
            first: First column
            operator: Comparison operator or second column
            second: Second column

        Returns:
            Self for chaining
        """
        return self.join(table, first, operator, second, type="left")

    def right_join(
        self, table: str, first: str, operator: str = None, second: str = None
    ) -> "QueryBuilder[T]":
        """Add a RIGHT JOIN clause.

        Args:
            table: Table to join
            first: First column
            operator: Comparison operator or second column
            second: Second column

        Returns:
            Self for chaining
        """
        return self.join(table, first, operator, second, type="right")

    def cross_join(self, table: str) -> "QueryBuilder[T]":
        """Add a CROSS JOIN clause.

        Args:
            table: Table to join

        Returns:
            Self for chaining
        """
        self._joins.append(JoinClause(table=table, type="cross"))
        return self

    # ========================================================================
    # Scopes
    # ========================================================================

    def with_global_scope(self, name: str, callback: Callable) -> "QueryBuilder[T]":
        """Add a global scope to the query.

        Args:
            name: Scope name
            callback: Scope callback that receives the query builder

        Returns:
            Self for chaining
        """
        if name not in self._removed_scopes:
            self._scopes[name] = callback
        return self

    def without_global_scope(self, name: str) -> "QueryBuilder[T]":
        """Remove a global scope from the query.

        Args:
            name: Scope name to remove

        Returns:
            Self for chaining
        """
        if name in self._scopes:
            del self._scopes[name]
        self._removed_scopes.append(name)
        return self

    def without_global_scopes(self, names: List[str]) -> "QueryBuilder[T]":
        """Remove multiple global scopes from the query.

        Args:
            names: List of scope names to remove

        Returns:
            Self for chaining
        """
        for name in names:
            self.without_global_scope(name)
        return self

    def _apply_scopes(self) -> "QueryBuilder[T]":
        """Apply all global scopes to the query.

        Returns:
            Self for chaining
        """
        for name, callback in self._scopes.items():
            if name not in self._removed_scopes:
                callback(self)
        return self

    # ========================================================================
    # Caching
    # ========================================================================

    def cache(self, ttl: int = 3600, key: Optional[str] = None) -> "QueryBuilder[T]":
        """Enable caching for this query.

        Args:
            ttl: Time-to-live in seconds (default: 3600 = 1 hour)
            key: Optional custom cache key

        Returns:
            Self for chaining
        """
        self._cache_ttl = ttl

        if key:
            self._cache_key = key
        else:
            # Generate key from query state
            self._cache_key = self._generate_cache_key()

        return self

    def cache_forever(self, key: Optional[str] = None) -> "QueryBuilder[T]":
        """Cache the query result forever.

        Args:
            key: Optional custom cache key

        Returns:
            Self for chaining
        """
        return self.cache(ttl=None, key=key)

    def cache_tags(self, *tags: str) -> "QueryBuilder[T]":
        """Set cache tags for this query.

        Args:
            *tags: Cache tags

        Returns:
            Self for chaining
        """
        self._cache_tags = list(tags)
        return self

    def _generate_cache_key(self) -> str:
        """Generate a cache key from the current query state.

        Returns:
            Cache key string
        """
        from pyloquent.cache.cache_manager import CacheManager

        # Apply scopes to ensure key reflects final query
        self._apply_scopes()

        # Get SQL and bindings
        sql, bindings = self.grammar.compile_select(self)

        return CacheManager.query_key(sql, bindings)

    async def _get_cached_or_execute(self) -> "Collection[T]":
        """Get cached results or execute the query.

        Returns:
            Collection of results
        """
        from pyloquent.cache.cache_manager import CacheManager

        if self._cache_ttl is None and not self._cache_key:  # pragma: no cover
            # Caching not enabled, execute normally
            return await self._execute_get()  # pragma: no cover

        cache = CacheManager.get_store()
        if cache is None:
            # No cache store configured, execute normally
            return await self._execute_get()

        cache_key = self._cache_key or self._generate_cache_key()

        # Try to get from cache
        cached = await cache.get(cache_key)
        if cached is not None:
            return cached

        # Execute and cache
        results = await self._execute_get()

        # Store in cache
        await cache.put(cache_key, results, self._cache_ttl)

        return results

    async def _execute_get(self) -> "Collection[T]":
        """Execute the query without caching.

        Returns:
            Collection of results
        """
        self._apply_scopes()

        sql, bindings = self.grammar.compile_select(self)

        if not self.connection:
            raise QueryException("No database connection available")

        results = await self.connection.fetch_all(sql, bindings)

        # Hydrate results if model class is set
        if self.model_class:
            models = self._hydrate_models(results)

            # Eager load relations if specified
            if self._eager_loads:
                await self._eager_load_relations(models)

            return models

        from pyloquent.orm.collection import Collection

        return Collection(results)

    # ========================================================================
    # Ordering, Grouping, Limiting
    # ========================================================================

    def order_by(self, column: str, direction: str = "asc") -> "QueryBuilder[T]":
        """Add an ORDER BY clause.

        Args:
            column: Column name
            direction: Sort direction ('asc' or 'desc')

        Returns:
            Self for chaining
        """
        self._orders.append(OrderClause(column=column, direction=direction))
        return self

    def order_by_desc(self, column: str) -> "QueryBuilder[T]":
        """Add a descending ORDER BY clause.

        Args:
            column: Column name

        Returns:
            Self for chaining
        """
        return self.order_by(column, "desc")

    def latest(self, column: str = "created_at") -> "QueryBuilder[T]":
        """Order by the given column in descending order.

        Args:
            column: Column name (default: created_at)

        Returns:
            Self for chaining
        """
        return self.order_by_desc(column)

    def oldest(self, column: str = "created_at") -> "QueryBuilder[T]":
        """Order by the given column in ascending order.

        Args:
            column: Column name (default: created_at)

        Returns:
            Self for chaining
        """
        return self.order_by(column, "asc")

    def reorder(self, column: Optional[str] = None, direction: str = "asc") -> "QueryBuilder[T]":
        """Remove all existing orders and optionally add a new one.

        Args:
            column: Optional new column to order by
            direction: Sort direction

        Returns:
            Self for chaining
        """
        self._orders = []
        if column:
            self.order_by(column, direction)
        return self

    def group_by(self, *columns: str) -> "QueryBuilder[T]":
        """Add GROUP BY clause(s).

        Args:
            *columns: Column names to group by

        Returns:
            Self for chaining
        """
        self._groups.extend(columns)
        return self

    def having(
        self, column: str, operator: Any, value: Any = None, boolean: str = "and"
    ) -> "QueryBuilder[T]":
        """Add a HAVING clause.

        Args:
            column: Column name
            operator: Comparison operator or value
            value: Value to compare
            boolean: Boolean connector

        Returns:
            Self for chaining
        """
        # Handle 2-argument form
        if value is None and operator is not None:
            value = operator
            operator = "="

        self._havings.append(
            HavingClause(column=column, operator=operator, value=value, boolean=boolean)
        )
        return self

    def or_having(self, column: str, operator: Any, value: Any = None) -> "QueryBuilder[T]":
        """Add an OR HAVING clause.

        Args:
            column: Column name
            operator: Comparison operator or value
            value: Value to compare

        Returns:
            Self for chaining
        """
        return self.having(column, operator, value, boolean="or")

    def limit(self, value: int) -> "QueryBuilder[T]":
        """Set the LIMIT.

        Args:
            value: Maximum number of rows to return

        Returns:
            Self for chaining
        """
        if value < 0:
            raise ValueError("Limit cannot be negative")
        self._limit = value
        return self

    def offset(self, value: int) -> "QueryBuilder[T]":
        """Set the OFFSET.

        Args:
            value: Number of rows to skip

        Returns:
            Self for chaining
        """
        if value < 0:
            raise ValueError("Offset cannot be negative")
        self._offset = value
        return self

    def for_page(self, page: int, per_page: int = 15) -> "QueryBuilder[T]":
        """Set the offset and limit for pagination.

        Args:
            page: Page number (1-indexed)
            per_page: Number of items per page

        Returns:
            Self for chaining
        """
        if page < 1:
            raise ValueError("Page must be >= 1")
        return self.offset((page - 1) * per_page).limit(per_page)

    def take(self, limit: int) -> "QueryBuilder[T]":
        """Alias for limit.

        Args:
            limit: Maximum number of rows

        Returns:
            Self for chaining
        """
        return self.limit(limit)

    def skip(self, offset: int) -> "QueryBuilder[T]":
        """Alias for offset.

        Args:
            offset: Number of rows to skip

        Returns:
            Self for chaining
        """
        return self.offset(offset)

    # ========================================================================
    # Eager Loading
    # ========================================================================

    def with_(self, *relations: str) -> "QueryBuilder[T]":
        """Eager load relations.

        Args:
            *relations: Relation names to eager load

        Returns:
            Self for chaining
        """
        self._eager_loads.extend(relations)
        return self

    def with_count(self, *relations: str) -> "QueryBuilder[T]":
        """Add relationship count columns to the query.

        This adds a subquery select for each relation count.

        Args:
            *relations: Relation names to count

        Returns:
            Self for chaining

        Example:
            users = await User.with_count('posts', 'comments').get()
            print(user.posts_count)  # Access the count
        """
        for relation in relations:
            self._add_relation_count(relation)

        return self

    def _add_relation_count(self, relation: str) -> None:
        """Add a relation count subquery to the select.

        Args:
            relation: Relation name
        """
        if not self.model_class:
            return

        column_alias = f"{relation}_count"

        # Ensure we still select all model columns if no selects set yet
        if not self._selects:
            self._selects.append(RawExpression(f"{self._table}.*" if self._table else "*"))

        try:
            temp = self.model_class.model_construct()
            rel_method = getattr(temp, relation, None)
            if rel_method is not None and callable(rel_method):
                rel_instance = rel_method()
                parent_table = self._table or getattr(self.model_class, "__table__", None)
                related_class = rel_instance.related
                related_table = getattr(related_class, "__table__", None) or related_class._get_default_table_name()

                from pyloquent.orm.relations.has_many import HasMany
                from pyloquent.orm.relations.has_one import HasOne
                from pyloquent.orm.relations.belongs_to import BelongsTo
                from pyloquent.orm.relations.belongs_to_many import BelongsToMany

                if isinstance(rel_instance, (HasMany, HasOne)):
                    fk = rel_instance.foreign_key
                    lk = rel_instance.local_key
                    subquery = f'(SELECT COUNT(*) FROM "{related_table}" WHERE "{related_table}"."{fk}" = "{parent_table}"."{lk}")'
                elif isinstance(rel_instance, BelongsTo):
                    fk = rel_instance.foreign_key
                    ok = rel_instance.owner_key
                    subquery = f'(SELECT COUNT(*) FROM "{related_table}" WHERE "{related_table}"."{ok}" = "{parent_table}"."{fk}")'
                elif isinstance(rel_instance, BelongsToMany):
                    pivot = rel_instance.table
                    fpk = rel_instance.foreign_pivot_key
                    pk = rel_instance.parent_key
                    subquery = f'(SELECT COUNT(*) FROM "{pivot}" WHERE "{pivot}"."{fpk}" = "{parent_table}"."{pk}")'
                else:
                    subquery = f'(SELECT COUNT(*) FROM "{related_table}" WHERE 1=1)'

                self._selects.append(RawExpression(f"{subquery} AS {column_alias}"))
                return
        except Exception:
            pass

        # Fallback
        self._selects.append(RawExpression(f"(SELECT 0) AS {column_alias}"))

    def has(self, relation: str, operator: str = ">=", count: int = 1) -> "QueryBuilder[T]":
        """Add a has relation constraint.

        Filters models that have at least the specified number of related models.

        Args:
            relation: Relation name
            operator: Comparison operator (default: >=)
            count: Count to compare against (default: 1)

        Returns:
            Self for chaining

        Example:
            users_with_posts = await User.has('posts').get()
            users_with_many_posts = await User.has('posts', '>=', 5).get()
        """
        return self._has_relation(relation, operator, count, boolean="and")

    def or_has(self, relation: str, operator: str = ">=", count: int = 1) -> "QueryBuilder[T]":
        """Add an or has relation constraint.

        Args:
            relation: Relation name
            operator: Comparison operator
            count: Count to compare against

        Returns:
            Self for chaining
        """
        return self._has_relation(relation, operator, count, boolean="or")

    def doesnt_have(self, relation: str) -> "QueryBuilder[T]":
        """Add a doesnt have relation constraint.

        Filters models that don't have any of the specified relation.

        Args:
            relation: Relation name

        Returns:
            Self for chaining

        Example:
            users_without_posts = await User.doesnt_have('posts').get()
        """
        return self._has_relation(relation, "<", 1, boolean="and")

    def or_doesnt_have(self, relation: str) -> "QueryBuilder[T]":
        """Add an or doesnt have relation constraint.

        Args:
            relation: Relation name

        Returns:
            Self for chaining
        """
        return self._has_relation(relation, "<", 1, boolean="or")

    def where_has(
        self,
        relation: str,
        callback: Optional[Callable[["QueryBuilder"], None]] = None,
        operator: str = ">=",
        count: int = 1,
    ) -> "QueryBuilder[T]":
        """Add a where has relation constraint with custom conditions.

        Filters models that have related models matching the given conditions.

        Args:
            relation: Relation name
            callback: Optional callback to constrain the relation query
            operator: Comparison operator
            count: Count to compare against

        Returns:
            Self for chaining

        Example:
            users = await User.where_has('posts', lambda q: q.where('published', True)).get()
        """
        return self._has_relation(relation, operator, count, boolean="and", callback=callback)

    def or_where_has(
        self,
        relation: str,
        callback: Optional[Callable[["QueryBuilder"], None]] = None,
        operator: str = ">=",
        count: int = 1,
    ) -> "QueryBuilder[T]":
        """Add an or where has relation constraint.

        Args:
            relation: Relation name
            callback: Optional callback to constrain the relation query
            operator: Comparison operator
            count: Count to compare against

        Returns:
            Self for chaining
        """
        return self._has_relation(relation, operator, count, boolean="or", callback=callback)

    def _has_relation(
        self,
        relation: str,
        operator: str,
        count: int,
        boolean: str = "and",
        callback: Optional[Callable[["QueryBuilder"], None]] = None,
    ) -> "QueryBuilder[T]":
        """Add a has relation constraint using a proper EXISTS subquery."""
        if self.model_class is not None:
            try:
                temp = self.model_class.model_construct()
                rel_method = getattr(temp, relation, None)
                if rel_method is not None and callable(rel_method):
                    rel_instance = rel_method()
                    parent_table = self._table or getattr(self.model_class, "__table__", None) or self.model_class._get_default_table_name()
                    related_class = rel_instance.related
                    related_table = getattr(related_class, "__table__", None) or related_class._get_default_table_name()

                    subquery = QueryBuilder(self.grammar, self.connection, related_class)
                    subquery._table = related_table

                    from pyloquent.orm.relations.has_many import HasMany
                    from pyloquent.orm.relations.has_one import HasOne
                    from pyloquent.orm.relations.belongs_to import BelongsTo
                    from pyloquent.orm.relations.belongs_to_many import BelongsToMany

                    if isinstance(rel_instance, (HasMany, HasOne)):
                        fk = rel_instance.foreign_key
                        lk = rel_instance.local_key
                        subquery.where_raw(f'"{related_table}"."{fk}" = "{parent_table}"."{lk}"')
                    elif isinstance(rel_instance, BelongsTo):
                        fk = rel_instance.foreign_key
                        ok = rel_instance.owner_key
                        subquery.where_raw(f'"{related_table}"."{ok}" = "{parent_table}"."{fk}"')
                    elif isinstance(rel_instance, BelongsToMany):
                        pivot = rel_instance.table
                        fpk = rel_instance.foreign_pivot_key
                        rpk = rel_instance.related_pivot_key
                        pk = rel_instance.parent_key
                        subquery.where_raw(f'"{pivot}"."{fpk}" = "{parent_table}"."{pk}"')
                        subquery._table = pivot

                    if callback is not None:
                        callback(subquery)

                    if operator == ">=" and count == 1:
                        self._wheres.append(WhereClause(
                            column="", boolean=boolean, type="exists", query=subquery
                        ))
                    else:
                        count_sub = subquery.clone()
                        count_sub._aggregate_data = Aggregate(function="count", column="*")
                        sub_sql, sub_bindings = self.grammar.compile_select(count_sub)
                        self._wheres.append(WhereClause(
                            column="", boolean=boolean, type="raw",
                            sql=f"({sub_sql}) {operator} {count}",
                            bindings=sub_bindings,
                        ))
                    return self
            except Exception:
                pass

        # Fallback when model_class is unknown
        self._wheres.append(
            WhereClause(column="1", operator="=", value=1, boolean=boolean, type="basic")
        )
        return self

    # ========================================================================
    # Aggregates
    # ========================================================================

    async def count(self, column: str = "*") -> int:
        """Count the number of rows.

        Args:
            column: Column to count (default: *)

        Returns:
            Row count
        """
        return await self._aggregate("count", column)

    async def max(self, column: str) -> Any:
        """Get the maximum value of a column.

        Args:
            column: Column name

        Returns:
            Maximum value
        """
        return await self._aggregate("max", column)

    async def min(self, column: str) -> Any:
        """Get the minimum value of a column.

        Args:
            column: Column name

        Returns:
            Minimum value
        """
        return await self._aggregate("min", column)

    async def sum(self, column: str) -> Any:
        """Get the sum of a column.

        Args:
            column: Column name

        Returns:
            Sum value (or 0 if no rows)
        """
        return await self._aggregate("sum", column)

    async def avg(self, column: str) -> Any:
        """Get the average value of a column.

        Args:
            column: Column name

        Returns:
            Average value
        """
        return await self._aggregate("avg", column)

    async def _aggregate(self, function: str, column: str) -> Any:
        """Execute an aggregate function.

        Args:
            function: Aggregate function name
            column: Column name

        Returns:
            Aggregate result
        """
        # Apply global scopes
        self._apply_scopes()

        # Store current state
        original_selects = self._selects
        original_aggregate = self._aggregate_data

        # Set aggregate
        self._aggregate_data = Aggregate(function=function, column=column)

        # Get SQL
        sql, bindings = self.grammar.compile_select(self)

        # Restore state
        self._selects = original_selects
        self._aggregate_data = original_aggregate

        # Execute
        if not self.connection:
            raise QueryException("No database connection available")

        result = await self.connection.fetch_one(sql, bindings)

        if result and "aggregate" in result:
            return result["aggregate"]
        return None

    # ========================================================================
    # Async Terminators
    # ========================================================================

    async def get(self) -> "Collection[T]":
        """Execute the query and return all results.

        Returns:
            Collection of model instances or dictionaries
        """
        # Check if caching is enabled
        if self._cache_ttl is not None or self._cache_key:
            return await self._get_cached_or_execute()

        return await self._execute_get()

    async def first(self) -> Optional[T]:
        """Execute the query and return the first result.

        Returns:
            First model instance/dict or None
        """
        # Apply global scopes
        self._apply_scopes()

        # Temporarily set limit to 1
        original_limit = self._limit
        self._limit = 1

        sql, bindings = self.grammar.compile_select(self)

        # Restore original limit
        self._limit = original_limit

        if not self.connection:
            raise QueryException("No database connection available")

        result = await self.connection.fetch_one(sql, bindings)

        if result is None:
            return None

        # Hydrate result if model class is set
        if self.model_class:
            model = self.model_class(**result)
            if hasattr(model, "_exists"):
                model._exists = True
            if hasattr(model, "_original"):
                model._original = result.copy()
            if hasattr(model, "_fire_event"):
                try:
                    import asyncio
                    coro = model._fire_event("retrieved")
                    if asyncio.iscoroutine(coro):
                        asyncio.ensure_future(coro)
                except Exception:
                    pass
            return model

        return result  # type: ignore

    async def first_or_fail(self) -> T:
        """Execute the query and return the first result or raise an exception.

        Returns:
            First model instance/dict

        Raises:
            ModelNotFoundException: If no results found
        """
        result = await self.first()
        if result is None:
            from pyloquent.exceptions import ModelNotFoundException
            from pyloquent.orm.model import Model

            if self.model_class and issubclass(self.model_class, Model):
                raise ModelNotFoundException(self.model_class)
            raise QueryException("No results found")
        return result

    async def find(self, id: Any) -> Optional[T]:
        """Find a record by primary key.

        Args:
            id: Primary key value

        Returns:
            Model instance/dict or None
        """
        return await self.where("id", id).first()

    async def find_or_fail(self, id: Any) -> T:
        """Find a record by primary key or raise an exception.

        Args:
            id: Primary key value

        Returns:
            Model instance/dict

        Raises:
            ModelNotFoundException: If not found
        """
        result = await self.find(id)
        if result is None:
            from pyloquent.exceptions import ModelNotFoundException
            from pyloquent.orm.model import Model

            if self.model_class and issubclass(self.model_class, Model):
                raise ModelNotFoundException(self.model_class, id)
            raise QueryException(f"Record with id {id} not found")
        return result

    async def pluck(self, column: str) -> List[Any]:
        """Get a list of a single column's values.

        Args:
            column: Column name

        Returns:
            List of values
        """
        # Store original model class
        original_model_class = self.model_class

        # Disable model hydration for pluck
        self.model_class = None

        # Apply scopes and compile
        self._apply_scopes()
        sql, bindings = self.grammar.compile_select(self)

        # Restore model class
        self.model_class = original_model_class

        if not self.connection:
            raise QueryException("No database connection available")

        results = await self.connection.fetch_all(sql, bindings)

        return [result.get(column) for result in results]

    async def value(self, column: str) -> Any:
        """Get a single column's value from the first result.

        Args:
            column: Column name

        Returns:
            Column value or None
        """
        result = await self.first()
        if result is None:
            return None
        if isinstance(result, dict):
            return result.get(column)
        return getattr(result, column, None)

    async def exists(self) -> bool:
        """Check if any records exist for the query.

        Returns:
            True if records exist
        """
        result = await self.count()
        return result > 0

    async def doesnt_exist(self) -> bool:
        """Check if no records exist for the query.

        Returns:
            True if no records exist
        """
        return not await self.exists()

    # ========================================================================
    # Insert / Update / Delete
    # ========================================================================

    async def insert(self, values: Union[Dict[str, Any], List[Dict[str, Any]]]) -> bool:
        """Insert records into the database.

        Args:
            values: Dictionary or list of dictionaries of column-value pairs

        Returns:
            True on success
        """
        if isinstance(values, dict):
            values = [values]

        if not values:
            raise ValueError("Cannot insert empty values")

        sql, bindings = self.grammar.compile_insert(self, values)

        if not self.connection:
            raise QueryException("No database connection available")

        await self.connection.execute(sql, bindings)
        return True

    async def insert_get_id(self, values: Dict[str, Any], sequence: str = "id") -> Any:
        """Insert a record and get the ID.

        Args:
            values: Dictionary of column-value pairs
            sequence: Name of the ID sequence column

        Returns:
            The inserted ID
        """
        sql, bindings = self.grammar.compile_insert_get_id(self, values, sequence)

        if not self.connection:
            raise QueryException("No database connection available")

        result = await self.connection.execute(sql, bindings)
        return result

    async def update(self, values: Dict[str, Any]) -> int:
        """Update records in the database.

        Args:
            values: Dictionary of column-value pairs to update

        Returns:
            Number of affected rows
        """
        if not self._wheres:
            raise QueryException(
                "Cannot update without WHERE clause (use update_all for mass updates)"
            )

        sql, bindings = self.grammar.compile_update(self, values)

        if not self.connection:
            raise QueryException("No database connection available")

        result = await self.connection.execute(sql, bindings)
        return result

    async def update_all(self, values: Dict[str, Any]) -> int:
        """Update all records in the table (without WHERE restriction).

        Args:
            values: Dictionary of column-value pairs to update

        Returns:
            Number of affected rows
        """
        sql, bindings = self.grammar.compile_update(self, values)

        if not self.connection:
            raise QueryException("No database connection available")

        result = await self.connection.execute(sql, bindings)
        return result

    async def delete(self) -> int:
        """Delete records from the database.

        Returns:
            Number of affected rows

        Raises:
            QueryException: If no WHERE clause is set
        """
        if not self._wheres:
            raise QueryException(
                "Cannot delete without WHERE clause (use delete_all for mass deletion)"
            )

        sql, bindings = self.grammar.compile_delete(self)

        if not self.connection:
            raise QueryException("No database connection available")

        result = await self.connection.execute(sql, bindings)
        return result

    async def delete_all(self) -> int:
        """Delete all records from the table (without WHERE restriction).

        Returns:
            Number of affected rows
        """
        sql, bindings = self.grammar.compile_delete(self)

        if not self.connection:
            raise QueryException("No database connection available")

        result = await self.connection.execute(sql, bindings)
        return result

    async def increment(self, column: str, amount: Union[int, float] = 1, extra: Optional[Dict[str, Any]] = None) -> int:
        """Atomically increment a column by the given amount.

        Args:
            column: Column to increment
            amount: Amount to increment by (default: 1)
            extra: Additional columns to update

        Returns:
            Number of affected rows
        """
        sql, bindings = self.grammar.compile_increment(self, column, amount, extra or {})
        if not self.connection:
            raise QueryException("No database connection available")
        return await self.connection.execute(sql, bindings)

    async def decrement(self, column: str, amount: Union[int, float] = 1, extra: Optional[Dict[str, Any]] = None) -> int:
        """Atomically decrement a column by the given amount.

        Args:
            column: Column to decrement
            amount: Amount to decrement by (default: 1)
            extra: Additional columns to update

        Returns:
            Number of affected rows
        """
        return await self.increment(column, -amount, extra)

    async def insert_or_ignore(self, values: Union[Dict[str, Any], List[Dict[str, Any]]]) -> bool:
        """Insert records, ignoring duplicates (INSERT OR IGNORE).

        Args:
            values: Dictionary or list of dictionaries

        Returns:
            True on success
        """
        if isinstance(values, dict):
            values = [values]
        sql, bindings = self.grammar.compile_insert_or_ignore(self, values)
        if not self.connection:
            raise QueryException("No database connection available")
        await self.connection.execute(sql, bindings)
        return True

    async def upsert(
        self,
        values: List[Dict[str, Any]],
        unique_by: Union[str, List[str]],
        update_columns: Optional[List[str]] = None,
    ) -> int:
        """Insert or update records (upsert).

        Args:
            values: List of row dictionaries
            unique_by: Column(s) that determine uniqueness
            update_columns: Columns to update on conflict (default: all non-unique columns)

        Returns:
            Number of affected rows
        """
        if isinstance(unique_by, str):
            unique_by = [unique_by]
        if update_columns is None and values:
            update_columns = [c for c in values[0].keys() if c not in unique_by]
        sql, bindings = self.grammar.compile_upsert(self, values, unique_by, update_columns or [])
        if not self.connection:
            raise QueryException("No database connection available")
        return await self.connection.execute(sql, bindings)

    async def update_or_insert(self, attributes: Dict[str, Any], values: Optional[Dict[str, Any]] = None) -> bool:
        """Insert or update a single record.

        Searches for a record matching attributes; updates it with values
        if found, or inserts attributes+values if not found.

        Args:
            attributes: Columns to search by
            values: Columns to update/insert

        Returns:
            True on success
        """
        query = self.clone()
        for col, val in attributes.items():
            query.where(col, val)
        existing = await query.first()
        all_values = {**attributes, **(values or {})}
        if existing is not None:
            await query.update(values or {})
        else:
            await self.insert(all_values)
        return True

    async def find_many(self, ids: List[Any], column: Optional[str] = None) -> "Collection[T]":
        """Find multiple records by primary key.

        Args:
            ids: List of primary key values
            column: Key column name (default: model pk or 'id')

        Returns:
            Collection of matching records
        """
        pk = column or (getattr(self.model_class, "__primary_key__", None) if self.model_class else None) or "id"
        return await self.where_in(pk, ids).get()

    def to_raw_sql(self) -> str:
        """Get the SQL string with bindings inlined (for debugging).

        Returns:
            SQL string with placeholder values substituted
        """
        sql, bindings = self.to_sql()
        for binding in bindings:
            if isinstance(binding, str):
                replacement = f"'{binding}'"
            elif binding is None:
                replacement = "NULL"
            elif isinstance(binding, bool):
                replacement = "1" if binding else "0"
            else:
                replacement = str(binding)
            sql = sql.replace("?", replacement, 1)
        return sql

    def where_exists(self, callback: Callable[["QueryBuilder"], None]) -> "QueryBuilder[T]":
        """Add a WHERE EXISTS subquery constraint.

        Args:
            callback: Callable that receives a QueryBuilder and adds constraints

        Returns:
            Self for chaining
        """
        subquery = QueryBuilder(self.grammar, self.connection)
        callback(subquery)
        self._wheres.append(WhereClause(column="", boolean="and", type="exists", query=subquery))
        return self

    def where_not_exists(self, callback: Callable[["QueryBuilder"], None]) -> "QueryBuilder[T]":
        """Add a WHERE NOT EXISTS subquery constraint.

        Args:
            callback: Callable that receives a QueryBuilder and adds constraints

        Returns:
            Self for chaining
        """
        subquery = QueryBuilder(self.grammar, self.connection)
        callback(subquery)
        self._wheres.append(WhereClause(column="", boolean="and", type="not_exists", query=subquery))
        return self

    def lock_for_update(self) -> "QueryBuilder[T]":
        """Lock the selected rows for update (SELECT ... FOR UPDATE).

        Returns:
            Self for chaining
        """
        self._lock = "for update"
        return self

    def for_share(self) -> "QueryBuilder[T]":
        """Lock the selected rows in share mode (SELECT ... FOR SHARE).

        Returns:
            Self for chaining
        """
        self._lock = "for share"
        return self

    def when(
        self,
        condition: Any,
        callback: Callable[["QueryBuilder"], "QueryBuilder[T]"],
        default: Optional[Callable[["QueryBuilder"], "QueryBuilder[T]"]] = None,
    ) -> "QueryBuilder[T]":
        """Apply a callback only when condition is truthy.

        Args:
            condition: Value to test
            callback: Applied when condition is truthy
            default: Applied when condition is falsy (optional)

        Returns:
            Self for chaining
        """
        if condition:
            callback(self)
        elif default is not None:
            default(self)
        return self

    def unless(
        self,
        condition: Any,
        callback: Callable[["QueryBuilder"], "QueryBuilder[T]"],
        default: Optional[Callable[["QueryBuilder"], "QueryBuilder[T]"]] = None,
    ) -> "QueryBuilder[T]":
        """Apply a callback only when condition is falsy.

        Args:
            condition: Value to test
            callback: Applied when condition is falsy
            default: Applied when condition is truthy (optional)

        Returns:
            Self for chaining
        """
        return self.when(not condition, callback, default)

    def tap(self, callback: Callable[["QueryBuilder"], None]) -> "QueryBuilder[T]":
        """Tap into the query chain without affecting it.

        Args:
            callback: Callable that receives the builder

        Returns:
            Self for chaining
        """
        callback(self)
        return self

    async def paginate(
        self,
        per_page: int = 15,
        page: int = 1,
        columns: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Paginate the results.

        Args:
            per_page: Records per page
            page: Page number (1-indexed)
            columns: Columns to select

        Returns:
            Dict with data, total, per_page, current_page, last_page, from, to
        """
        if columns:
            self.select(*columns)
        total = await self.clone().count()
        results = await self.offset((page - 1) * per_page).limit(per_page).get()
        last_page = max(1, -(-total // per_page))  # ceiling division
        frm = (page - 1) * per_page + 1 if total > 0 else 0
        to = min(page * per_page, total)
        return {
            "data": results,
            "total": total,
            "per_page": per_page,
            "current_page": page,
            "last_page": last_page,
            "from": frm,
            "to": to,
        }

    async def simple_paginate(
        self,
        per_page: int = 15,
        page: int = 1,
        columns: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Paginate without computing total count.

        Args:
            per_page: Records per page
            page: Page number (1-indexed)
            columns: Columns to select

        Returns:
            Dict with data, per_page, current_page, has_more_pages
        """
        if columns:
            self.select(*columns)
        results = await self.offset((page - 1) * per_page).limit(per_page + 1).get()
        results_list = list(results)
        has_more = len(results_list) > per_page
        if has_more:
            results_list = results_list[:per_page]
        from pyloquent.orm.collection import Collection
        return {
            "data": Collection(results_list),
            "per_page": per_page,
            "current_page": page,
            "has_more_pages": has_more,
        }

    async def cursor(self) -> AsyncIterator[T]:
        """Iterate over results one at a time using a cursor.

        Yields:
            Individual model instances
        """
        offset = 0
        batch_size = 100
        while True:
            batch = await self.offset(offset).limit(batch_size).get()
            if not batch:
                break
            for item in batch:
                yield item
            if len(batch) < batch_size:
                break
            offset += batch_size

    async def lazy(self, chunk_size: int = 1000) -> AsyncIterator[T]:
        """Lazily iterate over results in chunks.

        Args:
            chunk_size: Records per chunk

        Yields:
            Individual model instances
        """
        async for chunk in self.chunk(chunk_size):
            for item in chunk:
                yield item

    async def each(self, callback: Callable[[T], Any], chunk_size: int = 1000) -> bool:
        """Execute a callback for each record.

        Args:
            callback: Function to call for each record
            chunk_size: Number of records to fetch at a time

        Returns:
            True on completion
        """
        import asyncio
        async for chunk in self.chunk(chunk_size):
            for item in chunk:
                result = callback(item)
                if asyncio.iscoroutine(result):
                    await result
        return True

    # ========================================================================
    # Chunking
    # ========================================================================

    async def chunk(self, count: int) -> AsyncIterator[List[T]]:
        """Chunk the results into smaller groups.

        Args:
            count: Number of records per chunk

        Yields:
            Lists of records
        """
        offset = 0

        while True:
            chunk_results = await self.offset(offset).limit(count).get()

            if not chunk_results:
                break

            yield list(chunk_results)

            if len(chunk_results) < count:
                break

            offset += count

    async def chunk_by_id(self, count: int, column: str = "id") -> AsyncIterator[List[T]]:
        """Chunk results using an ID-based approach.

        This is more efficient for large datasets being updated.

        Args:
            count: Number of records per chunk
            column: Column to use for chunking (default: id)

        Yields:
            Lists of records
        """
        last_id = None

        while True:
            query = self.limit(count).order_by(column)

            if last_id is not None:
                query = query.where(column, ">", last_id)

            chunk_results = await query.get()

            if not chunk_results:
                break

            results_list = list(chunk_results)
            yield results_list

            if len(results_list) < count:
                break

            last_result = results_list[-1]
            if isinstance(last_result, dict):
                last_id = last_result.get(column)
            else:
                last_id = getattr(last_result, column, None)

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def to_sql(self) -> Tuple[str, List[Any]]:
        """Get the SQL representation of the query.

        Returns:
            Tuple of (SQL string, bindings list)
        """
        return self.grammar.compile_select(self)

    def clone(self) -> "QueryBuilder[T]":
        """Create a copy of the query builder.

        Returns:
            New query builder with same state
        """
        new_builder = QueryBuilder(self.grammar, self.connection, self.model_class)
        new_builder._table = self._table
        new_builder._selects = self._selects.copy()
        new_builder._distinct = self._distinct
        new_builder._distinct_on = self._distinct_on.copy() if self._distinct_on else None
        new_builder._wheres = self._wheres.copy()
        new_builder._joins = self._joins.copy()
        new_builder._orders = self._orders.copy()
        new_builder._groups = self._groups.copy()
        new_builder._havings = self._havings.copy()
        new_builder._limit = self._limit
        new_builder._offset = self._offset
        new_builder._lock = self._lock
        new_builder._bindings = {k: v.copy() for k, v in self._bindings.items()}
        return new_builder

    def _hydrate_models(self, results: List[Dict[str, Any]]) -> "Collection[T]":
        """Hydrate raw results into model instances.

        Args:
            results: List of raw database results

        Returns:
            Collection of model instances
        """
        from pyloquent.orm.collection import Collection

        if not self.model_class:
            return Collection(results)

        import asyncio
        model_field_names = set(self.model_class.model_fields.keys())
        models = []
        for result in results:
            known = {k: v for k, v in result.items() if k in model_field_names}
            extras = {k: v for k, v in result.items() if k not in model_field_names}
            model = self.model_class(**known)
            if hasattr(model, "_exists"):
                model._exists = True
            if hasattr(model, "_original"):
                model._original = result.copy()
            for key, val in extras.items():
                object.__setattr__(model, key, val)
            models.append(model)

        # Fire retrieved events (best-effort, non-blocking)
        for model in models:
            if hasattr(model, "_fire_event"):
                try:
                    coro = model._fire_event("retrieved")
                    if asyncio.iscoroutine(coro):
                        asyncio.ensure_future(coro)
                except Exception:
                    pass

        return Collection(models)

    async def _eager_load_relations(self, models: "Collection[T]") -> None:
        """Eager load relations for a collection of models.

        Args:
            models: Collection of models to load relations for
        """
        if not models or not self.model_class:
            return

        for relation_name in self._eager_loads:
            await self._eager_load_relation(models, relation_name)

    async def _eager_load_relation(self, models: "Collection[T]", relation_name: str) -> None:
        """Eager load a single relation for a collection of models.

        Args:
            models: Collection of models
            relation_name: Name of relation to load
        """
        if not models:  # pragma: no cover
            return  # pragma: no cover

        # Get the first model to access the relation method
        first_model = models.first()
        if not first_model:  # pragma: no cover
            return  # pragma: no cover

        # Check if relation method exists
        if not hasattr(first_model, relation_name):
            from pyloquent.exceptions import RelationNotFoundException

            raise RelationNotFoundException(self.model_class, relation_name)

        # Get relation instance
        relation = getattr(first_model, relation_name)()

        # Get related models
        related_models = await relation.query.where_in(
            relation.foreign_key, models.pluck(relation.local_key)
        ).get()

        # Group related models by foreign key
        dictionary = {}
        for related in related_models:
            key = getattr(related, relation.foreign_key)
            if key not in dictionary:
                dictionary[key] = []
            dictionary[key].append(related)

        # Match and set relations on parent models
        from pyloquent.orm.collection import Collection

        for model in models:
            key = getattr(model, relation.local_key)
            matches = Collection(dictionary.get(key, []))
            model.set_relation(relation_name, matches)

    def __await__(self):
        """Allow awaiting the query builder directly."""
        return self.get().__await__()
