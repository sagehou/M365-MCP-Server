"""Public MCP OAuth discovery and registration routes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from ..auth.settings import Settings
from .models import OAuthClientRegistration
from .registry import OAuthClientRegistry, OAuthRegistrationUnavailableError


def _oauth_error(description: str, *, status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": "invalid_client_metadata",
            "error_description": description,
        },
    )


def create_oauth_router(
    settings: Settings,
    registry: OAuthClientRegistry,
) -> APIRouter:
    """Create the feature-flagged OAuth discovery interface."""

    settings.validate_oauth_discovery_configuration()
    issuer = settings.normalized_oauth_issuer_url
    if settings.mcp_public_url is None:
        raise RuntimeError("MCP_PUBLIC_URL was not validated")
    router = APIRouter(include_in_schema=False)

    @router.get("/.well-known/oauth-protected-resource")
    async def protected_resource_metadata() -> Mapping[str, object]:
        return {
            "resource": settings.mcp_public_url,
            "authorization_servers": [issuer],
            "scopes_supported": sorted(settings.required_scopes),
        }

    @router.get("/.well-known/oauth-authorization-server")
    async def authorization_server_metadata() -> Mapping[str, object]:
        return {
            "issuer": issuer,
            "authorization_endpoint": f"{issuer}/oauth/authorize",
            "token_endpoint": f"{issuer}/oauth/token",
            "registration_endpoint": f"{issuer}/oauth/register",
            "scopes_supported": sorted(settings.required_scopes),
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
        }

    @router.post("/oauth/register")
    async def register_client(request: Request) -> JSONResponse:
        if request.headers.get("content-type", "").split(";", 1)[0].strip().casefold() != "application/json":
            return _oauth_error("registration body must be application/json")
        try:
            payload: Any = await request.json()
        except ValueError:
            return _oauth_error("registration body is not valid JSON")
        if not isinstance(payload, dict):
            return _oauth_error("registration body must be a JSON object")
        try:
            registration = OAuthClientRegistration.model_validate(payload)
            client = await registry.register(registration)
        except (ValidationError, ValueError) as exc:
            return _oauth_error(str(exc))
        except OAuthRegistrationUnavailableError:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "temporarily_unavailable",
                    "error_description": "client registration is temporarily unavailable",
                },
            )
        return JSONResponse(status_code=201, content=client.registration_response())

    return router
