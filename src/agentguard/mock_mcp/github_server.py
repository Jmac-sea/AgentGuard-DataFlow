from __future__ import annotations

import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

server = FastMCP("AgentGuard Mock GitHub")


@server.tool(name="create_issue")
def create_issue(title: str, body: str) -> dict[str, object]:
    """Append one synthetic issue to a local JSONL audit file."""
    log_path = Path(os.getenv("AGENTGUARD_ISSUE_LOG", "runtime/mock-issues.jsonl"))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    issue = {"number": _next_number(log_path), "title": title, "body": body}
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(issue) + "\n")
    return issue


def _next_number(log_path: Path) -> int:
    if not log_path.exists():
        return 1
    with log_path.open(encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip()) + 1


if __name__ == "__main__":
    server.run(transport="stdio")
