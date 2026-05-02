"""Tests for tool classification and the factory."""

from __future__ import annotations

import httpx
import respx

from trade_blotter_hitl_agent.hitl import Classification, load_classification
from trade_blotter_hitl_agent.mcp_client import MCPHTTPClient
from trade_blotter_hitl_agent.tool_factory import build_tools


BASE = "http://bridge.test"


def test_classification_defaults() -> None:
    cls = Classification(
        read_only=("list_*", "get_*"),
        mutating=("place_*", "cancel_*"),
        fail_closed=True,
    )
    assert cls.classify("list_open_trades") == "read_only"
    assert cls.classify("get_trade") == "read_only"
    assert cls.classify("place_trade") == "mutating"
    assert cls.classify("cancel_trade") == "mutating"
    # Unknown -> fail closed
    assert cls.classify("frobnicate") == "mutating"


def test_classification_fail_open() -> None:
    cls = Classification(read_only=("list_*",), mutating=("place_*",), fail_closed=False)
    assert cls.classify("frobnicate") == "read_only"


def test_load_classification_from_yaml(tmp_path) -> None:
    p = tmp_path / "rules.yaml"
    p.write_text(
        """
        fail_closed: true
        read_only: ["list_*"]
        mutating: ["place_*"]
        """,
        encoding="utf-8",
    )
    cls = load_classification(p, fail_closed=False)
    assert cls.fail_closed is True
    assert cls.classify("list_open_trades") == "read_only"
    assert cls.classify("place_trade") == "mutating"
    # Falls back to fail_closed when neither matches
    assert cls.classify("frobnicate") == "mutating"


@respx.mock
def test_build_tools_classifies_correctly() -> None:
    respx.get(f"{BASE}/tools").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"name": "list_open_trades", "description": "List.", "inputSchema": {}},
                {"name": "get_trade", "description": "Get.", "inputSchema": {}},
                {"name": "place_trade", "description": "Place.", "inputSchema": {}},
                {"name": "cancel_trade", "description": "Cancel.", "inputSchema": {}},
            ],
        )
    )
    cls = Classification(
        read_only=("list_*", "get_*"),
        mutating=("place_*", "cancel_*"),
        fail_closed=True,
    )
    with MCPHTTPClient(BASE) as client:
        tools, read_only, mutating = build_tools(client, cls)

    assert sorted(read_only) == ["get_trade", "list_open_trades"]
    assert sorted(mutating) == ["cancel_trade", "place_trade"]

    names = [t.name for t in tools]
    assert "list_open_trades" in names
    assert "get_trade" in names
    assert "execute_place_trade" in names
    assert "execute_cancel_trade" in names
