"""Human-in-the-loop building blocks.

The ADK pattern (see google/adk-python `contributing/samples/human_in_loop`):

* Define a function that returns a *pending* status, e.g.
    {"status": "pending", "ticketId": "..."}.
* Wrap it with `LongRunningFunctionTool`.
* The runner pauses after the LLM calls it. The host application surfaces the
  pending request to a human, then responds with a `FunctionResponse`
  containing the approval verdict (approved / rejected). The agent then
  decides whether to call the corresponding `execute_*` tool.

This module:

* Loads the tool classification YAML.
* Provides `classify(name)` -> "read_only" | "mutating".
* Provides `make_request_approval_tool()` — a factory that returns a single
  `LongRunningFunctionTool` named `request_trade_action` that the agent uses
  to request approval for any mutating MCP tool.
* Provides `before_tool_callback_factory(...)` — a defence-in-depth callback
  installed on the agent that refuses any `execute_*` call whose ticket has
  not been approved.
"""

from __future__ import annotations

import fnmatch
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml
from google.adk.tools.long_running_tool import LongRunningFunctionTool
from google.adk.tools.tool_context import ToolContext


logger = logging.getLogger(__name__)


APPROVAL_STATE_KEY = "trade_blotter_hitl.tickets"
"""Key under `tool_context.state` where approved tickets are tracked."""


# --------------------------------------------------------------------------- #
# Classification
# --------------------------------------------------------------------------- #

DEFAULT_CLASSIFICATION: dict[str, list[str]] = {
    "read_only": [
        "trade_api_*",
        "check_*",
        "list_*", "get_*", "search_*", "read_*", "describe_*",
        "fetch_*", "show_*", "find_*", "lookup_*", "query_*",
        "health", "ping",
    ],
    "mutating": [
        "place_*", "submit_*", "cancel_*", "amend_*", "modify_*",
        "delete_*", "create_*", "update_*", "set_*", "execute_*",
        "approve_*", "reject_*", "transfer_*", "trade_*",
    ],
}


@dataclass(slots=True)
class Classification:
    """Loaded classification rules."""

    read_only: tuple[str, ...]
    mutating: tuple[str, ...]
    fail_closed: bool

    def classify(self, tool_name: str) -> str:
        for pattern in self.read_only:
            if fnmatch.fnmatchcase(tool_name, pattern):
                return "read_only"
        for pattern in self.mutating:
            if fnmatch.fnmatchcase(tool_name, pattern):
                return "mutating"
        return "mutating" if self.fail_closed else "read_only"


def load_classification(path: Path | None, *, fail_closed: bool) -> Classification:
    """Load classification rules from YAML; fall back to defaults if missing."""
    data: dict[str, Any] = {}
    if path is not None and path.exists():
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to load classification %s: %s", path, exc)
            data = {}

    read_only = tuple(data.get("read_only") or DEFAULT_CLASSIFICATION["read_only"])
    mutating = tuple(data.get("mutating") or DEFAULT_CLASSIFICATION["mutating"])
    fail_closed = bool(data.get("fail_closed", fail_closed))
    return Classification(read_only=read_only, mutating=mutating, fail_closed=fail_closed)


# --------------------------------------------------------------------------- #
# Approval ticket bookkeeping
# --------------------------------------------------------------------------- #

def _tickets(tool_context: ToolContext) -> dict[str, dict[str, Any]]:
    state = tool_context.state
    tickets = state.get(APPROVAL_STATE_KEY)
    if not isinstance(tickets, dict):
        tickets = {}
        state[APPROVAL_STATE_KEY] = tickets
    return tickets


def record_pending_ticket(
    tool_context: ToolContext,
    *,
    tool: str,
    arguments: dict[str, Any],
) -> str:
    """Create and store a pending approval ticket; return the ticket id."""
    tickets = _tickets(tool_context)
    ticket_id = f"tb-{uuid.uuid4().hex[:8]}"
    tickets[ticket_id] = {
        "status": "pending",
        "tool": tool,
        "arguments": arguments,
    }
    tool_context.state[APPROVAL_STATE_KEY] = tickets
    return ticket_id


def lookup_ticket(tool_context: ToolContext, ticket_id: str) -> dict[str, Any] | None:
    return _tickets(tool_context).get(ticket_id)


def mark_ticket(tool_context: ToolContext, ticket_id: str, status: str) -> None:
    """Used by tests / manual flows to flip a ticket to `approved` / `rejected`."""
    tickets = _tickets(tool_context)
    if ticket_id in tickets:
        tickets[ticket_id]["status"] = status
        tool_context.state[APPROVAL_STATE_KEY] = tickets


# --------------------------------------------------------------------------- #
# The `request_trade_action` LongRunningFunctionTool
# --------------------------------------------------------------------------- #

def make_request_approval_tool(mutating_tool_names: Iterable[str]) -> LongRunningFunctionTool:
    """Build the approval-request LongRunningFunctionTool.

    The function signature is intentionally generic so it works for any MCP
    tool. The agent passes the target tool name and the arguments it would
    use; the runner pauses; a human responds with a FunctionResponse whose
    payload should look like:

        {"status": "approved" | "rejected",
         "ticketId": "tb-xxxx",
         "tool": "<name>",
         "arguments": {...}}
    """
    allowed = sorted(set(mutating_tool_names))
    allowed_list = ", ".join(allowed) or "(no mutating tools were discovered)"

    def request_trade_action(
        tool: str,
        arguments: dict[str, Any],
        rationale: str,
        tool_context: ToolContext,
    ) -> dict[str, Any]:
        f"""Request human approval for a mutating Trade Blotter MCP tool.

        Use this **before** calling any execute_* tool. The runner will pause
        and surface this request to a human reviewer; their FunctionResponse
        decides whether you may proceed.

        Args:
            tool: Name of the MCP tool the user wants to run. Must be one of:
                {allowed_list}.
            arguments: Arguments for the MCP tool, exactly as you would pass
                them to execute_<tool>.
            rationale: One-sentence justification shown to the human reviewer.

        Returns:
            A dict with `status: "pending"` and a `ticketId` to reference once
            the approval verdict comes back.
        """
        if tool not in allowed:
            return {
                "status": "rejected",
                "reason": (
                    f"Tool '{tool}' is not classified as mutating. Either it "
                    "doesn't exist on the bridge or it's already a read-only "
                    "tool you can call directly."
                ),
                "allowed": allowed,
            }
        ticket_id = record_pending_ticket(tool_context, tool=tool, arguments=arguments)
        return {
            "status": "pending",
            "ticketId": ticket_id,
            "tool": tool,
            "arguments": arguments,
            "rationale": rationale,
        }

    # Reset the docstring without the f-string template noise so ADK uses a
    # clean description for the FunctionDeclaration.
    request_trade_action.__doc__ = (
        "Request human approval for a mutating Trade Blotter MCP tool. "
        "Use this BEFORE calling any execute_* tool. The runner pauses and "
        "surfaces this request to a human reviewer; their FunctionResponse "
        "decides whether you may proceed.\n\n"
        f"Allowed `tool` values: {allowed_list}.\n\n"
        "Args:\n"
        "    tool: Name of the MCP tool to run.\n"
        "    arguments: Arguments for the MCP tool (same shape as execute_<tool>).\n"
        "    rationale: One-sentence justification shown to the reviewer.\n\n"
        "Returns: {status: 'pending', ticketId, tool, arguments, rationale}."
    )
    return LongRunningFunctionTool(func=request_trade_action)


# --------------------------------------------------------------------------- #
# before_tool_callback: defence in depth
# --------------------------------------------------------------------------- #

def before_tool_callback_factory(
    classification: Classification,
    execute_prefix: str = "execute_",
):
    """Return an ADK before_tool_callback that blocks unapproved execute_* calls.

    The factory captures the classification so we can decide which tools need a
    matching approved ticket. Read-only tools are always allowed through.
    """

    def before_tool_callback(*, tool, args, tool_context: ToolContext, **_):
        name = getattr(tool, "name", "") or ""
        # Allow the approval-request tool itself.
        if name == "request_trade_action":
            return None

        # If the tool isn't an `execute_*` wrapper, classify by raw name.
        target = name[len(execute_prefix):] if name.startswith(execute_prefix) else name
        kind = classification.classify(target)
        if kind == "read_only":
            return None

        # Mutating tool: require a matching approved ticket.
        ticket_id = (args or {}).get("ticket_id") or (args or {}).get("ticketId")
        if not ticket_id:
            return {
                "status": "rejected",
                "reason": (
                    "Refusing to call mutating tool without a ticket_id. "
                    "Call request_trade_action first and pass the returned "
                    "ticketId as ticket_id."
                ),
                "tool": name,
            }
        ticket = lookup_ticket(tool_context, ticket_id)
        if not ticket:
            return {
                "status": "rejected",
                "reason": f"No such ticket: {ticket_id}",
                "tool": name,
            }
        if ticket.get("status") != "approved":
            return {
                "status": "rejected",
                "reason": f"Ticket {ticket_id} is {ticket.get('status')!r}, not approved.",
                "tool": name,
            }
        if ticket.get("tool") != target:
            return {
                "status": "rejected",
                "reason": (
                    f"Ticket {ticket_id} was approved for tool "
                    f"{ticket.get('tool')!r}, not {target!r}."
                ),
                "tool": name,
            }
        return None  # proceed to actually execute

    return before_tool_callback
