"""ASGI application for the M365 MCP Server."""

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Literal

from fastapi import FastAPI
from fastmcp import FastMCP
from pydantic import BaseModel

from . import __version__
from .auth import BearerAuthMiddleware, JwtValidator, MsalOboService, Settings
from .auth.middleware import TokenValidator
from .graph import GraphClient, MailService
from .extractors import AttachmentExtractorRegistry
from .mail import MailToolService, register_mail_tools
from .oauth import (
    AesGcmTokenProtector,
    DynamicClientRegistry,
    MsalEntraAuthorizationClient,
    OAuthAuthorizationService,
    OAuthClientRegistry,
    OAuthSessionService,
    OAuthStore,
    SQLiteOAuthStore,
    create_oauth_router,
)
from .security import AuditLogger, SecurityHeadersMiddleware


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
    mail_service: MailService | None = None,
    audit_logger: AuditLogger | None = None,
    oauth_registry: OAuthClientRegistry | None = None,
    oauth_store: OAuthStore | None = None,
    oauth_authorization_service: OAuthAuthorizationService | None = None,
) -> FastAPI:
    """Create an application with protected MCP mail tools."""

    configured_settings = settings or Settings()
    configured_settings.validate_oauth_authorization_configuration()
    server = mcp_server or FastMCP("M365 MCP Server", mask_error_details=True)
    http_app = mcp_http_app or server.http_app(
        path="/", stateless_http=True, json_response=True
    )
    validator = token_validator or JwtValidator(configured_settings)

    graph_client: GraphClient | None = None
    if mail_service is None:
        graph_client = GraphClient(
            configured_settings,
            MsalOboService(configured_settings),
        )
        mail_service = MailService(graph_client)
    attachment_extractor = AttachmentExtractorRegistry(
        max_bytes=configured_settings.attachment_max_bytes,
        max_text_chars=configured_settings.attachment_max_text_chars,
    )
    register_mail_tools(
        server,
        MailToolService(mail_service, attachment_extractor=attachment_extractor),
        audit_logger=audit_logger or AuditLogger(),
    )

    registry = oauth_registry
    authorization_service = oauth_authorization_service
    store = oauth_store
    if configured_settings.oauth_enabled:
        store = store or SQLiteOAuthStore(configured_settings.oauth_database_path)
        registry = registry or DynamicClientRegistry(
            store,
            configured_settings.normalized_oauth_issuer_url,
        )
        if authorization_service is None:
            entra_client = MsalEntraAuthorizationClient(configured_settings)
            token_protector = AesGcmTokenProtector(
                configured_settings.oauth_encryption_key_bytes
            )
            session_service = OAuthSessionService(
                configured_settings,
                store,
                entra_client,
                validator,
                token_protector,
            )
            authorization_service = OAuthAuthorizationService(
                configured_settings,
                registry,
                store,
                entra_client,
                validator,
                token_protector,
                session_service,
            )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        async with http_app.lifespan(application):
            try:
                if registry is not None:
                    await registry.initialize()
                yield
            finally:
                if graph_client is not None:
                    await graph_client.aclose()

    application = FastAPI(
        title="M365 MCP Server",
        version=__version__,
        description="Microsoft 365 MCP gateway.",
        lifespan=lifespan,
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
    if configured_settings.oauth_enabled:
        if registry is None or authorization_service is None:
            raise RuntimeError("OAuth authorization modules are unavailable")
        application.include_router(
            create_oauth_router(
                configured_settings,
                registry,
                authorization_service,
            )
        )
    application.add_middleware(
        BearerAuthMiddleware,
        validator=validator,
        resource_metadata_url=(
            configured_settings.protected_resource_metadata_url
            if configured_settings.oauth_enabled
            else None
        ),
    )
    application.add_middleware(SecurityHeadersMiddleware)
    application.mount("/mcp", http_app)
    return application


mcp = FastMCP("M365 MCP Server", mask_error_details=True)
mcp_app = mcp.http_app(path="/", stateless_http=True, json_response=True)
app = create_app(mcp_server=mcp, mcp_http_app=mcp_app)
