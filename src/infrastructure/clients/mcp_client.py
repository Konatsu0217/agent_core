"""
MCPHubClient — enhanced with built-in skill support.

Changes from original:
  1. Integrates SkillRegistry for built-in tools (websearch, etc.)
  2. get_tools() merges remote MCP tools + built-in skill schemas
  3. call_tool() routes to built-in handler when tool name matches a skill
  4. Transparent to callers — same API, zero behaviour change for remote tools
"""

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from src.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)


class MCPHubClient:
    """
    Unified tool gateway: remote MCP Hub + built-in skills.

    - GET  /mcp_hub/servers      -> get_servers()
    - GET  /mcp_hub/tools        -> get_tools()       (merged with built-in)
    - GET  /mcp_hub/health       -> health()
    - POST /mcp_hub/call         -> call_tool()        (auto-routes built-in)
    - POST /mcp_hub/call_stream  -> call_tool_stream()
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 2,
        backoff: float = 0.5,
        *,
        enable_builtin_skills: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout)
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff = backoff
        self._tools_cache: Optional[List[Dict[str, Any]]] = None
        self._servers_cache: Optional[List[Dict[str, Any]]] = None
        self._lock = asyncio.Lock()

        # ---- Built-in skills ----
        self._skill_registry = SkillRegistry()
        if enable_builtin_skills:
            self._skill_registry.auto_register()
            logger.info(
                "Built-in skills loaded: %s", self._skill_registry.list_names()
            )

    # ==================================================================
    # Properties
    # ==================================================================
    @property
    def skill_registry(self) -> SkillRegistry:
        """Expose registry for external registration if needed."""
        return self._skill_registry

    # ==================================================================
    # Helpers
    # ==================================================================
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

    def _is_builtin(self, tool_name: str) -> bool:
        """Check if a tool name maps to a built-in skill."""
        return self._skill_registry.has(tool_name)

    # ==================================================================
    # Servers / Tools / Health
    # ==================================================================
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
        Returns merged list: remote MCP tools + built-in skill schemas.
        Built-in schemas are tagged with `"_builtin": True` for easy filtering.
        """
        # 1. Remote tools
        remote_tools: List[Dict[str, Any]] = []
        if use_cache and self._tools_cache is not None:
            remote_tools = self._tools_cache
        else:
            try:
                data = await self._request_json("GET", "/mcp_hub/tools")
                if isinstance(data, dict) and isinstance(data.get("tools"), list):
                    remote_tools = data["tools"]
                elif isinstance(data, list):
                    remote_tools = data
            except Exception as e:
                logger.warning("Failed to fetch remote tools, using built-in only: %s", e)
            self._tools_cache = remote_tools

        # 2. Built-in skill schemas (tagged)
        builtin_schemas = []
        for schema in self._skill_registry.list_schemas():
            tagged = {**schema, "_builtin": True}
            builtin_schemas.append(tagged)

        # 3. Deduplicate: built-in wins if name collision
        builtin_names = {s["function"]["name"] for s in builtin_schemas}
        filtered_remote = [
            t for t in remote_tools
            if t.get("function", {}).get("name") not in builtin_names
        ]

        return builtin_schemas + filtered_remote

    async def health(self) -> Dict[str, Any]:
        hub_health = await self._request_json("GET", "/mcp_hub/health")
        # Augment with built-in skill info
        hub_health["builtin_skills"] = self._skill_registry.list_names()
        return hub_health

    # ==================================================================
    # Tool call (normal) — auto-routes built-in vs remote
    # ==================================================================
    async def call_tool(
        self,
        tool: str,
        arguments: Dict[str, Any],
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Call a tool by name. Automatically routes:
          - Built-in skill  -> in-process execution
          - Remote MCP tool -> POST /mcp_hub/call
        """
        # ---- Built-in fast path ----
        if self._is_builtin(tool):
            logger.debug("Routing '%s' to built-in skill handler", tool)
            return await self._skill_registry.call(tool, arguments)

        # ---- Remote MCP hub ----
        payload = {
            "id": f"call_{hash(str(tool) + str(arguments))}",
            "type": "function",
            "function": {
                "name": tool,
                "arguments": arguments,
            },
        }
        if timeout:
            payload["timeout"] = timeout
        return await self._request_json("POST", "/mcp_hub/call", json=payload)

    async def approve_tool(
        self,
        tool: str,
        arguments: Dict[str, Any],
        approval_id: str,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Approve tool execution (POST /mcp_hub/approve)."""
        payload = {
            "tool": tool,
            "arguments": arguments,
            "approval_id": approval_id,
        }
        if timeout:
            payload["timeout"] = timeout
        return await self._request_json("POST", "/mcp_hub/approve", json=payload)

    # ==================================================================
    # Tool call (stream)
    # ==================================================================
    async def call_tool_stream(
        self,
        tool: str,
        arguments: Dict[str, Any],
        *,
        chunk_timeout: Optional[float] = None,
    ) -> AsyncGenerator[Any, None]:
        """
        Streaming tool call. Built-in skills return a single-chunk stream.
        Remote tools proxy through POST /mcp_hub/call_stream.
        """
        # ---- Built-in: wrap as single-chunk stream ----
        if self._is_builtin(tool):
            result = await self._skill_registry.call(tool, arguments)
            yield result
            return

        # ---- Remote stream ----
        url = f"{self.base_url}/mcp_hub/call_stream"
        payload = {
            "id": f"call_{hash(str(tool) + str(arguments))}",
            "type": "function",
            "function": {
                "name": tool,
                "arguments": arguments,
            },
        }
        async with httpx.AsyncClient(timeout=self._client.timeout) as client:
            try:
                async with client.stream(
                    "POST", url, json=payload,
                    timeout=chunk_timeout or self.timeout,
                ) as resp:
                    resp.raise_for_status()
                    async for raw_line in resp.aiter_lines():
                        if raw_line is None:
                            continue
                        line = raw_line.strip()
                        if not line:
                            continue
                        try:
                            yield json.loads(line)
                        except Exception:
                            yield line
            except Exception as e:
                yield {"error": str(e)}

    # ==================================================================
    # Utilities
    # ==================================================================
    async def invalidate_cache(self):
        async with self._lock:
            self._tools_cache = None
            self._servers_cache = None

    async def close(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
