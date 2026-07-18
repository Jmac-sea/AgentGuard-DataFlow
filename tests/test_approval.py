from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from agentguard.approval import ApprovalManager, ApprovalStatus, SQLiteApprovalManager
from agentguard.gateway import ToolApprovalRequiredError, ToolGateway
from agentguard.models import DecisionAction, PolicyDecision
from agentguard.policy import PolicyDocument, PolicyEngine
from agentguard.tools import MockEnvironment, create_mock_registry


def approval_decision() -> PolicyDecision:
    return PolicyDecision(
        action=DecisionAction.REQUIRE_APPROVAL,
        severity="high",
        matched_rule="approve_external_write",
        reason="External write requires approval",
    )


def test_approval_token_is_bound_and_single_use() -> None:
    manager = ApprovalManager(token_ttl=timedelta(minutes=5))
    request = manager.create(
        call_id="call_1",
        session_id="ses_1",
        tool_name="github.create_issue",
        arguments={"title": "A", "body": "B"},
        decision=approval_decision(),
    )
    approved = manager.approve(request.approval_id)
    assert approved.token is not None

    consumed = manager.authorize(
        token=approved.token,
        session_id="ses_1",
        tool_name="github.create_issue",
        arguments={"title": "A", "body": "B"},
    )
    assert consumed.status is ApprovalStatus.CONSUMED

    with pytest.raises(ValueError, match="Unknown"):
        manager.authorize(
            token=approved.token,
            session_id="ses_1",
            tool_name="github.create_issue",
            arguments={"title": "A", "body": "B"},
        )


def test_changed_arguments_invalidate_approval() -> None:
    manager = ApprovalManager()
    request = manager.create(
        call_id="call_1",
        session_id="ses_1",
        tool_name="github.create_issue",
        arguments={"title": "A", "body": "B"},
        decision=approval_decision(),
    )
    approved = manager.approve(request.approval_id)
    assert approved.token is not None

    with pytest.raises(ValueError, match="arguments changed"):
        manager.authorize(
            token=approved.token,
            session_id="ses_1",
            tool_name="github.create_issue",
            arguments={"title": "A", "body": "CHANGED"},
        )


def test_expired_approval_is_rejected() -> None:
    manager = ApprovalManager(token_ttl=timedelta(seconds=1))
    issued_at = datetime(2026, 7, 18, tzinfo=UTC)
    request = manager.create(
        call_id="call_1",
        session_id="ses_1",
        tool_name="github.create_issue",
        arguments={},
        decision=approval_decision(),
    )
    approved = manager.approve(request.approval_id, now=issued_at)
    assert approved.token is not None

    with pytest.raises(ValueError, match="expired"):
        manager.authorize(
            token=approved.token,
            session_id="ses_1",
            tool_name="github.create_issue",
            arguments={},
            now=issued_at + timedelta(seconds=2),
        )


def test_gateway_executes_only_after_approval(tmp_path: Path) -> None:
    policy = PolicyEngine(
        PolicyDocument.model_validate(
            {
                "policy_id": "approval-test",
                "defaults": {"read": "allow", "external_write": "require_approval"},
            }
        )
    )
    environment = MockEnvironment(emails={}, files={})
    approvals = ApprovalManager()
    gateway = ToolGateway(
        registry=create_mock_registry(environment),
        session_id="ses_1",
        trace_id="tr_1",
        canaries=set(),
        protection_enabled=True,
        output_dir=tmp_path,
        policy=policy,
        approvals=approvals,
    )
    arguments = {"title": "Approved issue", "body": "Public body"}

    with pytest.raises(ToolApprovalRequiredError) as raised:
        gateway.call("github.create_issue", arguments)
    approved = approvals.approve(raised.value.request.approval_id)
    assert approved.token is not None

    result = gateway.call("github.create_issue", arguments, approval_token=approved.token)

    assert result["number"] == 1
    assert len(environment.issues) == 1


def test_sqlite_approval_is_consumed_across_manager_instances(tmp_path: Path) -> None:
    database = tmp_path / "approvals.db"
    api_manager = SQLiteApprovalManager(database)
    request = api_manager.create(
        call_id="call_1",
        session_id="ses_shared",
        tool_name="github.create_issue",
        arguments={"title": "A", "body": "B"},
        decision=approval_decision(),
    )
    approved = api_manager.approve(request.approval_id)
    assert approved.token is not None

    gateway_manager = SQLiteApprovalManager(database)
    consumed = gateway_manager.authorize(
        token=approved.token,
        session_id="ses_shared",
        tool_name="github.create_issue",
        arguments={"title": "A", "body": "B"},
    )

    assert consumed.status is ApprovalStatus.CONSUMED
    assert api_manager.get(request.approval_id).status is ApprovalStatus.CONSUMED
