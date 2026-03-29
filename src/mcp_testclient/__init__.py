"""mcp-testclient — pytest-native TestClient for the MCP Python SDK Server class.

Quick start:

    from mcp.server.lowlevel import Server
    import mcp.types as types
    from mcp_testclient import TestClient

    server = Server("my-server")

    @server.call_tool()
    async def handle_call_tool(name, arguments):
        if name == "add":
            return [types.TextContent(type="text", text=str(arguments["a"] + arguments["b"]))]

    @server.list_tools()
    async def handle_list_tools():
        return [types.Tool(name="add", description="Add two numbers",
                           inputSchema={"type": "object", "properties":
                               {"a": {"type": "number"}, "b": {"type": "number"}}})]

    def test_add():
        with TestClient(server) as client:
            result = client.call_tool("add", {"a": 1, "b": 2})
            assert result[0].text == "3"

Note: Using FastMCP? You already have Client(server) built in — you don't need
this package. mcp-testclient targets the official mcp SDK Server class only.
"""

from .client import TestClient

__all__ = ["TestClient"]
__version__ = "0.1.0"
