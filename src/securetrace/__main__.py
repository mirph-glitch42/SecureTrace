"""SecureTrace command-line entrypoint (skeleton).

``main()`` is the single entrypoint referenced by the ``securetrace``
console script in pyproject.toml. Subcommands (backlog, lessons, algorithms,
rmf, gate) are added with backlog B3; until then the CLI reports its version
and that no subcommands are implemented yet.
"""

from __future__ import annotations

import argparse
import sys

from securetrace import __version__


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch. Returns a process exit code."""
    parser = argparse.ArgumentParser(
        prog="securetrace",
        description="Agentic tooling for secure, traceable software development.",
    )
    parser.add_argument("--version", action="version", version=f"securetrace {__version__}")
    args = parser.parse_args(argv)
    print(f"securetrace {__version__} — no subcommands implemented yet (backlog B3)")
    _ = args
    return 0


if __name__ == "__main__":
    sys.exit(main())
