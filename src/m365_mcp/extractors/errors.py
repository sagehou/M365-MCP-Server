"""Errors raised while reading email attachment content."""


class AttachmentExtractionError(Exception):
    """Base class for safe, client-facing attachment extraction failures."""


class AttachmentTooLargeError(AttachmentExtractionError):
    """The attachment exceeds the configured server-side byte limit."""


class UnsupportedAttachmentError(AttachmentExtractionError):
    """The attachment format is not enabled for text extraction."""


class InvalidAttachmentError(AttachmentExtractionError):
    """The attachment content could not be decoded or parsed."""
