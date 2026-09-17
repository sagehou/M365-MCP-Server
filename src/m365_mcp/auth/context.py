"""Access validated identity and assertion from a FastAPI request."""

from fastapi import Request

from .errors import AuthenticationError
from .models import AuthContext

IDENTITY_STATE_KEY = "m365_identity"
ACCESS_TOKEN_STATE_KEY = "m365_access_token"


def get_auth_context(request: Request) -> AuthContext:
    """Return the middleware-produced context or fail closed."""

    identity = getattr(request.state, IDENTITY_STATE_KEY, None)
    access_token = getattr(request.state, ACCESS_TOKEN_STATE_KEY, None)
    if identity is None or not isinstance(access_token, str) or not access_token:
        raise AuthenticationError("The request is not authenticated")
    return AuthContext(identity=identity, access_token=access_token)
