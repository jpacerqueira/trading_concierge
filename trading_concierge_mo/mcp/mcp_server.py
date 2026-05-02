import asyncio
import logging
import os
import urllib3
from typing import Any, Optional
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, Tool, Prompt, TextContent, PromptMessage, GetPromptResult
import httpx
from dotenv import load_dotenv
from token_manager import TokenManager

load_dotenv(encoding="utf-8")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Suppress SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_BASE_URL = os.getenv("TRADE_API_BASE_URL", "http://trade-api:8000")
token_manager: Optional[TokenManager] = None

app = Server("trade-blotter-mcp")

def _is_mock_api() -> bool:
    """Check if using mock API based on configuration."""
    if os.getenv("USE_MOCK_API", "").lower() == "true":
        return True
    if "localhost" in API_BASE_URL.lower() or "127.0.0.1" in API_BASE_URL or "http://trade-api:8000" in API_BASE_URL:
        return True
    return False

async def _get_auth_headers_async() -> dict[str, str]:
    if _is_mock_api():
        return {}
    if token_manager is None:
        return {}
    try:
        token = await token_manager.get_valid_token()
        return {"Authorization": f"Bearer {token}"}
    except Exception:
        return {}

@app.list_resources()
async def list_resources() -> list[Resource]:
    return [
        Resource(
            uri="resource://trade-blotter/api-docs",
            name="Trade Blotter API Documentation",
            mimeType="text/markdown",
            description="Documentation for Trade Blotter API views and filtering"
        ),
        Resource(
            uri="resource://trade-blotter/glossary",
            name="Trading Glossary",
            mimeType="text/markdown",
            description="Trading terms and definitions"
        ),
        Resource(
            uri="resource://trade-blotter/view-guide",
            name="View Selection Guide",
            mimeType="text/markdown",
            description="Guide for selecting appropriate trade views"
        )
    ]

@app.read_resource()
async def read_resource(uri: str) -> str:
    uri_str = str(uri)

    if uri_str == "resource://trade-blotter/api-docs":
        return """# Trade Blotter API Documentation

## Views Available
- **MX-TradeBlotter**: Primary trade view with comprehensive deal information
- **Tests-Data-Default**: Used for testing purposes

## Common Fields

### Trade Identification
- **Trade nb**: Unique trade identifier
- **Contract nb**: Contract reference number
- **Package nb**: Package identifier
- **Status**: Status of the trade (Ins; Cncl;)

### Trade Details
- **Typology**: Trade type (Spot, Outright, etc.)
- **Instrument**: Currency pair also known as instrument (EUR/USD, USD/JPY, etc.)
- **BuySell**: Buy or Sell direction
- **Amount**: Trade amount/notional

### Pricing & Economics
- **DealPrice**: Trade price or rate
- **DealYield**: Yield of the trade (if applicable)
- **Face cur**: Face currency of the trade

### Dates & Status
- **Maturity**: Maturity or settlement date
- **Last event**: Most recent event (e.g., Cancel, Modify)
- **Status**: Trade status (Ins=Inserted, Cncl=Cancelled, Mod=Modified)
- **Version**: Version number of the trade

### Parties & Organization
- **Counterparty**: Trading counterparty (e.g., CITIBANK N A, ABN AMRO AMS)
- **Portfolio**: Portfolio code (e.g., FWD_EUR_LN, FXMM_TRADER1)
- **User**: User who entered/modified the trade (typically MUREXFO)

### Data Source
- **Source**: Data source (mx, REUTERS, BLOOMBERG FXGO, FXALL, etc.)
- **VirtualSelected**: Virtual selection flag (N=No)

## Filtering
Use query parameters to filter on any field above. Filters are case-sensitive exact matches.
Example: `?Typology=Spot&Status=Ins`

## Asset Classes (by Instrument)
- **FX Spot/Forward**: EUR/USD, GBP/USD, USD/JPY, USD/CHF, EUR/CHF, EUR/GBP, USD/CAD, EUR/CAD, USD/AED, USD/ZAR
"""

    elif uri_str == "resource://trade-blotter/glossary":
        return """# Trading Glossary

## Asset Classes
- **FX**: Foreign Exchange trades (currency pairs)
- **IRS**: Interest Rate Swaps
- **BOND**: Fixed income securities
- **EQUITY**: Stock/equity trades
- **FXFWD**: FX Forward contracts

## Trade Status
- **CLOSED**: Dead, Closed, Cancel, Cncl
- **Inserted**: Ins, New, Fresh, Alive

## Time References
- **TODAY**: Current Date time, in a field corresponding format (e.g.: 10-Jan-24)
- **T0**: Means Today
- **T-1**: Today -1 business day, as well may be T-n where N would be a number of business days
- **T+1**: Today +1 business day
"""

    elif uri_str == "resource://trade-blotter/view-guide":
        return """# View Selection Guide

## Decision Tree
1. **Need real data**
   - Yes → Use "MX" views
   - No → Use "Test" views
"""

    raise ValueError(f"Unknown resource: {uri_str}")

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="check_service_health",
            description="Check if Trade Blotter API service is available",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="list_trade_views",
            description="Get list of available trade views",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_view_schema",
            description="Get schema (field definitions) for a specific view",
            inputSchema={
                "type": "object",
                "properties": {
                    "view_id": {
                        "type": "string",
                        "description": "View identifier (UUID e.g., '8ff46242-dffa-447e-b221-8c328d785906')"
                    }
                },
                "required": ["view_id"]
            }
        ),
        Tool(
            name="query_trades",
            description="Query trades from a view with optional filters",
            inputSchema={
                "type": "object",
                "properties": {
                    "view_id": {
                        "type": "string",
                        "description": "View identifier"
                    },
                    "filters": {
                        "type": "object",
                        "description": "Filter criteria (e.g., {'Typology': 'Spot, Outright'})",
                        "additionalProperties": {"type": "string"}
                    },
                    "include_schema": {
                        "type": "boolean",
                        "description": "Include schema in response",
                        "default": False
                    }
                },
                "required": ["view_id"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    headers = await _get_auth_headers_async()
    async with httpx.AsyncClient(timeout=30.0, headers=headers, verify=False) as client:
        try:
            if name == "check_service_health":
                response = await client.get(f"{API_BASE_URL}/health")
                response.raise_for_status()
                return [TextContent(type="text", text=str(response.json()))]

            elif name == "list_trade_views":
                response = await client.get(f"{API_BASE_URL}/v1/api/trade-blotter/trade-views")
                if response.status_code == 401 and token_manager:
                    await token_manager.refresh_immediately()
                    headers = await _get_auth_headers_async()
                    async with httpx.AsyncClient(timeout=30.0, headers=headers, verify=False) as retry_client:
                        response = await retry_client.get(f"{API_BASE_URL}/v1/api/trade-blotter/trade-views")
                response.raise_for_status()
                return [TextContent(type="text", text=str(response.json()))]

            elif name == "get_view_schema":
                view_id = arguments["view_id"]
                response = await client.get(
                    f"{API_BASE_URL}/v1/api/trade-blotter/trade-views/{view_id}",
                    params={"includeSchema": "true"}
                )
                if response.status_code == 401 and token_manager:
                    await token_manager.refresh_immediately()
                    headers = await _get_auth_headers_async()
                    async with httpx.AsyncClient(timeout=30.0, headers=headers, verify=False) as retry_client:
                        response = await retry_client.get(
                            f"{API_BASE_URL}/v1/api/trade-blotter/trade-views/{view_id}",
                            params={"includeSchema": "true"}
                        )
                response.raise_for_status()
                data = response.json()
                schema_only = {"schema": data.get("schema", {})}
                return [TextContent(type="text", text=str(schema_only))]

            elif name == "query_trades":
                view_id = arguments["view_id"]
                filters = arguments.get("filters", {})
                include_schema = arguments.get("include_schema", False)

                params = {"includeSchema": str(include_schema).lower()}
                params.update(filters)

                response = await client.get(
                    f"{API_BASE_URL}/v1/api/trade-blotter/trade-views/{view_id}",
                    params=params
                )
                if response.status_code == 401 and token_manager:
                    await token_manager.refresh_immediately()
                    headers = await _get_auth_headers_async()
                    async with httpx.AsyncClient(timeout=30.0, headers=headers, verify=False) as retry_client:
                        response = await retry_client.get(
                            f"{API_BASE_URL}/v1/api/trade-blotter/trade-views/{view_id}",
                            params=params
                        )
                response.raise_for_status()
                return [TextContent(type="text", text=str(response.json()))]

            else:
                raise ValueError(f"Unknown tool: {name}")

        except httpx.HTTPError as e:
            return [TextContent(type="text", text=f"HTTP Error: {str(e)}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

@app.list_prompts()
async def list_prompts() -> list[Prompt]:
    return [
        Prompt(
            name="analyze_trade_query",
            description="Analyze and execute a natural language trade query",
            arguments=[
                {"name": "user_question", "description": "User's trade query", "required": True}
            ]
        ),
        Prompt(
            name="validate_filter_criteria",
            description="Validate filter parameters against view schema",
            arguments=[
                {"name": "view_id", "description": "View identifier", "required": True},
                {"name": "requested_filters", "description": "Filters to validate", "required": True}
            ]
        ),
        Prompt(
            name="explain_trade_data",
            description="Generate summary of trade data",
            arguments=[
                {"name": "trade_records", "description": "Trade records to summarize", "required": True}
            ]
        )
    ]

@app.get_prompt()
async def get_prompt(name: str, arguments: dict[str, str]) -> GetPromptResult:
    if name == "analyze_trade_query":
        user_question = arguments.get("user_question", "")
        message_text = f"""You are a trade data analyst. The user asked: What are EUR/USD

Steps:
1. Read the trading glossary to understand terms (FX, recent, etc.)
2. Use view_selection_guide to pick the best view
3. Call list_trade_views to get available views
4. Call get_view_schema for the chosen view to see available fields
5. Determine appropriate filters based on user question and schema
6. Call query_trades with filters
7. Present results to user in a clear table/summary

Be precise with filter values—use exact field names from schema."""

        return GetPromptResult(
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=message_text)
                )
            ]
        )

    elif name == "validate_filter_criteria":
        view_id = arguments.get("view_id", "")
        requested_filters = arguments.get("requested_filters", "{}")
        message_text = f"""You are validating filter parameters for view {view_id}.

Steps:
1. Call get_view_schema({view_id})
2. Check if all keys in {requested_filters} exist in schema fields
3. If any field is missing, suggest valid alternatives
4. If all valid, confirm and proceed to query_trades"""

        return GetPromptResult(
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=message_text)
                )
            ]
        )

    elif name == "explain_trade_data":
        trade_records = arguments.get("trade_records", "[]")
        message_text = f"""You are a trade reporting assistant. Given these trade records: {trade_records}

Summarize:
- Total number of trades
- Breakdown by ProductType if available
- Date range if TradeDate is present
- Key observations (largest trade, unusual patterns)

Format response as a concise business summary."""

        return GetPromptResult(
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=message_text)
                )
            ]
        )

    raise ValueError(f"Unknown prompt: {name}")

async def main():
    global token_manager
    try:
        logger.info("Starting MCP Trade Blotter Server")
        logger.info("API Base URL: %s", API_BASE_URL)

        if _is_mock_api():
            logger.info("Using MOCK API (no authentication required)")
        else:
            logger.info("Using REAL API with OAuth2 authentication")

        if not _is_mock_api():
            mx_username = os.getenv("MX_USERNAME")
            mx_password = os.getenv("MX_PASSWORD")
            mx_group = os.getenv("MX_GROUP")
            mx_fo_desk = os.getenv("MX_FO_DESK")
            mx_load_balancer = os.getenv(
                "MX_LOAD_BALANCER_URL",
                "https://mx101373vm.hackathon.murex.com:25209"
            )
            if not all([mx_username, mx_password, mx_group, mx_fo_desk]):
                logger.error(
                    "Real API requires MX_USERNAME, MX_PASSWORD, MX_GROUP, and MX_FO_DESK "
                    "environment variables. Authentication will be skipped."
                )
                logger.warning("Set USE_MOCK_API=true to force mock mode")
            else:
                token_manager = TokenManager(
                    username=mx_username,
                    password=mx_password,
                    group=mx_group,
                    fo_desk=mx_fo_desk,
                    load_balancer_url=mx_load_balancer,
                    verify_ssl=False,
                )
                try:
                    await token_manager.initialize()
                    logger.info("Token manager initialized successfully")
                except Exception as exc:
                    logger.error("Failed to initialize token manager: %s", exc)
                    token_manager = None

        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())
    finally:
        if token_manager:
            await token_manager.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
