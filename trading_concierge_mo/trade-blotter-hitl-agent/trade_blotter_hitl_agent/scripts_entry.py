"""Console-script entry points wired up in pyproject.toml."""

from __future__ import annotations

import json
import sys

from .config import settings
from .mcp_client import MCPHTTPClient


def list_tools_main() -> None:
    """Print the tools / resources / prompts exposed by the bridge."""
    with MCPHTTPClient(
        settings.mcp_bridge_url,
        timeout=settings.mcp_bridge_timeout,
        token=settings.mcp_bridge_token,
    ) as client:
        try:
            health = client.health()
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED: cannot reach bridge at {settings.mcp_bridge_url}: {exc}",
                  file=sys.stderr)
            sys.exit(1)

        print(f"# bridge: {settings.mcp_bridge_url}")
        print(f"# health: {health}")
        print()
        print("## tools")
        for spec in client.list_tools():
            print(f"- {spec.name}: {spec.description}")
        print()
        print("## resources")
        for r in client.list_resources():
            print("-", json.dumps(r, ensure_ascii=False))
        print()
        print("## prompts")
        for p in client.list_prompts():
            print("-", json.dumps(p, ensure_ascii=False))


if __name__ == "__main__":  # pragma: no cover
    list_tools_main()
