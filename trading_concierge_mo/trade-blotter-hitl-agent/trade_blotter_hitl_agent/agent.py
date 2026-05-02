"""ADK agent definition for the Trade Blotter HITL agent.

`adk run trade_blotter_hitl_agent` and `adk web` look for `root_agent` in this
package's `__init__.py`. We build the agent at import time so the model
always sees the current MCP tool surface.

If the MCP bridge isn't reachable at import time we still construct an agent
with only the approval-request tool, so `adk web` doesn't crash; the agent
will tell the user the bridge is down and ask them to retry.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from google.adk import Agent
from google.adk.tools import FunctionTool
from google.genai import types

from .config import settings
from .direct_trade_tools import DIRECT_TRADE_TOOL_NAMES, build_direct_trade_api_tools
from .hitl import (
    before_tool_callback_factory,
    load_classification,
    make_request_approval_tool,
)
from .mcp_client import MCPHTTPClient
from .prompts import build_instruction
from .skills_builder import compile_hitl_skills_digest, maybe_write_skills_snapshot
from .tool_factory import build_tools
from .trade_api_client import TradeAPIHTTPClient


logger = logging.getLogger(__name__)


PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def _make_offline_agent(reason: str) -> Agent:
    """Build a degraded agent when the bridge isn't reachable at import time."""
    def report_bridge_down() -> dict[str, Any]:
        """Explain that the MCP bridge is unreachable."""
        return {"status": "error", "reason": reason}

    instruction = (
        "You are the Trade Blotter Concierge, but the MCP HTTP bridge is "
        f"currently unreachable: {reason}. Tell the user that the bridge is "
        "down, ask them to start mcp_http_server.py, and call "
        "`report_bridge_down` if they want to see the raw error."
    )
    return Agent(
        model=settings.adk_model,
        name="trade_blotter_concierge_offline",
        description=(
            "Trade Blotter Concierge in degraded mode (MCP HTTP bridge is "
            "unreachable). Will not call any tools."
        ),
        instruction=instruction,
        tools=[FunctionTool(func=report_bridge_down)],
        generate_content_config=types.GenerateContentConfig(temperature=0.1),
    )


def build_root_agent() -> Agent:
    """Build the root ADK agent.

    Discovers MCP tools via the HTTP bridge, classifies them, wraps them as
    ADK tools, and attaches the HITL approval tool plus the pre-tool callback.
    """
    classification = load_classification(
        settings.resolve_classification_path(PACKAGE_ROOT),
        fail_closed=settings.hitl_fail_closed,
    )

    client = MCPHTTPClient(
        settings.mcp_bridge_url,
        timeout=settings.mcp_bridge_timeout,
        token=settings.mcp_bridge_token,
    )

    try:
        client.health()
        max_skill_chars = settings.hitl_skills_max_chars
        if max_skill_chars == 0:
            max_skill_chars = None
        skills_digest = compile_hitl_skills_digest(
            client,
            package_root=PACKAGE_ROOT,
            max_chars=max_skill_chars,
        )
        if settings.hitl_write_skills_snapshot:
            try:
                maybe_write_skills_snapshot(
                    skills_digest,
                    settings.resolve_skills_snapshot_path(PACKAGE_ROOT),
                )
            except OSError as exc:
                logger.warning("Could not write skills snapshot: %s", exc)
        tools, read_only, mutating = build_tools(client, classification)
    except Exception as exc:  # noqa: BLE001
        logger.warning("MCP bridge not reachable at %s: %s", settings.mcp_bridge_url, exc)
        client.close()
        return _make_offline_agent(reason=str(exc))

    direct_tools: list = []
    direct_names: list[str] = []
    trade_api: TradeAPIHTTPClient | None = None
    if settings.trade_api_direct_tools_enabled:
        try:
            trade_api = TradeAPIHTTPClient(settings)
            trade_api.health()
            direct_tools = build_direct_trade_api_tools(trade_api)
            direct_names = list(DIRECT_TRADE_TOOL_NAMES)
            logger.info(
                "Direct Trade API tools enabled against %s", settings.trade_api_base_url
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Direct Trade API tools disabled (%s): %s",
                settings.trade_api_base_url,
                exc,
            )
            if trade_api is not None:
                trade_api.close()
                trade_api = None

    approval_tool = make_request_approval_tool(mutating)
    instruction = build_instruction(
        read_only=[*direct_names, *read_only],
        mutating=mutating,
        skills_digest=skills_digest,
    )

    return Agent(
        model=settings.adk_model,
        name="trade_blotter_concierge",
        description=(
            "ADK agent for Trade Blotter: MCP HTTP bridge tools plus optional "
            "trade_api_* REST calls to the same Trade API (authorized). "
            "Mutating MCP tools require human approval via LongRunningFunctionTool."
        ),
        instruction=instruction,
        tools=[approval_tool, *direct_tools, *tools],
        before_tool_callback=before_tool_callback_factory(classification),
        generate_content_config=types.GenerateContentConfig(temperature=0.1),
    )


root_agent: Agent = build_root_agent()
