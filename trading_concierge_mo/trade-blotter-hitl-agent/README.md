# Trade Blotter HITL Agent

Google **ADK** agent that uses the Trade Blotter MCP server via the HTTP bridge
(`mcp_http_server.py`). Read-only tools run immediately; mutating tools require
human approval (`request_trade_action` → `execute_*`, with a `before_tool_callback`
ticket check).

An **A2A HTTP API** (FastAPI) runs in the same container on port **8100** for
planning, classification, and validation—used by the desktop app.

At **startup**, the agent loads a **skills bundle** into its system instruction:
all MCP **resources** (full text), **prompt** templates (via the bridge), **tool**
schemas, plus `assets/includes/desktop_copilot_policy.md` (same file the desktop
prepends to the Gemini prompt). Optionally set `HITL_WRITE_SKILLS_SNAPSHOT=true`
to write the compiled markdown to `assets/cache/compiled_skills.md` for inspection.

## Run with Docker Compose (only supported path)

From **`tradeBlotterMCPAgent/`** (parent of this folder):

```bash
export GOOGLE_API_KEY=...   # or set in a `.env` next to docker-compose.yml
docker compose up --build
```

No install or manual bridge step is required: `trade-api` → `mcp-server` → this
agent and `desktop-app` start in order on the `mcp-trade-blotter` network.

| URL (host) | Service |
|------------|---------|
| http://localhost:8200 | ADK web UI (`adk web`) |
| http://localhost:8100 | A2A JSON API (`/health`, `/v1/a2a/...`) |
| http://localhost:5173 | Desktop app (chat + HITL tab) |

Stop only this service:

```bash
docker compose stop trade-blotter-hitl-agent
```

### Environment (set in compose or host `.env`)

| Variable | Default (in compose) | Meaning |
|----------|----------------------|---------|
| `MCP_BRIDGE_URL` | `http://mcp-server:7001` | MCP HTTP bridge inside the stack |
| `GOOGLE_API_KEY` / `GEMINI_API_KEY` | from host | Gemini for ADK and A2A |
| `ADK_MODEL` | `gemini-3.1-pro-preview` | Model name |
| `A2A_PORT` | `8100` | A2A listener |
| `A2A_ENABLED` | `true` | Set `false` to skip the sidecar API |
| `MCP_BRIDGE_WAIT_SECONDS` | `120` | Entrypoint polls bridge `/health` |
| `TOOL_CLASSIFICATION_PATH` | `/app/assets/tool_classification.yaml` | Read-only vs mutating rules |
| `HITL_FAIL_CLOSED` | `true` | Unknown tools treated as mutating |
| `HITL_SKILLS_MAX_CHARS` | `120000` | Cap on injected skills digest (`0` = unlimited) |
| `HITL_WRITE_SKILLS_SNAPSHOT` | `false` | Write compiled digest to `HITL_SKILLS_SNAPSHOT_PATH` |
| `TRADE_API_BASE_URL` | `http://trade-api:8000` | REST API for **`trade_api_*`** direct tools |
| `TRADE_API_DIRECT_TOOLS` | `true` | Register `trade_api_health`, `trade_api_list_views`, `trade_api_get_view` |
| `TRADE_API_BEARER_TOKEN` | (unset) | Optional static Bearer for secured Trade API |
| `MX_*` / `MX_LOAD_BALANCER_URL` | (unset) | Murex OAuth (same flow as `mcp/token_manager`) when API is not local mock |

See `.env.example` for variable names when tuning a compose override.

### Inspect bridge tools from the running container

```bash
docker compose exec trade-blotter-hitl-agent trade-blotter-list-tools
```

## HITL flow (short)

1. Model calls `request_trade_action` with tool name + arguments → runner pauses.
2. Human approves in the ADK UI (or the desktop chat gate for mutating tools).
3. Model calls `execute_<tool>` with the same arguments and `ticket_id`.
4. `before_tool_callback` rejects mismatched or unapproved tickets.

**Limits:** HITL reduces accidental writes; humans must still review payloads.
It does not replace authn/z on the bridge or trade API.

## Layout

```
trade-blotter-hitl-agent/
├── Dockerfile
├── docker/entrypoint.sh
├── pyproject.toml
├── .env.example
├── SKILL.md
├── assets/
│   ├── tool_classification.yaml
│   ├── includes/
│   │   ├── desktop_copilot_policy.md   # tool/JSON rules (also prepended in desktop Gemini)
│   │   └── desktop_stack_behaviour.md  # server.js + app.js behaviour mirror
│   └── cache/
├── trade_blotter_hitl_agent/
│   ├── agent.py
│   ├── a2a_app.py
│   ├── skills_builder.py
│   ├── trade_api_client.py
│   ├── direct_trade_tools.py
│   ├── murex_auth.py
│   ├── mcp_client.py
│   ├── tool_factory.py
│   ├── hitl.py
│   ├── prompts.py
│   ├── config.py
│   └── scripts_entry.py
└── tests/
```

The merged `docker-compose.yml` lives in the parent directory.

## Tests (contributors, local checkout)

```bash
cd trade-blotter-hitl-agent
pip install -e '.[dev]'
pytest -q
```
