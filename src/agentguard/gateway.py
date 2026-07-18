from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from agentguard.approval import ApprovalManager, ApprovalRequest, ApprovalStore
from agentguard.dataflow import ArtifactRegistry
from agentguard.models import DecisionAction, PolicyDecision, ToolCall, ToolResult
from agentguard.policy import PolicyEngine
from agentguard.tools import ToolRegistry
from agentguard.tracing import TraceCollector


class ToolBlockedError(RuntimeError):
    def __init__(self, decision: PolicyDecision) -> None:
        super().__init__(decision.reason)
        self.decision = decision


class ToolApprovalRequiredError(RuntimeError):
    def __init__(self, request: ApprovalRequest) -> None:
        super().__init__(f"Approval required: {request.approval_id}")
        self.request = request


class ToolGateway:
    def __init__(
        self,
        *,
        registry: ToolRegistry,
        session_id: str,
        trace_id: str,
        canaries: set[str],
        protection_enabled: bool,
        output_dir: Path,
        policy: PolicyEngine | None = None,
        approvals: ApprovalStore | None = None,
    ) -> None:
        self.registry = registry
        self.session_id = session_id
        self.trace_id = trace_id
        self.protection_enabled = protection_enabled
        self.artifacts = ArtifactRegistry(session_id=session_id, canaries=canaries)
        self.policy = policy or PolicyEngine()
        self.approvals = approvals or ApprovalManager()
        self.trace = TraceCollector(
            trace_id=trace_id,
            session_id=session_id,
            output_dir=output_dir,
            canaries=canaries,
        )
        self.blocked_calls = 0
        self.matched_rules: list[str] = []

    def call(
        self, tool_name: str, arguments: dict[str, Any], approval_token: str | None = None
    ) -> Any:
        spec = self.registry.spec(tool_name)
        call = ToolCall(
            call_id=f"call_{uuid4().hex[:12]}",
            session_id=self.session_id,
            tool_name=tool_name,
            category=spec.category,
            arguments=arguments,
        )
        self.trace.emit(
            "tool_call_requested",
            {
                "call_id": call.call_id,
                "tool_name": call.tool_name,
                "category": call.category,
                "arguments": arguments,
            },
        )

        matches = self.artifacts.match_arguments(arguments)
        for match in matches:
            self.trace.emit(
                "provenance_matched",
                {"target_call_id": call.call_id, **match.model_dump(mode="json")},
            )

        decision = self.policy.evaluate(call, matches)
        effective_decision = decision
        if not self.protection_enabled and decision.action is DecisionAction.DENY:
            effective_decision = decision.model_copy(
                update={
                    "action": DecisionAction.ALLOW,
                    "reason": "Protection disabled; blocking decision observed only",
                }
            )
        self.trace.emit(
            "policy_decided",
            {
                "call_id": call.call_id,
                "action": effective_decision.action,
                "severity": decision.severity,
                "matched_rule": decision.matched_rule,
                "reason": effective_decision.reason,
            },
        )

        if decision.matched_rule and decision.matched_rule not in self.matched_rules:
            self.matched_rules.append(decision.matched_rule)

        if effective_decision.action is DecisionAction.DENY:
            self.blocked_calls += 1
            self.trace.emit(
                "tool_call_blocked",
                {"call_id": call.call_id, "tool_name": tool_name, "reason": decision.reason},
            )
            raise ToolBlockedError(decision)
        if effective_decision.action is DecisionAction.REQUIRE_APPROVAL:
            if approval_token is not None:
                approval = self.approvals.authorize(
                    token=approval_token,
                    session_id=self.session_id,
                    tool_name=tool_name,
                    arguments=arguments,
                )
                self.trace.emit(
                    "approval_consumed",
                    {"call_id": call.call_id, "approval_id": approval.approval_id},
                )
            else:
                approval = self.approvals.create(
                    call_id=call.call_id,
                    session_id=self.session_id,
                    tool_name=tool_name,
                    arguments=arguments,
                    decision=decision,
                )
                self.trace.emit(
                    "approval_required",
                    {
                        "call_id": call.call_id,
                        "approval_id": approval.approval_id,
                        "tool_name": tool_name,
                        "arguments_digest": approval.arguments_digest,
                    },
                )
                raise ToolApprovalRequiredError(approval)

        try:
            value = self.registry.execute(tool_name, arguments)
        except Exception as exc:
            result = ToolResult(call_id=call.call_id, status="error", error=str(exc))
            self.trace.emit("tool_call_completed", result.model_dump(mode="json"))
            raise

        result = ToolResult(call_id=call.call_id, status="success", value=value)
        self.trace.emit("tool_call_completed", result.model_dump(mode="json"))
        artifacts = self.artifacts.register_tool_result(
            call_id=call.call_id,
            tool_name=tool_name,
            arguments=arguments,
            result=value,
        )
        for artifact in artifacts:
            self.trace.emit(
                "artifact_registered",
                {
                    "artifact_id": artifact.artifact_id,
                    "source_call_id": artifact.source_call_id,
                    "source_tool": artifact.source_tool,
                    "resource": artifact.resource,
                    "labels": artifact.labels,
                    "length": artifact.length,
                    "sha256": artifact.sha256,
                },
            )
        return value
