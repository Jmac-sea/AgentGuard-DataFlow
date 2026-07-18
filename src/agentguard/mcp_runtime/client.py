from __future__ import annotations

import json
from contextlib import AsyncExitStack
from types import TracebackType
from typing import Any, Self

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult, TextContent, Tool


class MCPProcessClient:
    """Manage one stdio MCP subprocess and expose a compact Python interface."""

    def __init__(self, parameters: StdioServerParameters) -> None:
        self.parameters = parameters
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None

    async def __aenter__(self) -> Self:
        stack = AsyncExitStack()
        try:
            read_stream, write_stream = await stack.enter_async_context(
                stdio_client(self.parameters)
            )
            session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
            await session.initialize()
        except BaseException:
            await stack.aclose()
            raise
        self._stack = stack
        self._session = session
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._stack = None
        self._session = None

    async def list_tools(self) -> list[str]:
        return [tool.name for tool in await self.discover_tools()]

    async def discover_tools(self) -> list[Tool]:
        result = await self._require_session().list_tools()
        return result.tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        result = await self._require_session().call_tool(name, arguments)
        return _decode_tool_result(name, result)

    def _require_session(self) -> ClientSession:
        if self._session is None:
            raise RuntimeError("MCP client is not connected")
        return self._session


class MCPHTTPClient:
    """Connect to an AgentGuard Streamable HTTP MCP endpoint."""

    def __init__(self, url: str, *, token: str | None = None, timeout_seconds: float = 90) -> None:
        self.url = url
        self.token = token
        self.timeout_seconds = timeout_seconds
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None

    async def __aenter__(self) -> Self:
        stack = AsyncExitStack()
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else None
        try:
            http_client = await stack.enter_async_context(
                httpx.AsyncClient(headers=headers, timeout=self.timeout_seconds)
            )
            read_stream, write_stream, _ = await stack.enter_async_context(
                streamable_http_client(self.url, http_client=http_client)
            )
            session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
            await session.initialize()
        except BaseException:
            await stack.aclose()
            raise
        self._stack = stack
        self._session = session
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._stack = None
        self._session = None

    async def discover_tools(self) -> list[Tool]:
        result = await self._require_session().list_tools()
        return result.tools

    async def list_tools(self) -> list[str]:
        return [tool.name for tool in await self.discover_tools()]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        result = await self._require_session().call_tool(name, arguments)
        return _decode_tool_result(name, result)

    def _require_session(self) -> ClientSession:
        if self._session is None:
            raise RuntimeError("MCP HTTP client is not connected")
        return self._session


def _decode_tool_result(name: str, result: CallToolResult) -> Any:
    text_blocks = [block.text for block in result.content if isinstance(block, TextContent)]
    text = "\n".join(text_blocks)
    if result.isError:
        raise RuntimeError(text or f"MCP tool failed: {name}")
    if result.structuredContent is not None:
        structured = result.structuredContent
        if set(structured) == {"result"}:
            return structured["result"]
        return structured
    if not text_blocks:
        return None
    if len(text_blocks) == 1:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return text
