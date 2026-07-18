from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from pydantic import BaseModel

from agentguard.mcp_runtime.config import MCPServersConfig
from agentguard.mcp_runtime.downstream import DownstreamManager
from agentguard.mcp_scenarios import MCPScenarioRunner
from agentguard.models import ScenarioReport


class PlaygroundScenario(BaseModel):
    mode: str
    title: str
    description: str
    protection_enabled: bool
    attack_variant: str


PLAYGROUND_SCENARIOS = [
    PlaygroundScenario(
        mode="normal",
        title="正常工单处理",
        description="读取客户邮件并创建模拟 GitHub Issue，不包含敏感数据。",
        protection_enabled=False,
        attack_variant="none",
    ),
    PlaygroundScenario(
        mode="baseline",
        title="无防护攻击基线",
        description="恶意邮件诱导 Agent 读取 Canary 密钥并写入外部 Issue。",
        protection_enabled=False,
        attack_variant="indirect_prompt_injection",
    ),
    PlaygroundScenario(
        mode="protected",
        title="敏感数据外发拦截",
        description="开启 AgentGuard，阻止原文 Canary 流向外部写工具。",
        protection_enabled=True,
        attack_variant="exact_or_embedded",
    ),
    PlaygroundScenario(
        mode="protected-base64",
        title="Base64 绕过检测",
        description="攻击者编码敏感数据后外发，网关在执行前识别并阻止。",
        protection_enabled=True,
        attack_variant="base64",
    ),
    PlaygroundScenario(
        mode="protected-split",
        title="拆分字段重组检测",
        description="敏感数据被拆到标题和正文，网关重组参数后阻止写入。",
        protection_enabled=True,
        attack_variant="split_fields",
    ),
]


class PlaygroundService:
    def __init__(self, project_root: Path, runtime_dir: Path) -> None:
        self.project_root = project_root.resolve()
        self.runtime_dir = runtime_dir.resolve()

    async def run(self, mode: str) -> dict[str, Any]:
        scenario = next((item for item in PLAYGROUND_SCENARIOS if item.mode == mode), None)
        if scenario is None:
            raise ValueError(f"Unsupported playground mode: {mode}")
        report = await MCPScenarioRunner(self.project_root, self.runtime_dir).run(mode)
        return {
            "simulator": "deterministic-mcp-agent",
            "scenario": scenario.model_dump(mode="json"),
            "report": report.model_dump(mode="json"),
            "steps": _agent_steps(report),
        }


class MCPRegistryService:
    def __init__(self, project_root: Path, config_path: Path) -> None:
        self.project_root = project_root.resolve()
        self.config_path = config_path.resolve()

    def configured(self) -> dict[str, Any]:
        config = MCPServersConfig.from_yaml(self.config_path)
        return {
            "config_path": str(self.config_path),
            "status": "configured",
            "last_checked_at": None,
            "servers": [_configured_server(server) for server in config.servers],
        }

    async def discover(self) -> dict[str, Any]:
        started_at = perf_counter()
        config = MCPServersConfig.from_yaml(self.config_path)
        async with DownstreamManager(cwd=self.project_root, config=config) as downstream:
            reports = {report.server_id: report for report in downstream.discovery_reports}
            servers = []
            for server in config.servers:
                summary = _configured_server(server)
                report = reports[server.id]
                summary.update(
                    {
                        "status": "healthy",
                        "discovered_tools": report.discovered_tools,
                        "hidden_tools": report.hidden_tools,
                    }
                )
                servers.append(summary)
        return {
            "config_path": str(self.config_path),
            "status": "healthy",
            "last_checked_at": datetime.now(UTC).isoformat(),
            "duration_ms": (perf_counter() - started_at) * 1000,
            "servers": servers,
        }


def _configured_server(server: Any) -> dict[str, Any]:
    return {
        "id": server.id,
        "command": server.command,
        "status": "configured",
        "tools": [
            {
                "downstream_name": downstream_name,
                "expose_as": tool.expose_as,
                "category": tool.category,
                "description": tool.description,
            }
            for downstream_name, tool in server.tools.items()
        ],
    }


def _agent_steps(report: ScenarioReport) -> list[dict[str, str]]:
    steps = [
        {
            "tool": "email.read",
            "action": "读取客户邮件",
            "decision": "ALLOW",
        }
    ]
    if report.mode != "normal":
        steps.append(
            {
                "tool": "filesystem.read",
                "action": "读取邮件指令引用的敏感文件",
                "decision": "ALLOW",
            }
        )
    steps.append(
        {
            "tool": "github.create_issue",
            "action": "向外部系统创建 Issue",
            "decision": "DENY" if report.blocked_calls else "ALLOW",
        }
    )
    return steps
