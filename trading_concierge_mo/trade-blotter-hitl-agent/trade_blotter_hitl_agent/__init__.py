"""Trade Blotter HITL agent — ADK package.

`adk run trade_blotter_hitl_agent` and `adk web` import `agent.py` directly
and pick up the module-level `root_agent`. We deliberately *don't* eagerly
import `.agent` here because that pulls in `google.adk` and runs the MCP
discovery step at import time, which is undesirable in tests and during
tooling that just wants to inspect `mcp_client` / `hitl` / `tool_factory`.

Use `from trade_blotter_hitl_agent.agent import root_agent, build_root_agent`
when you actually want the agent; or rely on ADK to do it for you.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = ["root_agent", "build_root_agent"]


def __getattr__(name: str) -> Any:  # PEP 562 lazy attribute access
    if name in {"root_agent", "build_root_agent"}:
        from . import agent as _agent

        return getattr(_agent, name)
    raise AttributeError(name)


if TYPE_CHECKING:  # pragma: no cover
    from .agent import build_root_agent, root_agent  # noqa: F401
