"""Package-level smoke tests: import, version, CLI entrypoint.

Behavioral tests for each subpackage land with their backlog items
(B3/B4); these pin the package contract at the skeleton stage.
"""

from __future__ import annotations

import re

import pytest

import securetrace
from securetrace.__main__ import main


def test_version_is_semver() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", securetrace.__version__)


def test_all_subpackages_import() -> None:
    import securetrace.algorithms  # noqa: F401
    import securetrace.backlog  # noqa: F401
    import securetrace.lessons  # noqa: F401
    import securetrace.pipeline  # noqa: F401
    import securetrace.rmf  # noqa: F401


def test_cli_reports_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert securetrace.__version__ in capsys.readouterr().out


def test_cli_requires_subcommand() -> None:
    """No subcommand: argparse rejects with SystemExit(2) (usage on stderr)."""
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code == 2
