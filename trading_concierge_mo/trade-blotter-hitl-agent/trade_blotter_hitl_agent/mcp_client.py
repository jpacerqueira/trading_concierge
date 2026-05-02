"""HTTP client for the Trade Blotter MCP HTTP bridge.

The bridge (`mcp_http_server.py`) re-exposes a stdio MCP server over plain REST:

    GET  /health
    GET  /tools                     -> list[ToolSpec]
    GET  /resources                 -> list[ResourceSpec]
    GET  /prompts                   -> list[PromptSpec]
    GET  /resource?uri=<uri>        -> {"uri", "content"}
    POST /tool/{name}               -> {"name", "content": [...]} (body: {"arguments": {...}})
    POST /prompt/{name}             -> {"messages": [...]}        (body: {"arguments": {...}})

This module wraps those endpoints with a sync and an async client. The agent
itself calls the sync client from inside ADK FunctionTool callables; the async
client is provided for places where you'd rather not block (tests, batch jobs,
or future migration to async tools).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

import httpx


@dataclass(slots=True)
class ToolSpec:
    """Subset of the MCP tool descriptor we care about."""

    name: str
    description: str
    input_schema: dict[str, Any]
    raw: dict[str, Any]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ToolSpec":
        # MCP returns either `inputSchema` or `input_schema` depending on
        # serializer version; accept both.
        schema = data.get("inputSchema") or data.get("input_schema") or {}
        return cls(
            name=str(data["name"]),
            description=str(data.get("description", "")),
            input_schema=dict(schema) if schema else {},
            raw=dict(data),
        )


class MCPBridgeError(RuntimeError):
    """Raised when the MCP HTTP bridge returns a non-2xx response."""


def _build_headers(token: str | None) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _content_to_python(content: Any) -> Any:
    """Best-effort conversion of MCP `content` into a JSON-friendly Python value.

    The MCP `call_tool` return is a list of content items (text/json/blob). We
    flatten the common cases so tool callers see a clean Python value rather
    than the raw protocol envelope.
    """
    if not isinstance(content, list):
        return content

    if not content:
        return None

    if len(content) == 1:
        item = content[0]
        if isinstance(item, dict):
            # Text content: try to JSON-decode, otherwise return as string.
            if item.get("type") == "text" and "text" in item:
                text = item["text"]
                try:
                    return json.loads(text)
                except (ValueError, TypeError):
                    return text
            # Already structured (json content type, or tool returned a dict).
            return item.get("data", item)
        return item

    # Multiple items: return the list of converted items.
    return [_content_to_python([item]) for item in content]


# --------------------------------------------------------------------------- #
# Sync client (used inside ADK FunctionTool callables).
# --------------------------------------------------------------------------- #

class MCPHTTPClient:
    """Thin synchronous client over the FastAPI bridge."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 30.0,
        token: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=self._base_url,
            timeout=timeout,
            headers=_build_headers(token),
        )

    # -- lifecycle -----------------------------------------------------------

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "MCPHTTPClient":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    # -- low-level -----------------------------------------------------------

    def _get(self, path: str, **kwargs: Any) -> Any:
        resp = self._client.get(path, **kwargs)
        if resp.status_code >= 400:
            raise MCPBridgeError(
                f"GET {path} -> {resp.status_code}: {resp.text}"
            )
        return resp.json()

    def _post(self, path: str, payload: Mapping[str, Any]) -> Any:
        resp = self._client.post(path, json=payload)
        if resp.status_code >= 400:
            raise MCPBridgeError(
                f"POST {path} -> {resp.status_code}: {resp.text}"
            )
        return resp.json()

    # -- public API ----------------------------------------------------------

    def health(self) -> dict[str, str]:
        return self._get("/health")

    def list_tools(self) -> list[ToolSpec]:
        data = self._get("/tools")
        return [ToolSpec.from_dict(item) for item in data]

    def list_resources(self) -> list[dict[str, Any]]:
        return self._get("/resources")

    def list_prompts(self) -> list[dict[str, Any]]:
        return self._get("/prompts")

    def read_resource(self, uri: str) -> dict[str, Any]:
        return self._get("/resource", params={"uri": uri})

    def call_tool(self, name: str, arguments: Mapping[str, Any] | None = None) -> Any:
        body = {"arguments": dict(arguments or {})}
        result = self._post(f"/tool/{name}", body)
        return _content_to_python(result.get("content"))

    def get_prompt(self, name: str, arguments: Mapping[str, Any] | None = None) -> Any:
        body = {"arguments": dict(arguments or {})}
        return self._post(f"/prompt/{name}", body)


# --------------------------------------------------------------------------- #
# Async client (parity surface, for tests and future async tools).
# --------------------------------------------------------------------------- #

class AsyncMCPHTTPClient:
    """Async parity of MCPHTTPClient."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 30.0,
        token: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
            headers=_build_headers(token),
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "AsyncMCPHTTPClient":
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.aclose()

    async def _get(self, path: str, **kwargs: Any) -> Any:
        resp = await self._client.get(path, **kwargs)
        if resp.status_code >= 400:
            raise MCPBridgeError(
                f"GET {path} -> {resp.status_code}: {resp.text}"
            )
        return resp.json()

    async def _post(self, path: str, payload: Mapping[str, Any]) -> Any:
        resp = await self._client.post(path, json=payload)
        if resp.status_code >= 400:
            raise MCPBridgeError(
                f"POST {path} -> {resp.status_code}: {resp.text}"
            )
        return resp.json()

    async def health(self) -> dict[str, str]:
        return await self._get("/health")

    async def list_tools(self) -> list[ToolSpec]:
        data = await self._get("/tools")
        return [ToolSpec.from_dict(item) for item in data]

    async def list_resources(self) -> list[dict[str, Any]]:
        return await self._get("/resources")

    async def list_prompts(self) -> list[dict[str, Any]]:
        return await self._get("/prompts")

    async def read_resource(self, uri: str) -> dict[str, Any]:
        return await self._get("/resource", params={"uri": uri})

    async def call_tool(
        self, name: str, arguments: Mapping[str, Any] | None = None
    ) -> Any:
        body = {"arguments": dict(arguments or {})}
        result = await self._post(f"/tool/{name}", body)
        return _content_to_python(result.get("content"))

    async def get_prompt(
        self, name: str, arguments: Mapping[str, Any] | None = None
    ) -> Any:
        body = {"arguments": dict(arguments or {})}
        return await self._post(f"/prompt/{name}", body)
