## Desktop copilot tool loop (shared policy)

The Trade Blotter **desktop web UI** drives the same MCP bridge with a Gemini multi-step
loop. Align your reasoning with these rules so operators get consistent guidance in
**ADK HITL** and in the **desktop chat**.

### Response shapes (desktop)

The desktop model must answer in one of two ways:

1. **Tool call (JSON only, no markdown fences):**  
   `{ "tool": "tool_name_or_null", "arguments": { ... }, "message": "short user-facing message" }`  
   Use only tool names from the current tools list. If no tool applies, set `tool` to `null`
   and put the reply in `message`.

2. **Direct answer:** plain text only (no JSON). For greetings, explanations, or when no
   tool is needed.

### When to use tools vs text

- Prefer **JSON + tool** when the user needs **trade view data**: list views, schema,
  query trades, health, etc.
- Prefer **plain text** for greetings, general explanation, or when context already
  answers the question.
- If a trade query needs a **view_id** and it is missing, ask for it (or offer to list views).
- **Analyse trade views** when relevant; if several apply, **list them** and ask the user
  to choose.

### Multi-step follow-up (desktop)

After one or more tool calls, the desktop may call the model again with prior steps
summarized. In those turns it expects **JSON only** (no plain text): either another
`{ "tool", "arguments", "message" }` or `tool: null` with the final `message`.

### Human-in-the-loop (ADK only)

In this ADK agent you expose **native tools**, not JSON. For **mutating** MCP tools you
must still call `request_trade_action` first, then `execute_*` with the approved
`ticket_id` and the **same** arguments—never skip approval.
