"""HTTP client for Cloudflare D1 API."""

import json
from typing import Any, Dict, List, Optional

from pyloquent.exceptions import QueryException


class D1HttpClient:
    """HTTP client for interacting with Cloudflare D1 via REST API.

    This client allows you to query D1 databases from outside Cloudflare Workers
    using the Cloudflare API.

    Example:
        client = D1HttpClient(
            account_id="your-account-id",
            database_id="your-database-id",
            api_token="your-api-token"
        )

        # Execute a query
        results = await client.query(
            "SELECT * FROM users WHERE id = ?",
            [1]
        )
    """

    def __init__(
        self,
        account_id: str,
        database_id: str,
        api_token: str,
        base_url: Optional[str] = None,
    ):
        """Initialize the D1 HTTP client.

        Args:
            account_id: Cloudflare account ID
            database_id: D1 database ID
            api_token: Cloudflare API token
            base_url: Optional custom API base URL
        """
        self.account_id = account_id
        self.database_id = database_id
        self.api_token = api_token
        self.base_url = base_url or "https://api.cloudflare.com/client/v4"

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for API requests.

        Returns:
            Headers dictionary
        """
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    def _get_query_url(self) -> str:
        """Get the query endpoint URL.

        Returns:
            URL string
        """
        return f"{self.base_url}/accounts/{self.account_id}/d1/database/{self.database_id}/query"

    async def query(self, sql: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        """Execute a SQL query via the D1 HTTP API.

        Args:
            sql: SQL query string
            params: Query parameters

        Returns:
            Query results

        Raises:
            QueryException: If the query fails
        """
        try:
            import httpx
        except ImportError:
            raise ImportError(
                "D1 HTTP client requires 'httpx' package. Install with: pip install httpx"
            )

        url = self._get_query_url()
        headers = self._get_headers()

        payload = {
            "sql": sql,
            "params": params or [],
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=headers,
                json=payload,
                timeout=30.0,
            )

        if response.status_code != 200:
            raise QueryException(f"D1 API request failed: {response.status_code} - {response.text}")

        data = response.json()

        if not data.get("success"):
            errors = data.get("errors", [])
            error_msg = errors[0].get("message", "Unknown error") if errors else "Unknown error"
            raise QueryException(f"D1 query failed: {error_msg}")

        # Parse results
        result = data.get("result", [])

        if not result:
            return []

        # D1 returns results in a specific format
        # Each result item has 'results', 'success', 'meta' keys
        query_result = result[0]

        if not query_result.get("success"):
            raise QueryException(f"D1 query execution failed")

        return query_result.get("results", [])

    async def execute(self, sql: str, params: Optional[List[Any]] = None) -> Dict[str, Any]:
        """Execute a SQL statement (INSERT, UPDATE, DELETE) via D1 HTTP API.

        Args:
            sql: SQL statement
            params: Query parameters

        Returns:
            Execution result with metadata

        Raises:
            QueryException: If the execution fails
        """
        results = await self.query(sql, params)

        # For non-SELECT queries, D1 returns metadata
        return {
            "success": True,
            "results": results,
        }

    async def batch(self, queries: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Execute multiple queries in a batch.

        Args:
            queries: List of query dictionaries with 'sql' and optional 'params'

        Returns:
            List of query results

        Raises:
            QueryException: If the batch fails
        """
        try:
            import httpx
        except ImportError:
            raise ImportError(
                "D1 HTTP client requires 'httpx' package. Install with: pip install httpx"
            )

        url = f"{self._get_query_url()}/batch"
        headers = self._get_headers()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=headers,
                json=queries,
                timeout=30.0,
            )

        if response.status_code != 200:
            raise QueryException(
                f"D1 API batch request failed: {response.status_code} - {response.text}"
            )

        data = response.json()

        if not data.get("success"):
            errors = data.get("errors", [])
            error_msg = errors[0].get("message", "Unknown error") if errors else "Unknown error"
            raise QueryException(f"D1 batch query failed: {error_msg}")

        results = data.get("result", [])
        return [r.get("results", []) for r in results]

    async def list_tables(self) -> List[str]:
        """List all tables in the database.

        Returns:
            List of table names
        """
        sql = "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        results = await self.query(sql)
        return [row["name"] for row in results]

    async def table_info(self, table_name: str) -> List[Dict[str, Any]]:
        """Get information about a table.

        Args:
            table_name: Table name

        Returns:
            List of column information
        """
        sql = f"PRAGMA table_info({table_name})"
        return await self.query(sql)
