from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from pydantic import ValidationError

from agentguard.mcp_runtime.config import MCPServersConfig
from agentguard.mcp_runtime.downstream import DownstreamManager
from agentguard.models import ToolCategory


def test_loads_default_mcp_server_config() -> None:
    config = MCPServersConfig.from_yaml(Path("config/mcp-servers.yaml"))

    assert [server.id for server in config.servers] == [
        "email",
        "filesystem",
        "github",
        "attacker",
    ]
    assert config.servers[2].tools["create_issue"].category is ToolCategory.EXTERNAL_WRITE


def test_rejects_duplicate_exposed_tool_names() -> None:
    with pytest.raises(ValidationError, match="Duplicate exposed MCP tool names"):
        MCPServersConfig.model_validate(
            {
                "servers": [
                    {
                        "id": "one",
                        "command": "tool-one",
                        "tools": {"read": {"expose_as": "shared.read", "category": "read"}},
                    },
                    {
                        "id": "two",
                        "command": "tool-two",
                        "tools": {"read": {"expose_as": "shared.read", "category": "read"}},
                    },
                ]
            }
        )


def test_rejects_unknown_tool_category() -> None:
    with pytest.raises(ValidationError, match="unknown_category"):
        MCPServersConfig.model_validate(
            {
                "servers": [
                    {
                        "id": "email",
                        "command": "tool",
                        "tools": {
                            "read": {
                                "expose_as": "email.read",
                                "category": "unknown_category",
                            }
                        },
                    }
                ]
            }
        )


def test_resolves_relative_server_working_directory_from_project_root(
    tmp_path: Path,
) -> None:
    config = MCPServersConfig.model_validate(
        {
            "servers": [
                {
                    "id": "email",
                    "command": "{python}",
                    "cwd": "services/email",
                    "tools": {"read": {"expose_as": "email.read", "category": "read"}},
                }
            ]
        }
    )

    assert config.servers[0].resolved_cwd(tmp_path) == (tmp_path / "services" / "email").resolve()


def test_discovers_renames_and_allowlists_downstream_tools() -> None:
    async def run() -> None:
        config = _email_config("inbox.fetch")
        async with DownstreamManager(
            cwd=Path.cwd(),
            config=config,
            env={"AGENTGUARD_EMAIL_BODY": "configured message"},
        ) as downstream:
            assert [tool.name for tool in downstream.exposed_tools] == ["inbox.fetch"]
            assert downstream.tool_specs[0].category is ToolCategory.READ
            assert "list_labels" not in {tool.name for tool in downstream.exposed_tools}
            result = await downstream.call_tool("inbox.fetch", {"message_id": "customer-001"})
            assert result == "configured message"

    asyncio.run(run())


def test_fails_when_configured_tool_is_missing() -> None:
    async def run() -> None:
        config = _email_config("inbox.fetch", downstream_name="missing")
        with pytest.raises(RuntimeError, match="missing configured tools"):
            async with DownstreamManager(cwd=Path.cwd(), config=config):
                pass

    asyncio.run(run())


def _email_config(expose_as: str, downstream_name: str = "read") -> MCPServersConfig:
    return MCPServersConfig.model_validate(
        {
            "servers": [
                {
                    "id": "email",
                    "command": "{python}",
                    "args": ["-m", "agentguard.mock_mcp.email_server"],
                    "tools": {downstream_name: {"expose_as": expose_as, "category": "read"}},
                }
            ]
        }
    )
