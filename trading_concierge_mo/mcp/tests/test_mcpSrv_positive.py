import pytest
from mcp_client import TradeBlotterMCPClient

@pytest.fixture(scope="function")
async def mcp_client(mcp_server_script):
    """Create and connect MCP client using absolute path to server script"""
    client = TradeBlotterMCPClient(mcp_server_script)
    try:
        await client.connect()
        yield client
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

@pytest.mark.asyncio
async def test_list_tools(mcp_client):
    tools = await mcp_client.list_tools()
    assert len(tools) == 4
    tool_names = [tool.name for tool in tools]
    assert "check_service_health" in tool_names
    assert "list_trade_views" in tool_names
    assert "get_view_schema" in tool_names
    assert "query_trades" in tool_names

@pytest.mark.asyncio
async def test_list_resources(mcp_client):
    resources = await mcp_client.list_resources()
    assert len(resources) == 3
    resource_uris = [str(resource.uri) for resource in resources]
    assert "resource://trade-blotter/api-docs" in resource_uris
    assert "resource://trade-blotter/glossary" in resource_uris
    assert "resource://trade-blotter/view-guide" in resource_uris

@pytest.mark.asyncio
async def test_list_prompts(mcp_client):
    prompts = await mcp_client.list_prompts()
    assert len(prompts) == 3
    prompt_names = [prompt.name for prompt in prompts]
    assert "analyze_trade_query" in prompt_names
    assert "validate_filter_criteria" in prompt_names
    assert "explain_trade_data" in prompt_names

@pytest.mark.asyncio
async def test_read_resource_api_docs(mcp_client):
    contents = await mcp_client.read_resource("resource://trade-blotter/api-docs")
    assert len(contents) > 0
    if hasattr(contents[0], 'text'):
        text = contents[0].text
    else:
        text = str(contents[0])
    assert "Trade Blotter API Documentation" in text
    assert "Daily Basic" in text
    assert "ProductType" in text

@pytest.mark.asyncio
async def test_read_resource_glossary(mcp_client):
    contents = await mcp_client.read_resource("resource://trade-blotter/glossary")
    assert len(contents) > 0
    if hasattr(contents[0], 'text'):
        text = contents[0].text
    else:
        text = str(contents[0])
    assert "Trading Glossary" in text
    assert "FX" in text
    assert "Foreign Exchange" in text

@pytest.mark.asyncio
async def test_read_resource_view_guide(mcp_client):
    contents = await mcp_client.read_resource("resource://trade-blotter/view-guide")
    assert len(contents) > 0
    if hasattr(contents[0], 'text'):
        text = contents[0].text
    else:
        text = str(contents[0])
    assert "View Selection Guide" in text
    assert "Decision Tree" in text

@pytest.mark.asyncio
async def test_call_tool_check_health(mcp_client):
    result = await mcp_client.call_tool("check_service_health", {})
    assert len(result) > 0
    response_text = result[0].text
    assert "status" in response_text.lower() or "error" in response_text.lower()

@pytest.mark.asyncio
async def test_call_tool_list_views(mcp_client):
    result = await mcp_client.call_tool("list_trade_views", {})
    assert len(result) > 0
    response_text = result[0].text
    assert "views" in response_text.lower() or "error" in response_text.lower()

@pytest.mark.asyncio
async def test_call_tool_get_schema(mcp_client):
    result = await mcp_client.call_tool("get_view_schema", {"view_id": "daily-basic"})
    assert len(result) > 0
    response_text = result[0].text
    assert "schema" in response_text.lower() or "error" in response_text.lower()

@pytest.mark.asyncio
async def test_call_tool_query_trades_no_filters(mcp_client):
    result = await mcp_client.call_tool("query_trades", {"view_id": "daily-basic"})
    assert len(result) > 0
    response_text = result[0].text
    assert len(response_text) > 0

@pytest.mark.asyncio
async def test_call_tool_query_trades_with_filters(mcp_client):
    result = await mcp_client.call_tool("query_trades", {
        "view_id": "daily-basic",
        "filters": {"TradeStatus": "ACTIVE"}
    })
    assert len(result) > 0
    response_text = result[0].text
    assert len(response_text) > 0

@pytest.mark.asyncio
async def test_call_tool_query_trades_with_schema(mcp_client):
    result = await mcp_client.call_tool("query_trades", {
        "view_id": "daily-basic",
        "include_schema": True
    })
    assert len(result) > 0
    response_text = result[0].text
    assert len(response_text) > 0

@pytest.mark.asyncio
async def test_get_prompt_analyze_trade_query(mcp_client):
    messages = await mcp_client.get_prompt("analyze_trade_query", {
        "user_question": "Show me recent FX trades"
    })
    assert len(messages) > 0
    content = messages[0].content.text
    assert "trade data analyst" in content.lower()
    assert "Show me recent FX trades" in content

@pytest.mark.asyncio
async def test_get_prompt_validate_filter(mcp_client):
    messages = await mcp_client.get_prompt("validate_filter_criteria", {
        "view_id": "daily-basic",
        "requested_filters": "{'ProductType': 'FX'}"
    })
    assert len(messages) > 0
    content = messages[0].content.text
    assert "validating" in content.lower()
    assert "daily-basic" in content

@pytest.mark.asyncio
async def test_get_prompt_explain_trade_data(mcp_client):
    messages = await mcp_client.get_prompt("explain_trade_data", {
        "trade_records": "[{'ProductType': 'FX', 'Amount': 1000}]"
    })
    assert len(messages) > 0
    content = messages[0].content.text
    assert "trade reporting" in content.lower()
    assert "summarize" in content.lower()
