from __future__ import annotations

import hmac
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from agentguard.mcp_runtime.gateway_runtime import GatewaySettings, create_gateway_server

DEFAULT_ALLOWED_HOSTS = ("127.0.0.1:*", "localhost:*", "[::1]:*")
DEFAULT_ALLOWED_ORIGINS = (
    "http://127.0.0.1:*",
    "http://localhost:*",
    "https://127.0.0.1:*",
    "https://localhost:*",
)


class StreamableHTTPApp:
    def __init__(self, manager: StreamableHTTPSessionManager) -> None:
        self.manager = manager

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.manager.handle_request(scope, receive, send)


class BearerTokenApp:
    def __init__(self, app: ASGIApp, token: str | None) -> None:
        self.app = app
        self.token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self.token is not None:
            headers = {key.lower(): value for key, value in scope.get("headers", [])}
            authorization = headers.get(b"authorization", b"").decode("latin-1")
            expected = f"Bearer {self.token}"
            if not hmac.compare_digest(authorization, expected):
                await JSONResponse(
                    {"error": "invalid_bearer_token"},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )(scope, receive, send)
                return
        await self.app(scope, receive, send)


def create_http_gateway_app(
    settings: GatewaySettings,
    *,
    token: str | None = None,
    allowed_hosts: Sequence[str] = DEFAULT_ALLOWED_HOSTS,
    allowed_origins: Sequence[str] = DEFAULT_ALLOWED_ORIGINS,
    session_idle_timeout: float = 900,
) -> Starlette:
    server = create_gateway_server(settings)
    manager = StreamableHTTPSessionManager(
        app=server,
        json_response=True,
        stateless=False,
        session_idle_timeout=session_idle_timeout,
        security_settings=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=list(allowed_hosts),
            allowed_origins=list(allowed_origins),
        ),
    )

    @asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncIterator[None]:
        async with manager.run():
            yield

    async def health(_: Request) -> Response:
        return JSONResponse(
            {
                "status": "ok",
                "transport": "streamable-http",
                "endpoint": "/mcp",
                "authentication": "bearer" if token else "none",
            }
        )

    async def metadata(_: Request) -> Response:
        return JSONResponse(
            {
                "name": "AgentGuard DataFlow Gateway",
                "transport": "streamable-http",
                "mcp_endpoint": "/mcp",
                "health_endpoint": "/health",
            }
        )

    mcp_app: ASGIApp = BearerTokenApp(StreamableHTTPApp(manager), token)
    return Starlette(
        routes=[
            Route("/", metadata, methods=["GET"]),
            Route("/health", health, methods=["GET"]),
            Route("/mcp", mcp_app),
        ],
        lifespan=lifespan,
    )


def validate_remote_binding(host: str, token: str | None) -> None:
    if host not in {"127.0.0.1", "localhost", "::1"} and not token:
        raise ValueError("A bearer token is required when binding MCP HTTP beyond localhost")
