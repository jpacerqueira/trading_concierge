## Desktop stack behaviour (server.js + app.js) — mirror for ADK

Use this to **predict how the Trade chat tab** behaves and to give operators the same
guidance they would get from the desktop UI. The **Human in the loop** tab embeds
**ADK web** (`adk web`); this document ties that UI to the Express + browser logic.

---

### Express server (`server.js`)

**Proxies MCP** — base URL `MCP_HTTP_BASE_URL` (default `http://mcp-server:7001`):

- `GET /api/health` → bridge `/health`
- `GET /api/tools`, `/api/resources`, `/api/prompts`
- `GET /api/resource?uri=`
- `POST /api/tool/:name` with JSON body (arguments at top level or under `arguments` per handler)
- `POST /api/prompt/:name`
- `POST /api/llm/gemini` — Gemini multi-step tool loop; may return **`needsApproval`**, **`resumeApprovalId`**, **`rejectApprovalId`**
- `POST /api/llm/summarize` — rolling summary for long chats
- `GET /api/config` — `hitlAdkWebUrl`, etc.
- `POST /api/hitl/plan`, `/api/hitl/classify`, `/api/hitl/validate_step`, `GET /api/hitl/skills` → HITL A2A container (`HITL_A2A_BASE_URL`, port **8100**)

**Tool classification (chat approval gate)** — same idea as `tool_classification.yaml`:

- Read-only glob examples: `check_*`, `list_*`, `get_*`, `query_*`, …
- Mutating: `place_*`, `cancel_*`, `submit_*`, `trade_*`, …
- `HITL_FAIL_CLOSED` env (default true): unknown tool names → treated as **mutating** → requires approval in chat before MCP execution.

**Gemini loop** — loads `analyze_trade_query` MCP prompt for context; max steps from `GEMINI_MAX_TOOL_STEPS` (default 5); high “thinking” for main calls.

Prepends **shared markdown skills** from `hitl-policy/*.md` (same files as HITL `assets/includes/`).

---

### Browser client (`public/app.js`)

**Tabs** — `Trade chat` vs `Human in the loop`:

- **Trade chat** — MCP panel, chat, **approval gate** for mutating tools, email preview, iterate hint.
- **Human in the loop** — iframe to ADK web (URL from `/api/config` `hitlAdkWebUrl`, default `http://localhost:8200`); **A2A** “Generate plan” / skills via `/api/hitl/*`.

**Chat flow** — `handleUserMessage` → `handleGeminiMessage` → `/api/llm/gemini` with last 10 turns + `chatSummary`.

- If response **`needsApproval`**: show **Approve mutating operation** panel (`approvalGate`) with tool + arguments JSON; user **Approve** → `resumeApprovalId`; **Reject** → `rejectApprovalId`.
- If Gemini errors: fallback **`handleMcpHeuristics`** (keyword routing, no LLM).

**Heuristic shortcuts** (fallback path, mirrors common intents):

| User message pattern | Action |
|---------------------|--------|
| contains `health` | `POST /api/tool/check_service_health` |
| `list views` / `trade views` / `views` | `list_trade_views` |
| `schema` | needs UUID in message → `get_view_schema` |
| `resource://...` in text | `GET /api/resource?uri=...` |
| `prompt` | `POST /api/prompt/analyze_trade_query` |
| `trade` / `trades` / `query` | needs UUID → `query_trades` with `extractFilters` key=value |
| else | `analyze_trade_query` prompt + guidance text |

**Helpers** — `extractViewId` (UUID regex), `extractFilters` (`Key=value`), `isJsonLikeResponse` controls **iterate hint**.

**Iterate hint** — shown when the last reply is not JSON-like: *“Multiple levels of reasoning, with you validating each step (man-in-the-middle).”* Button copies last assistant text into the composer.

**Email** — “Approve results for email” expects last assistant message parseable as JSON trade payload.

---

### How you (ADK) should use this

- When explaining what the **desktop** would do, reference this flow (JSON tool shape in Trade chat vs native tools here).
- **Planning / validation** in the HITL tab can use the same domain steps as MCP resources and prompts (list views → schema → query).
- Prefer **read-only** MCP tools first; **mutating** tools in ADK always go through `request_trade_action` + approved `execute_*`.
- **`trade_api_*` tools** call the **Trade REST API** directly (same `/v1/api/trade-blotter/...` as MCP) with **Bearer / Murex OAuth** when configured—use them to fetch views and data in one hop.
