from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from agentguard.models import (
    DecisionAction,
    PolicyDecision,
    ProvenanceMatch,
    ToolCall,
    ToolCategory,
)

STRICTNESS = {
    DecisionAction.ALLOW: 0,
    DecisionAction.REQUIRE_APPROVAL: 1,
    DecisionAction.DENY: 2,
}
OPERATORS = {"eq", "neq", "in", "not_in", "contains", "not_contains", "gte", "lte", "exists"}


class PolicyRule(BaseModel):
    id: str
    description: str = ""
    priority: int = 0
    when: dict[str, Any]
    action: DecisionAction
    severity: str = "info"

    @field_validator("action", mode="before")
    @classmethod
    def normalize_action(cls, value: Any) -> Any:
        return value.upper() if isinstance(value, str) else value


class PolicyDocument(BaseModel):
    version: str = "1.0"
    policy_id: str
    defaults: dict[ToolCategory, DecisionAction] = Field(default_factory=dict)
    rules: list[PolicyRule] = Field(default_factory=list)

    @field_validator("defaults", mode="before")
    @classmethod
    def normalize_defaults(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        return {
            str(key).lower(): item.upper() if isinstance(item, str) else item
            for key, item in value.items()
        }

    @model_validator(mode="after")
    def validate_unique_rules(self) -> PolicyDocument:
        ids = [rule.id for rule in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError("Policy rule IDs must be unique")
        return self


def default_policy_document() -> PolicyDocument:
    return PolicyDocument.model_validate(
        {
            "version": "1.0",
            "policy_id": "agentguard-default",
            "defaults": {
                "read": "ALLOW",
                "internal_write": "REQUIRE_APPROVAL",
                "external_write": "ALLOW",
                "execute": "DENY",
            },
            "rules": [
                {
                    "id": "block_secret_to_external",
                    "description": "Block tracked secret data from external write tools",
                    "priority": 100,
                    "when": {
                        "all": [
                            {"target.category.eq": "external_write"},
                            {"provenance.labels.contains": "sensitivity:secret"},
                            {"provenance.confidence.gte": 0.85},
                        ]
                    },
                    "action": "DENY",
                    "severity": "critical",
                }
            ],
        }
    )


class PolicyEngine:
    def __init__(self, document: PolicyDocument | None = None) -> None:
        self.document = document or default_policy_document()

    @classmethod
    def from_yaml(cls, path: Path) -> PolicyEngine:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Policy file must contain a YAML object")
        return cls(PolicyDocument.model_validate(raw))

    @property
    def policy_id(self) -> str:
        return self.document.policy_id

    def evaluate(self, call: ToolCall, matches: list[ProvenanceMatch]) -> PolicyDecision:
        matched_rules: list[PolicyRule] = []
        contexts = [self._context(call, match) for match in matches]
        if not contexts:
            contexts = [self._context(call, None)]

        for rule in self.document.rules:
            if any(self._evaluate_expression(rule.when, context) for context in contexts):
                matched_rules.append(rule)

        if matched_rules:
            rule = max(
                matched_rules,
                key=lambda item: (item.priority, STRICTNESS[item.action]),
            )
            return PolicyDecision(
                action=rule.action,
                severity=rule.severity,
                matched_rule=rule.id,
                reason=rule.description or f"Policy rule matched: {rule.id}",
                matches=matches,
            )

        action = self.document.defaults.get(call.category, DecisionAction.DENY)
        return PolicyDecision(
            action=action,
            reason=f"Default decision for tool category {call.category.value}",
            matches=matches,
        )

    @staticmethod
    def _context(call: ToolCall, match: ProvenanceMatch | None) -> dict[str, Any]:
        provenance: dict[str, Any] = {
            "exists": match is not None,
            "source_tool": None,
            "resource": None,
            "labels": set(),
            "match_type": None,
            "confidence": 0.0,
        }
        if match is not None:
            provenance.update(
                {
                    "source_tool": match.source_tool,
                    "resource": match.source_resource,
                    "labels": match.labels,
                    "match_type": match.match_type,
                    "confidence": match.confidence,
                }
            )
        return {
            "target": {
                "tool": call.tool_name,
                "category": call.category.value,
                "arguments": call.arguments,
            },
            "provenance": provenance,
        }

    def _evaluate_expression(self, expression: Any, context: dict[str, Any]) -> bool:
        if not isinstance(expression, dict) or len(expression) != 1:
            raise ValueError(f"Invalid policy expression: {expression!r}")
        key, expected = next(iter(expression.items()))
        if key == "all":
            return isinstance(expected, list) and all(
                self._evaluate_expression(item, context) for item in expected
            )
        if key == "any":
            return isinstance(expected, list) and any(
                self._evaluate_expression(item, context) for item in expected
            )
        if key == "not":
            return not self._evaluate_expression(expected, context)

        field_path, operator = self._parse_condition_key(key)
        actual = self._resolve(context, field_path)
        return self._compare(actual, operator, expected)

    @staticmethod
    def _parse_condition_key(key: str) -> tuple[str, str]:
        parts = key.split(".")
        if parts[-1] in OPERATORS:
            return ".".join(parts[:-1]), parts[-1]
        return key, "eq"

    @staticmethod
    def _resolve(context: dict[str, Any], path: str) -> Any:
        current: Any = context
        for part in path.split("."):
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        return current

    @staticmethod
    def _compare(
        actual: Any,
        operator: Literal[
            "eq", "neq", "in", "not_in", "contains", "not_contains", "gte", "lte", "exists"
        ]
        | str,
        expected: Any,
    ) -> bool:
        if operator == "eq":
            return bool(actual == expected)
        if operator == "neq":
            return bool(actual != expected)
        if operator == "in":
            return actual in expected
        if operator == "not_in":
            return actual not in expected
        if operator == "contains":
            return actual is not None and expected in actual
        if operator == "not_contains":
            return actual is None or expected not in actual
        if operator == "gte":
            return actual is not None and actual >= expected
        if operator == "lte":
            return actual is not None and actual <= expected
        if operator == "exists":
            return (actual is not None) is bool(expected)
        raise ValueError(f"Unsupported policy operator: {operator}")
