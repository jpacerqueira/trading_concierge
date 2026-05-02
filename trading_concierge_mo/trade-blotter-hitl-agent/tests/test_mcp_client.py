"""Tests for the synchronous MCP HTTP client (mocked with respx)."""

from __future__ import annotations

import httpx
import pytest
import respx

from trade_blotter_hitl_agent.mcp_client import MCPHTTPClient


BASE = "http://bridge.test"


@respx.mock
def test_health_and_list_tools() -> None:
    respx.get(f"{BASE}/health").mock(return_value=httpx.Response(200, json={"status": "healthy"}))
    respx.get(f"{BASE}/tools").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "name": "list_open_trades",
                    "description": "List open trades.",
                    "inputSchema": {"type": "object", "properties": {}},
                },
                {
                    "name": "place_trade",
                    "description": "Place a trade.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string"},
                            "qty": {"type": "integer"},
                        },
                        "required": ["symbol", "qty"],
                    },
                },
            ],
        )
    )

    with MCPHTTPClient(BASE) as client:
        assert client.health() == {"status": "healthy"}
        tools = client.list_tools()

    assert [t.name for t in tools] == ["list_open_trades", "place_trade"]
    assert tools[1].input_schema["required"] == ["symbol", "qty"]


@respx.mock
def test_call_tool_decodes_text_json() -> None:
    respx.post(f"{BASE}/tool/list_open_trades").mock(
        return_value=httpx.Response(
            200,
            json={
                "name": "list_open_trades",
                "content": [
                    {"type": "text", "text": '[{"id":"T-1","sym":"AAPL"}]'},
                ],
            },
        )
    )
    with MCPHTTPClient(BASE) as client:
        result = client.call_tool("list_open_trades", {})
    assert result == [{"id": "T-1", "sym": "AAPL"}]


@respx.mock
def test_call_tool_passes_arguments_in_body() -> None:
    route = respx.post(f"{BASE}/tool/place_trade").mock(
        return_value=httpx.Response(
            200,
            json={
                "name": "place_trade",
                "content": [{"type": "text", "text": '{"id":"T-9","status":"new"}'}],
            },
        )
    )
    with MCPHTTPClient(BASE) as client:
        client.call_tool("place_trade", {"symbol": "AAPL", "qty": 100})

    assert route.called
    sent = route.calls.last.request.read().decode()
    assert '"symbol": "AAPL"' in sent or '"symbol":"AAPL"' in sent
    assert '"qty": 100' in sent or '"qty":100' in sent


@respx.mock
def test_bridge_error_propagates() -> None:
    from trade_blotter_hitl_agent.mcp_client import MCPBridgeError

    respx.post(f"{BASE}/tool/place_trade").mock(
        return_value=httpx.Response(400, json={"detail": "boom"})
    )
    with MCPHTTPClient(BASE) as client:
        with pytest.raises(MCPBridgeError):
            client.call_tool("place_trade", {"symbol": "AAPL"})
