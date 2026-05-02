"""HTTP client for the Trade Blotter REST API (same routes the MCP server calls)."""

from __future__ import annotations

import logging
from typing import Any, Mapping

import httpx

from .config import Settings
from .murex_auth import get_murex_access_token_sync

logger = logging.getLogger(__name__)


def _is_local_unauthenticated_trade_api(settings: Settings) -> bool:
    """Match mcp_server._is_mock_api heuristic for the hackathon stack."""
    if settings.use_mock_api:
        return True
    u = settings.trade_api_base_url.lower()
    return (
        "trade-api:8000" in u
        or "http://trade-api:" in u
        or "localhost" in u
        or "127.0.0.1" in u
    )


class TradeAPIError(RuntimeError):
    """Non-success response from Trade API."""


class TradeAPIHTTPClient:
    """Sync client for ``/health`` and trade-blotter view endpoints."""

    def __init__(self, settings: Settings) -> None:
        self._s = settings
        self._base = settings.trade_api_base_url.rstrip("/")
        self._client = httpx.Client(timeout=settings.trade_api_timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> TradeAPIHTTPClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {"Accept": "application/json"}
        if _is_local_unauthenticated_trade_api(self._s):
            return h
        if self._s.trade_api_bearer_token:
            h["Authorization"] = f"Bearer {self._s.trade_api_bearer_token}"
            return h
        tok = get_murex_access_token_sync(self._s)
        if tok:
            h["Authorization"] = f"Bearer {tok}"
        else:
            logger.warning(
                "Trade API may require auth: set TRADE_API_BEARER_TOKEN or full MX_* + "
                "MX_LOAD_BALANCER_URL for OAuth."
            )
        return h

    def _get(self, path: str, **kwargs: Any) -> Any:
        url = f"{self._base}{path}"
        resp = self._client.get(url, headers=self._headers(), **kwargs)
        if resp.status_code >= 400:
            raise TradeAPIError(f"GET {path} -> {resp.status_code}: {resp.text}")
        return resp.json()

    def health(self) -> dict[str, Any]:
        return self._get("/health")

    def list_trade_views(self) -> dict[str, Any]:
        return self._get("/v1/api/trade-blotter/trade-views")

    def get_trade_view(
        self,
        view_id: str,
        *,
        include_schema: bool = True,
        filters: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, str] = {"includeSchema": str(include_schema).lower()}
        if filters:
            params.update({k: str(v) for k, v in filters.items()})
        return self._get(f"/v1/api/trade-blotter/trade-views/{view_id}", params=params)
