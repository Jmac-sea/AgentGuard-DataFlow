from __future__ import annotations

import sys
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

from agentguard.models import ToolCategory


class MCPToolConfig(BaseModel):
    expose_as: str = Field(min_length=1)
    category: ToolCategory
    description: str | None = None


class MCPServerConfig(BaseModel):
    id: str = Field(min_length=1)
    command: str = Field(min_length=1)
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    cwd: str | None = None
    tools: dict[str, MCPToolConfig] = Field(min_length=1)

    def resolved_command(self) -> str:
        return self.command.replace("{python}", sys.executable)

    def resolved_args(self, project_root: Path) -> list[str]:
        return [self._resolve(value, project_root) for value in self.args]

    def resolved_env(self, project_root: Path) -> dict[str, str]:
        return {key: self._resolve(value, project_root) for key, value in self.env.items()}

    def resolved_cwd(self, project_root: Path) -> Path:
        if self.cwd is None:
            return project_root
        configured = Path(self._resolve(self.cwd, project_root))
        if not configured.is_absolute():
            configured = project_root / configured
        return configured.resolve()

    @staticmethod
    def _resolve(value: str, project_root: Path) -> str:
        return value.replace("{python}", sys.executable).replace(
            "{project_root}", str(project_root)
        )


class MCPServersConfig(BaseModel):
    version: str = "1.0"
    servers: list[MCPServerConfig] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_names(self) -> MCPServersConfig:
        server_ids = [server.id for server in self.servers]
        duplicates = _duplicates(server_ids)
        if duplicates:
            raise ValueError(f"Duplicate MCP server ids: {duplicates}")

        exposed = [tool.expose_as for server in self.servers for tool in server.tools.values()]
        duplicates = _duplicates(exposed)
        if duplicates:
            raise ValueError(f"Duplicate exposed MCP tool names: {duplicates}")
        return self

    @classmethod
    def from_yaml(cls, path: Path) -> MCPServersConfig:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("MCP server config must be a YAML object")
        return cls.model_validate(raw)


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)
