from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class ToolCategory(StrEnum):
    READ = "read"
    INTERNAL_WRITE = "internal_write"
    EXTERNAL_WRITE = "external_write"
    EXECUTE = "execute"


class DecisionAction(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


class ToolSpec(BaseModel):
    name: str
    category: ToolCategory
    description: str


class ToolCall(BaseModel):
    call_id: str
    session_id: str
    tool_name: str
    category: ToolCategory
    arguments: dict[str, Any]
    requested_at: datetime = Field(default_factory=utc_now)


class ToolResult(BaseModel):
    call_id: str
    status: str
    value: Any | None = None
    error: str | None = None
    completed_at: datetime = Field(default_factory=utc_now)


class DataArtifact(BaseModel):
    artifact_id: str
    session_id: str
    source_call_id: str
    source_tool: str
    resource: str | None = None
    labels: set[str] = Field(default_factory=set)
    length: int
    sha256: str


class ProvenanceMatch(BaseModel):
    artifact_id: str
    source_tool: str
    source_resource: str | None
    target_path: str
    match_type: str
    confidence: float
    labels: set[str]


class PolicyDecision(BaseModel):
    action: DecisionAction
    severity: str = "info"
    matched_rule: str | None = None
    reason: str
    matches: list[ProvenanceMatch] = Field(default_factory=list)


class TraceEvent(BaseModel):
    schema_version: str = "1.0"
    event_id: str
    trace_id: str
    session_id: str
    timestamp: datetime = Field(default_factory=utc_now)
    type: str
    payload: dict[str, Any]


class ScenarioReport(BaseModel):
    scenario: str
    mode: str
    trace_id: str
    normal_task_completed: bool
    attack_succeeded: bool
    secret_leaked: bool
    issue_created: bool
    blocked_calls: int
    matched_rules: list[str]
    trace_path: str
    duration_ms: float = 0.0
