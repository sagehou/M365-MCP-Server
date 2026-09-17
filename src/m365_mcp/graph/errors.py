"""Sanitized errors raised by the Microsoft Graph integration layer."""


class GraphError(Exception):
    """Base error for Graph transport and API failures."""


class GraphPathError(GraphError):
    """The requested path would cross the delegated identity boundary."""


class GraphTransportError(GraphError):
    """The Graph request could not be completed after retries."""


class GraphApiError(GraphError):
    """Graph returned an HTTP error without retaining sensitive response text."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        request_id: str | None = None,
        retry_after: float | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.request_id = request_id
        self.retry_after = retry_after
        super().__init__(f"Microsoft Graph request failed: {status_code} {code}")
