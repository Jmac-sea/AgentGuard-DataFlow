from __future__ import annotations

from pathlib import Path

from agentguard.scenarios import CANARY, ScenarioRunner


def test_normal_task_is_allowed(tmp_path: Path) -> None:
    report = ScenarioRunner(tmp_path).run("normal")

    assert report.normal_task_completed is True
    assert report.issue_created is True
    assert report.secret_leaked is False
    assert report.blocked_calls == 0


def test_baseline_reproduces_secret_leak(tmp_path: Path) -> None:
    report = ScenarioRunner(tmp_path).run("baseline")

    assert report.attack_succeeded is True
    assert report.secret_leaked is True
    assert report.issue_created is True
    assert report.blocked_calls == 0
    assert "block_secret_to_external" in report.matched_rules


def test_protected_mode_blocks_external_write(tmp_path: Path) -> None:
    report = ScenarioRunner(tmp_path).run("protected")

    assert report.attack_succeeded is False
    assert report.secret_leaked is False
    assert report.issue_created is False
    assert report.blocked_calls == 1
    assert "block_secret_to_external" in report.matched_rules


def test_protected_mode_detects_base64_transformation(tmp_path: Path) -> None:
    report = ScenarioRunner(tmp_path).run("protected-base64")

    assert report.secret_leaked is False
    assert report.issue_created is False
    assert report.blocked_calls == 1


def test_protected_mode_detects_split_recombination(tmp_path: Path) -> None:
    report = ScenarioRunner(tmp_path).run("protected-split")

    assert report.secret_leaked is False
    assert report.issue_created is False
    assert report.blocked_calls == 1


def test_trace_never_persists_raw_canary(tmp_path: Path) -> None:
    report = ScenarioRunner(tmp_path).run("baseline")
    trace = Path(report.trace_path).read_text(encoding="utf-8")

    assert CANARY not in trace
    assert "[REDACTED]" in trace
