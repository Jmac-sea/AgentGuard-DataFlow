from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from mcp.server.lowlevel import Server
from mcp.types import CallToolResult, TextContent, Tool

from agentguard.approval import SQLiteApprovalManager
from agentguard.async_gateway import AsyncToolGateway
from agentguard.mcp_runtime.downstream import DownstreamManager
from agentguard.policy import PolicyEngine
from agentguard.tools import create_mcp_metadata_registry


@dataclass(frozen=True)
class GatewaySettings:
    project_root: Path
    runtime_dir: Path
    policy_path: Path
    config_path: Path
    canary: str = "CANARY_SECRET_8F31A72"
    protection_enabled: bool = True
    trace_id: str | None = None
    session_id: str | None = None

    @classmethod
    def from_env(cls) -> GatewaySettings:
        project_root = Path(os.getenv("AGENTGUARD_PROJECT_ROOT", Path.cwd())).resolve()
        return cls(
            project_root=project_root,
            runtime_dir=Path(
                os.getenv("AGENTGUARD_RUNTIME_DIR", project_root / "runtime")
            ).resolve(),
            policy_path=Path(
                os.getenv("AGENTGUARD_POLICY_PATH", project_root / "policies" / "default.yaml")
            ).resolve(),
            config_path=Path(
                os.getenv("AGENTGUARD_MCP_CONFIG", project_root / "config" / "mcp-servers.yaml")
            ).resolve(),
            canary=os.getenv("AGENTGUARD_CANARY", "CANARY_SECRET_8F31A72"),
            protection_enabled=os.getenv("AGENTGUARD_PROTECTION_ENABLED", "true").lower() == "true",
            trace_id=os.getenv("AGENTGUARD_TRACE_ID"),
            session_id=os.getenv("AGENTGUARD_SESSION_ID"),
        )


@dataclass
class GatewayRuntime:
    gateway: AsyncToolGateway
    tools: list[Tool]


def create_gateway_server(settings: GatewaySettings | None = None) -> Server[GatewayRuntime]:
    configured = settings or GatewaySettings.from_env()

    @asynccontextmanager
    async def lifespan(_: Server[Any]) -> AsyncIterator[GatewayRuntime]:
        policy = (
            PolicyEngine.from_yaml(configured.policy_path)
            if configured.policy_path.exists()
            else PolicyEngine()
        )
        async with DownstreamManager(
            cwd=configured.project_root, config_path=configured.config_path
        ) as downstream:
            gateway = AsyncToolGateway(
                registry=create_mcp_metadata_registry(downstream.tool_specs),
                downstream=downstream,
                session_id=configured.session_id or f"ses_{uuid4().hex[:12]}",
                trace_id=configured.trace_id or f"tr_{uuid4().hex[:12]}",
                canaries={configured.canary},
                protection_enabled=configured.protection_enabled,
                output_dir=configured.runtime_dir / "traces",
                policy=policy,
                approvals=SQLiteApprovalManager(configured.runtime_dir / "approvals.db"),
            )
            runtime = GatewayRuntime(gateway=gateway, tools=downstream.exposed_tools)
            try:
                yield runtime
            finally:
                gateway.artifacts.clear()

    server: Server[GatewayRuntime] = Server("AgentGuard DataFlow Gateway", lifespan=lifespan)

    @server.list_tools()  # type: ignore[untyped-decorator,no-untyped-call]
    async def list_tools() -> list[Tool]:
        return list(_runtime(server).tools)

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
        runtime = _runtime(server)
        forwarded = dict(arguments)
        approval_token = forwarded.pop("approval_token", None)
        result = await runtime.gateway.call(name, forwarded, approval_token=approval_token)
        tool = next((candidate for candidate in runtime.tools if candidate.name == name), None)
        structured = _structured_result(tool, result)
        if isinstance(result, dict):
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps(result, ensure_ascii=False))],
                structuredContent=structured,
            )
        if result is None:
            return CallToolResult(content=[], structuredContent=structured)
        return CallToolResult(
            content=[TextContent(type="text", text=str(result))],
            structuredContent=structured,
        )

    return server


def _runtime(server: Server[GatewayRuntime]) -> GatewayRuntime:
    return server.request_context.lifespan_context


def _structured_result(tool: Tool | None, result: Any) -> dict[str, Any] | None:
    if tool is None or tool.outputSchema is None:
        return result if isinstance(result, dict) else None
    properties = tool.outputSchema.get("properties", {})
    if not isinstance(result, dict) and set(properties) == {"result"}:
        return {"result": result}
    if isinstance(result, dict):
        return result
    return None
