"""Compile MCP resources, prompts, tool metadata, and desktop-aligned policy for HITL.

The digest is injected into the ADK agent instruction so the model internalizes
everything the MCP server advertises (resources, prompt templates, tool schemas)
plus the desktop app's tool-selection policy.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from .mcp_client import MCPHTTPClient, ToolSpec

logger = logging.getLogger(__name__)

_API_DOCS_HEADING = re.compile(r"^\s*#\s+Trade Blotter API Documentation", re.MULTILINE)

# Loaded in order into HITL instruction and (via Docker) prepended to desktop Gemini prompts.
_DESKTOP_SKILL_MARKDOWN_FILES: tuple[str, ...] = (
    "desktop_copilot_policy.md",
    "desktop_stack_behaviour.md",
)


def _load_desktop_skill_bundle(package_root: Path) -> str:
    """Concatenate packaged markdown skills that mirror server.js / app.js behaviour."""
    inc = package_root / "assets" / "includes"
    parts: list[str] = []
    for name in _DESKTOP_SKILL_MARKDOWN_FILES:
        path = inc / name
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8").strip())
        else:
            logger.warning("Desktop skill file missing: %s", path)
    if parts:
        return "\n\n---\n\n".join(parts)
    logger.warning("No desktop skill files under %s; using fallback blurb.", inc)
    return (
        "## Desktop copilot\n"
        "Mirror the desktop Gemini loop: JSON `{tool, arguments, message}` for tool "
        "calls; plain text otherwise. Ask for view_id when needed. "
        "ADK: use request_trade_action before execute_* for mutating tools."
    )


def _resource_body(data: dict[str, Any]) -> str:
    raw = data.get("content")
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        parts = []
        for item in raw:
            if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                parts.append(str(item["text"]))
        return "\n".join(parts)
    return json.dumps(raw, indent=2, ensure_ascii=False) if raw is not None else ""


def _strip_bridge_api_docs_preamble(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove duplicate api-docs system block the HTTP bridge prepends to prompts."""
    if not messages:
        return messages
    first = messages[0]
    if first.get("role") != "system":
        return messages
    content = first.get("content")
    text = ""
    if isinstance(content, dict):
        text = str(content.get("text", ""))
    elif isinstance(content, str):
        text = content
    if _API_DOCS_HEADING.search(text):
        return messages[1:]
    return messages


def _message_list_digest(messages: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content")
        text = ""
        if isinstance(content, str):
            text = content
        elif isinstance(content, dict):
            text = str(content.get("text", ""))
        lines.append(f"**{role}**: {text}")
    return "\n".join(lines)


def _placeholder_args_for_prompt(meta: dict[str, Any]) -> dict[str, str]:
    args: dict[str, str] = {}
    for spec in meta.get("arguments") or []:
        if not isinstance(spec, dict):
            continue
        name = spec.get("name")
        if not name:
            continue
        args[str(name)] = f"<{name}>"
    return args


def _format_tool_catalog(specs: list[ToolSpec]) -> str:
    blocks: list[str] = []
    for spec in specs:
        schema = json.dumps(spec.input_schema, indent=2, sort_keys=True) if spec.input_schema else "{}"
        blocks.append(
            f"### `{spec.name}`\n{spec.description or '_No description._'}\n\n"
            f"Input schema:\n```json\n{schema}\n```\n"
        )
    return "\n".join(blocks)


def compile_hitl_skills_digest(
    client: MCPHTTPClient,
    *,
    package_root: Path,
    max_chars: int | None = 120_000,
) -> str:
    """Fetch MCP surface + desktop policy; return one markdown string for the system prompt."""
    sections: list[str] = [
        "# Compiled skills (MCP + desktop policy)\n",
        "The following was loaded from the live MCP HTTP bridge and packaged skills files.\n",
    ]

    # --- Resources ---
    res_lines: list[str] = ["## MCP resources\n"]
    try:
        resources = client.list_resources()
    except Exception as exc:  # noqa: BLE001
        res_lines.append(f"_Could not list resources: {exc}_\n")
        resources = []

    for r in resources:
        uri = r.get("uri") or r.get("name") or ""
        name = r.get("name") or uri
        desc = r.get("description", "")
        res_lines.append(f"### {name}\n- URI: `{uri}`\n- {desc}\n")
        if not uri:
            continue
        try:
            payload = client.read_resource(str(uri))
            body = _resource_body(payload)
            res_lines.append(body + "\n")
        except Exception as exc:  # noqa: BLE001
            res_lines.append(f"_Failed to read resource: {exc}_\n")

    sections.append("\n".join(res_lines))

    # --- Prompts (metadata + template samples) ---
    pr_lines: list[str] = ["## MCP prompts (templates)\n"]
    try:
        prompts = client.list_prompts()
    except Exception as exc:  # noqa: BLE001
        pr_lines.append(f"_Could not list prompts: {exc}_\n")
        prompts = []

    for p in prompts:
        pname = p.get("name", "")
        pdesc = p.get("description", "")
        pr_lines.append(f"### Prompt `{pname}`\n{pdesc}\n")
        args_schema = p.get("arguments") or []
        if args_schema:
            pr_lines.append("Arguments:\n```json\n" + json.dumps(args_schema, indent=2) + "\n```\n")
        if not pname:
            continue
        try:
            sample_args = _placeholder_args_for_prompt(p)
            result = client.get_prompt(pname, sample_args)
            messages = result.get("messages") if isinstance(result, dict) else None
            if isinstance(messages, list):
                cleaned = _strip_bridge_api_docs_preamble(messages)
                pr_lines.append(_message_list_digest(cleaned) + "\n")
        except Exception as exc:  # noqa: BLE001
            pr_lines.append(f"_Could not fetch prompt template: {exc}_\n")

    sections.append("\n".join(pr_lines))

    # --- Tools (schemas; complements ADK tool declarations) ---
    try:
        tool_specs = client.list_tools()
    except Exception as exc:  # noqa: BLE001
        tool_specs = []
        sections.append(f"## MCP tools\n_Could not list tools: {exc}_\n")
    if tool_specs:
        sections.append("## MCP tools (reference)\n" + _format_tool_catalog(tool_specs))

    # --- Desktop policy + server.js / app.js behaviour (packaged markdown) ---
    sections.append("## Desktop app alignment (full stack)\n" + _load_desktop_skill_bundle(package_root))

    out = "\n\n".join(s for s in sections if s.strip())
    if max_chars is not None and len(out) > max_chars:
        out = (
            out[: max_chars - 120]
            + "\n\n… **(truncated)** — raise HITL_SKILLS_MAX_CHARS if the full digest is required.\n"
        )
    logger.info("Compiled HITL skills digest: %d characters", len(out))
    return out


def maybe_write_skills_snapshot(digest: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(digest, encoding="utf-8")
    logger.info("Wrote skills snapshot to %s", path)
