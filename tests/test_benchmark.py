from __future__ import annotations

from pathlib import Path

import pytest

from agentguard.benchmark import BenchmarkRunner, BenchmarkStore


def test_benchmark_aggregates_security_metrics(tmp_path: Path) -> None:
    report = BenchmarkRunner(tmp_path).run(
        runs=2,
        modes=["normal", "baseline", "protected", "protected-base64", "protected-split"],
    )
    metrics = {metric.mode: metric for metric in report.metrics}

    assert metrics["normal"].normal_task_completion_rate == 1.0
    assert metrics["normal"].secret_leak_rate == 0.0
    assert metrics["baseline"].attack_success_rate == 1.0
    assert metrics["baseline"].secret_leak_rate == 1.0
    assert metrics["protected"].secret_leak_rate == 0.0
    assert metrics["protected-base64"].blocking_rate == 1.0
    assert metrics["protected-split"].blocking_rate == 1.0

    stored = BenchmarkStore(tmp_path).get(report.run_id)
    assert stored.run_id == report.run_id
    markdown = BenchmarkStore(tmp_path).markdown(report.run_id)
    assert "| baseline | 100% | 100% |" in markdown


def test_benchmark_rejects_invalid_configuration(tmp_path: Path) -> None:
    runner = BenchmarkRunner(tmp_path)

    with pytest.raises(ValueError, match="between 1 and 100"):
        runner.run(runs=0)
    with pytest.raises(ValueError, match="Unsupported"):
        runner.run(runs=1, modes=["unknown"])
