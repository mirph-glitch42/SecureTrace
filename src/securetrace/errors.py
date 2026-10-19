"""Exception hierarchy for the SecureTrace core.

The pure core modules (``securetrace.backlog.index``,
``securetrace.algorithms.registry``, ``securetrace.lessons.record``) work on
plain text and signal problems with exceptions instead of printing or exiting;
the command layer (``securetrace.cli``) maps them onto the pinned exit codes:

- ``StaleIndex``   → exit 1 (index out of sync with the body; fix with ``sync``)
- ``FormatError``  → exit 2 (malformed document, or an internal invariant failed)
- ``InvalidInput`` → exit 2 (command input rejected by a guard, G4–G9)

Exception messages are part of the pinned user-visible contract: the command
layer prints them verbatim as ``{prog}: {message}`` on stderr, so core
messages must not change without a documented contract change.
"""

from __future__ import annotations

__all__ = ["FormatError", "InvalidInput", "SecureTraceError", "StaleIndex"]


class SecureTraceError(Exception):
    """Base class for all SecureTrace errors."""


class StaleIndex(SecureTraceError):
    """The index block is out of sync with the file body (exit 1)."""


class FormatError(SecureTraceError):
    """The document is malformed, or an internal invariant was violated (exit 2)."""


class InvalidInput(SecureTraceError):
    """Command input was rejected by a guard (G4–G9) (exit 2)."""
