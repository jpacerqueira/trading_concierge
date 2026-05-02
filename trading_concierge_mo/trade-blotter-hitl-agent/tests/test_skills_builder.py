"""Tests for MCP + desktop skills compilation."""

from __future__ import annotations

import httpx
import respx

from trade_blotter_hitl_agent.mcp_client import MCPHTTPClient
from trade_blotter_hitl_agent.skills_builder import compile_hitl_skills_digest


BASE = "http://skills.test"


@respx.mock
def test_compile_hitl_skills_digest_includes_surface(tmp_path) -> None:
    (tmp_path / "assets" / "includes").mkdir(parents=True)
    (tmp_path / "assets" / "includes" / "desktop_copilot_policy.md").write_text(
        "## Desktop policy test marker\n", encoding="utf-8"
    )
    (tmp_path / "assets" / "includes" / "desktop_stack_behaviour.md").write_text(
        "## Stack behaviour marker\n", encoding="utf-8"
    )

    respx.get(f"{BASE}/resources").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "uri": "resource://trade-blotter/glossary",
                    "name": "Glossary",
                    "description": "Terms",
                }
            ],
        )
    )
    respx.get(f"{BASE}/resource").mock(
        return_value=httpx.Response(
            200,
            json={"uri": "resource://trade-blotter/glossary", "content": "# Glossary body\n"},
        )
    )
    respx.get(f"{BASE}/prompts").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "name": "analyze_trade_query",
                    "description": "Analyze NL query",
                    "arguments": [{"name": "user_question", "required": True}],
                }
            ],
        )
    )
    respx.post(f"{BASE}/prompt/analyze_trade_query").mock(
        return_value=httpx.Response(
            200,
            json={
                "messages": [
                    {"role": "user", "content": {"type": "text", "text": "Template steps here"}}
                ]
            },
        )
    )
    respx.get(f"{BASE}/tools").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "name": "query_trades",
                    "description": "Query",
                    "inputSchema": {"type": "object"},
                }
            ],
        )
    )

    with MCPHTTPClient(BASE) as client:
        digest = compile_hitl_skills_digest(client, package_root=tmp_path, max_chars=50_000)

    assert "Glossary body" in digest
    assert "analyze_trade_query" in digest
    assert "Template steps here" in digest
    assert "query_trades" in digest
    assert "Desktop policy test marker" in digest
    assert "Stack behaviour marker" in digest
