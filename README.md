# mcp-testclient

pytest-native TestClient for the [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) `Server` class.

> **Using FastMCP?** You already have [`Client(server)`](https://gofastmcp.com/clients/client) built in. mcp-testclient targets the official `mcp.server.lowlevel.Server` class only.

## Why

The MCP Python SDK ships a `Server` class with no built-in test transport. Testing requires spawning a subprocess or standing up a real HTTP server — until now.

`mcp-testclient` wires your `Server` directly to a `ClientSession` using `anyio` memory streams. No subprocess. No network. No stdio. In-process, in a single pytest function.

```python
from mcp.server.lowlevel import Server
import mcp.types as types
from mcp_testclient import TestClient

server = Server("my-server")

@server.list_tools()
async def list_tools():
    return [types.Tool(name="add", description="Add two numbers",
                       inputSchema={"type": "object", "properties":
                           {"a": {"type": "number"}, "b": {"type": "number"}}})]

@server.call_tool()
async def call_tool(name, arguments):
    return [types.TextContent(type="text", text=str(arguments["a"] + arguments["b"]))]

def test_add():
    with TestClient(server) as client:
        tools = client.list_tools()
        assert tools[0].name == "add"

        result = client.call_tool("add", {"a": 1, "b": 2})
        assert result[0].text == "3"
```

## Install

```bash
pip install mcp-testclient
```

## API

```python
with TestClient(server) as client:
    client.list_tools()                            # → list[types.Tool]
    client.call_tool("name", {"arg": "value"})    # → list[TextContent | ...]
    client.list_resources()                        # → list[types.Resource]
    client.read_resource("resource://uri")         # → list[TextResourceContents | ...]
    client.list_prompts()                          # → list[types.Prompt]
    client.get_prompt("name", {"arg": "value"})   # → GetPromptResult
```

`call_tool` raises `RuntimeError` if the server returns `isError=True`.

## Compatibility

- Python 3.10, 3.11, 3.12
- `mcp >= 1.0.0` (tested on 1.26.0)

## MCP Registry

```
mcp-name: io.github.peytongreen-dev/mcp-testclient
```
