"""Connection manager for handling multiple database connections."""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional

from pyloquent.database.connection import Connection
from pyloquent.exceptions import PyloquentException


class ConnectionManager:
    """Manages multiple named database connections.

    This class provides centralized management of database connections
    with support for FastAPI lifespan integration.

    Example:
        manager = ConnectionManager()
        manager.add_connection('default', {
            'driver': 'sqlite',
            'database': ':memory:'
        })

        @app.on_event('startup')
        async def startup():
            await manager.connect()

        @app.on_event('shutdown')
        async def shutdown():
            await manager.disconnect()
    """

    def __init__(self):
        """Initialize the connection manager."""
        self._configs: Dict[str, Dict[str, Any]] = {}
        self._connections: Dict[str, Connection] = {}
        self._default: Optional[str] = None

    def add_connection(self, name: str, config: Dict[str, Any], default: bool = False) -> None:
        """Add a connection configuration.

        Args:
            name: Connection name
            config: Connection configuration dictionary
            default: Whether this should be the default connection

        Raises:
            ValueError: If connection name already exists
        """
        if name in self._configs:
            raise ValueError(f"Connection '{name}' already exists")

        self._configs[name] = config

        if default or self._default is None:
            self._default = name

    def connection(self, name: Optional[str] = None) -> Connection:
        """Get a connection by name.

        Args:
            name: Connection name (uses default if not specified)

        Returns:
            Connection instance

        Raises:
            PyloquentException: If connection doesn't exist or isn't connected
        """
        name = name or self._default

        if name is None:
            raise PyloquentException("No default connection configured")

        if name not in self._connections:
            # Create connection if config exists
            if name not in self._configs:
                raise PyloquentException(f"Connection '{name}' not configured")

            self._connections[name] = self._create_connection(name, self._configs[name])

        conn = self._connections[name]

        if not conn.is_connected():
            raise PyloquentException(f"Connection '{name}' is not connected")

        return conn

    def _create_connection(self, name: str, config: Dict[str, Any]) -> Connection:
        """Create a connection instance from configuration.

        Args:
            name: Connection name
            config: Connection configuration

        Returns:
            Connection instance

        Raises:
            PyloquentException: If driver is not supported
        """
        driver = config.get("driver", "sqlite")

        if driver == "sqlite":
            from pyloquent.database.sqlite_connection import SQLiteConnection

            return SQLiteConnection(config)
        elif driver in ("postgres", "postgresql"):
            from pyloquent.database.postgres_connection import PostgresConnection

            return PostgresConnection(config)
        elif driver == "mysql":
            from pyloquent.database.mysql_connection import MySQLConnection

            return MySQLConnection(config)
        elif driver == "d1":
            from pyloquent.d1.connection import D1Connection

            return D1Connection(config)
        elif driver == "d1_binding":
            from pyloquent.d1.binding import D1BindingConnection

            binding = config.get("binding")
            if binding is None:
                raise PyloquentException(
                    "d1_binding driver requires a 'binding' key in the config "
                    "(pass the env.DB binding object)"
                )
            return D1BindingConnection(binding, config)
        else:
            raise PyloquentException(f"Unsupported database driver: {driver}")

    async def connect(self, name: Optional[str] = None) -> None:
        """Establish database connection(s).

        Args:
            name: Connection name (connects all if not specified)
        """
        if name:
            conn = self._connections.get(name) or self._create_connection(name, self._configs[name])
            if not conn.is_connected():
                await conn.connect()
                self._connections[name] = conn
        else:
            for conn_name in self._configs:
                await self.connect(conn_name)

    async def disconnect(self, name: Optional[str] = None) -> None:
        """Close database connection(s).

        Args:
            name: Connection name (disconnects all if not specified)
        """
        if name:
            if name in self._connections:
                await self._connections[name].disconnect()
        else:
            for conn in self._connections.values():
                await conn.disconnect()
            self._connections.clear()

    @asynccontextmanager
    async def transaction(self, name: Optional[str] = None) -> AsyncGenerator[Connection, None]:
        """Context manager for database transactions.

        Args:
            name: Connection name (uses default if not specified)

        Yields:
            Connection instance within transaction

        Example:
            async with manager.transaction() as conn:
                await conn.table('users').insert({'name': 'John'})
                # Automatically commits or rolls back
        """
        conn = self.connection(name)

        try:
            await conn.begin_transaction()
            yield conn
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise

    def table(self, name: str, connection: Optional[str] = None) -> "QueryBuilder":
        """Start a query builder for a table.

        Args:
            name: Table name
            connection: Connection name (uses default if not specified)

        Returns:
            QueryBuilder instance
        """
        return self.connection(connection).table(name)

    def lifespan(self):
        """Get an async context manager for FastAPI lifespan events.

        Returns:
            Async context manager for startup/shutdown

        Example:
            app = FastAPI()
            manager = ConnectionManager()
            manager.add_connection('default', {...})

            @app.on_event('startup')
            async def startup():
                await manager.connect()

            @app.on_event('shutdown')
            async def shutdown():
                await manager.disconnect()
        """
        return self

    async def connect_all(self) -> None:
        """Alias for :meth:`connect` with no arguments — connects every configured connection.

        Useful in scripts and sync wrappers where the method name is more explicit.
        """
        await self.connect()

    async def disconnect_all(self) -> None:
        """Alias for :meth:`disconnect` with no arguments — closes every connection."""
        await self.disconnect()

    async def __aenter__(self):
        """Async context manager entry - connect to all databases."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - disconnect from all databases."""
        await self.disconnect()

    @classmethod
    def from_binding(cls, binding: Any, name: str = "default") -> "ConnectionManager":
        """Create a :class:`ConnectionManager` pre-configured for a D1 Workers binding.

        Convenience factory for Cloudflare Worker handlers where the D1 binding
        (``env.DB``) is the only connection needed.

        Args:
            binding: The D1 binding object (``env.DB`` from the Worker environment).
            name: Connection name (default: ``'default'``).

        Returns:
            A new :class:`ConnectionManager` with the binding registered **and
            already marked as connected** (no ``await manager.connect()`` needed).

        Example::

            # worker.py
            from pyloquent.database.manager import ConnectionManager, set_manager

            async def on_fetch(request, env):
                manager = ConnectionManager.from_binding(env.DB)
                set_manager(manager)
                users = await User.where('active', True).get()
                ...
        """
        from pyloquent.d1.binding import D1BindingConnection

        manager = cls()
        conn = D1BindingConnection(binding)
        # Mark as connected synchronously — no I/O required for binding setup
        conn._connected = True
        manager._configs[name] = {"driver": "d1_binding", "binding": binding}
        manager._connections[name] = conn
        manager._default = name
        return manager


# Global connection manager instance
_global_manager: Optional[ConnectionManager] = None


def get_manager() -> ConnectionManager:
    """Get the global connection manager instance.

    Returns:
        ConnectionManager instance
    """
    global _global_manager
    if _global_manager is None:
        _global_manager = ConnectionManager()
    return _global_manager


def set_manager(manager: ConnectionManager) -> None:
    """Set the global connection manager instance.

    Args:
        manager: ConnectionManager instance
    """
    global _global_manager
    _global_manager = manager
