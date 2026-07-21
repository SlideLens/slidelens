"""Typed exceptions for deck / audio ingest."""

from __future__ import annotations


class IngestError(Exception):
    """Base for all typed deck/audio ingest failures."""


class CorruptedFileError(IngestError):
    """The input file is not a valid PPTX/PDF/media container."""


class UnsupportedDeckFormatError(IngestError):
    """The deck extension is not in ``AllowedDeckFormat``."""


class PasswordProtectedError(IngestError):
    """The input file is encrypted and cannot be opened without a password."""


class EmptyDeckError(IngestError):
    """The deck has zero slides/pages."""


class DeckTooLargeError(IngestError):
    """The deck exceeds the size or slide-count limit."""


class RenderTimeoutError(IngestError):
    """PPTX→PDF rendering did not complete within the timeout budget."""


class NoAudioTrackError(IngestError):
    """The media file has no extractable audio track."""


class AudioTooLongError(IngestError):
    """Запись питча длиннее допустимого — транскрипция тарифицируется поминутно."""
