from __future__ import annotations

from pathlib import Path

from agentguard.policy import PolicyEngine
from agentguard.replay import ReplayEngine
from agentguard.scenarios import ScenarioRunner


def test_replay_changes_baseline_observation_to_deny(tmp_path: Path) -> None:
    scenario = ScenarioRunner(tmp_path).run("baseline")

    replay = ReplayEngine(PolicyEngine.from_yaml(Path("policies/default.yaml"))).replay(
        Path(scenario.trace_path)
    )

    changed = [decision for decision in replay.decisions if decision.changed]
    assert replay.policy_id == "agentguard-default"
    assert len(changed) == 1
    assert changed[0].tool_name == "github.create_issue"
    assert changed[0].original_action == "ALLOW"
    assert changed[0].replayed_action == "DENY"
