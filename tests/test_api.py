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
        json={
            "runs": 1,
            "modes": ["normal", "baseline", "protected"],
            "transport": "inprocess",
        },
    )
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    listed = client.get("/api/v1/benchmarks").json()
    assert listed[0]["run_id"] == run_id
    report = client.get(f"/api/v1/benchmarks/{run_id}/report")
    assert report.status_code == 200
    assert "| baseline | 100% | 100% | 0% |" in report.text


def test_control_plane_lists_playground_scenarios_and_mcp_servers(tmp_path: Path) -> None:
    client = TestClient(
        create_app(
            runtime_dir=tmp_path,
            project_root=Path.cwd(),
            policy_path=Path("policies/default.yaml"),
        )
    )

    scenarios = client.get("/api/v1/playground/scenarios").json()
    assert {scenario["mode"] for scenario in scenarios} == {
        "normal",
        "baseline",
        "protected",
        "protected-base64",
        "protected-split",
        "baseline-malicious-mcp",
        "protected-malicious-mcp",
    }

    registry = client.get("/api/v1/mcp/servers").json()
    assert registry["status"] == "configured"
    assert [server["id"] for server in registry["servers"]] == [
        "email",
        "filesystem",
        "github",
        "attacker",
    ]
    assert registry["servers"][2]["tools"][0]["category"] == "external_write"


def test_control_plane_discovers_tools_and_runs_protected_playground(tmp_path: Path) -> None:
    client = TestClient(
        create_app(
            runtime_dir=tmp_path,
            project_root=Path.cwd(),
            policy_path=Path("policies/default.yaml"),
        )
    )

    discovery = client.post("/api/v1/mcp/servers/discover")
    assert discovery.status_code == 200
    email = discovery.json()["servers"][0]
    assert email["status"] == "healthy"
    assert email["hidden_tools"] == ["list_labels"]

    response = client.post("/api/v1/playground/runs", json={"mode": "protected"})
    assert response.status_code == 200
    result = response.json()
    assert result["simulator"] == "deterministic-mcp-agent"
    assert result["report"]["attack_succeeded"] is False
    assert result["report"]["blocked_calls"] == 1
    assert result["steps"][-1]["decision"] == "DENY"
    assert Path(result["report"]["trace_path"]).exists()


def test_remote_gateway_status_reports_offline_endpoint(tmp_path: Path) -> None:
    client = TestClient(
        create_app(
            runtime_dir=tmp_path,
            project_root=Path.cwd(),
            remote_mcp_url="http://127.0.0.1:9/mcp",
            remote_mcp_health_url="http://127.0.0.1:9/health",
        )
    )

    result = client.get("/api/v1/gateway/remote").json()
    assert result["status"] == "offline"
    assert result["transport"] == "streamable-http"
    assert result["endpoint"] == "http://127.0.0.1:9/mcp"
