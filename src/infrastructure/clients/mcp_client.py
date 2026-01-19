# agent_core/client/mcp_hub_client.py
import asyncio
import json
from typing import Any, Dict, List, AsyncGenerator, Optional

import httpx

from src.agent.abs_agent import IBaseAgent


class MCPHubClient:
    """
    Client for your MCP Hub (matches README endpoints).
    - GET  /mcp_hub/servers      -> get_servers()
    - GET  /mcp_hub/tools        -> get_tools()
    - GET  /mcp_hub/health       -> health()
    - POST /mcp_hub/call         -> call(tool, arguments)  (returns dict)
    - POST /mcp_hub/call_stream  -> call_stream(tool, arguments) (yields chunks)
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 2,
        backoff: float = 0.5,
    ):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout)
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff = backoff
        self._tools_cache: Optional[List[Dict[str, Any]]] = None
        self._servers_cache: Optional[List[Dict[str, Any]]] = None
        self._lock = asyncio.Lock()

    # -----------------------
    # helpers
    # -----------------------
    async def _request_json(self, method: str, path: str, **kwargs) -> Any:
        url = f"{self.base_url}{path}"
        last_exc = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = await self._client.request(method, url, **kwargs)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                last_exc = e
                if attempt < self.max_retries:
                    await asyncio.sleep(self.backoff * (2 ** attempt))
                    continue
                raise last_exc

    # -----------------------
    # servers / tools / health
    # -----------------------
    async def get_servers(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        if use_cache and self._servers_cache is not None:
            return self._servers_cache
        data = await self._request_json("GET", "/mcp_hub/servers")
        if isinstance(data, list):
            self._servers_cache = data
            return data
        return []

    async def get_tools(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        Returns the 'tools' list as the hub provides it.
        """
        if use_cache and self._tools_cache is not None:
            return self._tools_cache
        data = await self._request_json("GET", "/mcp_hub/tools")
        if isinstance(data, dict) and isinstance(data.get("tools"), list):
            self._tools_cache = data["tools"]
            return self._tools_cache
        # some hubs may return list directly
        if isinstance(data, list):
            self._tools_cache = data
            return data
        return []

    async def health(self) -> Dict[str, Any]:
        return await self._request_json("GET", "/mcp_hub/health")

    # -----------------------
    # tool call (normal)
    # -----------------------
    async def call_tool(
        self,
        id: str,
        type: str,
        function: Dict[str, Any],
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Synchronous-style tool call (POST /hub/call).
        Returns parsed JSON (dict) from the hub.
        """
        payload = {"id": id, "type": type, "function": function}
        json_body = {"json": payload}
        # allow override timeout per-call
        if timeout:
            json_body["timeout"] = timeout
        return await self._request_json("POST", "/mcp_hub/call", json=payload)

    # -----------------------
    # tool call (stream)
    # -----------------------
    async def call_tool_stream(
        self,
        tool: str,
        arguments: Dict[str, Any],
        *,
        chunk_timeout: Optional[float] = None,
    ) -> AsyncGenerator[Any, None]:
        """
        Stream call: POST /hub/call_stream
        Yields each JSON-decoded chunk (or raw line) as produced by hub.
        This function does NOT interpret chunks — it forwards them raw.
        """
        url = f"{self.base_url}/mcp_hub/call_stream"
        payload = {"tool": tool, "arguments": arguments}
        # use a fresh client request so we can iterate response stream
        async with httpx.AsyncClient(timeout=self._client.timeout) as client:
            try:
                # Send request and get streaming response
                async with client.stream("POST", url, json=payload, timeout=chunk_timeout or self.timeout) as resp:
                    resp.raise_for_status()
                    async for raw_line in resp.aiter_lines():
                        if raw_line is None:
                            continue
                        line = raw_line.strip()
                        if not line:
                            continue
                        # try parse json, fallback to raw text
                        try:
                            yield json.loads(line)
                        except Exception:
                            yield line
            except Exception as e:
                # stream errors are yielded as an error dict for consumer convenience
                yield {"error": str(e)}

    # -----------------------
    # utilities
    # -----------------------
    async def invalidate_cache(self):
        async with self._lock:
            self._tools_cache = None
            self._servers_cache = None

    async def close(self):
        await self._client.aclose()

    # Context manager support
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
