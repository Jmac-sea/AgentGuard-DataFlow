from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer
import uvicorn

from agentguard.api import create_app
from agentguard.benchmark import DEFAULT_MODES, BenchmarkRunner
from agentguard.mcp_scenarios import MCPScenarioRunner
from agentguard.policy import PolicyEngine
from agentguard.replay import ReplayEngine
from agentguard.scenarios import ScenarioRunner

app = typer.Typer(help="AgentGuard DataFlow local security gateway MVP")
DEFAULT_PROJECT_ROOT = Path.cwd()
DEFAULT_POLICY_PATH = Path("policies/default.yaml")
DEFAULT_RUNTIME_DIR = Path("runtime")
DEFAULT_BENCHMARK_RUNTIME_DIR = Path("runtime-benchmark")


@app.callback()
def main() -> None:
    """Run AgentGuard DataFlow commands."""


@app.command()
def demo(
    mode: Annotated[
        str,
        typer.Option(
            help="Scenario mode: normal, baseline, protected, protected-base64, or protected-split"
        ),
    ] = "protected",
    runtime_dir: Annotated[Path, typer.Option(help="Trace and report output directory")] = Path(
        "runtime"
    ),
) -> None:
    """Run a deterministic end-to-end security scenario."""
    report = ScenarioRunner(runtime_dir=runtime_dir).run(mode)
    typer.echo(json.dumps(report.model_dump(mode="json"), indent=2))


@app.command(name="mcp-demo")
def mcp_demo(
    mode: Annotated[
        str,
        typer.Option(
            help="Scenario mode: normal, baseline, protected, protected-base64, or protected-split"
        ),
    ] = "protected",
    project_root: Annotated[Path, typer.Option(help="AgentGuard repository root")] = (
        DEFAULT_PROJECT_ROOT
    ),
    runtime_dir: Annotated[
        Path | None, typer.Option(help="Trace and report output directory")
    ] = None,
) -> None:
    """Run the scenario through a real stdio MCP gateway and downstream servers."""
    report = asyncio.run(MCPScenarioRunner(project_root, runtime_dir).run(mode))
    typer.echo(json.dumps(report.model_dump(mode="json"), indent=2))


@app.command()
def replay(
    trace: Annotated[Path, typer.Argument(help="JSONL trace to replay")],
    policy: Annotated[Path, typer.Option(help="YAML policy used for replay")] = DEFAULT_POLICY_PATH,
) -> None:
    """Re-evaluate a saved trace without calling the model or downstream MCP tools."""
    report = ReplayEngine(PolicyEngine.from_yaml(policy)).replay(trace)
    typer.echo(json.dumps(report.model_dump(mode="json"), indent=2))


@app.command(name="serve-api")
def serve_api(
    host: Annotated[str, typer.Option(help="API bind host")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="API bind port")] = 8000,
    runtime_dir: Annotated[
        Path, typer.Option(help="Trace runtime directory")
    ] = DEFAULT_RUNTIME_DIR,
    policy: Annotated[Path, typer.Option(help="Active YAML policy")] = DEFAULT_POLICY_PATH,
) -> None:
    """Serve Trace, Lineage, Policy, Replay, and Approval APIs."""
    uvicorn.run(create_app(runtime_dir=runtime_dir, policy_path=policy), host=host, port=port)


@app.command()
def benchmark(
    runs: Annotated[int, typer.Option(help="Runs per benchmark mode")] = 5,
    modes: Annotated[
        list[str] | None,
        typer.Option(help="Modes to include; repeat the option for multiple modes"),
    ] = None,
    runtime_dir: Annotated[Path, typer.Option(help="Benchmark output directory")] = (
        DEFAULT_BENCHMARK_RUNTIME_DIR
    ),
) -> None:
    """Run deterministic security scenarios and aggregate metrics."""
    report = BenchmarkRunner(runtime_dir).run(runs=runs, modes=modes or DEFAULT_MODES)
    typer.echo(json.dumps(report.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    app()
