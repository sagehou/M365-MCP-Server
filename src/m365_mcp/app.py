"""ASGI application for the M365 MCP Server."""

from typing import Literal

from fastapi import FastAPI
from fastmcp import FastMCP
from pydantic import BaseModel

from . import __version__


class HealthResponse(BaseModel):
    """Stable response returned by the service health endpoint."""

    status: Literal["ok"] = "ok"
    service: str = "m365-mcp-server"
    version: str = __version__


mcp = FastMCP("M365 MCP Server")
mcp_app = mcp.http_app(path="/")

app = FastAPI(
    title="M365 MCP Server",
    version=__version__,
    description="Microsoft 365 MCP gateway scaffold.",
    lifespan=mcp_app.lifespan,
)


@app.get("/health", response_model=HealthResponse, tags=["system"])
@app.get("/healthz", response_model=HealthResponse, include_in_schema=False)
async def health() -> HealthResponse:
    """Report whether the HTTP application is ready to receive requests."""

    return HealthResponse()


app.mount("/mcp", mcp_app)
