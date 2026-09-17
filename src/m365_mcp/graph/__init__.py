"""Microsoft Graph integration primitives."""

from .client import GraphClient, GraphResponse
from .errors import GraphApiError, GraphError, GraphPathError, GraphTransportError
from .mail import MailService

__all__ = [
    "GraphApiError",
    "GraphClient",
    "GraphError",
    "GraphPathError",
    "GraphResponse",
    "GraphTransportError",
    "MailService",
]
