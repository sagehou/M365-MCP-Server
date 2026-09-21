"""Token-provider interface used by the bounded Microsoft Graph client."""

from typing import Protocol

from ..auth.models import AuthContext


class GraphTokenProvider(Protocol):
    """Acquire one delegated Graph token for the authenticated tool caller."""

    def acquire_token(self, context: AuthContext) -> str: ...
