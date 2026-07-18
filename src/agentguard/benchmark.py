from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from agentguard.models import ScenarioReport
from agentguard.scenarios import ScenarioRunner

DEFAULT_MODES = ["normal", "baseline", "protected", "protected-base64", "protected-split"]


class ModeMetrics(BaseModel):
    mode: str
    runs: int
    attack_success_rate: float
    secret_leak_rate: float
    issue_creation_rate: float
    blocking_rate: float
    normal_task_completion_rate: float
    trace_ids: list[str] = Field(default_factory=list)


class BenchmarkReport(BaseModel):
    run_id: str
    created_at: datetime
    runs_per_mode: int
    modes: list[str]
    metrics: list[ModeMetrics]


class BenchmarkRunner:
    def __init__(self, runtime_dir: Path) -> None:
        self.runtime_dir = runtime_dir

    def run(self, *, runs: int = 5, modes: list[str] | None = None) -> BenchmarkReport:
        selected_modes = modes or DEFAULT_MODES
        if runs < 1 or runs > 100:
            raise ValueError("runs must be between 1 and 100")
        unknown = set(selected_modes) - set(DEFAULT_MODES)
        if unknown:
            raise ValueError(f"Unsupported benchmark modes: {sorted(unknown)}")

        run_id = f"bench_{uuid4().hex[:12]}"
        scenario_dir = self.runtime_dir / "benchmark-runs" / run_id
        runner = ScenarioRunner(scenario_dir)
        metrics: list[ModeMetrics] = []
        for mode in selected_modes:
            reports = [runner.run(mode) for _ in range(runs)]
            metrics.append(self._aggregate(mode, reports))

        report = BenchmarkReport(
            run_id=run_id,
            created_at=datetime.now(UTC),
            runs_per_mode=runs,
            modes=selected_modes,
            metrics=metrics,
        )
        self.save(report)
        return report

    def save(self, report: BenchmarkReport) -> None:
        output_dir = self.runtime_dir / "benchmarks"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / f"{report.run_id}.json").write_text(
            json.dumps(report.model_dump(mode="json"), indent=2), encoding="utf-8"
        )
        (output_dir / f"{report.run_id}.md").write_text(self.to_markdown(report), encoding="utf-8")

    @staticmethod
    def _aggregate(mode: str, reports: list[ScenarioReport]) -> ModeMetrics:
        count = len(reports)
        return ModeMetrics(
            mode=mode,
            runs=count,
            attack_success_rate=sum(report.attack_succeeded for report in reports) / count,
            secret_leak_rate=sum(report.secret_leaked for report in reports) / count,
            issue_creation_rate=sum(report.issue_created for report in reports) / count,
            blocking_rate=sum(report.blocked_calls > 0 for report in reports) / count,
            normal_task_completion_rate=(
                sum(report.normal_task_completed for report in reports) / count
            ),
            trace_ids=[report.trace_id for report in reports],
        )

    @staticmethod
    def to_markdown(report: BenchmarkReport) -> str:
        lines = [
            f"# AgentGuard Benchmark {report.run_id}",
            "",
            f"Created: {report.created_at.isoformat()}",
            f"Runs per mode: {report.runs_per_mode}",
            "",
            "| Mode | Attack success | Secret leak | Issue creation | Blocking | Task completion |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for metric in report.metrics:
            lines.append(
                "| "
                f"{metric.mode} | {metric.attack_success_rate:.0%} | "
                f"{metric.secret_leak_rate:.0%} | {metric.issue_creation_rate:.0%} | "
                f"{metric.blocking_rate:.0%} | {metric.normal_task_completion_rate:.0%} |"
            )
        return "\n".join(lines) + "\n"


class BenchmarkStore:
    def __init__(self, runtime_dir: Path) -> None:
        self.output_dir = runtime_dir / "benchmarks"

    def list(self) -> list[BenchmarkReport]:
        if not self.output_dir.exists():
            return []
        reports = [self.get(path.stem) for path in self.output_dir.glob("bench_*.json")]
        return sorted(reports, key=lambda report: report.created_at, reverse=True)

    def get(self, run_id: str) -> BenchmarkReport:
        path = self.output_dir / f"{run_id}.json"
        if not path.exists():
            raise FileNotFoundError(run_id)
        return BenchmarkReport.model_validate_json(path.read_text(encoding="utf-8"))

    def markdown(self, run_id: str) -> str:
        path = self.output_dir / f"{run_id}.md"
        if not path.exists():
            raise FileNotFoundError(run_id)
        return path.read_text(encoding="utf-8")
