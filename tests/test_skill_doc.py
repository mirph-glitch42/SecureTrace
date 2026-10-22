"""Pin the agent-facing skill doc (skills/securetrace/SKILL.md) against rot.

B9: the SKILL.md is the canonical "how an agent uses SecureTrace" reference.
This test asserts the parts that must stay true: valid Bionic front matter
(name matches the folder, kebab-case, bounded description, model invocation
enabled) and that every core command / contract the guide must teach is
still referenced. When a command or contract changes, update SKILL.md in
the same change so this guard keeps passing.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "securetrace"
SKILL_FILE = SKILL_DIR / "SKILL.md"

KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

# Every command / contract an agent must be able to find in the guide.
# B10 WI 10: the legacy markdown-index surface (scripts/backlog_index.py,
# scripts/manage_lessons.py, the sync/next-id verbs) is retired — the guide
# pins the store-based surface and the remaining scripts/ helpers only.
REQUIRED_REFERENCES = (
    "securetrace backlog upsert",
    "securetrace backlog progress",
    "securetrace backlog show",
    "securetrace backlog render",
    "securetrace backlog check",
    "securetrace lessons add",
    "securetrace lessons set-intro",
    "securetrace lessons show",
    "securetrace lessons render",
    "securetrace lessons check",
    "securetrace algorithms upsert",
    "securetrace algorithms show",
    "securetrace algorithms render",
    "securetrace algorithms check",
    "securetrace docs render-all",
    "securetrace docs check-all",
    "securetrace migrate",
    "securetrace rmf build",
    "make setup",
    "make gate",
    "make rmf-bundle",
    "make docs-render",
    "scripts/algorithm_index.py",
    "scripts/check_workflow_yaml.py",
    "BACKLOG.md",
    "LESSONS_LEARNED.md",
    "algorithms/INDEX.md",
    "docs/dow-requirements.md",
    "CONSISTENCY.md",
)


def _front_matter(text: str) -> dict[str, str]:
    """Parse the YAML front matter block (flat key: value lines only)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md must start with a '---' front matter line")
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise ValueError(f"unparseable front matter line: {line!r}")
        fields[key.strip()] = value.strip()
    raise ValueError("front matter is not terminated by a closing '---' line")


def test_skill_file_exists_in_matching_folder() -> None:
    assert SKILL_DIR.is_dir(), f"missing skill folder {SKILL_DIR}"
    assert SKILL_FILE.is_file(), f"missing {SKILL_FILE}"


def test_front_matter_is_valid() -> None:
    fields = _front_matter(SKILL_FILE.read_text(encoding="utf-8"))
    name = fields.get("name", "")
    assert name == SKILL_DIR.name, "front matter name must match the folder name"
    assert KEBAB.fullmatch(name), "name must be kebab-case"
    assert len(name) <= 63, "name must be at most 63 characters"
    assert fields.get("display-name"), "display-name is expected"
    desc = fields.get("description", "")
    assert desc, "description is required"
    assert len(desc) <= 300, "description must be at most 300 characters"


def test_model_invocation_is_enabled() -> None:
    fields = _front_matter(SKILL_FILE.read_text(encoding="utf-8"))
    assert fields.get("disable-model-invocation", "").lower() != "true", (
        "the agent must be able to read this skill on its own"
    )


@pytest.mark.parametrize("reference", REQUIRED_REFERENCES)
def test_core_commands_and_contracts_are_documented(reference: str) -> None:
    body = SKILL_FILE.read_text(encoding="utf-8")
    assert reference in body, (
        f"SKILL.md no longer references {reference!r} — update it in the same"
        " change as the change that dropped it"
    )
