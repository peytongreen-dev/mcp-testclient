"""In-process TestClient for the MCP Python SDK Server class.

Wires a Server directly to a ClientSession using anyio memory streams.
No subprocess. No network. No stdio. pytest-native.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

import anyio
import anyio.from_thread
from mcp import types
from mcp.client.session import ClientSession
from mcp.server.lowlevel import Server
from mcp.shared.message import SessionMessage


class TestClient:
    """Synchronous wrapper around an in-process MCP server.

    Usage::

        with TestClient(server) as client:
            tools = client.list_tools()
            result = client.call_tool("my_tool", {"arg": "value"})

    The client initialises the MCP session (sends ``initialize`` / receives
    ``initialized``) on ``__enter__`` and tears everything down on ``__exit__``.
    All public methods are synchronous — they drive an asyncio event loop
    internally so your test functions don't need to be ``async``.
    """

    def __init__(self, server: Server, *, raise_exceptions: bool = True) -> None:
        self._server = server
        self._raise_exceptions = raise_exceptions
        self._loop: asyncio.AbstractEventLoop | None = None
        self._session: ClientSession | None = None
        self._task_group_cancel: Any = None

    # ------------------------------------------------------------------
    # Context manager (sync)
    # ------------------------------------------------------------------

    def __enter__(self) -> "TestClient":
        self._loop = asyncio.new_event_loop()
        self._loop.run_until_complete(self._astart())
        return self

    def __exit__(self, *exc_info: Any) -> None:
        try:
            self._loop.run_until_complete(self._astop())
        finally:
            self._loop.close()
            self._loop = None

    # ------------------------------------------------------------------
    # Public API (sync wrappers)
    # ------------------------------------------------------------------

    def list_tools(self) -> list[types.Tool]:
        """Return the list of tools advertised by the server."""
        result = self._run(self._session.list_tools())  # type: ignore[union-attr]
        return result.tools

    def call_tool(
        self, name: str, arguments: dict[str, Any] | None = None
    ) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
        """Call a tool and return its content list."""
        result = self._run(
            self._session.call_tool(name, arguments or {})  # type: ignore[union-attr]
        )
        if result.isError:
            raise RuntimeError(
                f"Tool '{name}' returned an error: "
                + " ".join(
                    c.text for c in result.content if isinstance(c, types.TextContent)
                )
            )
        return result.content

    def list_resources(self) -> list[types.Resource]:
        """Return the list of resources advertised by the server."""
        result = self._run(self._session.list_resources())  # type: ignore[union-attr]
        return result.resources

    def read_resource(self, uri: str) -> list[types.TextResourceContents | types.BlobResourceContents]:
        """Read a resource by URI and return its contents list."""
        from pydantic import AnyUrl
        result = self._run(
            self._session.read_resource(AnyUrl(uri))  # type: ignore[union-attr]
        )
        return result.contents

    def list_prompts(self) -> list[types.Prompt]:
        """Return the list of prompts advertised by the server."""
        result = self._run(self._session.list_prompts())  # type: ignore[union-attr]
        return result.prompts

    def get_prompt(
        self, name: str, arguments: dict[str, str] | None = None
    ) -> types.GetPromptResult:
        """Get a prompt by name."""
        result = self._run(
            self._session.get_prompt(name, arguments or {})  # type: ignore[union-attr]
        )
        return result

    # ------------------------------------------------------------------
    # Internal async machinery
    # ------------------------------------------------------------------

    async def _astart(self) -> None:
        """Wire server and client streams, run server in background, initialise session."""
        # client → server
        client_to_server_send: anyio.abc.ObjectSendStream[SessionMessage]
        client_to_server_recv: anyio.abc.ObjectReceiveStream[SessionMessage | Exception]
        client_to_server_send, client_to_server_recv = anyio.create_memory_object_stream(32)

        # server → client
        server_to_client_send: anyio.abc.ObjectSendStream[SessionMessage]
        server_to_client_recv: anyio.abc.ObjectReceiveStream[SessionMessage | Exception]
        server_to_client_send, server_to_client_recv = anyio.create_memory_object_stream(32)

        init_options = self._server.create_initialization_options()

        # Run server in background task group
        self._tg_exit: Any = None

        async def _run_server() -> None:
            await self._server.run(
                client_to_server_recv,  # server reads what client sends
                server_to_client_send,  # server writes to client
                init_options,
                raise_exceptions=self._raise_exceptions,
            )

        # We need the server task group to persist beyond _astart, so we use
        # anyio task groups with a cancel scope trick.
        self._cancel_scope = anyio.CancelScope()
        self._server_task: asyncio.Task[None] = self._loop.create_task(  # type: ignore[union-attr]
            _run_server()
        )

        # Build the client session
        session = ClientSession(
            server_to_client_recv,  # client reads what server sends
            client_to_server_send,  # client writes to server
        )
        self._session = session

        # Run initialize handshake
        await session.__aenter__()
        await session.initialize()

    async def _astop(self) -> None:
        """Tear down session and cancel server task."""
        if self._session is not None:
            try:
                await self._session.__aexit__(None, None, None)
            except Exception:
                pass
            self._session = None
        if self._server_task is not None and not self._server_task.done():
            self._server_task.cancel()
            try:
                await self._server_task
            except (asyncio.CancelledError, Exception):
                pass
            self._server_task = None  # type: ignore[assignment]

    def _run(self, coro: Any) -> Any:
        """Run a coroutine on the event loop."""
        return self._loop.run_until_complete(coro)  # type: ignore[union-attr]
