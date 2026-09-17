"""ASGI application for the M365 MCP Server."""

from typing import Any, Literal

from fastapi import FastAPI
from fastmcp import FastMCP
from pydantic import BaseModel

from . import __version__
from .auth import BearerAuthMiddleware, JwtValidator, Settings
from .auth.middleware import TokenValidator


class HealthResponse(BaseModel):
    """Stable response returned by the service health endpoint."""

    status: Literal["ok"] = "ok"
    service: str = "m365-mcp-server"
    version: str = __version__


async def health() -> HealthResponse:
    """Report whether the HTTP application is ready to receive requests."""

    return HealthResponse()


def create_app(
    *,
    settings: Settings | None = None,
    token_validator: TokenValidator | None = None,
    mcp_server: FastMCP | None = None,
    mcp_http_app: Any | None = None,
) -> FastAPI:
    """Create an application with a protected MCP endpoint."""

    server = mcp_server or FastMCP("M365 MCP Server")
    http_app = mcp_http_app or server.http_app(path="/")
    validator = token_validator or JwtValidator(settings or Settings())

    application = FastAPI(
        title="M365 MCP Server",
        version=__version__,
        description="Microsoft 365 MCP gateway.",
        lifespan=http_app.lifespan,
    )
    application.add_api_route(
        "/health",
        health,
        methods=["GET"],
        response_model=HealthResponse,
        tags=["system"],
    )
    application.add_api_route(
        "/healthz",
        health,
        methods=["GET"],
        response_model=HealthResponse,
        include_in_schema=False,
    )
    application.add_middleware(BearerAuthMiddleware, validator=validator)
    application.mount("/mcp", http_app)
    return application


mcp = FastMCP("M365 MCP Server")
mcp_app = mcp.http_app(path="/")
app = create_app(mcp_server=mcp, mcp_http_app=mcp_app)
