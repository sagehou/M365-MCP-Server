"""Safe OAuth errors that may cross the public HTTP seam."""

from __future__ import annotations


class OAuthProtocolError(Exception):
    """Protocol error with a stable public code and sanitized description."""

    def __init__(
        self,
        error: str,
        description: str,
        *,
        status_code: int = 400,
    ) -> None:
        super().__init__(description)
        self.error = error
        self.description = description
        self.status_code = status_code
