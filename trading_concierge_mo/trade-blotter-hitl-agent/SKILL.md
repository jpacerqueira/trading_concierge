---
name: trade-blotter-hitl-agent
description: Google ADK agent for the Trade Blotter MCP HTTP bridge with Human-in-the-Loop on mutating tools, plus an in-container A2A JSON API for planning and validation. Intended to run via Docker Compose with trade-api, mcp-server, and desktop-app—no separate local install of the bridge or agent.
license: Apache-2.0
compatibility: Docker Compose on the mcp-trade-blotter network (Python 3.11 image). Requires GOOGLE_API_KEY or GEMINI_API_KEY and a reachable MCP bridge at MCP_BRIDGE_URL (default http://mcp-server:7001 inside compose).
metadata:
  author: Joao Pedro Cerqueira - Beyond/Qodea - Google Partner
  version: "1.0.0"
  agent-framework: google-adk
  mcp-transport: http-bridge
  hitl-pattern: long-running-function-tool
allowed-tools: Read Edit Write Bash(docker:*)
---

# Trade Blotter HITL Agent skill

## What this does

- Discovers MCP tools from the HTTP bridge and classifies them with
  `assets/tool_classification.yaml`.
- Exposes read-only tools as normal ADK `FunctionTool`s; mutating tools as
  `execute_<name>` plus `request_trade_action` (`LongRunningFunctionTool`).
- Runs **`adk web`** (UI on host port **8200**) and a **FastAPI A2A** service
  (host **8100**) for peer agents / the desktop app (`/v1/a2a/plan`,
  `/v1/a2a/classify`, `/v1/a2a/validate_step`).
- On import, compiles **skills** from the live MCP bridge (resource bodies, prompt
  templates, tool JSON schemas) and `assets/includes/desktop_copilot_policy.md`
  (shared with the desktop Gemini prompt) into the ADK system instruction.

## When to use

- You need an audit-friendly blotter agent: every state-changing MCP call goes
  through explicit human approval in ADK (and optional gates in the desktop).
- The stack is already using `docker-compose.yml` with `mcp-server` and
  `trade-api`.

## Quick start (Compose only)

From the parent folder that contains `docker-compose.yml`:

```bash
export GOOGLE_API_KEY=...
docker compose up --build
```

- ADK UI: http://localhost:8200  
- A2A: http://localhost:8100/health  
- Desktop: http://localhost:5173 (HITL tab + chat approval for mutating tools)

Optional: list tools inside the running agent container:

```bash
docker compose exec trade-blotter-hitl-agent trade-blotter-list-tools
```

## Package layout

```
trade-blotter-hitl-agent/
├── SKILL.md
├── README.md
├── Dockerfile
├── docker/entrypoint.sh
├── pyproject.toml
├── .env.example
├── assets/
│   ├── tool_classification.yaml
│   └── includes/
│       ├── desktop_copilot_policy.md
│       └── desktop_stack_behaviour.md
├── trade_blotter_hitl_agent/
│   ├── agent.py
│   ├── a2a_app.py
│   ├── skills_builder.py
│   ├── mcp_client.py
│   ├── tool_factory.py
│   ├── hitl.py
│   ├── prompts.py
│   ├── config.py
│   └── scripts_entry.py
└── tests/
```

## HITL gate (summary)

Mutating tools require `request_trade_action` first; `execute_*` calls must
include an approved `ticket_id`. `before_tool_callback` enforces ticket match.

## Validation

```bash
pipx run skills-ref validate ./
cd trade-blotter-hitl-agent && pip install -e '.[dev]' && pytest -q
```
