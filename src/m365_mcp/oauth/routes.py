"""Public MCP OAuth discovery and registration routes."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any
from urllib.parse import parse_qsl

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.responses import Response
from pydantic import ValidationError

from ..auth.settings import Settings
from .authorization import OAuthAuthorizationService
from .completion import authorization_completion_response
from .errors import OAuthProtocolError
from .models import (
    OAuthAuthorizationCodeTokenRequest,
    OAuthAuthorizationRequest,
    OAuthClientRegistration,
    OAuthRefreshTokenRequest,
    SUPPORTED_GRANT_TYPES,
)
from .registry import OAuthClientRegistry, OAuthRegistrationUnavailableError


logger = logging.getLogger(__name__)


def _oauth_error(description: str, *, status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": "invalid_client_metadata",
            "error_description": description,
        },
    )


def _protocol_error(error: OAuthProtocolError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={
            "error": error.error,
            "error_description": error.description,
        },
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )


def _single_value_parameters(items: list[tuple[str, str]]) -> dict[str, str]:
    parameters: dict[str, str] = {}
    for name, value in items:
        if name in parameters:
            raise OAuthProtocolError(
                "invalid_request",
                "duplicate parameters are not allowed",
            )
        parameters[name] = value
    return parameters


def _registration_error_summary(error: ValidationError | ValueError) -> str:
    """Return useful registration diagnostics without echoing client metadata."""

    if isinstance(error, ValidationError):
        summaries = []
        for detail in error.errors(include_input=False, include_url=False):
            location = ".".join(str(item) for item in detail["loc"])
            summaries.append(f"{location}: {detail['msg']}")
        return "; ".join(summaries)[:1000]
    return str(error)[:1000]


def create_oauth_router(
    settings: Settings,
    registry: OAuthClientRegistry,
    authorization_service: OAuthAuthorizationService,
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
        content_type = request.headers.get("content-type", "")
        if content_type.split(";", 1)[0].strip().casefold() != "application/json":
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
            redirect_uris = payload.get("redirect_uris")
            logger.warning(
                "OAuth client registration rejected",
                extra={
                    "error_type": type(exc).__name__,
                    "error": _registration_error_summary(exc),
                    "redirect_uri_count": (
                        len(redirect_uris) if isinstance(redirect_uris, list) else 0
                    ),
                },
            )
            return _oauth_error("client metadata is invalid")
        except OAuthRegistrationUnavailableError:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "temporarily_unavailable",
                    "error_description": (
                        "client registration is temporarily unavailable"
                    ),
                },
            )
        return JSONResponse(status_code=201, content=client.registration_response())

    @router.get("/oauth/authorize", response_model=None)
    async def authorize(request: Request) -> JSONResponse | RedirectResponse:
        try:
            parameters = _single_value_parameters(
                list(request.query_params.multi_items())
            )
            authorization_request = OAuthAuthorizationRequest.model_validate(parameters)
            authorization_uri = await authorization_service.authorize(
                authorization_request
            )
        except ValidationError:
            return _protocol_error(
                OAuthProtocolError(
                    "invalid_request",
                    "authorization request is invalid",
                )
            )
        except OAuthProtocolError as exc:
            return _protocol_error(exc)
        return RedirectResponse(
            authorization_uri,
            status_code=302,
            headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
        )

    @router.get("/oauth/callback", response_model=None)
    async def entra_callback(request: Request) -> Response:
        try:
            parameters = _single_value_parameters(
                list(request.query_params.multi_items())
            )
            redirect_uri = await authorization_service.complete(parameters)
        except OAuthProtocolError as exc:
            logger.warning(
                "OAuth callback rejected",
                extra={
                    "event": "oauth_callback_failed",
                    "error_type": type(exc).__name__,
                    "oauth_error": exc.error,
                    "status_code": exc.status_code,
                },
            )
            return _protocol_error(exc)
        except Exception as exc:
            logger.exception(
                "OAuth callback failed unexpectedly",
                extra={
                    "event": "oauth_callback_failed",
                    "error_type": type(exc).__name__,
                    "status_code": 500,
                },
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": "server_error",
                    "error_description": "OAuth callback failed",
                },
                headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
            )
        return authorization_completion_response(redirect_uri)

    @router.post("/oauth/token")
    async def token(request: Request) -> JSONResponse:
        content_type = request.headers.get("content-type", "").split(";", 1)[0]
        if content_type.strip().casefold() != "application/x-www-form-urlencoded":
            return _protocol_error(
                OAuthProtocolError(
                    "invalid_request",
                    "token request must be application/x-www-form-urlencoded",
                )
            )
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                parsed_content_length = int(content_length)
                if parsed_content_length < 0 or parsed_content_length > 16_384:
                    raise OAuthProtocolError(
                        "invalid_request", "token request is too large"
                    )
            except ValueError:
                return _protocol_error(
                    OAuthProtocolError("invalid_request", "content length is invalid")
                )
            except OAuthProtocolError as exc:
                return _protocol_error(exc)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 16_384:
                return _protocol_error(
                    OAuthProtocolError("invalid_request", "token request is too large")
                )
        grant_type: str | None = None
        try:
            items = parse_qsl(
                body.decode("utf-8"),
                keep_blank_values=True,
                strict_parsing=True,
                max_num_fields=10,
            )
            parameters = _single_value_parameters(items)
            grant_type = parameters.get("grant_type")
            if not grant_type:
                raise OAuthProtocolError(
                    "invalid_request",
                    "grant_type is required",
                )
            if grant_type == "authorization_code":
                token_request = OAuthAuthorizationCodeTokenRequest.model_validate(
                    parameters
                )
                response = await authorization_service.exchange(token_request)
            elif grant_type == "refresh_token":
                refresh_request = OAuthRefreshTokenRequest.model_validate(parameters)
                response = await authorization_service.refresh(refresh_request)
            else:
                raise OAuthProtocolError(
                    "unsupported_grant_type",
                    "grant_type is not supported",
                )
        except (UnicodeDecodeError, ValueError, ValidationError) as exc:
            error = OAuthProtocolError("invalid_request", "token request is invalid")
            authorization_service.audit_logger.token_failed(
                grant_type=(
                    grant_type if grant_type in SUPPORTED_GRANT_TYPES else "unknown"
                ),
                error_type=type(exc).__name__,
                oauth_error=error.error,
                status_code=error.status_code,
            )
            return _protocol_error(error)
        except OAuthProtocolError as exc:
            authorization_service.audit_logger.token_failed(
                grant_type=(
                    grant_type if grant_type in SUPPORTED_GRANT_TYPES else "unknown"
                ),
                error_type=type(exc).__name__,
                oauth_error=exc.error,
                status_code=exc.status_code,
            )
            return _protocol_error(exc)
        return JSONResponse(
            status_code=200,
            content=response.as_dict(),
            headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
        )

    return router
