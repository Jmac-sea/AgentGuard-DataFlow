from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from agentguard.approval import ApprovalStatus, ApprovalStore, SQLiteApprovalManager
from agentguard.benchmark import DEFAULT_MODES, BenchmarkRunner, BenchmarkStore
from agentguard.policy import PolicyDocument, PolicyEngine
from agentguard.replay import ReplayEngine


class PolicyValidationRequest(BaseModel):
    yaml: str


class ReplayRequest(BaseModel):
    trace_id: str
    policy_path: str | None = None


class BenchmarkRunRequest(BaseModel):
    runs: int = 5
    modes: list[str] = Field(default_factory=lambda: list(DEFAULT_MODES))


class TraceStore:
    def __init__(self, runtime_dir: Path) -> None:
        self.runtime_dir = runtime_dir

    @property
    def trace_dir(self) -> Path:
        return self.runtime_dir / "traces"

    def path(self, trace_id: str) -> Path:
        path = self.trace_dir / f"{trace_id}.jsonl"
        if not path.exists():
            raise FileNotFoundError(trace_id)
        return path

    def events(self, trace_id: str) -> list[dict[str, Any]]:
        return [
            json.loads(line)
            for line in self.path(trace_id).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def list(self) -> list[dict[str, Any]]:
        if not self.trace_dir.exists():
            return []
        traces: list[dict[str, Any]] = []
        for path in sorted(self.trace_dir.glob("tr_*.jsonl"), reverse=True):
            events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            traces.append(
                {
                    "trace_id": path.stem,
                    "event_count": len(events),
                    "blocked": any(event["type"] == "tool_call_blocked" for event in events),
                    "last_event_at": events[-1]["timestamp"] if events else None,
                }
            )
        return traces

    def lineage(self, trace_id: str) -> dict[str, Any]:
        nodes: dict[str, dict[str, Any]] = {}
        edges: list[dict[str, Any]] = []
        for event in self.events(trace_id):
            payload = event["payload"]
            if event["type"] == "tool_call_requested":
                call_id = str(payload["call_id"])
                nodes[call_id] = {
                    "id": call_id,
                    "type": "tool_call",
                    "label": payload["tool_name"],
                    "category": payload["category"],
                    "status": "requested",
                }
            elif event["type"] == "tool_call_blocked":
                call_id = str(payload["call_id"])
                if call_id in nodes:
                    nodes[call_id]["status"] = "blocked"
            elif event["type"] == "artifact_registered":
                artifact_id = str(payload["artifact_id"])
                nodes[artifact_id] = {
                    "id": artifact_id,
                    "type": "data_artifact",
                    "label": payload["resource"] or "Sensitive data",
                    "labels": payload["labels"],
                    "status": "critical",
                }
                edges.append(
                    {
                        "source": payload["source_call_id"],
                        "target": artifact_id,
                        "type": "produced",
                    }
                )
            elif event["type"] == "provenance_matched":
                edges.append(
                    {
                        "source": payload["artifact_id"],
                        "target": payload["target_call_id"],
                        "type": payload["match_type"],
                        "confidence": payload["confidence"],
                        "target_path": payload["target_path"],
                    }
                )
        return {"trace_id": trace_id, "nodes": list(nodes.values()), "edges": edges}


def create_app(
    *,
    runtime_dir: Path = Path("runtime"),
    policy_path: Path = Path("policies/default.yaml"),
    approvals: ApprovalStore | None = None,
) -> FastAPI:
    app = FastAPI(title="AgentGuard DataFlow API", version="0.1.0")
    store = TraceStore(runtime_dir)
    approval_manager = approvals or SQLiteApprovalManager(runtime_dir / "approvals.db")
    benchmark_store = BenchmarkStore(runtime_dir)

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/stats/overview")
    def overview() -> dict[str, int]:
        traces = store.list()
        return {
            "trace_count": len(traces),
            "blocked_trace_count": sum(bool(trace["blocked"]) for trace in traces),
        }

    @app.get("/api/v1/traces")
    def list_traces() -> list[dict[str, Any]]:
        return store.list()

    @app.get("/api/v1/traces/{trace_id}")
    def get_trace(trace_id: str) -> dict[str, Any]:
        try:
            events = store.events(trace_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Trace not found") from exc
        return {"trace_id": trace_id, "events": events}

    @app.get("/api/v1/traces/{trace_id}/lineage")
    def get_lineage(trace_id: str) -> dict[str, Any]:
        try:
            return store.lineage(trace_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Trace not found") from exc

    @app.get("/api/v1/policies/active")
    def active_policy() -> dict[str, Any]:
        try:
            engine = PolicyEngine.from_yaml(policy_path)
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return engine.document.model_dump(mode="json")

    @app.post("/api/v1/policies/validate")
    def validate_policy(request: PolicyValidationRequest) -> dict[str, Any]:
        import yaml

        try:
            raw = yaml.safe_load(request.yaml)
            document = PolicyDocument.model_validate(raw)
        except Exception as exc:
            return {"valid": False, "errors": [str(exc)]}
        return {"valid": True, "policy_id": document.policy_id, "errors": []}

    @app.post("/api/v1/replays")
    def replay(request: ReplayRequest) -> dict[str, Any]:
        selected_policy = Path(request.policy_path) if request.policy_path else policy_path
        try:
            report = ReplayEngine(PolicyEngine.from_yaml(selected_policy)).replay(
                store.path(request.trace_id)
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Trace or policy not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return report.model_dump(mode="json")

    @app.get("/api/v1/approvals")
    def list_approvals(status: ApprovalStatus | None = None) -> list[dict[str, Any]]:
        return [
            request.model_dump(mode="json", exclude={"token"})
            for request in approval_manager.list(status)
        ]

    @app.post("/api/v1/approvals/{approval_id}/approve")
    def approve(approval_id: str) -> dict[str, Any]:
        try:
            return approval_manager.approve(approval_id).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Approval not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/approvals/{approval_id}/reject")
    def reject(approval_id: str) -> dict[str, Any]:
        try:
            return approval_manager.reject(approval_id).model_dump(mode="json")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Approval not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/v1/benchmarks")
    def list_benchmarks() -> list[dict[str, Any]]:
        return [report.model_dump(mode="json") for report in benchmark_store.list()]

    @app.post("/api/v1/benchmarks/run")
    def run_benchmark(request: BenchmarkRunRequest) -> dict[str, Any]:
        try:
            report = BenchmarkRunner(runtime_dir).run(runs=request.runs, modes=request.modes)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return report.model_dump(mode="json")

    @app.get("/api/v1/benchmarks/{run_id}")
    def get_benchmark(run_id: str) -> dict[str, Any]:
        try:
            return benchmark_store.get(run_id).model_dump(mode="json")
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Benchmark not found") from exc

    @app.get("/api/v1/benchmarks/{run_id}/report", response_class=PlainTextResponse)
    def get_benchmark_report(run_id: str) -> str:
        try:
            return benchmark_store.markdown(run_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Benchmark not found") from exc

    return app
