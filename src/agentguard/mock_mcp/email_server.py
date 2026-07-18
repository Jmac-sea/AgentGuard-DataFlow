from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

server = FastMCP("AgentGuard Mock Email")


@server.tool(name="read")
def read_email(message_id: str) -> str:
    """Read one synthetic email message."""
    expected_id = os.getenv("AGENTGUARD_EMAIL_ID", "customer-001")
    if message_id != expected_id:
        raise KeyError(f"Unknown email: {message_id}")
    return os.getenv("AGENTGUARD_EMAIL_BODY", "Synthetic customer email")


@server.tool(name="list_labels")
def list_labels() -> list[str]:
    """Return synthetic mailbox labels used to test the gateway allowlist."""
    return ["inbox", "customer-support"]


if __name__ == "__main__":
    server.run(transport="stdio")
