import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class TradeBlotterMCPClient:
    def __init__(self, server_script_path: str = "mcp_server.py"):
        self.server_params = StdioServerParameters(
            command="python",
            args=[server_script_path],
            env=None
        )
        self.session = None
        self.read_stream = None
        self.write_stream = None
        self.stdio_context = None

    async def connect(self):
        self.stdio_context = stdio_client(self.server_params)
        self.read_stream, self.write_stream = await self.stdio_context.__aenter__()
        self.session = ClientSession(self.read_stream, self.write_stream)
        await self.session.__aenter__()
        await self.session.initialize()

    async def disconnect(self):
        if self.session:
            try:
                await self.session.__aexit__(None, None, None)
            except Exception:
                pass
        if self.stdio_context:
            try:
                await self.stdio_context.__aexit__(None, None, None)
            except Exception:
                pass

    async def list_tools(self):
        response = await self.session.list_tools()
        return response.tools

    async def list_resources(self):
        response = await self.session.list_resources()
        return response.resources

    async def list_prompts(self):
        response = await self.session.list_prompts()
        return response.prompts

    async def read_resource(self, uri: str):
        response = await self.session.read_resource(uri)
        return response.contents

    async def call_tool(self, tool_name: str, arguments: dict):
        response = await self.session.call_tool(tool_name, arguments)
        return response.content

    async def get_prompt(self, prompt_name: str, arguments: dict):
        response = await self.session.get_prompt(prompt_name, arguments)
        return response.messages

async def main():
    client = TradeBlotterMCPClient()

    try:
        print("Connecting to MCP server...")
        await client.connect()
        print("✓ Connected\n")

        print("=== Available Tools ===")
        tools = await client.list_tools()
        for tool in tools:
            print(f"- {tool.name}: {tool.description}")
        print()

        print("=== Available Resources ===")
        resources = await client.list_resources()
        for resource in resources:
            print(f"- {resource.name} ({resource.uri})")
        print()

        print("=== Available Prompts ===")
        prompts = await client.list_prompts()
        for prompt in prompts:
            print(f"- {prompt.name}: {prompt.description}")
        print()

        print("=== Testing: check_service_health ===")
        health_result = await client.call_tool("check_service_health", {})
        print(health_result[0].text)
        print()

        print("=== Testing: list_trade_views ===")
        views_result = await client.call_tool("list_trade_views", {})
        print(views_result[0].text)
        print()

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.disconnect()
        print("✓ Disconnected")

if __name__ == "__main__":
    asyncio.run(main())
