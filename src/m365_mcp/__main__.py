"""Process entry point for running the M365 MCP Server."""

import os

import uvicorn

from .app import app


def main() -> None:
    """Run the HTTP server using environment-configurable bind settings."""

    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
