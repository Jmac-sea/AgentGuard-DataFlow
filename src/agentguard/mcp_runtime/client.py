from __future__ import annotations

import json
from contextlib import AsyncExitStack
from types import TracebackType
from typing import Any, Self

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent, Tool


class MCPProcessClient:
    """Manage one stdio MCP subprocess and expose a compact Python interface."""

    def __init__(self, parameters: StdioServerParameters) -> None:
        self.parameters = parameters
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None

    async def __aenter__(self) -> Self:
        stack = AsyncExitStack()
        read_stream, write_stream = await stack.enter_async_context(stdio_client(self.parameters))
        session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
        await session.initialize()
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

    def _require_session(self) -> ClientSession:
        if self._session is None:
            raise RuntimeError("MCP client is not connected")
        return self._session
