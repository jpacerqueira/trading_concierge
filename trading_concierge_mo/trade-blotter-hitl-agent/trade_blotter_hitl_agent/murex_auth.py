"""Synchronous Murex OAuth2 token for direct Trade API calls from the HITL agent.

Mirrors the two-step flow in ``mcp/token_manager.py`` (authorize + token exchange).
Use when ``TRADE_API_BASE_URL`` targets a secured Murex instance and
``TRADE_API_BEARER_TOKEN`` is not set.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timedelta
from typing import Any

import httpx

from .config import Settings

logger = logging.getLogger(__name__)

_cache: dict[str, Any] = {}


def _jwt_exp(token: str) -> datetime | None:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload = parts[1]
        pad = 4 - len(payload) % 4
        if pad != 4:
            payload += "=" * pad
        data = json.loads(base64.urlsafe_b64decode(payload))
        if "exp" in data:
            return datetime.fromtimestamp(int(data["exp"]))
    except Exception:  # noqa: BLE001
        return None
    return None


def _credentials_ok(s: Settings) -> bool:
    return bool(
        s.mx_username
        and s.mx_password
        and s.mx_group
        and s.mx_fo_desk
        and s.mx_load_balancer_url
    )


def get_murex_access_token_sync(settings: Settings) -> str | None:
    """Return a Bearer access token, or None if OAuth is not configured."""
    if not _credentials_ok(settings):
        return None
    now = datetime.now()
    tok = _cache.get("access_token")
    exp: datetime | None = _cache.get("exp")
    if tok and exp and exp > now + timedelta(minutes=2):
        return str(tok)

    lb = str(settings.mx_load_balancer_url).rstrip("/")
    verify = settings.mx_verify_ssl
    with httpx.Client(timeout=30.0, verify=verify) as client:
        auth_url = f"{lb}/v1/api/auth/authorize"
        r1 = client.post(
            auth_url,
            auth=(str(settings.mx_username), str(settings.mx_password)),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=(
                "scope=openid"
                "&response_type=code"
                "&client_id=external-client"
                "&redirect_uri=mx%3A//"
            ),
        )
        r1.raise_for_status()
        auth_code = r1.text

        token_url = f"{lb}/v1/api/auth/token"
        r2 = client.post(
            token_url,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Bearer {auth_code}",
            },
            data=(
                "grant_type=authorization_code"
                f"&mx_gp={settings.mx_group}&mx_fod={settings.mx_fo_desk}"
            ),
        )
        r2.raise_for_status()
        body = r2.json()
        access = body.get("access_token")
        if not access:
            logger.error("Murex token response missing access_token")
            return None
        _cache["access_token"] = access
        _cache["exp"] = _jwt_exp(str(access)) or (now + timedelta(minutes=25))
        logger.info("HITL obtained Murex access token for direct Trade API")
        return str(access)
