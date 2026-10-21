"""Path containment for CLI-supplied paths (S8707 trust boundary, C4).

The CLI is the trust boundary: every user-supplied path (``<store>``,
``--doc``, ``--manifest``, ``migrate <doc>``) must resolve inside the
workspace base — the current working directory by default — before any file
I/O. ``resolve_within`` performs that containment check; callers catch
``ValueError`` (``PathEscapeError`` subclasses it) and surface it as exit 2
with the pinned ``securetrace:`` prefix (CC-001).

Relative input is checked against the base and returned as given, so
printed paths are unchanged (``data/backlog.json`` stays
``data/backlog.json``); absolute input must already lie inside the base and
is returned resolved. Nonexistent targets are allowed — only containment is
enforced here, existence is a caller concern.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["PathEscapeError", "resolve_within"]


class PathEscapeError(ValueError):
    """A CLI-supplied path escapes the workspace base (exit 2 at the CLI)."""


def resolve_within(raw: str | Path, base: str | Path | None = None) -> Path:
    """Contain *raw* within *base* (default: the current working directory).

    Returns:
        Path: the path as given for relative input (print-stable), or the
            resolved absolute path for absolute input.

    Raises:
        PathEscapeError: the resolved path is neither the base itself nor
            inside it.
    """
    base_resolved = Path(base).resolve() if base is not None else Path.cwd().resolve()
    candidate = Path(raw)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (base_resolved / candidate).resolve()
    if resolved != base_resolved and base_resolved not in resolved.parents:
        raise PathEscapeError(
            f"path {raw!r} escapes the workspace base {base_resolved}; "
            "CLI paths must stay inside the working directory"
        )
    return candidate if not candidate.is_absolute() else resolved
