"""ADK FunctionTools that call the Trade REST API directly (authorized, read-only)."""

from __future__ import annotations

import json
from typing import Any

from google.adk.tools import FunctionTool

from .trade_api_client import TradeAPIHTTPClient


def _wrap(exc: Exception, tool: str) -> dict[str, Any]:
    return {"status": "error", "tool": tool, "error": str(exc)}


def build_direct_trade_api_tools(api: TradeAPIHTTPClient) -> list[FunctionTool]:
    """Build ``trade_api_*`` tools sharing one HTTP client."""

    def trade_api_health() -> Any:
        """Check Trade Blotter REST API health (GET /health). Same service MCP uses."""
        try:
            return api.health()
        except Exception as exc:  # noqa: BLE001
            return _wrap(exc, "trade_api_health")

    def trade_api_list_views() -> Any:
        """List trade views from the Trade API (GET /v1/api/trade-blotter/trade-views)."""
        try:
            return api.list_trade_views()
        except Exception as exc:  # noqa: BLE001
            return _wrap(exc, "trade_api_list_views")

    def trade_api_get_view(
        view_id: str,
        include_schema: bool = True,
        filters_json: str = "{}",
    ) -> Any:
        """Fetch one view's schema and data with optional filters (query params).

        Args:
            view_id: View UUID.
            include_schema: Whether to include field schema in the response.
            filters_json: JSON object of filter key/value strings, e.g. '{"Status":"Ins"}'.
        """
        try:
            filters: dict[str, str] = {}
            if filters_json and filters_json.strip() not in ("", "{}"):
                parsed = json.loads(filters_json)
                if isinstance(parsed, dict):
                    filters = {str(k): str(v) for k, v in parsed.items()}
            return api.get_trade_view(
                view_id,
                include_schema=include_schema,
                filters=filters or None,
            )
        except Exception as exc:  # noqa: BLE001
            return _wrap(exc, "trade_api_get_view")

    trade_api_health.__doc__ = (
        "Call the Trade Blotter REST API GET /health. "
        "Uses the same base URL and authorization as the MCP server (Bearer / OAuth)."
    )
    trade_api_list_views.__doc__ = (
        "Call GET /v1/api/trade-blotter/trade-views. "
        "Prefer this or MCP list_trade_views when you need the raw API payload."
    )
    trade_api_get_view.__doc__ = (
        "Call GET /v1/api/trade-blotter/trade-views/{view_id} with optional filters. "
        "Pass filters as a JSON string of string values matching view fields."
    )

    return [
        FunctionTool(func=trade_api_health),
        FunctionTool(func=trade_api_list_views),
        FunctionTool(func=trade_api_get_view),
    ]


DIRECT_TRADE_TOOL_NAMES = (
    "trade_api_health",
    "trade_api_list_views",
    "trade_api_get_view",
)
