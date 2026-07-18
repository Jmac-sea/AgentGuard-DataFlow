from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

import anyio
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, TextContent, Tool

from agentguard.approval import SQLiteApprovalManager
from agentguard.async_gateway import AsyncToolGateway
from agentguard.mcp_runtime.downstream import DownstreamManager
from agentguard.policy import PolicyEngine
from agentguard.tools import create_mcp_metadata_registry

_gateway: AsyncToolGateway | None = None
_tools: list[Tool] = []


@asynccontextmanager
async def lifespan(_: Server[Any]) -> AsyncIterator[None]:
    global _gateway, _tools
    project_root = Path(os.getenv("AGENTGUARD_PROJECT_ROOT", Path.cwd())).resolve()
    runtime_dir = Path(os.getenv("AGENTGUARD_RUNTIME_DIR", project_root / "runtime"))
    canary = os.getenv("AGENTGUARD_CANARY", "CANARY_SECRET_8F31A72")
    trace_id = os.getenv("AGENTGUARD_TRACE_ID", f"tr_{uuid4().hex[:12]}")
    session_id = os.getenv("AGENTGUARD_SESSION_ID", f"ses_{uuid4().hex[:12]}")
    protection = os.getenv("AGENTGUARD_PROTECTION_ENABLED", "true").lower() == "true"
    policy_path = Path(
        os.getenv("AGENTGUARD_POLICY_PATH", project_root / "policies" / "default.yaml")
    )
    config_path = Path(
        os.getenv("AGENTGUARD_MCP_CONFIG", project_root / "config" / "mcp-servers.yaml")
    )
    policy = PolicyEngine.from_yaml(policy_path) if policy_path.exists() else PolicyEngine()

    async with DownstreamManager(cwd=project_root, config_path=config_path) as downstream:
        _tools = downstream.exposed_tools
        _gateway = AsyncToolGateway(
            registry=create_mcp_metadata_registry(downstream.tool_specs),
            downstream=downstream,
            session_id=session_id,
            trace_id=trace_id,
            canaries={canary},
            protection_enabled=protection,
            output_dir=runtime_dir / "traces",
            policy=policy,
            approvals=SQLiteApprovalManager(runtime_dir / "approvals.db"),
        )
        try:
            yield
        finally:
            _gateway.artifacts.clear()
            _gateway = None
            _tools = []


server: Server[None] = Server("AgentGuard DataFlow Gateway", lifespan=lifespan)


def gateway() -> AsyncToolGateway:
    if _gateway is None:
        raise RuntimeError("AgentGuard gateway has not started")
    return _gateway


@server.list_tools()  # type: ignore[untyped-decorator,no-untyped-call]
async def list_tools() -> list[Tool]:
    return list(_tools)


@server.call_tool()  # type: ignore[untyped-decorator]
async def call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
    forwarded = dict(arguments)
    approval_token = forwarded.pop("approval_token", None)
    result = await gateway().call(name, forwarded, approval_token=approval_token)
    tool = next((candidate for candidate in _tools if candidate.name == name), None)
    structured = _structured_result(tool, result)
    if isinstance(result, dict):
        text = json.dumps(result, ensure_ascii=False)
        return CallToolResult(
            content=[TextContent(type="text", text=text)], structuredContent=structured
        )
    if result is None:
        return CallToolResult(content=[], structuredContent=structured)
    return CallToolResult(
        content=[TextContent(type="text", text=str(result))], structuredContent=structured
    )


def _structured_result(tool: Tool | None, result: Any) -> dict[str, Any] | None:
    if tool is None or tool.outputSchema is None:
        return result if isinstance(result, dict) else None
    properties = tool.outputSchema.get("properties", {})
    if not isinstance(result, dict) and set(properties) == {"result"}:
        return {"result": result}
    if isinstance(result, dict):
        return result
    return None


async def run() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    anyio.run(run)
