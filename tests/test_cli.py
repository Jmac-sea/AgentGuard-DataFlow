from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from agentguard.cli import app

runner = CliRunner()


def test_demo_command(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["demo", "--mode", "protected", "--runtime-dir", str(tmp_path)],
    )

    assert result.exit_code == 0
    report = json.loads(result.stdout)
    assert report["blocked_calls"] == 1
    assert report["secret_leaked"] is False
