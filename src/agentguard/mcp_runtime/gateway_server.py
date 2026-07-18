from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from mcp.server.fastmcp import FastMCP

from agentguard.approval import SQLiteApprovalManager
from agentguard.async_gateway import AsyncToolGateway
from agentguard.mcp_runtime.downstream import DownstreamManager
from agentguard.policy import PolicyEngine
from agentguard.tools import create_mcp_metadata_registry

_gateway: AsyncToolGateway | None = None


@asynccontextmanager
async def lifespan(_: FastMCP[Any]) -> AsyncIterator[None]:
    global _gateway
    project_root = Path(os.getenv("AGENTGUARD_PROJECT_ROOT", Path.cwd()))
    runtime_dir = Path(os.getenv("AGENTGUARD_RUNTIME_DIR", project_root / "runtime"))
    canary = os.getenv("AGENTGUARD_CANARY", "CANARY_SECRET_8F31A72")
    trace_id = os.getenv("AGENTGUARD_TRACE_ID", f"tr_{uuid4().hex[:12]}")
    session_id = os.getenv("AGENTGUARD_SESSION_ID", f"ses_{uuid4().hex[:12]}")
    protection = os.getenv("AGENTGUARD_PROTECTION_ENABLED", "true").lower() == "true"
    policy_path = Path(
        os.getenv("AGENTGUARD_POLICY_PATH", project_root / "policies" / "default.yaml")
    )
    policy = PolicyEngine.from_yaml(policy_path) if policy_path.exists() else PolicyEngine()

    async with DownstreamManager(cwd=project_root) as downstream:
        await downstream.validate_tools()
        _gateway = AsyncToolGateway(
            registry=create_mcp_metadata_registry(),
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


server = FastMCP("AgentGuard DataFlow Gateway", lifespan=lifespan)


def gateway() -> AsyncToolGateway:
    if _gateway is None:
        raise RuntimeError("AgentGuard gateway has not started")
    return _gateway


@server.tool(name="email.read")
async def read_email(message_id: str) -> str:
    """Read an email through the AgentGuard security gateway."""
    result = await gateway().call("email.read", {"message_id": message_id})
    return str(result)


@server.tool(name="filesystem.read")
async def read_file(path: str) -> str:
    """Read a file through the AgentGuard security gateway."""
    result = await gateway().call("filesystem.read", {"path": path})
    return str(result)


@server.tool(name="github.create_issue")
async def create_issue(title: str, body: str, approval_token: str | None = None) -> dict[str, Any]:
    """Create an issue if AgentGuard policy allows the external write."""
    result = await gateway().call(
        "github.create_issue",
        {"title": title, "body": body},
        approval_token=approval_token,
    )
    if not isinstance(result, dict):
        raise TypeError("GitHub MCP returned an unexpected result")
    return result


if __name__ == "__main__":
    server.run(transport="stdio")
