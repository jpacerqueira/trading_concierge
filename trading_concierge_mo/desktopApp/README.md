# Desktop App (Local Run)

Run the desktop-style MCP UI without containers.

The Gemini system prompt prepends **`../trade-blotter-hitl-agent/assets/includes/desktop_copilot_policy.md`** when that file exists (Docker copies it to `/app/hitl-policy/`). Edit that file to keep desktop and HITL behavior aligned.

## Prerequisites

- Node.js (LTS recommended)

Check your installation:

```
node --version
```

## Install dependencies

From the repo root:

```
cd desktopApp
npm install
```

## Start the app

```
npm start
```

The UI will be available at `http://localhost:5173`.

## Required backend services

The desktop app expects the MCP HTTP bridge to be reachable at:

```
http://localhost:7001
```

If you are running everything locally without Docker, start these in separate terminals:

```
cd tradeQueryApi
uvicorn main:app --host 0.0.0.0 --port 8000
```

```
cd mcp
uvicorn mcp_http_server:app --host 0.0.0.0 --port 7001
```

## Environment override

You can point the desktop app at a different MCP bridge with:

```
MCP_HTTP_BASE_URL=http://localhost:7001 npm start
```

## LLM (Gemini) usage with the desktop app

The desktop app is designed to work alongside an LLM that can interpret
natural-language trade queries and turn them into MCP tool calls. Gemini is the
recommended LLM for this MVP.

1. Configure Gemini in your shell (the server uses these to call Gemini):

```
export GEMINI_API_KEY=your_api_key
export GEMINI_INFERENCE_MODEL=gemini-3-flash-preview
```

2. Start the server and ask questions in the chat panel.

The app now calls Gemini directly from the server, then executes the selected
MCP tool and returns the result in the chat.

