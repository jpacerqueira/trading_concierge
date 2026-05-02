"""Turn MCP bridge tools into ADK FunctionTools.

For each MCP tool returned by the bridge's `/tools` endpoint we create one
Python callable. Read-only tools become `<name>` callables that the LLM can
call directly. Mutating tools become `execute_<name>` callables that:

* Require a `ticket_id` argument.
* Are also gated by the agent's `before_tool_callback` (see hitl.py) so the
  ticket is verified against `tool_context.state` before the bridge is hit.

The factory keeps the dynamic surface tiny — it doesn't try to map JSON Schema
into Python type hints. Instead, callables accept `**kwargs` and the JSON
schema from the MCP server is surfaced in the docstring; ADK's function-tool
introspection still produces a usable FunctionDeclaration because we set the
`__doc__` and an explicit name.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from google.adk.tools import FunctionTool

from .hitl import Classification
from .mcp_client import MCPHTTPClient, ToolSpec


def _safe_call(client: MCPHTTPClient, name: str, arguments: dict[str, Any]) -> Any:
    """Wrap MCP errors as a structured response the LLM can reason about."""
    try:
        return client.call_tool(name, arguments)
    except Exception as exc:  # noqa: BLE001 - we want to surface every error
        return {
            "status": "error",
            "tool": name,
            "error": str(exc),
        }


def _format_schema_doc(schema: dict[str, Any]) -> str:
    if not schema:
        return "No input schema declared."
    try:
        return json.dumps(schema, indent=2, sort_keys=True)
    except (TypeError, ValueError):
        return repr(schema)


def _make_read_only_tool(client: MCPHTTPClient, spec: ToolSpec) -> FunctionTool:
    name = spec.name

    def _impl(**kwargs: Any) -> Any:
        return _safe_call(client, name, kwargs)

    _impl.__name__ = name
    _impl.__doc__ = (
        f"{spec.description}\n\n"
        f"This is a READ-ONLY MCP tool exposed by the Trade Blotter bridge. "
        f"It is safe to call without human approval.\n\n"
        f"Input schema (JSON Schema):\n{_format_schema_doc(spec.input_schema)}"
    )
    return FunctionTool(func=_impl)


def _make_execute_tool(client: MCPHTTPClient, spec: ToolSpec) -> FunctionTool:
    """Build an `execute_<tool>` FunctionTool requiring a ticket_id."""
    target = spec.name
    wrapper_name = f"execute_{target}"

    def _impl(ticket_id: str, **kwargs: Any) -> Any:
        # Drop ticket_id before forwarding to the MCP bridge — it isn't part
        # of the underlying tool's schema.
        if not ticket_id:
            return {
                "status": "rejected",
                "reason": "ticket_id is required.",
                "tool": wrapper_name,
            }
        return _safe_call(client, target, kwargs)

    _impl.__name__ = wrapper_name
    _impl.__doc__ = (
        f"EXECUTE the mutating MCP tool `{target}` after a human reviewer has "
        f"approved it.\n\n"
        f"You MUST call `request_trade_action(tool='{target}', arguments=..., "
        f"rationale=...)` first. When the runner returns a FunctionResponse "
        f"with status 'approved', call this tool, passing the returned "
        f"`ticketId` as `ticket_id` plus the same arguments you passed to "
        f"`request_trade_action`.\n\n"
        f"Underlying tool description: {spec.description or '(none)'}\n\n"
        f"Underlying input schema (JSON Schema):\n"
        f"{_format_schema_doc(spec.input_schema)}\n\n"
        f"Args:\n"
        f"    ticket_id: The approved ticket id from request_trade_action.\n"
        f"    **kwargs: Forwarded to the MCP `{target}` tool."
    )
    return FunctionTool(func=_impl)


def build_tools(
    client: MCPHTTPClient,
    classification: Classification,
) -> tuple[list[FunctionTool], list[str], list[str]]:
    """Discover MCP tools and build matching ADK FunctionTools.

    Returns:
        (tools, read_only_names, mutating_names)

        * tools: the FunctionTool instances ready to attach to the agent.
        * read_only_names: MCP tool names exposed directly.
        * mutating_names: MCP tool names exposed as execute_<name> wrappers.
    """
    specs = client.list_tools()
    tools: list[FunctionTool] = []
    read_only: list[str] = []
    mutating: list[str] = []

    for spec in specs:
        kind = classification.classify(spec.name)
        if kind == "read_only":
            tools.append(_make_read_only_tool(client, spec))
            read_only.append(spec.name)
        else:
            tools.append(_make_execute_tool(client, spec))
            mutating.append(spec.name)

    return tools, read_only, mutating
