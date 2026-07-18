from __future__ import annotations

import os
import sys
from contextlib import AsyncExitStack
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any, Self

from mcp import StdioServerParameters

from agentguard.mcp_runtime.client import MCPProcessClient


@dataclass(frozen=True)
class DownstreamTool:
    server_id: str
    downstream_name: str


TOOL_MAP: dict[str, DownstreamTool] = {
    "email.read": DownstreamTool("email", "read"),
    "filesystem.read": DownstreamTool("filesystem", "read"),
    "github.create_issue": DownstreamTool("github", "create_issue"),
}


class DownstreamManager:
    def __init__(self, *, cwd: Path, env: dict[str, str] | None = None) -> None:
        self.cwd = cwd
        self.env = {**os.environ, **(env or {})}
        self._stack: AsyncExitStack | None = None
        self._clients: dict[str, MCPProcessClient] = {}

    async def __aenter__(self) -> Self:
        stack = AsyncExitStack()
        modules = {
            "email": "agentguard.mock_mcp.email_server",
            "filesystem": "agentguard.mock_mcp.filesystem_server",
            "github": "agentguard.mock_mcp.github_server",
        }
        clients: dict[str, MCPProcessClient] = {}
        for server_id, module in modules.items():
            parameters = StdioServerParameters(
                command=sys.executable,
                args=["-m", module],
                env=self.env,
                cwd=self.cwd,
            )
            clients[server_id] = await stack.enter_async_context(MCPProcessClient(parameters))
        self._stack = stack
        self._clients = clients
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
        self._clients = {}

    async def call_tool(self, upstream_name: str, arguments: dict[str, Any]) -> Any:
        try:
            target = TOOL_MAP[upstream_name]
            client = self._clients[target.server_id]
        except KeyError as exc:
            raise KeyError(f"Unknown downstream MCP tool: {upstream_name}") from exc
        return await client.call_tool(target.downstream_name, arguments)

    async def validate_tools(self) -> None:
        expected = {
            "email": {"read"},
            "filesystem": {"read"},
            "github": {"create_issue"},
        }
        for server_id, names in expected.items():
            actual = set(await self._clients[server_id].list_tools())
            missing = names - actual
            if missing:
                raise RuntimeError(f"MCP server {server_id} is missing tools: {sorted(missing)}")
