"""MCP-safe input validation errors shared across tool services."""

from __future__ import annotations


class InvalidToolInputError(ValueError):
    """Raised when a caller-supplied tool argument fails validation before any
    provider call.

    These describe the client's own bad data rather than provider internals, so
    the tool layer may safely echo the ``param`` and machine-readable ``code``
    back to the caller. Subclasses ``ValueError`` to preserve existing callers
    that catch range/format errors generically.
    """

    def __init__(self, param: str, code: str, detail: str) -> None:
        super().__init__(f"{param}: {detail}")
        self.param = param
        self.code = code
        self.detail = detail
