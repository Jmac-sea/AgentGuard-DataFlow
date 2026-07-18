from __future__ import annotations

import asyncio
from pathlib import Path

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
