"""Basic TestClient tests — validates the in-process server wiring."""

import mcp.types as types
from mcp.server.lowlevel import Server

from mcp_testclient import TestClient


def _make_echo_server() -> Server:
    server = Server("test-echo")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="echo",
                description="Echo the input back",
                inputSchema={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
            ),
            types.Tool(
                name="add",
                description="Add two numbers",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "a": {"type": "number"},
                        "b": {"type": "number"},
                    },
                    "required": ["a", "b"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        if name == "echo":
            return [types.TextContent(type="text", text=arguments["text"])]
        if name == "add":
            return [types.TextContent(type="text", text=str(arguments["a"] + arguments["b"]))]
        raise ValueError(f"Unknown tool: {name}")

    return server


def test_list_tools():
    server = _make_echo_server()
    with TestClient(server) as client:
        tools = client.list_tools()
    assert len(tools) == 2
    assert tools[0].name == "echo"
    assert tools[1].name == "add"


def test_call_tool_echo():
    server = _make_echo_server()
    with TestClient(server) as client:
        result = client.call_tool("echo", {"text": "hello"})
    assert len(result) == 1
    assert isinstance(result[0], types.TextContent)
    assert result[0].text == "hello"


def test_call_tool_add():
    server = _make_echo_server()
    with TestClient(server) as client:
        result = client.call_tool("add", {"a": 3, "b": 4})
    assert result[0].text == "7"


def test_client_reuse_across_calls():
    server = _make_echo_server()
    with TestClient(server) as client:
        r1 = client.call_tool("echo", {"text": "first"})
        r2 = client.call_tool("echo", {"text": "second"})
    assert r1[0].text == "first"
    assert r2[0].text == "second"


def test_multiple_independent_sessions():
    """Each TestClient creates an independent session — no state leaks."""
    server = _make_echo_server()
    with TestClient(server) as c1:
        r1 = client_call = c1.call_tool("echo", {"text": "session-1"})
    with TestClient(server) as c2:
        r2 = c2.call_tool("echo", {"text": "session-2"})
    assert r1[0].text == "session-1"
    assert r2[0].text == "session-2"
