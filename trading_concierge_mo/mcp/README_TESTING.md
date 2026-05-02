# MCP Server Testing Guide

## Overview
This guide covers setup, automated tests, and manual validation for the Trade Blotter MCP Server.

## Prerequisites
- Python 3.10+
- Node.js 18+ (for standalone MCP testing)
- Trade Blotter API running on http://localhost:8000

## Initial Installation

### 1. Install Python Dependencies
```bash
cd mcp
pip install -r requirements.txt
```

### 2. Configure Environment
Create a `.env` file in the `mcp` directory:
```
TRADE_API_BASE_URL=http://localhost:8000
```

### 3. Start Trade Blotter API
```bash
cd ../tradeQueryApi
uvicorn main:app --reload
```

## Automated Tests

### Run All Tests
```bash
pytest tests/test_positive.py -v
```

### Run Specific Test
```bash
pytest tests/test_positive.py::test_list_tools -v
```

### Run with Coverage
```bash
pytest tests/test_positive.py --cov=mcp_server --cov-report=html
```

### Expected Results
All 15 tests should pass:
- 3 tests for listing capabilities (tools, resources, prompts)
- 3 tests for reading resources
- 6 tests for tool invocations
- 3 tests for prompt generation

## Manual Validation Steps

### Step 1: Test MCP Server Connection
```bash
python mcp_client.py
```

**Expected Output:**
- Connection confirmation
- List of 4 tools
- List of 3 resources
- List of 3 prompts
- Health check result
- Trade views list

### Step 2: Test with MCP Inspector (Node.js)
```bash
npx @modelcontextprotocol/inspector python mcp_server.py
```

**Validation:**
1. Open browser to http://localhost:5173
2. Verify server connects successfully
3. Navigate to Resources tab - should show 3 resources
4. Navigate to Tools tab - should show 4 tools
5. Navigate to Prompts tab - should show 3 prompts

### Step 3: Test Individual Tools

#### Test Health Check
```bash
# In MCP Inspector, call tool:
Tool: check_service_health
Arguments: {}
```
**Expected:** JSON with status, timestamp, version

#### Test List Views
```bash
Tool: list_trade_views
Arguments: {}
```
**Expected:** JSON array with view definitions

#### Test Get Schema
```bash
Tool: get_view_schema
Arguments: {"view_id": "daily-basic"}
```
**Expected:** Schema object with fields array

#### Test Query Trades
```bash
Tool: query_trades
Arguments: {"view_id": "daily-basic", "filters": {"TradeStatus": "ACTIVE"}}
```
**Expected:** JSON with data array of trades

### Step 4: Test Resources

#### Read API Documentation
```bash
Resource URI: resource://trade-blotter/api-docs
```
**Expected:** Markdown with view descriptions and filtering info

#### Read Glossary
```bash
Resource URI: resource://trade-blotter/glossary
```
**Expected:** Markdown with trading terms definitions

#### Read View Guide
```bash
Resource URI: resource://trade-blotter/view-guide
```
**Expected:** Markdown with decision tree for view selection

### Step 5: Test Prompts

#### Analyze Trade Query
```bash
Prompt: analyze_trade_query
Arguments: {"user_question": "Show me recent FX trades"}
```
**Expected:** Multi-step workflow instructions

#### Validate Filter Criteria
```bash
Prompt: validate_filter_criteria
Arguments: {"view_id": "daily-basic", "requested_filters": "{'ProductType': 'FX'}"}
```
**Expected:** Validation workflow instructions

#### Explain Trade Data
```bash
Prompt: explain_trade_data
Arguments: {"trade_records": "[{...}]"}
```
**Expected:** Summary generation instructions

## Integration with Claude Desktop

### Configuration
Add to Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):
```json
{
  "mcpServers": {
    "trade-blotter": {
      "command": "python",
      "args": ["/absolute/path/to/mcp/mcp_server.py"],
      "env": {
        "TRADE_API_BASE_URL": "http://localhost:8000"
      }
    }
  }
}
```

### Restart Claude Desktop
Close and reopen Claude Desktop to load the MCP server.

### Test in Claude
Ask Claude:
- "Check if the trade blotter service is available"
- "List all available trade views"
- "Get the schema for daily-basic view"
- "Show me all active trades"
- "Show me recent FX trades"

## Troubleshooting

### Server Won't Start
- Verify Python dependencies installed: `pip list | grep mcp`
- Check Trade API is running: `curl http://localhost:8000/health`
- Review environment variables in `.env`

### Tests Failing
- Ensure Trade API is running before tests
- Check API has sample data loaded
- Verify network connectivity to localhost:8000

### MCP Inspector Can't Connect
- Verify Node.js version: `node --version` (should be 18+)
- Check firewall settings
- Try different port: `npx @modelcontextprotocol/inspector python mcp_server.py --port 5174`

### Claude Desktop Not Showing Tools
- Verify config file path is correct
- Check absolute paths in configuration
- Review Claude Desktop logs: `~/Library/Logs/Claude/`

## Test Coverage

| Component | Coverage |
|-----------|----------|
| Tools | 4/4 (100%) |
| Resources | 3/3 (100%) |
| Prompts | 3/3 (100%) |
| Error Handling | Partial |
| Integration | Manual |

## Next Steps
- Add negative test cases (invalid inputs)
- Implement timeout tests
- Add performance benchmarks
- Create integration test suite
