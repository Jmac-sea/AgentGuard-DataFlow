from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from agentguard.api import create_app
from agentguard.approval import ApprovalManager
from agentguard.models import DecisionAction, PolicyDecision
from agentguard.scenarios import ScenarioRunner


def test_trace_and_lineage_endpoints(tmp_path: Path) -> None:
    report = ScenarioRunner(tmp_path).run("protected")
    client = TestClient(create_app(runtime_dir=tmp_path, policy_path=Path("policies/default.yaml")))

    assert client.get("/api/v1/health").json() == {"status": "ok"}
    traces = client.get("/api/v1/traces").json()
    assert traces[0]["trace_id"] == report.trace_id
    assert traces[0]["blocked"] is True

    lineage = client.get(f"/api/v1/traces/{report.trace_id}/lineage").json()
    assert lineage["trace_id"] == report.trace_id
    assert any(node["type"] == "data_artifact" for node in lineage["nodes"])
    assert any(edge["type"] == "exact_or_embedded" for edge in lineage["edges"])


def test_policy_validation_and_replay_api(tmp_path: Path) -> None:
    report = ScenarioRunner(tmp_path).run("baseline")
    client = TestClient(create_app(runtime_dir=tmp_path, policy_path=Path("policies/default.yaml")))
    policy_text = Path("policies/default.yaml").read_text(encoding="utf-8")

    validation = client.post("/api/v1/policies/validate", json={"yaml": policy_text}).json()
    assert validation["valid"] is True

    replay = client.post("/api/v1/replays", json={"trace_id": report.trace_id}).json()
    changed = [decision for decision in replay["decisions"] if decision["changed"]]
    assert changed[0]["tool_name"] == "github.create_issue"
    assert changed[0]["replayed_action"] == "DENY"


def test_approval_api_returns_token_only_on_approve() -> None:
    approvals = ApprovalManager()
    request = approvals.create(
        call_id="call_1",
        session_id="ses_1",
        tool_name="github.create_issue",
        arguments={"title": "A", "body": "B"},
        decision=PolicyDecision(
            action=DecisionAction.REQUIRE_APPROVAL,
            reason="Review external write",
        ),
    )
    client = TestClient(create_app(approvals=approvals))

    listed = client.get("/api/v1/approvals").json()
    assert "token" not in listed[0]

    approved = client.post(f"/api/v1/approvals/{request.approval_id}/approve").json()
    assert approved["status"] == "approved"
    assert approved["token"]


def test_benchmark_api_runs_and_returns_markdown(tmp_path: Path) -> None:
    client = TestClient(create_app(runtime_dir=tmp_path, policy_path=Path("policies/default.yaml")))

    response = client.post(
        "/api/v1/benchmarks/run",
        json={"runs": 1, "modes": ["normal", "baseline", "protected"]},
    )
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    listed = client.get("/api/v1/benchmarks").json()
    assert listed[0]["run_id"] == run_id
    report = client.get(f"/api/v1/benchmarks/{run_id}/report")
    assert report.status_code == 200
    assert "| baseline | 100% | 100% |" in report.text
