from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from agentguard.models import ProvenanceMatch, ToolCall
from agentguard.policy import PolicyEngine


class ReplayedDecision(BaseModel):
    call_id: str
    tool_name: str
    original_action: str
    replayed_action: str
    original_rule: str | None = None
    replayed_rule: str | None = None
    changed: bool


class ReplayReport(BaseModel):
    trace_id: str
    policy_id: str
    decisions: list[ReplayedDecision] = Field(default_factory=list)

    @property
    def changed_decisions(self) -> int:
        return sum(decision.changed for decision in self.decisions)


class ReplayEngine:
    def __init__(self, policy: PolicyEngine) -> None:
        self.policy = policy

    def replay(self, trace_path: Path) -> ReplayReport:
        events = [
            json.loads(line)
            for line in trace_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if not events:
            raise ValueError("Trace is empty")
        trace_id = str(events[0]["trace_id"])
        calls: dict[str, ToolCall] = {}
        matches: dict[str, list[ProvenanceMatch]] = {}
        original_decisions: dict[str, dict[str, Any]] = {}

        for event in events:
            payload = event["payload"]
            if event["type"] == "tool_call_requested":
                call_id = str(payload["call_id"])
                calls[call_id] = ToolCall(
                    call_id=call_id,
                    session_id=str(event["session_id"]),
                    tool_name=str(payload["tool_name"]),
                    category=payload["category"],
                    arguments=payload.get("arguments", {}),
                )
            elif event["type"] == "provenance_matched":
                target_call_id = str(payload["target_call_id"])
                match_payload = {
                    key: value for key, value in payload.items() if key != "target_call_id"
                }
                matches.setdefault(target_call_id, []).append(
                    ProvenanceMatch.model_validate(match_payload)
                )
            elif event["type"] == "policy_decided":
                original_decisions[str(payload["call_id"])] = payload

        decisions: list[ReplayedDecision] = []
        for call_id, original in original_decisions.items():
            call = calls[call_id]
            replayed = self.policy.evaluate(call, matches.get(call_id, []))
            original_action = str(original["action"])
            decisions.append(
                ReplayedDecision(
                    call_id=call_id,
                    tool_name=call.tool_name,
                    original_action=original_action,
                    replayed_action=replayed.action.value,
                    original_rule=original.get("matched_rule"),
                    replayed_rule=replayed.matched_rule,
                    changed=original_action != replayed.action.value,
                )
            )
        return ReplayReport(trace_id=trace_id, policy_id=self.policy.policy_id, decisions=decisions)
