from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from agentguard.models import ToolCategory, ToolSpec

ToolHandler = Callable[[dict[str, Any]], Any]


@dataclass
class MockEnvironment:
    emails: dict[str, str]
    files: dict[str, str]
    issues: list[dict[str, str]] = field(default_factory=list)
    sent_emails: list[dict[str, str]] = field(default_factory=list)


@dataclass
class RegisteredTool:
    spec: ToolSpec
    handler: ToolHandler | None


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, spec: ToolSpec, handler: ToolHandler) -> None:
        if spec.name in self._tools:
            raise ValueError(f"Tool already registered: {spec.name}")
        self._tools[spec.name] = RegisteredTool(spec=spec, handler=handler)

    def register_metadata(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"Tool already registered: {spec.name}")
        self._tools[spec.name] = RegisteredTool(spec=spec, handler=None)

    def spec(self, name: str) -> ToolSpec:
        try:
            return self._tools[name].spec
        except KeyError as exc:
            raise KeyError(f"Unknown tool: {name}") from exc

    def execute(self, name: str, arguments: dict[str, Any]) -> Any:
        try:
            tool = self._tools[name]
        except KeyError as exc:
            raise KeyError(f"Unknown tool: {name}") from exc
        if tool.handler is None:
            raise RuntimeError(f"Tool has metadata only and cannot execute locally: {name}")
        return tool.handler(arguments)


def create_mock_registry(environment: MockEnvironment) -> ToolRegistry:
    registry = ToolRegistry()

    def read_email(arguments: dict[str, Any]) -> str:
        message_id = str(arguments["message_id"])
        return environment.emails[message_id]

    def read_file(arguments: dict[str, Any]) -> str:
        path = str(arguments["path"])
        return environment.files[path]

    def create_issue(arguments: dict[str, Any]) -> dict[str, Any]:
        issue = {"title": str(arguments["title"]), "body": str(arguments["body"])}
        environment.issues.append(issue)
        return {"number": len(environment.issues), **issue}

    def send_email(arguments: dict[str, Any]) -> dict[str, Any]:
        email = {"to": str(arguments["to"]), "body": str(arguments["body"])}
        environment.sent_emails.append(email)
        return {"message_id": f"sent-{len(environment.sent_emails)}"}

    registry.register(
        ToolSpec(name="email.read", category=ToolCategory.READ, description="Read an email"),
        read_email,
    )
    registry.register(
        ToolSpec(
            name="filesystem.read", category=ToolCategory.READ, description="Read a local file"
        ),
        read_file,
    )
    registry.register(
        ToolSpec(
            name="github.create_issue",
            category=ToolCategory.EXTERNAL_WRITE,
            description="Create a public issue",
        ),
        create_issue,
    )
    registry.register(
        ToolSpec(
            name="email.send",
            category=ToolCategory.EXTERNAL_WRITE,
            description="Send an external email",
        ),
        send_email,
    )
    return registry


def create_mcp_metadata_registry(specs: list[ToolSpec] | None = None) -> ToolRegistry:
    """Create tool metadata for the real MCP gateway.

    Handlers are deliberately unusable because execution belongs to DownstreamManager.
    """

    registry = ToolRegistry()

    configured_specs = specs or [
        ToolSpec(name="email.read", category=ToolCategory.READ, description="Read an email"),
        ToolSpec(
            name="filesystem.read", category=ToolCategory.READ, description="Read a local file"
        ),
        ToolSpec(
            name="github.create_issue",
            category=ToolCategory.EXTERNAL_WRITE,
            description="Create a public issue",
        ),
    ]
    for spec in configured_specs:
        registry.register_metadata(spec)
    return registry
