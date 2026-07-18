from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any, Self

from mcp import StdioServerParameters
from mcp.types import Tool

from agentguard.mcp_runtime.client import MCPProcessClient
from agentguard.mcp_runtime.config import MCPServersConfig
from agentguard.models import ToolCategory, ToolSpec

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DownstreamTool:
    server_id: str
    downstream_name: str
    category: ToolCategory


@dataclass(frozen=True)
class ServerDiscoveryReport:
    server_id: str
    discovered_tools: list[str]
    exposed_tools: list[str]
    hidden_tools: list[str]


class DownstreamManager:
    def __init__(
        self,
        *,
        cwd: Path,
        env: dict[str, str] | None = None,
        config: MCPServersConfig | None = None,
        config_path: Path | None = None,
    ) -> None:
        self.cwd = cwd.resolve()
        self.env = {**os.environ, **(env or {})}
        self.config = config or MCPServersConfig.from_yaml(
            config_path or self.cwd / "config" / "mcp-servers.yaml"
        )
        self._clients: dict[str, MCPProcessClient] = {}
        self._tool_map: dict[str, DownstreamTool] = {}
        self._exposed_tools: list[Tool] = []
        self._tool_specs: list[ToolSpec] = []
        self._discovery_reports: list[ServerDiscoveryReport] = []

    @property
    def exposed_tools(self) -> list[Tool]:
        return list(self._exposed_tools)

    @property
    def tool_specs(self) -> list[ToolSpec]:
        return list(self._tool_specs)

    @property
    def discovery_reports(self) -> list[ServerDiscoveryReport]:
        return list(self._discovery_reports)

    async def __aenter__(self) -> Self:
        clients = {
            server_config.id: MCPProcessClient(
                StdioServerParameters(
                    command=server_config.resolved_command(),
                    args=server_config.resolved_args(self.cwd),
                    env={**self.env, **server_config.resolved_env(self.cwd)},
                    cwd=server_config.resolved_cwd(self.cwd),
                )
            )
            for server_config in self.config.servers
        }
        results = await asyncio.gather(
            *(client.__aenter__() for client in clients.values()),
            return_exceptions=True,
        )
        errors = [result for result in results if isinstance(result, BaseException)]
        if errors:
            await self._close_clients(clients)
            raise errors[0]
        self._clients = clients
        try:
            self._discover_and_validate(await self._discover(clients))
        except BaseException:
            await self._close_clients(clients)
            self._clients = {}
            raise
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self._close_clients(self._clients)
        self._clients = {}
        self._tool_map = {}
        self._exposed_tools = []
        self._tool_specs = []
        self._discovery_reports = []

    @staticmethod
    async def _close_clients(clients: dict[str, MCPProcessClient]) -> None:
        await asyncio.gather(
            *(client.__aexit__(None, None, None) for client in clients.values()),
            return_exceptions=True,
        )

    async def call_tool(self, upstream_name: str, arguments: dict[str, Any]) -> Any:
        try:
            target = self._tool_map[upstream_name]
            client = self._clients[target.server_id]
        except KeyError as exc:
            raise KeyError(f"Unknown downstream MCP tool: {upstream_name}") from exc
        return await client.call_tool(target.downstream_name, arguments)

    async def validate_tools(self) -> None:
        """Compatibility hook; discovery now validates tools during startup."""
        if not self._tool_map:
            raise RuntimeError("Downstream MCP tools have not been discovered")

    async def _discover(self, clients: dict[str, MCPProcessClient]) -> dict[str, list[Tool]]:
        return {server_id: await client.discover_tools() for server_id, client in clients.items()}

    def _discover_and_validate(self, discovered: dict[str, list[Tool]]) -> None:
        tool_map: dict[str, DownstreamTool] = {}
        exposed_tools: list[Tool] = []
        specs: list[ToolSpec] = []
        reports: list[ServerDiscoveryReport] = []
        for server_config in self.config.servers:
            actual = {tool.name: tool for tool in discovered[server_config.id]}
            configured_names = set(server_config.tools)
            missing = configured_names - set(actual)
            if missing:
                raise RuntimeError(
                    f"MCP server {server_config.id} is missing configured tools: {sorted(missing)}"
                )
            additional = set(actual) - configured_names
            if additional:
                logger.warning(
                    "MCP server %s has unconfigured tools that will not be exposed: %s",
                    server_config.id,
                    sorted(additional),
                )
            reports.append(
                ServerDiscoveryReport(
                    server_id=server_config.id,
                    discovered_tools=sorted(actual),
                    exposed_tools=sorted(tool.expose_as for tool in server_config.tools.values()),
                    hidden_tools=sorted(additional),
                )
            )
            for downstream_name, tool_config in server_config.tools.items():
                discovered_tool = actual[downstream_name]
                description = tool_config.description or discovered_tool.description or ""
                exposed_tool = discovered_tool.model_copy(
                    update={
                        "name": tool_config.expose_as,
                        "description": description,
                        "inputSchema": _gateway_schema(
                            discovered_tool.inputSchema, tool_config.category
                        ),
                    }
                )
                tool_map[tool_config.expose_as] = DownstreamTool(
                    server_id=server_config.id,
                    downstream_name=downstream_name,
                    category=tool_config.category,
                )
                exposed_tools.append(exposed_tool)
                specs.append(
                    ToolSpec(
                        name=tool_config.expose_as,
                        category=tool_config.category,
                        description=description,
                    )
                )
        self._tool_map = tool_map
        self._exposed_tools = exposed_tools
        self._tool_specs = specs
        self._discovery_reports = reports


def _gateway_schema(schema: dict[str, Any], category: ToolCategory) -> dict[str, Any]:
    if category is not ToolCategory.EXTERNAL_WRITE:
        return schema
    gateway_schema = dict(schema)
    properties = dict(gateway_schema.get("properties", {}))
    properties.setdefault(
        "approval_token",
        {
            "type": ["string", "null"],
            "description": "One-time AgentGuard approval token for this exact tool call",
            "default": None,
        },
    )
    gateway_schema["properties"] = properties
    return gateway_schema
