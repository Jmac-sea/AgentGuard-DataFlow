from __future__ import annotations

from pathlib import Path

import pytest

from agentguard.models import (
    DecisionAction,
    ProvenanceMatch,
    ToolCall,
    ToolCategory,
)
from agentguard.policy import PolicyEngine


def test_secret_to_external_write_is_denied() -> None:
    call = ToolCall(
        call_id="call_write",
        session_id="ses_test",
        tool_name="github.create_issue",
        category=ToolCategory.EXTERNAL_WRITE,
        arguments={"body": "redacted"},
    )
    match = ProvenanceMatch(
        artifact_id="art_test",
        source_tool="filesystem.read",
        source_resource="/secrets/api_key.txt",
        target_path="$.body",
        match_type="exact_or_embedded",
        confidence=1.0,
        labels={"sensitivity:secret"},
    )

    decision = PolicyEngine().evaluate(call, [match])

    assert decision.action is DecisionAction.DENY
    assert decision.matched_rule == "block_secret_to_external"


def test_untracked_external_write_is_allowed() -> None:
    call = ToolCall(
        call_id="call_write",
        session_id="ses_test",
        tool_name="github.create_issue",
        category=ToolCategory.EXTERNAL_WRITE,
        arguments={"body": "public report"},
    )

    decision = PolicyEngine().evaluate(call, [])

    assert decision.action is DecisionAction.ALLOW


def test_default_yaml_policy_loads() -> None:
    engine = PolicyEngine.from_yaml(Path("policies/default.yaml"))

    assert engine.policy_id == "agentguard-default"


def test_higher_priority_rule_wins(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(
        """
version: "1.0"
policy_id: priority-test
defaults:
  external_write: allow
rules:
  - id: allow-github
    priority: 10
    when:
      all:
        - target.tool.eq: github.create_issue
    action: allow
  - id: deny-github
    priority: 20
    when:
      all:
        - target.tool.eq: github.create_issue
    action: deny
""".strip(),
        encoding="utf-8",
    )
    call = ToolCall(
        call_id="call_write",
        session_id="ses_test",
        tool_name="github.create_issue",
        category=ToolCategory.EXTERNAL_WRITE,
        arguments={},
    )

    decision = PolicyEngine.from_yaml(policy_path).evaluate(call, [])

    assert decision.action is DecisionAction.DENY
    assert decision.matched_rule == "deny-github"


def test_duplicate_rule_ids_are_rejected(tmp_path: Path) -> None:
    policy_path = tmp_path / "invalid.yaml"
    policy_path.write_text(
        """
policy_id: invalid
rules:
  - id: duplicate
    when: {target.tool.eq: one}
    action: allow
  - id: duplicate
    when: {target.tool.eq: two}
    action: deny
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unique"):
        PolicyEngine.from_yaml(policy_path)
