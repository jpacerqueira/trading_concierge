
## Testing Without AI Assistant

You can test the MCP server directly using the MCP Inspector:

```bash
# Install MCP Inspector
npm install -g @modelcontextprotocol/inspector

# Run inspector
mcp-inspector python mcp_auth_server.py
```

This opens a web interface where you can:
- Call tools manually
- Read resources
- Test prompts
- See request/response data

## Architecture Overview

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│   DesktopApp    │  stdio  │   MCP Server     │  HTTP   │  FastAPI Server │
│ Claude Desktop  │◄───────►│ (mcp_auth_       │◄───────►│ (simple_api_    │
│                 │   MCP   │  server.py)      │ REST API│  server.py)     │
│   AI Assistant  │ Protocol│                  │         │                 │
│                 │         │ • Tools          │         │ • /auth         │
│                 │   MCP   │ • Resources      │         │ • /userInfo     │
│                 │  http   │ • Prompts        │         │ • /logout       │
│                 │         │ • Session State  │         │ • /health       │
│                 │         │ • API  services  │         │ • /trade{apis*} │
└─────────────────┘         └──────────────────┘         └─────────────────┘
```
