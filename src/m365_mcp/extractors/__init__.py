"""Attachment extraction primitives."""

from .attachment import (
    DEFAULT_MAX_BYTES,
    DEFAULT_MAX_TEXT_CHARS,
    AttachmentExtractor,
    AttachmentExtractorRegistry,
    AttachmentInput,
    DocxAttachmentExtractor,
    ExtractionResult,
    PdfAttachmentExtractor,
    PptxAttachmentExtractor,
    TextAttachmentExtractor,
    XlsxAttachmentExtractor,
)
from .errors import (
    AttachmentExtractionError,
    AttachmentTooLargeError,
    InvalidAttachmentError,
    UnsupportedAttachmentError,
)

__all__ = [
    "AttachmentExtractionError",
    "AttachmentExtractor",
    "AttachmentExtractorRegistry",
    "AttachmentInput",
    "AttachmentTooLargeError",
    "DEFAULT_MAX_BYTES",
    "DEFAULT_MAX_TEXT_CHARS",
    "DocxAttachmentExtractor",
    "ExtractionResult",
    "InvalidAttachmentError",
    "PdfAttachmentExtractor",
    "PptxAttachmentExtractor",
    "TextAttachmentExtractor",
    "UnsupportedAttachmentError",
    "XlsxAttachmentExtractor",
]
