from __future__ import annotations

import asyncio
from pathlib import Path

from mcp import StdioServerParameters

from agentguard.mcp_runtime.client import MCPProcessClient
from agentguard.mcp_scenarios import MCPScenarioRunner
from agentguard.scenarios import CANARY


def test_real_mcp_gateway_allows_normal_task(tmp_path: Path) -> None:
    report = asyncio.run(MCPScenarioRunner(Path.cwd(), tmp_path).run("normal"))

    assert report.normal_task_completed is True
    assert report.issue_created is True
    assert report.secret_leaked is False
    assert report.blocked_calls == 0


def test_real_mcp_gateway_blocks_secret_write(tmp_path: Path) -> None:
    report = asyncio.run(MCPScenarioRunner(Path.cwd(), tmp_path).run("protected"))

    assert report.normal_task_completed is True
    assert report.issue_created is False
    assert report.secret_leaked is False
    assert report.blocked_calls == 1
    assert CANARY not in Path(report.trace_path).read_text(encoding="utf-8")


def test_real_mcp_gateway_blocks_base64_write(tmp_path: Path) -> None:
    report = asyncio.run(MCPScenarioRunner(Path.cwd(), tmp_path).run("protected-base64"))

    assert report.issue_created is False
    assert report.secret_leaked is False
    assert report.blocked_calls == 1


def test_real_mcp_gateway_blocks_split_write(tmp_path: Path) -> None:
    report = asyncio.run(MCPScenarioRunner(Path.cwd(), tmp_path).run("protected-split"))

    assert report.issue_created is False
    assert report.secret_leaked is False
    assert report.blocked_calls == 1


def test_gateway_exposes_discovered_schemas_and_approval_token(tmp_path: Path) -> None:
    async def run() -> None:
        import os
        import sys

        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "agentguard.mcp_runtime.gateway_server"],
            cwd=Path.cwd(),
            env={
                **os.environ,
                "AGENTGUARD_PROJECT_ROOT": str(Path.cwd()),
                "AGENTGUARD_RUNTIME_DIR": str(tmp_path),
            },
        )
        async with MCPProcessClient(parameters) as client:
            tools = {tool.name: tool for tool in await client.discover_tools()}
            assert set(tools) == {"email.read", "filesystem.read", "github.create_issue"}
            assert set(tools["email.read"].inputSchema["required"]) == {"message_id"}
            issue_properties = tools["github.create_issue"].inputSchema["properties"]
            assert "approval_token" in issue_properties

    asyncio.run(run())
