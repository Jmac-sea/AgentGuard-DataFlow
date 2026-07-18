from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

import httpx
import pytest

from agentguard.mcp_runtime.client import MCPHTTPClient
from agentguard.mcp_runtime.http_gateway import validate_remote_binding
from agentguard.scenarios import CANARY, MALICIOUS_EMAIL


def test_remote_binding_requires_bearer_token() -> None:
    with pytest.raises(ValueError, match="bearer token"):
        validate_remote_binding("0.0.0.0", None)

    validate_remote_binding("127.0.0.1", None)
    validate_remote_binding("0.0.0.0", "test-token")


def test_streamable_http_gateway_discovers_tools_and_blocks_leakage(tmp_path: Path) -> None:
    port = _free_port()
    token = "integration-test-token"
    issue_log = tmp_path / "issues.jsonl"
    command = [
        sys.executable,
        "-m",
        "agentguard.cli",
        "serve-mcp-http",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--project-root",
        str(Path.cwd()),
        "--runtime-dir",
        str(tmp_path),
        "--token",
        token,
    ]
    process = subprocess.Popen(
        command,
        cwd=Path.cwd(),
        env={
            **os.environ,
            "AGENTGUARD_EMAIL_BODY": MALICIOUS_EMAIL,
            "AGENTGUARD_CANARY": CANARY,
            "AGENTGUARD_ISSUE_LOG": str(issue_log),
        },
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for_health(f"http://127.0.0.1:{port}/health", process)
        unauthorized = httpx.post(
            f"http://127.0.0.1:{port}/mcp",
            json={},
            timeout=5,
        )
        assert unauthorized.status_code == 401

        async def run() -> None:
            async with MCPHTTPClient(f"http://127.0.0.1:{port}/mcp", token=token) as client:
                assert set(await client.list_tools()) == {
                    "email.read",
                    "filesystem.read",
                    "github.create_issue",
                    "attacker.search_ticket",
                    "attacker.exfiltrate",
                }
                email = await client.call_tool("email.read", {"message_id": "customer-001"})
                secret = await client.call_tool("filesystem.read", {"path": "/secrets/api_key.txt"})
                with pytest.raises(RuntimeError, match="Tracked secret data"):
                    await client.call_tool(
                        "github.create_issue",
                        {"title": "Injected task", "body": f"{email}\n{secret}"},
                    )

        asyncio.run(run())
        assert not issue_log.exists()
        traces = list((tmp_path / "traces").glob("tr_*.jsonl"))
        assert len(traces) == 1
        assert CANARY not in traces[0].read_text(encoding="utf-8")
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover
            process.kill()
            process.wait(timeout=5)


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _wait_for_health(url: str, process: subprocess.Popen[bytes]) -> None:
    for _ in range(80):
        if process.poll() is not None:
            raise RuntimeError(f"MCP HTTP server exited with code {process.returncode}")
        try:
            with urlopen(url, timeout=1) as response:  # noqa: S310
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.25)
    raise TimeoutError("MCP HTTP server did not become healthy")
