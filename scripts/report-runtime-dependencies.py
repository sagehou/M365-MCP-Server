"""Print the resolved runtime dependency versions used by GitHub Actions."""

from __future__ import annotations

from importlib import metadata


PACKAGES = (
    ("fastmcp", "direct"),
    ("fastmcp-slim", "transitive via fastmcp"),
    ("mcp", "transitive via fastmcp"),
    ("mcp-types", "transitive via mcp/fastmcp"),
    ("authlib", "transitive via fastmcp"),
    ("joserfc", "transitive via fastmcp"),
    ("httpx", "direct Graph/OIDC client"),
    ("httpx2", "transitive FastMCP HTTP stack"),
    ("msal", "direct Entra OBO client"),
    ("PyJWT", "direct JWT validation"),
    ("fastapi", "direct ASGI application"),
    ("starlette", "transitive via FastAPI/FastMCP"),
    ("pydantic", "direct models/settings"),
)


def main() -> None:
    print("package\tversion\trelationship")
    for package, relationship in PACKAGES:
        try:
            version = metadata.version(package)
        except metadata.PackageNotFoundError:
            version = "not-installed"
        print(f"{package}\t{version}\t{relationship}")


if __name__ == "__main__":
    main()
