from __future__ import annotations

import anyio
from mcp.server.stdio import stdio_server

from agentguard.mcp_runtime.gateway_runtime import create_gateway_server

server = create_gateway_server()


async def run() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    anyio.run(run)
